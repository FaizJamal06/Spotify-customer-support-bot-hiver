"""
Focused tests for the baseline milestone: label-loading/exclusion logic,
leakage/boundary assertions, and basic sanity checks on both baselines.

Run with: pytest evaluation/test_baseline_milestone.py -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.data_loading import (
    load_discovery_rows, assert_expected_split, load_training_examples,
    load_golden_examples, load_retrieval_ids,
    DiscoverySplitMismatch, EXPECTED_VALID_COUNT, EXPECTED_EXCLUDED_IDS,
)
from evaluation.leakage_checks import assert_no_leakage, assert_no_overlap, LeakageError
from evaluation.baselines import MajorityClassBaseline, TfidfLogRegBaseline
from evaluation.metrics import compute_metrics


# ============================================================
# Label-loading / exclusion logic
# ============================================================

def test_discovery_rows_total_300():
    rows, source = load_discovery_rows()
    assert len(rows) == 300


def test_discovery_split_is_exactly_296_valid_4_excluded():
    rows, source = load_discovery_rows()
    excluded_ids = {r["example_id"] for r in rows if r["label"] is None}
    valid_ids = {r["example_id"] for r in rows if r["label"] is not None}
    assert len(valid_ids) == EXPECTED_VALID_COUNT
    assert excluded_ids == EXPECTED_EXCLUDED_IDS == {"70", "78", "164", "265"}


def test_assert_expected_split_passes_on_real_data():
    rows, _ = load_discovery_rows()
    assert_expected_split(rows)  # must not raise


def test_assert_expected_split_raises_on_wrong_total():
    with pytest.raises(DiscoverySplitMismatch):
        assert_expected_split([{"example_id": "1", "label": "ACCOUNT_ACCESS"}])


def test_assert_expected_split_raises_on_wrong_excluded_set():
    rows = [{"example_id": str(i), "label": "ACCOUNT_ACCESS"} for i in range(1, 301)]
    rows[0]["label"] = None  # excludes Ex 1 instead of the expected {70,78,164,265}
    with pytest.raises(DiscoverySplitMismatch):
        assert_expected_split(rows)


def test_assert_expected_split_raises_on_non_frozen_label():
    rows = [{"example_id": str(i), "label": "ACCOUNT_ACCESS"} for i in range(1, 301)]
    for eid in EXPECTED_EXCLUDED_IDS:
        rows[int(eid) - 1]["label"] = None
    rows[10]["label"] = "NOT_A_REAL_LABEL"
    with pytest.raises(DiscoverySplitMismatch):
        assert_expected_split(rows)


def test_load_training_examples_returns_296_with_expected_excluded_ids():
    examples, excluded, source = load_training_examples()
    assert len(examples) == EXPECTED_VALID_COUNT
    assert excluded == sorted(EXPECTED_EXCLUDED_IDS, key=int)
    example_ids = {e["example_id"] for e in examples}
    assert example_ids.isdisjoint(EXPECTED_EXCLUDED_IDS), (
        "excluded example IDs must never appear in the fitted training set"
    )


def test_training_examples_have_only_frozen_labels():
    examples, _, _ = load_training_examples()
    labels = {e["label"] for e in examples}
    assert labels.issubset(set(config.FROZEN_LABELS))


def test_training_examples_have_nonempty_text_and_ids():
    examples, _, _ = load_training_examples()
    for e in examples:
        assert e["text"].strip(), f"Ex {e['example_id']} has empty training text"
        assert e["tweet_id"]
        assert e["thread_id"]


# ============================================================
# Leakage / data-boundary assertions
# ============================================================

def test_no_overlap_helper_detects_overlap():
    with pytest.raises(LeakageError):
        assert_no_overlap({"1", "2"}, {"2", "3"}, "A", "B", "tweet_id")


def test_no_overlap_helper_passes_when_disjoint():
    assert_no_overlap({"1", "2"}, {"3", "4"}, "A", "B", "tweet_id")  # must not raise


def test_real_data_has_zero_leakage():
    train_examples, _, _ = load_training_examples()
    golden_examples = load_golden_examples()
    retrieval_tweet_ids, retrieval_thread_ids = load_retrieval_ids()
    summary = assert_no_leakage(train_examples, golden_examples, retrieval_tweet_ids, retrieval_thread_ids)
    assert summary["checks_passed"] == 6
    assert summary["train_tweet_ids"] == EXPECTED_VALID_COUNT
    assert summary["golden_tweet_ids"] == 200


def test_golden_examples_load_correctly():
    golden = load_golden_examples()
    assert len(golden) == 200
    labels = {e["label"] for e in golden}
    assert labels.issubset(set(config.FROZEN_LABELS))
    assert all(e["text"].strip() for e in golden)


# ============================================================
# Baseline sanity checks
# ============================================================

def test_majority_baseline_predicts_single_constant_label():
    labels = ["A", "A", "A", "B", "C"]
    m = MajorityClassBaseline().fit(labels)
    assert m.majority_label_ == "A"
    preds = m.predict(["x", "y", "z"])
    assert preds == ["A", "A", "A"]


def test_majority_baseline_matches_true_training_majority():
    examples, _, _ = load_training_examples()
    labels = [e["label"] for e in examples]
    m = MajorityClassBaseline().fit(labels)
    assert m.majority_label_ == "APP_TECH_ISSUE"  # verified majority class in the 296


def test_tfidf_logreg_predicts_valid_labels_for_all_inputs():
    examples, _, _ = load_training_examples()
    golden = load_golden_examples()
    texts = [e["text"] for e in examples]
    labels = [e["label"] for e in examples]
    clf = TfidfLogRegBaseline().fit(texts, labels)
    golden_texts = [e["text"] for e in golden]
    preds = clf.predict(golden_texts)
    assert len(preds) == len(golden_texts)
    assert set(preds).issubset(set(config.FROZEN_LABELS))


def test_tfidf_logreg_vocabulary_built_only_from_training_texts():
    examples, _, _ = load_training_examples()
    texts = [e["text"] for e in examples]
    labels = [e["label"] for e in examples]
    clf = TfidfLogRegBaseline().fit(texts, labels)
    assert len(clf.vectorizer.vocabulary_) > 0
    # transform (not fit_transform) must be used at prediction time
    golden = load_golden_examples()
    vocab_before = dict(clf.vectorizer.vocabulary_)
    clf.predict([e["text"] for e in golden])
    assert clf.vectorizer.vocabulary_ == vocab_before, "vocabulary must not change when predicting"


def test_metrics_shape_and_ranges():
    y_true = ["ACCOUNT_ACCESS", "SUBSCRIPTION_BILLING", "ACCOUNT_ACCESS"]
    y_pred = ["ACCOUNT_ACCESS", "ACCOUNT_ACCESS", "ACCOUNT_ACCESS"]
    m = compute_metrics(y_true, y_pred, config.FROZEN_LABELS)
    assert 0.0 <= m["accuracy"] <= 1.0
    assert 0.0 <= m["macro_f1"] <= 1.0
    assert set(m["per_class"].keys()) == set(config.FROZEN_LABELS)
    assert m["confusion_matrix"]["labels"] == config.FROZEN_LABELS
    assert len(m["confusion_matrix"]["matrix"]) == len(config.FROZEN_LABELS)
    assert m["n_examples"] == 3
