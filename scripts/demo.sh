#!/bin/sh
set -eu
python scripts/generate_logs.py /demo
(
    loganalyzer replay /demo/auth.log --speed 5 --db /demo/logs.sqlite3 &&
    loganalyzer replay /demo/access.log --speed 5 --db /demo/logs.sqlite3
) > /demo/replay.log 2>&1 &
exec node tui/dist/index.js /demo/logs.sqlite3
