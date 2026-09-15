# Retrieval k-Ablation: Full 200x4 Sweep Results

Generated from `evaluation/results/k_ablation_sweep.json` (800/800 conditions, 0 failures,
all integrity checks passed) via `evaluation/run_k_ablation_stats.py`.

## Sweep configuration

| Setting | Value |
|---|---|
| GENERATE_MODEL | `gpt-5.6-terra` |
| JUDGE_MODEL | `gpt-5.6-sol` |
| temperature / seed / reasoning_effort | 0 / 42 / `none` |
| max_workers | 8 |
| k conditions | [0, 1, 3, 5] |
| n examples x k conditions | 200 x 4 = 800 |
| Elapsed (concurrent phase) | 558.0s |

## Evidence-cleaning (Part 1) prevalence across the real sweep

Out of 1800 total retrieved evidence items shown to the
generator/judge across all k>0 conditions:

- **agent_signoff**: 1682 removed (93.4% of all evidence items)
- **uncued_trailing_url**: 588 removed (32.7% of all evidence items)

## Descriptive judge scores by k (all 200 examples, mean of 1-5 scale)

| k | n | Relevance | Groundedness | Helpfulness | Tone |
|---|---:|---:|---:|---:|---:|
| 0 | 200 | 4.825 | 4.295 | 3.815 | 4.985 |
| 1 | 200 | 4.360 | 4.730 | 3.515 | 4.565 |
| 3 | 200 | 4.700 | 4.910 | 3.950 | 4.795 |
| 5 | 200 | 4.690 | 4.940 | 3.940 | 4.860 |

## Full 12-comparison paired Wilcoxon table

12 pre-specified comparisons (3 treatment k values x 4 judge dimensions), each a paired
Wilcoxon signed-rank test vs. the k=0 baseline over the same 200 examples. All 12 are
reported below in the fixed order they were run -- no post-hoc "best k" selection.

| k vs 0 | Dimension | n | Mean k=0 | Mean k | Statistic | z | Effect r | p (raw) | p (Holm) | Direction |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| k=1 | relevance | 200 | 4.825 | 4.360 | 1999.0 | -6.713 | -0.475 | 0.000000 | 0.000000 | baseline (k=0) higher |
| k=1 | groundedness | 200 | 4.295 | 4.730 | 2731.0 | -5.840 | -0.413 | 0.000000 | 0.000000 | treatment (k>0) higher |
| k=1 | helpfulness | 200 | 3.815 | 3.515 | 4106.0 | -4.077 | -0.288 | 0.000046 | 0.000229 | baseline (k=0) higher |
| k=1 | tone | 200 | 4.985 | 4.565 | 157.5 | -8.882 | -0.628 | 0.000000 | 0.000000 | baseline (k=0) higher |
| k=3 | relevance | 200 | 4.825 | 4.700 | 2810.0 | -2.837 | -0.201 | 0.004559 | 0.018238 | baseline (k=0) higher |
| k=3 | groundedness | 200 | 4.295 | 4.910 | 808.5 | -8.198 | -0.580 | 0.000000 | 0.000000 | treatment (k>0) higher |
| k=3 | helpfulness | 200 | 3.815 | 3.950 | 4764.0 | -2.811 | -0.199 | 0.004935 | 0.018238 | treatment (k>0) higher |
| k=3 | tone | 200 | 4.985 | 4.795 | 535.5 | -5.643 | -0.399 | 0.000000 | 0.000000 | baseline (k=0) higher |
| k=5 | relevance | 200 | 4.825 | 4.690 | 2806.0 | -2.439 | -0.172 | 0.014735 | 0.018238 | baseline (k=0) higher |
| k=5 | groundedness | 200 | 4.295 | 4.940 | 423.0 | -8.722 | -0.617 | 0.000000 | 0.000000 | treatment (k>0) higher |
| k=5 | helpfulness | 200 | 3.815 | 3.940 | 4934.5 | -2.715 | -0.192 | 0.006618 | 0.018238 | treatment (k>0) higher |
| k=5 | tone | 200 | 4.985 | 4.860 | 555.0 | -4.275 | -0.302 | 0.000019 | 0.000115 | baseline (k=0) higher |

**12/12 comparisons significant at raw p<0.05; 12/12 remain significant after
Holm-Bonferroni adjustment.**

## Multiple comparisons

12 non-independent tests were run (4 judge dimensions scored from the same call are
correlated; k=1/3/5 all share the same k=0 baseline scores). Holm-Bonferroni was applied
across all 12 raw p-values to control the family-wise error rate; it does not require
independence between tests (unlike some alternatives) and is less conservative than plain
Bonferroni. Both raw and Holm-adjusted p-values are reported for every comparison above --
neither is hidden.
