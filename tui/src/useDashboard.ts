import {useEffect, useState} from 'react';
import {useStdout} from 'ink';
import {readSnapshot, type Snapshot} from './db.js';

export function useTerminalSize() {
  const {stdout} = useStdout();
  const measure = () => ({width: stdout.columns || 80, height: stdout.rows || 24});
  const [size, setSize] = useState(measure);
  useEffect(() => {
    const resize = () => setSize({width: stdout.columns || 80, height: stdout.rows || 24});
    stdout.on('resize', resize);
    return () => { stdout.off('resize', resize); };
  }, [stdout]);
  return size;
}

export function useDashboard(path: string, filter: string, paused: boolean) {
  const [snapshot, setSnapshot] = useState<Snapshot>();
  const [rates, setRates] = useState<number[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    if (paused) return;
    let previous: {count: number; time: number} | undefined;
    const poll = () => {
      try {
        const next = readSnapshot(path, filter);
        const now = performance.now();
        if (previous) {
          const rate = Math.max(0, Math.round(1000 * (next.total - previous.count) / (now - previous.time)));
          setRates(history => [...history.slice(-19), rate]);
        }
        previous = {count: next.total, time: now};
        setSnapshot(next);
        setError('');
      } catch (cause) {
        previous = undefined;
        const message = cause instanceof Error ? cause.message : String(cause);
        const waiting = /locked|busy|unable to open|does not exist|no such table|directory does not exist/i.test(message);
        setError(waiting ? 'waiting for daemon…' : message);
      }
    };
    poll();
    const timer = setInterval(poll, 1000);
    return () => clearInterval(timer);
  }, [path, filter, paused]);
  return {snapshot, rates, error};
}
