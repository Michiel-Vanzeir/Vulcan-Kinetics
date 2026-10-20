"""Stub: the LLM-based document reader we'll write later.
It should turn a raw source (email, Slack thread, PDF...) into a KnowledgeIn-shaped payload;
the embedding is NOT produced here, add_knowledge does that from title + summary + keywords."""
from .models import KnowledgeIn


def extract_knowledge(source_uri: str, holder_ids: list[str], supersedes_id: str | None = None) -> KnowledgeIn:
    raise NotImplementedError("LLM document reader not implemented yet")
