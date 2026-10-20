import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import test from 'node:test';
import { ApiError, createPreviewStore, servePreviewApi } from './preview-api.mjs';

test('incoming examples belong to the independent account, not a colleague', () => {
  const state = createPreviewStore().snapshot();
  assert.equal(state.account.id, 'you');
  assert.equal(state.messages[0].recipientId, 'you');
  assert.equal(state.messages[0].senderId, 'tom');
  assert.notEqual(state.messages[0].senderId, state.people[0].id);
  assert.equal(state.pings[0].recipientId, 'you');
  assert.equal(state.people.find(person => person.id === 'sarah').pingable, true);
});

test('server enforces recipient ping consent, even when client controls are bypassed', () => {
  const store = createPreviewStore();
  assert.throws(() => store.mutate('/ui-api/pings', { personId: 'tom' }),
    error => error instanceof ApiError && error.status === 409);
  store.mutate('/ui-api/preferences', { allowPings: false });
  store.mutate('/ui-api/read', { pingId: store.snapshot().pings[0].id });
  assert.throws(() => store.mutate('/ui-api/demo-incoming', { personId: 'sarah', kind: 'ping' }),
    /unavailable/);
  assert.equal(store.snapshot().people.find(person => person.id === 'sarah').pingable, true);
});

test('a timed pause expires after exactly 50 minutes and can be cancelled', () => {
  let time = Date.now();
  const store = createPreviewStore({ now: () => time });
  store.mutate('/ui-api/preferences', { pause: true });
  time += 50 * 60_000 - 1;
  assert.equal(store.snapshot().account.pingable, false);
  time += 1;
  assert.equal(store.snapshot().account.pingable, true);
  store.mutate('/ui-api/preferences', { pause: true });
  store.mutate('/ui-api/preferences', { pause: false });
  assert.equal(store.snapshot().account.pingable, true);
});

test('messages support repeated sends, automatic replies and marking incoming history read', () => {
  const replies = [];
  const store = createPreviewStore({ schedule: callback => replies.push(callback) });
  store.mutate('/ui-api/messages', { intent: 'ask', personId: 'lucas', text: 'First question' });
  store.mutate('/ui-api/messages', { intent: 'ask', personId: 'lucas', text: 'Follow-up' });
  for (const reply of replies) reply();
  const received = store.snapshot().messages.filter(message => message.senderId === 'lucas');
  assert.equal(received.length, 2);
  assert.ok(received.every(message => !message.read));
  store.mutate('/ui-api/read', { personId: 'lucas' });
  assert.ok(store.snapshot().messages.filter(message => message.senderId === 'lucas')
    .every(message => message.read));
});

test('demo replies thank the helper in incoming threads and offer help in outgoing requests', () => {
  const replies = [];
  const store = createPreviewStore({ schedule: callback => replies.push(callback) });
  for (const personId of ['sarah', 'lucas', 'emma']) {
    store.mutate('/ui-api/messages', { intent: personId === 'emma' ? 'ask' : 'reply', personId, text: 'Here is my message.' });
    replies.shift()();
    const reply = store.snapshot().messages.at(-1);
    const expected = personId === 'emma' ? /Happy to help/
      : personId === 'lucas' ? /question regarding french payroll/ : /Thanks for your help/;
    assert.match(reply.text, expected);
  }
});

test('a ping introduces the question before a later answer receives thanks', () => {
  const replies = [];
  const store = createPreviewStore({ schedule: callback => replies.push(callback) });
  store.mutate('/ui-api/messages', { personId: 'lucas', text: 'What can I help with?', intent: 'reply' });
  replies.shift()();
  assert.match(store.snapshot().messages.at(-1).text, /question regarding french payroll/);
  assert.equal(store.snapshot().messages.at(-1).intent, 'ask');
  store.mutate('/ui-api/messages', { personId: 'lucas', text: 'Here is how it works.', intent: 'reply' });
  replies.shift()();
  assert.match(store.snapshot().messages.at(-1).text, /Thanks for your help/);
});

test('the same colleague can ask for help and later answer a question from you', () => {
  const replies = [];
  const store = createPreviewStore({ schedule: callback => replies.push(callback) });
  store.mutate('/ui-api/demo-incoming', { personId: 'sarah', kind: 'message' });
  store.mutate('/ui-api/messages', { personId: 'sarah', text: 'Here is my answer.', intent: 'reply' });
  store.mutate('/ui-api/messages', { personId: 'sarah', text: 'Now can you help me?', intent: 'ask' });
  replies.shift()();
  assert.match(store.snapshot().messages.at(-1).text, /Thanks for your help/);
  replies.shift()();
  assert.match(store.snapshot().messages.at(-1).text, /Happy to help/);
  assert.equal(store.snapshot().messages.at(-1).replyToIntent, 'ask');
});

test('Sarah explains the PC 200 bonus when asked for help', () => {
  const replies = [];
  const store = createPreviewStore({ schedule: callback => replies.push(callback) });
  store.mutate('/ui-api/messages', { personId: 'sarah', text: 'How does PC 200 work?', intent: 'ask' });
  replies.shift()();
  const answer = store.snapshot().messages.at(-1).text;
  assert.match(answer, /one month's gross salary/);
  assert.match(answer, /eligibility conditions/);
  assert.match(answer, /prorated/);
});

test('new incoming pings are rejected for opt-out and DND without changing the inbox', () => {
  let time = Date.now();
  const store = createPreviewStore({ now: () => time });
  const before = store.snapshot().pings.length;
  store.mutate('/ui-api/read', { pingId: store.snapshot().pings[0].id });
  store.mutate('/ui-api/preferences', { allowPings: false });
  for (const personId of ['sarah', 'emma']) {
    assert.throws(() => store.mutate('/ui-api/demo-incoming', { personId, kind: 'ping' }), /unavailable/);
    assert.equal(store.snapshot().pings.length, before);
  }
  store.mutate('/ui-api/preferences', { allowPings: true, pause: true });
  assert.throws(() => store.mutate('/ui-api/demo-incoming',
    { personId: 'sarah', kind: 'ping' }), /unavailable/);
  assert.equal(store.snapshot().pings.length, before);
  time += 50 * 60_000;
  store.mutate('/ui-api/demo-incoming', { personId: 'sarah', kind: 'ping' });
  assert.equal(store.snapshot().pings.length, before + 1);
});

test('ping dismissal cannot acknowledge another recipient and duplicate pings are rejected', () => {
  const store = createPreviewStore();
  store.mutate('/ui-api/pings', { personId: 'sarah' });
  assert.throws(() => store.mutate('/ui-api/pings', { personId: 'sarah' }), /already waiting/);
  const outgoing = store.snapshot().pings.find(ping => ping.recipientId === 'sarah');
  assert.throws(() => store.mutate('/ui-api/read', { pingId: outgoing.id }), /not found/);
  const incoming = store.snapshot().pings.find(ping => ping.recipientId === 'you');
  store.mutate('/ui-api/read', { pingId: incoming.id });
  assert.equal(store.snapshot().pings.find(ping => ping.id === incoming.id).read, true);
});

test('a valid reply acknowledges incoming pings, but invalid messages leave them unanswered', () => {
  const store = createPreviewStore({ schedule() {} });
  const pingId = store.snapshot().pings[0].id;
  assert.throws(() => store.mutate('/ui-api/messages', { intent: 'ask', personId: 'lucas', text: ' ' }), /1000/);
  assert.equal(store.snapshot().pings.find(ping => ping.id === pingId).read, false);
  store.mutate('/ui-api/messages', { intent: 'ask', personId: 'lucas', text: 'What can I help with?' });
  assert.equal(store.snapshot().pings.find(ping => ping.id === pingId).read, true);
  assert.equal(store.snapshot().messages.at(-1).recipientId, 'lucas');
});

test('feedback updates server vouches once and cannot be submitted before a reply', () => {
  const replies = [];
  const store = createPreviewStore({ schedule: callback => replies.push(callback) });
  assert.throws(() => store.mutate('/ui-api/votes', { personId: 'sarah', helpful: true }), /asked/);
  store.mutate('/ui-api/messages', { intent: 'ask', personId: 'emma', text: 'Can you help?' });
  assert.throws(() => store.mutate('/ui-api/votes', { personId: 'emma', helpful: true }), /reply/);
  replies.shift()();
  const before = store.snapshot().people[2].vouches;
  store.mutate('/ui-api/votes', { personId: 'emma', helpful: true });
  assert.equal(store.snapshot().people[2].vouches, before + 1);
  assert.throws(() => store.mutate('/ui-api/votes', { personId: 'emma', helpful: true }), /already/);
});

test('input validation rejects unknown people, empty or oversized text and invalid settings', () => {
  const store = createPreviewStore();
  assert.throws(() => store.mutate('/ui-api/messages', { intent: 'ask', personId: 'missing', text: 'Hi' }), /not found/);
  for (const text of ['', ' ', 'a'.repeat(1001), 123]) {
    assert.throws(() => store.mutate('/ui-api/messages', { intent: 'ask', personId: 'sarah', text }), /1000/);
  }
  assert.throws(() => store.mutate('/ui-api/preferences', { allowPings: 'false' }), /boolean/);
  assert.throws(() => store.mutate('/ui-api/preferences', { unknown: true }), /Unknown/);
  assert.throws(() => store.mutate('/ui-api/messages', { personId: 'sarah', text: 'Hi' }), /question/);
  assert.throws(() => store.mutate('/ui-api/demo-incoming', { personId: 'sarah', kind: 'other' }), /Choose/);
});

test('HTTP API rejects cross-origin writes, invalid JSON and oversized bodies', async t => {
  const store = createPreviewStore();
  const server = createServer((request, response) =>
    servePreviewApi(request, response, request.url, store));
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => { server.closeAllConnections(); server.close(); });
  const url = `http://127.0.0.1:${server.address().port}`;
  const headers = { Origin: url,
    'Content-Type': 'application/json' };
  const state = await fetch(`${url}/ui-api/state`, { headers });
  assert.equal(state.status, 200);
  const badOrigin = await fetch(`${url}/ui-api/preferences`, { method: 'POST',
    headers: { ...headers, Origin: 'https://another-site.example' }, body: '{"allowPings":false}' });
  assert.equal(badOrigin.status, 403);
  const badJson = await fetch(`${url}/ui-api/preferences`, { method: 'POST', headers, body: '{' });
  assert.equal(badJson.status, 400);
  const large = await fetch(`${url}/ui-api/messages`, { method: 'POST', headers,
    body: JSON.stringify({ text: 'a'.repeat(9000) }) });
  assert.equal(large.status, 413);
  const updated = await fetch(`${url}/ui-api/preferences`, { method: 'POST', headers,
    body: '{"allowPings":false}' });
  assert.equal((await updated.json()).account.allowPings, false);
});

test('backend bridge protects consent and sends only derived explicit answer fields', async t => {
  const calls = [];
  let enabled = false;
  const bridge = async (path, body) => {
    calls.push({ path, body });
    if (path === '/preferences') return { capture_enabled: enabled,
      allowed_surfaces: ['other'], hidden_topics: [] };
    return { accepted: true };
  };
  const store = createPreviewStore({ schedule() {} });
  const server = createServer((request, response) =>
    servePreviewApi(request, response, request.url, store, bridge));
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => { server.closeAllConnections(); server.close(); });
  const url = `http://127.0.0.1:${server.address().port}`;
  const post = (path, body, origin = url) => fetch(`${url}/ui-api${path}`, {
    method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  assert.equal((await post('/capture-preferences', {}, 'https://attacker.example')).status, 403);
  assert.equal(calls.length, 0);
  const answer = { personId: 'tom', intent: 'reply',
    text: 'For the year-end bonus, check eligible service months and absences before calculating the amount.',
    writing: { chars_typed: 95, fluency_run_seconds: 15, longest_fluency_run_seconds: 15 } };
  await post('/messages', answer);
  assert.equal(calls.some(call => call.path === '/analyze'), false);
  enabled = true;
  await post('/messages', answer);
  const signal = calls.find(call => call.path === '/analyze').body;
  assert.equal(signal.is_reply, true);
  assert.equal(signal.prior_message_char_count > 0, true);
  assert.equal(signal.surface, 'other');
  assert.ok(signal.topics.includes('year_end_bonus'));
  assert.ok(!JSON.stringify(signal).includes('check eligible'));
  assert.ok(Object.values(signal).every(value => typeof value !== 'string' || !value.includes(' ')));
  await post('/messages', answer);
  const signals = calls.filter(call => call.path === '/analyze');
  assert.equal(signals[0].body.context_id, signals[1].body.context_id);
  const before = signals.length;
  await post('/messages', { ...answer, personId: 'sarah', intent: 'ask' });
  assert.equal(calls.filter(call => call.path === '/analyze').length, before);
});
