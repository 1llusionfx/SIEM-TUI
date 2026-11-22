import Database from 'better-sqlite3';

export interface Entry {
  key: string;
  label: string;
  detail: string;
  severity?: string;
}

export interface Snapshot {
  total: number;
  panes: Entry[][];
}

interface EventRow {
  id: number; ts: number; ip: string; event_type: string; raw: string;
}

interface AlertRow {
  id: number; rule: string; ip: string; severity: string; count: number;
  details: string; first_seen: number; last_seen: number;
}

function time(ts: number): string {
  return new Date(ts * 1000).toISOString().slice(11, 19);
}

export function readSnapshot(path: string, filter: string): Snapshot {
  const db = new Database(path, {readonly: true, fileMustExist: true, timeout: 100});
  try {
    return db.transaction(() => {
      const total = db.prepare('SELECT count(*) AS n FROM events').get() as {n: number};
      const term = filter.toLowerCase();
      const match = "instr(lower(raw || ' ' || ip || ' ' || event_type), ?) > 0";
      const where = term ? ' WHERE ' + match : '';
      const args = term ? [term] : [];
      const ips = db.prepare('SELECT ip, count(*) AS n FROM events' + where +
        ' GROUP BY ip ORDER BY n DESC, ip LIMIT 100').all(...args) as {ip: string; n: number}[];
      const events = db.prepare('SELECT id, ts, ip, event_type, raw FROM events' + where +
        ' ORDER BY id DESC LIMIT 100').all(...args) as EventRow[];
      const alerts = db.prepare(`SELECT * FROM alerts
        WHERE instr(lower(rule || ' ' || ip || ' ' || severity || ' ' || details), ?) > 0
        ORDER BY last_seen DESC, id DESC LIMIT 100`).all(term) as AlertRow[];
      return {
        total: total.n,
        panes: [
          ips.map(row => ({key: row.ip, label: `${row.ip}  ${row.n}`,
            detail: `${row.ip} · ${row.n} matching events`})),
          events.map(row => ({key: String(row.id), label: `${time(row.ts)} ${row.ip} ${row.event_type}`,
            detail: row.raw})),
          alerts.map(row => ({key: String(row.id), severity: row.severity,
            label: `${row.severity} ${row.rule} ${row.ip} ×${row.count}`,
            detail: `${row.rule} · ${row.severity} · ${row.ip}\n${row.details}\n` +
              `${row.count} observations · ${new Date(row.first_seen * 1000).toISOString()} to ` +
              new Date(row.last_seen * 1000).toISOString()})),
        ],
      };
    })();
  } finally {
    db.close();
  }
}
