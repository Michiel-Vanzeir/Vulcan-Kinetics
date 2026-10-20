"""Tests for the people-panel popup and its hotkey wiring."""

import urllib.parse

import pytest

from agent import panel as panel_module
from agent.buffer import RingBuffer
from agent.panel import PANEL_FILE, PanelWindow, panel_url
from agent.pipeline import Action, Pipeline
from agent.surfaces import Surface
from conftest import FakeClock
from signal_detector import DetectorConfig, SignalDetector

TEAMS = Surface(id="teams_desktop:42.1", name="teams_desktop", is_sensitive=False)


class FakePanel:
    def __init__(self) -> None:
        self.opened: list[list[str]] = []

    def open(self, topics: list[str]) -> None:
        self.opened.append(topics)


class NullTransport:
    def send(self, payload) -> None:
        pass

    def request_experts(self, topics: list[str]) -> list[dict]:
        return []


@pytest.fixture
def setup():
    clock = FakeClock()
    panel = FakePanel()
    detector = SignalDetector(DetectorConfig(user_id="emp_014", clock=clock))
    pipeline = Pipeline(RingBuffer(), detector, NullTransport(), panel=panel)
    return pipeline, panel, clock


def test_panel_file_exists():
    assert PANEL_FILE.is_file()


def test_url_holds_only_vocabulary_topics():
    url = panel_url(["notice_period", "the user typed this", "country_BE"])
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert url.startswith("file:///")
    assert query == {"popup": ["1"], "topics": ["notice_period,country_BE"]}


def test_hotkey_opens_panel_with_the_fields_topics(setup):
    pipeline, panel, clock = setup
    for char in "de opzegtermijn in Spanje":
        clock.now_ms += 100
        pipeline.handle(TEAMS, Action.CHAR, clock.now_ms, char=char)
    pipeline.handle(TEAMS, Action.MANUAL, clock.now_ms + 100)
    assert panel.opened == [["country_ES", "notice_period"]]


def test_hotkey_outside_captured_fields_opens_panel_without_topics(setup):
    pipeline, panel, clock = setup
    pipeline.handle(None, Action.MANUAL, clock.now_ms)
    assert panel.opened == [[]]


def test_typing_does_not_open_the_panel(setup):
    pipeline, panel, clock = setup
    for char in "maybe the notice period? ":
        clock.now_ms += 100
        pipeline.handle(TEAMS, Action.CHAR, clock.now_ms, char=char)
    assert panel.opened == []


def test_open_starts_browser_in_app_mode_and_closes_previous(monkeypatch):
    launched: list[list[str]] = []
    closed: list[int] = []
    open_windows = [111]

    monkeypatch.setattr(panel_module.subprocess, "Popen", lambda args, **kw: launched.append(args))
    monkeypatch.setattr(panel_module, "_place_when_ready", lambda anchor: None)
    monkeypatch.setattr(panel_module, "_forget_saved_placement", lambda: None)
    monkeypatch.setattr(panel_module, "_find_panel_windows", lambda: list(open_windows))

    def post_close(hwnd, message, wparam, lparam):
        closed.append(hwnd)
        open_windows.remove(hwnd)

    monkeypatch.setattr(panel_module._user32, "PostMessageW", post_close)
    window = PanelWindow(browser="C:/browser.exe")
    window.open(["notice_period"])

    assert closed == [111]
    [args] = launched
    assert args[0] == "C:/browser.exe"
    assert any(a.startswith("--app=file:///") and "notice_period" in a for a in args)
    assert "--window-size=500,860" in args
    assert not any(a.startswith("--window-position") for a in args)
    assert any(a.startswith("--user-data-dir=") for a in args)
