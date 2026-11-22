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

## Configure detection

Ingest reads `rules.yaml` from the working directory. Use `--rules PATH` to select another file. Each rule has a positive window length in seconds and a severity of `low`, `medium` or `high`.

| Rule | Condition for one IP within the window |
| --- | --- |
| brute_force | At least `threshold` failed SSH passwords |
| credential_stuffing | At least `threshold` distinct usernames in failed SSH passwords |
| scan | At least `missing_threshold` HTTP 404s or `paths_threshold` distinct request paths |

The generated sample produces four alert rows with the default rules. The sequence with eight usernames also qualifies as brute force. A rule change applies on subsequent ingestion. Existing alert rows retain their history.

## Open the dashboard

After ingesting the generated files, run these commands from the repository root with Node 20+ and npm installed.

```sh
cd tui
npm ci
npm run build
npm start
```

The default database is `../loganalyzer.sqlite3` relative to the TUI working directory. Use `npm start -- PATH` for another database. Running the dashboard first shows “waiting for daemon…” until ingestion creates the schema.

The header shows committed events per second over the last 20 samples. Top IPs ranks matching events by address. Live events are ordered by insertion, and alerts by their latest observation. Each pane holds up to 100 rows. Narrow or short terminals show the focused pane.

| Key | Action |
| --- | --- |
| Tab / Shift+Tab | Change pane |
| ↑ / ↓ | Select a row or scroll a detail |
| Enter | Inspect a row, including the raw log in Live events |
| Esc / Enter | Close detail |
| / | Edit a literal, case-insensitive filter. Enter applies it and resumes polling. Esc cancels. |
| p | Pause or resume polling |
| q | Quit |

Severity labels remain visible with `NO_COLOR=1`. From `tui/`, run `npm test`, `npm run lint` and `npm run typecheck` to check the terminal UI.

## Run the core tests

From the repository root, with Python 3.12 and uv installed, run

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run mypy --strict
```

A synthetic batch crosses New Year in the parser tests. A storage test reopens a database and checks what survives a failed write. The walkthrough includes a runnable example and explains both cases. [Python walkthrough](docs/PYTHON_WALKTHROUGH.md)
