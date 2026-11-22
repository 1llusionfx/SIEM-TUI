from datetime import UTC, datetime

import pytest

from loganalyzer.ingest import parse_auth_batch
from loganalyzer.parsers.auth import parse_auth

REFERENCE = datetime(2025, 1, 2, tzinfo=UTC)
HEADER = "Dec 31 23:59:59 demo sshd[42]: "


@pytest.mark.parametrize(
    ("message", "kind", "user", "ip"),
    [
        (
            "Failed password for alex from 192.0.2.1 port 42000 ssh2",
            "ssh_failed",
            "alex",
            "192.0.2.1",
        ),
        (
            "Failed password for invalid user guest from 192.0.2.1 port 42001 ssh2",
            "ssh_failed",
            "guest",
            "192.0.2.1",
        ),
        (
            "Accepted password for sam from 2001:db8::1 port 42002 ssh2",
            "ssh_accepted",
            "sam",
            "2001:db8::1",
        ),
        (
            "Invalid user guest from 192.0.2.1 port 42003",
            "ssh_invalid_user",
            "guest",
            "192.0.2.1",
        ),
    ],
)
def test_supported_logins(message: str, kind: str, user: str, ip: str) -> None:
    event = parse_auth(HEADER + message + "\r\n", REFERENCE)
    assert event is not None
    assert (event.event_type, event.user, str(event.ip)) == (kind, user, ip)
    assert event.ts == int(datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC).timestamp())
    assert event.raw == HEADER + message


def test_batch_tracks_rollover_and_counts_bad_lines() -> None:
    login = "Invalid user guest from 192.0.2.1 port 4242"
    batch = parse_auth_batch(
        [
            HEADER + login,
            "Jan  1 00:00:00 demo sshd[43]: " + login,
            "broken header",
            HEADER + login.replace("192.0.2.1", "invalid"),
            HEADER + "Failed password for sam",
            HEADER.replace("Dec 31", "Feb 30") + login,
            HEADER + "Connection closed",
            HEADER.replace("sshd", "sudo") + "session opened",
        ],
        datetime(2024, 12, 30, tzinfo=UTC),
    )
    first, second = batch.events
    assert second.ts == first.ts + 1
    assert batch.reference == datetime(2025, 1, 1, tzinfo=UTC)
    assert (batch.malformed, batch.ignored) == (4, 2)


def test_batch_requires_timezone_before_reading_lines() -> None:
    with pytest.raises(ValueError, match="time zone"):
        parse_auth_batch([], datetime(2025, 1, 1))
