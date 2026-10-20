"""Named entities: countries, joint committees and worker classes.

Each maps to a typed token (country_ES, PC_200, worker_white_collar). The matched
text itself is never returned.
"""

import re

from topic_extractor.normalize import normalize, tokenize
from topic_extractor.stems import PatternIndex, add_pattern, match_index


class CountryMatcher:
    """Matches country names in any language to country_<ISO2>."""

    def __init__(self, countries: dict[str, list[str]]):
        self._index: PatternIndex = {}
        for iso, names in countries.items():
            for name in names:
                words = tuple(tokenize(normalize(name)))
                if words:
                    add_pattern(self._index, words, country_token(iso))

    def match(self, words: list[str], capitalised: frozenset[str]) -> set[str]:
        return match_index(self._index, words, words, capitalised)


def country_token(iso: str) -> str:
    return f"country_{iso}"


def compile_joint_committee(pattern: str) -> re.Pattern[str]:
    """Compile the vocab's PC pattern (one capture group for the number) for normalised text."""
    compiled = re.compile(rf"(?<![a-z0-9])(?:{pattern})(?![0-9])", re.IGNORECASE)
    if compiled.groups != 1:
        raise ValueError("joint_committee pattern must have exactly one capture group")
    return compiled


def joint_committees(normalized_text: str, pattern: re.Pattern[str]) -> set[str]:
    """PC_<number> tokens. Run on normalised text BEFORE numbers are masked."""
    return {f"PC_{match.group(1)}" for match in pattern.finditer(normalized_text)}


def worker_class_patterns(
    worker_classes: dict[str, dict[str, list[str]]],
) -> dict[str, dict[str, list[str]]]:
    """Turn {language: {class: phrases}} into {worker_<class>: {language: phrases}}."""
    patterns: dict[str, dict[str, list[str]]] = {}
    for language, classes in worker_classes.items():
        for worker_class, phrases in classes.items():
            patterns.setdefault(f"worker_{worker_class}", {})[language] = phrases
    return patterns
