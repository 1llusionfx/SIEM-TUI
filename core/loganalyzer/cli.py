import sqlite3
from contextlib import closing
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from .ingest import ingest_file
from .storage import open_database

app = typer.Typer(add_completion=False)
Database = Annotated[Path, typer.Option("--db", help="SQLite database path.")]


class LogFormat(str, Enum):
    auth = "auth"
    nginx = "nginx"


@app.command()
def ingest(
    file: Path,
    db: Database = Path("loganalyzer.sqlite3"),
    format_: Annotated[LogFormat | None, typer.Option("--format")] = None,
) -> None:
    """Read new lines from an SSH or nginx log."""
    if format_ is None:
        if file.name.startswith(("auth.log", "secure")):
            format_ = LogFormat.auth
        elif file.name.startswith("access.log"):
            format_ = LogFormat.nginx
        else:
            raise typer.BadParameter(
                "Use --format auth or --format nginx for this filename."
            )
    try:
        with closing(open_database(db)) as connection:
            result = ingest_file(connection, file, format_.value)
    except (OSError, sqlite3.Error, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(
        f"Events {result.events} | malformed {result.malformed} | ignored {result.ignored}"
    )


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
