"""Placeholder matchers.

They run on the detector's private in-memory window and return a PlaceholderKind,
never the matched text.
"""

import re

from signal_detector.events import PlaceholderKind

_BRACKET = re.compile(r"\[[^\[\]\n]*\]$")
_ANGLE = re.compile(r"<[^<>\n]*>$")
# Fire once, when a run reaches exactly three; longer runs don't fire again.
_X_RUN = re.compile(r"(?<!x)xxx$", re.IGNORECASE)
_QUESTION_RUN = re.compile(r"(?<!\?)\?\?\?$")


def completed_placeholder(text: str) -> PlaceholderKind | None:
    """Placeholder completed by the last char of `text`, or None."""
    if not text:
        return None
    last = text[-1]
    if last == "]" and _BRACKET.search(text):
        return PlaceholderKind.BRACKET
    if last == ">" and _ANGLE.search(text):
        return PlaceholderKind.ANGLE
    if last in "xX" and _X_RUN.search(text):
        return PlaceholderKind.X_RUN
    if last == "?" and _QUESTION_RUN.search(text):
        return PlaceholderKind.QUESTION_RUN
    return None


def ends_with_ellipsis(text: str) -> bool:
    """True if the text ends with "...". Counts as a placeholder only after a > 2 s pause."""
    return text.endswith("...")
