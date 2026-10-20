"""Unit tests for the pure who-knows ranking helpers (no database needed)."""

from datetime import datetime

from app import config
from app.services import _keyword_boost, _recency_weight


def test_recency_weight_halves_each_half_life():
    now = datetime(2026, 10, 20)
    assert _recency_weight("2026-10-20T00:00:00", now) == 1.0
    half = now.replace(year=2026, month=4, day=23)  # ~half-life (180d) before now
    assert abs(_recency_weight(half.isoformat(), now) - 0.5) < 0.05
    assert _recency_weight("2024-01-01T00:00:00", now) < _recency_weight("2026-01-01T00:00:00", now)


def test_recency_weight_handles_missing_or_bad_dates():
    now = datetime(2026, 10, 20)
    assert _recency_weight("", now) == 1.0
    assert _recency_weight("not-a-date", now) == 1.0


def test_keyword_boost_counts_query_terms_in_keywords():
    assert _keyword_boost({"fraud", "threshold"}, ["fraud", "model"]) == config.KEYWORD_BOOST
    assert _keyword_boost({"apple", "pay"}, ["apple pay", "ios"]) == 2 * config.KEYWORD_BOOST
    assert _keyword_boost({"unrelated"}, ["fraud", "model"]) == 0.0


def test_keyword_boost_is_capped():
    many = {f"w{i}" for i in range(20)}
    keywords = [f"w{i}" for i in range(20)]
    assert _keyword_boost(many, keywords) == 1.0
