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
    ("freshdesk", "freshdesk_web"),
    ("hubspot", "hubspot_web"),
    ("intercom", "intercom_web"),
    ("workday", "workday_web"),
    ("successfactors", "successfactors_web"),
    ("google chat", "google_chat_web"),
    ("viva engage", "viva_engage_web"),
    ("asana", "asana_web"),
    ("trello", "trello_web"),
    ("clickup", "clickup_web"),
    ("azure devops", "azure_devops_web"),
    ("github", "github_web"),
    ("gitlab", "gitlab_web"),
)

# Window title fragments of private windows and personal browser profiles: never captured.
# Includes the Dutch, French and German browser UI, since titles follow the UI language.
PRIVATE_WINDOW_MARKERS = (
    "inprivate",
    "incognito",
    "inkognito",
    "(private)",
    "private browsing",
    "privénavigatie",
    "navigation privée",
    "privater modus",
    "- personal -",
    "- persoonlijk -",
    "- personnel -",
    "- persönlich -",
)

# Words in a field's accessible name or automation id that mark it as sensitive.
# Matched as whole words, case- and accent-insensitive, in EN/NL/FR/DE. The address bar
# is included because what people type there is browsing, not work writing.
SENSITIVE_FIELD_WORDS = (
    # Credentials
    "password",
    "passwort",
    "wachtwoord",
    "mot de passe",
    "kennwort",
    "passcode",
    "passphrase",
    "pin",
    "pincode",
    "pin code",
    "code pin",
    "geheime code",
    "security code",
    "verification code",
    "verificatiecode",
    "code de verification",
    "bestatigungscode",
    "one time code",
    "otp",
    "2fa",
    "mfa",
    "authenticator",
    "recovery code",
    "secret",
    "api key",
    "apikey",
    "private key",
    # Payment cards
    "cvv",
    "cvv2",
    "cvc",
    "cvc2",
    "card number",
    "cardnumber",
    "kaartnummer",
    "numero de carte",
    "kartennummer",
    "credit card",
    "creditcard",
    "kredietkaart",
    "carte bancaire",
    "bankkaart",
    "expiry",
    "expiration",
    # Bank accounts
    "iban",
    "account number",
    "rekeningnummer",
    "numero de compte",
    "kontonummer",
    "routing number",
    "sort code",
    # National identifiers
    "social security",
    "ssn",
    "rijksregisternummer",
    "rijksregister",
    "national register",
    "insz",
    "niss",
    "numero national",
    "bsn",
    "burgerservicenummer",
    "sofinummer",
    "sozialversicherungsnummer",
    "steuer id",
    "steueridentifikationsnummer",
    "tax id",
    "passport",
    "paspoort",
    "passeport",
    "reisepass",
    # Browser address bar
    "address and search bar",
    "search or enter address",
    "urlbar",
)

ALL_SURFACES = frozenset(PROCESS_SURFACES.values()) | frozenset(name for _, name in WEB_SURFACES)

# Surfaces the employee has opted in to. Default: every known work surface.
DEFAULT_ALLOWED_SURFACES = ALL_SURFACES
