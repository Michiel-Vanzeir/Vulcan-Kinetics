# whoknows capture agent

Local agent that captures keystrokes from work apps (desktop and browser) into an in-memory ring buffer.
Full spec: "Capture agent spec" in `../IDEA.md`. Windows only for now (UI Automation).

## Setup

```sh
cd capture-agent
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
```

## Run

```sh
.venv/Scripts/python -m agent                                # all known work surfaces
.venv/Scripts/python -m agent --surfaces teams_desktop,gmail_web
```

Browser tabs are captured only when the window title shows a known work web app.
Private windows, personal profiles, the address bar, password fields and other
sensitive fields (PIN, card, IBAN, ...) are always skipped. The lists live in `agent/config.py`.

It prints capture counts every 5 s. Typed text is never printed, logged or written to disk.

## Test

```sh
.venv/Scripts/python -m pytest
```

## How it works

| File | Role |
|---|---|
| `agent/capture.py` | Global keyboard hook. Enqueues keys fast, a worker thread resolves the focused field and fills the buffer. Drops the key if the field is sensitive, not opted in, or can't be resolved (fails closed). |
| `agent/surfaces.py` | OS-independent rules: which app or browser tab is a work surface, and which fields are sensitive. |
| `agent/surface_windows.py` | Focused app (foreground process + window title) and text field (UI Automation runtime id, `IsPassword`, name). The only OS-specific file; a macOS version would replace it. |
| `agent/buffer.py` | Fixed-size ring buffer (4096 keystrokes) with per-field reads. `window()` applies backspaces and scrubs emails and numbers, keeping joint committees like `PC_200`. |
| `agent/config.py` | Buffer size, desktop and web surface lists, private-window markers, sensitive field words. |
