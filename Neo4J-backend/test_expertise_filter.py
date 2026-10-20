"""Tests for expertise_filter.

Run with: pytest Neo4J-backend/test_expertise_filter.py
"""
from __future__ import annotations

import copy
import time

import pytest

from expertise_filter import (
    CONFIG,
    ExpertiseFilter,
    PersonStore,
    SignalPayload,
    build_filter,
    confidence_score,
    direction,
    doubt_score,
)


BASE_TS = 1_760_000_000_000  # fixed Unix ms, so decay is deterministic in tests


def _payload(**overrides):
    """Minimum valid payload; override anything the test cares about."""
    base = {
        "user_id": "emp_014",
        "context_id": "ctx-1",
        "ts": BASE_TS,
        "trigger": "pause",
        "surface": "outlook_desktop",
        "is_reply": False,
        "topics": [],
        "chars_typed": 0,
        "chars_deleted": 0,
        "current_message_char_count": 0,
        "prior_message_char_count": 0,
        "pasted_char_count": 0,
        "baseline_avg_pause_ms": 500,
        "baseline_avg_deletion_rate": 0.05,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. New user created on first payload
# ---------------------------------------------------------------------------
def test_new_user_document_created_on_first_payload():
    f = build_filter()
    assert f._store.get("emp_014") is None
    f.process(_payload(topics=["bonus_pc200"], current_message_char_count=120))
    doc = f._store.get("emp_014")
    assert doc is not None
    assert doc["profile"] is None  # no directory passed in
    assert "outlook_desktop" in doc["surfaces_seen"]


def test_profile_enriched_from_directory():
    directory = {"emp_014": {"job_title": "Payroll consultant",
                             "seniority": "senior", "department": "Payroll BE"}}
    store = PersonStore(":memory:")
    f = ExpertiseFilter(store, directory)
    f.process(_payload(topics=["bonus_pc200"], current_message_char_count=50))
    assert f._store.get("emp_014")["profile"]["seniority"] == "senior"


# ---------------------------------------------------------------------------
# 2. Cumulative counts: later payloads of same context_id don't double-sum
# ---------------------------------------------------------------------------
def test_cumulative_counts_are_not_summed_across_payloads():
    f = build_filter()
    # First payload: already carries full history for the context.
    f.process(_payload(topics=["bonus_pc200"], current_message_char_count=100,
                       pasted_char_count=20, chars_typed=80, chars_deleted=4))
    # Second payload for the SAME context, later timestamp: capture agent re-sends
    # cumulative values. We must take the latest snapshot, not add to the old one.
    f.process(_payload(ts=BASE_TS + 10_000, topics=["bonus_pc200"],
                       current_message_char_count=140, pasted_char_count=20,
                       chars_typed=120, chars_deleted=6))
    doc = f._store.get("emp_014")
    # Pasted total should equal the latest snapshot (20), not 20 + 20 = 40.
    assert doc["total_pasted_chars"] == 20
    # Authored total should equal latest authored chars (140 - 20 = 120).
    assert doc["total_authored_chars"] == 120


# ---------------------------------------------------------------------------
# 3. A fluent, low-deletion, answering senior => expert
# ---------------------------------------------------------------------------
def test_senior_answering_fluently_becomes_expert():
    directory = {"emp_014": {"job_title": "Payroll consultant",
                             "seniority": "senior", "department": "Payroll BE"}}
    f = ExpertiseFilter(PersonStore(":memory:"), directory)

    # Build authored history across a few answering contexts on the same topic.
    now_ms = int(time.time() * 1000)
    for i in range(3):
        f.process(_payload(
            ts=now_ms + i * 1000,
            context_id=f"ctx-{i}",
            trigger="punctuation",
            topics=["bonus_pc200"],
            is_reply=True,
            prior_message_char_count=120,
            current_message_char_count=600,          # long reply vs short prior
            chars_typed=600, chars_deleted=10,       # ~1.7% deletions
            fluency_run_seconds=25.0,
            longest_fluency_run_seconds=40.0,
            question_marks_written=0,
            hedge_words=0,
            placeholders=0,
            long_pauses=0,
            deletion_bursts=0,
            rewrite_loops=0,
            pasted_char_count=0,
            surface="outlook_desktop",
        ))

    is_exp, score, reasons = f.is_expert("emp_014", "bonus_pc200")
    assert is_exp, f"expected expert; got score={score} reasons={reasons}"
    assert any("evidence" in r for r in reasons)


def test_direction_classifies_long_reply_as_answering():
    snap = SignalPayload.from_dict(_payload(
        is_reply=True, prior_message_char_count=100,
        current_message_char_count=500, question_marks_written=0,
    ))
    assert direction(snap) == "answering"


# ---------------------------------------------------------------------------
# 4. An asker with hedges / '?' and high deletion => NOT expert, recorded as doubt
# ---------------------------------------------------------------------------
def test_hesitant_asker_is_not_expert_and_is_recorded_as_doubt():
    f = build_filter()
    f.process(_payload(
        user_id="emp_112",
        context_id="ctx-ask",
        trigger="hedge",
        topics=["bonus_pc200"],
        is_reply=False,
        current_message_char_count=120,
        chars_typed=160, chars_deleted=40,          # 25% deletions
        deletion_bursts=3,
        rewrite_loops=2,
        hedge_words=4,
        placeholders=2,
        question_marks_written=3,
        long_pauses=5,
        window_switches_away=4,
        fluency_run_seconds=1.0,
        longest_fluency_run_seconds=2.0,
        context_age_ms=120_000,
    ))
    is_exp, score, reasons = f.is_expert("emp_112", "bonus_pc200")
    assert not is_exp

    doc = f._store.get("emp_112")
    entry = doc["topics"]["bonus_pc200"]
    assert entry["doubt_evidence"] > 0
    assert entry["expertise_evidence"] == 0.0
    assert entry["asking_count"] >= 1


# ---------------------------------------------------------------------------
# 5. A mostly-pasted context does NOT raise expertise
# ---------------------------------------------------------------------------
def test_mostly_pasted_context_does_not_raise_expertise():
    directory = {"emp_045": {"job_title": "Legal counsel",
                             "seniority": "principal", "department": "Legal"}}
    f = ExpertiseFilter(PersonStore(":memory:"), directory)
    f.process(_payload(
        user_id="emp_045",
        topics=["policy_pto"],
        is_reply=True,
        prior_message_char_count=50,
        current_message_char_count=500,              # long reply
        chars_typed=200, chars_deleted=4,
        fluency_run_seconds=30.0, longest_fluency_run_seconds=30.0,
        pasted_char_count=450,                       # almost all pasted
    ))
    entry = f._store.get("emp_045")["topics"]["policy_pto"]
    assert entry["expertise_evidence"] == 0.0

    is_exp, _, reasons = f.is_expert("emp_045", "policy_pto")
    assert not is_exp
    assert any("paste" in r.lower() or "evidence" in r.lower() for r in reasons)


# ---------------------------------------------------------------------------
# 6. Empty-topics payload is buffered and resolved once topics arrive
# ---------------------------------------------------------------------------
def test_empty_topics_payload_is_buffered_and_resolved():
    f = build_filter()
    out = f.process(_payload(context_id="ctx-later", topics=[],
                             current_message_char_count=80, chars_typed=80))
    assert out is None
    assert "ctx-later" in f._agg.pending_contexts

    # Follow-up payload for the SAME context now carries topics.
    out = f.process(_payload(
        ts=BASE_TS + 5000, context_id="ctx-later",
        topics=["bonus_pc200"],
        is_reply=True, prior_message_char_count=120,
        current_message_char_count=600,
        chars_typed=600, chars_deleted=10,
        fluency_run_seconds=25.0, longest_fluency_run_seconds=40.0,
    ))
    assert "ctx-later" not in f._agg.pending_contexts
    # The person doc now has expertise accumulators on the topic.
    entry = f._store.get("emp_014")["topics"]["bonus_pc200"]
    assert entry["expertise_evidence"] >= 0.0  # feature path exercised


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def test_signal_payload_missing_required_field_raises():
    with pytest.raises(ValueError):
        SignalPayload.from_dict({"user_id": "x", "context_id": "y", "ts": 1})


def test_unknown_surface_falls_back_to_other():
    p = SignalPayload.from_dict(_payload(surface="slack_desktop"))
    assert p.surface == "other"


def test_invalid_trigger_raises():
    bad = _payload()
    bad["trigger"] = "typing"
    with pytest.raises(ValueError):
        SignalPayload.from_dict(bad)
