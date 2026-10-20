"""Seed the expertise filter's store with synthetic answering history. Usage: python seed_signals.py [--reset]

Live typing never counts as answering yet (the agent can't see the message being replied to),
so without this /experts answers "nobody" in the demo. Every payload goes through
ExpertiseFilter.process(), the same path POST /analyze uses. The people match the panel's
fixtures in preview-api.mjs. Tom's history is from 2024, so recency decay keeps him out of
/experts: stale expertise is never presented as current. Run it before starting run.py.
"""
import sys
import time
from pathlib import Path

import expertise_filter
from app.signals import DIRECTORY_PATH, FILTER_DB_PATH

DAY_MS = 86_400_000

# user_id -> (topics, [(days_ago, surface), ...]) for confident answers on those topics.
HISTORY = {
    "emp_021": (["year_end_bonus", "PC_200", "payslip"], [
        (25, "outlook_desktop"), (18, "teams_desktop"), (12, "word_desktop"),
        (7, "outlook_desktop"), (3, "teams_desktop"),
    ]),
    "emp_045": (["year_end_bonus", "PC_200"], [
        (640, "word_desktop"), (610, "outlook_desktop"), (590, "outlook_desktop"),
    ]),
    "emp_077": (["notice_period", "dismissal", "country_BE"], [
        (27, "outlook_desktop"), (15, "word_desktop"), (6, "teams_desktop"), (2, "outlook_desktop"),
    ]),
    "emp_088": (["country_FR", "payslip"], [
        (26, "outlook_desktop"), (19, "teams_desktop"), (13, "outlook_desktop"),
        (8, "teams_desktop"), (4, "outlook_desktop"),
    ]),
}


def answering_payload(user_id: str, context_id: str, ts: int, surface: str,
                      topics: list[str]) -> dict:
    """A long, fluent reply to a short message: what the filter credits as expertise."""
    return {
        "user_id": user_id, "context_id": context_id, "ts": ts, "trigger": "submit",
        "surface": surface, "is_reply": True, "prior_message_char_count": 140,
        "current_message_char_count": 620, "chars_typed": 640, "chars_deleted": 20,
        "pauses": 2, "context_age_ms": 95_000, "fluency_run_seconds": 22.0,
        "longest_fluency_run_seconds": 38.0, "baseline_avg_pause_ms": 450,
        "baseline_avg_deletion_rate": 0.05, "topics": topics,
    }


def main() -> None:
    db_path = Path(FILTER_DB_PATH)
    if "--reset" in sys.argv and db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            sys.exit(f"{db_path} is in use. Stop the backend (run.py) first, then re-run.")
    store = expertise_filter.PersonStore(db_path)
    if store.all_user_ids():
        sys.exit(f"{db_path} already has people. Re-run with --reset to wipe and reseed.")
    flt = expertise_filter.ExpertiseFilter(store, expertise_filter.load_directory(DIRECTORY_PATH))

    now_ms = int(time.time() * 1000)
    contexts = [(now_ms - days * DAY_MS, user_id, surface, topics)
                for user_id, (topics, sessions) in HISTORY.items()
                for days, surface in sessions]
    # Oldest first, so each new answer decays the evidence accumulated before it.
    for n, (ts, user_id, surface, topics) in enumerate(sorted(contexts)):
        flt.process(answering_payload(user_id, f"seed_{n}", ts, surface, topics))

    print(f"Seeded {len(contexts)} answers into {db_path}.")
    for user_id, (topics, _) in HISTORY.items():
        name = (store.get(user_id)["profile"] or {}).get("name", user_id)
        for topic in topics:
            is_expert, score, _ = flt.is_expert(user_id, topic)
            print(f"  {name:<14} {topic:<15} {'expert' if is_expert else 'not shown':<9} {score:.2f}")
    store.close()


if __name__ == "__main__":
    main()
