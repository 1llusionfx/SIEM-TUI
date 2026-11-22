# loganalyzer

A personal project for educational purposes. Use it only with logs you own or have permission to analyze. All sample lines in this repository are generated.

The Python core parses OpenSSH password logins and invalid-user messages from traditional syslog. It validates each event, counts malformed lines and saves batches in SQLite. This is the first milestone of a mini SIEM with a planned detection engine and terminal dashboard.

## Run the core tests

From the repository root, with Python 3.12 and uv installed, run

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run mypy --strict
```

A synthetic batch crosses New Year in the parser tests. A storage test reopens a database and checks what survives a failed write. The walkthrough includes a runnable example and explains both cases. [Python walkthrough](docs/PYTHON_WALKTHROUGH.md)
