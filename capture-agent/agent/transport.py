"""THE ONLY PLACE WHERE THE CAPTURE AGENT TALKS TO THE NETWORK.

Transport.send() converts a SignalPayload (topics already filled in) to the backend's wire
format, checks it, and POSTs it to <backend>/analyze on a background thread: fire-and-forget,
one retry, then drop. When the backend answers with a doubt_alert (the user is struggling
with this draft), its vocabulary topics go to the `on_doubt` callback. Transport.request_experts() POSTs topic tokens to <backend>/experts and
waits for the answer.

Before anything is sent, check() enforces the wire format: known keys only, numbers and flags
for counts, strings only for short ids and categories, topics only from the fixed vocabulary.
Logging is counts only, never payload content.
"""

import json
import logging
import queue
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from agent.backend_payload import BackendPayloads
from agent.config import AgentConfig
from signal_detector import SignalPayload
from topic_extractor import is_vocab_token

log = logging.getLogger(__name__)

TIMEOUT_S = 2.0
RETRY_DELAY_S = 0.2

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


def check(payload: dict[str, Any]) -> bool:
    """True if the payload holds only counts, flags, short ids/categories and vocabulary topics."""
    if set(payload) - _ALLOWED_KEYS:
        return False
    for key, value in payload.items():
        if key == "topics":
            if not isinstance(value, list) or not all(is_vocab_token(t) for t in value):
                return False
        elif key in _STRING_KEYS:
            if not isinstance(value, str) or len(value) > _MAX_STRING_LENGTH or " " in value:
                return False
        elif not isinstance(value, (int, float, bool)):
            return False
    return True


class Transport:
    """Sends payloads to the backend and asks it for experts.

    Without a backend URL nothing leaves the machine (demo mode). With `echo`, every payload
    is printed as the exact JSON that would be sent.
    """

    def __init__(
        self,
        config: AgentConfig,
        echo: bool = False,
        on_doubt: Callable[[list[str]], None] | None = None,
    ):
        self._config = config
        self._echo = echo
        self._on_doubt = on_doubt
        self._converter = BackendPayloads()
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=128)
        self._thread = threading.Thread(target=self._run, daemon=True, name="transport")
        self._thread.start()
        self.sent = 0
        self.retried = 0
        self.dropped = 0
        self.rejected = 0
        self._consent = frozenset()
        self._consent_at = 0.0
        self._hidden = frozenset()
        self._closing = threading.Event()

    def start_consent_polling(self) -> None:
        """Keep a short-lived consent cache; network failures immediately disable capture."""
        def poll():
            while not self._closing.is_set():
                try:
                    preferences = self._post("/preferences", None)
                    self._hidden = frozenset(preferences.get("hidden_topics", []))
                    self._consent = frozenset(preferences.get("allowed_surfaces", [])) \
                        if preferences.get("capture_enabled") else frozenset()
                    self._consent_at = time.monotonic()
                except (OSError, ValueError):
                    self._consent = frozenset()
                self._closing.wait(1)
        threading.Thread(target=poll, daemon=True, name="consent").start()

    def capture_policy(self) -> frozenset[str]:
        """Never capture using stale or unavailable consent."""
        return self._consent if time.monotonic() - self._consent_at < 2.5 else frozenset()

    def send(self, payload: SignalPayload) -> None:
        """Queue one payload for /analyze and return immediately (fire-and-forget).

        Privacy invariants: only the wire format leaves the machine, which holds no raw text
        (counts, flags, ids, categories, vocabulary topic tokens). Payloads failing check()
        are dropped. Nothing about the payload content is logged.
        """
        body = self._converter.convert(payload)
        body["topics"] = [topic for topic in body["topics"] if topic not in self._hidden]
        if not check(body):
            self.rejected += 1
            log.warning("dropped a payload that failed the wire-format check")
            return
        if self._echo:
            print(f"-> {json.dumps(body, separators=(',', ':'))}", flush=True)
        if self._config.backend_url is not None:
            try:
                self._queue.put_nowait(body)
            except queue.Full:
                self.dropped += 1

    def request_experts(self, topics: list[str]) -> list[dict[str, Any]]:
        """Ranked experts for topic tokens from /experts. Blocks; returns [] when unavailable.

        Only vocabulary topic tokens are sent, never free text.
        """
        topics = sorted({t for t in topics if is_vocab_token(t)})
        if not topics or self._config.backend_url is None:
            return []
        body = {"topics": topics, "exclude_user_id": self._config.user_id}
        try:
            return list(self._post("/experts", body).get("experts", []))
        except (OSError, ValueError):
            log.warning("experts request failed")
            return []

    def close(self) -> None:
        """Send what is queued, then stop the background thread."""
        self._closing.set()
        self._queue.put(None)
        self._thread.join(timeout=2 * (TIMEOUT_S + RETRY_DELAY_S) + 1)

    def _run(self) -> None:
        while (body := self._queue.get()) is not None:
            for attempt in range(2):
                try:
                    response = self._post("/analyze", body)
                except (OSError, ValueError) as error:
                    # A 4xx means the payload itself was refused; sending it again won't help.
                    refused = isinstance(error, urllib.error.HTTPError) and error.code < 500
                    if attempt == 0 and not refused:
                        self.retried += 1
                        time.sleep(RETRY_DELAY_S)
                        continue
                    self.dropped += 1
                    log.warning("dropped a payload after a retry (%d dropped so far)", self.dropped)
                else:
                    self.sent += 1
                    self._handle_response(response)
                break

    def _handle_response(self, response: dict[str, Any]) -> None:
        tip = response.get("tip")
        if self._echo and tip:
            print(f"<- tip: {tip.get('author')} knows {tip.get('topic')}", flush=True)
        alert = response.get("doubt_alert")
        if not isinstance(alert, dict):
            return
        topics = [t for t in alert.get("topics") or [] if isinstance(t, str) and is_vocab_token(t)]
        if self._echo:
            print(f"<- doubt: struggling with {topics or 'an unknown topic'}", flush=True)
        if self._on_doubt is not None:
            self._on_doubt(topics)

    # THE FUNCTION THAT CROSSES THE NETWORK BOUNDARY (agent side): every request goes through here.
    def _post(self, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self._config.auth_token:
            headers["Authorization"] = f"Bearer {self._config.auth_token}"
        request = urllib.request.Request(
            f"{self._config.backend_url}{path}",
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers=headers,
            method="POST" if body is not None else "GET",
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return json.loads(response.read() or b"{}")
