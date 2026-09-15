"""
Tests for evaluation/k_ablation_stats.py: the paired Wilcoxon comparison logic and the
Holm-Bonferroni multiple-comparisons adjustment. All synthetic/deterministic -- no API
calls, no dependency on the real sweep having run.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluation.k_ablation_stats import (
    DIMENSIONS,
    TREATMENT_KS,
    holm_bonferroni,
    paired_scores_by_k,
    run_all_comparisons,
    run_wilcoxon_comparison,
)


# ============================================================
# run_wilcoxon_comparison -- known synthetic cases
# ============================================================

def test_all_positive_differences_yields_significant_result_correct_direction():
    """Every treatment score is baseline+1: an unambiguous, maximal effect. Wilcoxon
    statistic must be 0 (sum of negative-difference ranks), p-value very small, and
    direction must correctly say the treatment is higher."""
    baseline = [1, 2, 3, 4, 5] * 4  # n=20
    treatment = [b + 1 for b in baseline]
    result = run_wilcoxon_comparison(baseline, treatment)
    assert result["n"] == 20
    assert result["statistic"] == 0.0
    assert result["pvalue"] < 0.001
    assert result["direction"] == "treatment (k>0) higher"
    assert result["n_positive_diffs"] == 20
    assert result["n_negative_diffs"] == 0
    assert result["treatment_mean"] - result["baseline_mean"] == pytest.approx(1.0)


def test_all_negative_differences_yields_significant_result_correct_direction():
    baseline = [3, 4, 5, 2, 1] * 4
    treatment = [b - 1 for b in baseline]
    result = run_wilcoxon_comparison(baseline, treatment)
    assert result["statistic"] == 0.0
    assert result["pvalue"] < 0.001
    assert result["direction"] == "baseline (k=0) higher"
    assert result["n_negative_diffs"] == 20


def test_wilcoxon_wrapper_matches_direct_scipy_call_on_mixed_data():
    """Cross-check against calling scipy directly with the same parameters, on a fixed
    mixed-sign, tied-value array (the realistic case for 1-5 integer judge scores) --
    proves the wrapper is a faithful, bug-free pass-through, not testing scipy itself."""
    rng = np.random.RandomState(12345)
    baseline = rng.randint(1, 6, size=40).astype(float)
    treatment = rng.randint(1, 6, size=40).astype(float)

    expected = wilcoxon(treatment, baseline, zero_method="pratt", method="approx",
                         correction=True, alternative="two-sided")
    result = run_wilcoxon_comparison(baseline, treatment)

    assert result["statistic"] == pytest.approx(expected.statistic)
    assert result["pvalue"] == pytest.approx(expected.pvalue)
    assert result["zstatistic"] == pytest.approx(expected.zstatistic)


def test_effect_size_r_matches_z_over_sqrt_n():
    baseline = [1, 2, 3, 4, 5] * 4
    treatment = [b + 1 for b in baseline]
    result = run_wilcoxon_comparison(baseline, treatment)
    expected_r = result["zstatistic"] / np.sqrt(result["n"])
    assert result["effect_size_r"] == pytest.approx(expected_r)


def test_identical_arrays_raise_rather_than_silently_report_a_p_value():
    """All-zero differences: scipy raises for the exact method, and with zero_method='pratt'
    (retaining zeros) the normal-approximation path degenerates to a zero-variance z --
    either way this must surface as an explicit error, not a silently fabricated p=1.0."""
    baseline = [3, 3, 3, 3, 3]
    treatment = [3, 3, 3, 3, 3]
    with pytest.raises((ValueError, ZeroDivisionError, RuntimeWarning)):
        run_wilcoxon_comparison(baseline, treatment)


def test_descriptive_stats_are_correct_for_a_known_small_case():
    baseline = [1, 2, 3, 4]
    treatment = [2, 2, 4, 6]
    result = run_wilcoxon_comparison(baseline, treatment)
    assert result["baseline_mean"] == pytest.approx(2.5)
    assert result["baseline_median"] == pytest.approx(2.5)
    assert result["treatment_mean"] == pytest.approx(3.5)
    assert result["treatment_median"] == pytest.approx(3.0)
    assert result["n_positive_diffs"] == 3  # (2-1),(4-3),(6-4) positive; (2-2)=0
    assert result["n_zero_diffs"] == 1


# ============================================================
# Holm-Bonferroni -- known hand-computed case
# ============================================================

def test_holm_bonferroni_matches_hand_computed_values():
    """4 p-values, hand-computed Holm adjustment:
    sorted: 0.01 (m=4 -> 0.04), 0.02 (m=3 -> 0.06), 0.03 (m=2 -> 0.06, but running-max
    with prior 0.06 -> 0.06), 0.50 (m=1 -> 0.50, running-max -> 0.50).
    Step-down monotonicity: adjusted p's must be non-decreasing in raw-p order.
    """
    raw = [0.01, 0.02, 0.03, 0.50]
    adjusted = holm_bonferroni(raw)
    assert adjusted[0] == pytest.approx(0.04)
    assert adjusted[1] == pytest.approx(0.06)
    assert adjusted[2] == pytest.approx(0.06)
    assert adjusted[3] == pytest.approx(0.50)


def test_holm_bonferroni_preserves_input_order_not_sorted_order():
    raw = [0.50, 0.01, 0.03, 0.02]  # deliberately unsorted
    adjusted = holm_bonferroni(raw)
    # the smallest raw p (0.01, index 1) should get the largest multiplier (m=4)
    assert adjusted[1] == pytest.approx(0.04)
    # the largest raw p (0.50, index 0) should be unchanged (m=1, and already the max)
    assert adjusted[0] == pytest.approx(0.50)


def test_holm_bonferroni_never_exceeds_1():
    raw = [0.9, 0.8, 0.99, 0.95]
    adjusted = holm_bonferroni(raw)
    assert all(a <= 1.0 for a in adjusted)


def test_holm_bonferroni_single_pvalue_unchanged():
    assert holm_bonferroni([0.03]) == pytest.approx([0.03])


# ============================================================
# run_all_comparisons -- structure and exhaustiveness (synthetic records)
# ============================================================

def _synthetic_sweep_records(n_examples=200, seed=0):
    rng = np.random.RandomState(seed)
    records = []
    for i in range(n_examples):
        tweet_id = str(1000 + i)
        for k in (0, 1, 3, 5):
            # k>0 conditions score slightly higher on average, to exercise a real effect
            bump = 0 if k == 0 else 1
            scores = {
                dim: int(np.clip(rng.randint(1, 5) + (bump if rng.random() < 0.4 else 0), 1, 5))
                for dim in DIMENSIONS
            }
            records.append(dict(tweet_id=tweet_id, k=k, judge_scores=scores))
    return records


def test_run_all_comparisons_produces_exactly_12_comparisons_in_fixed_order():
    records = _synthetic_sweep_records()
    comparisons = run_all_comparisons(records)
    assert len(comparisons) == len(TREATMENT_KS) * len(DIMENSIONS) == 12

    expected_order = [(k, dim) for k in TREATMENT_KS for dim in DIMENSIONS]
    actual_order = [(c["k"], c["dimension"]) for c in comparisons]
    assert actual_order == expected_order


def test_run_all_comparisons_every_comparison_uses_all_200_pairs():
    records = _synthetic_sweep_records()
    comparisons = run_all_comparisons(records)
    assert all(c["n"] == 200 for c in comparisons)


def test_run_all_comparisons_includes_holm_adjustment_for_every_comparison():
    records = _synthetic_sweep_records()
    comparisons = run_all_comparisons(records)
    for c in comparisons:
        assert "pvalue_holm_adjusted" in c
        assert c["pvalue_holm_adjusted"] >= c["pvalue"] - 1e-12  # Holm never makes a p-value smaller


def test_run_all_comparisons_raises_if_a_k_condition_is_missing():
    records = [r for r in _synthetic_sweep_records() if r["k"] != 3]  # drop k=3 entirely
    with pytest.raises(ValueError):
        run_all_comparisons(records)


def test_paired_scores_by_k_groups_correctly():
    records = [
        dict(tweet_id="1", k=0, judge_scores={"relevance": 3}),
        dict(tweet_id="1", k=1, judge_scores={"relevance": 4}),
        dict(tweet_id="2", k=0, judge_scores={"relevance": 2}),
    ]
    grouped = paired_scores_by_k(records, "relevance")
    assert grouped[0] == {"1": 3, "2": 2}
    assert grouped[1] == {"1": 4}
