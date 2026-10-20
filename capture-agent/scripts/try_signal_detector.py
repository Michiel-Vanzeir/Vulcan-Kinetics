"""Try the signal detector by typing in this console window (Windows only).

Only keys typed in this window are read; nothing else on the machine is captured.
Your typing is echoed like any terminal. Each payload is printed as its non-zero counts.

    .venv/Scripts/python -m scripts.try_signal_detector

Keys: Ctrl+T manual trigger, Ctrl+S submit (send/clear the field), Esc quit.
"""

import msvcrt
import time

from signal_detector import DetectorConfig, KeyEvent, KeyKind, SignalDetector, SignalPayload

CONTEXT_ID = "console"
SURFACE = "console_test"
TICK_S = 0.05
CTRL_S = "\x13"
CTRL_T = "\x14"
ESC = "\x1b"
# Fields that are always set and only add noise when trying things out.
_HIDDEN_FIELDS = {
    "schema_version", "ts", "user_id", "device_id", "agent_version", "os",
    "surface", "context_id", "trigger", "payload_seq", "is_reply",
}


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def show(payload: SignalPayload) -> None:
    counts = {
        name: value
        for name, value in payload.to_dict().items()
        if name not in _HIDDEN_FIELDS and value not in (0, 0.0, None, {}, [])
    }
    print(f"\n  >> #{payload.payload_seq} {payload.trigger.upper()}  {counts}\n", flush=True)


def event(kind: KeyKind, **fields) -> KeyEvent:
    return KeyEvent(ts=_now_ms(), kind=kind, surface=SURFACE, context_id=CONTEXT_ID, **fields)


def main() -> None:
    detector = SignalDetector(DetectorConfig(user_id="u_try", device_id="d_try", clock=_now_ms))
    detector.handle_event(event(KeyKind.FOCUS_IN))
    print(__doc__.split("\n\n")[-1].strip())
    print("Start typing. Try a hedge (\"I think \"), a pause, fast backspaces, [name], xxx...\n")

    while True:
        if not msvcrt.kbhit():
            for payload in detector.tick():
                show(payload)
            time.sleep(TICK_S)
            continue

        char = msvcrt.getwch()
        payload = None
        if char in ("\x00", "\xe0"):
            msvcrt.getwch()  # arrow/function key: second half of the code, ignored
        elif char == ESC:
            break
        elif char == CTRL_T:
            payload = detector.manual_trigger(CONTEXT_ID)
        elif char == CTRL_S:
            payload = detector.handle_event(event(KeyKind.SUBMIT))
            detector.handle_event(event(KeyKind.FOCUS_IN))
        elif char == "\b":
            print("\b \b", end="", flush=True)
            payload = detector.handle_event(event(KeyKind.BACKSPACE))
        else:
            char = "\n" if char == "\r" else char
            print(char, end="", flush=True)
            payload = detector.handle_event(event(KeyKind.CHAR, char=char))
        if payload is not None:
            show(payload)

    print("\nBaseline:", detector.get_baseline("u_try"))


if __name__ == "__main__":
    main()
