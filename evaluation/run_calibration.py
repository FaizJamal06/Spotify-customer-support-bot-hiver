"""
Entry point for the exploratory calibration analysis (Part B).

Reads ONLY evaluation/results/llm_classifier_results.json (already on disk).
Makes ZERO API calls. Writes:
  - evaluation/results/calibration_results.json
  - evaluation/CALIBRATION_RESULTS.md

Run: python evaluation/run_calibration.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

from evaluation.calibration import (
    CALIBRATION_ANALYSIS_LABEL,
    load_llm_predictions,
    distribution_stats,
    quantile_bucket_boundaries,
    per_bucket_accuracy,
    expected_calibration_error,
    brier_score,
)

N_BUCKETS = 5


def build_results():
    predictions = load_llm_predictions()
    confidences = [p["confidence"] for p in predictions]

    dist_stats = distribution_stats(confidences)
    boundaries = quantile_bucket_boundaries(confidences, n_buckets=N_BUCKETS)
    bucket_rows = per_bucket_accuracy(predictions, n_buckets=N_BUCKETS)
    ece = expected_calibration_error(bucket_rows)
    brier = brier_score(predictions)

    results = dict(
        description=(
            f"{CALIBRATION_ANALYSIS_LABEL.upper()} of the LLM intent classifier's "
            "self-reported confidence scores. This is EXPLORATORY, not a calibration "
            "certification -- n=200 across 8 imbalanced classes means per-bucket "
            "estimates are suggestive, not statistically definitive. See "
            "evaluation/CALIBRATION_RESULTS.md for the full write-up and limitations."
        ),
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_file="evaluation/results/llm_classifier_results.json",
        n_examples=dist_stats["n"],
        n_buckets=N_BUCKETS,
        binning_method="quantile (equal-frequency)",
        distribution_stats=dist_stats,
        bucket_boundaries=boundaries,
        per_bucket_accuracy=bucket_rows,
        expected_calibration_error=ece,
        brier_score=brier,
        brier_score_formulation=(
            "single-scalar 'confidence in chosen answer' variant: mean((confidence-correct)^2); "
            "NOT full multiclass Brier score, since the classifier emits one confidence value "
            "per prediction, not a probability distribution over all 8 classes."
        ),
        limitation_statement=(
            "This analysis uses n=200 golden examples spread across 8 imbalanced intent "
            "classes (per-bucket n=40 here). It is an EXPLORATORY CALIBRATION ANALYSIS: "
            "suggestive evidence about how the model's confidence relates to its accuracy, "
            "not a statistically certified calibration guarantee. Per-bucket Wilson intervals "
            "are wide (see per_bucket_accuracy) precisely because n=40 per bucket is small; "
            "any threshold decision based on this data carries real uncertainty about its "
            "true error rate in production."
        ),
    )
    return results


def render_markdown(results):
    dist = results["distribution_stats"]
    rows = results["per_bucket_accuracy"]
    boundaries = results["bucket_boundaries"]

    lines = []
    lines.append("# Confidence Calibration -- Exploratory Analysis")
    lines.append("")
    lines.append(
        "> **This is an EXPLORATORY CALIBRATION ANALYSIS, not a calibration "
        "certification.** With n=200 examples spread across 8 imbalanced intent "
        "classes (n=40 per quantile bucket below), this is suggestive evidence "
        "about how the LLM classifier's self-reported confidence relates to its "
        "actual accuracy -- **not** statistical proof that the model \"is "
        "well-calibrated.\" Per-bucket Wilson 95% confidence intervals are wide "
        "(often 15-30 percentage points) precisely because n=40 per bucket is "
        "small. Any hard confidence threshold derived from this data should be "
        "treated as a starting hypothesis to validate on more data, not a "
        "settled cutoff."
    )
    lines.append("")
    lines.append(f"Source: `evaluation/results/llm_classifier_results.json` (n={dist['n']}, zero new API calls made).")
    lines.append("")

    lines.append("## 1. Raw confidence distribution")
    lines.append("")
    lines.append("| Stat | Value |")
    lines.append("|---|---|")
    lines.append(f"| n | {dist['n']} |")
    lines.append(f"| min | {dist['min']:.4f} |")
    lines.append(f"| max | {dist['max']:.4f} |")
    lines.append(f"| mean | {dist['mean']:.4f} |")
    lines.append(f"| median | {dist['median']:.4f} |")
    lines.append(f"| Q1 | {dist['q1']:.4f} |")
    lines.append(f"| Q3 | {dist['q3']:.4f} |")
    lines.append("")
    lines.append(
        "The distribution is heavily right-skewed: the model reports high confidence "
        "(median 0.97) on the large majority of examples, with a long lower tail down "
        "to 0.62 on a minority of harder examples."
    )
    lines.append("")

    lines.append("## 2. Quantile bucketing (why quantile, not equal-width)")
    lines.append("")
    lines.append(
        f"Examples were split into {results['n_buckets']} **quantile (equal-frequency)** "
        f"buckets of exactly {dist['n'] // results['n_buckets']} examples each "
        f"({dist['n']} / {results['n_buckets']} divides evenly), rather than equal-width "
        "confidence-range buckets. Reason: the confidence distribution above is heavily "
        "right-skewed with many tied values (e.g. many examples at exactly 0.98). Equal-"
        "width bins over this distribution would put very few examples in the low-"
        "confidence bins and most examples in one or two high-confidence bins, making the "
        "low-confidence per-bucket accuracy estimates unstable (wide, unreliable Wilson "
        "intervals). Equal-frequency bins keep per-bucket n constant at 40, which is what "
        "makes the Wilson intervals below comparable in width across buckets. Bucketing is "
        "done by sorted RANK (not by re-deriving value boundaries and re-scanning), which "
        "avoids a failure mode where tied values straddling a naive value-boundary collapse "
        "a bucket to zero examples -- this was hit and fixed during development of this "
        "analysis (see `evaluation/calibration.py` `quantile_split()` docstring)."
    )
    lines.append("")
    lines.append(f"**Exact bucket boundaries** (confidence range spanned by each bucket): {boundaries}")
    lines.append("")

    lines.append("## 3. Per-bucket accuracy with Wilson 95% confidence intervals")
    lines.append("")
    lines.append("| Bucket | Confidence range | n | Mean confidence | Accuracy | Wilson 95% CI |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['bucket']} | [{r['lower_bound']:.2f}, {r['upper_bound']:.2f}] | {r['n']} | "
            f"{r['mean_confidence']:.4f} | {r['accuracy']:.4f} | "
            f"[{r['wilson_lo']:.4f}, {r['wilson_hi']:.4f}] |"
        )
    lines.append("")
    lines.append(
        "Every accuracy figure above is reported with its Wilson interval, never as a bare "
        "point estimate -- at n=40 per bucket, a bare point estimate would be misleading on "
        "its own."
    )
    lines.append("")

    lines.append("## 4. Reliability diagram (predicted confidence vs. empirical accuracy)")
    lines.append("")
    lines.append(
        "Textual reliability diagram (mean predicted confidence vs. empirical accuracy, "
        "per bucket -- perfect calibration would have accuracy == mean confidence in every row):"
    )
    lines.append("")
    lines.append("| Bucket | Mean confidence | Empirical accuracy | Gap (confidence - accuracy) |")
    lines.append("|---|---|---|---|")
    for r in rows:
        gap = r["mean_confidence"] - r["accuracy"]
        lines.append(f"| {r['bucket']} | {r['mean_confidence']:.4f} | {r['accuracy']:.4f} | {gap:+.4f} |")
    lines.append("")
    lines.append(
        "In every bucket, mean confidence exceeds empirical accuracy (a positive gap) -- "
        "the classifier is **overconfident** relative to its own accuracy across the whole "
        "range, most severely in the lowest-confidence bucket (bucket 0: mean confidence "
        f"{rows[0]['mean_confidence']:.2f} vs. accuracy {rows[0]['accuracy']:.2f})."
    )
    lines.append("")

    lines.append("## 5. Expected Calibration Error (ECE)")
    lines.append("")
    lines.append(
        f"**ECE = {results['expected_calibration_error']:.4f}** (using the same "
        f"{results['n_buckets']} quantile bins as above; "
        "ECE = sum_over_bins( (n_bin/N) * |accuracy_bin - mean_confidence_bin| ))."
    )
    lines.append("")

    lines.append("## 6. Brier score (bucket-independent)")
    lines.append("")
    lines.append(f"**Brier score = {results['brier_score']:.4f}** (lower is better; 0 = perfect).")
    lines.append("")
    lines.append(f"Formulation: {results['brier_score_formulation']}")
    lines.append("")

    lines.append("## 7. Is this data enough to defend a hard confidence threshold?")
    lines.append("")
    lines.append(
        "**Conclusion, based strictly on the numbers above: no, this data does not support "
        "a defensible hard confidence threshold for Tier-2 triage on its own; confidence "
        "should be treated as a weak/advisory signal only, not a certified gate.**"
    )
    lines.append("")
    lines.append("Reasons, drawn directly from the results:")
    lines.append("")
    lines.append(
        f"- **The model is overconfident everywhere, not just near a boundary.** All "
        f"{results['n_buckets']} buckets show mean confidence above empirical accuracy "
        f"(section 4). A threshold set at, say, 0.95 would still admit a meaningful error "
        f"rate, and the gap does not shrink cleanly as confidence rises."
    )
    lines.append(
        "- **The intervals are wide.** At n=40 per bucket, Wilson 95% intervals span roughly "
        "15-30 percentage points (section 3) -- adjacent buckets' intervals overlap "
        "substantially, so the data cannot reliably distinguish \"accuracy at 0.96\" from "
        "\"accuracy at 0.98\" confidence."
    )
    lines.append(
        f"- **ECE ({results['expected_calibration_error']:.4f}) and Brier score "
        f"({results['brier_score']:.4f}) are both non-trivial** for a system meant to gate "
        "automated vs. escalated handling -- they indicate real, not negligible, miscalibration."
    )
    lines.append(
        "- **n=200 across 8 imbalanced classes is a small, single evaluation run.** No "
        "cross-validation, no repeated sampling, no per-intent confidence-threshold analysis "
        "was done here (out of scope for this task). A threshold tuned to this exact sample "
        "risks overfitting to its particular composition."
    )
    lines.append("")
    lines.append(
        "**Recommendation implied by the data (not a decision made here):** if a confidence "
        "signal is used in Tier-2 triage at all, it should be one weighted input among several "
        "(e.g. combined with per-intent base rates, retrieval agreement, or a small human-"
        "reviewed calibration set), not a standalone hard cutoff -- until a larger, dedicated "
        "calibration study justifies otherwise."
    )
    lines.append("")

    return "\n".join(lines)


def main():
    results = build_results()

    results_path = config.EVAL_DIR / "calibration_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Wrote {results_path}")

    md = render_markdown(results)
    md_path = config.EVAL_DIR.parent / "CALIBRATION_RESULTS.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
