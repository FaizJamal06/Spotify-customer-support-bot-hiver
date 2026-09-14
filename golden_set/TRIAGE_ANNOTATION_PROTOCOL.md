# Triage Annotation Protocol (n=40 shared subset)

## What this is

A single, deterministic, 40-example subset of `golden_set/GOLDEN_200_FINAL.csv`,
used as the basis for `golden_set/TRIAGE_ANNOTATION_40.csv`. This same 40-example
subset is intended to be reused later for judge calibration as well — **do not
draw a second, different 40-example sample when that task comes up**; reuse the
example_ids listed below.

This is a **separate, additive annotation layer** on top of the frozen intent
gold set. It does **not** modify `golden_set/GOLDEN_200_FINAL.csv` or any of its
200 `human_gold_label` values in any way. No pre-existing 40-example
judge-calibration or triage subset was found anywhere else in the repository
before this one was created (searched `golden_set/`, `evaluation/`, and all
markdown docs for "40", "TRIAGE", "JUDGE", and related terms).

## Sampling method

- **Source**: all 200 rows of `golden_set/GOLDEN_200_FINAL.csv` (read-only).
- **Stratified by**: `human_gold_label` (the 8 frozen intents).
- **Target size**: 40 examples (20% of 200).
- **Per-class allocation**: proportional to each class's share of the 200
  golden examples, computed exactly (`40 * class_count / 200`), then rounded
  to integers via the **largest-remainder (Hamilton) apportionment method**
  so the 8 per-class counts sum to exactly 40. Ties in the remainder step are
  broken deterministically by each label's position in `config.FROZEN_LABELS`
  (`ACCOUNT_ACCESS, SUBSCRIPTION_BILLING, APP_TECH_ISSUE, CONTENT_CATALOG,
  FEATURE_FEEDBACK, ARTIST_SUPPORT, GENERAL_HOW_TO_INFO, UNKNOWN_OTHER`).
- **Row selection within each class**: a single `random.Random(SEED)` instance
  (seed = 42, matching this project's existing seed convention —
  `config.BASELINE_SEED` / `config.LLM_SEED`), consumed once per class in
  `config.FROZEN_LABELS` order, sampling without replacement from that class's
  rows sorted by `candidate_id`. This makes the result exactly reproducible —
  see `golden_set/build_triage_sample.py`.
- Every class had enough available examples to hit its target count cleanly
  (smallest class, `ARTIST_SUPPORT`, has 14 available and only needed 3) — no
  class required falling back to unstratified sampling.

## Per-class distribution (200-example golden set vs. 40-example subset)

| Intent | Count in golden-200 | Exact proportional target (40 * n/200) | Final stratified count |
|---|---|---|---|
| ACCOUNT_ACCESS | 19 | 3.8 | 4 |
| SUBSCRIPTION_BILLING | 21 | 4.2 | 4 |
| APP_TECH_ISSUE | 40 | 8.0 | 8 |
| CONTENT_CATALOG | 15 | 3.0 | 3 |
| FEATURE_FEEDBACK | 40 | 8.0 | 8 |
| ARTIST_SUPPORT | 14 | 2.8 | 3 |
| GENERAL_HOW_TO_INFO | 28 | 5.6 | 6 |
| UNKNOWN_OTHER | 23 | 4.6 | 4 |
| **Total** | **200** | **40.0** | **40** |

Three classes (`ACCOUNT_ACCESS`, `ARTIST_SUPPORT`, and one of the
`GENERAL_HOW_TO_INFO`/`UNKNOWN_OTHER` tie) received one extra example each via
the largest-remainder step, since 40/200 does not divide every class count
into a whole number. `ACCOUNT_ACCESS` (remainder 0.8) and `ARTIST_SUPPORT`
(remainder 0.8) had the two largest remainders; `GENERAL_HOW_TO_INFO` won the
remaining slot over the tied `UNKNOWN_OTHER` (both remainder 0.6) via the
`config.FROZEN_LABELS`-order tie-break.

## The 40 selected example_ids (sorted ascending)

```
CAND_0003, CAND_0013, CAND_0014, CAND_0017, CAND_0018, CAND_0021, CAND_0026,
CAND_0027, CAND_0030, CAND_0034, CAND_0045, CAND_0054, CAND_0056, CAND_0058,
CAND_0059, CAND_0063, CAND_0068, CAND_0071, CAND_0072, CAND_0080, CAND_0084,
CAND_0085, CAND_0088, CAND_0094, CAND_0109, CAND_0110, CAND_0120, CAND_0129,
CAND_0134, CAND_0138, CAND_0140, CAND_0141, CAND_0151, CAND_0165, CAND_0177,
CAND_0179, CAND_0183, CAND_0187, CAND_0190, CAND_0200
```

(40 ids, matching the `example_id` column of `golden_set/TRIAGE_ANNOTATION_40.csv`
exactly, same order.)

## What the annotator sees

The annotator (Faiz) sees, per row: `example_id`, `tweet_id`, `target_message`,
and `human_gold_label` — all four copied read-only from `GOLDEN_200_FINAL.csv`.
Showing `human_gold_label` was explicitly approved: this is an *additive* triage
layer on top of the existing, already-frozen intent gold, not a re-judgment of
intent, so seeing the intent label while making a triage decision is intended,
not a leak.

`triage_decision`, `escalation_reason` are intentionally blank in the generated
file and must be filled in by the human annotator only — no automated process
writes to them, as a draft, suggestion, or inferred default, in
`golden_set/build_triage_sample.py` or anywhere else. `notes` is blank and
optional, for the annotator's own free-text use.

## Limitations (state explicitly in any future report using this data)

Any eventual report built on this annotation layer must describe it as an
**n≈40 sample** with the limitations that implies: small absolute per-class
counts (as low as 3 for `ARTIST_SUPPORT` and `CONTENT_CATALOG`), drawn from a
200-example golden set that is itself a fixed sample of the TEST pool, not the
full customer-support traffic distribution. Findings from this subset are
exploratory and directional, not a statistically certified triage evaluation.
