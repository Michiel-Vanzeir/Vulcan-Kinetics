"""Tests for the topic extractor."""

import logging
import time

import pytest

from topic_extractor import extract_topics, is_vocab_token, vocabulary
from topic_extractor.normalize import load_typos


def test_empty_window_returns_empty_list():
    assert extract_topics("") == []
    assert extract_topics("   \n ") == []


@pytest.mark.parametrize(
    ("window", "lang_hint", "expected"),
    [
        ("Can you check the notice period for this contract?", None, "notice_period"),
        ("Can you check the notice period for this contract?", "en", "notice_period"),
        ("Wat is de opzegtermijn voor dit contract?", None, "notice_period"),
        ("Wat is de opzegtermijn voor dit contract?", "nl", "notice_period"),
        ("Quel est le préavis pour ce contrat ?", None, "notice_period"),
        ("Quel est le préavis pour ce contrat ?", "fr", "notice_period"),
        ("When is the year-end bonus paid out this year?", None, "year_end_bonus"),
        ("Wanneer wordt de eindejaarspremie uitbetaald?", None, "year_end_bonus"),
        ("Quand la prime de fin d'année est-elle versée ?", None, "year_end_bonus"),
        ("How many meal vouchers does a part-timer get?", None, "meal_vouchers"),
        ("Hoeveel maaltijdcheques krijgt een deeltijdse?", None, "meal_vouchers"),
        ("Combien de chèques-repas pour un temps partiel ?", None, "meal_vouchers"),
    ],
)
def test_single_language_windows(window, lang_hint, expected):
    assert expected in extract_topics(window, lang_hint)


def test_mixed_language_sentence_hits_topics_from_several_languages():
    topics = extract_topics(
        "Quick question about the opzegtermijn and the payslip, and is the préavis different?"
    )
    assert {"notice_period", "payslip"} <= set(topics)
    assert extract_topics("the opzegtermijn for the eindejaarspremie in English mail") == [
        "notice_period",
        "year_end_bonus",
    ]


def test_inflected_forms_match_through_stemming():
    assert "payslip" in extract_topics("I sent both payslips yesterday")
    assert "parental_leave" in extract_topics("questions about parental leaves")


def test_dutch_compound_words_match():
    assert "year_end_bonus" in extract_topics("de eindejaarspremieberekening klopt niet")


@pytest.mark.parametrize(
    ("window", "expected"),
    [
        ("de opzegtermjin is te kort", "notice_period"),
        ("de eindjaarspremie is laat", "year_end_bonus"),
        ("je vakantiegelt komt in juni", "holiday_pay"),
        ("your paysilp is attached", "payslip"),
        ("we offer severence to everyone", "severance"),
        ("il y a un licensiement prévu", "dismissal"),
        ("les chequerepas arrivent", "meal_vouchers"),
    ],
)
def test_typos_still_match(window, expected):
    assert expected in extract_topics(window)


def test_every_typo_entry_maps_to_a_matching_canonical_form():
    for misspelling in load_typos():
        assert extract_topics(f"about the {misspelling} please"), misspelling


def test_iban_and_long_digit_runs_create_no_topics():
    assert extract_topics("Please pay to IBAN BE68 5390 0754 7034 before Friday") == []
    assert extract_topics("Reference 202610200001234567 and phone 0470 12 34 56") == []
    assert extract_topics("Account BE68539007547034") == []


def test_email_addresses_create_no_topics():
    assert extract_topics("Send it to preavis.payslip@sdworx.com today") == []
    assert extract_topics("contact jan.opzegtermijn@belgium.be") == []


@pytest.mark.parametrize("window", ["Under PC 200 the rule is", "Under PC200 the rule is", "onder pc 200"])
def test_joint_committee_extracts_to_pc_token(window):
    assert "PC_200" in extract_topics(window)


def test_joint_committee_needs_exactly_three_digits():
    assert extract_topics("PC 2000 euro") == []
    assert extract_topics("my PC is broken") == []


@pytest.mark.parametrize(
    ("window", "expected"),
    [
        ("an employee in Spain", "country_ES"),
        ("een werknemer in Spanje", "country_ES"),
        ("un employé en Espagne", "country_ES"),
        ("payroll in Belgium", "country_BE"),
        ("loonverwerking in België", "country_BE"),
        ("la paie en Belgique", "country_BE"),
        ("working in the Netherlands", "country_NL"),
        ("werken in Nederland", "country_NL"),
        ("travailler aux Pays-Bas", "country_NL"),
        ("moving to the UK", "country_UK"),
        ("verhuizen naar het Verenigd Koninkrijk", "country_UK"),
        ("déménager aux États-Unis", "country_US"),
    ],
)
def test_country_names_in_all_languages(window, expected):
    assert expected in extract_topics(window)


def test_short_patterns_need_capitals():
    assert extract_topics("I will look at it or not, the average is fine") == []
    assert "works_council" in extract_topics("Ask the OR about it")
    assert "social_security" in extract_topics("De RSZ-bijdragen")
    assert "country_UK" not in extract_topics("uk is not a word here")


def test_digit_patterns_match_before_numbers_are_masked():
    assert "year_end_bonus" in extract_topics("We pay the 13th month in December")
    assert "year_end_bonus" in extract_topics("De 13de maand wordt in december betaald")
    assert "dismissal" in extract_topics("een C4 is nodig")


@pytest.mark.parametrize(
    "window",
    [
        "I noticed the meeting moved to Friday",
        "Thanks to every employee who joined the call",
        "The integration with the new tool is done",
        "Our flight will depart at nine",
        "Ask your manager for approval",
        "Search the index of the document",
        "het vertrek van de trein is om negen uur",
        "Termination of the old server is planned",
        "Dans le cadre de ce projet, merci",
        "la sortie du nouveau produit",
        "I will look at it or not, the average is fine",
    ],
)
def test_everyday_sentences_have_no_topics(window):
    assert extract_topics(window) == []


def test_worker_classes():
    assert "worker_blue_collar" in extract_topics("is hij arbeider of bediende?")
    assert "worker_white_collar" in extract_topics("is hij arbeider of bediende?")
    assert "worker_executive" in extract_topics("pour un cadre supérieur")


SAMPLE_WINDOWS = [
    "What is the notice period for a white collar employee in Spain under PC 200?",
    "De opzegtermijn voor een bediende in Spanje, PC200, en de eindejaarspremie",
    "Le préavis pour un ouvrier en Belgique et les chèques-repas, PC 124",
    "Telework allowance, bike lease and the company car policy for the UK",
    "mail jan@sdworx.com about IBAN BE68 5390 0754 7034 and the GDPR datalek",
    "random words without any payroll content at all",
]


@pytest.mark.parametrize("window", SAMPLE_WINDOWS)
def test_every_returned_token_is_in_the_vocabulary(window):
    topics = extract_topics(window)
    assert topics == sorted(set(topics))
    for token in topics:
        assert is_vocab_token(token), token
        assert token in vocabulary() or token.startswith("PC_")


def test_no_window_text_in_output_or_logs(caplog):
    caplog.set_level(logging.DEBUG, logger="topic_extractor")
    window = "Zebrafinch opzegtermijn quokka@sdworx.com 987654 PC 200 in Spanje"
    topics = extract_topics(window)
    assert topics == ["PC_200", "country_ES", "notice_period"]
    logged = " ".join(record.getMessage() for record in caplog.records).lower()
    assert "extracted 3 topics" in logged
    for fragment in ["zebrafinch", "quokka", "opzegtermijn", "spanje", "987654", "sdworx"]:
        assert fragment not in logged


def _synthetic_window(length: int) -> str:
    text = " ".join(SAMPLE_WINDOWS) + " "
    return (text * (length // len(text) + 1))[:length]


def test_2000_char_window_runs_under_50_ms():
    window = _synthetic_window(2000)
    extract_topics(window)  # warm the stem cache, as during normal typing
    runs = 20
    started = time.perf_counter()
    for _ in range(runs):
        extract_topics(window)
    assert (time.perf_counter() - started) / runs * 1000 < 50


def test_shared_network_catalog_matches_extractor_vocabulary():
    """The backend and UI must accept precisely the same fixed topic ids as capture."""
    import json
    from pathlib import Path
    from topic_extractor import vocabulary
    catalog = json.loads((Path(__file__).resolve().parents[2] / "topic-catalog.json")
                         .read_text("utf-8"))
    assert {topic["token"] for topic in catalog} == set(vocabulary())
