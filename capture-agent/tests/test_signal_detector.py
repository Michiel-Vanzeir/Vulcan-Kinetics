"""Tests for the signal detector, using synthetic event streams."""

import dataclasses
import json
import typing

import pytest

from conftest import BACKSPACE, Typist
from signal_detector import KeyKind, PlaceholderKind, SignalPayload, Trigger


def test_empty_context_emits_nothing(typist, detector):
    typist.focus_out()
    assert typist.payloads == []
    assert detector.tick() == []


def test_manual_trigger_on_empty_context_has_zero_counts(typist, detector):
    payload = detector.manual_trigger("c1")
    assert payload.trigger == Trigger.MANUAL
    assert payload.chars_typed == 0
    assert payload.hedge_words == 0
    assert payload.gap_before_trigger_ms is None


def test_manual_trigger_on_unknown_context_returns_none(detector):
    assert detector.manual_trigger("nope") is None


def test_pure_typing_emits_no_signals(typist):
    typist.type("the notice period in spain is one month")
    assert typist.payloads == []


def test_pause_trigger_on_next_key(typist):
    typist.type("hello")
    typist.wait(900)
    typist.type("w")
    [payload] = typist.payloads
    assert payload.trigger == Trigger.PAUSE
    assert payload.pause_count == 1
    assert payload.longest_pause_ms == 1000  # 900 ms wait + 100 ms key interval


def test_pause_trigger_from_tick_fires_once(typist):
    typist.type("hello")
    typist.wait(3000, tick_every_ms=100)
    typist.type("w")
    assert typist.triggers == [Trigger.PAUSE]
    assert typist.payloads[0].pause_count == 1


def test_long_pause_counted_once(typist):
    typist.type("hello")
    typist.wait(3000, tick_every_ms=100)
    typist.type("w")
    payload = typist.detector.manual_trigger("c1")
    total = sum(p.long_pause_count for p in typist.payloads) + payload.long_pause_count
    assert total == 1


def test_rewrite_loop(typist):
    typist.type("the bonsu" + BACKSPACE * 3 + "nus")
    payload = typist.detector.manual_trigger("c1")
    assert payload.rewrite_loops == 1


def test_short_gaps_are_not_pauses(typist):
    typist.type("hello", interval_ms=800)
    assert typist.payloads == []


def test_deletion_burst_trigger(typist):
    typist.type("notice perido")
    typist.type(BACKSPACE * 4, interval_ms=100)
    [payload] = typist.payloads
    assert payload.trigger == Trigger.DELETION_BURST
    assert payload.deletion_bursts == 1
    assert payload.backspaces == 4
    assert payload.longest_deletion_run == 4


def test_three_quick_backspaces_are_not_a_burst(typist):
    typist.type("notice" + BACKSPACE * 3)
    assert typist.payloads == []


def test_slow_backspaces_are_not_a_burst(typist):
    typist.type("notice")
    typist.type(BACKSPACE * 5, interval_ms=200)
    assert typist.payloads == []


def test_long_burst_counts_once(typist):
    typist.type("notice period")
    typist.type(BACKSPACE * 10, interval_ms=50)
    assert typist.triggers == [Trigger.DELETION_BURST]


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("I think ", "en"),
        ("i'm not sure ", "en"),
        ("I’m not sure ", "en"),
        ("the bonus is maybe ", "en"),
        ("TODO\n", "en"),
        ("dat is misschien ", "nl"),
        ("het is denk ik ", "nl"),
        ("Volgens mij ", "nl"),
        ("je pense ", "fr"),
        ("c'est peut-être ", "fr"),
        ("à peu près ", "fr"),
        ("is it maybe?", "en"),
    ],
)
def test_hedge_detection(typist, text, language):
    typist.type(text)
    hedge_payloads = [p for p in typist.payloads if p.hedge_words]
    assert len(hedge_payloads) == 1
    assert hedge_payloads[0].trigger == Trigger.HEDGE_WORD
    assert hedge_payloads[0].hedge_words_by_language == {language: 1}


@pytest.mark.parametrize("text", ["rethinking ", "maybeline ", "aroundabout ", "I thinks "])
def test_no_hedge_inside_other_words(typist, text):
    typist.type(text)
    assert all(p.hedge_words == 0 for p in typist.payloads)


def test_hedge_fires_only_when_word_is_completed(typist):
    typist.type("maybe")
    assert typist.payloads == []
    typist.type(" ")
    assert typist.triggers == [Trigger.HEDGE_WORD]


def test_corrected_hedge_does_not_count(typist):
    typist.type("maybf\bb")
    typist.type(" ")
    assert all(p.hedge_words == 0 for p in typist.payloads)


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("dear [name]", PlaceholderKind.BRACKET),
        ("for <client>", PlaceholderKind.ANGLE),
        ("amount xxx", PlaceholderKind.X_RUN),
        ("amount XXXX", PlaceholderKind.X_RUN),
        ("deadline ???", PlaceholderKind.QUESTION_RUN),
    ],
)
def test_placeholder_detection(typist, text, kind):
    typist.type(text)
    placeholder_payloads = [p for p in typist.payloads if p.placeholders]
    assert len(placeholder_payloads) == 1
    assert placeholder_payloads[0].trigger == Trigger.PLACEHOLDER
    assert placeholder_payloads[0].placeholders_by_kind == {kind: 1}


def test_trailing_ellipsis_after_long_pause(typist):
    typist.type("the rate for spain is...")
    typist.wait(2500, tick_every_ms=100)
    assert typist.triggers == [Trigger.PAUSE, Trigger.PLACEHOLDER]
    assert typist.payloads[1].placeholders_by_kind == {PlaceholderKind.TRAILING_ELLIPSIS: 1}


def test_trailing_ellipsis_without_long_pause_is_not_a_placeholder(typist):
    typist.type("well... ok")
    assert all(p.placeholders == 0 for p in typist.payloads)


def test_punctuation_trigger(typist):
    typist.type("The notice period is one month. ")
    [payload] = typist.payloads
    assert payload.trigger == Trigger.PUNCTUATION
    assert payload.sentence_ends == 1


def test_question_mark_triggers_immediately(typist):
    typist.type("Is it one month?")
    [payload] = typist.payloads
    assert payload.trigger == Trigger.PUNCTUATION
    assert payload.question_marks == 1


def test_password_field_is_hard_skipped(detector, clock):
    secret = Typist(detector, clock, context_id="pw")
    secret.focus_in(is_password_field=True)
    secret.type("maybe hunter2. ")
    secret.wait(3000, tick_every_ms=100)
    assert secret.payloads == []
    assert detector.manual_trigger("pw") is None
    assert detector.get_baseline("u_test") == {"avg_pause_ms": None, "avg_deletion_rate": None}


def test_password_skip_ends_at_focus_out(detector, clock):
    field = Typist(detector, clock, context_id="pw")
    field.focus_in(is_password_field=True)
    field.type("secret")
    field.focus_out()
    field.focus_in()
    field.type("maybe ")
    assert field.triggers == [Trigger.HEDGE_WORD]
    assert field.payloads[0].chars_typed == 6


def test_numbers_are_masked(typist):
    typist.type("the salary is 3000 euro")
    payload = typist.detector.manual_trigger("c1")
    assert payload.chars_typed == 23
    assert payload.content_chars == 19
    assert payload.masked_tokens == 1


def test_decimal_point_is_not_punctuation(typist):
    typist.type("rate 3.5 percent")
    assert typist.payloads == []


def test_period_after_number_still_ends_sentence(typist):
    typist.type("Paid 200. ")
    assert typist.triggers == [Trigger.PUNCTUATION]


def test_digit_runs_never_make_placeholders(typist):
    typist.type("code 1000 ")
    assert typist.payloads == []


def test_emails_are_masked(typist):
    typist.type("mail jan.maybe@sdworx.com today")
    assert typist.payloads == []
    payload = typist.detector.manual_trigger("c1")
    assert payload.chars_typed == 31
    assert payload.content_chars == len("mail  today")
    assert payload.masked_tokens == 1
    assert payload.hedge_words == 0
    assert payload.sentence_ends == 0


def test_paste_counts_only_as_paste(typist):
    typist.paste(500)
    payload = typist.detector.manual_trigger("c1")
    assert payload.paste_events == 1
    assert payload.pasted_char_count == 500
    assert payload.chars_typed == 0
    assert payload.content_chars == 0
    assert payload.fluency_run_seconds == 0
    assert payload.longest_fluency_run_seconds == 0


def test_paste_breaks_fluency_run(typist):
    typist.type("abcdefghij")
    typist.paste(300)
    typist.type("klm")
    payload = typist.detector.manual_trigger("c1")
    assert payload.fluency_run_seconds == pytest.approx(0.2)
    assert payload.longest_fluency_run_seconds == pytest.approx(0.9)


def test_fluency_run_ends_at_pause(typist):
    typist.type("abcdefghijk")
    typist.wait(1000)
    typist.type("lmn")
    [pause] = typist.payloads
    assert pause.longest_fluency_run_seconds == pytest.approx(1.0)
    assert typist.detector.manual_trigger("c1").fluency_run_seconds == pytest.approx(0.2)


def test_deletion_breaks_fluency_run(typist):
    typist.type("abcdef")
    typist.type(BACKSPACE)
    typist.type("gh")
    payload = typist.detector.manual_trigger("c1")
    assert payload.longest_fluency_run_seconds == pytest.approx(0.5)
    assert payload.fluency_run_seconds == pytest.approx(0.1)


def test_focus_switch_pauses_and_resumes(detector, clock):
    first = Typist(detector, clock, context_id="c1", surface="outlook_desktop")
    second = Typist(detector, clock, context_id="c2", surface="teams_desktop")
    first.focus_in()
    first.type("dear sarah")
    first.focus_out()
    second.focus_in()
    second.type("hi")
    clock.now_ms += 30_000
    second.focus_out()
    first.focus_in()
    first.type(" thanks")

    # 30 s spent in the other field is neither a pause nor an idle flush.
    assert first.payloads == []
    payload = detector.manual_trigger("c1")
    assert payload.chars_typed == len("dear sarah thanks")
    assert payload.focus_switches == 1
    assert payload.surface == "outlook_desktop"


def test_blurred_context_gets_no_tick_triggers(typist, detector):
    typist.type("hello")
    typist.focus_out()
    typist.wait(15_000, tick_every_ms=100)
    assert typist.payloads == []


def test_submit_flushes_and_resets(typist, detector):
    typist.type("sounds good")
    payload = typist.submit()
    assert payload.trigger == Trigger.SUBMIT
    assert payload.chars_typed == 11
    assert detector.manual_trigger("c1") is None


def test_idle_flush_after_ten_seconds(typist):
    typist.type("a" * 21, interval_ms=500)
    assert typist.triggers == [Trigger.IDLE_FLUSH]


def test_idle_flush_from_tick_needs_activity(typist):
    typist.wait(25_000, tick_every_ms=100)
    assert typist.payloads == []


def test_reply_metadata_is_passed_through(detector, clock):
    reply = Typist(detector, clock)
    reply.focus_in(is_reply=True, prior_message_char_count=320)
    payload = detector.manual_trigger("c1")
    assert payload.is_reply is True
    assert payload.prior_message_char_count == 320


def test_baseline_tracking(typist, detector):
    typist.type("one month notice. ", interval_ms=100)
    first = typist.payloads[-1]
    assert first.baseline_avg_pause_ms == pytest.approx(100)
    assert detector.get_baseline("u_test")["avg_pause_ms"] == pytest.approx(100)

    typist.type("two weeks notice. ", interval_ms=110)
    assert typist.payloads[-1].baseline_avg_pause_ms is None  # shift under 20%

    already_sent = len(typist.payloads)
    typist.type("three months notice for the company. ", interval_ms=300)
    shifted = [p for p in typist.payloads[already_sent:] if p.baseline_avg_pause_ms is not None]
    assert len(shifted) >= 1
    assert shifted[0].baseline_avg_pause_ms > 120


def test_baseline_ignores_gaps_of_ten_seconds_or_more(typist, detector):
    typist.type("ab", interval_ms=100)
    typist.wait(20_000)
    typist.type("c")
    assert detector.get_baseline("u_test")["avg_pause_ms"] == pytest.approx(100)


def test_baseline_deletion_rate(typist, detector):
    typist.type("abcd\b", interval_ms=100)
    detector.manual_trigger("c1")
    assert detector.get_baseline("u_test")["avg_deletion_rate"] == pytest.approx(0.25)


# Hard constraint 1: no raw text leaves the detector.

_ALLOWED_STR_FIELDS = {
    "user_id", "device_id", "agent_version", "os", "surface", "context_id", "trigger",
}


def test_payload_has_no_free_text_fields():
    hints = typing.get_type_hints(SignalPayload)
    for f in dataclasses.fields(SignalPayload):
        hint = hints[f.name]
        if hint is str:
            assert f.name in _ALLOWED_STR_FIELDS, f"{f.name} could carry text"
    # Dict keys are language codes and placeholder kinds; topics are vocabulary ids.
    assert hints["hedge_words_by_language"] == dict[str, int]
    assert hints["placeholders_by_kind"] == dict[str, int]
    assert hints["topics"] == tuple[str, ...]


def test_typed_text_never_appears_in_payloads(typist, detector):
    typist.type("Zebrafinch quokka maybe [wombat] <capybara> volgens mij. ")
    typist.paste(40)
    typist.type("jan.axolotl@sdworx.com 987654 ")
    typist.wait(3000, tick_every_ms=100)
    typist.payloads.append(detector.manual_trigger("c1"))
    typist.payloads.append(typist.submit())

    serialized = json.dumps([p.to_dict() for p in typist.payloads]).lower()
    for secret in ["zebrafinch", "quokka", "maybe", "wombat", "capybara", "volgens", "axolotl", "sdworx", "987654"]:
        assert secret not in serialized
    assert len(typist.payloads) >= 4


def test_payload_is_json_serializable(typist, detector):
    typist.type("maybe ")
    data = typist.payloads[0].to_dict()
    assert json.loads(json.dumps(data))["trigger"] == "hedge_word"
    assert set(data) == {f.name for f in dataclasses.fields(SignalPayload)}
