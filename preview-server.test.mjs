import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import test from 'node:test';
import { servePreview } from './preview-server.mjs';

test('only literal preview assets can be read through HTTP', async t => {
  const server = createServer(servePreview);
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => { server.closeAllConnections(); server.close(); });
  const origin = `http://127.0.0.1:${server.address().port}`;
  for (const path of ['/.env', '/../.env', '/%2e%2e/.env', '/%252e%252e/.env',
    '/C:/Windows/win.ini', '/file:///etc/passwd', '/popup.html%00.env', '/AGENTS.md']) {
    const response = await fetch(`${origin}${path}`);
    assert.equal(response.status, 404, path);
    assert.equal(await response.text(), 'Not found');
  }
  const page = await fetch(`${origin}/popup.html?file=../.env`);
  assert.equal(page.status, 200);
  assert.match(page.headers.get('content-type'), /text\/html/);
  const content = await page.text();
  assert.match(content, /Detect hesitation/);
  assert.ok(!content.includes('WHOKNOWS_AUTH_TOKEN='));
  const catalog = await fetch(`${origin}/topic-catalog.json`);
  assert.equal(catalog.status, 200);
  assert.ok((await catalog.json()).some(topic => topic.token === 'notice_period'));
});
