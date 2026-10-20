"""Fixed-size in-memory ring buffer of recent keystrokes.

Memory use is constant: slots are preallocated and overwritten in place.
Nothing in this module writes to disk or the network.
"""

import re
import threading
from dataclasses import dataclass

from agent.config import BUFFER_CAPACITY

BACKSPACE = "\b"
NEWLINE = "\n"

_EMAIL = re.compile(r"\S+@\S+")
# Joint committee numbers ("PC 200") are a topic, not personal data, so they survive
# scrubbing (normalised to "PC 200"). Every other number is removed.
_NUMBER_OR_COMMITTEE = re.compile(
    r"\b(PC|PSC|CP)\s?(\d{3}(?:\.\d{2})?)\b|\d+(?:[.,/-]\d+)*", re.IGNORECASE
)
_SPACES = re.compile(r" {2,}")


@dataclass(frozen=True, slots=True)
class KeyEntry:
    """One keystroke: a printable char, BACKSPACE or NEWLINE, tied to a text field."""

    char: str
    ts: float
    surface_id: str


def scrub(text: str) -> str:
    """Remove email addresses and numbers so they never reach topic extraction."""
    text = _EMAIL.sub(" ", text)
    text = _NUMBER_OR_COMMITTEE.sub(
        lambda m: f"{m.group(1).upper()} {m.group(2)}" if m.group(1) else " ", text
    )
    return _SPACES.sub(" ", text)


class RingBuffer:
    """Thread-safe ring buffer shared by the capture thread and the detectors."""

    def __init__(self, capacity: int = BUFFER_CAPACITY):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._slots: list[KeyEntry | None] = [None] * capacity
        self._next = 0
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return len(self._slots)

    def append(self, entry: KeyEntry) -> None:
        with self._lock:
            self._slots[self._next] = entry
            self._next = (self._next + 1) % len(self._slots)

    def entries(self, surface_id: str) -> list[KeyEntry]:
        """Keystrokes for one text field, oldest first. Used for timing signals."""
        with self._lock:
            ordered = self._slots[self._next:] + self._slots[: self._next]
        return [e for e in ordered if e is not None and e.surface_id == surface_id]

    def window(self, surface_id: str) -> str:
        """Current text for one field with backspaces applied, scrubbed for extraction."""
        chars: list[str] = []
        for entry in self.entries(surface_id):
            if entry.char == BACKSPACE:
                if chars:
                    chars.pop()
            else:
                chars.append(entry.char)
        return scrub("".join(chars))

    def clear(self, surface_id: str) -> None:
        """Forget a field's keystrokes, e.g. after the message is sent."""
        with self._lock:
            for i, entry in enumerate(self._slots):
                if entry is not None and entry.surface_id == surface_id:
                    self._slots[i] = None
