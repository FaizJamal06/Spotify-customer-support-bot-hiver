"""
Part 6: the pre-specified statistical comparison for Experiment 3 (retrieval k-ablation).

Exactly 12 pre-specified paired comparisons (implementation_plan.md §9's "Metrics per
condition", made concrete per this milestone's instructions): for each of k in {1, 3, 5}
vs. k=0, and for each of Relevance / Groundedness / Helpfulness / Tone, a paired Wilcoxon
signed-rank test over the 200 golden examples (same examples, paired by tweet_id, across
conditions).

No post-hoc "best k" selection: run_all_comparisons() always runs and reports all 12,
in the same fixed order, before anything downstream may summarize the results.

Multiple comparisons: 12 non-independent tests (4 correlated judge dimensions scored from
the same call; k=1/3/5 all share the same k=0 baseline). Holm-Bonferroni is applied across
all 12 p-values (family-wise error rate control; unlike plain Bonferroni it does not require
independence, and is less conservative). Both raw and Holm-adjusted p-values are reported
for every comparison -- neither is hidden.
"""
import sys
from pathlib import Path
from statistics import mean, median, stdev

import numpy as np
from scipy.stats import wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DIMENSIONS = ("relevance", "groundedness", "helpfulness", "tone")
TREATMENT_KS = (1, 3, 5)
BASELINE_K = 0


def paired_scores_by_k(records, dimension):
    """records: list of sweep result dicts (each has tweet_id, k, judge_scores).
    Returns {k: {tweet_id: score}} for the given dimension, across all k present."""
    out = {}
    for r in records:
        out.setdefault(r["k"], {})[r["tweet_id"]] = r["judge_scores"][dimension]
    return out


def _aligned_arrays(baseline_map, treatment_map):
    """Both maps are {tweet_id: score}. Returns (baseline_array, treatment_array) aligned
    by the SAME tweet_id order (sorted for determinism), restricted to tweet_ids present
    in both (should be all 200 for a complete, paired sweep -- see integrity checks)."""
    common_ids = sorted(set(baseline_map) & set(treatment_map), key=lambda t: int(t))
    baseline = np.array([baseline_map[t] for t in common_ids], dtype=float)
    treatment = np.array([treatment_map[t] for t in common_ids], dtype=float)
    return baseline, treatment, common_ids


def run_wilcoxon_comparison(baseline_scores, treatment_scores):
    """baseline_scores, treatment_scores: aligned 1-D arrays (same length, paired by index).
    Returns a dict with n, statistic, pvalue, zstatistic, effect_size_r (matched-pairs
    rank-biserial correlation, r = z / sqrt(n)), direction, and descriptive stats for both
    sides. Raises ValueError if every paired difference is exactly zero (scipy's own
    behavior -- surfaced, not swallowed)."""
    baseline_scores = np.asarray(baseline_scores, dtype=float)
    treatment_scores = np.asarray(treatment_scores, dtype=float)
    n = len(baseline_scores)
    if n == 0:
        raise ValueError("no paired observations to compare")

    diffs = treatment_scores - baseline_scores
    result = wilcoxon(
        treatment_scores, baseline_scores,
        zero_method="pratt",  # retains zero-difference pairs in the ranking (many ties expected: 1-5 integer scores)
        method="approx",      # normal approximation -- gives a z-statistic for a consistent effect-size formula
        correction=True,
        alternative="two-sided",
    )
    z = result.zstatistic
    effect_size_r = float(z) / np.sqrt(n) if n > 0 else float("nan")

    mean_diff = float(np.mean(diffs))
    if mean_diff > 0:
        direction = "treatment (k>0) higher"
    elif mean_diff < 0:
        direction = "baseline (k=0) higher"
    else:
        direction = "no difference in means"

    return dict(
        n=n,
        statistic=float(result.statistic),
        zstatistic=float(z),
        pvalue=float(result.pvalue),
        effect_size_r=float(effect_size_r),
        direction=direction,
        n_positive_diffs=int(np.sum(diffs > 0)),
        n_negative_diffs=int(np.sum(diffs < 0)),
        n_zero_diffs=int(np.sum(diffs == 0)),
        baseline_mean=float(mean(baseline_scores)),
        baseline_median=float(median(baseline_scores)),
        baseline_stdev=float(stdev(baseline_scores)) if n > 1 else 0.0,
        treatment_mean=float(mean(treatment_scores)),
        treatment_median=float(median(treatment_scores)),
        treatment_stdev=float(stdev(treatment_scores)) if n > 1 else 0.0,
    )


def holm_bonferroni(pvalues):
    """Standard Holm-Bonferroni step-down adjustment. Returns adjusted p-values in the
    SAME order as the input (not sorted), each clipped to <= 1.0 and monotonically
    non-decreasing when read in ascending-p order (the standard Holm guarantee)."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [None] * m
    running_max = 0.0
    for rank, idx in enumerate(order):  # rank is 0-based
        candidate = (m - rank) * pvalues[idx]
        running_max = max(running_max, candidate)
        adjusted[idx] = min(running_max, 1.0)
    return adjusted


def run_all_comparisons(records, dimensions=DIMENSIONS, treatment_ks=TREATMENT_KS, baseline_k=BASELINE_K):
    """Runs all len(treatment_ks) * len(dimensions) pre-specified comparisons, in a FIXED
    order (treatment_ks outer, dimensions inner), and appends Holm-Bonferroni-adjusted
    p-values across the full set. Returns a list of comparison dicts -- always the full
    set, never a post-hoc subset."""
    comparisons = []
    for k in treatment_ks:
        for dim in dimensions:
            by_k = paired_scores_by_k(records, dim)
            if baseline_k not in by_k:
                raise ValueError(f"No k={baseline_k} records found for dimension {dim!r}")
            if k not in by_k:
                raise ValueError(f"No k={k} records found for dimension {dim!r}")
            baseline_arr, treatment_arr, common_ids = _aligned_arrays(by_k[baseline_k], by_k[k])
            result = run_wilcoxon_comparison(baseline_arr, treatment_arr)
            result["comparison"] = f"k={k} vs k={baseline_k}"
            result["dimension"] = dim
            result["k"] = k
            result["baseline_k"] = baseline_k
            comparisons.append(result)

    raw_pvalues = [c["pvalue"] for c in comparisons]
    adjusted = holm_bonferroni(raw_pvalues)
    for c, adj_p in zip(comparisons, adjusted):
        c["pvalue_holm_adjusted"] = adj_p
        c["significant_raw_p_lt_05"] = c["pvalue"] < 0.05
        c["significant_holm_adjusted_p_lt_05"] = adj_p < 0.05

    return comparisons
