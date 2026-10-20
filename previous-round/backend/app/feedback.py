"""Peer feedback ("did they know their stuff?") and opaque expert references.

Clients never see employee IDs. Each expert in a response gets a `ref`: an HMAC of
(employee id, topic id) with a server secret. Feedback must send that ref back, and the
server resolves it only among the people it would show for that topic, so a client can't
vote for arbitrary employees, for opted-out people, or across topics.

Votes are kept in memory: a restart resets them, which is what we want for a demo.
"""

import hashlib
import hmac
import os
import secrets
from collections import defaultdict
from threading import Lock

_SECRET = (os.environ.get("WHOKNOWS_SECRET") or secrets.token_hex(32)).encode()
_votes: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"up": 0, "down": 0})
_lock = Lock()


def expert_ref(employee_id: str, topic_id: str) -> str:
    return hmac.new(_SECRET, f"{employee_id}:{topic_id}".encode(), hashlib.sha256).hexdigest()[:32]


def votes(employee_id: str, topic_id: str) -> dict[str, int]:
    with _lock:
        return dict(_votes.get((employee_id, topic_id), {"up": 0, "down": 0}))


def record_vote(employee_id: str, topic_id: str, helpful: bool) -> None:
    with _lock:
        _votes[(employee_id, topic_id)]["up" if helpful else "down"] += 1


def reset() -> None:
    with _lock:
        _votes.clear()
