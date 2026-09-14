"""
Tests for evaluation/retrieval.py (query function) and the leakage/dedup
logic in evaluation/build_retrieval_index.py.

Most tests run against the REAL serialized index at config.RETRIEVAL_INDEX_DIR
(built by evaluation/build_retrieval_index.py -- these are skipped if it
doesn't exist yet). The leakage-assertion failure case and the model-mismatch
case use small synthetic fixtures instead, since they need to deliberately
trigger a failure that the real index (correctly) never has.
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from evaluation.build_retrieval_index import assert_hard_leakage_free, filter_short_messages
from evaluation.leakage_checks import LeakageError
from evaluation.retrieval import IndexModelMismatch, load_index, retrieve_top_k

REAL_INDEX_EXISTS = (config.RETRIEVAL_INDEX_DIR / "manifest.json").exists()
requires_real_index = pytest.mark.skipif(
    not REAL_INDEX_EXISTS,
    reason="No real retrieval index at cache/retrieval_index/ -- run evaluation/build_retrieval_index.py first.",
)
requires_api_key = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
)


def _fresh_query():
    return f"Synthetic retrieval test query {time.time()}_{os.getpid()}"


# ---------------------------------------------------------------------------
# retrieve_top_k determinism (real index)
# ---------------------------------------------------------------------------

@requires_real_index
@requires_api_key
def test_retrieve_top_k_is_deterministic_for_identical_query():
    query = "My account was hacked and I cannot log in."
    results1 = retrieve_top_k(query, k=5)
    results2 = retrieve_top_k(query, k=5)

    assert len(results1) == 5
    ids1 = [m["customer_tweet_id"] for _, _, _, m in results1]
    ids2 = [m["customer_tweet_id"] for _, _, _, m in results2]
    assert ids1 == ids2

    sims1 = [s for _, _, s, _ in results1]
    sims2 = [s for _, _, s, _ in results2]
    assert sims1 == sims2


@requires_real_index
@requires_api_key
def test_retrieve_top_k_results_are_sorted_descending_by_similarity():
    results = retrieve_top_k("How do I cancel my subscription?", k=5)
    sims = [s for _, _, s, _ in results]
    assert sims == sorted(sims, reverse=True)


# ---------------------------------------------------------------------------
# k=0: no embedding call
# ---------------------------------------------------------------------------

def test_k_zero_returns_empty_list_with_no_embedding_call(monkeypatch):
    call_count = {"n": 0}

    def fail_if_called(*args, **kwargs):
        call_count["n"] += 1
        raise AssertionError("get_embedding must not be called when k=0")

    monkeypatch.setattr("evaluation.retrieval.get_embedding", fail_if_called)

    result = retrieve_top_k("this text should never be embedded", k=0)
    assert result == []
    assert call_count["n"] == 0


# ---------------------------------------------------------------------------
# Hard leakage assertion: real-data pass + synthetic-failure case
# ---------------------------------------------------------------------------

@requires_real_index
def test_hard_leakage_assertion_passes_on_real_index():
    manifest, embeddings, metadata = load_index()

    with open(config.GOLDEN_FINAL_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        import csv
        golden_rows = list(csv.DictReader(f))
    assert len(golden_rows) == 200

    summary = assert_hard_leakage_free(golden_rows, metadata)
    assert summary["index_tweet_ids"] == manifest["sample_size"]


def test_hard_leakage_assertion_triggers_on_synthetic_overlap():
    golden_rows = [
        dict(tweet_id="123", thread_id="1"),
        dict(tweet_id="456", thread_id="2"),
    ]
    # Synthetic retrieval sample that deliberately shares tweet_id "123" with golden.
    sample = [
        dict(customer_tweet_id="123", thread_id="999"),
        dict(customer_tweet_id="789", thread_id="1000"),
    ]
    with pytest.raises(LeakageError):
        assert_hard_leakage_free(golden_rows, sample)


# ---------------------------------------------------------------------------
# Model-version-mismatch detection
# ---------------------------------------------------------------------------

def test_model_mismatch_raises_clearly(tmp_path, monkeypatch):
    fake_index_dir = tmp_path / "fake_index"
    fake_index_dir.mkdir()

    embeddings = np.zeros((2, 4), dtype=np.float32)
    embeddings[0] = [1.0, 0.0, 0.0, 0.0]
    embeddings[1] = [0.0, 1.0, 0.0, 0.0]
    np.save(fake_index_dir / "embeddings.npy", embeddings)

    with open(fake_index_dir / "metadata.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps(dict(customer_text="a", brand_text="b", customer_tweet_id="1", brand_tweet_id="2", thread_id="3")) + "\n")
        f.write(json.dumps(dict(customer_text="c", brand_text="d", customer_tweet_id="4", brand_tweet_id="5", thread_id="6")) + "\n")

    manifest = dict(embedding_model="some-other-embedding-model", dimensions=4, sample_size=2, seed=42)
    with open(fake_index_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    def fake_get_embedding(text):
        raise AssertionError("get_embedding must not be reached after a model mismatch is detected")

    monkeypatch.setattr("evaluation.retrieval.get_embedding", fake_get_embedding)

    with pytest.raises(IndexModelMismatch, match="some-other-embedding-model"):
        retrieve_top_k("irrelevant query", k=1, index_dir=fake_index_dir)


def test_load_index_raises_file_not_found_for_missing_index(tmp_path):
    empty_dir = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError):
        load_index(index_dir=empty_dir)


# ---------------------------------------------------------------------------
# Corpus-quality filter (filter_short_messages) -- fast, isolated unit test,
# never run against the real 26,914-row corpus here.
# ---------------------------------------------------------------------------

def test_filter_short_messages_excludes_below_threshold_includes_at_and_above():
    assert config.MIN_CUSTOMER_MSG_LENGTH == 10  # test assumes this; fails loudly if it ever changes

    pairs = [
        dict(customer_text="@handle", label="7 chars -- below"),
        dict(customer_text="123456789", label="9 chars -- just below boundary"),
        dict(customer_text="1234567890", label="exactly 10 chars -- at boundary, included"),
        dict(customer_text="  1234567890  ", label="10 chars after stripping whitespace -- included"),
        dict(customer_text="This is a genuinely long customer message.", label="well above -- included"),
    ]

    result = filter_short_messages(pairs)
    result_labels = {p["label"] for p in result}

    assert result_labels == {
        "exactly 10 chars -- at boundary, included",
        "10 chars after stripping whitespace -- included",
        "well above -- included",
    }
    assert len(result) == 3
