import {Box, Text} from 'ink';
import type {Entry} from './db.js';

export function printable(value: string): string {
  return Array.from(value, char => {
    const n = char.codePointAt(0)!;
    return n < 32 || (n >= 127 && n <= 159) ? '\\x' + n.toString(16).padStart(2, '0') : char;
  }).join('');
}

export function Pane({title, entries, selected, focused, rows}: {
  title: string; entries: Entry[]; selected: number; focused: boolean; rows: number;
}) {
  const start = Math.max(0, selected - rows + 1);
  return <Box flexDirection="column" flexShrink={0}>
    <Text bold wrap="truncate-end">{focused ? '› ' : '  '}{title}</Text>
    {entries.length === 0 && <Text dimColor>  —</Text>}
    {entries.slice(start, start + rows).map((entry, i) => {
      const color = process.env.NO_COLOR === undefined
        ? ({high: 'red', medium: 'yellow', low: 'cyan'}[entry.severity ?? '']) : undefined;
      return <Text key={entry.key} color={color} wrap="truncate-end">
        {focused && start + i === selected ? '> ' : '  '}{printable(entry.label)}
      </Text>;
    })}
  </Box>;
}
