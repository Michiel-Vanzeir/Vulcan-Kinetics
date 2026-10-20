import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache
def load_topics() -> dict[str, dict]:
    topics = json.loads((DATA_DIR / "topics.json").read_text(encoding="utf-8"))
    return {t["id"]: t for t in topics}


@lru_cache
def load_employees() -> list[dict]:
    return json.loads((DATA_DIR / "company.json").read_text(encoding="utf-8"))["employees"]
