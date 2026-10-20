"""OS-independent rules for which app, tab and field may be captured."""

import re
import unicodedata
from dataclasses import dataclass

from agent.config import BROWSER_PROCESSES, PROCESS_SURFACES, SENSITIVE_FIELD_WORDS

@dataclass(frozen=True, slots=True)
class Surface:
    """The focused text field: a stable id, the surface name and whether to skip it."""

    id: str
    name: str
    is_sensitive: bool


_SENSITIVE_FIELD = re.compile(
    r"\b(" + "|".join(re.escape(word) for word in SENSITIVE_FIELD_WORDS) + r")\b"
)


def surface_name(process: str, window_title: str) -> str | None:
    """Surface for the foreground window, or None if it must not be captured."""
    if process in BROWSER_PROCESSES:
        # A page title cannot establish its origin or whether this is a work profile.
        return None
    return PROCESS_SURFACES.get(process)


def is_sensitive_field(name: str, automation_id: str) -> bool:
    """True if the field's label or id suggests credentials or personal data."""
    # Split camelCase ids like "cardNumber" so whole-word matching works.
    automation_id = re.sub(r"([a-z])([A-Z])", r"\1 \2", automation_id)
    label = f"{name} {automation_id}".replace("_", " ").replace("-", " ").lower()
    # Strip accents so "Numéro de carte" and "Bestätigungscode" match the plain list entries.
    label = "".join(c for c in unicodedata.normalize("NFKD", label) if not unicodedata.combining(c))
    return _SENSITIVE_FIELD.search(label) is not None
