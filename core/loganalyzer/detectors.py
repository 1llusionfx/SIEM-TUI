import sqlite3
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from .models import Event
from .parsers.nginx import parse_nginx
from .rules import LoginRule, Rules, ScanRule


@dataclass
class Observation:
    ts: int
    user: str | None
    path: str | None
    status: int | None


def restore_window(
    db: sqlite3.Connection, event: Event, seconds: int
) -> deque[Observation]:
    ip = str(event.ip)
    latest = db.execute(
        "SELECT max(ts) FROM events WHERE ip = ? AND event_type = ?",
        (ip, event.event_type),
    ).fetchone()[0]
    cutoff = max(event.ts, latest if latest is not None else event.ts) - seconds
    rows = db.execute(
        """SELECT ts, user, raw FROM events WHERE ip = ? AND ts >= ? AND event_type = ?
           ORDER BY ts, id""",
        (ip, cutoff, event.event_type),
    )
    window: deque[Observation] = deque()
    for ts, user, raw in rows:
        request = parse_nginx(raw) if event.source == "nginx" else None
        window.append(
            Observation(
                ts,
                user,
                request.path if request else None,
                request.status if request else None,
            )
        )
    return window


def evaluate(
    name: str, rule: LoginRule | ScanRule, window: deque[Observation]
) -> tuple[bool, str]:
    if isinstance(rule, ScanRule):
        missing = sum(item.status == 404 for item in window)
        paths = len({item.path for item in window})
        return (
            missing >= rule.missing_threshold or paths >= rule.paths_threshold,
            f"{missing} responses with status 404, {paths} distinct paths",
        )
    if name == "credential_stuffing":
        users = len({item.user for item in window})
        return users >= rule.threshold, f"{users} distinct usernames"
    return len(window) >= rule.threshold, f"{len(window)} failed passwords"


def observe(
    db: sqlite3.Connection,
    name: str,
    rule: LoginRule | ScanRule,
    event: Event,
    window: deque[Observation],
) -> None:
    end = max(event.ts, window[-1].ts) if window else event.ts
    cutoff = end - rule.window_seconds
    if event.ts < cutoff:
        return
    # Keep both endpoints, including an observation exactly one window old.
    while window and window[0].ts < cutoff:
        window.popleft()
    previously_matched, _ = evaluate(name, rule, window)
    previous_end = window[-1].ts if window else None
    window.append(Observation(event.ts, event.user, event.path, event.status))
    if event.ts < end:
        ordered = sorted(window, key=lambda item: item.ts)
        window.clear()
        window.extend(ordered)
    matches, details = evaluate(name, rule, window)
    if not matches:
        return

    ip = str(event.ip)
    if previously_matched:
        updated = db.execute(
            """UPDATE alerts SET count = count + 1, first_seen = min(first_seen, ?),
                      last_seen = ?, details = ?, severity = ?
               WHERE id = (SELECT id FROM alerts WHERE rule = ? AND ip = ?
                           AND last_seen = ? ORDER BY id DESC LIMIT 1)""",
            (event.ts, end, details, rule.severity, name, ip, previous_end),
        )
        if updated.rowcount:
            return
    db.execute(
        """INSERT INTO alerts(rule, ip, severity, count, first_seen, last_seen, details)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (name, ip, rule.severity, len(window), window[0].ts, end, details),
    )


def detect_batch(db: sqlite3.Connection, events: Sequence[Event], rules: Rules) -> None:
    windows: dict[tuple[str, str], deque[Observation]] = {}
    for event in events:
        applicable: list[tuple[str, LoginRule | ScanRule]]
        if event.event_type == "ssh_failed":
            applicable = [
                ("brute_force", rules.brute_force),
                ("credential_stuffing", rules.credential_stuffing),
            ]
        elif event.event_type == "http_request":
            applicable = [("scan", rules.scan)]
        else:
            continue
        for name, rule in applicable:
            key = (name, str(event.ip))
            if key not in windows:
                windows[key] = restore_window(db, event, rule.window_seconds)
            observe(db, name, rule, event, windows[key])
