import {Box, Text} from 'ink';
import type {Entry} from './db.js';

export function printable(value: string): string {
  return Array.from(value, char => {
    const n = char.codePointAt(0)!;
    return n < 32 || (n >= 127 && n <= 159) ? '\\x' + n.toString(16).padStart(2, '0') : char;
  }).join('');
}

export function inkColor(color: string) {
  return process.env.NO_COLOR === undefined ? color : undefined;
}

const headings = [
  ['Address', 'Events'],
  ['UTC', 'Address', 'Event'],
  ['Level', 'Rule', 'Address', 'Count'],
];

function columns(pane: number, width: number) {
  if (pane === 0) return [width - 7, 6];
  if (pane === 1) {
    const address = Math.max(10, Math.floor((width - 10) / 2));
    return [8, address, width - address - 10];
  }
  const rule = Math.floor((width - 15) / 2);
  return [6, rule, width - rule - 14, 5];
}

function rowText(values: string[], sizes: number[], numeric: boolean) {
  return values.map((value, index) => {
    const size = Math.max(1, sizes[index]);
    const safe = printable(value);
    const text = safe.length > size ? safe.slice(0, size - 1) + '…' : safe;
    return numeric && index === values.length - 1 ? text.padStart(size) : text.padEnd(size);
  }).join(' ');
}

export function Pane({pane, title, entries, selected, focused, width, height, filtered}: {
  pane: number; title: string; entries: Entry[]; selected: number; focused: boolean;
  width: number; height: number; filtered: boolean;
}) {
  const framed = height >= 5 && width >= 30;
  const table = framed && width >= (pane === 2 ? 48 : 27);
  const rows = Math.max(0, height - 1 - Number(table) - (framed ? 2 : 0));
  const start = Math.max(0, selected - rows + 1);
  const sizes = columns(pane, width - 6);
  const accent = inkColor(focused ? 'cyan' : 'gray');
  return <Box flexDirection="column" width={width} height={height} overflow="hidden"
    borderStyle={framed ? 'round' : undefined} borderColor={accent} paddingX={framed ? 1 : 0}>
    <Box justifyContent="space-between">
      <Text bold color={focused ? inkColor('cyan') : undefined}>{focused ? '› ' + title : title}</Text>
      {width >= 28 && rows > 0 && <Text dimColor>{entries.length ? `${start + 1}–${Math.min(entries.length, start + rows)} / ${entries.length}` : '0'}</Text>}
    </Box>
    {table && <Text dimColor wrap="truncate-end">  {rowText(headings[pane], sizes, pane !== 1)}</Text>}
    {!entries.length && <Text dimColor wrap="truncate-end">{filtered ? 'No matches' : 'No records yet'}</Text>}
    {entries.slice(start, start + rows).map((entry, i) => {
      const active = focused && start + i === selected;
      const severity = entry.severity === 'high' ? 'red' : entry.severity === 'medium' ? 'yellow' : 'cyan';
      return <Text key={entry.key} wrap="truncate-end" inverse={active} bold={active}
        color={entry.severity ? inkColor(severity) : active ? inkColor('cyan') : undefined}>
        {(active ? '› ' : '  ') + (table ? rowText(entry.cells, sizes, pane !== 1) : printable(entry.label))}
      </Text>;
    })}
  </Box>;
}
