import {useState} from 'react';
import {Box, Text, useApp, useInput} from 'ink';
import {TextInput} from '@inkjs/ui';
import type {Entry} from './db.js';
import {Pane, printable} from './Pane.js';
import {useDashboard, useTerminalSize} from './useDashboard.js';

const titles = ['Top IPs', 'Live events', 'Alerts'];

export function App({path}: {path: string}) {
  const {exit} = useApp();
  const {width, height} = useTerminalSize();
  const [focus, setFocus] = useState(1);
  const [selected, setSelected] = useState<string>();
  const [paused, setPaused] = useState(false);
  const [editing, setEditing] = useState(false);
  const [filter, setFilter] = useState('');
  const [detail, setDetail] = useState<Entry>();
  const [line, setLine] = useState(0);
  const {snapshot, rates, error} = useDashboard(path, filter, paused);
  const entries = snapshot?.panes[focus] ?? [];
  const index = Math.max(0, entries.findIndex(entry => entry.key === selected));
  const compact = width < 52 || height < 13;
  const bodyRows = Math.max(1, height - 3);
  const paneRows = compact ? Math.max(1, bodyRows - 1) : Math.floor(bodyRows / 3) - 1;
  const detailLines = detail?.detail.split('\n').flatMap(part => {
    const chars = Array.from(printable(part));
    const lines = [];
    for (let i = 0; i < chars.length; i += width) lines.push(chars.slice(i, i + width).join(''));
    return lines.length ? lines : [''];
  }) ?? [];
  const detailRows = Math.max(1, bodyRows - (filter ? 1 : 0));
  const lastPage = Math.max(0, detailLines.length - detailRows);

  useInput((input, key) => {
    if (editing) {
      if (key.escape) setEditing(false);
      return;
    }
    if (input === 'q') { exit(); return; }
    if (detail) {
      if (key.escape || key.return) setDetail(undefined);
      if (key.upArrow) setLine(Math.max(0, Math.min(line, lastPage) - 1));
      if (key.downArrow) setLine(Math.min(lastPage, line + 1));
      return;
    }
    if (key.tab) {
      setFocus((focus + (key.shift ? 2 : 1)) % 3);
      setSelected(undefined);
    } else if (key.upArrow || key.downArrow) {
      const next = Math.max(0, Math.min(entries.length - 1, index + (key.upArrow ? -1 : 1)));
      setSelected(entries[next]?.key);
    } else if (key.return && entries[index]) {
      setDetail(entries[index]);
      setLine(0);
    } else if (input === '/') setEditing(true);
    else if (input === 'p') setPaused(!paused);
  });

  const peak = Math.max(1, ...rates);
  const spark = rates.map(n => '▁▂▃▄▅▆▇█'[Math.round(7 * n / peak)]).join('') || '▁';
  const hints = detail ? 'Enter/Esc back · ↑↓ scroll · q quit'
    : 'Tab/⇧Tab pane · ↑↓ select · Enter detail · / filter · p pause · q quit';
  const start = Math.min(line, lastPage);
  return <Box flexDirection="column" width={width} height={height} overflow="hidden">
    <Text bold wrap="truncate-end">{paused ? 'Paused' : 'loganalyzer'}  {rates.at(-1) ?? 0} events/s  {spark}</Text>
    {editing ? <Box><Text>Filter: </Text><TextInput defaultValue={filter}
      onSubmit={value => { setFilter(value); setEditing(false); setPaused(false); setSelected(undefined); }}/>
    </Box> : filter ? <Text wrap="truncate-end">Filter: {printable(filter)}</Text> : null}
    {detail ? <>
      <Text bold wrap="truncate-end">{titles[focus]} · detail</Text>
      {detailLines.slice(start, start + detailRows).map((part, i) =>
        <Text key={i} wrap="truncate-end">{part}</Text>)}
    </> : error ? <Text wrap="truncate-end">{printable(error)}</Text> :
      titles.map((title, i) => (!compact || i === focus) && <Pane key={title}
        title={title} entries={snapshot?.panes[i] ?? []} focused={focus === i}
        selected={focus === i ? index : 0} rows={paneRows}/>)}
    {!editing && <Text dimColor wrap="truncate-end">{compact && !detail ? 'Tab ↑↓ Enter / p q' : hints}</Text>}
  </Box>;
}
