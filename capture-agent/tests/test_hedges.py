"""Tests for the hedge list and matcher."""

import time

import pytest

from signal_detector.hedges import HedgeMatcher, load_hedges, normalize


@pytest.fixture(scope="module")
def matcher() -> HedgeMatcher:
    return HedgeMatcher(load_hedges())


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("peut etre", "fr"),
        ("a peu pres", "fr"),
        ("Im not sure", "en"),
        ("i dont know", "en"),
        ("ich weiss nicht", "de"),
        ("ICH WEIß NICHT", "de"),
        ("zo n beetje", None),
        ("zon beetje", "nl"),
        ("(maybe", "en"),
        ("the rate is, if I'm not mistaken", "en"),
        ("het bedrag is nog te bepalen", "nl"),
        ("le montant est à confirmer", "fr"),
        ("das ist noch zu klären", "de"),
    ],
)
def test_spelling_variants(matcher, text, language):
    assert matcher.match(text) == language


def test_no_match_on_partial_words(matcher):
    assert matcher.match("rethink") is None
    assert matcher.match("peut-êtres") is None


def test_list_has_no_phrase_in_two_languages():
    seen: dict[str, str] = {}
    for language, phrases in load_hedges().items():
        for phrase in phrases:
            key = " ".join(normalize(phrase).split())
            assert seen.setdefault(key, language) == language, f"{phrase!r} in {seen[key]} and {language}"


NEUTRAL_SENTENCES = [
    "Please send the payslips as soon as possible.",
    "Kunt u de loonbrieven zo snel mogelijk versturen?",
    "The notice period in Spain is fifteen days for this contract.",
    "De opzegtermijn bedraagt drie maanden volgens het paritair comité.",
    "Le préavis est de deux mois pour cet employé, sans aucune exception.",
    "Ce n'est pas sur la liste des avantages.",
    "Die Kündigungsfrist beträgt vier Wochen zum Monatsende.",
    "We will double check the totals before Friday.",
    "Ik heb het dossier nagekeken en alles is in orde.",
    "Merci de vérifier les fiches de paie avant lundi.",
    "Zonder twijfel is dit de juiste berekening.",
    "Wir sind noch offen für Vorschläge.",
    "Ça marche, je vous envoie le document.",
]


@pytest.mark.parametrize("sentence", NEUTRAL_SENTENCES)
def test_neutral_sentences_have_no_hedges(matcher, sentence):
    words = sentence.split()
    for end in range(1, len(words) + 1):
        text = " ".join(words[:end]).rstrip(".,;:?!")
        assert matcher.match(text) is None, f"false hedge at {words[end - 1]!r}"


def test_match_is_fast_on_a_full_window(matcher):
    window = ("the notice period for this employee is " * 6)[:200]
    start = time.perf_counter()
    for _ in range(10_000):
        matcher.match(window)
    per_match_us = (time.perf_counter() - start) / 10_000 * 1e6
    # A word ends a few times per second while typing; 1 ms per check would still be fine.
    assert per_match_us < 200
