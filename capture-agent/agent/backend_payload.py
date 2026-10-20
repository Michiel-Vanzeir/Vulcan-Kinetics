"""Convert signal detector payloads into the backend's wire format.

The detector counts since its previous payload; the backend (Neo4J-backend/expertise_filter.py)
expects counts CUMULATIVE since the compose context opened and keeps only the latest payload
per context. This module keeps the running totals, per context, in memory.

Only counts, flags, ids and topic tokens go in. No text can: the input is a SignalPayload.
"""

from dataclasses import dataclass, field

from signal_detector import SignalPayload, Trigger

# Detector trigger -> backend trigger name.
_TRIGGERS = {Trigger.HEDGE_WORD: "hedge"}


@dataclass
class _Totals:
    opened_ts: int
    pauses: int = 0
    long_pauses: int = 0
    chars_typed: int = 0
    chars_deleted: int = 0
    deletion_bursts: int = 0
    rewrite_loops: int = 0
    longest_fluency_run_seconds: float = 0.0
    hedge_words: int = 0
    placeholders: int = 0
    question_marks: int = 0
    paste_events: int = 0
    pasted_char_count: int = 0
    topics: set[str] = field(default_factory=set)


class BackendPayloads:
    """Turns each detector payload into the cumulative dict the backend ingests."""

    def __init__(self) -> None:
        self._totals: dict[str, _Totals] = {}
        self._baseline_pause_ms = 0
        self._baseline_deletion_rate = 0.0

    def convert(self, p: SignalPayload) -> dict:
        """Backend payload for this detector payload. A submit closes the context."""
        t = self._totals.setdefault(p.context_id, _Totals(opened_ts=p.ts - p.focus_session_ms))
        t.pauses += p.pause_count
        t.long_pauses += p.long_pause_count
        t.chars_typed += p.chars_typed
        t.chars_deleted += p.backspaces + p.deletes
        t.deletion_bursts += p.deletion_bursts
        t.rewrite_loops += p.rewrite_loops
        t.longest_fluency_run_seconds = max(
            t.longest_fluency_run_seconds, p.longest_fluency_run_seconds
        )
        t.hedge_words += p.hedge_words
        t.placeholders += p.placeholders
        t.question_marks += p.question_marks
        t.paste_events += p.paste_events
        t.pasted_char_count += p.pasted_char_count
        t.topics.update(p.topics)
        if p.baseline_avg_pause_ms is not None:
            self._baseline_pause_ms = round(p.baseline_avg_pause_ms)
        if p.baseline_avg_deletion_rate is not None:
            self._baseline_deletion_rate = round(p.baseline_avg_deletion_rate, 4)

        payload = {
            "user_id": p.user_id,
            "context_id": p.context_id,
            "ts": p.ts,
            "trigger": _TRIGGERS.get(p.trigger, str(p.trigger)),
            "pauses": t.pauses,
            "long_pauses": t.long_pauses,
            "time_since_last_key_ms": max(0, p.gap_before_trigger_ms or 0),
            "context_age_ms": max(0, p.ts - t.opened_ts),
            "chars_typed": t.chars_typed,
            "chars_deleted": t.chars_deleted,
            "deletion_bursts": t.deletion_bursts,
            "rewrite_loops": t.rewrite_loops,
            "fluency_run_seconds": round(p.fluency_run_seconds, 2),
            "longest_fluency_run_seconds": round(t.longest_fluency_run_seconds, 2),
            "hedge_words": t.hedge_words,
            "placeholders": t.placeholders,
            "question_marks_written": t.question_marks,
            "question_marks_in_prior_message": 0,
            "window_switches_away": p.focus_switches,
            "paste_events": t.paste_events,
            "pasted_char_count": t.pasted_char_count,
            "surface": p.surface,
            "is_reply": p.is_reply,
            "prior_message_char_count": p.prior_message_char_count or 0,
            "current_message_char_count": max(
                0, t.chars_typed + t.pasted_char_count - t.chars_deleted
            ),
            "baseline_avg_pause_ms": self._baseline_pause_ms,
            "baseline_avg_deletion_rate": self._baseline_deletion_rate,
            "topics": sorted(t.topics),
        }
        if p.trigger == Trigger.SUBMIT:
            del self._totals[p.context_id]
        return payload
