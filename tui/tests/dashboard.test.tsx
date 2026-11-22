import assert from 'node:assert/strict';
import {existsSync, mkdtempSync, rmdirSync, unlinkSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {afterEach, test} from 'node:test';
import {setTimeout as delay} from 'node:timers/promises';
import Database from 'better-sqlite3';
import {cleanup, render} from 'ink-testing-library';
import {App} from '../src/App.js';
import {readSnapshot} from '../src/db.js';

afterEach(cleanup);

function temporaryDatabase() {
  const dir = mkdtempSync(join(tmpdir(), 'loganalyzer-'));
  const path = join(dir, 'test.sqlite3');
  return {path, remove() {
    if (existsSync(path)) unlinkSync(path);
    rmdirSync(dir);
  }};
}

function seed(path: string) {
  const db = new Database(path);
  db.exec(`CREATE TABLE events(id INTEGER PRIMARY KEY, ts, ip, event_type, raw);
    CREATE TABLE alerts(id INTEGER PRIMARY KEY, rule, ip, severity, count, details, first_seen, last_seen);
    INSERT INTO events VALUES(1, 1, '192.0.2.1', 'ssh_failed', 'first raw line');
    INSERT INTO events VALUES(2, 2, '192.0.2.2', 'ssh_accepted', 'second raw line');
    INSERT INTO alerts VALUES(1, 'brute_force', '192.0.2.1', 'high', 6, '6 failed passwords', 1, 2);`);
  return db;
}

test('reader leaves a missing database absent and filters a consistent snapshot', () => {
  const file = temporaryDatabase();
  try {
    assert.throws(() => readSnapshot(file.path, ''));
    assert.equal(existsSync(file.path), false);
    seed(file.path).close();
    const view = readSnapshot(file.path, '192.0.2.1');
    assert.equal(view.total, 2);
    assert.deepEqual(view.panes.map(pane => pane.length), [1, 1, 1]);
    assert.equal(view.panes[1][0].detail, 'first raw line');
    assert.equal(view.panes[2][0].severity, 'high');
  } finally { file.remove(); }
});

test('missing and locked screens recover on polling', async () => {
  const file = temporaryDatabase();
  const ui = render(<App path={file.path}/>);
  try {
    await delay(80);
    assert.match(ui.lastFrame()!, /waiting for daemon…/);
    const writer = seed(file.path);
    try {
      writer.exec('BEGIN EXCLUSIVE');
      await delay(1150);
      assert.match(ui.lastFrame()!, /waiting for daemon…/);
      writer.exec('ROLLBACK');
      await delay(1100);
      assert.match(ui.lastFrame()!, /ssh_failed/);
    } finally { writer.close(); }
  } finally { ui.unmount(); file.remove(); }
});

test('selection, details, pane focus, pause, filtering, resize and quit', async () => {
  const originalColor = process.env.NO_COLOR;
  process.env.NO_COLOR = '1';
  const file = temporaryDatabase();
  const db = seed(file.path);
  const ui = render(<App path={file.path}/>);
  const key = async (input: string) => { ui.stdin.write(input); await delay(60); };
  try {
    await delay(80);
    assert.match(ui.lastFrame()!, /› Live events/);
    await key('\x1b[B');
    await key('\r');
    assert.match(ui.lastFrame()!, /first raw line/);
    await key('\r');
    await key('\x1b[A');
    await key('\r');
    assert.match(ui.lastFrame()!, /second raw line/);
    await key('\r');
    await key('\t');
    assert.match(ui.lastFrame()!, /› Alerts/);
    await key('\x1b[Z');
    assert.match(ui.lastFrame()!, /› Live events/);
    await key('p');
    db.exec("INSERT INTO events VALUES(3, 3, '192.0.2.3', 'new_event', 'new raw')");
    await delay(1100);
    assert.match(ui.lastFrame()!, /Paused/);
    assert.doesNotMatch(ui.lastFrame()!, /new_event/);
    await key('p');
    assert.match(ui.lastFrame()!, /new_event/);
    await key('/');
    await key('192.0.2.1');
    await key('\r');
    assert.match(ui.lastFrame()!, /Filter: 192\.0\.2\.1/);
    assert.doesNotMatch(ui.lastFrame()!, /ssh_accepted/);
    Object.defineProperty(ui.stdout, 'columns', {value: 24});
    Object.defineProperty(ui.stdout, 'rows', {value: 6});
    ui.stdout.emit('resize');
    await delay(80);
    assert.match(ui.lastFrame()!, /Live events/);
    assert.doesNotMatch(ui.lastFrame()!, /Top IPs/);
    assert.ok(ui.lastFrame()!.split('\n').length <= 6);
    assert.doesNotMatch(ui.lastFrame()!, /\x1b\[[0-9;]*m/);
    await key('q');
    const final = ui.lastFrame();
    await key('\t');
    assert.equal(ui.lastFrame(), final);
  } finally {
    ui.unmount();
    db.close();
    file.remove();
    if (originalColor === undefined) delete process.env.NO_COLOR;
    else process.env.NO_COLOR = originalColor;
  }
});

test('arrival rate uses committed rows between polls', async () => {
  const file = temporaryDatabase();
  const db = seed(file.path);
  const ui = render(<App path={file.path}/>);
  try {
    await delay(80);
    db.exec("INSERT INTO events VALUES(3, 1, '192.0.2.3', 'ssh_failed', 'old log')");
    await delay(1100);
    assert.match(ui.lastFrame()!, /1 events\/s  █/);
  } finally { ui.unmount(); db.close(); file.remove(); }
});
