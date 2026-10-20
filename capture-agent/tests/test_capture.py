"""Safety checks around the hook's raw-character queue, without installing a keyboard hook."""

from contextlib import nullcontext

from agent import capture
from agent.surfaces import Surface


class PipelineProbe:
    """Record only whether unsafe input was forwarded or local windows were erased."""

    def __init__(self):
        self.forwarded = []
        self.suspended = False

    def handle(self, *args, **kwargs):
        self.forwarded.append((args, kwargs))

    def suspend(self):
        self.suspended = True


def make_capture(monkeypatch, policy):
    """Build inert capture workers; no global listeners are started."""
    monkeypatch.setattr(capture.keyboard, "Listener", lambda **kwargs: None)
    monkeypatch.setattr(capture.auto, "UIAutomationInitializerInThread", nullcontext)
    probe = PipelineProbe()
    return capture.Capture(probe, frozenset(), policy=policy), probe


def test_sensitive_fields_are_rejected_before_key_classification(monkeypatch):
    hook, probe = make_capture(monkeypatch, lambda: {"teams_desktop"})
    monkeypatch.setattr(capture, "focused_surface", lambda:
                        Surface("password", "teams_desktop", True))
    monkeypatch.setattr(hook, "_classify", lambda key: (_ for _ in ()).throw(AssertionError()))
    hook._on_press(capture.keyboard.KeyCode.from_char("s"))
    assert hook._queue.empty()
    assert not probe.forwarded


def test_disabled_capture_never_resolves_or_queues_the_key(monkeypatch):
    hook, _ = make_capture(monkeypatch, frozenset)
    monkeypatch.setattr(capture, "focused_surface", lambda: (_ for _ in ()).throw(AssertionError()))
    hook._on_press(capture.keyboard.KeyCode.from_char("s"))
    assert hook._queue.empty()


def test_changed_focus_drops_queued_characters_and_clears_text(monkeypatch):
    hook, probe = make_capture(monkeypatch, lambda: {"teams_desktop"})
    original = Surface("first", "teams_desktop", False)
    monkeypatch.setattr(capture, "focused_surface", lambda:
                        Surface("second", "teams_desktop", False))
    hook._handle(capture.Action.CHAR, "s", capture._now_ms(), original)
    assert not probe.forwarded
    assert probe.suspended


def test_capture_queue_is_bounded(monkeypatch):
    hook, _ = make_capture(monkeypatch, lambda: {"teams_desktop"})
    monkeypatch.setattr(capture, "focused_surface", lambda:
                        Surface("first", "teams_desktop", False))
    for _ in range(200):
        hook._on_press(capture.keyboard.KeyCode.from_char("s"))
    assert hook._queue.qsize() == 128
    assert hook.dropped["queue full"] == 72
