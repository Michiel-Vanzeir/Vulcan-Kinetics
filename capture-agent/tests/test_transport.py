"""Tests for agent.transport and agent.config, against a local HTTP server."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from agent.config import AgentConfig, load_config
from agent.transport import Transport, backend_address
from conftest import make_payload


class FakeBackend:
    """Records requests; answers with queued status codes (default 200) after `delay_s`."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.statuses: list[int] = []
        self.delay_s = 0.0
        self.experts = [{"user_id": "emp_021", "topic": "notice_period", "score": 0.81}]
        self.analysis: dict = {"accepted": True}
        self.redirect_to = None
        backend = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                backend.requests.append(
                    {"path": self.path, "body": body, "auth": self.headers.get("Authorization")}
                )
                time.sleep(backend.delay_s)
                status = backend.statuses.pop(0) if backend.statuses else 200
                reply = {"experts": backend.experts} if self.path == "/experts" else backend.analysis
                data = json.dumps(reply).encode()
                self.send_response(status)
                if backend.redirect_to:
                    self.send_header("Location", backend.redirect_to)
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


def test_doubt_alert_hands_vocabulary_topics_to_callback(backend):
    backend.analysis = {
        "accepted": True,
        "doubt_alert": {"doubt": 0.7, "topics": ["notice_period", "not a token"]},
    }
    doubts: list[list[str]] = []
    transport = Transport(config_for(backend), on_doubt=doubts.append)
    transport.send(make_payload())
    transport.close()
    assert doubts == [["notice_period"]]


def test_no_doubt_alert_no_callback(backend):
    backend.analysis = {"accepted": True, "tip": None, "doubt_alert": None}
    doubts: list[list[str]] = []
    transport = Transport(config_for(backend), on_doubt=doubts.append)
    transport.send(make_payload())
    transport.close()
    assert doubts == []


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


@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data", "http://example.com:5000",
    "http://127.0.0.1.evil.example:5000", "file:///etc/passwd", "ftp://127.0.0.1",
    "http://employee:secret@127.0.0.1:5000", "http://127.0.0.1:5000/other",
    "http://127.0.0.1:5000?redirect=external", "http://127.0.0.1:5000#fragment",
    "http://127.0.0.1:70000", "http://localhost:5000\\@example.com",
    "http://127.0.0.1:5000\n", "http://2130706433:5000", "http://127.0.0.1:0",
])
def test_non_backend_origins_are_rejected_before_network_or_worker_start(url):
    with pytest.raises(ValueError):
        Transport(AgentConfig(backend_url=url, user_id="emp_014"))


def test_localhost_is_pinned_to_a_loopback_literal_without_dns():
    assert backend_address("http://localhost:5000/") == ("http", "127.0.0.1", 5000)
    assert backend_address("https://[::1]:5000") == ("https", "::1", 5000)


def test_redirects_cannot_forward_counts_or_credentials(backend):
    target = FakeBackend()
    try:
        backend.redirect_to = target.url + "/analyze"
        backend.statuses = [307]
        transport = Transport(config_for(backend, token="synthetic-secret"))
        transport.send(make_payload())
        transport.close()
        assert transport.sent == 0
        assert transport.dropped == 1
        assert len(backend.requests) == 1
        assert target.requests == []
    finally:
        target.close()


def test_request_paths_cannot_escape_the_fixed_endpoints(backend):
    transport = Transport(config_for(backend))
    try:
        for path in ["http://example.com/", "//example.com/", "/../admin", "/analyze?url=external"]:
            with pytest.raises(ValueError, match="Unknown backend endpoint"):
                transport._post(path, {})
        assert backend.requests == []
    finally:
        transport.close()


def test_proxy_environment_cannot_reroute_agent_requests(backend, monkeypatch):
    proxy = FakeBackend()
    try:
        monkeypatch.setenv("HTTP_PROXY", proxy.url)
        monkeypatch.setenv("http_proxy", proxy.url)
        monkeypatch.setenv("NO_PROXY", "")
        transport = Transport(config_for(backend))
        transport.send(make_payload())
        transport.close()
        assert transport.sent == 1
        assert len(backend.requests) == 1
        assert proxy.requests == []
    finally:
        proxy.close()
