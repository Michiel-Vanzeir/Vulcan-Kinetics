"""Demo readiness: the health check and the seeded expertise history."""

import expertise_filter
import seed_signals
from app import create_app


def test_health_needs_no_database():
    response = create_app().test_client().get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_seed_ranks_fresh_experts_and_hides_stale_ones(tmp_path, monkeypatch):
    db_path = tmp_path / "seeded.db"
    monkeypatch.setattr(seed_signals, "FILTER_DB_PATH", str(db_path))
    seed_signals.main()

    store = expertise_filter.PersonStore(db_path)
    flt = expertise_filter.ExpertiseFilter(store)
    assert flt.is_expert("emp_021", "year_end_bonus")[0]  # Sarah, recent and fluent
    assert flt.is_expert("emp_077", "notice_period")[0]   # Emma
    assert not flt.is_expert("emp_045", "year_end_bonus")[0]  # Tom, last active in 2024
    assert store.get("emp_021")["profile"]["name"] == "Sarah De Vos"
    store.close()
