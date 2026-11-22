# loganalyzer

A personal project for educational purposes. Use it only with logs you own or have permission to analyze. All sample lines in this repository are generated.

The Python core parses OpenSSH password logins, invalid-user messages and nginx combined access logs. It validates events, counts malformed lines and stores batches in SQLite.

## Ingest generated logs

```sh
uv run python scripts/generate_logs.py samples
uv run loganalyzer ingest samples/auth.log
uv run loganalyzer ingest samples/access.log
uv run loganalyzer stats
```

The generator replaces both files in the chosen directory. Each contains 60 events and one malformed line. Repeating an ingest resumes at the saved byte offset. Pass `--format auth` or `--format nginx` for a custom filename, and `--db PATH` to select a database. SSH times are interpreted as UTC, using the file modification time as the initial year reference. nginx timestamps include their own UTC offsets.

## Run the core tests

From the repository root, with Python 3.12 and uv installed, run

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run mypy --strict
```

A synthetic batch crosses New Year in the parser tests. A storage test reopens a database and checks what survives a failed write. The walkthrough includes a runnable example and explains both cases. [Python walkthrough](docs/PYTHON_WALKTHROUGH.md)
