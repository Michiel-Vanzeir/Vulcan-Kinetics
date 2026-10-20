"""Global keyboard hook that feeds the pipeline.

Only opted-in work surfaces are captured; password and other sensitive fields are skipped.
When the focused field can't be resolved, the keystroke is dropped: capture fails closed.
"""

import logging
import queue
import threading
import time
from collections import Counter

import uiautomation as auto
from pynput import keyboard

from agent.pipeline import Action, Pipeline
from agent.surface_windows import clipboard_text_length, focused_surface

log = logging.getLogger(__name__)

TICK_INTERVAL_MS = 100
# Ctrl+Alt+W ("who knows?") opens the panel for the current field.
MANUAL_TRIGGER_VK = 0x57
_PASTE_VK = 0x56  # V

_CTRL = {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}
# AltGr counts as Alt: Windows reports Ctrl+Alt as AltGr on many layouts (incl. Belgian AZERTY).
_ALT = {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr}
_SHIFT = {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


class Capture:
    """Runs the keyboard hook and a worker thread that resolves surfaces and drives the pipeline.

    The hook callback only enqueues, because Windows drops low-level hooks that respond slowly.
    """

    def __init__(self, pipeline: Pipeline, allowed_surfaces: frozenset[str]):
        self._pipeline = pipeline
        self._allowed = allowed_surfaces
        self._queue: queue.Queue[tuple[Action, str | None, int] | None] = queue.Queue()
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._worker = threading.Thread(target=self._run_worker, daemon=True)
        self._ctrl = self._alt = self._shift = False
        # Keystroke counts per surface name and per drop reason. Never any text.
        self.captured: Counter[str] = Counter()
        self.dropped: Counter[str] = Counter()

    def start(self) -> None:
        self._worker.start()
        self._listener.start()

    def wait(self) -> None:
        """Block until the hook stops (Ctrl+C raises KeyboardInterrupt here)."""
        while self._listener.is_alive():
            self._listener.join(timeout=0.5)

    def stop(self) -> None:
        self._listener.stop()
        self._queue.put(None)
        self._worker.join(timeout=2)

    # Hook thread: classify the key and enqueue, nothing else.

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        self._set_modifier(key, pressed=False)

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key is None or self._set_modifier(key, pressed=True):
            return
        action = self._classify(key)
        if action is not None:
            self._queue.put((*action, _now_ms()))

    def _set_modifier(self, key: keyboard.Key | keyboard.KeyCode | None, pressed: bool) -> bool:
        if key in _CTRL:
            self._ctrl = pressed
        elif key in _ALT:
            self._alt = pressed
        elif key in _SHIFT:
            self._shift = pressed
        else:
            return False
        return True

    def _classify(self, key: keyboard.Key | keyboard.KeyCode) -> tuple[Action, str | None] | None:
        vk = getattr(key, "vk", None)
        if self._ctrl and self._alt and vk == MANUAL_TRIGGER_VK:
            return Action.MANUAL, None
        if self._ctrl and not self._alt and vk == _PASTE_VK:
            return Action.PASTE, None
        if key == keyboard.Key.enter:
            if self._ctrl:
                return Action.SUBMIT, None
            return (Action.CHAR, "\n") if self._shift else (Action.ENTER, None)
        if key == keyboard.Key.space:
            return Action.CHAR, " "
        if key == keyboard.Key.backspace:
            return Action.BACKSPACE, None
        if key == keyboard.Key.delete:
            return Action.DELETE, None
        char = getattr(key, "char", None)
        # Ctrl+letter arrives as a control character; shortcuts aren't text.
        if char is not None and len(char) == 1 and char.isprintable():
            return Action.CHAR, char
        return None

    # Worker thread: resolve the focused field, drive the pipeline, tick.

    def _run_worker(self) -> None:
        with auto.UIAutomationInitializerInThread():
            last_tick = _now_ms()
            while True:
                try:
                    item = self._queue.get(timeout=TICK_INTERVAL_MS / 1000)
                except queue.Empty:
                    item = ()
                if item is None:
                    return
                if item:
                    self._handle(*item)
                now = _now_ms()
                if now - last_tick >= TICK_INTERVAL_MS:
                    self._pipeline.tick(now)
                    last_tick = now

    def _handle(self, action: Action, char: str | None, ts_ms: int) -> None:
        try:
            surface = focused_surface()
        except Exception:
            log.debug("Could not resolve focused surface", exc_info=True)
            surface = None
        if surface is None:
            self.dropped["not a work surface"] += 1
        elif surface.is_sensitive:
            self.dropped[f"sensitive field ({surface.name})"] += 1
        elif surface.name not in self._allowed:
            self.dropped[f"not opted in ({surface.name})"] += 1
            surface = None
        else:
            self.captured[surface.name] += 1
        pasted = clipboard_text_length() if action == Action.PASTE and surface else 0
        self._pipeline.handle(surface, action, ts_ms, char=char, pasted_char_count=pasted)
