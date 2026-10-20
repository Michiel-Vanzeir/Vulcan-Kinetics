"""Tests for expertise_filter. Run with: pytest Neo4J-backend/test_expertise_filter.py"""
from __future__ import annotations

import time

import pytest

from expertise_filter import (
    ExpertiseFilter,
    PersonStore,
    SignalPayload,
    build_filter,
    direction,
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


def test_repeated_snapshots_cannot_create_multiple_answer_contexts():
    flt = build_filter()
    now = int(time.time() * 1000)
    payload = _payload(ts=now, topics=["year_end_bonus"], is_reply=True,
                       prior_message_char_count=50, current_message_char_count=300,
                       chars_typed=300, fluency_run_seconds=30,
                       longest_fluency_run_seconds=30)
    for offset in range(20):
        flt.process({**payload, "ts": now + offset})
    entry = flt._store.get("emp_014")["topics"]["year_end_bonus"]
    assert entry["answering_count"] == 1
    assert entry["expertise_evidence"] <= 1.001
    assert not flt.is_expert("emp_014", "year_end_bonus")[0]
    before = flt._store.get("emp_014")
    flt.process(payload)
    assert flt._store.get("emp_014") == before


def test_equal_context_ids_from_different_employees_are_isolated():
    flt = build_filter()
    now = int(time.time() * 1000)
    flt.process(_payload(ts=now, user_id="first", topics=["notice_period"], chars_typed=10))
    flt.process(_payload(ts=now - 1, user_id="second", topics=["country_ES"], chars_typed=20))
    assert "country_ES" in flt._store.get("second")["topics"]
    assert "notice_period" not in flt._store.get("second")["topics"]


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
    assert "emp_014:ctx-later" in f._agg.pending_contexts

    # Follow-up payload for the SAME context now carries topics.
    out = f.process(_payload(
        ts=BASE_TS + 5000, context_id="ctx-later",
        topics=["bonus_pc200"],
        is_reply=True, prior_message_char_count=120,
        current_message_char_count=600,
        chars_typed=600, chars_deleted=10,
        fluency_run_seconds=25.0, longest_fluency_run_seconds=40.0,
    ))
    assert "emp_014:ctx-later" not in f._agg.pending_contexts
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


# ---------------------------------------------------------------------------
# Interaction emission (participants supplied -> network edges)
# ---------------------------------------------------------------------------
def _senior_filter():
    directory = {"emp_014": {"job_title": "Payroll consultant",
                             "seniority": "senior", "department": "Payroll BE"}}
    return ExpertiseFilter(PersonStore(":memory:"), directory)


def _warm_up_expertise(f, user="emp_014", topic="bonus_pc200", times=2):
    """Push expertise above the is_expert threshold so a single live payload tests emission."""
    now_ms = int(time.time() * 1000)
    for i in range(times):
        f.process(_payload(
            user_id=user,
            context_id=f"warmup-{i}",
            ts=now_ms + i * 1000,
            trigger="punctuation",
            topics=[topic],
            is_reply=True,
            prior_message_char_count=120,
            current_message_char_count=600,
            chars_typed=600, chars_deleted=10,
            fluency_run_seconds=25.0, longest_fluency_run_seconds=40.0,
        ))


def test_answering_with_participants_emits_compose_answer_edges():
    f = _senior_filter()
    _warm_up_expertise(f)
    live_ts = int(time.time() * 1000) + 10_000
    out = f.process(_payload(
        context_id="live-ctx",
        ts=live_ts,
        topics=["bonus_pc200"],
        is_reply=True,
        prior_message_char_count=120,
        current_message_char_count=600,
        chars_typed=600, chars_deleted=10,
        fluency_run_seconds=25.0, longest_fluency_run_seconds=40.0,
    ), participants=["emp_112"])
    assert out is not None
    assert out["tip"] is not None
    assert out["tip"]["recipient"] == "emp_112"
    edges = out["interactions"]
    assert len(edges) == 1
    edge = edges[0]
    assert edge["giver"] == "emp_014"
    assert edge["receiver"] == "emp_112"
    assert edge["kind"] == "compose_answer"
    assert edge["topics"] == ["bonus_pc200"]
    assert edge["weight"] > 0


def test_asking_with_participants_emits_asked_about_edges():
    f = build_filter()
    out = f.process(_payload(
        user_id="emp_112",
        context_id="ctx-ask",
        trigger="hedge",
        topics=["bonus_pc200"],
        is_reply=False,
        current_message_char_count=120,
        chars_typed=160, chars_deleted=40,
        hedge_words=4, placeholders=2, question_marks_written=3,
        long_pauses=5, window_switches_away=4,
    ), participants=["emp_014", "emp_021"])
    assert out is not None
    assert out["tip"] is None  # asker is not an expert
    edges = out["interactions"]
    assert len(edges) == 2
    kinds = {e["kind"] for e in edges}
    assert kinds == {"asked_about"}
    assert {e["giver"] for e in edges} == {"emp_014", "emp_021"}
    for e in edges:
        assert e["receiver"] == "emp_112"


def test_no_participants_means_no_interactions_but_tip_still_fires():
    f = _senior_filter()
    _warm_up_expertise(f)
    live_ts = int(time.time() * 1000) + 10_000
    out = f.process(_payload(
        context_id="live-ctx",
        ts=live_ts,
        topics=["bonus_pc200"],
        is_reply=True,
        prior_message_char_count=120,
        current_message_char_count=600,
        chars_typed=600, chars_deleted=10,
        fluency_run_seconds=25.0, longest_fluency_run_seconds=40.0,
    ))
    assert out is not None
    assert out["interactions"] == []
    assert out["tip"] is not None
    assert out["tip"]["recipient"] is None


# ---------------------------------------------------------------------------
# Doubt push: upstream signal that "this person is having doubts"
# ---------------------------------------------------------------------------
def _hesitant_payload(**overrides):
    base = dict(
        user_id="emp_112",
        context_id="ctx-doubt",
        trigger="hedge",
        is_reply=False,
        current_message_char_count=120,
        chars_typed=160, chars_deleted=40,
        hedge_words=4, placeholders=2, question_marks_written=3,
        long_pauses=5, window_switches_away=4,
        deletion_bursts=3, rewrite_loops=2,
    )
    base.update(overrides)
    return _payload(**base)


def test_hesitant_payload_emits_doubt_alert():
    f = build_filter()
    out = f.process(_hesitant_payload(topics=["bonus_pc200"]))
    assert out is not None
    assert out["doubt_alert"] is not None
    alert = out["doubt_alert"]
    assert alert["user_id"] == "emp_112"
    assert alert["context_id"] == "ctx-doubt"
    assert alert["direction"] == "asking"
    assert alert["doubt"] > 0.5
    assert alert["topics"] == ["bonus_pc200"]
    assert len(alert["reasons"]) > 0


def test_confident_writer_does_not_trigger_doubt_alert():
    f = _senior_filter()
    out = f.process(_payload(
        topics=["bonus_pc200"],
        is_reply=True,
        prior_message_char_count=120,
        current_message_char_count=600,
        chars_typed=600, chars_deleted=10,
        fluency_run_seconds=25.0, longest_fluency_run_seconds=40.0,
    ))
    # No tip (one payload isn't enough on its own), no edges, no alert.
    assert out is None


def test_doubt_alert_fires_even_without_topics():
    f = build_filter()
    out = f.process(_hesitant_payload(topics=[]))
    assert out is not None
    assert out["tip"] is None
    assert out["interactions"] == []
    assert out["doubt_alert"] is not None
    assert out["doubt_alert"]["topics"] == []


def test_doubt_alert_respects_cooldown_per_context():
    f = build_filter()
    first = f.process(_hesitant_payload(ts=BASE_TS, topics=["bonus_pc200"]))
    assert first and first["doubt_alert"] is not None

    # Second payload for the same context, right after - cooldown blocks it.
    second = f.process(_hesitant_payload(ts=BASE_TS + 1_000,
                                         topics=["bonus_pc200"]))
    assert second is None or second.get("doubt_alert") is None

    # Well past the cooldown - alert fires again.
    third = f.process(_hesitant_payload(ts=BASE_TS + 60_000,
                                        topics=["bonus_pc200"]))
    assert third and third["doubt_alert"] is not None


def test_double_question_mark_fires_doubt_alert_but_single_does_not():
    single = build_filter().process(_payload(topics=["notice_period"], question_marks_written=1))
    assert single is None
    double = build_filter().process(_payload(topics=["notice_period"], question_marks_written=2))
    assert double["doubt_alert"] is not None


def test_one_pause_or_one_hedge_alone_does_not_fire():
    for signal in ({"pauses": 1}, {"hedge_words": 1}):
        assert build_filter().process(_payload(topics=["notice_period"], **signal)) is None
    out = build_filter().process(_payload(topics=["notice_period"], pauses=1, hedge_words=1))
    assert out["doubt_alert"] is not None


def test_pauses_and_deletions_alone_do_not_fire():
    out = build_filter().process(_payload(
        topics=["notice_period"], pauses=3, long_pauses=2, deletion_bursts=1, rewrite_loops=1))
    assert out is None or out["doubt_alert"] is None


def test_demo_script_fires_only_on_the_hedge():
    """Pause, type "24 week", delete it, pause, then "I think around"."""
    f = build_filter()
    hesitation = {"pauses": 2, "long_pauses": 1, "deletion_bursts": 1, "rewrite_loops": 1,
                  "topics": ["PC_200", "notice_period"]}
    before = f.process(_payload(ts=BASE_TS, **hesitation))
    assert before is None or before["doubt_alert"] is None
    after = f.process(_payload(ts=BASE_TS + 1_000, hedge_words=1, **hesitation))
    assert after["doubt_alert"] is not None


def test_doubt_push_callback_is_invoked():
    received = []
    f = ExpertiseFilter(PersonStore(":memory:"), on_doubt_push=received.append)
    f.process(_hesitant_payload(topics=["bonus_pc200"]))
    assert len(received) == 1
    assert received[0]["user_id"] == "emp_112"


def test_pasted_answering_does_not_emit_compose_answer_edge():
    f = build_filter()
    out = f.process(_payload(
        topics=["bonus_pc200"],
        is_reply=True,
        prior_message_char_count=50,
        current_message_char_count=500,
        chars_typed=200, chars_deleted=4,
        fluency_run_seconds=30.0, longest_fluency_run_seconds=30.0,
        pasted_char_count=450,
    ), participants=["emp_112"])
    # Either no routable output at all, or an output with no answering edge.
    edges = (out or {}).get("interactions", [])
    assert all(e["kind"] != "compose_answer" for e in edges)
