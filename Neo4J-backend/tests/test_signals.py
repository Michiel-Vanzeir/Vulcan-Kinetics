"""Tests for the capture-agent ingestion routes (/analyze, /experts)."""

import pytest

import expertise_filter
from app import create_app, signals

VALID = {
    "user_id": "emp_014",
    "context_id": "c_9f2",
    "ts": 1_729_512_345_000,
    "trigger": "hedge",
    "surface": "teams_desktop",
    "chars_typed": 44,
    "hedge_words": 1,
    "topics": ["notice_period", "country_ES"],
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(signals, "FILTER_DB_PATH", ":memory:")
    monkeypatch.setattr(signals, "_filter", None)
    monkeypatch.setattr(signals, "_store", None)
    return create_app().test_client()


def test_valid_payload_is_accepted(client):
    response = client.post("/analyze", json=VALID)
    assert response.status_code == 200
    assert response.get_json() == {"accepted": True, "tip": None}


@pytest.mark.parametrize(
    "change",
    [
        {"trigger": "typing"},
        {"topics": ["the user typed this sentence"]},
        {"surface": "Dear Sarah, about your notice"},
        {"chars_typed": -1},
        {"chars_typed": "many"},
        {"note": "free text"},
        {"user_id": None},
    ],
)
def test_malformed_payload_is_rejected(client, change):
    response = client.post("/analyze", json={**VALID, **change})
    assert response.status_code == 400
    assert response.get_json()["error"] == "validation"


def test_non_json_body_is_rejected(client):
    assert client.post("/analyze", data="not json").status_code == 400


def test_validation_errors_do_not_echo_input(client):
    response = client.post("/analyze", json={**VALID, "topics": ["secret words here"]})
    assert "secret" not in response.get_data(as_text=True)


def test_filter_process_called_with_payload(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        expertise_filter.ExpertiseFilter, "process", lambda self, payload: calls.append(payload)
    )
    client.post("/analyze", json=VALID)
    [payload] = calls
    assert {k: payload[k] for k in VALID} == VALID
    assert payload["pauses"] == 0  # defaults filled in for fields the agent left out
    assert set(payload) == set(signals.SignalPayloadIn.model_fields)


def test_experts_returns_ranked_list(client, monkeypatch):
    for user_id in ("emp_014", "emp_021", "emp_003"):
        client.post("/analyze", json={**VALID, "user_id": user_id})
    scores = {"emp_014": 0.9, "emp_021": 0.7}
    monkeypatch.setattr(
        expertise_filter.ExpertiseFilter,
        "is_expert",
        lambda self, user_id, topic: (user_id in scores, scores.get(user_id, 0.1), ["test"]),
    )
    response = client.post("/experts", json={"topics": ["notice_period"], "exclude_user_id": "emp_021"})
    assert response.status_code == 200
    experts = response.get_json()["experts"]
    assert isinstance(experts, list)
    assert [e["user_id"] for e in experts] == ["emp_014"]
    assert experts[0]["profile"]["job_title"] == "Payroll consultant"


def test_experts_rejects_free_text(client):
    assert client.post("/experts", json={"topics": ["who knows about notice"]}).status_code == 400
    assert client.post("/experts", json={"topics": []}).status_code == 400
