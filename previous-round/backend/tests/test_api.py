from datetime import date

from fastapi.testclient import TestClient

from app.data import load_employees, load_topics
from app.main import app
from app.ranking import rank_experts

client = TestClient(app)
DEMO_DAY = date(2026, 9, 30)
MAIL = "Thanks for your question about the year-end bonus for part-time employees under PC 200. I believe that"


def names(result):
    return [e["name"] for e in result["experts"]]


def test_analyze_finds_topic_and_hedge():
    body = client.post("/analyze", json={"text": MAIL}).json()
    assert body["topics"][0]["id"] == "year_end_bonus_pc200"
    assert "i believe" in body["hedges"]


def test_sarah_ranks_first_and_tom_is_stale():
    result = rank_experts(load_topics()["year_end_bonus_pc200"], load_employees(), MAIL, DEMO_DAY)
    assert names(result)[0] == "Sarah De Vos"
    tom = next(e for e in result["experts"] if e["name"] == "Tom Janssens")
    assert tom["trust"]["stale"] and tom["authored"]


def test_opt_out_never_returned():
    for topic_id in load_topics():
        body = client.post("/experts", json={"topic_id": topic_id, "text": MAIL}).json()
        assert "Lotte Maes" not in names(body)


def test_hidden_topic_respected():
    body = client.post("/experts", json={"topic_id": "sick_leave_be"}).json()
    assert "Pieter Claes" not in names(body)


def test_knowledge_gap():
    result = rank_experts(load_topics()["cross_border_lux"], load_employees(), "", DEMO_DAY)
    assert result["knowledge_gap"]


def test_no_internal_ids_leak():
    body = client.post("/experts", json={"topic_id": "year_end_bonus_pc200"}).text
    assert "emp_" not in body


def test_input_validation():
    assert client.post("/experts", json={"topic_id": "../etc/passwd"}).status_code == 422
    assert client.post("/experts", json={"topic_id": "nope"}).status_code == 404
    assert client.post("/analyze", json={"text": "x" * 5000}).status_code == 422


def _sarah_ref():
    body = client.post("/experts", json={"topic_id": "year_end_bonus_pc200"}).json()
    return next(e for e in body["experts"] if e["name"] == "Sarah De Vos")


def test_feedback_counts_as_vouch():
    from app import feedback
    feedback.reset()
    sarah = _sarah_ref()
    res = client.post("/feedback", json={"topic_id": "year_end_bonus_pc200", "ref": sarah["ref"], "helpful": True})
    assert res.status_code == 200
    assert res.json()["trust"]["vouches"] == sarah["trust"]["vouches"] + 1
    feedback.reset()


def test_unhelpful_lowers_score():
    from app import feedback
    feedback.reset()
    sarah = _sarah_ref()
    for _ in range(3):
        client.post("/feedback", json={"topic_id": "year_end_bonus_pc200", "ref": sarah["ref"], "helpful": False})
    assert _sarah_ref()["score"] < sarah["score"]
    feedback.reset()


def test_feedback_rejects_foreign_refs():
    from app import feedback
    sarah = _sarah_ref()
    # Valid ref, wrong topic -> can't be reused across topics.
    assert client.post("/feedback", json={"topic_id": "notice_period_nl", "ref": sarah["ref"], "helpful": True}).status_code == 404
    # Forged ref for the opted-out expert.
    forged = feedback.expert_ref("emp_019", "year_end_bonus_pc200")
    assert client.post("/feedback", json={"topic_id": "year_end_bonus_pc200", "ref": forged, "helpful": True}).status_code == 404
    assert client.post("/feedback", json={"topic_id": "year_end_bonus_pc200", "ref": "zz", "helpful": True}).status_code == 422
