"""Thin wrapper over langdetect: returns a language only when it is confident."""

from langdetect import DetectorFactory, LangDetectException, detect_langs

SUPPORTED_LANGUAGES = frozenset({"en", "nl", "fr"})
# langdetect is overconfident on short text ("questions about parental leaves" -> fr, 0.99999),
# so shorter samples count as unconfident and get matched in all languages.
MIN_CHARS = 60
MIN_PROBABILITY = 0.8
# The end of the window is what the user is writing now; this also caps detection time.
MAX_CHARS = 1000

# langdetect is random by default; a fixed seed makes results reproducible.
DetectorFactory.seed = 0


def detect_language(text: str) -> str | None:
    """"en", "nl" or "fr" if detection is confident, else None (caller matches all languages)."""
    sample = text[-MAX_CHARS:]
    if len(sample.strip()) < MIN_CHARS:
        return None
    try:
        best = detect_langs(sample)[0]
    except LangDetectException:
        return None
    if best.lang in SUPPORTED_LANGUAGES and best.prob >= MIN_PROBABILITY:
        return best.lang
    return None


# langdetect loads its language profiles on first use; do that at import, not mid-typing.
detect_language("load the language profiles at import time")
