"""Capture agent settings. Surfaces are opt-in: anything not listed is never captured."""

# About 4 KB of recent keystrokes, as in the spec.
BUFFER_CAPACITY = 4096

# Desktop apps: foreground process name (lowercase) -> surface name used in payloads.
PROCESS_SURFACES = {
    "ms-teams.exe": "teams_desktop",
    "teams.exe": "teams_desktop",
    "outlook.exe": "outlook_desktop",
    "olk.exe": "outlook_desktop",
    "winword.exe": "word_desktop",
    "powerpnt.exe": "powerpoint_desktop",
    "onenote.exe": "onenote_desktop",
    "slack.exe": "slack_desktop",
    "notion.exe": "notion_desktop",
}

BROWSER_PROCESSES = frozenset({
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "vivaldi.exe",
})

# Browser tabs are captured only when the window title shows a known work app,
# so banking, shopping and other personal pages are never captured.
# Checked in order against the lowercase window title; first match wins.
WEB_SURFACES = (
    ("gmail", "gmail_web"),
    ("microsoft teams", "teams_web"),
    ("outlook", "outlook_web"),
    ("google docs", "google_docs_web"),
    ("slack", "slack_web"),
    ("notion", "notion_web"),
    ("confluence", "confluence_web"),
    ("jira", "jira_web"),
    ("sharepoint", "sharepoint_web"),
    ("zendesk", "zendesk_web"),
    ("salesforce", "salesforce_web"),
    ("servicenow", "servicenow_web"),
)

# Window title fragments of private windows and personal browser profiles: never captured.
PRIVATE_WINDOW_MARKERS = ("inprivate", "incognito", "private browsing", "- personal -")

# Words in a field's accessible name or automation id that mark it as sensitive.
# Matched as whole words. The address bar is included because what people type there
# is browsing, not work writing.
SENSITIVE_FIELD_WORDS = (
    "password",
    "wachtwoord",
    "passcode",
    "pin",
    "cvv",
    "cvc",
    "card number",
    "kaartnummer",
    "iban",
    "social security",
    "rijksregisternummer",
    "national register",
    "address and search bar",
    "search or enter address",
    "urlbar",
)

ALL_SURFACES = frozenset(PROCESS_SURFACES.values()) | frozenset(name for _, name in WEB_SURFACES)

# Surfaces the employee has opted in to. Default: every known work surface.
DEFAULT_ALLOWED_SURFACES = ALL_SURFACES
