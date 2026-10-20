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
.venv/Scripts/python -m agent --backend-url http://localhost:5000/analyze --user-id emp_014
.venv/Scripts/python -m agent --surfaces teams_desktop,gmail_web
```

Every payload is printed as the exact JSON that would be sent (`-> {...}`): this is all that
leaves the machine. Keys:

| Key | Effect |
|---|---|
| Enter | sends the message in chat apps (Teams, Slack, Google Chat); new line elsewhere |
| Ctrl+Enter | sends the message anywhere |
| Ctrl+Alt+W | "who knows?": emit a payload for the current field now |

Browser tabs are captured only when the window title shows a known work web app.
Private windows, personal profiles, the address bar, password fields and other
sensitive fields (PIN, card, IBAN, ...) are always skipped. The lists live in `agent/config.py`.

## Test

```sh
.venv/Scripts/python -m pytest
```

`tests/test_pipeline.py` runs synthetic keystrokes through the whole chain and into the
backend's `Neo4J-backend/expertise_filter.py`.

## How it works

```
keyboard hook -> focused field (UI Automation) -> pipeline
  -> ring buffer (text, memory only)       -> topic extractor -> topic tokens
  -> signal detector (counts per trigger)  -> backend format (cumulative) -> sender (check, POST)
```

| File | Role |
|---|---|
| `agent/capture.py` | Global keyboard hook. Classifies keys (text, backspace, paste, Enter, hotkey) and enqueues them; a worker thread resolves the focused field and drives the pipeline. Fails closed. |
| `agent/pipeline.py` | Turns keys into `KeyEvent`s for the signal detector, handles focus switches and send/clear, adds topics to each payload, hands it to the sender. |
| `agent/backend_payload.py` | Converts detector payloads into the backend's wire format (counts cumulative per context). |
| `agent/sender.py` | **The only network path.** Checks every payload (known keys, no free text, vocabulary topics only), then POSTs it on a background thread. |
| `agent/surfaces.py` | OS-independent rules: which app or browser tab is a work surface, and which fields are sensitive. |
| `agent/surface_windows.py` | Focused app (foreground process + window title) and text field (UI Automation). Clipboard length for pastes. The only OS-specific file. |
| `agent/buffer.py` | Fixed-size ring buffer (4096 keystrokes) with per-field reads. `window()` applies backspaces and scrubs emails and numbers, keeping joint committees like `PC 200`. |
| `agent/config.py` | Buffer size, desktop and web surface lists, private-window markers, sensitive field words. |
| `signal_detector/` | Keystroke events in, counted signal payloads out. See its README. |
| `topic_extractor/` | Recent typing in, topic tokens from the fixed vocabulary out. See its README. |
