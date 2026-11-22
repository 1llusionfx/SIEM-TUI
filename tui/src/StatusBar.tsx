import {Text} from 'ink';
import {inkColor} from './Pane.js';

export function StatusBar({items, width}: {items: string[][]; width: number}) {
  const compact = items.reduce((n, [key, label]) => n + key.length + label.length + 4, 0) > width;
  return <Text wrap="truncate-end">{items.map(([key, label]) =>
    <Text key={key}><Text bold inverse={!compact} color={inkColor('cyan')}>{key}</Text>
      {compact ? ' ' : <Text dimColor> {label}   </Text>}</Text>)}</Text>;
}
