# whoknows capture agent

Local agent that watches typing in work apps (desktop and browser), detects doubt signals and
topics, and sends only counts and topic tokens to the backend. Typed text never leaves the
machine. Full spec: "Capture agent spec" in `../IDEA.md`. Windows only for now (UI Automation).

## Setup

```sh
cd capture-agent
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
```

## Run

```sh
.venv/Scripts/python -m agent                                  # demo mode: prints payloads, sends nothing
.venv/Scripts/python -m agent --backend-url http://localhost:5000 --user-id emp_014
.venv/Scripts/python -m agent --surfaces teams_desktop,gmail_web
```

Settings come from environment variables or `capture-agent/.env` (copy `.env.example`):
`WHOKNOWS_BACKEND_URL`, `WHOKNOWS_USER_ID`, `WHOKNOWS_AUTH_TOKEN`, all documented in
`agent/config.py`. Flags override them. Start the backend first: `cd Neo4J-backend && uv run python run.py`.

Every payload is printed as the exact JSON that would be sent (`-> {...}`): this is all that
leaves the machine. Ctrl+Alt+W also asks the backend who knows the field's topics (`<- who knows ...`). Keys:

| Key | Effect |
|---|---|
| Enter | sends the message in chat apps (Teams, Slack, Google Chat); new line elsewhere |
| Ctrl+Enter | sends the message anywhere |
| Ctrl+Alt+W | "who knows?": opens the people panel as a popup (top right), pre-filtered on the field's topics, and emits a payload for the field now. Works anywhere; outside captured fields the panel opens unfiltered. |

The popup is Thomas's `../people-panel.html` in Edge or Chrome app mode (own window, separate browser
profile). Try it without the agent: `.venv/Scripts/python -m agent.panel notice_period country_BE`.
The panel also opens by itself when the backend answers a payload with a `doubt_alert` (the
expertise filter decided you are struggling with this draft), unless a panel is already open.
`--no-panel` turns both off.

Browser tabs are captured only when the window title shows a known work web app.
Private windows, personal profiles, the address bar, password fields and other
sensitive fields (PIN, card, IBAN, ...) are always skipped. The lists live in `agent/config.py`.

## Test

```sh
.venv/Scripts/python -m pytest
```

`tests/test_pipeline.py` runs synthetic keystrokes through the whole chain and into the
backend's `Neo4J-backend/expertise_filter.py`. `tests/test_e2e.py` starts the real backend on a
local port and sends a payload over HTTP (needs the backend deps from `requirements-dev.txt`).

## How it works

```
keyboard hook -> focused field (UI Automation) -> pipeline
  -> ring buffer (text, memory only)       -> topic extractor -> topic tokens
  -> signal detector (counts per trigger)  -> transport: backend format, check, POST /analyze
```

| File | Role |
|---|---|
| `agent/capture.py` | Global keyboard hook. Classifies keys (text, backspace, paste, Enter, hotkey) and enqueues them; a worker thread resolves the focused field and drives the pipeline. Fails closed. |
| `agent/pipeline.py` | Turns keys into `KeyEvent`s for the signal detector, handles focus switches and send/clear, adds topics to each payload (`extract_topics()`), hands it to `Transport.send()`. |
| `agent/backend_payload.py` | Converts detector payloads into the backend's wire format (counts cumulative per context). |
| `agent/transport.py` | **The only network path.** `send()` converts, checks (known keys, no free text, vocabulary topics only) and POSTs to `/analyze` on a background thread, one retry. `request_experts()` asks `/experts`. `_post()` is the one function that crosses the network. |
| `agent/panel.py` | Opens the people panel as a popup window on Ctrl+Alt+W or a doubt alert, with the field's topic tokens in the URL. |
| `agent/config.py` (top) | `load_config()`: backend URL, user id and auth token from the environment or `.env`. |
| `agent/surfaces.py` | OS-independent rules: which app or browser tab is a work surface, and which fields are sensitive. |
| `agent/surface_windows.py` | Focused app (foreground process + window title) and text field (UI Automation). Clipboard length for pastes. The only OS-specific file. |
| `agent/buffer.py` | Fixed-size ring buffer (4096 keystrokes) with per-field reads. `window()` applies backspaces and scrubs emails and numbers, keeping joint committees like `PC 200`. |
| `agent/config.py` | Buffer size, desktop and web surface lists, private-window markers, sensitive field words. |
| `signal_detector/` | Keystroke events in, counted signal payloads out. See its README. |
| `topic_extractor/` | Recent typing in, topic tokens from the fixed vocabulary out. See its README. |
