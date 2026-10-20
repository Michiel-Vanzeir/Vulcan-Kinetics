"""Input and output types of the signal detector.

KeyEvent is what the capture agent feeds in. SignalPayload is what the detector emits
and what crosses the network to the backend. The payload contract is documented in
IDEA.md under "Signal detector output".
"""

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

SCHEMA_VERSION = 1


class KeyKind(StrEnum):
    CHAR = "char"
    BACKSPACE = "backspace"
    DELETE = "delete"
    PASTE = "paste"
    FOCUS_IN = "focus_in"
    FOCUS_OUT = "focus_out"
    # The field was sent or cleared: the context's state is flushed and reset.
    SUBMIT = "submit"


class Trigger(StrEnum):
    PAUSE = "pause"
    DELETION_BURST = "deletion_burst"
    PUNCTUATION = "punctuation"
    HEDGE_WORD = "hedge_word"
    PLACEHOLDER = "placeholder"
    IDLE_FLUSH = "idle_flush"
    MANUAL = "manual"
    SUBMIT = "submit"


class PlaceholderKind(StrEnum):
    BRACKET = "bracket"
    ANGLE = "angle"
    X_RUN = "x_run"
    QUESTION_RUN = "question_run"
    TRAILING_ELLIPSIS = "trailing_ellipsis"


@dataclass(frozen=True, slots=True)
class KeyEvent:
    """One input event from the capture agent, for one compose context.

    `context_id` identifies one focused text field during one focus session.
    `char` is set only for CHAR events; `pasted_char_count` only for PASTE events.
    """

    ts: int
    kind: KeyKind
    surface: str
    context_id: str
    char: str | None = None
    pasted_char_count: int | None = None
    is_password_field: bool = False
    is_reply: bool = False
    prior_message_char_count: int | None = None


@dataclass(frozen=True, slots=True)
class SignalPayload:
    """Counted signals for one compose context. This is what crosses the network.

    Hard constraints, enforced by construction in SignalDetector.build_payload():
    - No raw text. No field can carry a sentence, a word or a character sequence.
      Every field is a count, a duration, a flag, a category (enum value, language code,
      surface name, topic id from the fixed vocabulary) or an id from the agent config.
    - Password fields never produce a payload.
    - Numbers and email addresses count toward `chars_typed` and `masked_tokens` only,
      never toward content or lexical signals.
    - Pastes count toward `paste_events` and `pasted_char_count` only, never toward
      typing, fluency or lexical signals.

    Counters cover the period since the previous payload of the same context.
    """

    # Housekeeping
    schema_version: int
    payload_seq: int
    ts: int
    user_id: str
    device_id: str
    agent_version: str
    os: str
    # Surface
    surface: str
    context_id: str
    # Timing
    trigger: Trigger
    gap_before_trigger_ms: int | None
    pause_count: int
    longest_pause_ms: int
    mean_interkey_ms: float | None
    active_typing_ms: int
    # Deletions
    backspaces: int
    deletes: int
    deletion_bursts: int
    longest_deletion_run: int
    deletion_rate: float
    # Fluency
    fluency_run_seconds: float
    longest_fluency_run_seconds: float
    # Lexical
    chars_typed: int
    content_chars: int
    masked_tokens: int
    sentence_ends: int
    question_marks: int
    hedge_words: int
    hedge_words_by_language: dict[str, int]
    placeholders: int
    placeholders_by_kind: dict[str, int]
    topics: tuple[str, ...]
    # Context
    is_reply: bool
    prior_message_char_count: int | None
    paste_events: int
    pasted_char_count: int
    focus_switches: int
    focus_session_ms: int
    # Baseline (None unless included in this payload)
    baseline_avg_pause_ms: float | None = None
    baseline_avg_deletion_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready dict of the payload."""
        data = asdict(self)
        data["topics"] = list(self.topics)
        return data
