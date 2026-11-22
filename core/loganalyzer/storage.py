import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .models import Event

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY, ts INTEGER NOT NULL, source TEXT NOT NULL,
    ip TEXT NOT NULL, user TEXT, event_type TEXT NOT NULL, raw TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_ip_ts ON events(ip, ts);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY, rule TEXT NOT NULL, ip TEXT NOT NULL, severity TEXT NOT NULL,
    count INTEGER NOT NULL, first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL,
    details TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ingest_state (
    file TEXT PRIMARY KEY NOT NULL, inode TEXT NOT NULL, offset INTEGER NOT NULL CHECK(offset >= 0)
);
"""


@dataclass(frozen=True)
class Checkpoint:
    file: str
    inode: str
    offset: int


def open_database(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    try:
        # WAL lets the dashboard read the last commit while ingestion writes the next one.
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(SCHEMA)
    except sqlite3.Error:
        db.close()
        raise
    return db


def read_checkpoint(db: sqlite3.Connection, file: str) -> Checkpoint | None:
    row = db.execute(
        "SELECT file, inode, offset FROM ingest_state WHERE file = ?", (file,)
    ).fetchone()
    return Checkpoint(*row) if row else None


def write_batch(
    db: sqlite3.Connection, events: Sequence[Event], checkpoint: Checkpoint
) -> None:
    with db:
        db.executemany(
            "INSERT INTO events(ts, source, ip, user, event_type, raw) VALUES (?, ?, ?, ?, ?, ?)",
            [(e.ts, e.source, str(e.ip), e.user, e.event_type, e.raw) for e in events],
        )
        db.execute(
            """INSERT INTO ingest_state(file, inode, offset) VALUES (?, ?, ?)
               ON CONFLICT(file) DO UPDATE SET inode = excluded.inode, offset = excluded.offset""",
            (checkpoint.file, checkpoint.inode, checkpoint.offset),
        )
