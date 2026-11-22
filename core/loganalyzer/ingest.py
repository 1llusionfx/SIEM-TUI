from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from .models import Event
from .parsers.auth import parse_auth


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
