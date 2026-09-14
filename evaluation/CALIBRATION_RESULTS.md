# Confidence Calibration -- Exploratory Analysis

> **This is an EXPLORATORY CALIBRATION ANALYSIS, not a calibration certification.** With n=200 examples spread across 8 imbalanced intent classes (n=40 per quantile bucket below), this is suggestive evidence about how the LLM classifier's self-reported confidence relates to its actual accuracy -- **not** statistical proof that the model "is well-calibrated." Per-bucket Wilson 95% confidence intervals are wide (often 15-30 percentage points) precisely because n=40 per bucket is small. Any hard confidence threshold derived from this data should be treated as a starting hypothesis to validate on more data, not a settled cutoff.

Source: `evaluation/results/llm_classifier_results.json` (n=200, zero new API calls made).

## 1. Raw confidence distribution

| Stat | Value |
|---|---|
| n | 200 |
| min | 0.6200 |
| max | 0.9900 |
| mean | 0.9503 |
| median | 0.9700 |
| Q1 | 0.9300 |
| Q3 | 0.9800 |

The distribution is heavily right-skewed: the model reports high confidence (median 0.97) on the large majority of examples, with a long lower tail down to 0.62 on a minority of harder examples.

## 2. Quantile bucketing (why quantile, not equal-width)

Examples were split into 5 **quantile (equal-frequency)** buckets of exactly 40 examples each (200 / 5 divides evenly), rather than equal-width confidence-range buckets. Reason: the confidence distribution above is heavily right-skewed with many tied values (e.g. many examples at exactly 0.98). Equal-width bins over this distribution would put very few examples in the low-confidence bins and most examples in one or two high-confidence bins, making the low-confidence per-bucket accuracy estimates unstable (wide, unreliable Wilson intervals). Equal-frequency bins keep per-bucket n constant at 40, which is what makes the Wilson intervals below comparable in width across buckets. Bucketing is done by sorted RANK (not by re-deriving value boundaries and re-scanning), which avoids a failure mode where tied values straddling a naive value-boundary collapse a bucket to zero examples -- this was hit and fixed during development of this analysis (see `evaluation/calibration.py` `quantile_split()` docstring).

**Exact bucket boundaries** (confidence range spanned by each bucket): [0.62, 0.93, 0.96, 0.98, 0.98, 0.99]

## 3. Per-bucket accuracy with Wilson 95% confidence intervals

| Bucket | Confidence range | n | Mean confidence | Accuracy | Wilson 95% CI |
|---|---|---|---|---|---|
| 0 | [0.62, 0.93] | 40 | 0.8762 | 0.6000 | [0.4460, 0.7365] |
| 1 | [0.93, 0.96] | 40 | 0.9455 | 0.7500 | [0.5981, 0.8581] |
| 2 | [0.96, 0.98] | 40 | 0.9665 | 0.9000 | [0.7695, 0.9604] |
| 3 | [0.98, 0.98] | 40 | 0.9800 | 0.8500 | [0.7093, 0.9294] |
| 4 | [0.98, 0.99] | 40 | 0.9830 | 0.9500 | [0.8350, 0.9862] |

Every accuracy figure above is reported with its Wilson interval, never as a bare point estimate -- at n=40 per bucket, a bare point estimate would be misleading on its own.

## 4. Reliability diagram (predicted confidence vs. empirical accuracy)

Textual reliability diagram (mean predicted confidence vs. empirical accuracy, per bucket -- perfect calibration would have accuracy == mean confidence in every row):

| Bucket | Mean confidence | Empirical accuracy | Gap (confidence - accuracy) |
|---|---|---|---|
| 0 | 0.8762 | 0.6000 | +0.2762 |
| 1 | 0.9455 | 0.7500 | +0.1955 |
| 2 | 0.9665 | 0.9000 | +0.0665 |
| 3 | 0.9800 | 0.8500 | +0.1300 |
| 4 | 0.9830 | 0.9500 | +0.0330 |

In every bucket, mean confidence exceeds empirical accuracy (a positive gap) -- the classifier is **overconfident** relative to its own accuracy across the whole range, most severely in the lowest-confidence bucket (bucket 0: mean confidence 0.88 vs. accuracy 0.60).

## 5. Expected Calibration Error (ECE)

**ECE = 0.1402** (using the same 5 quantile bins as above; ECE = sum_over_bins( (n_bin/N) * |accuracy_bin - mean_confidence_bin| )).

## 6. Brier score (bucket-independent)

**Brier score = 0.1659** (lower is better; 0 = perfect).

Formulation: single-scalar 'confidence in chosen answer' variant: mean((confidence-correct)^2); NOT full multiclass Brier score, since the classifier emits one confidence value per prediction, not a probability distribution over all 8 classes.

## 7. Is this data enough to defend a hard confidence threshold?

**Conclusion, based strictly on the numbers above: no, this data does not support a defensible hard confidence threshold for Tier-2 triage on its own; confidence should be treated as a weak/advisory signal only, not a certified gate.**

Reasons, drawn directly from the results:

- **The model is overconfident everywhere, not just near a boundary.** All 5 buckets show mean confidence above empirical accuracy (section 4). A threshold set at, say, 0.95 would still admit a meaningful error rate, and the gap does not shrink cleanly as confidence rises.
- **The intervals are wide.** At n=40 per bucket, Wilson 95% intervals span roughly 15-30 percentage points (section 3) -- adjacent buckets' intervals overlap substantially, so the data cannot reliably distinguish "accuracy at 0.96" from "accuracy at 0.98" confidence.
- **ECE (0.1402) and Brier score (0.1659) are both non-trivial** for a system meant to gate automated vs. escalated handling -- they indicate real, not negligible, miscalibration.
- **n=200 across 8 imbalanced classes is a small, single evaluation run.** No cross-validation, no repeated sampling, no per-intent confidence-threshold analysis was done here (out of scope for this task). A threshold tuned to this exact sample risks overfitting to its particular composition.

**Recommendation implied by the data (not a decision made here):** if a confidence signal is used in Tier-2 triage at all, it should be one weighted input among several (e.g. combined with per-intent base rates, retrieval agreement, or a small human-reviewed calibration set), not a standalone hard cutoff -- until a larger, dedicated calibration study justifies otherwise.
