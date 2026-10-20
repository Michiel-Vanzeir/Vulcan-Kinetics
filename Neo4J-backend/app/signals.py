"""Ingestion routes for the capture agent: POST /analyze and POST /experts.

POST /analyze
    Body: one capture-agent payload (SignalPayloadIn below). Counts, flags, ids and
    topic tokens only.
    200 -> {"accepted": true, "tip": null | {"author", "recipient", "topic", "score", "reasons"}}
    400 -> {"error": "validation", "details": [...]}

POST /experts
    Body: {"topics": ["notice_period", "country_ES"], "exclude_user_id": "emp_003" (optional),
           "limit": 5 (optional)}
    200 -> {"experts": [{"user_id", "topic", "score", "reasons", "profile"}]}, best first
    400 -> {"error": "validation", "details": [...]}

Both hand off to the expertise filter (expertise_filter.py), which owns all scoring and storage.
Nothing here logs payload content: only counts and categories.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Any, Literal

from flask import Blueprint, jsonify, request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import expertise_filter

log = logging.getLogger(__name__)
bp = Blueprint("signals", __name__)

_BACKEND_DIR = Path(__file__).resolve().parents[1]
FILTER_DB_PATH = os.getenv("WHOKNOWS_FILTER_DB", str(_BACKEND_DIR / "whoknows.db"))
DIRECTORY_PATH = os.getenv("WHOKNOWS_DIRECTORY", str(_BACKEND_DIR / "directory.json"))

# Ids, categories and topic tokens: short, no spaces, so they can't carry a sentence.
_ID = r"^[A-Za-z0-9_.:-]{1,64}$"
_CATEGORY = r"^[a-z0-9_]{1,40}$"
_TOPIC = r"^[A-Za-z][A-Za-z0-9_]{0,63}$"
Trigger = Literal[
    "pause", "deletion_burst", "punctuation", "hedge", "placeholder", "idle_flush", "manual", "submit"
]
Count = Field(default=0, ge=0)
Topic = Annotated[str, Field(pattern=_TOPIC)]


class SignalPayloadIn(BaseModel):
    """The capture agent's wire format. Unknown keys and free-text strings are rejected.

    TODO: deduplicate with expertise_filter.SignalPayload once the schema settles.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(pattern=_ID)
    context_id: str = Field(pattern=_ID)
    ts: int = Field(ge=0)
    trigger: Trigger
    surface: str = Field(default="other", pattern=_CATEGORY)
    is_reply: bool = False
    prior_message_char_count: int = Count
    current_message_char_count: int = Count
    pauses: int = Count
    long_pauses: int = Count
    time_since_last_key_ms: int = Count
    context_age_ms: int = Count
    chars_typed: int = Count
    chars_deleted: int = Count
    deletion_bursts: int = Count
    rewrite_loops: int = Count
    fluency_run_seconds: float = Field(default=0.0, ge=0)
    longest_fluency_run_seconds: float = Field(default=0.0, ge=0)
    hedge_words: int = Count
    placeholders: int = Count
    question_marks_written: int = Count
    question_marks_in_prior_message: int = Count
    window_switches_away: int = Count
    paste_events: int = Count
    pasted_char_count: int = Count
    baseline_avg_pause_ms: int = Count
    baseline_avg_deletion_rate: float = Field(default=0.0, ge=0)
    topics: list[Topic] = Field(default_factory=list, max_length=50)


class ExpertsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[Topic] = Field(min_length=1, max_length=20)
    exclude_user_id: str | None = Field(default=None, pattern=_ID)
    limit: int = Field(default=5, ge=1, le=50)


# The filter's SQLite connection may only be used by the thread that created it, while Flask
# serves each request on its own thread. So the filter lives on, and is only called from, one
# dedicated thread.
_filter_thread = ThreadPoolExecutor(max_workers=1, thread_name_prefix="expertise-filter")
_store: expertise_filter.PersonStore | None = None
_filter: expertise_filter.ExpertiseFilter | None = None


def _get_filter() -> expertise_filter.ExpertiseFilter:
    """Build the filter on first use, on the filter thread (same as build_filter(), keeping the store)."""
    global _store, _filter
    if _filter is None:
        path = Path(DIRECTORY_PATH)
        directory = expertise_filter.load_directory(path) if path.exists() else {}
        _store = expertise_filter.PersonStore(FILTER_DB_PATH)
        _filter = expertise_filter.ExpertiseFilter(_store, directory)
    return _filter


def _on_filter_thread(fn, *args):
    return _filter_thread.submit(fn, *args).result()


def _process(payload: dict[str, Any]) -> dict[str, Any] | None:
    return _get_filter().process(payload)


def _rank_experts(topics: list[str], exclude: str | None, limit: int) -> list[dict[str, Any]]:
    """Every known person the filter rates as an expert on one of the topics, best first."""
    flt = _get_filter()
    experts = []
    for user_id in _store.all_user_ids():
        if user_id == exclude:
            continue
        for topic in topics:
            is_expert, score, reasons = flt.is_expert(user_id, topic)
            if is_expert:
                profile = (_store.get(user_id) or {}).get("profile")
                experts.append(
                    {"user_id": user_id, "topic": topic, "score": round(score, 3),
                     "reasons": reasons, "profile": profile}
                )
    experts.sort(key=lambda e: e["score"], reverse=True)
    return experts[:limit]


# THE FUNCTION THAT CROSSES THE NETWORK BOUNDARY (backend side): payloads from agents land here.
@bp.post("/analyze")
def analyze():
    """Accept one capture-agent payload and hand it to the expertise filter.

    Privacy invariants: the payload holds no raw text. The schema has no field for it, unknown
    keys are rejected, and every string must be a short id, category or vocabulary token
    (no spaces), so a sentence can't pass validation. Only counts and categories are logged,
    never the payload.
    """
    payload = SignalPayloadIn.model_validate(request.get_json(force=True, silent=True) or {})
    tip = _on_filter_thread(_process, payload.model_dump())
    log.info("received payload for %s: trigger=%s, %d topics, tip=%s",
             payload.user_id, payload.trigger, len(payload.topics), tip is not None)
    return jsonify({"accepted": True, "tip": tip})


@bp.post("/experts")
def experts():
    """Ranked experts for a list of topic tokens. The request holds topic tokens only."""
    body = ExpertsIn.model_validate(request.get_json(force=True, silent=True) or {})
    ranked = _on_filter_thread(_rank_experts, body.topics, body.exclude_user_id, body.limit)
    log.info("experts request: %d topics, %d experts", len(body.topics), len(ranked))
    return jsonify({"experts": ranked})


@bp.errorhandler(ValidationError)
def _validation(error: ValidationError):
    details = [{"loc": list(e["loc"]), "type": e["type"]} for e in error.errors()]
    return jsonify({"error": "validation", "details": details}), 400

