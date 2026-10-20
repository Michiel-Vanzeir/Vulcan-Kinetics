"""Tests for agent.transport and agent.config, against a local HTTP server."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from agent.config import AgentConfig, load_config
from agent.transport import Transport
from conftest import make_payload


class FakeBackend:
    """Records requests; answers with queued status codes (default 200) after `delay_s`."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.statuses: list[int] = []
        self.delay_s = 0.0
        self.experts = [{"user_id": "emp_021", "topic": "notice_period", "score": 0.81}]
        backend = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                backend.requests.append(
                    {"path": self.path, "body": body, "auth": self.headers.get("Authorization")}
                )
                time.sleep(backend.delay_s)
                status = backend.statuses.pop(0) if backend.statuses else 200
                reply = {"experts": backend.experts} if self.path == "/experts" else {"accepted": True}
                data = json.dumps(reply).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture(autouse=True)
def fast_timeouts(monkeypatch):
    monkeypatch.setattr("agent.transport.TIMEOUT_S", 0.5)
    monkeypatch.setattr("agent.transport.RETRY_DELAY_S", 0.01)


@pytest.fixture
def backend():
    server = FakeBackend()
    yield server
    server.close()


def config_for(backend: FakeBackend, token: str | None = None) -> AgentConfig:
    return AgentConfig(backend_url=backend.url, user_id="emp_014", auth_token=token)


def test_payload_is_serialized_to_the_wire_format(backend):
    transport = Transport(config_for(backend))
    transport.send(make_payload())
    transport.close()
    [request] = backend.requests
    assert request["path"] == "/analyze"
    body = request["body"]
    assert body["user_id"] == "emp_014"
    assert body["trigger"] == "hedge"
    assert body["hedge_words"] == 1
    assert body["chars_typed"] == 6
    assert body["topics"] == ["country_ES", "notice_period"]
    assert "maybe" not in json.dumps(body)


def test_successful_send_with_bearer_token(backend):
    transport = Transport(config_for(backend, token="s3cret"))
    transport.send(make_payload())
    transport.close()
    assert transport.sent == 1
    assert transport.retried == 0
    assert backend.requests[0]["auth"] == "Bearer s3cret"


def test_failure_is_retried_once(backend):
    backend.statuses = [500, 200]
    transport = Transport(config_for(backend))
    transport.send(make_payload())
    transport.close()
    assert (transport.sent, transport.retried, transport.dropped) == (1, 1, 0)
    assert len(backend.requests) == 2


def test_second_failure_drops_the_payload(backend):
    backend.statuses = [500, 503]
    transport = Transport(config_for(backend))
    transport.send(make_payload())
    transport.close()
    assert (transport.sent, transport.retried, transport.dropped) == (0, 1, 1)


def test_refused_payload_is_not_retried(backend):
    backend.statuses = [400]
    transport = Transport(config_for(backend))
    transport.send(make_payload())
    transport.close()
    assert (transport.sent, transport.retried, transport.dropped) == (0, 0, 1)
    assert len(backend.requests) == 1


def test_unreachable_backend_drops_without_raising():
    transport = Transport(AgentConfig(backend_url="http://127.0.0.1:9", user_id="emp_014"))
    transport.send(make_payload())
    transport.close()
    assert transport.dropped == 1


def test_send_does_not_block_on_a_slow_backend(backend):
    backend.delay_s = 1.0
    transport = Transport(config_for(backend))
    started = time.perf_counter()
    for _ in range(3):
        transport.send(make_payload())
    assert time.perf_counter() - started < 0.2
    transport.close()


def test_demo_mode_sends_nothing(backend):
    transport = Transport(AgentConfig(backend_url=None, user_id="emp_014"))
    transport.send(make_payload())
    assert transport.request_experts(["notice_period"]) == []
    transport.close()
    assert backend.requests == []


def test_payload_failing_the_check_is_rejected(backend):
    transport = Transport(config_for(backend))
    transport.send(make_payload(topics=("the user typed this",)))
    transport.close()
    assert transport.rejected == 1
    assert backend.requests == []


def test_experts_round_trip(backend):
    transport = Transport(config_for(backend))
    experts = transport.request_experts(["notice_period", "free text here", "country_ES"])
    transport.close()
    assert experts == backend.experts
    [request] = backend.requests
    assert request["path"] == "/experts"
    assert request["body"] == {
        "topics": ["country_ES", "notice_period"],
        "exclude_user_id": "emp_014",
    }


def test_experts_unavailable_returns_empty_list():
    transport = Transport(AgentConfig(backend_url="http://127.0.0.1:9", user_id="emp_014"))
    assert transport.request_experts(["notice_period"]) == []
    transport.close()


def test_load_config_from_env_file_and_environment(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\nWHOKNOWS_BACKEND_URL=http://example.test:5000/\nWHOKNOWS_USER_ID=emp_003\n",
        encoding="utf-8",
    )
    config = load_config(env={"WHOKNOWS_AUTH_TOKEN": "tok", "WHOKNOWS_USER_ID": "emp_021"},
                         env_file=env_file)
    assert config == AgentConfig("http://example.test:5000", "emp_021", "tok")
    assert load_config(env={}, env_file=tmp_path / "missing") == AgentConfig(None, "emp_014", None)
