"""Hedge word list loading and matching.

The matcher returns a language code, never the matched phrase, so the phrase
can't end up in a payload.

Matching is a set lookup on the last few words of the text, so the cost per check
stays constant no matter how long the list grows. Text and phrases are normalised
the same way: lowercase, accents removed, apostrophes removed, "ß" as "ss". So
"peut etre", "Im not sure" and "weiss nicht" match like their correctly spelled forms.
"""

import re
import unicodedata
from pathlib import Path

import yaml

DEFAULT_HEDGES_PATH = Path(__file__).with_name("hedges.yaml")

_LANGUAGE_CODE = re.compile(r"^[a-z]{2}$")
_LEADING_NON_WORD = re.compile(r"^\W+")
# Stripped from the end of phrases, mirroring what the detector strips from the text.
_TRAILING_PUNCTUATION = ".,;:!?)]}\"'"


def normalize(text: str) -> str:
    """Lowercase, strip accents and apostrophes, so spelling variants compare equal."""
    text = text.lower().replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.replace("'", "").replace("’", "")


def load_hedges(path: Path = DEFAULT_HEDGES_PATH) -> dict[str, list[str]]:
    """Load the hedge list: language code -> phrases. Raises ValueError on a bad file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping of language code to phrases")
    hedges: dict[str, list[str]] = {}
    for language, phrases in data.items():
        if not isinstance(language, str) or not _LANGUAGE_CODE.match(language):
            raise ValueError(f"{path}: language key must be a two-letter code, got {language!r}")
        if not isinstance(phrases, list) or not all(
            isinstance(p, str) and p.strip() for p in phrases
        ):
            raise ValueError(f"{path}: {language} must be a list of non-empty phrases")
        hedges[language] = phrases
    return hedges


class HedgeMatcher:
    """Finds a hedge phrase at the very end of a text, on whole-word boundaries."""

    def __init__(self, hedges: dict[str, list[str]]):
        # Normalised phrase -> language. A phrase listed in two languages keeps the first.
        self._phrases: dict[str, str] = {}
        for language, phrases in hedges.items():
            for phrase in phrases:
                key = " ".join(normalize(phrase).split()).rstrip(_TRAILING_PUNCTUATION)
                if key:
                    self._phrases.setdefault(key, language)
        self._max_words = max((key.count(" ") + 1 for key in self._phrases), default=0)

    def __len__(self) -> int:
        return len(self._phrases)

    def match(self, text: str) -> str | None:
        """Language code of the hedge that `text` ends with, or None.

        Only the last few words are looked at, so the cost doesn't depend on the text length.
        """
        if not self._max_words:
            return None
        words = normalize(" ".join(text.rsplit(maxsplit=self._max_words)[-self._max_words :]))
        words = words.split()
        # Longest phrase first, so "I'm not sure" wins over a shorter phrase it ends with.
        for count in range(len(words), 0, -1):
            candidate = _LEADING_NON_WORD.sub("", " ".join(words[-count:]))
            language = self._phrases.get(candidate)
            if language is not None:
                return language
        return None
