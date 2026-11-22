import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from loganalyzer.models import Event
from loganalyzer.parsers.auth import parse_auth
from loganalyzer.parsers.nginx import parse_nginx
from loganalyzer.rules import Rules, load_rules
from loganalyzer.storage import Checkpoint, open_database, read_checkpoint, write_batch


@pytest.fixture
def db(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    with closing(open_database(tmp_path / "logs.sqlite3")) as connection:
        yield connection


@pytest.fixture
def rules() -> Rules:
    config = load_rules(Path("rules.yaml"))
    config.brute_force.threshold = 3
    config.credential_stuffing.threshold = 3
    config.scan.missing_threshold = 3
    config.scan.paths_threshold = 3
    return config


def login(t: int, ip: str = "192.0.2.1", user: str = "alex") -> Event:
    line = f"Jan  1 00:00:00 host sshd: Failed password for {user} from {ip} port 1234"
    event = parse_auth(line, datetime(2025, 1, 1, tzinfo=UTC))
    assert event
    return event.model_copy(update={"ts": t})


def request(t: int, path: str, status: int) -> Event:
    line = f'192.0.2.2 - - [01/Jan/2025:00:00:00 +0000] "GET {path} HTTP/1.1" {status} 9 "-" "-"'
    return parse_nginx(line).model_copy(update={"ts": t})


def store(db: sqlite3.Connection, rules: Rules, *events: Event) -> None:
    previous = read_checkpoint(db, "test")
    offset = (previous.offset if previous else 0) + len(events)
    write_batch(db, events, Checkpoint("test", "1", offset), rules, previous)


def test_boundary_restart_and_separate_incidents(
    db: sqlite3.Connection, rules: Rules
) -> None:
    store(db, rules, login(0), login(30), login(60), login(60, "192.0.2.9"))
    store(db, rules, login(60), login(150), login(151), login(152))
    rows = db.execute(
        "SELECT rule, count, first_seen, last_seen FROM alerts ORDER BY id"
    ).fetchall()
    assert rows == [("brute_force", 4, 0, 60), ("brute_force", 3, 150, 152)]


def test_distinct_users_and_outside_window(
    db: sqlite3.Connection, rules: Rules
) -> None:
    store(
        db, rules, login(0, user="one"), login(60, user="two"), login(61, user="three")
    )
    assert db.execute("SELECT count(*) FROM alerts").fetchone() == (0,)
    store(db, rules, login(62, user="three"), login(63, user="four"))
    row = db.execute(
        "SELECT count, details FROM alerts WHERE rule = 'credential_stuffing'"
    ).fetchone()
    assert row == (4, "3 distinct usernames")


@pytest.mark.parametrize(
    ("paths", "status"), [(["/a", "/a", "/a"], 404), (["/a", "/b", "/c"], 200)]
)
def test_scan_branches_across_batches(
    db: sqlite3.Connection, rules: Rules, paths: list[str], status: int
) -> None:
    store(db, rules, request(0, paths[0], status), request(30, paths[1], status))
    store(db, rules, request(60, paths[2], status), request(60, paths[2], status))
    assert db.execute("SELECT rule, count FROM alerts").fetchall() == [("scan", 4)]


def test_late_events_and_expired_requests(db: sqlite3.Connection, rules: Rules) -> None:
    store(
        db,
        rules,
        request(100, "/a", 200),
        request(50, "/b", 200),
        request(39, "/c", 200),
    )
    assert db.execute("SELECT count(*) FROM alerts").fetchone() == (0,)
    store(db, rules, request(55, "/c", 200))
    assert db.execute("SELECT first_seen, last_seen FROM alerts").fetchone() == (
        50,
        100,
    )


def test_failed_checkpoint_rolls_back_alert(
    db: sqlite3.Connection, rules: Rules
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        write_batch(db, [login(1)] * 3, Checkpoint("test", "1", -1), rules)
    assert db.execute("SELECT count(*) FROM alerts").fetchone() == (0,)


def test_rules_reject_invalid_threshold(tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(
        Path("rules.yaml").read_text().replace("threshold: 6", "threshold: 0")
    )
    with pytest.raises(ValidationError, match="brute_force.threshold"):
        load_rules(path)
