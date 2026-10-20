"""Topic extractor: recent typing in, topic tokens from a fixed vocabulary out.

Returns a subset of a fixed vocabulary, never free text. See extract_topics().

Called by agent/pipeline.py for each signal payload, filling SignalPayload.topics.
Keyword, pattern and stem matching only: no models,
no network, no disk IO after import.
"""

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from topic_extractor.entities import (
    CountryMatcher,
    compile_joint_committee,
    country_token,
    joint_committees,
    worker_class_patterns,
)
from topic_extractor.lang_detect import SUPPORTED_LANGUAGES, detect_language
from topic_extractor.normalize import (
    apply_typos,
    capitalised_words,
    load_typos,
    mask_emails,
    mask_numbers,
    normalize,
    tokenize,
)
from topic_extractor.stems import LANGUAGES, TopicIndex

log = logging.getLogger(__name__)

VOCAB_PATH = Path(__file__).with_name("vocab.yaml")
_TOPIC_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_PC_TOKEN = re.compile(r"^PC_\d{3}$")


@dataclass(frozen=True)
class Vocabulary:
    """The loaded vocab.yaml. `tokens` lists every output token except PC_<3 digits>."""

    patterns: dict[str, dict[str, list[str]]]
    countries: dict[str, list[str]]
    joint_committee: re.Pattern[str]
    tokens: frozenset[str]


def load_vocabulary(path: Path = VOCAB_PATH) -> Vocabulary:
    """Load and validate vocab.yaml. Raises ValueError on a malformed file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        topics = data["topics"]
        entities = data["entities"]
        countries = entities["country"]
        pc_pattern = entities["joint_committee"]["pattern"]
        worker_classes = entities["worker_class"]
    except (KeyError, TypeError) as error:
        raise ValueError(f"{path}: missing section {error}") from error

    patterns: dict[str, dict[str, list[str]]] = {}
    for token, entry in topics.items():
        if not _TOPIC_TOKEN.match(str(token)) or not isinstance(entry, dict):
            raise ValueError(f"{path}: bad topic {token!r}")
        patterns[token] = entry.get("patterns") or {}
    patterns.update(worker_class_patterns(worker_classes))
    for token, by_language in patterns.items():
        for language, phrases in by_language.items():
            if language not in LANGUAGES:
                raise ValueError(f"{path}: {token} has unknown language {language!r}")
            if not isinstance(phrases, list) or not all(isinstance(p, str) for p in phrases):
                raise ValueError(f"{path}: {token}.{language} must be a list of strings")

    for iso, names in countries.items():
        if not re.match(r"^[A-Z]{2}$", str(iso)) or not all(isinstance(n, str) for n in names):
            raise ValueError(f"{path}: bad country {iso!r}")

    tokens = frozenset(patterns) | frozenset(country_token(iso) for iso in countries)
    return Vocabulary(patterns, countries, compile_joint_committee(pc_pattern), tokens)


_VOCAB = load_vocabulary()
_TYPOS = load_typos()
_INDEX = TopicIndex(_VOCAB.patterns)
_COUNTRIES = CountryMatcher(_VOCAB.countries)


def vocabulary() -> frozenset[str]:
    """Every token extract_topics() can return, except PC_<3 digits> (joint committees)."""
    return _VOCAB.tokens


def is_vocab_token(token: str) -> bool:
    """True if `token` belongs to the fixed vocabulary."""
    return token in _VOCAB.tokens or _PC_TOKEN.match(token) is not None


# THE FUNCTION THAT PRODUCES TOPIC TOKENS.
def extract_topics(window: str, lang_hint: str | None = None) -> list[str]:
    """Return the topics in `window` as a sorted subset of a fixed vocabulary, never free text.

    Output constraints (hard):
    1. Every returned token is in the vocabulary loaded from vocab.yaml at import: a topic key,
       country_<ISO2>, worker_<class> or PC_<3 digits>. Tokens are validated against the
       vocabulary right before returning; anything else is dropped.
    2. The window, and any part of it, is never returned, logged or stored. Logging is
       counts and timings only.
    3. Numbers and email addresses are masked before matching. They only ever surface as
       typed tokens (PC_200), never as values.

    `window` is recent typing (up to a few thousand chars, may be mid-sentence, mixed
    EN/NL/FR, with typos). `lang_hint` ("en", "nl", "fr") skips language detection; without
    it the language is detected, and all three are matched when detection is unconfident.
    """
    if not window or not window.strip():
        return []
    started = time.perf_counter()

    text = mask_emails(normalize(window))
    hits = joint_committees(text, _VOCAB.joint_committee)
    hits |= _INDEX.match_digit_patterns(text)
    text = mask_numbers(text)

    words = apply_typos(tokenize(text), _TYPOS)
    capitalised = capitalised_words(window)
    if lang_hint in SUPPORTED_LANGUAGES:
        languages = [lang_hint]
    else:
        detected = detect_language(mask_numbers(mask_emails(window.lower())))
        languages = [detected] if detected else sorted(SUPPORTED_LANGUAGES)

    hits |= _INDEX.match_words(words, languages, capitalised)
    hits |= _INDEX.match_compounds(words)
    hits |= _COUNTRIES.match(words, capitalised)

    topics = sorted(token for token in hits if is_vocab_token(token))
    log.debug("extracted %d topics in %.1f ms", len(topics), (time.perf_counter() - started) * 1000)
    return topics
