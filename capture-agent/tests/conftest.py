"""Shared fixtures: a detector with a fake clock and a Typist that builds synthetic event streams."""

import pytest

from signal_detector import DetectorConfig, KeyEvent, KeyKind, SignalDetector, SignalPayload

START_MS = 1_729_512_345_000
BACKSPACE = "\b"


class FakeClock:
    def __init__(self, now_ms: int = START_MS):
        self.now_ms = now_ms

    def __call__(self) -> int:
        return self.now_ms


class Typist:
    """Feeds synthetic KeyEvents for one context and collects the payloads."""

    def __init__(
        self,
        detector: SignalDetector,
        clock: FakeClock,
        context_id: str = "c1",
        surface: str = "gmail_web",
        interval_ms: int = 100,
    ):
        self.detector = detector
        self.clock = clock
        self.context_id = context_id
        self.surface = surface
        self.interval_ms = interval_ms
        self.payloads: list[SignalPayload] = []

    def send(self, kind: KeyKind, **fields) -> SignalPayload | None:
        event = KeyEvent(
            ts=self.clock.now_ms,
            kind=kind,
            surface=self.surface,
            context_id=self.context_id,
            **fields,
        )
        payload = self.detector.handle_event(event)
        if payload is not None:
            self.payloads.append(payload)
        return payload

    def focus_in(self, **fields) -> None:
        self.send(KeyKind.FOCUS_IN, **fields)

    def focus_out(self) -> None:
        self.send(KeyKind.FOCUS_OUT)

    def type(self, text: str, interval_ms: int | None = None) -> None:
        """Type text one key at a time; "\\b" is a backspace."""
        for char in text:
            self.clock.now_ms += self.interval_ms if interval_ms is None else interval_ms
            if char == BACKSPACE:
                self.send(KeyKind.BACKSPACE)
            else:
                self.send(KeyKind.CHAR, char=char)

    def paste(self, char_count: int) -> None:
        self.clock.now_ms += self.interval_ms
        self.send(KeyKind.PASTE, pasted_char_count=char_count)

    def wait(self, ms: int, tick_every_ms: int | None = None) -> None:
        """Let time pass, optionally calling detector.tick() like the agent's timer would."""
        if tick_every_ms is None:
            self.clock.now_ms += ms
            return
        end = self.clock.now_ms + ms
        while self.clock.now_ms < end:
            self.clock.now_ms = min(end, self.clock.now_ms + tick_every_ms)
            self.payloads.extend(self.detector.tick())

    def submit(self) -> SignalPayload | None:
        self.clock.now_ms += self.interval_ms
        return self.send(KeyKind.SUBMIT)

    @property
    def triggers(self) -> list[str]:
        return [p.trigger for p in self.payloads]


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def detector(clock: FakeClock) -> SignalDetector:
    return SignalDetector(DetectorConfig(user_id="u_test", device_id="d_test", clock=clock))


@pytest.fixture
def typist(detector: SignalDetector, clock: FakeClock) -> Typist:
    typist = Typist(detector, clock)
    typist.focus_in()
    return typist
