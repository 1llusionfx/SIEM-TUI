import re
from datetime import datetime

from ..models import Event
from .auth import MONTHS

COMBINED = re.compile(
    r"(?P<ip>\S+) \S+ (?P<user>\S+) \[(?P<day>\d{2})/(?P<month>[A-Za-z]{3})/"
    r"(?P<rest>\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4})\] "
    r'"(?:[^"\\ ]+) (?P<target>(?:[^"\\ ]|\\.)+) HTTP/[\d.]+" '
    r'(?P<status>[1-5]\d{2}) (?:\d+|-) "(?:[^"\\]|\\.)*" "(?:[^"\\]|\\.)*"'
)


def parse_nginx(line: str) -> Event:
    raw = line.rstrip("\r\n")
    match = COMBINED.fullmatch(raw)
    if match is None:
        raise ValueError("Invalid nginx combined log line")
    month = MONTHS.index(match["month"]) + 1
    stamp = f"{match['day']}/{month}/{match['rest']}"
    timestamp = datetime.strptime(stamp, "%d/%m/%Y:%H:%M:%S %z")
    return Event.model_validate(
        {
            "ts": int(timestamp.timestamp()),
            "source": "nginx",
            "ip": match["ip"],
            "user": None if match["user"] == "-" else match["user"],
            "event_type": "http_request",
            "status": int(match["status"]),
            "path": match["target"].partition("?")[0],
            "raw": raw,
        }
    )
