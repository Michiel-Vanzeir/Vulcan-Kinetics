"""Normalisation and masking for the topic extractor.

Works on the in-memory window only and returns transformed text or tokens.
Nothing here logs, stores or returns any part of the window to a caller outside
the extractor.
"""

import re
import unicodedata
from pathlib import Path

import yaml

TYPOS_PATH = Path(__file__).with_name("typos.yaml")

_EMAIL = re.compile(r"\S+@\S+")
_DIGITS = re.compile(r"\d+")
_WHITESPACE = re.compile(r"\s+")
_WORD = re.compile(r"[a-z0-9]+")
_RAW_WORD = re.compile(r"[A-Za-z0-9]+")
_TYPO_WORD = re.compile(r"^[a-z]+$")


def strip_accents(text: str) -> str:
    """Remove diacritics: "préavis" -> "preavis", "België" -> "Belgie"."""
    decomposed = unicodedata.normalize("NFKD", text.replace("ß", "ss"))
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize(text: str) -> str:
    """Lowercase, strip accents and collapse whitespace."""
    return _WHITESPACE.sub(" ", strip_accents(text.lower())).strip()


def mask_emails(text: str) -> str:
    """Replace email addresses with a space, so their parts can't match anything."""
    return _EMAIL.sub(" ", text)


def mask_numbers(text: str) -> str:
    """Replace every run of digits with a space (IBANs, amounts, phone numbers, dates)."""
    return _DIGITS.sub(" ", text)


def tokenize(text: str) -> list[str]:
    """Split normalised text into words. Hyphens and apostrophes separate words."""
    return _WORD.findall(text)


def capitalised_words(window: str) -> frozenset[str]:
    """Lowercased forms of the words written in capitals, e.g. {"or", "rsz"} for "OR" and "RSZ".

    Short patterns (1 to 3 letters) only match when capitalised, so Dutch "or" (works council)
    doesn't fire on every English "or".
    """
    return frozenset(
        word.lower()
        for word in _RAW_WORD.findall(strip_accents(window))
        if word.isupper()
    )


def load_typos(path: Path = TYPOS_PATH) -> dict[str, tuple[str, ...]]:
    """Load the typo map as misspelling -> canonical words. Raises ValueError on a bad file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected canonical form -> list of misspellings")
    typos: dict[str, tuple[str, ...]] = {}
    for canonical, misspellings in data.items():
        if not isinstance(canonical, str) or not isinstance(misspellings, list):
            raise ValueError(f"{path}: bad entry {canonical!r}")
        canonical_words = tuple(tokenize(normalize(canonical)))
        for misspelling in misspellings:
            if not isinstance(misspelling, str) or not _TYPO_WORD.match(misspelling):
                raise ValueError(f"{path}: misspelling must be one lowercase word, got {misspelling!r}")
            typos[misspelling] = canonical_words
    return typos


def apply_typos(tokens: list[str], typos: dict[str, tuple[str, ...]]) -> list[str]:
    """Replace known misspellings with their canonical words."""
    fixed: list[str] = []
    for token in tokens:
        fixed.extend(typos.get(token, (token,)))
    return fixed
