from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .data import load_employees, load_topics
from .matching import find_hedges, match_topics
from . import feedback
from .ranking import find_by_ref, rank_experts, trust_for

app = FastAPI(title="whoknows", version="0.1.0")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ExpertsRequest(BaseModel):
    topic_id: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    text: str = Field(default="", max_length=4000)


class FeedbackRequest(BaseModel):
    topic_id: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    ref: str = Field(pattern=r"^[0-9a-f]{32}$")
    helpful: bool


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    return {"topics": match_topics(req.text, load_topics()), "hedges": find_hedges(req.text)}


@app.post("/experts")
def experts(req: ExpertsRequest):
    topic = load_topics().get(req.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Unknown topic")
    return rank_experts(topic, load_employees(), req.text, date.today())


@app.post("/feedback")
def give_feedback(req: FeedbackRequest):
    """'Did they know their stuff?' A helpful vote counts as a vouch, unhelpful lowers the ranking."""
    if req.topic_id not in load_topics():
        raise HTTPException(status_code=404, detail="Unknown topic")
    emp = find_by_ref(req.topic_id, req.ref, load_employees())
    if emp is None:
        raise HTTPException(status_code=404, detail="Unknown expert")
    feedback.record_vote(emp["id"], req.topic_id, req.helpful)
    return {"trust": trust_for(emp, req.topic_id, date.today())}


# Fake mail and chat pages to demo the extension on.
app.mount("/demo", StaticFiles(directory=Path(__file__).resolve().parent.parent / "demo", html=True), name="demo")
