import math
import os
import sqlite3
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .ingest import Totals, parse_record
from .rules import Rules
from .storage import write_batch


def replay_file(
    db: sqlite3.Connection,
    path: Path,
    source: str,
    rules: Rules,
    speed: float,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Totals:
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError("Speed must be a positive finite number")
    totals = Totals()
    first_ts: int | None = None
    with path.open("rb") as stream:
        reference = datetime.fromtimestamp(os.fstat(stream.fileno()).st_mtime, UTC)
        start = clock()
        for raw in stream:
            event = parse_record(raw, source, reference, totals)
            if event is None:
                continue
            reference = datetime.fromtimestamp(event.ts, UTC)
            if first_ts is None:
                first_ts = event.ts
                start = clock()
            delay = start + (event.ts - first_ts) / speed - clock()
            if delay > 0:
                sleep(delay)
            write_batch(db, [event], None, rules)
    return totals
