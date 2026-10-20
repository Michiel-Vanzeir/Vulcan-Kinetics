/** Synthetic fixtures for testing the reference people panel without extension APIs. */
// HACK: Search, replies and vouches are browser-local demos, not backend operations.
const PEOPLE = [
  { id: 'sarah', name: 'Sarah De Vos', role: 'Payroll consultant', country: 'BE',
    topic: 'Year-end bonus PC 200', keywords: 'payroll bonus part-time pc 200',
    evidence: 'Calculated year-end bonus for part-time employee',
    recent: '2 weeks ago', count: 12, vouches: 8 },
  { id: 'tom', name: 'Tom Janssens', role: 'Senior payroll advisor', country: 'BE',
    topic: 'Year-end bonus PC 200', keywords: 'payroll bonus procedure pc 200',
    evidence: 'Wrote the original year-end bonus procedure',
    recent: '2024', count: 24, vouches: 5, stale: true, allowPings: false },
  { id: 'emma', name: 'Emma Peeters', role: 'HR legal consultant', country: 'BE',
    topic: 'Notice periods', keywords: 'notice termination employment belgium',
    evidence: 'Reviewed notice periods for Belgian employment contracts',
    recent: '3 days ago', count: 18, vouches: 9, dndUntil: Date.now() + 50 * 60_000 },
  { id: 'lucas', name: 'Lucas Martin', role: 'Payroll specialist', country: 'FR',
    topic: 'French payroll', keywords: 'france french payroll salary',
    evidence: 'Resolved a payroll calculation question for a French client',
    recent: '1 week ago', count: 16, vouches: 6 },
];
const conversations = new Map();
const drafts = new Map();
const pingedPeople = new Set();
const DND_DURATION_MS = 50 * 60_000;
const ACCOUNT_STORAGE_KEY = 'whoknows-preview-account';
let accountPreferences = { allowPings: true, dndUntil: 0 };
let activePerson = null;
let accountOpen = false;
let listScrollTop = 0;
const results = document.querySelector('.body');
const searchInput = document.querySelector('#people-search');

/** Load only valid local demo preferences, keeping storage failures visible. */
function loadAccountPreferences() {
  try {
    const saved = JSON.parse(localStorage.getItem(ACCOUNT_STORAGE_KEY) || 'null');
    if (saved && typeof saved.allowPings === 'boolean' && Number.isFinite(saved.dndUntil)) {
      accountPreferences = { allowPings: saved.allowPings, dndUntil: saved.dndUntil };
    }
  } catch {
    showAccountStorageError();
  }
}

/** Explain when browser storage prevents account preferences from persisting. */
function showAccountStorageError() {
  const error = document.querySelector('#account-error');
  error.hidden = false;
  error.textContent = 'Account settings could not be saved or loaded in this browser.';
}

/** Persist account choices and immediately refresh the availability shown on cards. */
function saveAccountPreferences() {
  try {
    localStorage.setItem(ACCOUNT_STORAGE_KEY, JSON.stringify(accountPreferences));
  } catch {
    showAccountStorageError();
  }
  renderAccount();
  renderPeople();
}

/** Compute availability from recipient consent and an absolute DND expiry time. */
function getPingAvailability(person) {
  const preferences = person.id === 'sarah' ? accountPreferences : person;
  if (preferences.allowPings === false || preferences.dndUntil > Date.now()) {
    return { allowed: false, label: 'Unavailable for pings' };
  }
  return { allowed: true, label: 'Available for pings' };
}

/** Keep account controls and the DND countdown in sync with the current time. */
function renderAccount() {
  const dndActive = accountPreferences.dndUntil > Date.now();
  document.querySelector('#allow-pings').checked = accountPreferences.allowPings;
  const dndButton = document.querySelector('#dnd-button');
  dndButton.textContent = dndActive ? 'Resume pings' : 'Pause pings';
  dndButton.setAttribute('aria-pressed', String(dndActive));
  dndButton.disabled = !accountPreferences.allowPings && !dndActive;
  document.querySelector('#account-status').textContent = getPingAvailability(PEOPLE[0]).label;
}

/** Switch to account settings and restore the previous list or chat on return. */
function setAccountOpen(open) {
  accountOpen = open;
  document.querySelector('#account-settings').hidden = !open;
  document.querySelector('#account-button').setAttribute('aria-expanded', String(open));
  document.querySelector('.list-view').hidden = open || Boolean(activePerson);
  document.querySelector('.chat-view').hidden = open || !activePerson;
  if (open) {
    document.querySelector('#account-back').focus();
  } else {
    if (activePerson) openChat(activePerson, false);
    document.querySelector('#account-button').focus();
  }
}

/** Match every search term against synthetic names, roles and topic evidence. */
function searchPeople(query) {
  const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  return PEOPLE.filter(person => {
    const searchable = [person.name, person.role, person.country, person.topic,
      person.keywords, person.evidence].join(' ').toLowerCase();
    return terms.every(term => searchable.includes(term));
  });
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

/** Display cards grouped by topic with the first current expert highlighted. */
function renderPeople() {
  const matches = searchPeople(searchInput.value);
  results.replaceChildren();
  if (!matches.length) {
    const gap = element('div', 'gap');
    gap.append(element('b', '', 'Knowledge gap'), element('p', '',
      'Nobody in this demo has recent expertise on this topic. Try “bonus”, “notice” or a name.'));
    results.append(gap);
    return;
  }
  const topics = [...new Set(matches.map(person => person.topic))];
  for (const topic of topics) {
    results.append(element('div', 'topic', topic));
    const experts = matches.filter(person => person.topic === topic);
    const best = experts.find(person => !person.stale);
    for (const person of experts) results.append(createCard(person, person === best));
  }
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
  const ping = button(pingedPeople.has(person.id) ? 'Pinged' : 'Ping', 'btn ghost', () => {
    if (!getPingAvailability(person).allowed || pingedPeople.has(person.id)) return;
    pingedPeople.add(person.id);
    ping.textContent = 'Pinged';
    ping.disabled = true;
    pingStatus.textContent = `Demo ping sent to ${firstName}.`;
  });
  ping.setAttribute('aria-label', `Ping ${person.name}`);
  ping.disabled = !availability.allowed || pingedPeople.has(person.id);
  if (!availability.allowed) ping.setAttribute('title', availability.label);
  if (pingedPeople.has(person.id)) pingStatus.textContent = `Demo ping sent to ${firstName}.`;
  actions.append(button(conversations.has(person.id) ? `Open chat with ${firstName}` : `Ask ${firstName}`,
    `btn${person.stale ? ' ghost' : ''}`, () => openChat(person)), ping);
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

/** Open a dedicated conversation while keeping the list query and scroll position. */
function openChat(person, focus = true) {
  if (!activePerson) listScrollTop = results.scrollTop;
  activePerson = person;
  document.querySelector('.list-view').hidden = true;
  const chat = document.querySelector('.chat-view');
  chat.hidden = false;
  const back = button('', 'back', returnToPeople);
  back.setAttribute('aria-label', 'Back to people');
  back.setAttribute('title', 'Back to people');
  const contactHeader = element('div', 'chat-contact-header');
  const contact = element('div', 'chat-contact');
  const identity = element('div');
  identity.append(element('h1', 'chat-heading', person.name),
    element('p', 'chat-subtitle', `${person.role} · ${person.country}`),
    element('p', 'chat-topic', person.topic));
  contact.append(createPortrait(person), identity);
  contactHeader.append(back, contact);
  const content = element('div', 'chat-content');
  content.setAttribute('aria-live', 'polite');
  chat.replaceChildren(contactHeader, content);
  if (conversations.has(person.id)) renderAction(content, person);
  else showComposer(content, person);
  if (focus && conversations.has(person.id)) back.focus();
}

/** Restore the people list without discarding drafts, messages or feedback. */
function returnToPeople() {
  activePerson = null;
  document.querySelector('.chat-view').hidden = true;
  document.querySelector('.list-view').hidden = false;
  renderPeople();
  results.scrollTop = listScrollTop;
  searchInput.focus();
}

/** Restore the ask action or a simulated conversation when search results change. */
function renderAction(slot, person) {
  const firstName = person.name.split(' ')[0];
  const conversation = conversations.get(person.id);
  if (!conversation) {
    slot.replaceChildren(button(`Ask ${firstName}`, `btn${person.stale ? ' ghost' : ''}`,
      () => showComposer(slot, person)));
    return;
  }
  const thread = element('div', 'thread');
  thread.append(element('div', 'bubble me', conversation.message));
  if (!conversation.replied) {
    thread.append(element('div', 'status', `Demo sent · waiting for ${firstName}…`));
  } else {
    thread.append(element('div', 'bubble them', person.stale
      ? 'I have not worked on this since 2024. Please double-check with a current expert.'
      : 'Hi! I have handled this recently. Happy to walk you through it. (Simulated reply)'));
    if (conversation.vote) {
      const confirmation = element('div', 'votebox feedback-recorded');
      confirmation.append(element('div', 'feedback-title', 'Thanks for your feedback'),
        element('p', 'feedback-description', 'Recorded for this demo session.'));
      thread.append(confirmation);
    } else {
      const votes = element('div', 'votebox');
      votes.append(element('div', 'feedback-title', `Did ${firstName} know their stuff?`),
        element('p', 'feedback-description', 'Help colleagues find the right person next time.'));
      const row = element('div', 'feedback-actions');
      for (const helpful of [true, false]) {
        row.append(button(helpful ? 'Yes, vouch' : 'Not really',
          helpful ? 'vote vote-primary' : 'vote', () => {
          conversation.vote = helpful ? 'up' : 'down';
          if (helpful) person.vouches += 1;
          renderAction(slot, person);
        }));
      }
      votes.append(row);
      thread.append(votes);
    }
  }
  slot.replaceChildren(thread);
}

/** Let the user edit and send a local demo message without contacting anyone. */
function showComposer(slot, person) {
  const firstName = person.name.split(' ')[0];
  const compose = element('div', 'compose');
  const message = element('textarea');
  message.maxLength = 1000;
  message.setAttribute('aria-label', `Message to ${firstName}`);
  message.value = drafts.get(person.id)
    ?? `Hi ${firstName}, quick question about ${person.topic}: ${searchInput.value}`;
  message.addEventListener('input', () => drafts.set(person.id, message.value));
  const row = element('div', 'row');
  row.append(button('Cancel', 'btn ghost', returnToPeople),
    button(`Send to ${firstName}`, 'btn', () => {
      if (!message.value.trim()) { message.focus(); return; }
      const conversation = { message: message.value.trim(), replied: false };
      conversations.set(person.id, conversation);
      renderAction(slot, person);
      setTimeout(() => {
        conversation.replied = true;
        if (!accountOpen && activePerson?.id === person.id) openChat(person, false);
      }, 1500);
    }));
  compose.append(message, row);
  slot.replaceChildren(compose);
  message.focus();
}

/** Close or reopen the preview while preserving search and conversation state. */
function setPanelOpen(open) {
  document.querySelector('.panel').hidden = !open;
  document.querySelector('#reopen').hidden = open;
  if (open && accountOpen) document.querySelector('#account-back').focus();
  else if (open && activePerson) document.querySelector('.chat-view .back').focus();
  else if (open) searchInput.focus();
  else document.querySelector('#reopen').focus();
}

document.querySelector('form').addEventListener('submit', event => {
  event.preventDefault();
  renderPeople();
});
searchInput.addEventListener('input', renderPeople);
document.querySelector('.close').addEventListener('click', () => setPanelOpen(false));
document.querySelector('#reopen').addEventListener('click', () => setPanelOpen(true));
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && accountOpen) {
    setAccountOpen(false);
    return;
  }
  if (event.key === 'Escape') setPanelOpen(false);
});
document.querySelector('#account-button').addEventListener('click', () => {
  setAccountOpen(!accountOpen);
});
document.querySelector('#account-back').addEventListener('click', () => setAccountOpen(false));

/** Share the hesitation preference with the standalone settings popup. */
function loadHesitationPreference() {
  try {
    document.querySelector('#account-auto-detect').checked =
      localStorage.getItem('autoDetect') !== 'false';
  } catch {
    showAccountStorageError();
  }
}

document.querySelector('#account-auto-detect').addEventListener('change', event => {
  try {
    localStorage.setItem('autoDetect', String(event.target.checked));
  } catch {
    showAccountStorageError();
  }
});
window.addEventListener('storage', event => {
  if (event.key === 'autoDetect' || event.key === null) loadHesitationPreference();
});
loadHesitationPreference();
document.querySelector('#allow-pings').addEventListener('change', event => {
  accountPreferences.allowPings = event.target.checked;
  saveAccountPreferences();
});
document.querySelector('#dnd-button').addEventListener('click', () => {
  accountPreferences.dndUntil = accountPreferences.dndUntil > Date.now()
    ? 0 : Date.now() + DND_DURATION_MS;
  saveAccountPreferences();
});
loadAccountPreferences();
renderAccount();
// Absolute timestamps restore availability correctly after reloads or suspended tabs.
setInterval(() => {
  renderAccount();
  for (const status of document.querySelectorAll('.ping-availability')) {
    const person = PEOPLE.find(candidate => candidate.id === status.dataset.personId);
    if (!person) continue;
    const availability = getPingAvailability(person);
    status.textContent = availability.label;
    status.className = `ping-availability${availability.allowed ? '' : ' unavailable'}`;
    const ping = status.parentElement.querySelector('.card-actions button:last-child');
    ping.disabled = !availability.allowed || pingedPeople.has(person.id);
    ping.title = availability.allowed ? '' : availability.label;
  }
}, 1000);
renderPeople();
