# Python core walkthrough

Start with one failed SSH login. The parser reads the time, IP and username. The detector checks how many recent failures came from that IP. If this failure reaches the limit, SQLite saves the event and its alert together. The dashboard sees both on its next read.

## From a file to an event

| Module | Job |
| --- | --- |
| `cli.py` | Handles `ingest`, `watch`, `replay` and `stats`. Picks the log format from the filename or `--format`. |
| `ingest.py` | Reads bytes, decodes UTF-8 and calls the parser. A full-file import saves a batch every 500 input lines and saves the last batch at the end. |
| `parsers/auth.py` | Reads accepted passwords, failed passwords and “Invalid user” messages from SSH logs. |
| `parsers/nginx.py` | Reads combined access logs. It keeps the HTTP status and strips the query string from the path, so two searches on the same page count as one path. |
| `models.py` | Defines the shared event fields, checks IPv4 and IPv6 addresses, and keeps the original line for the detail view. |

The import report counts malformed and ignored lines separately. A broken timestamp is malformed. A valid SSH “Connection closed” message is ignored because it describes a different kind of event.

### Why December needs special handling

A syslog line might say `Dec 31 23:59:59` without a year. If the file was written on January 2, using the file’s year would put that December event almost a year in the future.

The parser tries the reference year, the year before and the year after. It keeps valid dates and picks the closest one.

```python
timestamp = min(candidates, key=lambda date: abs(date - reference))
```

The CLI starts with the file’s modification time in UTC. As it reads a batch, each accepted event becomes the next reference. An old archive with a recent modification time can still get the wrong year. nginx logs include a year and UTC offset.

## How one burst becomes one alert

`rules.py` reads the YAML and checks it before ingestion starts. A typo in a field name or a threshold of zero raises an error. In `detectors.py`, each rule keeps a short history for each IP in a `deque`, a queue that can quickly remove its oldest item.

```python
while window and window[0].ts < cutoff:
    window.popleft()
previously_matched, _ = evaluate(name, rule, window)
```

For a 60-second rule, a failure at 12:00:00 still counts at 12:01:00. One second later it drops out. A late event can still count if its timestamp falls inside the window. Older events remain available in the dashboard.

The detector checks the rule before and after adding the new event. With the default brute-force rule, the sixth failure opens an alert. A seventh failure a moment later updates it. Once enough old failures expire, a later burst can open a new alert. A fixed cooldown could hide that second burst.

At the start of a batch, the detector reads recent events for the IP from SQLite. This costs a few reads, but it lets a restarted process continue an existing alert. For HTTP events, it reads the saved raw line again to recover the path and status.

## What happens if a write fails?

`storage.py` enables SQLite’s write-ahead log (WAL). The dashboard can keep reading the last saved data while Python writes the next batch. SQLite allows one writer at a time.

The writer takes the lock with `BEGIN IMMEDIATE`, checks the previous file position, then saves the events, alert changes and new position in one transaction. If a step fails, SQLite rolls the whole batch back. Saving the position separately could make a restart skip lines or read them twice.

Each second, the TUI reads its three panes in one short transaction. Its events-per-second figure measures new rows arriving in the database. Replaying a year-old file can still make the sparkline rise.

## Watching and replaying

**Watch** waits for complete lines. `tail.py` saves a byte offset and a file ID made from the device and inode. It closes the file between polls so Windows can rename it. Before reading again, it checks whether the saved position still fits the same file.

```python
if previous and inode == previous.inode and previous.offset <= stat.st_size:
    stream.seek(previous.offset)
```

If the file shrank below that offset, reading starts at zero. If it was renamed to a sibling such as `access.log.1`, the watcher looks for its old ID and reads the remaining complete lines before switching files. A partial line in the current file waits for its newline.

**Replay** reads the archive from the start. `replay.py` keeps the original timestamps and schedules playback from the first event. At `--speed 10`, a ten-second gap takes one second. Using a single start time keeps small database delays from adding up. Replay leaves the watcher’s saved position alone.

## Try it and debug it

Run this from the project folder to see a sample pass through the full core.

```sh
uv run python scripts/generate_logs.py samples
uv run loganalyzer ingest samples/auth.log --db example.sqlite3
uv run loganalyzer stats --db example.sqlite3
```

On a fresh database, the SSH file gives **60 events, one malformed line and three alerts**. Import it again and the saved offset keeps the event count at 60.

| To investigate | Run from the project folder |
| --- | --- |
| Dates, addresses or bad lines | `uv run pytest tests/test_auth.py tests/test_nginx.py -v` |
| Window boundaries and repeated alerts | `uv run pytest tests/test_detectors.py -v` |
| A failed write or a CLI count | `uv run pytest tests/test_storage.py tests/test_cli.py -v` |
| Rotation, partial lines or replay timing | `uv run pytest tests/test_streams.py -v` |

Add `--pdb` to inspect variables when a test fails. If the dashboard and CLI look different, check that both use the same database, then check the dashboard filter and pause state. In Docker, `docker compose exec demo cat /demo/replay.log` shows the replay output.

## Questions you might get asked

**Why save the raw line?** It lets someone inspect the evidence behind an alert and check how the parser read it.

**Why count bytes?** A UTF-8 character can take several bytes. A byte offset lets the reader seek to the right place after a restart.

**Why batch writes?** A single commit can save hundreds of lines. Committing every line spends more time waiting for disk writes. Replay commits each event so it appears at the right time.

**Why can one IP trigger two SSH alerts?** Brute force counts failed passwords. Credential stuffing counts different usernames in those failures. One burst can meet both rules.
