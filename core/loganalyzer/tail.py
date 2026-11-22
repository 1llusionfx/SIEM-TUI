import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .ingest import Totals, parse_record
from .rules import Rules
from .storage import Checkpoint, read_checkpoint, write_batch


def identity(stat: os.stat_result) -> str:
    return f"{stat.st_dev}:{stat.st_ino}"


def read_available(
    db: sqlite3.Connection, path: Path, source: str, rules: Rules, totals: Totals
) -> bool:
    file = str(path.resolve())
    previous = read_checkpoint(db, file)
    try:
        current = identity(path.stat())
    except FileNotFoundError:
        current = None
    target = path
    if previous and previous.inode != current:
        # A rotated sibling may still contain complete lines beyond the checkpoint.
        for sibling in path.parent.glob(path.name + ".*"):
            try:
                stat = sibling.stat()
            except FileNotFoundError:
                continue
            if identity(stat) == previous.inode and stat.st_size > previous.offset:
                target = sibling
                break
    try:
        stream = target.open("rb")
    except FileNotFoundError:
        return False
    with stream:
        stat = os.fstat(stream.fileno())
        inode = identity(stat)
        if previous and inode == previous.inode and previous.offset <= stat.st_size:
            stream.seek(previous.offset)
        offset = stream.tell()
        reference = datetime.fromtimestamp(stat.st_mtime, UTC)
        events = []
        read = 0
        for _ in range(500):
            raw = stream.readline()
            if not raw:
                break
            if not raw.endswith(b"\n"):
                if target != path:
                    totals.malformed += 1
                    offset = stream.tell()
                break
            read += 1
            offset = stream.tell()
            event = parse_record(raw, source, reference, totals)
            if event:
                events.append(event)
                reference = datetime.fromtimestamp(event.ts, UTC)
        next_checkpoint = Checkpoint(file, inode, offset)
        if next_checkpoint != previous:
            write_batch(db, events, next_checkpoint, rules, previous)
    return read == 500 or target != path
