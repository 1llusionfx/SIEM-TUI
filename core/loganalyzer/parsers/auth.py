import re
from datetime import datetime

from ..models import Event

HEADER = re.compile(
    r"(?P<month>[A-Z][a-z]{2}) +(?P<day>\d{1,2}) "
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2}) "
    r"\S+ (?P<service>[\w./-]+)(?:\[\d+\])?: (?P<message>.*)"
)
LOGIN = re.compile(
    r"(?P<action>Failed password for|Accepted password for|Invalid user) "
    r"(?:invalid user )?(?P<user>\S+) from (?P<ip>\S+) port \d+(?: .*)?"
)
MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def parse_auth(line: str, reference: datetime) -> Event | None:
    raw = line.rstrip("\r\n")
    header = HEADER.fullmatch(raw)
    if header is None:
        raise ValueError("Invalid syslog header")
    if reference.utcoffset() is None:
        raise ValueError("The reference date needs a time zone")

    month = MONTHS.index(header["month"]) + 1
    day, hour, minute, second = map(
        int, header.group("day", "hour", "minute", "second")
    )
    candidates = []
    # A December line read in January usually belongs to the previous year.
    for year in range(reference.year - 1, reference.year + 2):
        try:
            candidate = datetime(
                year, month, day, hour, minute, second, tzinfo=reference.tzinfo
            )
        except ValueError:
            continue
        candidates.append(candidate)
    if not candidates:
        raise ValueError("Invalid syslog date")
    timestamp = min(candidates, key=lambda date: abs(date - reference))

    message = header["message"]
    if header["service"] != "sshd" or not message.startswith(
        ("Failed password", "Accepted password", "Invalid user")
    ):
        return None
    login = LOGIN.fullmatch(message)
    if login is None:
        raise ValueError("Invalid SSH login message")
    return Event.model_validate(
        {
            "ts": int(timestamp.timestamp()),
            "source": "auth",
            "ip": login["ip"],
            "user": login["user"],
            "event_type": {
                "Failed password for": "ssh_failed",
                "Accepted password for": "ssh_accepted",
                "Invalid user": "ssh_invalid_user",
            }[login["action"]],
            "raw": raw,
        }
    )
