"""Keyword-based topic matching and hesitation detection.

Each topic has weighted keywords (EN + NL). A topic matches when the summed weight
of the keywords found in the text reaches MIN_SCORE, so a weak hint like "PC 200"
alone is not enough, but "year-end bonus" is.
"""

import re
import unicodedata

MIN_SCORE = 3
MAX_TOPICS = 2

HEDGES = [
    "i believe", "i think", "not sure", "not 100% sure", "not certain", "probably", "i guess", "i assume", "i suppose",
    "maybe", "perhaps", "if i'm not mistaken", "if i remember correctly", "as far as i know", "afaik", "iirc",
    "i would say", "i'd say", "should be", "might be", "could be", "normally", "in principle", "let me check",
    "i'll check", "i need to check", "double-check", "not entirely", "unclear",
    "denk ik", "ik denk", "niet zeker", "volgens mij", "misschien", "waarschijnlijk", "ik vermoed", "normaal gezien",
    "in principe", "als ik me niet vergis", "moet ik nakijken", "ik check", "twijfel",
]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9']+", " ", text)
    return f" {text.strip()} "


def match_topics(text: str, topics: dict[str, dict]) -> list[dict]:
    norm = normalize(text)
    scored = []
    for topic in topics.values():
        hits = [kw for kw in topic["keywords"] if normalize(kw) in norm]
        score = sum(topic["keywords"][kw] for kw in hits)
        if score >= MIN_SCORE:
            scored.append({"id": topic["id"], "label": topic["label"], "score": score, "matched": hits})
    scored.sort(key=lambda t: t["score"], reverse=True)
    return scored[:MAX_TOPICS]


def find_hedges(text: str) -> list[str]:
    norm = normalize(text)
    return [h for h in HEDGES if normalize(h) in norm]
