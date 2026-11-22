import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path


def generate(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    start = datetime(2025, 1, 2, 12, tzinfo=UTC)
    with (
        (directory / "auth.log").open("w", encoding="utf-8") as auth,
        (directory / "access.log").open("w", encoding="utf-8") as web,
    ):
        for i in range(60):
            time = (start + timedelta(seconds=i)).strftime("%H:%M:%S")
            ip, user, action = f"192.0.2.{i % 5 + 1}", "alex", "Accepted"
            if 15 <= i < 25:
                ip, action = "198.51.100.10", "Failed"
            if 35 <= i < 43:
                ip, user, action = "198.51.100.20", f"guest{i - 35}", "Failed"
            auth.write(
                f"Jan  2 {time} demo sshd[{4000 + i}]: {action} password for "
                f"{user} from {ip} port {50000 + i} ssh2\n"
            )
            path, status, client = "/", 200, f"192.0.2.{i % 5 + 1}"
            if 20 <= i < 32:
                path, status, client = f"/archive/item-{i}", 404, "203.0.113.7"
            web.write(
                f'{client} - - [02/Jan/2025:{time} +0000] "GET {path} HTTP/1.1" '
                f'{status} 240 "-" "DemoBrowser/1.0"\n'
            )
        auth.write("incomplete synthetic SSH line\n")
        web.write("incomplete synthetic HTTP line\n")
    # The syslog reader uses file mtime to anchor timestamps without a year.
    import os

    stamp = start.timestamp()
    os.utime(directory / "auth.log", (stamp, stamp))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Write generated auth.log and access.log fixtures."
    )
    parser.add_argument("directory", type=Path)
    generate(parser.parse_args().directory)
