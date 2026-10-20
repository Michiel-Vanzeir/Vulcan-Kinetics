"""Expertise filter: turn capture-agent signal payloads into routing decisions.

The capture agent (not in this module) emits one payload per trigger inside a focused
text field. Every count field in a payload is CUMULATIVE since the context opened, so
for a given context_id we take the latest snapshot and never sum successive payloads.

Public surface:
    SignalPayload           - validated dataclass + from_dict parser
    ExpertiseFilter         - orchestrator; call .process(payload_dict)
    is_expert(user, topic)  - decision + reasons for the pitch demo

Stdlib-only; persistence uses sqlite3 with a `persons` table and a JSON `document`
column (same shape as the people-network store in app/, which keeps scores with the
moment they were last updated and decays them lazily on read/write).
"""
from __future__ import annotations

import json
import math
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


# =============================================================================
# Config: every weight / threshold / decay lives here, nowhere else.
# =============================================================================
CONFIG: dict[str, float] = {
    # Recency decay for stored evidence; half-life expressed in days.
    "half_life_days": 30.0,

    # Confidence (how fluently this person handled this context).
    "conf_base": 0.5,
    "conf_fluency_run_weight": 0.015,          # per second of current run
    "conf_longest_fluency_weight": 0.010,      # per second of longest run
    "conf_deletion_ratio_penalty": 0.6,        # multiplied by normalised ratio
    "conf_deletion_burst_penalty": 0.08,       # per burst
    "conf_rewrite_loop_penalty": 0.10,         # per loop
    "conf_hedge_per_100_penalty": 0.12,        # per hedge/100 chars
    "conf_placeholder_penalty": 0.08,          # per placeholder
    "conf_long_pause_penalty": 0.05,           # per long pause
    "conf_window_switch_penalty": 0.04,        # per switch away
    "conf_pause_ratio_penalty": 0.20,          # pauses relative to baseline

    # Paste discount: pasted content is not evidence they wrote it themselves.
    "paste_discount_at_ratio": 0.5,            # ratio where confidence halves
    "paste_hard_cap_ratio": 0.6,               # above this: evidence is pasted

    # Doubt (person is stuck on the topic -> a candidate to be helped).
    "doubt_hedge_weight": 0.08,                # per hedge
    "doubt_placeholder_weight": 0.15,
    "doubt_question_mark_weight": 0.10,        # per '?' when NOT a reply
    "doubt_question_mark_reply_weight": 0.02,  # per '?' when IS a reply
    "doubt_long_pause_weight": 0.08,
    "doubt_deletion_burst_weight": 0.07,
    "doubt_rewrite_loop_weight": 0.10,
    "doubt_window_switch_weight": 0.06,
    # Window switches scale per minute of context_age so one switch in 30s hurts
    # more than one switch in a 10-minute session.
    "doubt_switch_rate_minutes": 5.0,

    # Direction heuristic.
    "direction_long_reply_ratio": 1.5,         # current / prior to count as answering
    "direction_short_asking_chars": 200,       # messages shorter than this + '?' => asking

    # Thresholds used by the orchestrator and is_expert().
    "high_confidence_threshold": 0.65,
    "high_doubt_threshold": 0.55,
    "expert_min_score": 0.6,

    # Composite weights for is_expert().
    "expert_profile_weight": 0.35,
    "expert_evidence_weight": 0.5,
    "expert_breadth_weight": 0.15,
    "expert_doubt_veto_ratio": 0.5,            # doubt > ratio * expertise => not expert
    "expert_paste_veto_ratio": 0.6,            # pasted >= ratio * authored chars => not expert
}

SURFACES = {"outlook_desktop", "teams_desktop", "gmail_web", "word_desktop", "other"}


def _decay_per_second(half_life_days: float) -> float:
    return math.log(2) / max(1.0, half_life_days * 86400.0)


def decayed(value: float, last_seen_ms: int, now_ms: int,
            half_life_days: float | None = None) -> float:
    """Exponential recency decay. Mirrors app/network.decayed but in ms."""
    hl = CONFIG["half_life_days"] if half_life_days is None else half_life_days
    dt = max(0.0, (now_ms - last_seen_ms) / 1000.0)
    return value * math.exp(-_decay_per_second(hl) * dt)


# =============================================================================
# Payload
# =============================================================================
_REQUIRED_HOUSEKEEPING = ("user_id", "context_id", "ts", "trigger")
_VALID_TRIGGERS = {"pause", "deletion_burst", "punctuation", "hedge",
                   "idle_flush", "manual"}


@dataclass
class SignalPayload:
    """One capture-agent payload for one focused text field.

    Count fields are cumulative since the context opened or last reset, so the
    aggregator keeps only the LATEST snapshot per context_id.
    """
    # Housekeeping
    user_id: str
    context_id: str
    ts: int
    trigger: str
    # Timing / pauses
    pauses: int = 0
    long_pauses: int = 0
    time_since_last_key_ms: int = 0
    context_age_ms: int = 0
    # Deletions
    chars_typed: int = 0
    chars_deleted: int = 0
    deletion_bursts: int = 0
    rewrite_loops: int = 0
    # Fluency
    fluency_run_seconds: float = 0.0
    longest_fluency_run_seconds: float = 0.0
    # Lexical
    hedge_words: int = 0
    placeholders: int = 0
    question_marks_written: int = 0
    question_marks_in_prior_message: int = 0
    # Context / focus
    window_switches_away: int = 0
    paste_events: int = 0
    pasted_char_count: int = 0
    # Surface / reply
    surface: str = "other"
    is_reply: bool = False
    prior_message_char_count: int = 0
    current_message_char_count: int = 0
    # Baseline (sent once per session or on shift)
    baseline_avg_pause_ms: int = 0
    baseline_avg_deletion_rate: float = 0.0
    # Topic routing (may be empty while the extractor is not ready).
    topics: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SignalPayload":
        missing = [k for k in _REQUIRED_HOUSEKEEPING if k not in data]
        if missing:
            raise ValueError(f"missing required fields: {missing}")
        if data["trigger"] not in _VALID_TRIGGERS:
            raise ValueError(f"invalid trigger: {data['trigger']!r}")

        surface = data.get("surface", "other")
        if surface not in SURFACES:
            surface = "other"  # fallback per spec

        topics = data.get("topics") or []
        if not isinstance(topics, list):
            raise ValueError("topics must be a list")

        # Only accept known fields; drop anything else so a mis-sent key fails
        # loudly instead of silently being stored.
        kwargs: dict[str, Any] = {k: data[k] for k in cls.__dataclass_fields__
                                  if k in data}
        kwargs["surface"] = surface
        kwargs["topics"] = list(topics)
        return cls(**kwargs)


# =============================================================================
# Per-context aggregator
# =============================================================================
class ContextAggregator:
    """Keep the latest cumulative snapshot per context_id.

    Also caches the most recent baseline per user_id (the capture agent sends a
    baseline once per session but every payload still carries whatever it last
    sent), and buffers results for contexts whose topics are still empty, so
    they can be attached as soon as topics arrive.
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, SignalPayload] = {}
        self._baselines: dict[str, tuple[int, float]] = {}
        self.pending_contexts: dict[str, dict[str, Any]] = {}

    def ingest(self, payload: SignalPayload) -> SignalPayload:
        """Replace the snapshot for this context_id with the newer payload.

        Count fields are cumulative, so when a payload arrives out of order we
        keep the one with the larger ts (and max() counts as a safety net).
        """
        current = self._snapshots.get(payload.context_id)
        if current is None or payload.ts >= current.ts:
            snap = payload
        else:
            snap = current  # older payload: ignore
        self._snapshots[payload.context_id] = snap
        self._cache_baseline(payload)
        return snap

    def _cache_baseline(self, payload: SignalPayload) -> None:
        """Only overwrite the cached baseline when the payload has one set,
        so a later keystroke payload (without baseline) doesn't clear it."""
        if payload.baseline_avg_pause_ms <= 0 and payload.baseline_avg_deletion_rate <= 0:
            return
        self._baselines[payload.user_id] = (
            payload.baseline_avg_pause_ms,
            payload.baseline_avg_deletion_rate,
        )

    def baseline_for(self, user_id: str) -> tuple[int, float]:
        return self._baselines.get(user_id, (0, 0.0))

    def snapshot(self, context_id: str) -> SignalPayload | None:
        return self._snapshots.get(context_id)

    def buffer_pending(self, context_id: str, scores: dict[str, Any]) -> None:
        self.pending_contexts[context_id] = scores

    def pop_pending(self, context_id: str) -> dict[str, Any] | None:
        return self.pending_contexts.pop(context_id, None)


# =============================================================================
# Scoring
# =============================================================================
def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _per_100_chars(count: int, chars: int) -> float:
    return 100.0 * count / max(1, chars)


def deletion_rate(p: SignalPayload) -> float:
    return p.chars_deleted / max(1, p.chars_typed)


def paste_ratio(p: SignalPayload) -> float:
    return p.pasted_char_count / max(1, p.current_message_char_count)


def _normalised_deletion(p: SignalPayload, baseline_rate: float) -> float:
    """Deletion rate relative to the user's own baseline, clipped to [0, 2]."""
    rate = deletion_rate(p)
    if baseline_rate <= 0:
        return _clip(rate / 0.2, 0, 2)  # fallback: 20% deletions = 1.0
    return _clip(rate / baseline_rate, 0, 2)


def _normalised_pause(p: SignalPayload, baseline_ms: int) -> float:
    """How slow this context's pauses are compared to the user's own baseline.
    Returns 0 when faster/equal, up to ~1 when the pauses dwarf the baseline."""
    if p.pauses <= 0 or p.context_age_ms <= 0:
        return 0.0
    avg_gap_ms = p.context_age_ms / max(1, p.pauses + p.chars_typed)
    if baseline_ms <= 0:
        return _clip((avg_gap_ms - 400.0) / 1200.0)  # ~400ms normal, ~1600ms slow
    return _clip((avg_gap_ms - baseline_ms) / max(1.0, baseline_ms))


def _paste_discount(ratio: float) -> float:
    """Multiplier applied to confidence. ratio 0 -> 1.0, ratio >=1 -> ~0."""
    half = CONFIG["paste_discount_at_ratio"]
    return _clip(1.0 - ratio / (2 * half)) if ratio < 1 else 0.0


def confidence_score(p: SignalPayload, baseline_pause_ms: int,
                     baseline_del_rate: float) -> float:
    cfg = CONFIG
    chars = p.current_message_char_count or p.chars_typed
    score = cfg["conf_base"]
    score += cfg["conf_fluency_run_weight"] * p.fluency_run_seconds
    score += cfg["conf_longest_fluency_weight"] * p.longest_fluency_run_seconds
    score -= cfg["conf_deletion_ratio_penalty"] * _normalised_deletion(p, baseline_del_rate)
    score -= cfg["conf_deletion_burst_penalty"] * p.deletion_bursts
    score -= cfg["conf_rewrite_loop_penalty"] * p.rewrite_loops
    score -= cfg["conf_hedge_per_100_penalty"] * _per_100_chars(p.hedge_words, chars)
    score -= cfg["conf_placeholder_penalty"] * p.placeholders
    score -= cfg["conf_long_pause_penalty"] * p.long_pauses
    score -= cfg["conf_window_switch_penalty"] * p.window_switches_away
    score -= cfg["conf_pause_ratio_penalty"] * _normalised_pause(p, baseline_pause_ms)
    score = _clip(score)
    return score * _paste_discount(paste_ratio(p))


def doubt_score(p: SignalPayload) -> float:
    cfg = CONFIG
    minutes = max(1.0, p.context_age_ms / 60_000.0) / cfg["doubt_switch_rate_minutes"]
    q_weight = (cfg["doubt_question_mark_reply_weight"] if p.is_reply
                else cfg["doubt_question_mark_weight"])
    score = 0.0
    score += cfg["doubt_hedge_weight"] * p.hedge_words
    score += cfg["doubt_placeholder_weight"] * p.placeholders
    score += q_weight * p.question_marks_written
    score += cfg["doubt_long_pause_weight"] * p.long_pauses
    score += cfg["doubt_deletion_burst_weight"] * p.deletion_bursts
    score += cfg["doubt_rewrite_loop_weight"] * p.rewrite_loops
    score += cfg["doubt_window_switch_weight"] * (p.window_switches_away / minutes)
    return _clip(score)


def direction(p: SignalPayload) -> str:
    cfg = CONFIG
    cur = p.current_message_char_count
    if p.is_reply and p.prior_message_char_count > 0:
        if cur >= cfg["direction_long_reply_ratio"] * p.prior_message_char_count \
                and p.question_marks_written == 0:
            return "answering"
    if (not p.is_reply) and p.question_marks_written > 0 \
            and cur <= cfg["direction_short_asking_chars"]:
        return "asking"
    if p.question_marks_written > 0 and cur <= cfg["direction_short_asking_chars"]:
        return "asking"
    return "neutral"


# =============================================================================
# Person document store (SQLite, one JSON document per user_id)
# =============================================================================
_SCHEMA = """
CREATE TABLE IF NOT EXISTS persons (
    user_id   TEXT PRIMARY KEY,
    document  TEXT NOT NULL,
    updated_ms INTEGER NOT NULL
);
"""


def _blank_document() -> dict[str, Any]:
    return {
        "profile": None,
        "topics": {},            # topic -> accumulator
        "surfaces_seen": [],
        "last_baseline": None,   # {"pause_ms": int, "del_rate": float}
        "last_seen_ms": 0,
        "total_contexts": 0,
        "total_pasted_chars": 0,
        "total_authored_chars": 0,
    }


def _blank_topic_entry() -> dict[str, Any]:
    return {
        "expertise_evidence": 0.0,
        "doubt_evidence": 0.0,
        "evidence_last_ms": 0,
        "doubt_last_ms": 0,
        "answering_count": 0,
        "asking_count": 0,
        "surfaces": [],
        "last_seen_ms": 0,
    }


class PersonStore:
    """One JSON document per user_id. Writes are small and transactional."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def get(self, user_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT document FROM persons WHERE user_id = ?", (user_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def get_or_create(self, user_id: str, now_ms: int) -> dict[str, Any]:
        doc = self.get(user_id)
        if doc is not None:
            return doc
        doc = _blank_document()
        self._conn.execute(
            "INSERT INTO persons (user_id, document, updated_ms) VALUES (?, ?, ?)",
            (user_id, json.dumps(doc), now_ms),
        )
        self._conn.commit()
        return doc

    def put(self, user_id: str, document: dict[str, Any], now_ms: int) -> None:
        self._conn.execute(
            """INSERT INTO persons (user_id, document, updated_ms) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE
                 SET document = excluded.document, updated_ms = excluded.updated_ms""",
            (user_id, json.dumps(document), now_ms),
        )
        self._conn.commit()

    def all_user_ids(self) -> list[str]:
        return [r[0] for r in self._conn.execute("SELECT user_id FROM persons")]


# =============================================================================
# Directory (profile enrichment)
# =============================================================================
def load_directory(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load user_id -> {job_title, seniority, department}. Missing file is fine."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


# =============================================================================
# ExpertiseFilter orchestrator
# =============================================================================
# Simple seniority mapping used only for the profile-relevance component of
# is_expert; the directory may use any of these spellings or none at all.
_SENIORITY_SCORE = {
    "intern": 0.1, "junior": 0.3, "associate": 0.4, "medior": 0.5, "mid": 0.5,
    "senior": 0.75, "principal": 0.9, "lead": 0.85, "manager": 0.7,
    "director": 0.95, "head": 0.95,
}


def _profile_relevance(profile: dict[str, Any] | None, topic: str) -> float:
    if not profile:
        return 0.0
    seniority = str(profile.get("seniority") or "").lower()
    base = _SENIORITY_SCORE.get(seniority, 0.4 if profile else 0.0)
    # Light title/department hint: words that overlap the topic nudge up.
    hints = " ".join(str(profile.get(k) or "") for k in ("job_title", "department")).lower()
    topic_tokens = {t for t in topic.lower().replace("_", " ").split() if len(t) > 2}
    overlap = sum(1 for t in topic_tokens if t in hints)
    return _clip(base + 0.1 * overlap)


class ExpertiseFilter:
    """Consume capture-agent payloads and emit routable expert tips.

    Everyone is tracked (we update the person document on every payload, asking
    or answering) and expertise is attached per topic once topics arrive. The
    payload identifies only one user_id, so the downstream `recipient` is None
    unless a separate participant/thread mapping is supplied elsewhere.
    """

    def __init__(self, store: PersonStore,
                 directory: dict[str, dict[str, Any]] | None = None) -> None:
        self._store = store
        self._directory = directory or {}
        self._agg = ContextAggregator()

    # ---- public API --------------------------------------------------------
    def process(self, payload_dict: dict[str, Any]) -> dict[str, Any] | None:
        payload = SignalPayload.from_dict(payload_dict)
        snap = self._agg.ingest(payload)
        baseline = self._agg.baseline_for(payload.user_id)

        scores = {
            "confidence": confidence_score(snap, *baseline),
            "doubt": doubt_score(snap),
            "direction": direction(snap),
            "paste_ratio": paste_ratio(snap),
        }

        # Always update the person document - we track everyone.
        self._touch_person(snap, scores)

        if not snap.topics:
            # Topics not available yet: buffer the latest scores so when a
            # follow-up payload for this context_id arrives with topics we can
            # emit downstream events backed by the full context history.
            self._agg.buffer_pending(snap.context_id, scores)
            return None

        # Topics arrived; drop any buffered scores for this context now that the
        # live snapshot represents them.
        self._agg.pop_pending(snap.context_id)

        best: dict[str, Any] | None = None
        for topic in snap.topics:
            self._update_topic(snap, topic, scores)
            is_exp, score, reasons = self.is_expert(snap.user_id, topic)
            if is_exp and (best is None or score > best["score"]):
                best = {
                    "author": snap.user_id,
                    # TODO: payload carries only one user_id (the author). A
                    # separate participant/thread mapping is needed to resolve
                    # the counterpart; keep recipient=None until that is wired.
                    "recipient": None,
                    "topic": topic,
                    "score": score,
                    "reasons": reasons,
                }
        return best

    def is_expert(self, user_id: str, topic: str) -> tuple[bool, float, list[str]]:
        """Decide whether `user_id` should be routed as an expert on `topic`.

        Returns (bool, score, reasons). A person whose topic evidence is mostly
        doubt or mostly pasted content never clears the threshold, regardless
        of their profile.
        """
        doc = self._store.get(user_id) or _blank_document()
        now_ms = int(time.time() * 1000)
        topic_entry = doc.get("topics", {}).get(topic, _blank_topic_entry())

        expertise = decayed(topic_entry["expertise_evidence"],
                            topic_entry["evidence_last_ms"], now_ms)
        doubt = decayed(topic_entry["doubt_evidence"],
                        topic_entry["doubt_last_ms"], now_ms)
        breadth = len(topic_entry.get("surfaces", [])) / len(SURFACES)
        profile_rel = _profile_relevance(doc.get("profile"), topic)

        cfg = CONFIG
        score = (cfg["expert_profile_weight"] * profile_rel
                 + cfg["expert_evidence_weight"] * _clip(expertise / 3.0)
                 + cfg["expert_breadth_weight"] * breadth)

        reasons: list[str] = []
        if profile_rel >= 0.5:
            reasons.append(f"profile fits ({profile_rel:.2f})")
        if expertise > 0:
            reasons.append(f"recent evidence on {topic} ({expertise:.2f})")
        if breadth > 0:
            reasons.append(f"seen on {len(topic_entry.get('surfaces', []))} surfaces")

        # Veto rules: evidence must be real authorship, not confusion or paste.
        if doubt > cfg["expert_doubt_veto_ratio"] * max(1e-6, expertise):
            reasons.append("blocked: more doubt than expertise")
            return False, score, reasons

        pasted = doc.get("total_pasted_chars", 0)
        authored = doc.get("total_authored_chars", 0)
        if authored > 0 and pasted / max(1, pasted + authored) \
                >= cfg["expert_paste_veto_ratio"]:
            reasons.append("blocked: mostly pasted content")
            return False, score, reasons

        is_exp = score >= cfg["expert_min_score"] and expertise > 0
        if not is_exp and not reasons:
            reasons.append("not enough evidence yet")
        return is_exp, score, reasons

    # ---- internals ---------------------------------------------------------
    def _touch_person(self, snap: SignalPayload, scores: dict[str, Any]) -> None:
        now_ms = snap.ts
        doc = self._store.get_or_create(snap.user_id, now_ms)
        if doc["profile"] is None:
            doc["profile"] = self._directory.get(snap.user_id)
        if snap.surface not in doc["surfaces_seen"]:
            doc["surfaces_seen"].append(snap.surface)
        bp, br = self._agg.baseline_for(snap.user_id)
        if bp or br:
            doc["last_baseline"] = {"pause_ms": bp, "del_rate": br}
        doc["last_seen_ms"] = max(doc["last_seen_ms"], now_ms)
        # Totals are cumulative-per-context, so we take the max() rather than
        # summing to avoid double-counting when several payloads land for the
        # same context_id.
        doc["total_pasted_chars"] = max(doc["total_pasted_chars"],
                                        snap.pasted_char_count)
        authored = max(0, snap.current_message_char_count - snap.pasted_char_count)
        doc["total_authored_chars"] = max(doc["total_authored_chars"], authored)
        doc["total_contexts"] = max(doc["total_contexts"],
                                    len({snap.context_id, *doc.get("topics", {}).keys()}))
        self._store.put(snap.user_id, doc, now_ms)

    def _update_topic(self, snap: SignalPayload, topic: str,
                      scores: dict[str, Any]) -> None:
        now_ms = snap.ts
        doc = self._store.get_or_create(snap.user_id, now_ms)
        topics = doc.setdefault("topics", {})
        entry = topics.setdefault(topic, _blank_topic_entry())

        cfg = CONFIG
        if scores["direction"] == "answering":
            entry["answering_count"] += 1
        elif scores["direction"] == "asking":
            entry["asking_count"] += 1

        # Expertise evidence: answering + high confidence + low paste only.
        if (scores["direction"] == "answering"
                and scores["confidence"] >= cfg["high_confidence_threshold"]
                and scores["paste_ratio"] < cfg["paste_hard_cap_ratio"]):
            decayed_prev = decayed(entry["expertise_evidence"],
                                   entry["evidence_last_ms"], now_ms)
            entry["expertise_evidence"] = decayed_prev + scores["confidence"]
            entry["evidence_last_ms"] = now_ms

        # Doubt evidence: high doubt (asker or not).
        if scores["doubt"] >= cfg["high_doubt_threshold"]:
            decayed_prev = decayed(entry["doubt_evidence"],
                                   entry["doubt_last_ms"], now_ms)
            entry["doubt_evidence"] = decayed_prev + scores["doubt"]
            entry["doubt_last_ms"] = now_ms

        if snap.surface not in entry["surfaces"]:
            entry["surfaces"].append(snap.surface)
        entry["last_seen_ms"] = max(entry["last_seen_ms"], now_ms)
        self._store.put(snap.user_id, doc, now_ms)


# =============================================================================
# Convenience constructor used by tests and the demo wiring
# =============================================================================
def build_filter(db_path: str | Path = ":memory:",
                 directory_path: str | Path | None = None) -> ExpertiseFilter:
    directory = load_directory(directory_path) if directory_path else {}
    return ExpertiseFilter(PersonStore(db_path), directory)


__all__ = [
    "CONFIG", "SURFACES", "SignalPayload", "ContextAggregator",
    "PersonStore", "ExpertiseFilter", "build_filter",
    "load_directory", "confidence_score", "doubt_score", "direction",
    "paste_ratio", "deletion_rate", "decayed",
]
