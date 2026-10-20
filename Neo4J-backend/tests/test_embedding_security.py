"""Model loading must retain the security settings even when ML is installed optionally."""

import sys
from types import SimpleNamespace

from app import config, embedding


def test_model_loader_disables_remote_code_and_requires_safetensors(monkeypatch):
    calls = []

    def load_model(name, **options):
        """Record constructor arguments without downloading or executing a model."""
        calls.append((name, options))
        return SimpleNamespace(encode=lambda text, **kwargs:
                               SimpleNamespace(tolist=lambda: [1.0, 0.0]))

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        SimpleNamespace(SentenceTransformer=load_model))
    monkeypatch.setattr(embedding, "_model", None)
    assert embedding._st_embed("synthetic payroll example") == [1.0, 0.0]
    assert calls == [(config.EMBED_MODEL, {
        "trust_remote_code": False, "model_kwargs": {"use_safetensors": True},
    })]
    embedding._st_embed("another example")
    assert len(calls) == 1
