"""
Tests for evaluation/embeddings.py.

These tests call the real OpenAI embeddings API (no mocking of the API
response itself -- only network-call counting), mirroring how
evaluation/test_llm_classifier_milestone.py exercises live-API-adjacent
code. They require OPENAI_API_KEY to be set. Synthetic strings only --
no real customer-support text, no pool data.
"""
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from evaluation.embeddings import get_embedding
from openai.resources.embeddings import Embeddings


def _fresh_string():
    return f"Synthetic embedding test string {time.time()}_{os.getpid()}"


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
def test_get_embedding_returns_expected_dimensionality():
    vec = get_embedding(_fresh_string())
    assert isinstance(vec, list)
    assert len(vec) == 1536
    assert all(isinstance(x, float) for x in vec)


def test_get_embedding_raises_clearly_when_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
        get_embedding(_fresh_string())


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
def test_identical_text_is_a_cache_hit_no_second_api_call(monkeypatch):
    call_count = {"n": 0}
    original_create = Embeddings.create

    def counting_create(self, *args, **kwargs):
        call_count["n"] += 1
        return original_create(self, *args, **kwargs)

    monkeypatch.setattr(Embeddings, "create", counting_create)

    text = _fresh_string()
    vec1 = get_embedding(text)
    assert call_count["n"] == 1, "first call on a never-before-seen string must hit the API"

    vec2 = get_embedding(text)
    assert call_count["n"] == 1, "second call on the identical string must be a cache hit (no new API call)"

    assert vec1 == vec2
