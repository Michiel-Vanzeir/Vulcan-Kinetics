# whoknows

## Local popup preview

Requires Node.js 22 or newer. No package installation or environment variables are needed.

```sh
node --watch preview-server.mjs
```

Open http://127.0.0.1:4173. Stop the server with Ctrl+C. Watch mode restarts the server
when its code changes. Refresh the popup after editing HTML, CSS or client JavaScript.

The page embeds the people panel and the smaller settings popup. Open
`/people-panel.html` or `/popup.html` to test either alone.
All people and profile photographs are fictional. No real notifications are sent.

### People and chat

Search by name, role or topic, such as Sarah, bonus, notice or payroll.
The information icon switches a profile card to its evidence view; the back arrow restores
its activity statistics. **Cases handled** is a synthetic fixture count in `preview-api.mjs`.

**Ask** opens a full conversation. **Send message** stores a message on the local UI server,
and a fictional colleague replies after 1.5 seconds. You can send follow-up messages.
Opening a chat from a profile card sends a question; opening an incoming question or ping
from Account sends a reply. Each message records that intent, so earlier conversations with
the same person do not reverse who is asking for help. Demo replies and feedback follow
the intent of the individual message.
Drafts survive navigation within the page. Feedback updates the server's vouch count once
per colleague. Chat fields and messages have light blue outlines.

**Ping** creates a server-side ping. It is disabled when the recipient is unavailable or
already has an unread ping. The server also enforces these rules if the UI is bypassed.

### Account inbox and Settings

The profile icon opens **Your account**, a separate demo identity from Sarah De Vos.
The inbox starts with one incoming message and one ping. Open a message to read and reply;
use **Message** on a ping to start a conversation, or **Dismiss** to acknowledge it.
Sending a valid reply clears that person's incoming ping from the inbox automatically.
Opening the conversation without replying leaves the ping waiting.
The account icon indicates unread activity. Open chats mark incoming messages as read.

**Settings** opens a separate view containing **Allow pings**, a 50-minute **Pause pings**,
and **Detect hesitation**. Timed pauses expire automatically or can be ended early.
Cards show the same unavailable label for opt-out and pauses. Tom demonstrates opt-out;
Emma starts with a 50-minute pause. Your account's preferences never change Sarah's availability.
The compact settings popup shares the detection preference through the UI API.
Detection is a saved UI preference; this preview does not control the desktop capture agent.

### Local UI API

`preview-api.mjs` supplies `/ui-api/state` and POST endpoints for preferences, messages,
pings, read status, votes and demo incoming events. The client polls every two seconds,
so separate preview windows share the same state. Errors are visible with a retry action.
State survives page reloads but is held in memory and resets on server restart.
Drafts are browser-page state and reset on reload.

This loopback-only, single-account synthetic API is separate from the team's Flask/Neo4j
expertise backend. It has no production authentication or external messaging integration.
Recipient ids, payload lengths, preferences, ping consent and feedback are checked server-side.
Browser writes require a matching local Origin and JSON content type.

The settings popup's live backend indicator checks `http://127.0.0.1:8000/health` through
the preview server. It shows offline when that backend is not running. Its status selector
also supports explicit visual simulations.

Run the UI API and interaction checks with:

```sh
node --test preview-api.test.mjs preview-ui.test.mjs
```

The previews use local sans-serif fonts, SD Worx blue (`#006dd8`), white and neutral text.
Profile images are local assets. No code is imported or run from `previous-round/`.

## Other project components

See [the expertise backend](Neo4J-backend/README.md) and
[the capture agent](capture-agent/README.md) for their setup and run commands.
