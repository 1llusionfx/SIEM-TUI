import os
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .models import Event
from .parsers.auth import parse_auth
from .parsers.nginx import parse_nginx
from .rules import Rules
from .storage import Checkpoint, read_checkpoint, write_batch


@dataclass
class ParsedBatch:
    reference: datetime
    events: list[Event] = field(default_factory=list)
    malformed: int = 0
    ignored: int = 0


def parse_auth_batch(lines: Iterable[str], reference: datetime) -> ParsedBatch:
    if reference.utcoffset() is None:
        raise ValueError("The reference date needs a time zone")
    batch = ParsedBatch(reference)
    for line in lines:
        try:
            event = parse_auth(line, batch.reference)
        except ValueError:
            batch.malformed += 1
            continue
        if event is None:
            batch.ignored += 1
        else:
            batch.events.append(event)
            batch.reference = datetime.fromtimestamp(event.ts, reference.tzinfo)
    return batch


@dataclass
class Totals:
    events: int = 0
    malformed: int = 0
    ignored: int = 0


def ingest_file(
    db: sqlite3.Connection, path: Path, format_name: str, rules: Rules
) -> Totals:
    file = str(path.resolve())
    totals = Totals()
    with path.open("rb") as stream:
        stat = os.fstat(stream.fileno())
        inode = f"{stat.st_dev}:{stat.st_ino}"
        checkpoint = read_checkpoint(db, file)
        if (
            checkpoint
            and checkpoint.inode == inode
            and checkpoint.offset <= stat.st_size
        ):
            stream.seek(checkpoint.offset)
        reference = datetime.fromtimestamp(stat.st_mtime, UTC)
        events: list[Event] = []
        pending = 0
        for raw in stream:
            try:
                line = raw.decode("utf-8")
                event = (
                    parse_auth(line, reference)
                    if format_name == "auth"
                    else parse_nginx(line)
                )
            except ValueError:
                totals.malformed += 1
            else:
                if event is None:
                    totals.ignored += 1
                else:
                    events.append(event)
                    reference = datetime.fromtimestamp(event.ts, UTC)
                    totals.events += 1
            pending += 1
            if pending == 500:
                next_checkpoint = Checkpoint(file, inode, stream.tell())
                write_batch(db, events, next_checkpoint, rules, checkpoint)
                checkpoint = next_checkpoint
                events.clear()
                pending = 0
        if pending:
            write_batch(
                db, events, Checkpoint(file, inode, stream.tell()), rules, checkpoint
            )
    return totals
