"""whoknows signal detector: keystroke events in, counted signal payloads out."""

from signal_detector.detector import DetectorConfig, SignalDetector
from signal_detector.events import KeyEvent, KeyKind, PlaceholderKind, SignalPayload, Trigger

__all__ = [
    "DetectorConfig",
    "KeyEvent",
    "KeyKind",
    "PlaceholderKind",
    "SignalDetector",
    "SignalPayload",
    "Trigger",
]
