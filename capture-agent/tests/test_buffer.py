"""Tests for the ring buffer and scrubbing."""

import pytest

from agent.buffer import BACKSPACE, KeyEntry, RingBuffer, scrub


def type_text(buffer: RingBuffer, text: str, surface_id: str = "s1") -> None:
    for i, char in enumerate(text):
        buffer.append(KeyEntry(char=char, ts=float(i), surface_id=surface_id))


def test_rejects_non_positive_capacity():
    with pytest.raises(ValueError):
        RingBuffer(capacity=0)


def test_window_returns_typed_text():
    buffer = RingBuffer(capacity=64)
    type_text(buffer, "notice period")
    assert buffer.window("s1") == "notice period"


def test_overwrites_oldest_when_full():
    buffer = RingBuffer(capacity=5)
    type_text(buffer, "abcdefg")
    assert buffer.window("s1") == "cdefg"
    assert len(buffer.entries("s1")) == 5


def test_applies_backspaces():
    buffer = RingBuffer(capacity=64)
    type_text(buffer, "bonis" + BACKSPACE * 2 + "us")
    assert buffer.window("s1") == "bonus"


def test_separates_surfaces():
    buffer = RingBuffer(capacity=64)
    type_text(buffer, "teams", surface_id="a")
    type_text(buffer, "word", surface_id="b")
    assert buffer.window("a") == "teams"
    assert buffer.window("b") == "word"


def test_clear_forgets_only_that_surface():
    buffer = RingBuffer(capacity=64)
    type_text(buffer, "sent", surface_id="a")
    type_text(buffer, "draft", surface_id="b")
    buffer.clear("a")
    assert buffer.window("a") == ""
    assert buffer.window("b") == "draft"


def test_entries_are_oldest_first_after_wrap():
    buffer = RingBuffer(capacity=3)
    type_text(buffer, "wxyz")
    assert [e.char for e in buffer.entries("s1")] == ["x", "y", "z"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mail sarah@sdworx.com today", "mail today"),
        ("salary 3.250,50 per month", "salary per month"),
        ("call 0470 12 34 56", "call "),
        ("IBAN BE68539007547034", "IBAN BE "),
        ("bonus under PC 200 for ES", "bonus under PC 200 for ES"),
        ("pc200 and PSC 200.01", "PC 200 and PSC 200.01"),
    ],
)
def test_scrub(text, expected):
    assert scrub(text) == expected
