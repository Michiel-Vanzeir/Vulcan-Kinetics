import { randomUUID } from 'node:crypto';

const DND_DURATION_MS = 50 * 60_000;
const PEOPLE = [
  { id: 'sarah', name: 'Sarah De Vos', role: 'Payroll consultant', country: 'BE',
    topic: 'Year-end bonus PC 200', keywords: 'payroll bonus part-time pc 200',
    evidence: 'Calculated year-end bonus for part-time employee',
    recent: '2 weeks ago', count: 12, vouches: 8,
    // Keep the demo explanation aligned with https://www.sfonds200.be/nl/sectorinformatie/verloning/.
    demoAnswer: "Happy to help. For PC 200, the year-end bonus generally equals one month's "
      + 'gross salary, provided the eligibility conditions are met. If someone joined during '
      + 'the year, it can be prorated for the eligible months worked. I would check their '
      + 'start date and relevant absences before calculating the final amount. (Demo reply)' },
  { id: 'tom', name: 'Tom Janssens', role: 'Senior payroll advisor', country: 'BE',
    topic: 'Year-end bonus PC 200', keywords: 'payroll bonus procedure pc 200',
    evidence: 'Wrote the original year-end bonus procedure',
    recent: '2024', count: 24, vouches: 5, stale: true, allowPings: false },
  { id: 'emma', name: 'Emma Peeters', role: 'HR legal consultant', country: 'BE',
    topic: 'Notice periods', keywords: 'notice termination employment belgium',
    evidence: 'Reviewed notice periods for Belgian employment contracts',
    recent: '3 days ago', count: 18, vouches: 9, dndUntil: Date.now() + DND_DURATION_MS },
  { id: 'lucas', name: 'Lucas Martin', role: 'Payroll specialist', country: 'FR',
    topic: 'French payroll', keywords: 'france french payroll salary',
    evidence: 'Resolved a payroll calculation question for a French client',
    recent: '1 week ago', count: 16, vouches: 6 },
];

/** Keep synthetic UI interactions on this local server, separate from the expertise backend. */
export function createPreviewStore({ now = Date.now, schedule = setTimeout } = {}) {
  const people = structuredClone(PEOPLE);
  const preferences = { allowPings: true, autoDetect: true, dndUntil: 0 };
  const messages = [];
  const pings = [];
  const votes = {};

  /** Validate every recipient against the synthetic directory on the server. */
  function personById(id) {
    const person = people.find(candidate => candidate.id === id);
    if (!person) throw new ApiError(404, 'Person not found.');
    return person;
  }

  /** Store an explicit chat message with a server-generated identity and timestamp. */
  function addMessage(senderId, recipientId, text, context = {}) {
    const message = { id: randomUUID(), senderId, recipientId, text,
      createdAt: now(), read: senderId === 'you', ...context };
    messages.push(message);
    return message;
  }

  /** Evaluate current consent and timed pauses for the recipient of a ping. */
  function canPing(recipient) {
    return recipient.allowPings !== false && !(recipient.dndUntil > now());
  }

  /** Permit feedback only for a colleague's response to an explicit question from this account. */
  function hasHelpfulReply(personId) {
    const latestReply = messages.findLast(message => message.senderId === personId);
    return latestReply?.replyToIntent === 'ask';
  }

  /** Return only conversations belonging to the fixed local demo account. */
  function snapshot() {
    return {
      people: people.map(person => ({ ...person, pingable: canPing(person) })),
      account: { id: 'you', name: 'Your account', ...preferences, pingable: canPing(preferences) },
      messages: structuredClone(messages), pings: structuredClone(pings), votes: { ...votes },
    };
  }

  /** Dispatch validated mutations; this is a single-account, loopback-only demo API. */
  function mutate(path, body) {
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      throw new ApiError(400, 'A JSON object is required.');
    }
    if (messages.length + pings.length > 2000) {
      throw new ApiError(409, 'Demo session is full. Restart the preview server to reset it.');
    }
    if (path === '/ui-api/preferences') {
      for (const key of Object.keys(body)) {
        if (!['allowPings', 'autoDetect', 'pause'].includes(key)) {
          throw new ApiError(400, 'Unknown account preference.');
        }
        if (typeof body[key] !== 'boolean') throw new ApiError(400, 'Settings must be boolean.');
      }
      if ('allowPings' in body) preferences.allowPings = body.allowPings;
      if ('autoDetect' in body) preferences.autoDetect = body.autoDetect;
      if ('pause' in body) preferences.dndUntil = body.pause ? now() + DND_DURATION_MS : 0;
    } else if (path === '/ui-api/pings' || path === '/ui-api/demo-incoming') {
      const person = personById(body.personId);
      const incoming = path === '/ui-api/demo-incoming';
      if (incoming && !['ping', 'message'].includes(body.kind)) {
        throw new ApiError(400, 'Choose an incoming ping or message.');
      }
      if (incoming && body.kind === 'message') {
        addMessage(person.id, 'you', `Hi! Could you help me with ${person.topic.toLowerCase()}?`,
          { intent: 'ask' });
      } else {
        const recipientId = incoming ? 'you' : person.id;
        if (!canPing(incoming ? preferences : person)) {
          throw new ApiError(409, 'Recipient is unavailable for pings.');
        }
        if (pings.some(ping => ping.recipientId === recipientId && !ping.read)) {
          throw new ApiError(409, 'A ping is already waiting for this person.');
        }
        pings.push({ id: randomUUID(), senderId: incoming ? person.id : 'you',
          recipientId, createdAt: now(), read: false });
      }
    } else if (path === '/ui-api/messages') {
      const person = personById(body.personId);
      if (typeof body.text !== 'string' || !body.text.trim() || body.text.length > 1000) {
        throw new ApiError(400, 'Enter a message between 1 and 1000 characters.');
      }
      if (!['ask', 'reply'].includes(body.intent)) {
        throw new ApiError(400, 'Specify whether this message is a question or a reply.');
      }
      const answeringPing = body.intent === 'reply' && pings.some(ping =>
        ping.senderId === person.id && ping.recipientId === 'you' && !ping.read);
      const sent = addMessage('you', person.id, body.text.trim(), { intent: body.intent });
      for (const ping of pings) {
        if (ping.senderId === person.id && ping.recipientId === 'you') ping.read = true;
      }
      // HACK: Fictional colleagues reply automatically so the complete chat can be tested locally.
      const timer = schedule(() => {
        const text = answeringPing
          ? `I've a question regarding ${person.topic.toLowerCase()}. Could you help me? (Demo reply)`
          : sent.intent === 'reply'
          ? 'Thanks for your help. That makes things clearer. (Demo reply)'
          : person.stale
            ? 'My experience on this is from 2024. Please check with a current expert.'
            : person.demoAnswer || 'Happy to help. Let us walk through this together. (Demo reply)';
        addMessage(person.id, 'you', text,
          { intent: answeringPing ? 'ask' : 'reply', inReplyTo: sent.id, replyToIntent: sent.intent });
      }, 1500);
      timer?.unref?.();
    } else if (path === '/ui-api/read') {
      if (body.personId) {
        personById(body.personId);
        for (const message of messages) {
          if (message.senderId === body.personId && message.recipientId === 'you') message.read = true;
        }
      } else {
        const ping = pings.find(item => item.id === body.pingId && item.recipientId === 'you');
        if (!ping) throw new ApiError(404, 'Incoming ping not found.');
        ping.read = true;
      }
    } else if (path === '/ui-api/votes') {
      const person = personById(body.personId);
      if (typeof body.helpful !== 'boolean') throw new ApiError(400, 'Choose a feedback option.');
      if (votes[person.id]) throw new ApiError(409, 'Feedback was already recorded.');
      if (!hasHelpfulReply(person.id)) {
        throw new ApiError(409, 'Feedback is only available after a reply to a question you asked.');
      }
      votes[person.id] = body.helpful ? 'up' : 'down';
      if (body.helpful) person.vouches += 1;
    } else {
      throw new ApiError(404, 'UI endpoint not found.');
    }
    return snapshot();
  }

  // HACK: Seeded incoming examples demonstrate what the recipient sees on first launch.
  addMessage('tom', 'you', 'Could you check a part-time year-end bonus calculation with me?',
    { intent: 'ask' });
  pings.push({ id: randomUUID(), senderId: 'lucas', recipientId: 'you', createdAt: now(), read: false });
  return { snapshot, mutate };
}

/** Return a useful status and message for a rejected UI action. */
export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/** Bound request bodies before parsing JSON so demo endpoints cannot consume arbitrary memory. */
async function readJson(request) {
  if (!request.headers['content-type']?.startsWith('application/json')) {
    throw new ApiError(415, 'Use application/json.');
  }
  let length = 0;
  const chunks = [];
  for await (const chunk of request) {
    length += chunk.length;
    if (length > 8192) throw new ApiError(413, 'Request is too large.');
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch {
    throw new ApiError(400, 'Invalid JSON.');
  }
}

/** Protect browser mutations against cross-origin requests to the local demo account. */
export async function servePreviewApi(request, response, path, store) {
  try {
    const host = request.headers.host;
    const port = request.socket.localPort;
    if (![`127.0.0.1:${port}`, `localhost:${port}`].includes(host)) {
      throw new ApiError(403, 'Invalid preview host.');
    }
    let snapshot;
    if (request.method === 'GET' && path === '/ui-api/state') {
      snapshot = store.snapshot();
    } else if (request.method === 'POST') {
      if (request.headers.origin !== `http://${host}`) {
        throw new ApiError(403, 'Open the UI on the same local preview address.');
      }
      snapshot = store.mutate(path, await readJson(request));
    } else {
      throw new ApiError(405, 'Unsupported UI request.');
    }
    response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    response.end(JSON.stringify(snapshot));
  } catch (error) {
    if (!(error instanceof ApiError)) console.error(`UI API failed: ${error.message}`);
    response.writeHead(error instanceof ApiError ? error.status : 500,
      { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    response.end(JSON.stringify({ error: error instanceof ApiError ? error.message : 'UI API failed.' }));
  }
}
