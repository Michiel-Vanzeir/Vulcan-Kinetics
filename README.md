# whoknows

Expertise finds you, not the other way around. A local capture agent notices when you
hesitate while writing and opens a panel showing which colleagues know the topic.
Typed text never leaves your machine: only counts and topic tokens do.

## Run the full demo (Windows)

Needs [uv](https://docs.astral.sh/uv/) for the backend (it installs the Python it needs),
Python 3.12 or newer for the agent, Node.js 22 or newer, and Edge or Chrome.
Neo4j and Docker are **not** needed for this flow. Use three terminals from the repo root.

First run `node configure-demo.mjs` from the root. It creates a gitignored `.env` with a
random employee bearer token, employee identity and backend URL. Both servers and the agent
read this file. It never overwrites existing settings or prints the token. Copy missing
variable names from `.env.example` if you already have a root `.env`.

**1. Backend** (Flask on http://127.0.0.1:5000):

```sh
cd Neo4J-backend
uv sync
uv run seed_signals.py --reset
uv run run.py
```

Use only uv in `Neo4J-backend/`: installing into its `.venv` with pip as well breaks packages.

`seed_signals.py` gives the expertise filter a synthetic history (Sarah, Emma and Lucas as
current experts, Tom as stale), so the agent's "who knows" answer matches the panel.

**2. Panel and preview server** (http://127.0.0.1:4173):

```sh
node preview-server.mjs
```

**3. Capture agent:**

```sh
cd capture-agent
py -3 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m agent --backend-url http://127.0.0.1:5000
```

The agent prints every payload it sends (`-> {...}`), which is the privacy proof for the pitch.

In the panel, open **Your account → Settings**, select **Teams desktop**, enable
**Detect hesitation**, and save. Capture starts off and stops when consent expires or the
backend is unavailable. Browser capture is disabled because window titles do not prove a
trusted work origin. Only selected desktop fields are eligible.

**Demo script.** Open a Teams chat (desktop), and type:

> Hi Tom, the year-end bonus for a part-time employee in PC 200 is pro rata??

The second `?` opens the panel. So does a pause followed by "I think" or "not sure", a
deletion burst after a pause, or a placeholder like `[check]`. A single `?`, pause or hedge
does not. The agent prints
`<- doubt: struggling with ['PC_200', 'year_end_bonus']` and the panel opens top right with
Sarah De Vos using seeded recent signals. Ctrl+Alt+W opens it on demand in an opted-in field
and prints `<- who knows ...`. "Notice period in Spain" shows Emma for notice periods; Spain
itself has no expert, shown as a separate knowledge gap. A notice-period match does not
establish knowledge of Spanish employment rules.

**Check that everything is up:** http://127.0.0.1:4173/popup.html should say
"Connected to backend".

**Tests:** `uv run --with pytest pytest` in `Neo4J-backend/`, `.venv/Scripts/python -m pytest`
in `capture-agent/`, and
`node --test preview-api.test.mjs preview-ui.test.mjs` in the repo root.

## Local popup preview

Requires Node.js 22 or newer. The synthetic directory and chats work without Flask.
Topic rankings and capture settings require the authenticated backend described above.

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
its activity statistics. Browsing the demo directory shows synthetic activity and vouches.
Topic searches show backend answer-context counts and recency, with heuristic labels.

With `?popup=1` the panel fills its window and **Close**/Esc close the window: the capture agent
opens it this way on **Ctrl+Alt+W** and when the backend reports doubt (see
`capture-agent/README.md`), so keep this server running during the demo.
`?topics=notice_period,country_BE` requests both topics from `/experts`. All topics are
preserved; unavailable topics show gaps. Free-text topic aliases are matched locally using
`topic-catalog.json`; only fixed topic ids go to the expertise backend. No fabricated best
match is substituted when the backend is offline.

**Ask** opens a full conversation. **Send message** stores a message on the local UI server,
and a fictional colleague replies after 1.5 seconds. You can send follow-up messages.
Opening a chat from a profile card sends a question; opening an incoming question or ping
from Account sends a reply. Each message records that intent, so earlier conversations with
the same person do not reverse who is asking for help. Demo replies and feedback follow
the intent of the individual message.
Drafts survive navigation within the page. Feedback updates the server's vouch count once
per colleague. Chat fields and messages have light blue outlines.

For live answer learning, explicitly enable **Preview chat answers** in capture settings.
Answer a recorded incoming question. The preview sends measured input counts, fixed topic
ids and reply metadata to Flask, never the chat text. Asking questions or answering a ping
without a question does not generate an answer signal. Repeated replies to the same question
share one evidence context. Three separate credited question contexts are needed for a
suggestion. Desktop capture alone cannot identify replies. Demo feedback does not affect
backend ranking. This heuristic has no demonstrated real-world accuracy; see
[`docs/trust-validation.md`](docs/trust-validation.md).

The bearer token authenticates one configured local employee, not an organisation SSO system.
Employee writes cannot choose another user id. Graph APIs require the separately configured
`WHOKNOWS_ADMIN_TOKEN`; never expose it to the browser. Servers bind to loopback and the
preview rejects cross-origin mutations. This prototype must not be exposed as a shared
multi-employee service without per-employee authentication and access policy.

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
The compact settings popup shares the persisted backend capture preference through the
authenticated preview proxy. App opt-ins and topic exclusions are edited in Account Settings.
The agent polls these settings; capture is off on startup until consent has been loaded.

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

The settings popup's live backend indicator checks the Flask backend's `/health` through the
preview server (`http://127.0.0.1:5000` by default; set `WHOKNOWS_BACKEND_URL` to change it).
It shows offline when that backend is not running. Its status selector also supports
explicit visual simulations.

Run the UI API and interaction checks with:

```sh
node --test preview-api.test.mjs preview-ui.test.mjs
```

The previews use local sans-serif fonts, SD Worx blue (`#006dd8`), white and neutral text.
Profile images are local assets.

## Other project components

See [the expertise backend](Neo4J-backend/README.md) and
[the capture agent](capture-agent/README.md) for their setup and run commands.
