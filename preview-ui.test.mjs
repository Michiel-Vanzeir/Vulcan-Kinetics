import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import { createPreviewStore } from './preview-api.mjs';

/** Minimal DOM harness for exercising the UI's event wiring against the real demo store. */
class Element {
  constructor(tag = 'div') {
    this.tag = tag;
    this.children = [];
    this.events = {};
    this.attributes = {};
    this.dataset = {};
    this.value = '';
    this.className = '';
    this.isConnected = true;
    this.hidden = false;
    this.classList = { toggle: (name, enabled) => {
      const classes = new Set(this.className.split(' ').filter(Boolean));
      if (enabled) classes.add(name); else classes.delete(name);
      this.className = [...classes].join(' ');
    } };
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(event, callback) { this.events[event] = callback; }
  focus() {}
  get options() { return this.children; }
  get selectedOptions() { return this.children.filter(option => option.selected); }
}

/** Traverse the UI's generated controls without duplicating their implementation. */
function descendants(node) {
  return [node, ...node.children.flatMap(descendants)];
}

/** Load the UI with an API bridge so every button uses the same server-side mutations. */
async function setup() {
  const replies = [];
  const store = createPreviewStore({ schedule: callback => replies.push(callback) });
  const nodes = new Map();
  let capture = { capture_enabled: false, allowed_surfaces: [], hidden_topics: [] };
  const document = {
    createElement: tag => new Element(tag),
    addEventListener() {},
    querySelectorAll(selector) {
      const inputs = descendants(this.querySelector('#capture-surfaces'))
        .filter(node => node.tag === 'input');
      return selector.endsWith(':checked') ? inputs.filter(node => node.checked) : inputs;
    },
    querySelector(selector) {
      const dynamic = [...nodes.values()].flatMap(descendants).find(node =>
        selector.startsWith('#') ? node.id === selector.slice(1)
          : selector.startsWith('.') && node.className.split(' ').includes(selector.slice(1)));
      if (dynamic) return dynamic;
      if (!nodes.has(selector)) nodes.set(selector, new Element());
      return nodes.get(selector);
    },
  };
  const context = vm.createContext({ document, AbortSignal, URLSearchParams, setTimeout,
    clearTimeout, location: { search: '' },
    setInterval() {}, fetch: async (url, options = {}) => {
      try {
        if (url === '/topic-catalog.json') return { ok: true, json: async () =>
          JSON.parse(readFileSync(new URL('./topic-catalog.json', import.meta.url), 'utf8')) };
        const path = url.replace('/ui-api', '');
        const body = options.body ? JSON.parse(options.body) : undefined;
        if (path === '/capture-preferences') {
          if (body) capture = body;
          return { ok: true, json: async () => capture };
        }
        if (path === '/experts') return { ok: true, json: async () =>
          ({ experts: [], knowledge_gaps: body.topics }) };
        const state = body === undefined ? store.snapshot() : store.mutate(`/ui-api${path}`, body);
        return { ok: true, json: async () => state };
      } catch (error) {
        return { ok: false, json: async () => ({ error: error.message }) };
      }
    } });
  vm.runInContext(readFileSync(new URL('./people-panel.js', import.meta.url), 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  const click = async (selector, text) => {
    const root = document.querySelector(selector);
    const control = text ? descendants(root).find(node => node.textContent === text) : root;
    assert.ok(control, `Missing control: ${text || selector}`);
    await control.events.click({ target: control, preventDefault() {} });
    await new Promise(resolve => setImmediate(resolve));
  };
  return { store, replies, document, context, click };
}

test('Account opens an inbox; settings are isolated and changes reach the server', async () => {
  const app = await setup();
  await app.click('#account-button');
  assert.equal(app.document.querySelector('#account-view').hidden, false);
  assert.equal(app.document.querySelector('.list-view').hidden, true);
  assert.ok(descendants(app.document.querySelector('#inbox-items'))
    .some(node => node.textContent === 'Tom Janssens'));
  await app.click('#settings-button');
  assert.equal(app.document.querySelector('#account-view').hidden, true);
  assert.equal(app.document.querySelector('#settings-view').hidden, false);
  const allow = app.document.querySelector('#allow-pings');
  allow.checked = false;
  await allow.events.change({ target: allow });
  assert.equal(app.store.snapshot().account.allowPings, false);
  await app.click('#settings-back');
  assert.equal(app.document.querySelector('#account-view').hidden, false);
});

test('incoming messages open as chat; repeated replies and drafts survive inbox navigation', async () => {
  const app = await setup();
  await app.click('#account-button');
  const incoming = descendants(app.document.querySelector('#inbox-items'))
    .find(node => node.className.includes('inbox-thread'));
  await incoming.events.click();
  const chat = app.document.querySelector('.chat-view');
  assert.equal(chat.hidden, false);
  assert.ok(app.store.snapshot().messages[0].read);
  assert.ok(!descendants(chat).some(node => node.textContent === 'Did this answer help?'));
  let composer = descendants(chat).find(node => node.className === 'chat-composer');
  let input = descendants(composer).find(node => node.tag === 'textarea');
  input.value = 'Yes, I can help.';
  input.events.input();
  composer.events.submit({ preventDefault() {} });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(input.value, '');
  input.value = 'A draft that must survive polling';
  input.events.input();
  app.replies.shift()();
  await vm.runInContext('refresh()', app.context);
  assert.equal(input.value, 'A draft that must survive polling');
  await app.click('#account-button');
  await app.click('#account-back');
  assert.equal(app.document.querySelector('.chat-view').hidden, false);
  assert.equal(input.value, 'A draft that must survive polling');
  composer.events.submit({ preventDefault() {} });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(app.store.snapshot().messages.filter(message => message.senderId === 'you').length, 2);
});

test('incoming ping opens an empty composer and can be dismissed', async () => {
  const app = await setup();
  await app.click('#account-button');
  await app.click('#inbox-items', 'Message');
  const input = descendants(app.document.querySelector('.chat-view'))
    .find(node => node.tag === 'textarea');
  assert.equal(input.value, '');
  await app.click('#account-button');
  await app.click('#inbox-items', 'Dismiss');
  assert.ok(app.store.snapshot().pings[0].read);
  assert.ok(!descendants(app.document.querySelector('#inbox-items'))
    .some(node => node.textContent === 'Dismiss'));
});

test('answering a ping clears it from account only after a message is successfully sent', async () => {
  const app = await setup();
  await app.click('#account-button');
  await app.click('#inbox-items', 'Message');
  assert.equal(app.store.snapshot().pings[0].read, false);
  const chat = app.document.querySelector('.chat-view');
  const composer = descendants(chat).find(node => node.className === 'chat-composer');
  const input = descendants(composer).find(node => node.tag === 'textarea');
  input.value = 'What can I help you with?';
  input.events.input();
  composer.events.submit({ preventDefault() {} });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(app.store.snapshot().pings[0].read, true);
  await app.click('#account-button');
  assert.ok(!descendants(app.document.querySelector('#inbox-items'))
    .some(node => node.textContent === 'Dismiss'));
  assert.ok(descendants(app.document.querySelector('#inbox-items'))
    .some(node => node.textContent === 'Lucas Martin'));
});

test('outgoing help requests show feedback only after a reply', async () => {
  const app = await setup();
  await vm.runInContext('openChat("emma", "people")', app.context);
  const chat = app.document.querySelector('.chat-view');
  const composer = descendants(chat).find(node => node.className === 'chat-composer');
  composer.events.submit({ preventDefault() {} });
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(!descendants(chat).some(node => node.textContent === 'Yes, vouch'));
  app.replies.shift()();
  await vm.runInContext('refresh()', app.context);
  await app.click('.chat-view', 'Yes, vouch');
  assert.equal(app.store.snapshot().people[2].vouches, 10);
});

test('asking a previously incoming colleague starts an explicit outgoing question', async () => {
  const app = await setup();
  app.store.mutate('/ui-api/demo-incoming', { personId: 'sarah', kind: 'message' });
  await vm.runInContext('refresh()', app.context);
  await app.click('.body', 'Open chat with Sarah');
  const chat = app.document.querySelector('.chat-view');
  const composer = descendants(chat).find(node => node.className === 'chat-composer');
  const input = descendants(composer).find(node => node.tag === 'textarea');
  input.value = 'Can you help me with my payroll question?';
  composer.events.submit({ preventDefault() {} });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(app.store.snapshot().messages.at(-1).intent, 'ask');
  app.replies.shift()();
  await vm.runInContext('refresh()', app.context);
  assert.match(app.store.snapshot().messages.at(-1).text, /Happy to help/);
  assert.ok(descendants(chat).some(node => node.textContent === 'Yes, vouch'));
});

test('profile information, outgoing pings and search controls use the current state', async () => {
  const app = await setup();
  const card = descendants(app.document.querySelector('.body'))
    .find(node => node.tag === 'article');
  const information = descendants(card).find(node => node.className === 'information-toggle');
  const details = descendants(card).find(node => node.className === 'card-information');
  await information.events.click();
  assert.equal(details.hidden, false);
  descendants(card).find(node => node.className === 'information-back').events.click();
  assert.equal(details.hidden, true);
  const ping = descendants(card).find(node => node.attributes['aria-label'] === 'Ping Sarah De Vos');
  await ping.events.click();
  assert.ok(app.store.snapshot().pings.some(item => item.recipientId === 'sarah'));
  const currentPing = descendants(app.document.querySelector('.body'))
    .find(node => node.attributes['aria-label'] === 'Ping Sarah De Vos');
  assert.equal(currentPing.disabled, true);
  app.document.querySelector('#people-search').value = 'no-matching-colleague';
  app.document.querySelector('form.ask-box').events.submit({ preventDefault() {} });
  assert.ok(descendants(app.document.querySelector('.body'))
    .some(node => node.textContent === 'No matching colleagues. Try a name or topic.'));
});

test('detection, pause/resume, retry and close/reopen controls work', async () => {
  const app = await setup();
  await app.click('#account-button');
  await app.click('#settings-button');
  const detection = app.document.querySelector('#account-auto-detect');
  detection.checked = false;
  await detection.events.change({ target: detection });
  assert.equal(app.store.snapshot().account.autoDetect, undefined);
  await app.click('#dnd-button');
  assert.equal(app.store.snapshot().account.pingable, false);
  assert.equal(app.document.querySelector('#dnd-button').textContent, 'Resume pings');
  await app.click('#dnd-button');
  assert.equal(app.store.snapshot().account.pingable, true);
  await app.click('.close');
  assert.equal(app.document.querySelector('.panel').hidden, true);
  await app.click('#reopen');
  assert.equal(app.document.querySelector('.panel').hidden, false);
  assert.equal(app.document.querySelector('#settings-view').hidden, false);
  await app.click('#retry');
  assert.equal(app.document.querySelector('#ui-error').hidden, true);
});

test('all agent topics remain visible as backend knowledge gaps', async () => {
  const app = await setup();
  vm.runInContext("pageParams.set('topics', 'notice_period,country_ES'); renderPeople();", app.context);
  await new Promise(resolve => setImmediate(resolve));
  const content = descendants(app.document.querySelector('.body'));
  assert.ok(content.some(node => node.textContent === 'notice period'));
  assert.ok(content.some(node => node.textContent === 'spain'));
  assert.equal(content.filter(node => node.textContent ===
    'Knowledge gap: no qualifying recent signals.').length, 2);
  assert.equal(content.filter(node => node.tag === 'article').length, 0);
});

test('capture settings persist independently of synthetic account preferences', async () => {
  const app = await setup();
  const surfaces = app.document.querySelectorAll('#capture-surfaces input');
  surfaces[0].checked = true;
  const detection = app.document.querySelector('#account-auto-detect');
  detection.checked = true;
  await detection.events.change({ target: detection });
  assert.equal(detection.checked, true);
  assert.equal(surfaces[0].checked, true);
  assert.equal(app.store.snapshot().account.autoDetect, undefined);
  assert.match(app.document.querySelector('#capture-status').textContent, /selected desktop apps/);
});

test('compact popup changes real capture consent and preserves app and topic preferences', async () => {
  const nodes = new Map();
  const document = { querySelector(selector) {
    if (!nodes.has(selector)) nodes.set(selector, new Element());
    return nodes.get(selector);
  } };
  let preferences = { capture_enabled: false, allowed_surfaces: ['teams_desktop'],
    hidden_topics: ['notice_period'] };
  const context = vm.createContext({ document, URLSearchParams, AbortSignal,
    location: { search: '' }, setInterval() {},
    fetch: async (url, options = {}) => {
      if (options.body) preferences = JSON.parse(options.body);
      return { ok: true, json: async () => preferences };
    } });
  vm.runInContext(readFileSync(new URL('./popup.js', import.meta.url), 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  const toggle = document.querySelector('#auto-detect');
  assert.equal(toggle.checked, false);
  toggle.checked = true;
  await toggle.events.change();
  assert.equal(preferences.capture_enabled, true);
  assert.deepEqual(preferences.allowed_surfaces, ['teams_desktop']);
  assert.deepEqual(preferences.hidden_topics, ['notice_period']);
});
