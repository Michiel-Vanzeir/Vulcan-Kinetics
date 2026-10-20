"""Tests for which apps, tabs and fields may be captured."""

import pytest

from agent.surfaces import is_sensitive_field, surface_name


@pytest.mark.parametrize(
    ("process", "title", "expected"),
    [
        ("ms-teams.exe", "Chat | Microsoft Teams", "teams_desktop"),
        ("olk.exe", "Mail - Sarah De Vos - Outlook", "outlook_desktop"),
        ("chrome.exe", "Inbox (3) - sarah@sdworx.com - Gmail - Google Chrome", None),
        ("msedge.exe", "Mail - Sarah - Outlook - Work - Microsoft Edge", None),
        ("firefox.exe", "Chat | Microsoft Teams — Mozilla Firefox", None),
        ("chrome.exe", "KBC Online - Google Chrome", None),
        ("chrome.exe", "Gmail - Google Chrome (Incognito)", None),
        ("msedge.exe", "Gmail - Personal - Microsoft Edge", None),
        ("msedge.exe", "Gmail and 2 more pages - InPrivate - Microsoft Edge", None),
        ("spotify.exe", "Spotify Premium", None),
        ("chrome.exe", "Ticket #123 - Freshdesk - Google Chrome", None),
        ("brave.exe", "Gmail - Brave (Private)", None),
        ("firefox.exe", "Gmail — Mozilla Firefox Privénavigatie", None),
        ("chrome.exe", "Gmail - Google Chrome (Navigation privée)", None),
        ("msedge.exe", "Gmail - Persoonlijk - Microsoft Edge", None),
    ],
)
def test_surface_name(process, title, expected):
    assert surface_name(process, title) == expected


@pytest.mark.parametrize(
    ("name", "automation_id", "expected"),
    [
        ("Password", "", True),
        ("", "cardNumber", True),
        ("Enter your PIN", "", True),
        ("IBAN", "iban_input", True),
        ("Address and search bar", "", True),
        ("", "urlbar-input", True),
        ("Type a message", "", False),
        ("Message body", "", False),
        ("Opinion", "spinner", False),
        ("Mot de passe", "", True),
        ("Numéro de carte", "", True),
        ("Bestätigungscode", "", True),
        ("Rekeningnummer", "", True),
        ("", "otpInput", True),
        ("Verification code", "", True),
        ("Subject", "subjectLine", False),
        ("Nachricht", "", False),
        ("Objet", "", False),
    ],
)
def test_is_sensitive_field(name, automation_id, expected):
    assert is_sensitive_field(name, automation_id) is expected
