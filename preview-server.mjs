import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { createPreviewStore, servePreviewApi } from './preview-api.mjs';

const PORT = 4173;
const previewStore = createPreviewStore();
const ASSETS = new Map([
  ['/', ['index.html', 'text/html']],
  ['/index.html', ['index.html', 'text/html']],
  ['/popup.html', ['popup.html', 'text/html']],
  ['/popup.css', ['popup.css', 'text/css']],
  ['/popup.js', ['popup.js', 'text/javascript']],
  ['/people-panel.html', ['people-panel.html', 'text/html']],
  ['/people-panel.css', ['people-panel.css', 'text/css']],
  ['/people-panel.js', ['people-panel.js', 'text/javascript']],
  ['/whoknows-icon.png', ['whoknows-icon.png', 'image/png']],
  ['/profile-portraits.png', ['profile-portraits.png', 'image/png']],
  ['/account-portrait.png', ['account-portrait.png', 'image/png']],
]);

/** Serve only preview assets and proxy the fixed local health endpoint to avoid CORS issues. */
async function servePreview(request, response) {
  const pathname = new URL(request.url, 'http://localhost').pathname;
  if (pathname.startsWith('/ui-api/')) {
    await servePreviewApi(request, response, pathname, previewStore);
    return;
  }
  if (request.method !== 'GET') {
    response.writeHead(405, { Allow: 'GET' }).end('Method not allowed');
    return;
  }
  if (pathname === '/preview-health') {
    try {
      const health = await fetch('http://127.0.0.1:8000/health', {
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
    const content = await readFile(new URL(asset[0], import.meta.url));
    response.writeHead(200, {
      'Content-Type': asset[1],
      'Cache-Control': 'no-store',
    }).end(content);
  } catch (error) {
    console.error(`Cannot serve ${asset[0]}: ${error.message}`);
    response.writeHead(500).end('Unable to load preview asset');
  }
}

const server = createServer(servePreview);
server.on('error', (error) => {
  console.error(`Preview server failed: ${error.message}`);
  process.exitCode = 1;
});
server.listen(PORT, '127.0.0.1', () => {
  console.info(`Popup preview: http://127.0.0.1:${PORT}`);
});
