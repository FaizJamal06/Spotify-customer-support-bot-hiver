"""
Exploratory calibration analysis for the LLM intent classifier.

IMPORTANT (terminology, applies everywhere this module is used): this is an
EXPLORATORY CALIBRATION ANALYSIS, not a calibration certification. With
n=200 examples spread across 8 imbalanced classes, per-bucket sample sizes
are small; results here are suggestive evidence about calibration behavior,
not proof that the model "is well-calibrated." Never describe the output of
this module as a calibration guarantee.

Reads ONLY from evaluation/results/llm_classifier_results.json (already on
disk from the completed LLM classifier milestone). Makes ZERO API calls --
this module does not import openai, does not construct an OpenAI client,
and does not perform any network I/O.
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

from statsmodels.stats.proportion import proportion_confint

CALIBRATION_ANALYSIS_LABEL = "exploratory calibration analysis"  # use this term everywhere, never "proof of calibration"


def load_llm_predictions(path=None):
    """Reads evaluation/results/llm_classifier_results.json (read-only) and returns a
    list of dicts: {confidence, predicted_intent, gold_label, correct}. No API calls."""
    import json
    path = path or (config.EVAL_DIR / "llm_classifier_results.json")
    with open(path, encoding="utf-8") as f:
        results = json.load(f)
    preds = []
    for p in results["predictions"]:
        correct = int(p["predicted_intent"] == p["gold_label"])
        preds.append(dict(
            confidence=float(p["confidence"]),
            predicted_intent=p["predicted_intent"],
            gold_label=p["gold_label"],
            correct=correct,
        ))
    return preds


def distribution_stats(confidences):
    """min, max, mean, median, and quartiles (Q1/Q3) of the raw confidence values."""
    sorted_c = sorted(confidences)
    n = len(sorted_c)
    quantiles = statistics.quantiles(sorted_c, n=4, method="inclusive") if n >= 2 else [sorted_c[0]] * 3
    return dict(
        n=n,
        min=min(sorted_c),
        max=max(sorted_c),
        mean=statistics.mean(sorted_c),
        median=statistics.median(sorted_c),
        q1=quantiles[0],
        q3=quantiles[2],
    )


def quantile_split(items, n_buckets=5, key=lambda x: x):
    """
    Splits `items` into n_buckets contiguous groups of as-equal-as-possible SIZE
    (equal-frequency / quantile binning), after stably sorting by `key`. Returns a
    list of n_buckets lists.

    Deliberately index-based rather than value-boundary-based: LLM confidence scores
    cluster heavily at a handful of round-ish values (e.g. many examples tied at
    exactly 0.98), so computing a fixed VALUE boundary per bucket and then
    reassigning items by "is this value within [lo, hi)" can collapse a bucket to
    zero examples whenever a tie straddles a boundary. Splitting by sorted RANK
    instead guarantees every bucket gets floor(n/k) or ceil(n/k) items regardless
    of ties, at the cost of ties exactly at a cut point being split across two
    buckets by stable-sort order (acceptable for this exploratory analysis; the
    resulting bucket boundary values are reported so this is auditable).
    """
    ordered = sorted(items, key=key)
    n = len(ordered)
    base, rem = divmod(n, n_buckets)
    groups, idx = [], 0
    for b in range(n_buckets):
        size = base + (1 if b < rem else 0)
        groups.append(ordered[idx: idx + size])
        idx += size
    return groups


def quantile_bucket_boundaries(confidences, n_buckets=5):
    """
    Returns the [min, max] confidence spanned by each of the n_buckets equal-frequency
    groups produced by quantile_split(), as a flat list of n_buckets+1 boundary values
    (ascending) -- boundaries[i], boundaries[i+1] is the [min, max] of bucket i. These
    are DERIVED FROM the same index-based grouping used everywhere else in this module
    (never recomputed independently), so the reported boundaries always match the
    actual bucket assignment -- including when many values are tied.
    """
    groups = quantile_split(confidences, n_buckets=n_buckets)
    boundaries = [groups[0][0]]
    for g in groups:
        boundaries.append(g[-1])
    return boundaries


def wilson_interval(successes, n, confidence_level=0.95):
    """95% Wilson score interval for a binomial proportion (successes/n). Uses
    statsmodels' proportion_confint(method='wilson') -- a standard, independently-
    verified implementation rather than a hand-rolled formula. Returns (lower, upper)."""
    if n == 0:
        return (float("nan"), float("nan"))
    alpha = 1 - confidence_level
    lo, hi = proportion_confint(successes, n, alpha=alpha, method="wilson")
    return (float(lo), float(hi))


def per_bucket_accuracy(predictions, n_buckets=5):
    """
    Splits `predictions` (list of {confidence, correct, ...}) into n_buckets
    equal-frequency groups by confidence (quantile_split), and for each bucket
    computes: n, accuracy (point estimate), Wilson 95% CI, mean predicted confidence,
    and the [lower_bound, upper_bound] confidence range actually spanned by that
    bucket's examples. Buckets are ordered from lowest to highest confidence.
    """
    groups = quantile_split(predictions, n_buckets=n_buckets, key=lambda p: p["confidence"])
    rows = []
    for b, items in enumerate(groups):
        n = len(items)
        if n == 0:
            rows.append(dict(bucket=b, n=0, accuracy=None, wilson_lo=None, wilson_hi=None,
                              mean_confidence=None, lower_bound=None, upper_bound=None))
            continue
        correct = sum(p["correct"] for p in items)
        acc = correct / n
        lo, hi = wilson_interval(correct, n)
        mean_conf = statistics.mean(p["confidence"] for p in items)
        confs = [p["confidence"] for p in items]
        rows.append(dict(
            bucket=b, n=n, accuracy=acc, wilson_lo=lo, wilson_hi=hi,
            mean_confidence=mean_conf, lower_bound=min(confs), upper_bound=max(confs),
        ))
    return rows


def expected_calibration_error(bucket_rows):
    """ECE = sum_over_bins( (n_bin / N) * |accuracy_bin - mean_confidence_bin| ),
    using the same quantile bins as per_bucket_accuracy(). Bins with n=0 are skipped
    (should not occur with equal-frequency binning unless n_buckets > n examples)."""
    total_n = sum(r["n"] for r in bucket_rows)
    if total_n == 0:
        return float("nan")
    ece = 0.0
    for r in bucket_rows:
        if r["n"] == 0:
            continue
        ece += (r["n"] / total_n) * abs(r["accuracy"] - r["mean_confidence"])
    return ece


def brier_score(predictions):
    """
    Brier score = mean( (confidence - correct)^2 ), where `correct` in {0,1} indicates
    whether the model's top (predicted) label matched gold. NOTE: this is the
    single-probability ("confidence in the chosen answer") formulation used when only
    one scalar confidence is available per prediction -- not the full multiclass Brier
    score (which needs a probability assigned to every one of the 8 classes, which this
    classifier's output schema does not produce). Lower is better; 0 = perfect.
    """
    if not predictions:
        return float("nan")
    return statistics.mean((p["confidence"] - p["correct"]) ** 2 for p in predictions)
