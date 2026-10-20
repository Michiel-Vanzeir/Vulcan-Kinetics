"""Wires the capture agent together: keys -> signal detector -> topic extractor -> sender.

Runs entirely on the capture worker thread, so the detector needs no locking. Text only
ever lives in the ring buffer and the detector's private window; what reaches the sender
is a SignalPayload (counts) with topics from the fixed vocabulary.

Wiring point: _emit() is where every detector payload passes. It calls extract_topics() once to
fill `topics` and hands the payload to Transport.send() once.
"""

import hashlib
import threading
from dataclasses import replace
from enum import StrEnum

from agent.buffer import BACKSPACE, NEWLINE, KeyEntry, RingBuffer
from agent.panel import PanelWindow
from agent.surfaces import Surface
from agent.transport import Transport
from signal_detector import KeyEvent, KeyKind, SignalDetector, SignalPayload
from topic_extractor import extract_topics

# Surfaces where Enter sends the message (Shift+Enter is a new line). Ctrl+Enter sends anywhere.
CHAT_SURFACES = frozenset({
    "teams_desktop", "teams_web", "slack_desktop", "slack_web", "google_chat_web",
})


class Action(StrEnum):
    CHAR = "char"
    BACKSPACE = "backspace"
    DELETE = "delete"
    PASTE = "paste"
    ENTER = "enter"
    SUBMIT = "submit"
    MANUAL = "manual"


def context_id(surface_id: str) -> str:
    """Short opaque id for a text field, so OS element ids don't travel."""
    return "c_" + hashlib.sha256(surface_id.encode("utf-8")).hexdigest()[:12]


class Pipeline:
    """Feeds one user's keystrokes through the detector and sends the resulting payloads."""

    def __init__(
        self,
        buffer: RingBuffer,
        detector: SignalDetector,
        transport: Transport,
        show_experts: bool = False,
        panel: PanelWindow | None = None,
    ):
        self._buffer = buffer
        self._detector = detector
        self._transport = transport
        self._show_experts = show_experts
        self._panel = panel
        self._focused: Surface | None = None
        self._surface_ids: dict[str, str] = {}
        self.payloads = 0

    def handle(
        self,
        surface: Surface | None,
        action: Action,
        ts_ms: int,
        char: str | None = None,
        pasted_char_count: int = 0,
    ) -> None:
        """Process one key. `surface` is None (or sensitive) for fields that must not be captured."""
        target = surface if surface is not None and not surface.is_sensitive else None
        self._switch_focus(target, ts_ms)
        if target is None:
            if action == Action.MANUAL and self._panel is not None:
                # The hotkey also works outside captured fields, just without topics.
                self._panel.open([])
            return

        if action == Action.ENTER:
            in_chat = target.name in CHAT_SURFACES
            action, char = (Action.SUBMIT, None) if in_chat else (Action.CHAR, NEWLINE)

        if action == Action.SUBMIT:
            self._emit(self._event(target, KeyKind.SUBMIT, ts_ms))
            self._buffer.clear(target.id)
        elif action == Action.MANUAL:
            payload = self._emit(self._detector.manual_trigger(context_id(target.id)))
            topics = list(payload.topics) if payload is not None else []
            if self._panel is not None:
                self._panel.open(topics)
            if self._show_experts:
                self._ask_experts(topics)
        elif action == Action.CHAR and char:
            self._buffer.append(KeyEntry(char=char, ts=ts_ms, surface_id=target.id))
            self._emit(self._event(target, KeyKind.CHAR, ts_ms, char=char))
        elif action == Action.BACKSPACE:
            self._buffer.append(KeyEntry(char=BACKSPACE, ts=ts_ms, surface_id=target.id))
            self._emit(self._event(target, KeyKind.BACKSPACE, ts_ms))
        elif action == Action.DELETE:
            self._emit(self._event(target, KeyKind.DELETE, ts_ms))
        elif action == Action.PASTE:
            self._emit(self._event(target, KeyKind.PASTE, ts_ms, pasted_char_count=pasted_char_count))

    def tick(self, now_ms: int) -> None:
        """Time-based triggers (pause, trailing ellipsis, idle flush). Call about every 100 ms."""
        for payload in self._detector.tick(now_ms):
            self._emit(payload)

    def _switch_focus(self, target: Surface | None, ts_ms: int) -> None:
        if (target and target.id) == (self._focused and self._focused.id):
            return
        if self._focused is not None:
            self._emit(self._event(self._focused, KeyKind.FOCUS_OUT, ts_ms))
        if target is not None:
            self._emit(self._event(target, KeyKind.FOCUS_IN, ts_ms))
        self._focused = target

    def _event(self, surface: Surface, kind: KeyKind, ts_ms: int, **fields) -> SignalPayload | None:
        ctx = context_id(surface.id)
        self._surface_ids[ctx] = surface.id
        return self._detector.handle_event(
            KeyEvent(ts=ts_ms, kind=kind, surface=surface.name, context_id=ctx, **fields)
        )

    def _emit(self, payload: SignalPayload | None) -> SignalPayload | None:
        """Add topics from the field's text and send. Returns the payload as sent."""
        if payload is None:
            return None
        surface_id = self._surface_ids.get(payload.context_id)
        window = self._buffer.window(surface_id) if surface_id else ""
        payload = replace(payload, topics=tuple(extract_topics(window)))
        self._transport.send(payload)
        self.payloads += 1
        return payload

    def _ask_experts(self, topics: list[str]) -> None:
        """Print who knows these topics. Runs on its own thread so typing never waits on it."""

        def ask() -> None:
            experts = self._transport.request_experts(topics)
            names = ", ".join(f"{e['user_id']} on {e['topic']} ({e['score']:.2f})" for e in experts)
            print(f"<- who knows {topics}: {names or 'nobody yet (knowledge gap)'}", flush=True)

        if topics:
            threading.Thread(target=ask, daemon=True).start()
