"""End-to-end: keys -> signal detector -> topic extractor -> wire format -> backend filter."""

import importlib.util
import sys
import json
from pathlib import Path

import pytest

from agent.backend_payload import BackendPayloads
from agent.buffer import RingBuffer
from agent.pipeline import Action, Pipeline, context_id
from agent.transport import check
from agent.surfaces import Surface
from conftest import FakeClock
from signal_detector import DetectorConfig, SignalDetector

TEAMS = Surface(id="teams_desktop:42.1", name="teams_desktop", is_sensitive=False)
OUTLOOK = Surface(id="outlook_desktop:7.3", name="outlook_desktop", is_sensitive=False)
PASSWORD = Surface(id="gmail_web:9.9", name="gmail_web", is_sensitive=True)
FILTER_PATH = Path(__file__).resolve().parents[2] / "Neo4J-backend" / "expertise_filter.py"


class RecordingTransport:
    """Stands in for agent.transport.Transport: same conversion and check, no network."""

    def __init__(self) -> None:
        self.converter = BackendPayloads()
        self.payloads: list[dict] = []

    def send(self, payload) -> None:
        body = self.converter.convert(payload)
        assert check(body), body
        self.payloads.append(body)

    def request_experts(self, topics: list[str]) -> list[dict]:
        return []


class Keyboard:
    def __init__(self, pipeline: Pipeline, clock: FakeClock):
        self.pipeline = pipeline
        self.clock = clock

    def type(self, surface: Surface, text: str, interval_ms: int = 100) -> None:
        for char in text:
            self.clock.now_ms += interval_ms
            if char == "\b":
                self.pipeline.handle(surface, Action.BACKSPACE, self.clock.now_ms)
            elif char == "\n":
                self.pipeline.handle(surface, Action.ENTER, self.clock.now_ms)
            else:
                self.pipeline.handle(surface, Action.CHAR, self.clock.now_ms, char=char)

    def press(self, surface: Surface, action: Action, **fields) -> None:
        self.clock.now_ms += 100
        self.pipeline.handle(surface, action, self.clock.now_ms, **fields)

    def wait(self, ms: int) -> None:
        end = self.clock.now_ms + ms
        while self.clock.now_ms < end:
            self.clock.now_ms += 100
            self.pipeline.tick(self.clock.now_ms)


@pytest.fixture
def sender() -> RecordingTransport:
    return RecordingTransport()


@pytest.fixture
def keyboard(sender: RecordingTransport) -> Keyboard:
    clock = FakeClock()
    detector = SignalDetector(DetectorConfig(user_id="emp_014", clock=clock))
    return Keyboard(Pipeline(RingBuffer(), detector, sender), clock)


def test_hedge_in_teams_sends_payload_with_topics(keyboard, sender):
    keyboard.type(TEAMS, "De opzegtermijn voor een bediende in Spanje onder PC 200 is denk ik ")
    hedge = [p for p in sender.payloads if p["trigger"] == "hedge"]
    assert len(hedge) == 1
    assert hedge[0]["topics"] == ["PC_200", "country_ES", "notice_period", "worker_white_collar"]
    assert hedge[0]["hedge_words"] == 1
    assert hedge[0]["surface"] == "teams_desktop"
    assert hedge[0]["context_id"] == context_id(TEAMS.id)


def test_counts_are_cumulative_per_context(keyboard, sender):
    keyboard.type(TEAMS, "Is the year-end bonus paid? ")
    keyboard.type(TEAMS, "Or the 13th month? ")
    first, second = [p for p in sender.payloads if p["trigger"] == "punctuation"]
    assert second["chars_typed"] > first["chars_typed"]
    assert second["question_marks_written"] == 2
    assert second["topics"] == ["year_end_bonus"]


def test_enter_submits_in_chat_and_resets(keyboard, sender):
    keyboard.type(TEAMS, "the payslip is wrong\n")
    submit = sender.payloads[-1]
    assert submit["trigger"] == "submit"
    assert submit["topics"] == ["payslip"]
    keyboard.type(TEAMS, "hello")
    keyboard.press(TEAMS, Action.MANUAL)
    assert sender.payloads[-1]["chars_typed"] == 5
    assert sender.payloads[-1]["topics"] == []


def test_enter_is_a_new_line_outside_chat(keyboard, sender):
    keyboard.type(OUTLOOK, "Dear Sarah,\n")
    assert all(p["trigger"] != "submit" for p in sender.payloads)
    assert sender.payloads[-1]["trigger"] == "punctuation"


def test_manual_trigger_and_pause(keyboard, sender):
    keyboard.type(OUTLOOK, "about the meal vouchers")
    keyboard.wait(1000)
    assert sender.payloads[-1]["trigger"] == "pause"
    keyboard.press(OUTLOOK, Action.MANUAL)
    assert sender.payloads[-1]["trigger"] == "manual"
    assert sender.payloads[-1]["topics"] == ["meal_vouchers"]


def test_paste_counts(keyboard, sender):
    keyboard.press(OUTLOOK, Action.PASTE, pasted_char_count=250)
    keyboard.press(OUTLOOK, Action.MANUAL)
    payload = sender.payloads[-1]
    assert payload["paste_events"] == 1
    assert payload["pasted_char_count"] == 250
    assert payload["chars_typed"] == 0


def test_sensitive_field_sends_nothing_and_blurs_previous_field(keyboard, sender):
    keyboard.type(TEAMS, "hi")
    keyboard.type(PASSWORD, "hunter2. maybe ")
    keyboard.wait(15_000)
    assert sender.payloads == []
    keyboard.type(TEAMS, " there")
    keyboard.press(TEAMS, Action.MANUAL)
    assert sender.payloads[-1]["window_switches_away"] == 1


def test_no_typed_text_reaches_the_sender(keyboard, sender):
    keyboard.type(TEAMS, "Zebrafinch quokka, maybe the opzegtermijn? mail jan@sdworx.com 0470123456\n")
    serialized = json.dumps(sender.payloads).lower()
    for fragment in ["zebrafinch", "quokka", "maybe", "opzegtermijn", "sdworx", "0470123456"]:
        assert fragment not in serialized
    assert "notice_period" in serialized


def test_check_rejects_text_and_unknown_topics():
    good = {"user_id": "u", "context_id": "c", "trigger": "manual", "ts": 1, "topics": ["payslip"]}
    assert check(good)
    assert not check({**good, "topics": ["some free text"]})
    assert not check({**good, "note": "the user typed this"})
    assert not check({**good, "chars_typed": "12 chars"})
    assert not check({**good, "surface": "x" * 200})


def test_backend_filter_accepts_every_payload(keyboard, sender, tmp_path):
    spec = importlib.util.spec_from_file_location("expertise_filter", FILTER_PATH)
    expertise_filter = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = expertise_filter
    spec.loader.exec_module(expertise_filter)
    store = expertise_filter.PersonStore(str(tmp_path / "people.db"))
    backend = expertise_filter.ExpertiseFilter(store)

    keyboard.type(TEAMS, "Hoe zit het met de eindejaarspremie [naam] denk ik? xxx ")
    keyboard.type(TEAMS, "notice perido" + "\b" * 5 + "riod in Spain\n")
    triggers = {p["trigger"] for p in sender.payloads}
    assert {"hedge", "placeholder", "deletion_burst", "submit"} <= triggers
    for payload in sender.payloads:
        backend.process(payload)
