"""OS-independent rules for which app, tab and field may be captured."""

import re

from agent.config import (
    BROWSER_PROCESSES,
    PRIVATE_WINDOW_MARKERS,
    PROCESS_SURFACES,
    SENSITIVE_FIELD_WORDS,
    WEB_SURFACES,
)

_SENSITIVE_FIELD = re.compile(
    r"\b(" + "|".join(re.escape(word) for word in SENSITIVE_FIELD_WORDS) + r")\b"
)


def surface_name(process: str, window_title: str) -> str | None:
    """Surface for the foreground window, or None if it must not be captured."""
    if process in BROWSER_PROCESSES:
        title = window_title.lower()
        if any(marker in title for marker in PRIVATE_WINDOW_MARKERS):
            return None
        return next((name for marker, name in WEB_SURFACES if marker in title), None)
    return PROCESS_SURFACES.get(process)


def is_sensitive_field(name: str, automation_id: str) -> bool:
    """True if the field's label or id suggests credentials or personal data."""
    # Split camelCase ids like "cardNumber" so whole-word matching works.
    automation_id = re.sub(r"([a-z])([A-Z])", r"\1 \2", automation_id)
    label = f"{name} {automation_id}".replace("_", " ").replace("-", " ").lower()
    return _SENSITIVE_FIELD.search(label) is not None
