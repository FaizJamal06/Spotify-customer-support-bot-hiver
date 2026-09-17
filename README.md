# Hiver SDE Take-Home — SpotifyCares Support Agent

An AI customer-support agent built on the [Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter)
(TWCS) dataset, for the **SpotifyCares** brand. Classifies incoming customer
messages into an 8-intent taxonomy, will draft grounded replies from
historical resolutions, and will decide auto-handle vs. escalate.

**Status: complete** — intent classification (3 classifiers), retrieval,
response generation, an LLM judge, a k=0/1/3/5 retrieval-ablation experiment
(800 conditions), a three-tier triage policy, a held-out triage evaluation
(Part J), a judge-vs-human calibration study (Part I), and the final written
report. **Start with [report/REPORT.md](report/REPORT.md)** — problem
framing, results vs. baselines, top-5 failure analysis, "misleading headline
number," next steps, and the decision log. See [CHECKLIST.md](CHECKLIST.md)
for the full status table.

Two headline findings worth knowing before reading further: (1) retrieval
measurably improves Groundedness but measurably *hurts* Relevance and Tone
(paired Wilcoxon, all 12 comparisons significant — [`evaluation/K_ABLATION_SWEEP_RESULTS.md`](evaluation/K_ABLATION_SWEEP_RESULTS.md)),
and (2) the LLM judge's agreement with human ratings on the same 40 replies
is weak on every dimension (weighted Cohen's κ 0.09–0.23; 3 of 4 dimensions'
95% CIs span zero, and the fourth, Groundedness, sits entirely at-or-below
zero — [`evaluation/results/judge_human_agreement.json`](evaluation/results/judge_human_agreement.json)),
so finding (1) should be read with that caveat, not as a certified result.

## Start here

| Doc | What it's for |
|---|---|
| [report/REPORT.md](report/REPORT.md) | **The final report — start here.** Problem framing, results vs. baselines, top-5 failure analysis, "misleading headline number," next steps, decision log |
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | Current project state, hard requirements, dataset facts |
| [DECISION_LOG.md](DECISION_LOG.md) | Why the non-obvious decisions were made, with explicit human-vs-AI-assistance attribution |
| [discovery/TAXONOMY_REVIEW_GUIDE.md](discovery/TAXONOMY_REVIEW_GUIDE.md) | The frozen, authoritative annotation rulebook |
| [CHECKLIST.md](CHECKLIST.md) | What's done vs. not started, against the assignment requirements |
| [REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md) | What every file/directory is for |
| [hiver_sde_takehome_strategy.md](hiver_sde_takehome_strategy.md) | Strategic north-star doc (architecture, evaluation philosophy) |
| [evaluation/FAILURE_ANALYSIS_DRAFT.md](evaluation/FAILURE_ANALYSIS_DRAFT.md) | Backing detail for the report's failure analysis — full examples and citations behind `report/REPORT.md` §3 |
| [golden_set/REPORT_DECISION_LOG.md](golden_set/REPORT_DECISION_LOG.md) | Backing detail for the report's decision log — the curated source list behind `report/REPORT.md` §6 |

## What's done

- SpotifyCares selected from TWCS; thread-level DEVELOPMENT/RETRIEVAL/TEST split built and leakage-checked (`data/prepare.py`, `data/split.py`).
- 8-intent taxonomy derived empirically from a 300-example discovery review, frozen, and documented in `discovery/TAXONOMY_REVIEW_GUIDE.md`.
- **200-example golden evaluation set complete**: sampled from the sealed TEST pool only, individually QA'd, blindly annotated, AI-prelabeled to speed review, and fully human-labeled. Gold export: [`golden_set/GOLDEN_200_FINAL.csv`](golden_set/GOLDEN_200_FINAL.csv). **These labels are final and immutable** (`DECISION_LOG.md` #17) — not used for training, not inserted into retrieval.
- Post-golden review: an AI-prelabel-vs-human-gold agreement analysis (91.5% exact agreement) was run as a validity check, and the taxonomy was re-confirmed to need exactly 8 intents (no new intent). 7 small guide wording clarifications were approved and applied; 3 were deliberately left open rather than force-resolved on weak evidence. Full detail in `golden_set/GOLDEN_200_ANALYSIS.md` and `golden_set/GUIDE_CHANGELOG_AFTER_GOLD.md`.
- **Intent-classification baselines complete**: majority-class and TF-IDF + Logistic Regression, trained on 296 of the 300 DEVELOPMENT-pool discovery examples (4 excluded as unparseable — Ex 70, 78, 164, 265; see `DECISION_LOG.md` #24), evaluated on the 200 golden TEST examples. Full metrics: [`evaluation/BASELINE_RESULTS.md`](evaluation/BASELINE_RESULTS.md) and `evaluation/results/baseline_results.json`.
- **LLM few-shot intent classifier complete**: gpt-5.4-mini, few-shot demonstrations drawn from a MATCH-status-only subset of the same 296-example discovery substitution (39 examples, deterministic selection, never touches golden-200), evaluated on the 200 golden TEST examples. Full metrics and the three-way comparison against both baselines: [`evaluation/LLM_CLASSIFIER_RESULTS.md`](evaluation/LLM_CLASSIFIER_RESULTS.md) and `evaluation/results/llm_classifier_results.json`.
- **Exploratory confidence calibration complete**: the classifier is overconfident in every one of 5 quantile buckets (ECE=0.14, Brier=0.166); concluded a hard confidence threshold is not defensible for triage from this evidence. [`evaluation/CALIBRATION_RESULTS.md`](evaluation/CALIBRATION_RESULTS.md).
- **Retrieval index built**: brute-force cosine-similarity index over a 3,000-pair sample of the RETRIEVAL pool (26,914 deduplicated pairs), `text-embedding-3-small`, leakage-checked against golden-200. `evaluation/build_retrieval_index.py`, `evaluation/retrieval.py`; index manifest at `cache/retrieval_index/manifest.json` (gitignored — see reproduction section below).
- **Response generator + minimal LLM judge complete**: `GENERATE_MODEL=gpt-5.6-terra`, `JUDGE_MODEL=gpt-5.6-sol` (deliberately different models to reduce self-preference bias), rubric scoring Relevance/Groundedness/Helpfulness/Tone (1–5). An evidence-cleaning step strips stale agent sign-offs and uncued tracking URLs from retrieved historical replies before they reach the generator/judge. `evaluation/generation.py`; 8-example pilot in [`evaluation/GENERATION_JUDGE_PILOT_RESULTS.md`](evaluation/GENERATION_JUDGE_PILOT_RESULTS.md).
- **Full k=0/1/3/5 retrieval-ablation sweep complete**: all 200 golden examples × 4 conditions = 800 generate+judge pairs, 0 failures, all integrity checks passed. 12 pre-specified paired Wilcoxon comparisons (Holm-Bonferroni corrected): retrieval significantly *raises* Groundedness at every k, and significantly *lowers* Relevance and Tone at every k — a genuine tradeoff, not a clean win. [`evaluation/K_ABLATION_SWEEP_RESULTS.md`](evaluation/K_ABLATION_SWEEP_RESULTS.md); full audit trail at `evaluation/results/k_ablation_sweep.json` (committed).
- **20-example manual retrieval-inspection complete**: human-graded (Retrieval Usefulness / Best Rank / Relevance Problem / Grounding Value) via `evaluation/build_retrieval_inspection_workbook.py`, filled in, exported to the canonical `evaluation/results/retrieval_inspection_annotations.csv`.
- **Three-tier triage policy implemented and evaluated against a held-out human triage set** (Part J): Tier 1 deterministic safety rules (UNKNOWN intent / security language / legal language → escalate), a confidence-threshold hypothesis explicitly tested and rejected (per the calibration finding above), one evidence-driven intent-specific rule (ACCOUNT_ACCESS) that a follow-up Fisher's-exact audit found "plausible but fragile" (p=0.094 vs. its closest competitor) and is therefore **shipped disabled by default** (`TIER2_ACCOUNT_ACCESS_RULE_ENABLED = False`), and an explicitly-unvalidated Tier-3 anger-keyword heuristic. `evaluation/triage.py`, `evaluation/audit_triage_tier2.py`. Evaluated against `golden_set/TRIAGE_ANNOTATION_40.csv` (the shipped-default policy agrees with the human triage decision on 32/40 = 80.0% of examples; 3/40 dangerous false-auto-handles, 5/40 false-escalates). `evaluation/run_part_j_triage_eval.py`, `evaluation/results/part_j_triage_eval.json` (gitignored).
- **Judge-vs-human calibration complete** (Part I): 40 shared examples (same subset as the triage holdout, k=3 condition), independently human-graded on the same rubric with no judge scores/reasoning shown. Agreement is weak on every dimension — weighted Cohen's κ ranges 0.09 (Relevance) to 0.23 (Tone/Helpfulness), and 3 of 4 dimensions' 95% bootstrap CIs include zero (Groundedness's CI tops out *at* zero). `evaluation/build_judge_human_calibration_workbook.py`, `evaluation/analyze_judge_human_agreement.py`; workbook at `evaluation/results/JUDGE_HUMAN_CALIBRATION_40.xlsx` (committed), stats at `evaluation/results/judge_human_agreement.json` (gitignored).
- **328 tests** across `evaluation/`, `discovery/`, and `golden_set/`. From a bare fresh clone: 301 passed, 16 failed (all explained — data-prep prerequisite or API credit, none a logic bug), 11 skipped (correctly gated on the embedding cache). Full breakdown and exact fresh-clone verification: see "What you can reproduce today" below.

## What's NOT done yet (by design, not oversight)

- Golden-set generation scripts reproducibility gap (see `PROJECT_CONTEXT.md` §9) — unchanged, not addressed by any later milestone.
- No production action/tool layer, no trained/learned triage model, no sentiment model — deliberately out of scope throughout (see `implementation_plan.md` §15 and each milestone's own "what not to build" notes).

## What you can reproduce today

Every claim in this section was re-verified by cloning this exact repository
into a clean, isolated directory (no cache, no untracked files, no
environment state carried over) and actually running each command there.

**Environment note:** `cache/` (embeddings + the retrieval index),
`data/generated/` (the split pools), and `twcs.csv` itself are gitignored on
purpose (large, mechanically-regenerable, or third-party-licensed data) and
are genuinely absent from a fresh clone. `evaluation/results/` is gitignored
as a whole directory, but the specific files needed for analysis-only
reproduction are individually force-committed — see the list below.

**No raw dataset is required to reproduce the headline results.** The fast/free
path below needs nothing from `twcs.csv` (~500MB, not committed) — every input
it reads is already committed to this repo. `twcs.csv` is only relevant to the
separate, optional "Requires `twcs.csv`" section further down.

**This project's own design already follows the assignment's "subsample is
expected and encouraged" rule** (`assignment.text`: *"we will not run your code
on the full dataset — a subsample is expected and encouraged"*), independent of
raw-data subsampling: the golden evaluation set is 200 examples (not the full
~8,700-pair TEST pool), the retrieval index is a 3,000-pair sample (not the
full 26,914-pair deduplicated RETRIEVAL pool), and the LLM classifier's
few-shot set is 39 examples. Separately, if a grader wants to exercise the
optional data-preparation path below with less than the full ~500MB file,
`data/prepare.py` and `data/split.py` were confirmed (by filtering the real
`twcs.csv` down to a 2.6%-sized, SpotifyCares-only subsample and running both
scripts against it) to run correctly against a subsampled `twcs.csv` — they
produce proportionally smaller pools, not an error.

### Fast / free — works from a bare fresh clone, no API calls, roughly 4–8 minutes total

```bash
pip install -r requirements.txt

python3 -m pytest evaluation/ discovery/ golden_set/ -q
python3 evaluation/run_calibration.py
python3 evaluation/run_k_ablation_stats.py
python3 evaluation/triage.py
python3 evaluation/audit_triage_tier2.py
python3 evaluation/run_part_j_triage_eval.py
python3 evaluation/analyze_judge_human_agreement.py
```

Verified from a genuine fresh clone (not this working tree): the test suite
collects **328 tests → 301 passed, 16 failed, 11 skipped**, taking roughly
2–3 minutes on its own (measured 123s and 161s across two fresh-clone runs on
the same machine — pytest startup and the bootstrap-heavy calibration tests
dominate; expect it to vary by hardware). The 16 failures are **not** random —
every one is explained below, none are a logic bug:
- **13** (`test_baseline_milestone.py` x7, `test_llm_classifier_milestone.py` x6)
  need `data/generated/dev_pairs.jsonl`, which requires the data-prep step
  below (`twcs.csv` + `data/prepare.py` + `data/split.py`) — not part of the
  free path.
- **2** (`test_embeddings.py`) need a funded `OPENAI_API_KEY` and are
  documented as such — they skip cleanly if the key is simply absent, but
  fail (not skip) if a key is present without credit.
- **1** (`test_retrieval_inspection_workbook.py::test_freeze_panes_header_row_only_no_frozen_columns`)
  is a benign Excel re-save artifact on the committed, human-edited
  `RETRIEVAL_INSPECTION_20.xlsx` (Excel rewrites an internal view-state
  attribute on save; the actual freeze-pane *behavior* the test cares about
  is unaffected) — cosmetic, not a defect.

(This repo ships a `.gitattributes` forcing LF line endings on checkout,
regardless of the grader's local git config. Without it, a Windows client with
`core.autocrlf=true` would silently convert `evaluation/results/retrieval_inspection_scaffold.csv`'s
committed LF endings to CRLF on clone, which previously broke 2 additional
tests that compare that CSV's checked-out text against the same content
embedded — still LF — inside the binary `RETRIEVAL_INSPECTION_20.xlsx`. Verified
fixed by cloning fresh with `core.autocrlf=true` explicitly set.)

The 11 skips are all correctly gated on `cache/retrieval_index/` (the
embedding index) being absent, which is expected in a bare clone.

The 6 analysis scripts above (`run_calibration.py` through
`analyze_judge_human_agreement.py`) each independently verified to **PASS and
reproduce their documented headline numbers exactly** — e.g.
`run_calibration.py` reproduces ECE=0.1402/Brier=0.1659, and
`run_part_j_triage_eval.py` reproduces 32/40 (80.0%) agreement — reading only
the following committed files, no others:
`evaluation/results/llm_classifier_results.json`,
`evaluation/results/k_ablation_sweep.json`,
`evaluation/results/JUDGE_HUMAN_CALIBRATION_40.xlsx`,
`golden_set/TRIAGE_ANNOTATION_40.csv`.
The five short scripts (`run_calibration.py` through
`run_part_j_triage_eval.py`) each finish in 1–2s. `analyze_judge_human_agreement.py`
is the outlier — its two bootstrap 95% CIs (kappa and Spearman, 10,000
resamples each, across 4 dimensions) dominate its cost, measured between 74s
and 220s across separate runs on the same machine, depending on system load.
Combined, the whole fast/free sequence (`pip install` + pytest + all 6
scripts) measured **roughly 4–8 minutes end to end** across repeated runs in
this repo's own testing — comfortably under the assignment's 15-minute
requirement even at the high end, but noticeably more than "a minute," which
is why this section now gives a range instead of a single figure.

The golden set itself never needs regenerating — it's already committed at
`golden_set/GOLDEN_200_FINAL.csv`.

### Requires `twcs.csv` + the data-preparation step (still zero API calls)

```bash
# 1. Download the raw Kaggle TWCS CSV and place it at the repo root as twcs.csv (~500MB, not committed).
python3 data/prepare.py
python3 data/split.py
python3 evaluation/run_baselines.py
```

This also unblocks the 13 currently-failing baseline/classifier tests noted
above. No API calls are made by any of these three scripts.

### Requires a funded OpenAI API key

These were already run once; their outputs are what's committed/cached above.
Re-running them makes new API calls and is **not** part of the fast/free path.

```bash
export OPENAI_API_KEY=...        # must have credit

python3 evaluation/build_retrieval_index.py     # embeds a 3,000-pair sample of the RETRIEVAL pool
python3 evaluation/run_llm_classifier.py        # classifies the 200 golden examples (gpt-5.4-mini)
python3 evaluation/run_generation_judge_pilot.py  # 8-example generate+judge pilot
python3 evaluation/run_k_ablation_sweep.py      # the full 200x4=800-condition sweep
```

The full sweep (`run_k_ablation_sweep.py`) is the most expensive step: ~$6.21
in API spend and ~12 minutes wall-clock (concurrent, `SWEEP_MAX_WORKERS=8`),
per [`evaluation/K_ABLATION_SWEEP_RESULTS.md`](evaluation/K_ABLATION_SWEEP_RESULTS.md).
The other three are each a small fraction of that.

**Known gap**: the interactive scripts that produced `golden_set/CANDIDATE_MANIFEST_200.csv`,
the annotation workbooks, and `golden_set/ai_prelabels.csv` are not yet
checked into this repo (only their outputs are). See `PROJECT_CONTEXT.md` §9.
This doesn't affect the validity of the golden set — it's already a committed,
fixed artifact — only the ability to regenerate it from scratch.

## Citations / AI assistance

Per the assignment's rules ("You may use AI coding assistants freely... cite
anything you borrowed"): this project was built with Claude Code as a coding
assistant across exploration, scripting, QA checks, and drafting. See
`DECISION_LOG.md` for a detailed accounting of which decisions were mine and
where AI assistance was used, including the AI-assisted prelabeling workflow
used to speed up (not replace) human annotation of the golden set.
