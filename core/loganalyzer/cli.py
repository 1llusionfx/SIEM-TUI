import sqlite3
import time
from contextlib import closing
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from .ingest import Totals, ingest_file
from .replay import replay_file
from .rules import load_rules
from .storage import open_database
from .tail import read_available

app = typer.Typer(add_completion=False)
Database = Annotated[Path, typer.Option("--db", help="SQLite database path.")]
RuleFile = Annotated[Path, typer.Option("--rules")]


class LogFormat(str, Enum):
    auth = "auth"
    nginx = "nginx"


Format = Annotated[LogFormat | None, typer.Option("--format")]


def source_name(file: Path, format_: LogFormat | None) -> str:
    if format_ is None:
        if file.name.startswith(("auth.log", "secure")):
            format_ = LogFormat.auth
        elif file.name.startswith("access.log"):
            format_ = LogFormat.nginx
        else:
            raise typer.BadParameter(
                "Use --format auth or --format nginx for this filename."
            )
    return format_.value


def report(result: Totals) -> None:
    typer.echo(
        f"Events {result.events} | malformed {result.malformed} | ignored {result.ignored}"
    )


@app.command()
def ingest(
    file: Path,
    db: Database = Path("loganalyzer.sqlite3"),
    format_: Format = None,
    rules: RuleFile = Path("rules.yaml"),
) -> None:
    """Read new lines from an SSH or nginx log."""
    source = source_name(file, format_)
    try:
        config = load_rules(rules)
        with closing(open_database(db)) as connection:
            result = ingest_file(connection, file, source, config)
    except (OSError, sqlite3.Error, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    report(result)


@app.command()
def replay(
    file: Path,
    speed: float = 1,
    db: Database = Path("loganalyzer.sqlite3"),
    format_: Format = None,
    rules: RuleFile = Path("rules.yaml"),
) -> None:
    """Play a complete file from the beginning at the selected speed."""
    source = source_name(file, format_)
    try:
        config = load_rules(rules)
        with closing(open_database(db)) as connection:
            report(replay_file(connection, file, source, config, speed))
    except (OSError, sqlite3.Error, ValueError) as error:
        raise typer.BadParameter(str(error)) from error


@app.command()
def watch(
    files: list[Path],
    db: Database = Path("loganalyzer.sqlite3"),
    format_: Format = None,
    rules: RuleFile = Path("rules.yaml"),
) -> None:
    """Follow one or more files until Ctrl+C."""
    sources = [(path, source_name(path, format_)) for path in files]
    totals = Totals()
    try:
        config = load_rules(rules)
        with closing(open_database(db)) as connection:
            while True:
                busy = False
                for path, source in sources:
                    if read_available(connection, path, source, config, totals):
                        busy = True
                if not busy:
                    time.sleep(0.25)
    except KeyboardInterrupt:
        report(totals)
    except (OSError, sqlite3.Error, ValueError) as error:
        raise typer.BadParameter(str(error)) from error


@app.command()
def stats(db: Database = Path("loganalyzer.sqlite3")) -> None:
    """Show committed event and alert totals."""
    try:
        with closing(
            sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        ) as connection:
            events, alerts = connection.execute(
                "SELECT (SELECT count(*) FROM events), (SELECT count(*) FROM alerts)"
            ).fetchone()
    except sqlite3.Error as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(f"Events {events} | alerts {alerts}")
