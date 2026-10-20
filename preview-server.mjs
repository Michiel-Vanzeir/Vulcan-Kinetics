import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { createPreviewStore, servePreviewApi } from './preview-api.mjs';

try { process.loadEnvFile(); } catch (error) {
  if (error.code !== 'ENOENT') throw error;
}

const PORT = 4173;
// Same variable as the capture agent; the Flask backend (Neo4J-backend/run.py) listens on 5000.
const BACKEND_URL = (process.env.WHOKNOWS_BACKEND_URL || 'http://127.0.0.1:5000').replace(/\/$/, '');
const previewStore = createPreviewStore();
const ASSETS = new Map([
  ['/', [() => readFile(new URL('index.html', import.meta.url)), 'text/html']],
  ['/index.html', [() => readFile(new URL('index.html', import.meta.url)), 'text/html']],
  ['/popup.html', [() => readFile(new URL('popup.html', import.meta.url)), 'text/html']],
  ['/popup.css', [() => readFile(new URL('popup.css', import.meta.url)), 'text/css']],
  ['/popup.js', [() => readFile(new URL('popup.js', import.meta.url)), 'text/javascript']],
  ['/people-panel.html',
    [() => readFile(new URL('people-panel.html', import.meta.url)), 'text/html']],
  ['/people-panel.css',
    [() => readFile(new URL('people-panel.css', import.meta.url)), 'text/css']],
  ['/people-panel.js',
    [() => readFile(new URL('people-panel.js', import.meta.url)), 'text/javascript']],
  ['/topic-catalog.json',
    [() => readFile(new URL('topic-catalog.json', import.meta.url)), 'application/json']],
  ['/whoknows-icon.png',
    [() => readFile(new URL('whoknows-icon.png', import.meta.url)), 'image/png']],
  ['/profile-portraits.png',
    [() => readFile(new URL('profile-portraits.png', import.meta.url)), 'image/png']],
  ['/account-portrait.png',
    [() => readFile(new URL('account-portrait.png', import.meta.url)), 'image/png']],
]);

/** Serve only preview assets and proxy the fixed local health endpoint to avoid CORS issues. */
export async function servePreview(request, response) {
  let pathname;
  try {
    pathname = new URL(request.url, 'http://localhost').pathname;
  } catch {
    response.writeHead(400).end('Invalid request URL');
    return;
  }
  if (pathname.startsWith('/ui-api/')) {
    await servePreviewApi(request, response, pathname, previewStore, backendRequest);
    return;
  }
  if (request.method !== 'GET') {
    response.writeHead(405, { Allow: 'GET' }).end('Method not allowed');
    return;
  }
  if (pathname === '/preview-health') {
    try {
      const health = await fetch(`${BACKEND_URL}/health`, {
        signal: AbortSignal.timeout(3000),
        redirect: 'error',
      });
      await health.body?.cancel();
      response.writeHead(health.ok ? 200 : 503, { 'Cache-Control': 'no-store' }).end();
    } catch {
      response.writeHead(503, { 'Cache-Control': 'no-store' }).end('Backend unavailable');
    }
    return;
  }
  const asset = ASSETS.get(pathname);
  if (!asset) {
    response.writeHead(404).end('Not found');
    return;
  }
  try {
    const content = await asset[0]();
    response.writeHead(200, {
      'Content-Type': asset[1],
      'Cache-Control': 'no-store',
    }).end(content);
  } catch (error) {
    console.error(`Cannot serve preview asset: ${error.message}`);
    response.writeHead(500).end('Unable to load preview asset');
  }
}

/** Keep employee credentials server-side and proxy only the employee-owned APIs. */
async function backendRequest(path, body) {
  const token = process.env.WHOKNOWS_AUTH_TOKEN;
  if (!token) throw new Error('Run node configure-demo.mjs and restart both servers.');
  const upstream = await fetch(`${BACKEND_URL}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(3000), redirect: 'error',
  });
  const result = await upstream.json();
  if (!upstream.ok) throw new Error(result.error || 'Backend rejected the request.');
  return result;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const server = createServer(servePreview);
  server.on('error', (error) => {
    console.error(`Preview server failed: ${error.message}`);
    process.exitCode = 1;
  });
  server.listen(PORT, '127.0.0.1', () => {
    console.info(`Popup preview: http://127.0.0.1:${PORT}`);
  });
}
