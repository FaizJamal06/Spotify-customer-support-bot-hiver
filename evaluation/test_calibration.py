"""
Tests for evaluation/calibration.py (exploratory calibration analysis).

Covers: quantile bucket-boundary correctness on synthetic data, Wilson interval
correctness against known reference values, ECE correctness on a known synthetic
case, and confirmation that this module makes zero API calls.
"""
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.calibration import (
    quantile_split,
    quantile_bucket_boundaries,
    per_bucket_accuracy,
    wilson_interval,
    expected_calibration_error,
    brier_score,
    distribution_stats,
)


# ---------------------------------------------------------------------------
# Quantile bucketing correctness
# ---------------------------------------------------------------------------

def test_quantile_split_even_division():
    # 20 items, 5 buckets -> exactly 4 per bucket.
    items = list(range(20))
    groups = quantile_split(items, n_buckets=5)
    assert [len(g) for g in groups] == [4, 4, 4, 4, 4]
    assert sum(len(g) for g in groups) == 20
    # groups are contiguous in sorted order
    assert groups[0] == [0, 1, 2, 3]
    assert groups[4] == [16, 17, 18, 19]


def test_quantile_split_uneven_division_distributes_remainder():
    # 23 items, 5 buckets -> base=4, remainder=3 -> first 3 buckets get 5, rest get 4.
    items = list(range(23))
    groups = quantile_split(items, n_buckets=5)
    sizes = [len(g) for g in groups]
    assert sizes == [5, 5, 5, 4, 4]
    assert sum(sizes) == 23


def test_quantile_split_handles_ties_without_empty_buckets():
    # Many tied values (mirrors the real confidence data: heavy clustering at 0.98).
    items = [0.5, 0.6, 0.7] + [0.98] * 15 + [0.99] * 2
    groups = quantile_split(items, n_buckets=5)
    sizes = [len(g) for g in groups]
    assert sum(sizes) == 20
    # No degenerate (empty) buckets despite heavy ties.
    assert all(s > 0 for s in sizes)
    # Equal-frequency: max/min bucket size differ by at most 1.
    assert max(sizes) - min(sizes) <= 1


def test_quantile_bucket_boundaries_matches_groups():
    confs = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    boundaries = quantile_bucket_boundaries(confs, n_buckets=5)
    assert len(boundaries) == 6
    # boundaries ascending
    assert boundaries == sorted(boundaries)
    assert boundaries[0] == 0.1
    assert boundaries[-1] == 1.0


def test_per_bucket_accuracy_on_synthetic_data_no_empty_buckets():
    # 40 synthetic predictions, deliberately with a tie cluster, split into 5 buckets of 8.
    preds = []
    for i in range(40):
        conf = 0.5 + 0.01 * (i % 10)  # clustered/tied values
        correct = 1 if i % 3 == 0 else 0
        preds.append(dict(confidence=conf, correct=correct))
    rows = per_bucket_accuracy(preds, n_buckets=5)
    assert len(rows) == 5
    assert sum(r["n"] for r in rows) == 40
    assert all(r["n"] == 8 for r in rows)
    assert all(r["wilson_lo"] is not None and r["wilson_hi"] is not None for r in rows)


# ---------------------------------------------------------------------------
# Wilson interval correctness against known reference values
# ---------------------------------------------------------------------------

def test_wilson_interval_reference_case_8_of_10():
    lo, hi = wilson_interval(8, 10)
    assert math.isclose(lo, 0.4902, abs_tol=1e-3)
    assert math.isclose(hi, 0.9433, abs_tol=1e-3)


def test_wilson_interval_reference_case_90_of_100():
    lo, hi = wilson_interval(90, 100)
    assert math.isclose(lo, 0.8256, abs_tol=1e-3)
    assert math.isclose(hi, 0.9448, abs_tol=1e-3)


def test_wilson_interval_zero_n_returns_nan():
    lo, hi = wilson_interval(0, 0)
    assert math.isnan(lo) and math.isnan(hi)


# ---------------------------------------------------------------------------
# ECE correctness on a known synthetic case
# ---------------------------------------------------------------------------

def test_ece_known_synthetic_case():
    # Two bins of equal size (10 each). Bin 0: mean_confidence=0.6, accuracy=0.5
    # -> |0.5-0.6|=0.1. Bin 1: mean_confidence=0.9, accuracy=0.8 -> |0.8-0.9|=0.1.
    # Equal bin weights (10/20 each) -> ECE = 0.5*0.1 + 0.5*0.1 = 0.1.
    bucket_rows = [
        dict(bucket=0, n=10, accuracy=0.5, mean_confidence=0.6),
        dict(bucket=1, n=10, accuracy=0.8, mean_confidence=0.9),
    ]
    ece = expected_calibration_error(bucket_rows)
    assert math.isclose(ece, 0.1, abs_tol=1e-9)


def test_ece_perfect_calibration_is_zero():
    bucket_rows = [
        dict(bucket=0, n=10, accuracy=0.7, mean_confidence=0.7),
        dict(bucket=1, n=10, accuracy=0.9, mean_confidence=0.9),
    ]
    ece = expected_calibration_error(bucket_rows)
    assert math.isclose(ece, 0.0, abs_tol=1e-9)


def test_ece_skips_empty_bins():
    bucket_rows = [
        dict(bucket=0, n=0, accuracy=None, mean_confidence=None),
        dict(bucket=1, n=10, accuracy=0.8, mean_confidence=0.8),
    ]
    ece = expected_calibration_error(bucket_rows)
    assert math.isclose(ece, 0.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# Brier score sanity checks
# ---------------------------------------------------------------------------

def test_brier_score_perfect_predictions_is_zero():
    preds = [dict(confidence=1.0, correct=1), dict(confidence=0.0, correct=0)]
    assert math.isclose(brier_score(preds), 0.0, abs_tol=1e-9)


def test_brier_score_known_value():
    # confidence=0.8, correct=1 -> (0.8-1)^2 = 0.04
    # confidence=0.8, correct=0 -> (0.8-0)^2 = 0.64
    # mean = 0.34
    preds = [dict(confidence=0.8, correct=1), dict(confidence=0.8, correct=0)]
    assert math.isclose(brier_score(preds), 0.34, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# Distribution stats sanity
# ---------------------------------------------------------------------------

def test_distribution_stats_basic():
    confs = [0.1, 0.2, 0.3, 0.4, 0.5]
    stats = distribution_stats(confs)
    assert stats["n"] == 5
    assert stats["min"] == 0.1
    assert stats["max"] == 0.5
    assert math.isclose(stats["mean"], 0.3, abs_tol=1e-9)
    assert stats["median"] == 0.3


# ---------------------------------------------------------------------------
# Zero-API-calls confirmation
# ---------------------------------------------------------------------------

def test_calibration_module_makes_no_network_calls():
    """
    Confirms evaluation/calibration.py does not import openai or any other
    network-capable module, via AST inspection of actual import statements
    (not a raw substring search, since the module's own docstring mentions
    "does not import openai" in prose). This guards against that commitment
    ever silently changing.
    """
    import ast

    calibration_path = Path(__file__).resolve().parent / "calibration.py"
    source = calibration_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(calibration_path))

    forbidden_modules = {"openai", "requests", "urllib.request", "httpx", "http.client", "socket"}
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden_hits = imported_modules & forbidden_modules
    assert not forbidden_hits, f"Found forbidden network-related imports: {forbidden_hits}"


def test_calibration_runs_successfully_with_no_api_key_set():
    """
    Runs the full calibration pipeline against the real, already-on-disk
    llm_classifier_results.json with OPENAI_API_KEY deliberately unset/removed
    from the environment, confirming the module needs no API access to function.
    """
    old_key = os.environ.pop("OPENAI_API_KEY", None)
    try:
        from evaluation.calibration import load_llm_predictions

        preds = load_llm_predictions()
        assert len(preds) == 200
        confs = [p["confidence"] for p in preds]
        stats = distribution_stats(confs)
        assert stats["n"] == 200
        rows = per_bucket_accuracy(preds, n_buckets=5)
        assert sum(r["n"] for r in rows) == 200
        ece = expected_calibration_error(rows)
        assert 0.0 <= ece <= 1.0
        brier = brier_score(preds)
        assert 0.0 <= brier <= 1.0
    finally:
        if old_key is not None:
            os.environ["OPENAI_API_KEY"] = old_key
