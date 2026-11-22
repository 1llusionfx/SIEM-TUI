from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pytest_benchmark.fixture import BenchmarkFixture

from loganalyzer.ingest import ingest_file
from loganalyzer.rules import load_rules
from loganalyzer.storage import open_database


def test_ingest_5000_lines(benchmark: BenchmarkFixture, tmp_path: Path) -> None:
    path = tmp_path / "access.log"
    start = datetime(2025, 1, 1, tzinfo=UTC)
    with path.open("w", encoding="utf-8") as stream:
        for i in range(5000):
            stamp = (start + timedelta(seconds=i)).strftime("%H:%M:%S")
            stream.write(
                f"192.0.2.{i % 5 + 1} - - [01/Jan/2025:{stamp} +0000] "
                f'"GET /page-{i % 47} HTTP/1.1" 404 40 "-" "Demo/1.0"\n'
            )
    rules = load_rules(Path("rules.yaml"))
    run = 0

    def ingest() -> int:
        nonlocal run
        run += 1
        with closing(open_database(tmp_path / f"{run}.sqlite3")) as db:
            return ingest_file(db, path, "nginx", rules).events

    count = benchmark.pedantic(ingest, rounds=5, iterations=1)  # type: ignore[no-untyped-call]
    assert count == 5000
