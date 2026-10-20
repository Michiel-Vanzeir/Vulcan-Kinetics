"""Tests for which apps, tabs and fields may be captured."""

import pytest

from agent.surfaces import is_sensitive_field, surface_name


@pytest.mark.parametrize(
    ("process", "title", "expected"),
    [
        ("ms-teams.exe", "Chat | Microsoft Teams", "teams_desktop"),
        ("olk.exe", "Mail - Sarah De Vos - Outlook", "outlook_desktop"),
        ("chrome.exe", "Inbox (3) - sarah@sdworx.com - Gmail - Google Chrome", "gmail_web"),
        ("msedge.exe", "Mail - Sarah - Outlook - Work - Microsoft Edge", "outlook_web"),
        ("firefox.exe", "Chat | Microsoft Teams — Mozilla Firefox", "teams_web"),
        ("chrome.exe", "KBC Online - Google Chrome", None),
        ("chrome.exe", "Gmail - Google Chrome (Incognito)", None),
        ("msedge.exe", "Gmail - Personal - Microsoft Edge", None),
        ("msedge.exe", "Gmail and 2 more pages - InPrivate - Microsoft Edge", None),
        ("spotify.exe", "Spotify Premium", None),
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
    ],
)
def test_is_sensitive_field(name, automation_id, expected):
    assert is_sensitive_field(name, automation_id) is expected
