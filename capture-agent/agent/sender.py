"""THE ONLY PLACE WHERE THE CAPTURE AGENT TALKS TO THE NETWORK.

Every payload leaves the machine through Sender.send(). Before anything is sent, check()
enforces the wire format: known keys only, numbers and flags for counts, strings only for
ids and categories, and topics only from the fixed vocabulary. Anything else is dropped.
"""

import json
import logging
import queue
import threading
import urllib.request

from topic_extractor import is_vocab_token

log = logging.getLogger(__name__)

# Keys that may be strings; every other key must be a number or a bool.
_STRING_KEYS = {"user_id", "context_id", "trigger", "surface"}
_ALLOWED_KEYS = _STRING_KEYS | {
    "ts", "pauses", "long_pauses", "time_since_last_key_ms", "context_age_ms",
    "chars_typed", "chars_deleted", "deletion_bursts", "rewrite_loops",
    "fluency_run_seconds", "longest_fluency_run_seconds", "hedge_words", "placeholders",
    "question_marks_written", "question_marks_in_prior_message", "window_switches_away",
    "paste_events", "pasted_char_count", "is_reply", "prior_message_char_count",
    "current_message_char_count", "baseline_avg_pause_ms", "baseline_avg_deletion_rate",
    "topics",
}
_MAX_STRING_LENGTH = 64
TIMEOUT_S = 2


def check(payload: dict) -> bool:
    """True if the payload holds only counts, flags, short ids/categories and vocabulary topics."""
    if set(payload) - _ALLOWED_KEYS:
        return False
    for key, value in payload.items():
        if key == "topics":
            if not isinstance(value, list) or not all(is_vocab_token(t) for t in value):
                return False
        elif key in _STRING_KEYS:
            if not isinstance(value, str) or len(value) > _MAX_STRING_LENGTH:
                return False
        elif not isinstance(value, (int, float, bool)):
            return False
    return True


class Sender:
    """Sends payloads on a background thread, so the keyboard path never waits on the network.

    With no `url`, nothing leaves the machine (demo mode). With `echo`, each payload is
    printed as the exact JSON that would be sent.
    """

    def __init__(self, url: str | None, echo: bool = True):
        self._url = url
        self._echo = echo
        self._queue: queue.Queue[dict | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.sent = 0
        self.rejected = 0
        self.failed = 0

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._queue.put(None)
        self._thread.join(timeout=TIMEOUT_S + 1)

    def send(self, payload: dict) -> None:
        """Queue a payload for sending. Payloads that fail check() are dropped."""
        if not check(payload):
            self.rejected += 1
            log.warning("dropped a payload that failed the wire-format check")
            return
        self._queue.put(payload)

    def _run(self) -> None:
        while (payload := self._queue.get()) is not None:
            body = json.dumps(payload, separators=(",", ":"))
            if self._echo:
                print(f"-> {body}", flush=True)
            if self._url is None:
                continue
            request = urllib.request.Request(
                self._url,
                data=body.encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=TIMEOUT_S):
                    self.sent += 1
            except OSError:
                self.failed += 1
                log.warning("sending a payload failed (%d failures so far)", self.failed)
