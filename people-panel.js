/** Local demo client for the preview server's synthetic inbox and account API. */
let state = null;
let screen = 'people';
let accountReturn = 'people';
let chatReturn = 'people';
let activePersonId = null;
let listScrollTop = 0;
let searchTimer;
let refreshRunning = false;
let savingPreference = false;
const drafts = new Map();
const results = document.querySelector('.body');
const searchInput = document.querySelector('#people-search');

/** Show actionable API errors without losing the current screen or message draft. */
function showError(error) {
  const output = document.querySelector('#ui-error');
  output.hidden = !error;
  output.textContent = error ? error.message : '';
  document.querySelector('#retry').hidden = !error;
}

/** Read or mutate the loopback UI API with a bounded request timeout. */
async function request(path, body) {
  const response = await fetch(`/ui-api${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(5000),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The preview server could not complete this action.');
  return result;
}

/** Apply server-owned data without replacing the active chat composer. */
function applyState(next) {
  const changed = JSON.stringify(state) !== JSON.stringify(next);
  state = next;
  renderPreferences();
  if (changed) {
    if (screen === 'people') renderPeople();
    renderInbox();
    if (screen === 'chat') renderMessages();
  }
  const unread = state.pings.filter(ping => ping.recipientId === 'you' && !ping.read).length
    + state.messages.filter(message => message.recipientId === 'you' && !message.read).length;
  document.querySelector('#account-button').classList.toggle('has-unread', unread > 0);
  document.querySelector('#account-button').setAttribute('aria-label',
    unread ? `Account, ${unread} unread items` : 'Your account');
}

/** Synchronize the current demo state across preview windows. */
async function refresh() {
  if (refreshRunning) return;
  refreshRunning = true;
  try {
    applyState(await request('/state'));
    if (screen === 'chat' && state.messages.some(message =>
      message.senderId === activePersonId && message.recipientId === 'you' && !message.read)) {
      applyState(await request('/read', { personId: activePersonId }));
    }
    showError(null);
  } catch (error) {
    showError(new Error(`Cannot reach the UI server. ${error.message}`));
  } finally {
    refreshRunning = false;
  }
}

/** Keep errors visible and prevent duplicate submissions while an action is in progress. */
async function perform(control, action) {
  control.disabled = true;
  showError(null);
  try {
    await action();
  } catch (error) {
    showError(error);
  } finally {
    if (control.isConnected) control.disabled = false;
  }
}

/** Save a mutation and use the server response as the source of truth. */
async function mutate(path, body) {
  const next = await request(path, body);
  applyState(next);
}

/** Keep controls synchronized with the server, including expired timed pauses. */
function renderPreferences() {
  if (!state || savingPreference) return;
  document.querySelector('#allow-pings').checked = state.account.allowPings;
  document.querySelector('#account-auto-detect').checked = state.account.autoDetect;
  const paused = state.account.dndUntil > Date.now();
  const pause = document.querySelector('#dnd-button');
  pause.textContent = paused ? 'Resume pings' : 'Pause pings';
  pause.setAttribute('aria-pressed', String(paused));
  pause.disabled = !state.account.allowPings && !paused;
  document.querySelector('#account-status').textContent = state.account.pingable
    ? 'Available for pings' : 'Unavailable for pings';
}

/** Update settings on the server and restore the controls after any failed save. */
async function savePreference(control, changes) {
  savingPreference = true;
  await perform(control, async () => mutate('/preferences', changes));
  savingPreference = false;
  renderPreferences();
}

/** Navigate separate list, inbox, settings and chat views without discarding drafts. */
function navigate(next) {
  screen = next;
  document.querySelector('.list-view').hidden = next !== 'people';
  document.querySelector('.chat-view').hidden = next !== 'chat';
  document.querySelector('#account-view').hidden = next !== 'account';
  document.querySelector('#settings-view').hidden = next !== 'settings';
  document.querySelector('#account-button').setAttribute('aria-expanded', String(next === 'account'));
  if (next === 'people') { renderPeople(); results.scrollTop = listScrollTop; }
  if (next === 'account') renderInbox();
  if (next === 'chat') renderMessages();
}

/** Match every search term against the synthetic directory supplied by the server. */
function searchPeople(query) {
  const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  return state.people.filter(person => terms.every(term =>
    [person.name, person.role, person.country, person.topic, person.keywords, person.evidence]
      .join(' ').toLowerCase().includes(term)));
}

/** Use server-calculated availability so client controls cannot bypass recipient consent. */
function getPingAvailability(person) {
  return { allowed: person.pingable,
    label: person.pingable ? 'Available for pings' : 'Unavailable for pings' };
}

/** Build dynamic content as text so search and message text cannot inject markup. */
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

/** Create a keyboard-accessible action with a local callback. */
function button(label, className, action) {
  const node = element('button', className, label);
  node.type = 'button';
  node.addEventListener('click', action);
  return node;
}

/** Display searchable profile cards grouped by expertise topic. */
function renderPeople() {
  if (!state) return;
  const scrollTop = results.scrollTop;
  results.replaceChildren();
  const matches = searchPeople(searchInput.value);
  if (!matches.length) {
    results.append(element('div', 'gap', 'No matching colleagues. Try a name or topic.'));
  }
  for (const topic of new Set(matches.map(person => person.topic))) {
    results.append(element('div', 'topic', topic));
    const people = matches.filter(person => person.topic === topic);
    const best = people.find(person => !person.stale);
    for (const person of people) results.append(createCard(person, person === best));
  }
  results.scrollTop = scrollTop;
}

/** Recreate the reference expert card, evidence and trust signal layout. */
function createCard(person, best) {
  const card = element('article', `card${best ? ' top' : ''}${person.stale ? ' stale' : ''}`);
  const who = element('div', 'who');
  const identity = element('div');
  const nameRow = element('div', 'name-row');
  const information = element('div', 'profile-information');
  const details = element('div', 'card-information');
  details.id = `information-${person.id}`;
  details.hidden = true;
  const heading = element('div', 'information-heading',
    person.stale ? 'Authored work' : 'Recent work');
  const returnButton = button('', 'information-back', () => setInformation(false));
  returnButton.setAttribute('aria-label', 'Back to profile');
  returnButton.setAttribute('title', 'Back to profile');
  details.append(heading, element('p', 'information-description', person.evidence),
    element('div', 'information-context', person.topic), returnButton);
  const informationToggle = button('i', 'information-toggle', () => setInformation(true));
  informationToggle.setAttribute('aria-label', `More information about ${person.name}`);
  informationToggle.setAttribute('title', `More information about ${person.name}`);
  informationToggle.setAttribute('aria-controls', details.id);
  informationToggle.setAttribute('aria-expanded', 'false');
  information.append(informationToggle);

  /** Swap the card content while keeping its identity and chat action available. */
  function setInformation(open) {
    signals.hidden = open;
    details.hidden = !open;
    informationToggle.hidden = open;
    informationToggle.setAttribute('aria-expanded', String(open));
    if (open) returnButton.focus();
    else informationToggle.focus();
  }

  nameRow.append(element('div', 'name', person.name), information);
  identity.append(nameRow,
    element('div', 'role', `${person.role} · ${person.country}`));
  who.append(createPortrait(person), identity);
  if (best) card.append(element('div', 'badge', 'Best match'));
  const signals = element('dl', 'signals');
  signals.append(createStatistic('Last active', person.recent, person.stale ? 'old' : ''),
    createStatistic('Cases handled', String(person.count)),
    createStatistic('Vouches', String(person.vouches)));
  card.append(who, signals, details);
  const firstName = person.name.split(' ')[0];
  const availability = getPingAvailability(person);
  const availabilityStatus = element('div',
    `ping-availability${availability.allowed ? '' : ' unavailable'}`, availability.label);
  availabilityStatus.dataset.personId = person.id;
  card.append(availabilityStatus);
  const actions = element('div', 'card-actions');
  const pingStatus = element('div', 'ping-status');
  pingStatus.setAttribute('role', 'status');
  const pinged = state.pings.some(ping => ping.recipientId === person.id && !ping.read);
  const ping = button(pinged ? 'Pinged' : 'Ping', 'btn ghost', async () => {
    await perform(ping, async () => {
      await mutate('/pings', { personId: person.id });
      pingStatus.textContent = `Ping sent to ${firstName} in this demo.`;
      ping.textContent = 'Pinged';
      ping.disabled = true;
    });
  });
  ping.setAttribute('aria-label', `Ping ${person.name}`);
  ping.disabled = !availability.allowed || pinged;
  if (!availability.allowed) ping.setAttribute('title', availability.label);
  if (pinged) pingStatus.textContent = `Demo ping sent to ${firstName}.`;
  actions.append(button(state.messages.some(message => message.senderId === person.id || message.recipientId === person.id) ? `Open chat with ${firstName}` : `Ask ${firstName}`,
    `btn${person.stale ? ' ghost' : ''}`, () => openChat(person.id, 'people')), ping);
  card.append(actions, pingStatus);
  return card;
}

/** Pair trust values with consistent labels for quick comparison between profiles. */
function createStatistic(label, value, className = '') {
  const statistic = element('div', `statistic ${className}`);
  statistic.append(element('dt', 'statistic-label', label),
    element('dd', 'statistic-value', value));
  return statistic;
}

/** Reuse locally generated synthetic headshots in profile cards and chat headers. */
function createPortrait(person) {
  const portrait = element('div', `avatar avatar-${person.id}`);
  portrait.setAttribute('role', 'img');
  portrait.setAttribute('aria-label', `${person.name}, synthetic profile picture`);
  return portrait;
}

/** Render incoming pings and message previews with read and reply actions. */
function renderInbox() {
  if (!state) return;
  const inbox = document.querySelector('#inbox-items');
  inbox.replaceChildren();
  const incomingPings = state.pings.filter(ping => ping.recipientId === 'you' && !ping.read);
  const contacts = state.people.filter(person => state.messages.some(message =>
    message.senderId === person.id || message.recipientId === person.id));
  const unreadMessages = state.messages.filter(message => message.recipientId === 'you' && !message.read);
  document.querySelector('#inbox-count').textContent =
    `${incomingPings.length + unreadMessages.length} unread`;
  for (const ping of incomingPings) {
    const person = state.people.find(candidate => candidate.id === ping.senderId);
    const item = element('article', 'inbox-item unread');
    item.append(element('div', 'inbox-kind', 'Ping'), element('div', 'name', person.name),
      element('p', 'account-description', 'Would like your attention.'));
    const actions = element('div', 'row');
    actions.append(button('Message', 'vote vote-primary', async () => {
      await openChat(person.id, 'account');
    }));
    const dismiss = button('Dismiss', 'vote', () => perform(dismiss,
      async () => mutate('/read', { pingId: ping.id })));
    actions.append(dismiss);
    item.append(actions);
    inbox.append(item);
  }
  for (const person of contacts) {
    const messages = messagesFor(person.id);
    const latest = messages.at(-1);
    const unread = messages.some(message => message.recipientId === 'you' && !message.read);
    const item = button('', `inbox-item inbox-thread${unread ? ' unread' : ''}`,
      () => openChat(person.id, 'account'));
    const identity = element('div', 'inbox-person');
    identity.append(createPortrait(person), element('div', 'name', person.name));
    item.append(identity, element('p', 'inbox-preview',
      `${latest.senderId === 'you' ? 'You: ' : ''}${latest.text}`),
      element('span', 'inbox-kind', unread ? 'New message ? Open to reply' : 'Open conversation'));
    inbox.append(item);
  }
  if (!inbox.children.length) inbox.append(element('p', 'muted', 'You are all caught up.'));
}

/** Filter a thread to the fixed local account and its selected colleague. */
function messagesFor(personId) {
  return state.messages.filter(message =>
    (message.senderId === 'you' && message.recipientId === personId)
    || (message.senderId === personId && message.recipientId === 'you'));
}

/** Open a full conversation with a persistent composer for repeated replies. */
async function openChat(personId, from = chatReturn) {
  if (!state) return;
  const person = state.people.find(candidate => candidate.id === personId);
  if (!person) return;
  const history = messagesFor(personId);
  const latest = history.at(-1);
  const intent = from === 'people' ? 'ask'
    : latest?.senderId === 'you' ? latest.intent
      : latest?.replyToIntent === 'ask' ? 'ask' : 'reply';
  if (screen === 'people') listScrollTop = results.scrollTop;
  activePersonId = personId;
  chatReturn = from;
  const chat = document.querySelector('.chat-view');
  const header = element('div', 'chat-contact-header');
  const back = button('', 'back', () => navigate(chatReturn));
  back.setAttribute('aria-label', from === 'account' ? 'Back to inbox' : 'Back to people');
  const contact = element('div', 'chat-contact');
  const identity = element('div');
  identity.append(element('h1', 'chat-heading', person.name),
    element('p', 'chat-subtitle', `${person.role} ? ${person.country}`),
    element('p', 'chat-topic', person.topic));
  contact.append(createPortrait(person), identity);
  header.append(back, contact);
  const content = element('div', 'chat-content');
  const messages = element('div', 'thread');
  messages.id = 'chat-messages';
  messages.setAttribute('role', 'log');
  messages.setAttribute('aria-live', 'polite');
  content.append(messages);
  const compose = element('form', 'chat-composer');
  compose.append(element('p', 'composer-context', intent === 'ask'
    ? 'You are asking for help.' : 'You are replying to a colleague.'));
  const message = element('textarea');
  message.maxLength = 1000;
  message.required = true;
  message.setAttribute('aria-label', `Message to ${person.name}`);
  message.placeholder = 'Write a message...';
  message.value = drafts.get(personId) ?? (from === 'account' || messagesFor(personId).length ? ''
    : `Hi ${person.name.split(' ')[0]}, quick question about ${person.topic}: ${searchInput.value}`);
  message.addEventListener('input', () => drafts.set(personId, message.value));
  const send = element('button', 'btn', 'Send message');
  send.type = 'submit';
  const cancel = button('Back', 'btn ghost', () => navigate(chatReturn));
  const row = element('div', 'row');
  row.append(cancel, send);
  compose.append(message, row);
  compose.addEventListener('submit', event => {
    event.preventDefault();
    if (!message.value.trim()) { message.focus(); return; }
    const text = message.value;
    message.disabled = true;
    perform(send, async () => {
      await mutate('/messages', { personId, text, intent });
      if (message.value === text) { message.value = ''; drafts.set(personId, ''); }
    }).finally(() => { message.disabled = false; message.focus(); });
  });
  chat.replaceChildren(header, content, compose);
  navigate('chat');
  renderMessages();
  message.focus();
  try { await mutate('/read', { personId }); } catch (error) { showError(error); }
}

/** Update only message history and feedback, leaving the draft and focus intact. */
function renderMessages() {
  if (!activePersonId || screen !== 'chat') return;
  const container = document.querySelector('#chat-messages');
  if (!container) return;
  const messages = messagesFor(activePersonId);
  container.replaceChildren();
  for (const message of messages) {
    container.append(element('div', `bubble ${message.senderId === 'you' ? 'me' : 'them'}`, message.text));
  }
  if (!messages.length) container.append(element('p', 'muted', 'Start the conversation below.'));
  if (messages.at(-1)?.senderId === 'you') {
    container.append(element('p', 'status', 'Sent. Waiting for a demo reply...'));
  }
  const latestReply = messages.findLast(message => message.senderId === activePersonId);
  if (latestReply?.replyToIntent === 'ask') {
    const feedback = element('div', 'votebox');
    if (state.votes[activePersonId]) {
      feedback.append(element('div', 'feedback-title', 'Thanks for your feedback'));
    } else {
      feedback.append(element('div', 'feedback-title', 'Did this answer help?'));
      const row = element('div', 'feedback-actions');
      for (const helpful of [true, false]) {
        const vote = button(helpful ? 'Yes, vouch' : 'Not really',
          helpful ? 'vote vote-primary' : 'vote', () => perform(vote,
            async () => mutate('/votes', { personId: activePersonId, helpful })));
        row.append(vote);
      }
      feedback.append(row);
    }
    container.append(feedback);
  }
  const scrolling = document.querySelector('.chat-content');
  scrolling.scrollTop = scrolling.scrollHeight;
}

/** Close and reopen the panel without discarding server state or local drafts. */
function setPanelOpen(open) {
  document.querySelector('.panel').hidden = !open;
  document.querySelector('#reopen').hidden = open;
  if (open) document.querySelector('#account-button').focus();
  else document.querySelector('#reopen').focus();
}

document.querySelector('form.ask-box').addEventListener('submit', event => {
  event.preventDefault();
  if (state) renderPeople(); else refresh();
});
searchInput.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(renderPeople, 120);
});
document.querySelector('#account-button').addEventListener('click', () => {
  if (screen !== 'account' && screen !== 'settings') accountReturn = screen;
  navigate('account');
});
document.querySelector('#account-back').addEventListener('click', () => navigate(accountReturn));
document.querySelector('#settings-button').addEventListener('click', () => navigate('settings'));
document.querySelector('#settings-back').addEventListener('click', () => navigate('account'));
document.querySelector('#allow-pings').addEventListener('change', event =>
  savePreference(event.target, { allowPings: event.target.checked }));
document.querySelector('#account-auto-detect').addEventListener('change', event =>
  savePreference(event.target, { autoDetect: event.target.checked }));
document.querySelector('#dnd-button').addEventListener('click', event => {
  if (state) savePreference(event.target, { pause: !(state.account.dndUntil > Date.now()) });
});
document.querySelector('.close').addEventListener('click', () => setPanelOpen(false));
document.querySelector('#reopen').addEventListener('click', () => setPanelOpen(true));
document.querySelector('#retry').addEventListener('click', refresh);
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  if (screen === 'settings') navigate('account');
  else if (screen === 'account') navigate(accountReturn);
  else if (screen === 'chat') navigate(chatReturn);
  else setPanelOpen(false);
});
results.append(element('p', 'muted', 'Loading colleagues...'));
refresh();
setInterval(refresh, 2000);
