"""End-to-end: Transport -> real HTTP -> backend /analyze and /experts -> expertise filter."""

import sys
import threading
from pathlib import Path

import pytest

from agent.config import AgentConfig
from agent.transport import Transport
from conftest import make_payload

BACKEND_DIR = Path(__file__).resolve().parents[2] / "Neo4J-backend"
sys.path.insert(0, str(BACKEND_DIR))

flask = pytest.importorskip("flask", reason="backend deps not installed (requirements-dev.txt)")
from werkzeug.serving import make_server  # noqa: E402

import expertise_filter  # noqa: E402
from app import create_app, signals  # noqa: E402


@pytest.fixture
def backend_url(monkeypatch):
    monkeypatch.setenv("WHOKNOWS_AUTH_TOKEN", "e2e-token")
    monkeypatch.setenv("WHOKNOWS_USER_ID", "emp_014")
    monkeypatch.setattr(signals, "FILTER_DB_PATH", ":memory:")
    monkeypatch.setattr(signals, "_filter", None)
    monkeypatch.setattr(signals, "_store", None)
    app = create_app()
    with app.test_client() as client:
        client.post("/preferences", json={"capture_enabled": True,
                    "allowed_surfaces": ["teams_desktop"], "hidden_topics": []},
                    headers={"Authorization": "Bearer e2e-token"})
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def process_calls(monkeypatch):
    """Record every call to the teammate's ExpertiseFilter.process, then run the real thing."""
    calls: list[dict] = []
    original = expertise_filter.ExpertiseFilter.process

    def recording(self, payload_dict):
        calls.append(payload_dict)
        return original(self, payload_dict)

    monkeypatch.setattr(expertise_filter.ExpertiseFilter, "process", recording)
    return calls


def test_payload_reaches_the_expertise_filter(backend_url, process_calls):
    transport = Transport(AgentConfig(backend_url=backend_url, user_id="emp_014", auth_token="e2e-token"))
    transport.send(make_payload())
    experts = transport.request_experts(["notice_period"])
    transport.close()

    assert transport.sent == 1
    assert transport.dropped == transport.rejected == 0
    [payload] = process_calls
    assert payload["user_id"] == "emp_014"
    assert payload["context_id"] == "c_1"
    assert payload["trigger"] == "hedge"
    assert payload["surface"] == "teams_desktop"
    assert payload["hedge_words"] == 1
    assert payload["chars_typed"] == 6
    assert payload["topics"] == ["country_ES", "notice_period"]
    assert isinstance(experts, list)
