"""Global keyboard hook that feeds the ring buffer.

Only opted-in work surfaces are captured; password and other sensitive fields are skipped.
When the focused field can't be resolved, the keystroke is dropped: capture fails closed.
"""

import logging
import queue
import threading
import time
from collections import Counter
from collections.abc import Callable

import uiautomation as auto
from pynput import keyboard

from agent.buffer import BACKSPACE, NEWLINE, KeyEntry, RingBuffer
from agent.surface_windows import focused_surface

log = logging.getLogger(__name__)

_SPECIAL_KEYS = {
    keyboard.Key.space: " ",
    keyboard.Key.enter: NEWLINE,
    keyboard.Key.backspace: BACKSPACE,
}


def key_to_char(key: keyboard.Key | keyboard.KeyCode) -> str | None:
    """Map a pynput key to a buffer char, or None for keys we don't record."""
    if key in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[key]
    char = getattr(key, "char", None)
    # Ctrl+letter arrives as a control character; shortcuts aren't text.
    if char is not None and len(char) == 1 and char.isprintable():
        return char
    return None


class Capture:
    """Runs the keyboard hook and a worker thread that resolves surfaces and fills the buffer.

    The hook callback only enqueues, because Windows drops low-level hooks that respond slowly.
    """

    def __init__(
        self,
        buffer: RingBuffer,
        allowed_surfaces: frozenset[str],
        on_entry: Callable[[KeyEntry], None] | None = None,
    ):
        self._buffer = buffer
        self._allowed = allowed_surfaces
        self._on_entry = on_entry
        self._queue: queue.Queue[tuple[str, float] | None] = queue.Queue()
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._worker = threading.Thread(target=self._run_worker, daemon=True)
        # Keystroke counts per surface name and per drop reason. Never any text.
        self.captured: Counter[str] = Counter()
        self.dropped: Counter[str] = Counter()

    def start(self) -> None:
        self._worker.start()
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()
        self._queue.put(None)
        self._worker.join(timeout=2)

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        char = key_to_char(key) if key is not None else None
        if char is not None:
            self._queue.put((char, time.time()))

    def _run_worker(self) -> None:
        with auto.UIAutomationInitializerInThread():
            while (item := self._queue.get()) is not None:
                self._handle(*item)

    def _handle(self, char: str, ts: float) -> None:
        try:
            surface = focused_surface()
        except Exception:
            log.debug("Could not resolve focused surface", exc_info=True)
            surface = None
        if surface is None:
            self.dropped["not a work surface"] += 1
            return
        if surface.is_sensitive:
            self.dropped[f"sensitive field ({surface.name})"] += 1
            return
        if surface.name not in self._allowed:
            self.dropped[f"not opted in ({surface.name})"] += 1
            return
        entry = KeyEntry(char=char, ts=ts, surface_id=surface.id)
        self._buffer.append(entry)
        self.captured[surface.name] += 1
        if self._on_entry is not None:
            self._on_entry(entry)
