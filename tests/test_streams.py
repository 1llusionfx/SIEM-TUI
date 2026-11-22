from contextlib import closing
from pathlib import Path

import pytest
from typer.testing import CliRunner

from loganalyzer.cli import app
from loganalyzer.ingest import Totals
from loganalyzer.replay import replay_file
from loganalyzer.rules import load_rules
from loganalyzer.storage import open_database, read_checkpoint
from loganalyzer.tail import read_available


def record(second: int) -> bytes:
    return (
        f"192.0.2.1 - - [01/Jan/2025:00:00:{second:02d} +0000] "
        f'"GET /item-{second} HTTP/1.1" 404 24 "-" "sample"\n'
    ).encode()


def test_watch_restart_partial_rotation_and_truncation(tmp_path: Path) -> None:
    path = tmp_path / "access.log"
    db_path = tmp_path / "events.db"
    config = load_rules(Path("rules.yaml"))
    totals = Totals()
    with closing(open_database(db_path)) as db:
        assert not read_available(db, path, "nginx", config, totals)
        path.write_bytes(record(1) + record(2)[:20])
        read_available(db, path, "nginx", config, totals)
        assert totals.events == 1
    with path.open("ab") as stream:
        stream.write(record(2)[20:])
    path.rename(path.with_suffix(".log.1"))
    path.write_bytes(record(3) + record(4))
    with closing(open_database(db_path)) as db:
        while read_available(db, path, "nginx", config, totals):
            pass
        path.write_bytes(record(5))
        read_available(db, path, "nginx", config, totals)
        read_available(db, path, "nginx", config, totals)
        assert totals == Totals(events=5)
        rows = db.execute("SELECT raw FROM events ORDER BY id").fetchall()
        assert [row[0] for row in rows] == [
            record(i).decode().strip() for i in range(1, 6)
        ]


def test_replay_scales_gaps_without_advancing_ingest(tmp_path: Path) -> None:
    path = tmp_path / "access.log"
    path.write_bytes(record(1) + b"broken\n" + record(11) + record(10) + record(21))
    now = 50.0
    delays = []

    def sleep(seconds: float) -> None:
        nonlocal now
        delays.append(seconds)
        now += seconds

    with closing(open_database(tmp_path / "demo.db")) as db:
        totals = replay_file(
            db, path, "nginx", load_rules(Path("rules.yaml")), 10, sleep, lambda: now
        )
        assert totals == Totals(events=4, malformed=1)
        assert delays == [1, 1]
        assert read_checkpoint(db, str(path.resolve())) is None


@pytest.mark.parametrize("speed", ["0", "-1", "nan", "inf"])
def test_replay_cli_rejects_invalid_speed(tmp_path: Path, speed: str) -> None:
    result = CliRunner().invoke(
        app,
        [
            "replay",
            str(tmp_path / "auth.log"),
            "--speed",
            speed,
            "--db",
            str(tmp_path / "demo.db"),
        ],
    )
    assert result.exit_code != 0
    assert "positive finite" in result.output
