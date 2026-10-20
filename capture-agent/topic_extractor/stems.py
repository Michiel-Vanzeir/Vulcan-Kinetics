"""Per-language Snowball stemming and the inverted pattern index.

The index is built once at import: first word of a pattern -> patterns starting with it.
Matching a window then costs one dict lookup per word, independent of vocabulary size.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from nltk.stem.snowball import SnowballStemmer

from topic_extractor.normalize import normalize, tokenize

LANGUAGES = {"en": "english", "nl": "dutch", "fr": "french"}
_STEMMERS = {code: SnowballStemmer(name) for code, name in LANGUAGES.items()}
# Patterns this short only match when the word is written in capitals.
SHORT_PATTERN_MAX_LETTERS = 3
# Dutch single-word patterns at least this long also match inside compound words.
COMPOUND_MIN_LETTERS = 9
# A stemmed match may be at most this much shorter than the pattern word: "payslips" and
# "leaves" match, but "index" doesn't match "indexation" just because they share a stem.
MAX_STEM_SHORTENING = 3


@lru_cache(maxsize=50_000)
def stem(language: str, word: str) -> str:
    """Snowball stem of one normalised word in one of LANGUAGES."""
    return _STEMMERS[language].stem(word)


@dataclass(frozen=True, slots=True)
class Pattern:
    """A pattern as a word sequence, the token it produces, and whether it needs capitals."""

    words: tuple[str, ...]
    token: str
    needs_capitals: bool
    # Minimum length of each matching window word (unstemmed).
    min_lengths: tuple[int, ...]


PatternIndex = dict[str, list[Pattern]]


def match_index(
    index: PatternIndex, words: list[str], raw_words: list[str], capitalised: frozenset[str]
) -> set[str]:
    """Tokens of all patterns found in `words`. `raw_words` are the unstemmed forms."""
    hits: set[str] = set()
    for i, word in enumerate(words):
        for pattern in index.get(word, ()):
            end = i + len(pattern.words)
            if tuple(words[i:end]) != pattern.words:
                continue
            if pattern.needs_capitals and raw_words[i] not in capitalised:
                continue
            if any(len(raw) < n for raw, n in zip(raw_words[i:end], pattern.min_lengths)):
                continue
            hits.add(pattern.token)
    return hits


def add_pattern(
    index: PatternIndex,
    words: tuple[str, ...],
    token: str,
    raw_words: tuple[str, ...] | None = None,
) -> None:
    """Index a pattern. `raw_words` (the unstemmed pattern) is given for stemmed patterns."""
    raw = raw_words or words
    needs_capitals = len(raw) == 1 and len(raw[0]) <= SHORT_PATTERN_MAX_LETTERS
    if raw_words:
        min_lengths = tuple(max(1, len(w) - MAX_STEM_SHORTENING) for w in raw_words)
    else:
        min_lengths = (0,) * len(words)
    index.setdefault(words[0], []).append(Pattern(words, token, needs_capitals, min_lengths))


class TopicIndex:
    """All topic patterns, stemmed per language, plus the special cases.

    - stemmed: per language, matched against the window stemmed in that language
    - exact: all languages unstemmed, so a Dutch word in an English sentence still matches
    - digit_patterns: patterns containing digits (13th month, c4), matched before numbers are masked
    - compounds: long Dutch words, also matched inside compounds ("eindejaarspremieberekening")
    """

    def __init__(self, patterns: dict[str, dict[str, list[str]]]):
        self.stemmed: dict[str, PatternIndex] = {language: {} for language in LANGUAGES}
        self.exact: PatternIndex = {}
        self.digit_patterns: list[tuple[re.Pattern[str], str]] = []
        self.compounds: list[tuple[str, str]] = []
        for token, by_language in patterns.items():
            for language, phrases in by_language.items():
                for phrase in phrases:
                    self._add(token, language, phrase)

    def _add(self, token: str, language: str, phrase: str) -> None:
        words = tuple(tokenize(normalize(phrase)))
        if not words:
            return
        if any(char.isdigit() for word in words for char in word):
            body = r"\s+".join(re.escape(word) for word in words)
            self.digit_patterns.append((re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])"), token))
            return
        add_pattern(self.exact, words, token)
        add_pattern(self.stemmed[language], tuple(stem(language, w) for w in words), token, words)
        if language == "nl" and len(words) == 1 and len(words[0]) >= COMPOUND_MIN_LETTERS:
            self.compounds.append((words[0], token))

    def match_digit_patterns(self, normalized_text: str) -> set[str]:
        """Run on normalised text BEFORE numbers are masked."""
        return {token for pattern, token in self.digit_patterns if pattern.search(normalized_text)}

    def match_words(
        self, words: list[str], languages: list[str], capitalised: frozenset[str]
    ) -> set[str]:
        """Exact matches in any language, plus stemmed matches in the given languages."""
        hits = match_index(self.exact, words, words, capitalised)
        for language in languages:
            stemmed = [stem(language, word) for word in words]
            hits |= match_index(self.stemmed[language], stemmed, words, capitalised)
        return hits

    def match_compounds(self, words: list[str]) -> set[str]:
        hits: set[str] = set()
        for word in set(words):
            if len(word) > COMPOUND_MIN_LETTERS:
                hits.update(token for part, token in self.compounds if part in word and part != word)
        return hits
