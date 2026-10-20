# whoknows capture agent

Local agent that watches typing in opted-in desktop work apps, detects doubt signals and
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
.venv/Scripts/python -m agent --surfaces teams_desktop
```

Run `node configure-demo.mjs` at the repo root first. Settings come from root `.env`,
`capture-agent/.env`, then environment variables (later values override earlier ones):
`WHOKNOWS_BACKEND_URL`, `WHOKNOWS_USER_ID`, `WHOKNOWS_AUTH_TOKEN`, all documented in
`agent/config.py`. Flags override them. Start the backend first: `cd Neo4J-backend && uv run python run.py`.

Every payload is printed as the exact JSON that would be sent (`-> {...}`): this is all that
leaves the machine. Ctrl+Alt+W also asks the backend who knows the field's topics (`<- who knows ...`). Keys:

| Key | Effect |
|---|---|
| Enter | sends the message in chat apps (Teams, Slack, Google Chat); new line elsewhere |
| Ctrl+Enter | sends the message anywhere |
| Ctrl+Alt+W | Opens the people panel for the current opted-in desktop field and emits a derived payload. Disabled capture does not inspect keys. |

The popup is Thomas's `../people-panel.html` in Edge or Chrome app mode (own window, separate browser
profile), served by the preview server: start it first with `node preview-server.mjs` in the repo
root (see `../README.md`), or the panel shows no colleagues. Try it without the agent: `.venv/Scripts/python -m agent.panel notice_period country_BE`.
The panel also opens by itself when the backend answers a payload with a `doubt_alert` (the
expertise filter decided you are struggling with this draft), unless a panel is already open.
`--no-panel` turns both off.

Capture starts off. In Account > Settings, select a desktop app and enable detection.
The agent polls persisted backend consent and stops on expired consent or network failure.
Backend URLs must be local HTTP(S) origins (`127.0.0.1`, `localhost` or `[::1]`), with an
optional port. External hosts, URL credentials, paths, queries and fragments are rejected.
Redirects and environment proxies cannot reroute agent requests. See
[`../docs/runtime-security.md`](../docs/runtime-security.md) for the boundary and tests.
Browser capture is disabled: page titles cannot prove a trusted origin or work profile.
Unresolved and sensitive fields are dropped before queueing; focus is checked again before
processing. Slow accessibility providers cause dropped keys. See `../docs/trust-validation.md`.

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
| `agent/capture.py` | Checks consent and field sensitivity before classifying and queueing keys. Queue is bounded; worker rechecks focus. Untrusted focus clears local text. |
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
