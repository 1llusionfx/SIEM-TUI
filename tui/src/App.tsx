import {useState} from 'react';
import {Box, Text, useApp, useInput} from 'ink';
import {TextInput} from '@inkjs/ui';
import type {Entry} from './db.js';
import {inkColor, Pane, printable} from './Pane.js';
import {StatusBar} from './StatusBar.js';
import {useDashboard, useTerminalSize} from './useDashboard.js';

const titles = ['Top IPs', 'Live events', 'Alerts'];

export function App({path}: {path: string}) {
  const {exit} = useApp();
  const {width, height} = useTerminalSize();
  const [focus, setFocus] = useState(1);
  const [selected, setSelected] = useState<Record<number, string | undefined>>({});
  const [paused, setPaused] = useState(false);
  const [editing, setEditing] = useState(false);
  const [filter, setFilter] = useState('');
  const [detail, setDetail] = useState<Entry>();
  const [line, setLine] = useState(0);
  const {snapshot, rates, error} = useDashboard(path, filter, paused);
  const entries = snapshot?.panes[focus] ?? [];
  const index = Math.max(0, entries.findIndex(entry => entry.key === selected[focus]));
  const compact = width < 76 || height < 17;
  // Ink clears the screen when a frame fills the terminal. Reserve the final line.
  const screenHeight = Math.max(1, height - 1);
  const bodyRows = Math.max(1, screenHeight - 2 - Number(Boolean(filter || editing)) - Number(Boolean(error)));
  const alertRows = Math.max(6, Math.floor(bodyRows * 0.4));
  const ipWidth = Math.max(29, Math.floor(width * 0.31));
  const detailWidth = Math.max(1, width - (compact ? 2 : 4));
  const detailLines = detail?.detail.split('\n').flatMap(part => {
    const chars = Array.from(printable(part));
    const lines = [];
    for (let i = 0; i < chars.length; i += detailWidth) lines.push(chars.slice(i, i + detailWidth).join(''));
    return lines.length ? lines : [''];
  }) ?? [];
  const detailRows = Math.max(1, bodyRows - (compact ? 1 : 4));
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
    } else if (key.upArrow || key.downArrow) {
      const next = Math.max(0, Math.min(entries.length - 1, index + (key.upArrow ? -1 : 1)));
      setSelected({...selected, [focus]: entries[next]?.key});
    } else if (key.return && entries[index]) {
      setDetail(entries[index]);
      setLine(0);
    } else if (input === '/') setEditing(true);
    else if (input === 'p') setPaused(!paused);
  });

  const peak = Math.max(1, ...rates);
  const spark = rates.map(n => '▁▂▃▄▅▆▇█'[Math.round(7 * n / peak)]).join('') || '▁';
  const hints = detail ? [['Esc', 'back'], ['↑↓', 'scroll'], ['q', 'quit']]
    : editing ? [['Enter', 'apply'], ['Esc', 'cancel']]
    : [['Tab/⇧Tab', 'pane'], ['↑↓', 'select'], ['Enter', 'inspect'], ['/', 'filter'],
      ['p', paused ? 'resume' : 'pause'], ['q', 'quit']];
  const start = Math.min(line, lastPage);
  function pane(i: number, w: number, h: number) {
    return <Pane pane={i} title={titles[i]} entries={snapshot?.panes[i] ?? []}
      selected={i === focus ? index : 0} focused={i === focus} width={w} height={h} filtered={Boolean(filter)}/>;
  }
  const state = paused ? 'Paused' : error || !snapshot ? 'Waiting' : 'Live';
  return <Box flexDirection="column" width={width} height={screenHeight} overflow="hidden">
    <Box justifyContent="space-between" height={1}>
      <Text wrap="truncate-end"><Text bold color={inkColor('cyan')}>loganalyzer</Text>  <Text color={inkColor(state === 'Live' ? 'green' : 'yellow')}>● {state}</Text></Text>
      {width >= 42 && <Text wrap="truncate-end"><Text dimColor>{width >= 64 ? `${snapshot?.total ?? 0} events   │   ` : ''}</Text>
        <Text color={inkColor('cyan')}>{rates.at(-1) ?? 0} events/s  {spark}</Text></Text>}
    </Box>
    {editing ? <Box height={1} overflow="hidden"><Text>Filter: </Text><TextInput defaultValue={filter}
      onSubmit={value => { setFilter(value); setEditing(false); setPaused(false); setSelected({}); }}/>
    </Box> : filter ? <Text wrap="truncate-end">Filter: {printable(filter)}</Text> : null}
    {error && <Text color={inkColor('yellow')} wrap="truncate-end">{printable(error)}</Text>}
    {detail ? <Box flexDirection="column" height={bodyRows} paddingX={1}
      borderStyle={compact ? undefined : 'round'} borderColor={inkColor('cyan')} overflow="hidden">
      <Text bold color={inkColor('cyan')} wrap="truncate-end">{titles[focus]} / {focus === 1 ? 'Raw event' : 'Detail'}</Text>
      {!compact && <Text dimColor wrap="truncate-end">{printable(detail.label)}</Text>}
      {detailLines.slice(start, start + detailRows).map((part, i) =>
        <Text key={i} wrap="truncate-end">{part}</Text>)}
    </Box> : compact ? pane(focus, width, bodyRows) : <>
      <Box gap={1}>{pane(0, ipWidth, bodyRows - alertRows)}{pane(1, width - ipWidth - 1, bodyRows - alertRows)}</Box>
      {pane(2, width, alertRows)}
    </>}
    <StatusBar width={width} items={hints}/>
  </Box>;
}
