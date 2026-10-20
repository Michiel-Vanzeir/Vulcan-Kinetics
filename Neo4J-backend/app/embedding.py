import hashlib
import math
from . import config

_model = None


def _st_embed(text: str) -> list[float]:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(config.EMBED_MODEL)
    return _model.encode(text, normalize_embeddings=True).tolist()


def _fake_embed(text: str) -> list[float]:
    """Hashed bag-of-words. Only for smoke tests: matches on shared words, not meaning."""
    vec = [0.0] * config.EMBED_DIM
    for tok in text.lower().split():
        vec[int(hashlib.md5(tok.encode()).hexdigest(), 16) % config.EMBED_DIM] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed(text: str) -> list[float]:
    return _fake_embed(text) if config.EMBED_BACKEND == "fake" else _st_embed(text)


def build_knowledge_text(title: str, summary: str, keywords: list[str]) -> str:
    return f"{title}. {summary}. Keywords: {', '.join(keywords)}"
