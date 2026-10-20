"""Signal detector: turns keystroke events into counted signals per compose context.

Consumes KeyEvent streams produced by the capture agent (`capture-agent/agent/pipeline.py`).
The detector itself is tested with synthetic streams.

The detector measures, it doesn't interpret: hesitation labels (TYPING / HESITATING /
STRUGGLING) come from the backend scoring module, which consumes these payloads.

Hard constraints:
1. No raw text leaves the detector. `build_payload()` is the only producer of payloads and
   copies counts and categories only. The private text window is never read there.
2. Password fields are hard-skipped from focus_in to focus_out: no state, no payloads.
3. Numbers and email addresses are masked before any lexical detection. They count toward
   `chars_typed` and `masked_tokens` only.
4. Pastes count toward `paste_events` and `pasted_char_count` only, never toward typing,
   fluency or lexical signals.
5. State is per context: focus_out pauses it, focus_in resumes it, submit resets it.
"""

import time
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from signal_detector.baseline import BaselineTracker
from signal_detector.events import (
    SCHEMA_VERSION,
    KeyEvent,
    KeyKind,
    PlaceholderKind,
    SignalPayload,
    Trigger,
)
from signal_detector.hedges import DEFAULT_HEDGES_PATH, HedgeMatcher, load_hedges
from signal_detector.placeholders import completed_placeholder, ends_with_ellipsis

# Stands in for a masked number, email or pasted block in the private window.
MASK = "\x00"
# Chars kept in the private window: enough for the longest hedge or placeholder.
WINDOW_CHARS = 200
# Closing chars stripped before hedge matching, so "maybe)" or "maybe." still match.
_TRAILING_PUNCTUATION = ".,;:)]}\"'"
# Highest priority first: one payload per event, carrying the most specific trigger.
_TRIGGER_PRIORITY = (
    Trigger.DELETION_BURST,
    Trigger.HEDGE_WORD,
    Trigger.PLACEHOLDER,
    Trigger.PUNCTUATION,
    Trigger.PAUSE,
)


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


@dataclass(frozen=True)
class DetectorConfig:
    """Settings constant for one agent run. Thresholds default to the IDEA.md spec."""

    user_id: str
    device_id: str = "unknown"
    agent_version: str = "0.1.0"
    os: str = "windows"
    pause_ms: int = 800
    long_pause_ms: int = 2_000
    rewrite_min_deletions: int = 3  # deleting at least this many, then typing again
    deletion_burst_keys: int = 3  # a burst is MORE than this many deletions...
    deletion_burst_window_ms: int = 500  # ...within this window
    idle_flush_ms: int = 10_000
    ellipsis_pause_ms: int = 2_000
    baseline_alpha: float = 0.1
    baseline_gap_cap_ms: int = 10_000
    baseline_shift: float = 0.2
    hedges_path: Path = DEFAULT_HEDGES_PATH
    clock: Callable[[], int] = _now_ms


@dataclass
class _Counters:
    """Signals since the previous payload of one context. Reset after every payload."""

    events: int = 0
    pause_count: int = 0
    long_pauses: int = 0
    longest_pause_ms: int = 0
    gap_sum_ms: int = 0
    gap_count: int = 0
    active_typing_ms: int = 0
    backspaces: int = 0
    deletes: int = 0
    deletion_bursts: int = 0
    longest_deletion_run: int = 0
    rewrite_loops: int = 0
    longest_fluency_ms: int = 0
    chars_typed: int = 0
    content_chars: int = 0
    masked_tokens: int = 0
    sentence_ends: int = 0
    question_marks: int = 0
    hedges: Counter[str] = field(default_factory=Counter)
    placeholders: Counter[str] = field(default_factory=Counter)
    paste_events: int = 0
    pasted_char_count: int = 0


@dataclass
class _Context:
    """State of one compose context. `window` is the only text held, in memory only."""

    context_id: str
    surface: str
    is_reply: bool
    prior_message_char_count: int | None
    last_emit_ts: int
    counters: _Counters = field(default_factory=_Counters)
    window: deque[str] = field(default_factory=lambda: deque(maxlen=WINDOW_CHARS))
    in_email: bool = False
    in_number: bool = False
    token_content_chars: int = 0
    last_key_ts: int | None = None
    run_start_ts: int | None = None
    pause_reported: bool = False
    long_pause_reported: bool = False
    ellipsis_reported: bool = False
    recent_deletions: deque[int] = field(default_factory=deque)
    in_burst: bool = False
    deletion_run: int = 0
    focused: bool = False
    focus_started_ts: int = 0
    focus_ms: int = 0
    focus_switches: int = 0
    was_blurred: bool = False

    def text(self) -> str:
        return "".join(self.window)


class SignalDetector:
    """Keeps per-context state and emits a SignalPayload when a trigger fires."""

    def __init__(self, config: DetectorConfig):
        self._config = config
        self._hedges = HedgeMatcher(load_hedges(config.hedges_path))
        self._baseline = BaselineTracker(
            alpha=config.baseline_alpha,
            gap_cap_ms=config.baseline_gap_cap_ms,
            shift_threshold=config.baseline_shift,
        )
        self._contexts: dict[str, _Context] = {}
        self._password_contexts: set[str] = set()
        self._payload_seq = 0

    # Public API

    def handle_event(self, event: KeyEvent) -> SignalPayload | None:
        """Process one event. Returns a payload if a trigger fired, else None.

        Password contexts are ignored from focus_in to focus_out, without creating state.
        """
        if self._skip_password(event):
            return None
        if event.kind == KeyKind.FOCUS_IN:
            self._focus_in(event)
            return None
        if event.kind == KeyKind.FOCUS_OUT:
            ctx = self._contexts.get(event.context_id)
            if ctx is not None and ctx.focused:
                self._blur(ctx, event.ts)
            return None
        if event.kind == KeyKind.SUBMIT:
            ctx = self._contexts.pop(event.context_id, None)
            return self.build_payload(ctx, Trigger.SUBMIT, event.ts) if ctx else None
        return self._handle_input(event)

    def tick(self, now_ms: int | None = None) -> list[SignalPayload]:
        """Fire time-based triggers (pause, trailing ellipsis, idle flush) without a keystroke.

        The capture agent should call this every ~100 ms. Only focused contexts are checked.
        """
        now = self._config.clock() if now_ms is None else now_ms
        payloads = []
        for ctx in list(self._contexts.values()):
            if ctx.focused:
                trigger = self._time_trigger(ctx, now)
                if trigger is not None:
                    payloads.append(self.build_payload(ctx, trigger, now))
        return payloads

    def manual_trigger(self, context_id: str) -> SignalPayload | None:
        """Emit a payload for a context now, e.g. from the hotkey. None if the context is unknown."""
        ctx = self._contexts.get(context_id)
        if ctx is None:
            return None
        return self.build_payload(ctx, Trigger.MANUAL, self._config.clock())

    def get_baseline(self, user_id: str) -> dict[str, float | None]:
        """Rolling baseline for a user: avg_pause_ms and avg_deletion_rate (None until observed)."""
        return self._baseline.get(user_id)

    # THE FUNCTION THAT PRODUCES THE PAYLOAD SENT TO THE NETWORK.
    # It reads counters, timestamps, flags and config ids only. It never reads ctx.window,
    # the only text this module holds, and SignalPayload has no field that could carry text.
    def build_payload(self, ctx: _Context, trigger: Trigger, now_ms: int) -> SignalPayload:
        """Build the payload for one context, then reset that context's counters."""
        c = ctx.counters
        deletions = c.backspaces + c.deletes
        current_run_ms = (
            ctx.last_key_ts - ctx.run_start_ts
            if ctx.run_start_ts is not None and ctx.last_key_ts is not None
            else 0
        )
        focus_session_ms = ctx.focus_ms + (now_ms - ctx.focus_started_ts if ctx.focused else 0)
        self._baseline.observe_deletion_rate(self._config.user_id, deletions, c.chars_typed)
        baseline = self._baseline.take_if_due(self._config.user_id) or {}
        self._payload_seq += 1

        payload = SignalPayload(
            schema_version=SCHEMA_VERSION,
            payload_seq=self._payload_seq,
            ts=now_ms,
            user_id=self._config.user_id,
            device_id=self._config.device_id,
            agent_version=self._config.agent_version,
            os=self._config.os,
            surface=ctx.surface,
            context_id=ctx.context_id,
            trigger=trigger,
            gap_before_trigger_ms=None if ctx.last_key_ts is None else now_ms - ctx.last_key_ts,
            pause_count=c.pause_count,
            long_pause_count=c.long_pauses,
            longest_pause_ms=c.longest_pause_ms,
            mean_interkey_ms=c.gap_sum_ms / c.gap_count if c.gap_count else None,
            active_typing_ms=c.active_typing_ms,
            backspaces=c.backspaces,
            deletes=c.deletes,
            deletion_bursts=c.deletion_bursts,
            longest_deletion_run=c.longest_deletion_run,
            rewrite_loops=c.rewrite_loops,
            deletion_rate=deletions / c.chars_typed if c.chars_typed else 0.0,
            fluency_run_seconds=current_run_ms / 1000,
            longest_fluency_run_seconds=max(c.longest_fluency_ms, current_run_ms) / 1000,
            chars_typed=c.chars_typed,
            content_chars=c.content_chars,
            masked_tokens=c.masked_tokens,
            sentence_ends=c.sentence_ends,
            question_marks=c.question_marks,
            hedge_words=sum(c.hedges.values()),
            hedge_words_by_language=dict(c.hedges),
            placeholders=sum(c.placeholders.values()),
            placeholders_by_kind=dict(c.placeholders),
            topics=(),
            is_reply=ctx.is_reply,
            prior_message_char_count=ctx.prior_message_char_count,
            paste_events=c.paste_events,
            pasted_char_count=c.pasted_char_count,
            focus_switches=ctx.focus_switches,
            focus_session_ms=focus_session_ms,
            baseline_avg_pause_ms=baseline.get("avg_pause_ms"),
            baseline_avg_deletion_rate=baseline.get("avg_deletion_rate"),
        )
        ctx.counters = _Counters()
        ctx.last_emit_ts = now_ms
        return payload

    # Focus and password handling

    def _skip_password(self, event: KeyEvent) -> bool:
        if event.context_id in self._password_contexts:
            if event.kind == KeyKind.FOCUS_OUT:
                self._password_contexts.discard(event.context_id)
            return True
        if event.is_password_field:
            if event.kind != KeyKind.FOCUS_OUT:
                self._password_contexts.add(event.context_id)
            # A field that turns out to be a password field keeps no state at all.
            self._contexts.pop(event.context_id, None)
            return True
        return False

    def _focus_in(self, event: KeyEvent) -> _Context:
        for other in self._contexts.values():
            if other.focused and other.context_id != event.context_id:
                self._blur(other, event.ts)
        ctx = self._contexts.get(event.context_id)
        if ctx is None:
            ctx = _Context(
                context_id=event.context_id,
                surface=event.surface,
                is_reply=event.is_reply,
                prior_message_char_count=event.prior_message_char_count,
                last_emit_ts=event.ts,
            )
            self._contexts[event.context_id] = ctx
        elif ctx.focused:
            return ctx
        if ctx.was_blurred:
            ctx.focus_switches += 1
        ctx.is_reply = event.is_reply
        ctx.prior_message_char_count = event.prior_message_char_count
        ctx.focused = True
        ctx.focus_started_ts = event.ts
        # Time spent elsewhere is neither a pause nor idle time in this context.
        ctx.last_key_ts = None
        ctx.last_emit_ts = event.ts
        return ctx

    def _blur(self, ctx: _Context, ts: int) -> None:
        self._end_run(ctx)
        ctx.focus_ms += ts - ctx.focus_started_ts
        ctx.focused = False
        ctx.was_blurred = True

    # Input handling

    def _handle_input(self, event: KeyEvent) -> SignalPayload | None:
        ctx = self._contexts.get(event.context_id)
        if ctx is None or not ctx.focused:
            # Input without a focus_in implies focus.
            ctx = self._focus_in(event)
        ctx.counters.events += 1
        if event.kind in (KeyKind.BACKSPACE, KeyKind.DELETE, KeyKind.PASTE):
            # Deleting or pasting ends the fluent run at the previous keystroke.
            self._end_run(ctx)
        triggers = set(self._timing(ctx, event))

        if event.kind == KeyKind.CHAR and event.char:
            triggers.update(self._on_char(ctx, event.char, event.ts))
        elif event.kind in (KeyKind.BACKSPACE, KeyKind.DELETE):
            triggers.update(self._on_deletion(ctx, event.kind, event.ts))
        elif event.kind == KeyKind.PASTE:
            self._on_paste(ctx, event.pasted_char_count or 0)

        if event.kind not in (KeyKind.BACKSPACE, KeyKind.DELETE):
            if event.kind == KeyKind.CHAR and ctx.deletion_run >= self._config.rewrite_min_deletions:
                # Deleted a chunk and started typing again: one rewrite loop.
                ctx.counters.rewrite_loops += 1
            ctx.in_burst = False
            ctx.deletion_run = 0
            ctx.recent_deletions.clear()

        trigger = next((t for t in _TRIGGER_PRIORITY if t in triggers), None)
        if trigger is None and event.ts - ctx.last_emit_ts >= self._config.idle_flush_ms:
            trigger = Trigger.IDLE_FLUSH
        return self.build_payload(ctx, trigger, event.ts) if trigger else None

    def _timing(self, ctx: _Context, event: KeyEvent) -> list[Trigger]:
        """Gap since the previous input: pause and ellipsis triggers, timing stats."""
        triggers: list[Trigger] = []
        if ctx.last_key_ts is not None:
            gap = event.ts - ctx.last_key_ts
            c = ctx.counters
            if gap > self._config.pause_ms:
                if not ctx.pause_reported:
                    c.pause_count += 1
                    triggers.append(Trigger.PAUSE)
                c.longest_pause_ms = max(c.longest_pause_ms, gap)
                if gap > self._config.long_pause_ms and not ctx.long_pause_reported:
                    c.long_pauses += 1
                self._end_run(ctx)
                if self._ellipsis_due(ctx, gap):
                    triggers.append(Trigger.PLACEHOLDER)
            is_keystroke = event.kind != KeyKind.PASTE
            if is_keystroke and gap <= self._config.pause_ms:
                c.active_typing_ms += gap
            if is_keystroke and gap < self._config.baseline_gap_cap_ms:
                c.gap_sum_ms += gap
                c.gap_count += 1
                self._baseline.observe_gap(self._config.user_id, gap)
        ctx.pause_reported = False
        ctx.long_pause_reported = False
        ctx.ellipsis_reported = False
        ctx.last_key_ts = event.ts
        return triggers

    def _time_trigger(self, ctx: _Context, now: int) -> Trigger | None:
        """Trigger for a focused context that has been quiet until `now`, if any."""
        triggers = []
        if ctx.last_key_ts is not None:
            idle = now - ctx.last_key_ts
            if idle > self._config.pause_ms and not ctx.pause_reported:
                ctx.pause_reported = True
                ctx.counters.pause_count += 1
                ctx.counters.longest_pause_ms = max(ctx.counters.longest_pause_ms, idle)
                self._end_run(ctx)
                triggers.append(Trigger.PAUSE)
            if idle > self._config.long_pause_ms and not ctx.long_pause_reported:
                ctx.long_pause_reported = True
                ctx.counters.long_pauses += 1
            if self._ellipsis_due(ctx, idle):
                triggers.append(Trigger.PLACEHOLDER)
        trigger = next((t for t in _TRIGGER_PRIORITY if t in triggers), None)
        if (
            trigger is None
            and ctx.counters.events
            and now - ctx.last_emit_ts >= self._config.idle_flush_ms
        ):
            trigger = Trigger.IDLE_FLUSH
        return trigger

    def _ellipsis_due(self, ctx: _Context, quiet_ms: int) -> bool:
        if (
            quiet_ms > self._config.ellipsis_pause_ms
            and not ctx.ellipsis_reported
            and ends_with_ellipsis(ctx.text())
        ):
            ctx.ellipsis_reported = True
            ctx.counters.placeholders[PlaceholderKind.TRAILING_ELLIPSIS] += 1
            return True
        return False

    def _on_char(self, ctx: _Context, char: str, ts: int) -> list[Trigger]:
        c = ctx.counters
        c.chars_typed += 1
        char = char.replace("’", "'")

        # Masking: emails and numbers are never content and never reach lexical detection.
        if char == "@":
            self._mask_current_token(ctx)
            ctx.in_email = True
            return []
        if ctx.in_email and not char.isspace():
            return []
        if char.isdigit():
            if len(ctx.window) >= 2 and ctx.window[-1] in ".," and ctx.window[-2] == MASK:
                # Decimal or thousands separator inside a number: part of the masked token.
                ctx.window.pop()
                c.content_chars = max(0, c.content_chars - 1)
            elif not ctx.in_number:
                ctx.in_number = True
                c.masked_tokens += 1
                ctx.window.append(MASK)
            return []
        if ctx.in_number and char not in ".,":
            ctx.in_number = False

        c.content_chars += 1
        ctx.token_content_chars += 1
        triggers: list[Trigger] = []

        if char.isspace():
            ctx.in_email = False
            ctx.in_number = False
            triggers += self._complete_token(ctx, newline=char == "\n")
            ctx.token_content_chars = 0
        elif char in "?!":
            if self._match_hedge(ctx, ctx.text()):
                triggers.append(Trigger.HEDGE_WORD)
            c.sentence_ends += 1
            if char == "?":
                c.question_marks += 1
            triggers.append(Trigger.PUNCTUATION)

        self._extend_run(ctx, ts)
        ctx.window.append(char)
        placeholder = completed_placeholder(ctx.text())
        if placeholder is not None:
            c.placeholders[placeholder] += 1
            triggers.append(Trigger.PLACEHOLDER)
        return triggers

    def _complete_token(self, ctx: _Context, newline: bool) -> list[Trigger]:
        """Whitespace ends a token: check for a hedge and a sentence end before it."""
        triggers = []
        text = ctx.text()
        if self._match_hedge(ctx, text.rstrip(_TRAILING_PUNCTUATION)):
            triggers.append(Trigger.HEDGE_WORD)
        # "." only ends a sentence once whitespace follows, so "3.5" and "a.b@x.com" don't.
        closed = text.rstrip(")]}\"'")
        if newline or (closed.endswith(".") and not closed.endswith("..")):
            ctx.counters.sentence_ends += 1
            triggers.append(Trigger.PUNCTUATION)
        return triggers

    def _match_hedge(self, ctx: _Context, text: str) -> bool:
        language = self._hedges.match(text)
        if language is None:
            return False
        ctx.counters.hedges[language] += 1
        # A hedge interrupts a fluent run.
        self._end_run(ctx)
        return True

    def _mask_current_token(self, ctx: _Context) -> None:
        """Replace the token typed so far (an email's local part) with a mask."""
        while ctx.window and not ctx.window[-1].isspace():
            ctx.window.pop()
        ctx.counters.content_chars = max(0, ctx.counters.content_chars - ctx.token_content_chars)
        ctx.token_content_chars = 0
        if not ctx.in_number:
            ctx.counters.masked_tokens += 1
        ctx.in_number = False
        ctx.window.append(MASK)

    def _on_deletion(self, ctx: _Context, kind: KeyKind, ts: int) -> list[Trigger]:
        c = ctx.counters
        if kind == KeyKind.BACKSPACE:
            c.backspaces += 1
            if ctx.window and not ctx.in_email:
                if ctx.window.pop() == MASK:
                    ctx.in_number = False
                ctx.token_content_chars = max(0, ctx.token_content_chars - 1)
        else:
            c.deletes += 1
        ctx.deletion_run += 1
        c.longest_deletion_run = max(c.longest_deletion_run, ctx.deletion_run)

        window_start = ts - self._config.deletion_burst_window_ms
        ctx.recent_deletions.append(ts)
        while ctx.recent_deletions and ctx.recent_deletions[0] <= window_start:
            ctx.recent_deletions.popleft()
        if len(ctx.recent_deletions) > self._config.deletion_burst_keys:
            if not ctx.in_burst:
                ctx.in_burst = True
                c.deletion_bursts += 1
                return [Trigger.DELETION_BURST]
        else:
            ctx.in_burst = False
        return []

    def _on_paste(self, ctx: _Context, pasted_char_count: int) -> None:
        ctx.counters.paste_events += 1
        ctx.counters.pasted_char_count += pasted_char_count
        # Pasted text isn't typing and is opaque to lexical checks.
        ctx.in_email = False
        ctx.in_number = False
        ctx.token_content_chars = 0
        ctx.window.append(MASK)

    # Fluency runs

    def _extend_run(self, ctx: _Context, ts: int) -> None:
        if ctx.run_start_ts is None:
            ctx.run_start_ts = ts

    def _end_run(self, ctx: _Context) -> None:
        if ctx.run_start_ts is not None and ctx.last_key_ts is not None:
            run_ms = ctx.last_key_ts - ctx.run_start_ts
            ctx.counters.longest_fluency_ms = max(ctx.counters.longest_fluency_ms, run_ms)
        ctx.run_start_ts = None
