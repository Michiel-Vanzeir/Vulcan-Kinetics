import { randomBytes } from 'node:crypto';
import { writeFileSync } from 'node:fs';

// Exclusive creation prevents replacing a teammate's existing credentials or settings.
const settings = [
  `WHOKNOWS_AUTH_TOKEN=${randomBytes(32).toString('hex')}`,
  'WHOKNOWS_USER_ID=emp_014',
  'WHOKNOWS_BACKEND_URL=http://127.0.0.1:5000',
  '',
].join('\n');
try {
  writeFileSync(new URL('.env', import.meta.url), settings, { flag: 'wx' });
  console.info('Created local .env credentials. Keep this file private; do not commit it.');
} catch (error) {
  if (error.code !== 'EEXIST') throw error;
  console.info('.env already exists and was left unchanged.');
}
