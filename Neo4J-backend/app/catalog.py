"""Validate network topic ids against the repository's explicit payroll vocabulary."""

import json
import re
from pathlib import Path

CATALOG = json.loads((Path(__file__).resolve().parents[2] / "topic-catalog.json").read_text("utf-8"))
TOKENS = frozenset(item["token"] for item in CATALOG)


def valid_topic(token: str) -> bool:
    """Joint committees follow the vocabulary's bounded PC-number pattern."""
    return token in TOKENS or bool(re.fullmatch(r"PC_\d{3}", token))
