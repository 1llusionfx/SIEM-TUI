import {resolve} from 'node:path';
import {render} from 'ink';
import {App} from './App.js';

const path = resolve(process.argv[2] ?? '../loganalyzer.sqlite3');
await render(<App path={path}/>).waitUntilExit();
process.stdout.write('', () => process.exit(0));
