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
    monkeypatch.setenv("WHOKNOWS_AUTH_TOKEN", "employee-test-token")
    monkeypatch.setenv("WHOKNOWS_USER_ID", "emp_014")
    monkeypatch.setattr(signals, "FILTER_DB_PATH", ":memory:")
    monkeypatch.setattr(signals, "_filter", None)
    monkeypatch.setattr(signals, "_store", None)
    client = create_app().test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = "Bearer employee-test-token"
    client.post("/preferences", json={"capture_enabled": True,
                "allowed_surfaces": ["teams_desktop"], "hidden_topics": []})
    return client


def test_valid_payload_is_accepted(client):
    response = client.post("/analyze", json=VALID)
    assert response.status_code == 200
    assert response.get_json() == {"accepted": True, "tip": None, "doubt_alert": None}


def test_doubt_alert_is_returned_to_the_agent(client):
    doubting = {**VALID, "hedge_words": 4, "placeholders": 2, "deletion_bursts": 3,
                "rewrite_loops": 2, "long_pauses": 3, "chars_deleted": 30}
    alert = client.post("/analyze", json=doubting).get_json()["doubt_alert"]
    assert alert["context_id"] == "c_9f2"
    assert alert["topics"] == ["notice_period", "country_ES"]


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
        signals._on_filter_thread(signals._process, {**VALID, "user_id": user_id})
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
    assert [e["user_id"] for e in experts] == ["emp_021"]
    assert experts[0]["profile"]["job_title"] == "Payroll consultant"


def test_experts_rejects_free_text(client):
    assert client.post("/experts", json={"topics": ["who knows about notice"]}).status_code == 400
    assert client.post("/experts", json={"topics": []}).status_code == 400


def test_employee_authentication_and_identity_are_enforced(client):
    assert client.get("/preferences", headers={"Authorization": ""}).status_code == 401
    assert client.post("/analyze", json={**VALID, "user_id": "emp_021"}).status_code == 403
    assert client.post("/nodes", json={}).status_code == 403
    assert client.get("/health", headers={"Authorization": ""}).status_code == 200


def test_consent_revocation_blocks_new_signals(client):
    response = client.post("/preferences", json={"capture_enabled": False})
    assert response.status_code == 200
    assert client.post("/analyze", json=VALID).status_code == 403
    assert client.get("/preferences").json["capture_enabled"] is False


def test_surface_opt_in_is_required(client):
    assert client.post("/analyze", json={**VALID, "surface": "word_desktop"}).status_code == 403
    assert client.post("/preferences", json={"allowed_surfaces": ["unknown"]}).status_code == 400


def test_hidden_topics_are_not_collected_or_ranked(client, monkeypatch):
    client.post("/preferences", json={"capture_enabled": True,
                "allowed_surfaces": ["teams_desktop"], "hidden_topics": ["notice_period"]})
    calls = []
    monkeypatch.setattr(expertise_filter.ExpertiseFilter, "process",
                        lambda self, payload: calls.append(payload))
    assert client.post("/analyze", json=VALID).status_code == 200
    assert calls[0]["topics"] == ["country_ES"]
    assert client.post("/experts", json={"topics": ["country_ES"]}).json["knowledge_gaps"] == ["country_ES"]


def test_unknown_topic_ids_and_oversized_requests_are_rejected(client):
    assert client.post("/analyze", json={**VALID, "topics": ["secret_payload"]}).status_code == 400
    assert client.post("/analyze", data=" " * 32769,
                       content_type="application/json").status_code == 413


def test_seeded_history_drives_ranking_and_keeps_spain_gap(client):
    """Exercise the real demo history and scorer through authenticated HTTP ranking."""
    import time
    from seed_signals import HISTORY, DAY_MS, answering_payload
    now = int(time.time() * 1000)
    for user_id, (topics, events) in HISTORY.items():
        for index, (days_ago, surface) in enumerate(events):
            signals._on_filter_thread(signals._process,
                answering_payload(user_id, f"seed-{index}", now - days_ago * DAY_MS,
                                  surface, topics))
    bonus = client.post("/experts", json={"topics": ["year_end_bonus", "PC_200"]}).json
    assert {expert["user_id"] for expert in bonus["experts"]} == {"emp_021"}
    assert bonus["knowledge_gaps"] == []
    notice = client.post("/experts", json={"topics": ["notice_period", "country_ES"]}).json
    assert notice["experts"][0]["user_id"] == "emp_077"
    assert notice["knowledge_gaps"] == ["country_ES"]
    assert "context_credits" not in notice["experts"][0]["evidence"]
