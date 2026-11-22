# Python core walkthrough

## From SSH message to database row

The three input commands call `ingest.parse_record` to decode bytes and choose the source parser. Valid events flow into `storage.write_batch`, where the detector compares the incoming observations with recent history. A threshold crossing adds an alert in the same transaction as its triggering event. Once the commit succeeds the dashboard can read both rows.

In `parsers/auth.py`, `parse_auth` splits the syslog header from the message. It recognizes three SSH messages. A failed password for an invalid user still counts as a failed password. A separate “Invalid user” message gets its own event type. Unrelated messages with a valid header return `None`. A broken header, impossible date, incomplete login message or invalid address raises `ValueError`.

In `models.py`, the Pydantic event carries the timestamp, source, IP address, username, type and original text. Address validation handles IPv4 and IPv6. The parser removes the line ending and preserves the rest for inspection.

In `ingest.py`, `parse_auth_batch` keeps separate counts for malformed and ignored lines. Its reference date advances after each accepted event. The caller can pass the returned reference to the next batch. Keeping this state outside the single-line parser makes a date inference easy to reproduce in a test.

## The missing year

The parser tries dates in the reference year and its two neighboring years. Invalid calendar dates drop out before it chooses the nearest candidate.

```python
timestamp = min(candidates, key=lambda date: abs(date - reference))
```

A line dated December 31 read on January 2 normally belongs to the previous year. After a December event, a January 1 line normally belongs to the following year. Always using the current year can place two events seconds apart almost a year apart.

The caller supplies an aware reference in the source time zone. The input has neither a year nor a UTC offset, so old archives need a reference near the start of the file. A repeated local hour during a daylight-saving transition is ambiguous.

## Batches, WAL and checkpoints

In `storage.py`, `open_database` enables write-ahead logging and creates the tables and the index on IP and event time. WAL lets a reader keep its snapshot during a write. SQLite still allows one writer at a time. Each event stores its normalized IP as text and its timestamp as Unix seconds.

`write_batch` inserts the events with `executemany` and updates the file checkpoint inside the same `with db` transaction. If the checkpoint write fails, the inserted events roll back too. Committing the checkpoint separately could skip input or insert a batch twice after a crash. A commit per line would also spend more time waiting for disk writes.

## Run one batch

Start `uv run python` from the repository root and enter the following code. It uses an in-memory database for the example. The storage tests use a temporary file to exercise WAL and reopening.

```python
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from loganalyzer.ingest import parse_auth_batch
from loganalyzer.storage import Checkpoint, open_database, write_batch

line = "Dec 31 23:59:59 demo sshd[42]: Invalid user guest from 192.0.2.1 port 42000\n"
batch = parse_auth_batch([line], datetime(2025, 1, 2, tzinfo=UTC))
print(batch.events[0], batch.malformed)
with closing(open_database(Path(":memory:"))) as db:
    write_batch(db, batch.events, Checkpoint("auth.log", "demo", len(line.encode())))
    print(db.execute("SELECT ip, event_type FROM events").fetchall())
```

Run `uv run pytest tests/test_auth.py -v` to inspect the parser cases or `uv run pytest tests/test_storage.py -v` to check transaction behavior. Add `--pdb` to inspect local variables at a failing assertion.

## Questions you might get asked

**How does file ingestion work?** The Typer command in `cli.py` picks a parser from the filename or the explicit format. `ingest_file` opens a completed file in binary mode so each checkpoint is a byte offset. It decodes UTF-8 one line at a time, counts decoding and parsing errors, and commits after 500 input lines or at EOF. The final line of a completed file can omit its newline.

**What is specific to nginx?** `parsers/nginx.py` reads combined-format HTTP request lines and their numeric timezone offset. The normalized event carries the path and status for detection. Removing the query string keeps variations of one resource together. A request that lacks a parseable HTTP request line counts as malformed. Use `uv run pytest tests/test_nginx.py tests/test_cli.py -v` to exercise nginx parsing and the generated-file workflow.

**Why keep the raw line?** It preserves the evidence behind a normalized event. It also makes a parser error easier to diagnose.

**Why store a byte offset?** A file reader can seek to a byte position after a restart. The number of decoded characters can differ from the number of bytes.

**Where are alerts created?** `storage.write_batch` obtains the SQLite writer lock with `BEGIN IMMEDIATE`. It checks that another reader has not advanced the same file checkpoint. Then it runs detection, inserts events, saves the offset and commits. A checkpoint failure rolls back alert updates as well.

## Detection windows and deduplication

`rules.py` loads the YAML with a safe loader. Pydantic rejects unknown fields, nonpositive thresholds and unsupported severity values before ingestion opens the database.

`detectors.py` keeps a deque for each rule and IP touched by the current batch. On first use, it reads qualifying events from the indexed time range in SQLite. nginx observations are parsed from their raw lines to recover paths and status codes. This costs some reads at batch boundaries but makes a fresh CLI process continue an attack without a separate state file.

```python
while window and window[0].ts < cutoff:
    window.popleft()
```

The window includes both endpoints. A late observation inside the current window is inserted in time order. An older observation is stored for inspection and contributes no new alert. The window clock is the latest qualifying event time for that IP and rule.

Each event is evaluated twice, once after expiration and once after insertion. If the surviving observations already meet the threshold, the detector updates the alert ending at the previous window time. Otherwise a new crossing opens a new alert. This also works after restarting the CLI. A fixed cooldown would merge independent bursts occurring close together. Alert count records the initial window size plus subsequent observations while the alert continues. Details describe the latest qualifying window.

Run `uv run pytest tests/test_detectors.py -v` for the window boundary, both scan conditions, database rollback and episodes split across batches.

## Following a file and playing an archive

In `tail.py`, each poll reads up to 500 lines per file. Closing the file between polls allows renames on Windows. A reader compares the saved device and inode to the open file and checks the size before seeking.

```python
if previous and inode == previous.inode and previous.offset <= stat.st_size:
    stream.seek(previous.offset)
```

A shorter file starts at byte zero. After a rename the reader looks for the old inode under the original filename plus a suffix, drains unread complete lines, then switches to the replacement. A partial current line stays behind the checkpoint until a newline arrives. A partial final line on a rotated sibling counts as malformed. A missing file can appear on a later poll.

The replay command uses the same parser and database writer. Each event becomes visible at its playback deadline. Computing deadlines from the first timestamp avoids accumulating time spent writing earlier events. Equal or out-of-order timestamps can be played immediately. Replay leaves file checkpoints alone so a demonstration cannot move a live watcher forward.

Use `uv run pytest tests/test_streams.py -v` to exercise rotation during downtime, truncation and playback with a fake clock. Run `loganalyzer watch` and `loganalyzer stats` in separate terminals to inspect newly committed rows.

## Reading committed results

The Ink dashboard has no Python imports or direct connection to the ingestion process. Each second, `tui/src/db.ts` opens the database read-only and reads all three panes in one short SQLite transaction. The panes therefore show the same commit even if ingestion is writing the next batch. Closing the connection after the read releases the WAL snapshot and lets the next poll recover after a database replacement. Reopening adds a small cost per poll.

The rate uses the difference between successive committed event counts divided by elapsed wall time. Loading an archive can therefore show activity even though its event timestamps are years old. To debug a difference between the CLI and the TUI, run `loganalyzer stats --db PATH` and start the TUI against the same absolute path. Check the active filter and pause state.

## Reproducing the benchmark and demo

`tests/benchmarks/test_ingest.py` uses the same file ingestion function as the CLI. It prepares a generated nginx file, runs five imports into separate databases and checks the returned event count. Divide 5,000 by the median reported time in seconds to get lines per second. Run `uv run pytest tests/benchmarks --benchmark-only` on the target machine before comparing changes.

In Docker, `scripts/demo.sh` generates both log formats under `/demo` and starts the two replay runs in sequence in the background. The foreground Node process owns the terminal. Inspect playback with `docker compose exec demo cat /demo/replay.log` and counts with `docker compose exec demo loganalyzer stats --db /demo/logs.sqlite3`.
