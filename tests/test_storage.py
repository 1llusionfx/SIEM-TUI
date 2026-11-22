import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from loganalyzer.ingest import parse_auth_batch
from loganalyzer.storage import Checkpoint, open_database, read_checkpoint, write_batch


def test_batches_and_checkpoints_survive_reopening(tmp_path: Path) -> None:
    path = tmp_path / "logs.sqlite3"
    line = "Jan  1 01:00:00 demo sshd: Invalid user guest from 192.0.2.2 port 4200"
    batch = parse_auth_batch([line, line], datetime(2025, 1, 1, tzinfo=UTC))
    checkpoint = Checkpoint("auth.log", "1:20", 144)
    with closing(open_database(path)) as db:
        assert db.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert read_checkpoint(db, "auth.log") is None
        write_batch(db, batch.events, checkpoint)
        with pytest.raises(sqlite3.IntegrityError):
            write_batch(db, batch.events, Checkpoint("auth.log", "1:21", -1))
        assert read_checkpoint(db, "auth.log") == checkpoint
    with closing(open_database(path)) as db:
        assert db.execute("SELECT raw FROM events ORDER BY id").fetchall() == [
            (line,),
            (line,),
        ]
        assert read_checkpoint(db, "auth.log") == checkpoint
        rotated = Checkpoint("auth.log", "1:21", 0)
        write_batch(db, [], rotated)
        assert read_checkpoint(db, "auth.log") == rotated
