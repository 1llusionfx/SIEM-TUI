from datetime import UTC, datetime

import pytest

from loganalyzer.parsers.nginx import parse_nginx

LINE = '2001:db8::5 - - [02/Jan/2025:13:15:04 +0100] "GET /a?q=1 HTTP/1.1" 404 42 "-" "Demo/1.0"'


def test_combined_request() -> None:
    event = parse_nginx(LINE + "\n")
    assert event.ts == int(datetime(2025, 1, 2, 12, 15, 4, tzinfo=UTC).timestamp())
    assert (event.path, event.status, event.user, str(event.ip)) == (
        "/a",
        404,
        None,
        "2001:db8::5",
    )
    assert event.raw == LINE


@pytest.mark.parametrize(
    "line",
    [
        LINE[:-1],
        LINE.replace("Jan", "Xxx"),
        LINE.replace("404", "900"),
        LINE.replace("2001:db8::5", "bad"),
    ],
)
def test_malformed_requests(line: str) -> None:
    with pytest.raises(ValueError):
        parse_nginx(line)
