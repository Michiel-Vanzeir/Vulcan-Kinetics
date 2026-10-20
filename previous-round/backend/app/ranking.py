"""Expert ranking with trust signals.

score = relevance + recency + frequency + peer recognition - unhelpful votes
Consent is enforced here, server-side: people who opted out, or who hid a topic,
are dropped before scoring and never leave the backend.
"""

import math
from datetime import date

from . import feedback

W_RELEVANCE = 1.0
W_RECENCY = 3.0
W_FREQUENCY = 1.0
W_PEER = 0.6
W_UNHELPFUL = 0.8
RECENCY_HALF_LIFE_DAYS = 120
STALE_AFTER_DAYS = 365
GAP_THRESHOLD = 2.5  # best score below this -> knowledge gap
TOP_N = 3


def _tokens(text: str) -> set[str]:
    return {w for w in text.lower().replace("-", " ").split() if len(w) > 2}


def visible_evidence(employee: dict, topic_id: str) -> list[dict]:
    if not employee.get("opt_in") or topic_id in employee.get("hidden_topics", []):
        return []
    return [e for e in employee["evidence"] if e["topic"] == topic_id]


def ago_label(days: int) -> str:
    if days < 1:
        return "today"
    if days < 14:
        return f"{days} day{'s' if days != 1 else ''} ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    if days < 365:
        return f"{days // 30} months ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def score_employee(evidence: list[dict], query: str, today: date, votes: dict[str, int]) -> dict:
    last = max(date.fromisoformat(e["date"]) for e in evidence)
    days = (today - last).days
    vouchers = {v for e in evidence for v in e.get("vouched_by", [])}
    vouches = len(vouchers) + votes["up"]
    query_tokens = _tokens(query)
    relevance = max((len(query_tokens & _tokens(e["text"])) / max(len(_tokens(e["text"])), 1) for e in evidence), default=0)

    score = (W_RELEVANCE * relevance
             + W_RECENCY * math.exp(-math.log(2) * days / RECENCY_HALF_LIFE_DAYS)
             + W_FREQUENCY * math.log1p(len(evidence))
             + W_PEER * math.log1p(vouches)
             - W_UNHELPFUL * math.log1p(votes["down"]))
    return {"score": round(score, 2), "days": days, "last": last, "count": len(evidence), "vouches": vouches, "unhelpful": votes["down"]}


def highlight(evidence: list[dict]) -> str:
    authored = [e for e in evidence if e.get("author")]
    pick = authored[0] if authored else max(evidence, key=lambda e: e["date"])
    return pick["text"]


def initials(name: str) -> str:
    parts = name.split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else name[:2].upper()


def trust_signals(s: dict) -> dict:
    stale = s["days"] > STALE_AFTER_DAYS
    return {
        "count": s["count"],
        "last_active": s["last"].isoformat(),
        "last_active_label": ago_label(s["days"]),
        "vouches": s["vouches"],
        "unhelpful": s["unhelpful"],
        "stale": stale,
        "stale_since": s["last"].year if stale else None,
    }


def find_by_ref(topic_id: str, ref: str, employees: list[dict]) -> dict | None:
    """Resolve an opaque ref, only among people who may be shown for this topic."""
    for emp in employees:
        if visible_evidence(emp, topic_id) and feedback.expert_ref(emp["id"], topic_id) == ref:
            return emp
    return None


def trust_for(emp: dict, topic_id: str, today: date) -> dict:
    s = score_employee(visible_evidence(emp, topic_id), "", today, feedback.votes(emp["id"], topic_id))
    return trust_signals(s)


def rank_experts(topic: dict, employees: list[dict], query: str, today: date) -> dict:
    ranked = []
    for emp in employees:
        evidence = visible_evidence(emp, topic["id"])
        if not evidence:
            continue
        s = score_employee(evidence, query, today, feedback.votes(emp["id"], topic["id"]))
        ranked.append({
            # Only public profile fields leave the backend: no internal IDs, no voucher identities.
            "ref": feedback.expert_ref(emp["id"], topic["id"]),
            "name": emp["name"],
            "role": emp["role"],
            "country": emp["country"],
            "initials": initials(emp["name"]),
            "score": s["score"],
            "highlight": highlight(evidence),
            "authored": any(e.get("author") for e in evidence),
            "trust": trust_signals(s),
        })
    ranked.sort(key=lambda r: r["score"], reverse=True)

    best = ranked[0]["score"] if ranked else 0
    return {
        "topic": {"id": topic["id"], "label": topic["label"], "answer": topic.get("answer", "")},
        "knowledge_gap": best < GAP_THRESHOLD,
        "experts": ranked[:TOP_N],
    }
