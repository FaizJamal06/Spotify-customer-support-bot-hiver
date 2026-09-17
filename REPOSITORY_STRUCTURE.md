# Repository Structure Guide

This document provides a comprehensive overview of the current repository structure, detailing what each directory and file does. This is intended to help new agents and engineers navigate the Hiver SDE Take-Home project.

## 📂 Root Directory

The root directory contains project-level documentation, core configuration, and initial exploration scripts.

### Documentation & Strategy
- **`PROJECT_CONTEXT.md`**: The primary onboarding document. Contains the current project state, completed phases, hard requirements, and dataset facts. Start here.
- **`DECISION_LOG.md`**: A chronological record of all major non-obvious decisions made during the project (e.g., why SpotifyCares was chosen, why the taxonomy is frozen, why we use thread-level splits).
- **`CHECKLIST.md`**: Tracks progress against the assignment requirements (Completed, Current, Not Yet Completed).
- **`hiver_sde_takehome_strategy.md`**: The strategic "North Star" document. Details the agent architecture, evaluation methodology, baseline definitions, and overall project philosophy.
- **`implementation_plan.md`**: A detailed, step-by-step pipeline execution plan (Phase 1 through Phase 16).
- **`candidate_taxonomy.md`**: An early historical draft of the intent taxonomy (now superseded by `discovery/TAXONOMY_REVIEW_GUIDE.md`).
- **`assignment.text`**: The original instructions/prompt for the Hiver SDE take-home assignment.

### Code & Data
- **`config.py`**: Centralized configuration file containing global constants, file paths, and environment variable requirements.
- **`analyze_brands.py`**: Early exploratory script used to evaluate different brands in the TWCS dataset, leading to the selection of SpotifyCares.
- **`analyze_spotify.py`**: Early exploratory script used to generate volume and interaction insights specifically for SpotifyCares.
- **`twcs.csv`**: The raw Kaggle Customer Support on Twitter dataset (~500MB). *(Note: Not committed to version control due to size).*

---

## 📂 `data/`

Contains scripts for parsing the raw dataset and enforcing strict data isolation.

- **`prepare.py`**: Filters `twcs.csv` for SpotifyCares interactions and deterministically reconstructs isolated conversation threads.
- **`split.py`**: Performs the strict 3-way split (DEVELOPMENT, RETRIEVAL, TEST) ensuring thread-level isolation so that context does not leak between development and evaluation.
- **`generated/`**: Output directory for the resulting JSONL thread split files.

---

## 📂 `discovery/`

Contains artifacts and scripts from the taxonomy discovery and annotation protocol (Pilot) phases.

### Core Annotation Rulebook
- **`TAXONOMY_REVIEW_GUIDE.md`**: **(Authoritative)** The frozen 8-label intent annotation rulebook. Contains definitions, boundary rules, and edge-case tiebreakers. This is the source of truth for all human golden-set labels. Now includes 7 wording/example clarifications added after golden annotation (each tagged `(post-golden clarification)` inline) — see `golden_set/GUIDE_CHANGELOG_AFTER_GOLD.md`.
- **`chronology.py`**: Shared `created_at`-based chronology utility (`parse_time`, `get_target_context`). Fixes the tweet-ID-ordering bug (`DECISION_LOG.md` #8); reused by the pilot workbook and the golden-set `THREAD_VIEW` sheet so chronology logic is never re-derived per script.
- **`test_chronology.py`**: Regression tests for `chronology.py`.

### Discovery Artifacts (Historical)
- **`HUMAN_REVIEW.md`**: A 300-example sample drawn from the DEVELOPMENT pool used to discover the taxonomy.
- **`HUMAN_REVIEW_labeled.md`**: The human-reviewed version of the 300 examples. Used historically to refine boundaries and finalize the 8-label taxonomy.
- **`discovery_sample.md`**: The raw thread dump of the 300 discovery examples.
- **`DEVELOPMENT_DIVERSITY_AUDIT.md`**: An analysis of the DEVELOPMENT pool to ensure it contains a diverse mix of intents, message lengths, and conversation complexities.
- **`candidates.txt`**: Early extraction of raw customer actions used to build the initial taxonomy.

### Pilot Artifacts (Historical)
- **`PILOT_ANNOTATION_100*.xlsx`**: Various iterations of the 100-example pilot workbook. This was an annotation-protocol dress rehearsal to test the taxonomy rules and context presentation (not the final golden set).

### Scripts
- **`create_pilot.py`**: Generates the pilot workbook. Critically, it implements chronological sorting using `created_at` timestamps to ensure no future messages leak into the target context.
- **`audit_development.py`**: Script used to generate the `DEVELOPMENT_DIVERSITY_AUDIT.md` report.
- **`generate_human_review.py`**: Generated the 300-example `HUMAN_REVIEW.md`.
- **`update_human_review.py`**: Helper script for updating review files.
- **`sample_discovery.py` & `generate_candidates.py`**: Utilities for initial taxonomy exploration.

---

## 📂 `golden_set/`

The final, isolated 200-example Golden Evaluation Set, sampled entirely from the TEST pool. **Complete and immutable** — see `DECISION_LOG.md` #17.

- **`GOLDEN_200_FINAL.csv`**: The clean gold export. Columns: `candidate_id, tweet_id, thread_id, customer_id, target_message, human_gold_label, human_notes`. **This is the file downstream evaluation code should load.**
- **`GOLDEN_ANNOTATION_200_labeled.xlsx`**: The completed annotation workbook. Gold lives in the `Human Final Label` column of the `GOLDEN_200` sheet (see `DECISION_LOG.md` #21 for why). Also contains `THREAD_VIEW` (chronological context per candidate), `GUIDE` (annotation rulebook transcription), `SAMPLING_INFO`, and `AI_PRELABEL_SUMMARY` sheets.
- **`GOLDEN_ANNOTATION_200.xlsx`**: The pre-annotation blind workbook (same structure, before the human labeled it or AI prelabels were reviewed). Kept for provenance.
- **`CANDIDATE_MANIFEST_200.csv`**: The sampling manifest — provisional/heuristic labels, boundary tags, selection rationale, QA notes. **NOT gold** (it was never shown to the human annotator); useful for understanding how/why each candidate was selected.
- **`ai_prelabels.csv`**: The AI Suggested Label / Reasoning / Confidence generated to accelerate human review. Advisory only.
- **`GOLDEN_200_ANALYSIS.md`**: Post-annotation validation results, final gold distribution, AI-prelabel-vs-gold agreement analysis (91.5% exact agreement), disagreement pattern breakdown.
- **`PROPOSED_GUIDE_CLARIFICATIONS.md`**: 9 candidate guide clarifications derived from the 17 AI/human disagreements, each with evidence, proposed wording, and a `PROPOSED ONLY` marker.
- **`GUIDE_CHANGELOG_AFTER_GOLD.md`**: Which of those 9 were approved and applied to `discovery/TAXONOMY_REVIEW_GUIDE.md` (7), and which were deliberately left unresolved (3), with reasoning for each.
- **`REPORT_DECISION_LOG.md`**: Backing detail behind `report/REPORT.md` §6 (Decision Log) — the curated, condensed source list of 14 non-obvious decisions the report's version draws on.

*Known gap*: the scripts that produced `CANDIDATE_MANIFEST_200.csv`, the workbooks, and `ai_prelabels.csv` were run interactively and are not yet checked into this repo — see `PROJECT_CONTEXT.md` §9.

---

## 📂 `evaluation/`

Contains the full evaluation pipeline: intent-classification baselines and the LLM few-shot classifier, confidence calibration, the retrieval index and response generator, the LLM judge and k-ablation sweep, manual retrieval inspection, the three-tier triage policy, and the two held-out evaluations against human annotation (Part J triage, Part I judge calibration).

### Intent-classification baselines

- **`data_loading.py`**: Loads the 296 parseable DEVELOPMENT-pool discovery examples (4 excluded as unparseable — Ex 70, 78, 164, 265) as training data, and the 200 golden TEST examples as evaluation-only data.
- **`leakage_checks.py`**: Hard assertions that training, evaluation, and the RETRIEVAL pool share zero tweet_id/thread_id overlap.
- **`baselines.py`**: The majority-class and TF-IDF + Logistic Regression baseline models.
- **`metrics.py`**: Accuracy, macro/per-class precision/recall/F1, and confusion matrix computation.
- **`run_baselines.py`**: End-to-end entry point — trains both baselines on the 296 discovery examples and evaluates them on the 200 golden TEST examples.
- **`test_baseline_milestone.py`**: Tests for the data-loading/exclusion logic, leakage checks, and baseline sanity.
- **`BASELINE_RESULTS.md`**: The results report.
- **`results/baseline_results.json`**: Machine-readable metrics for both baselines.

### LLM few-shot classifier

- **`fewshot_selection.py`**: Deterministic few-shot demonstration selection — a MATCH-status-only subset of the 296-example discovery substitution, up to 5 (min 3) per intent, sorted by example_id, no randomness.
- **`llm_classifier.py`**: The LLM intent classifier (Experiment 1's third classifier) — implements `LLMProvider.classify()` with a strict JSON-schema response format constraining output to the 8 frozen labels; `.generate_reply()`/`.judge()` are left as `NotImplementedError` stubs here (implemented later in `generation.py`).
- **`run_llm_classifier.py`**: Entry point — runs gpt-5.4-mini few-shot classification on the 200 golden examples; writes `results/llm_classifier_results.json` and `LLM_CLASSIFIER_RESULTS.md`.
- **`test_llm_classifier_milestone.py`**: Tests for deterministic few-shot selection, MATCH-status filtering, the >=3-per-intent hard assertion, the leakage assertion, and output-schema validation.
- **`LLM_CLASSIFIER_RESULTS.md`**: The results report, including the three-way comparison against both baselines.
- **`results/llm_classifier_results.json`**: Machine-readable predictions/metrics for the LLM classifier.

### Confidence calibration

- **`calibration.py`**: Exploratory (not certified) calibration analysis of the LLM classifier's confidence — quantile bucketing, Wilson intervals, ECE, Brier score. Reads only `results/llm_classifier_results.json`; zero API calls.
- **`test_calibration.py`**: Tests for quantile bucket-boundary correctness, Wilson-interval correctness, and ECE correctness on synthetic data.
- **`run_calibration.py`**: Entry point — writes `results/calibration_results.json` and `CALIBRATION_RESULTS.md`.
- **`CALIBRATION_RESULTS.md`**: The calibration report — the classifier is overconfident in every one of 5 quantile buckets (ECE=0.14, Brier=0.166); concludes the data does not support a defensible hard confidence threshold.
- **`results/calibration_results.json`**: Machine-readable calibration statistics.

### Embeddings & retrieval

- **`embeddings.py`**: Minimal OpenAI embedding utility (`text-embedding-3-small`), reusing the same `DiskCache` pattern as `llm_classifier.py`. Not the retrieval index itself.
- **`test_embeddings.py`**: Tests against the real OpenAI embeddings API (network-call counting, not response mocking); requires `OPENAI_API_KEY`.
- **`retrieval.py`**: Brute-force cosine-similarity top-k retrieval over the serialized index; `k=0` returns `[]` with no embedding call.
- **`build_retrieval_index.py`**: One-time entry point — deduplicates the RETRIEVAL pool, samples 3,000 pairs, embeds `customer_text` only, serializes the index to `cache/retrieval_index/` (gitignored), and hard-asserts zero leakage against the golden 200. Requires a funded OpenAI API key; not part of the fast/free reproduction path.
- **`test_retrieval.py`**: Tests for `retrieve_top_k()` and the dedup/leakage logic in `build_retrieval_index.py`, mostly against the real serialized index (skipped if absent).

### Response generation & LLM judge

- **`generation.py`**: Response generator + minimal LLM judge (Experiment 3) — subclasses the frozen `LLMProvider` to implement `.generate_reply()`/`.judge()`; includes the evidence-cleaning step (`clean_brand_text`) that strips stale agent sign-offs and uncued tracking URLs from retrieved historical replies before they reach the generator/judge.
- **`test_generation.py`**: Tests for generator/judge output-schema validation, `k=0` short-circuiting, and the gold-data-isolation rule.
- **`run_generation_judge_pilot.py`**: Entry point — runs the generate→judge pipeline on an 8-example, 4-k-condition pilot to sanity-check before the full sweep.
- **`GENERATION_JUDGE_PILOT_RESULTS.md`**: The 8-example pilot's full output — the run that caught the generator copying/fabricating stale sign-off codes, which motivated the evidence-cleaning fix in `generation.py`.
- **`results/generation_judge_pilot.json`**: Machine-readable pilot output.

### Retrieval k-ablation sweep (Experiment 3)

- **`run_k_ablation_sweep.py`**: Entry point — the full 200×4 generate+judge sweep across k in {0,1,3,5}, with integrity checks and bounded concurrency; writes `results/k_ablation_sweep.json`.
- **`test_k_ablation_sweep.py`**: Tests for the gold-isolation example builder and the integrity-check logic, against both synthetic and real committed data.
- **`k_ablation_stats.py`**: The 12 pre-specified paired Wilcoxon comparisons (k=1/3/5 vs. k=0, x4 judge dimensions), with Holm-Bonferroni correction.
- **`test_k_ablation_stats.py`**: Tests for the paired Wilcoxon logic and the Holm-Bonferroni adjustment, on synthetic data.
- **`run_k_ablation_stats.py`**: Entry point — reads `results/k_ablation_sweep.json` and writes the 12-comparison table, descriptive stats, and `K_ABLATION_SWEEP_RESULTS.md`.
- **`K_ABLATION_SWEEP_RESULTS.md`**: The full sweep results report — retrieval significantly raises Groundedness and significantly lowers Relevance/Tone at every k (all 12 comparisons Holm-corrected significant).
- **`results/k_ablation_sweep.json`**: The 800 generate+judge audit records plus integrity summary (committed, force-added).
- **`results/k_ablation_stats_results.json`**: Machine-readable statistical comparison output.

### Manual retrieval inspection (20 examples)

- **`build_retrieval_inspection_scaffold.py`**: Builds the 20-example manual retrieval-inspection scaffold CSV (blank qualitative-judgment columns) for Faiz to fill in by hand; deterministic sampling, seed=20.
- **`test_retrieval_inspection_scaffold.py`**: Tests for deterministic sampling and the "judgment columns must remain genuinely blank" rule.
- **`build_retrieval_inspection_workbook.py`**: Builds the polished Excel annotation workbook (`results/RETRIEVAL_INSPECTION_20.xlsx`) from the scaffold CSV; presentation layer only, no new judgments.
- **`test_retrieval_inspection_workbook.py`**: Tests for the workbook builder and its output, against the generated workbook and/or an isolated temp copy.
- **`export_retrieval_inspection.py`**: Exports Faiz's completed annotations from the workbook into the canonical `results/retrieval_inspection_annotations.csv`, honestly shaped as one row per example (20), not per retrieved pair.
- **`test_export_retrieval_inspection.py`**: Tests using synthetic fixture workbooks; the one test against the real xlsx is skipped automatically if absent.
- **`results/retrieval_inspection_scaffold.csv`**: The raw 20-example x top-5 scaffold (committed, force-added).
- **`results/RETRIEVAL_INSPECTION_20.xlsx`**: The completed human annotation workbook.
- **`results/retrieval_inspection_annotations.csv`**: Canonical exported annotations (committed).

### Triage policy

- **`triage.py`**: The three-tier triage policy — Tier 1 deterministic safety rules (UNKNOWN intent / security language / legal language), Tier 2A confidence threshold explicitly tested and rejected, Tier 2B ACCOUNT_ACCESS DM-redirect rule shipped disabled by default (`TIER2_ACCOUNT_ACCESS_RULE_ENABLED = False`), Tier 3 explicitly-unvalidated anger-keyword heuristic.
- **`test_triage.py`**: Tests for `triage.py`; never references the real `TRIAGE_ANNOTATION_40.csv` labels.
- **`audit_triage_tier2.py`**: The Fisher's-exact robustness audit of the Tier-2B ACCOUNT_ACCESS rule against its closest competitor and two alternative heuristic-wording variants; reads only the cached sweep, zero new API calls.
- **`test_triage_tier2_audit.py`**: Tests for the audit; no real API calls or holdout labels referenced.
- **`results/triage_tier2_dm_redirect_analysis.json`**: Per-intent DM-redirect rate breakdown (gitignored, regenerated on demand).
- **`results/triage_tier2_audit.json`**: The Fisher's-exact / robustness-variant audit output (gitignored, regenerated on demand).

### Part J: triage vs. human holdout

- **`run_part_j_triage_eval.py`**: Part J — the held-out evaluation of `triage.py`'s `apply_triage_rules()` exactly as-is against `golden_set/TRIAGE_ANNOTATION_40.csv`'s human `triage_decision` column; 4 conditions (2 arms x 2 intent sources), zero new API/embedding calls.
- **`test_run_part_j_triage_eval.py`**: Tests for the four-condition computation logic, using synthetic examples, never the real 40-example holdout.
- **`results/part_j_triage_eval.json`**: Part J's full results (gitignored, regenerated on demand).

### Part I: judge-vs-human calibration

- **`build_judge_human_calibration_workbook.py`**: Part I Stage 1 — builds the human response-quality calibration workbook (`results/JUDGE_HUMAN_CALIBRATION_40.xlsx`) for the 40-example shared subset at k=3; presentation/scaffold layer only, zero API calls, never exposes judge scores/reasoning to the human grader.
- **`test_judge_human_calibration_workbook.py`**: Tests for the workbook builder and its output.
- **`analyze_judge_human_agreement.py`**: Part I Stage 2 — computes judge-human agreement (weighted Cohen's kappa, confusion matrices, bootstrap CIs) from the completed workbook against the k=3 LLM judge scores; valid for k=3 only.
- **`test_analyze_judge_human_agreement.py`**: Tests for the agreement computation, cross-checked against sklearn's `cohen_kappa_score` directly.
- **`results/JUDGE_HUMAN_CALIBRATION_40.xlsx`**: The completed human-graded calibration workbook (committed).
- **`results/judge_human_agreement.json`**: Part I's agreement statistics (gitignored, regenerated on demand) — weak agreement on every dimension; Groundedness's kappa is negative.

### Report drafts

- **`FAILURE_ANALYSIS_DRAFT.md`**: Backing detail behind `report/REPORT.md` §3 (Top-5 Failure Analysis) — the full examples, citations, and reasoning the report's condensed version draws on.

**Status**: Complete — intent classification (3 classifiers), retrieval, response generation, the LLM judge, the k=0/1/3/5 retrieval-ablation sweep, the three-tier triage policy, both held-out evaluations (Part J triage, Part I judge calibration), and the final written report (`report/REPORT.md`). See `CHECKLIST.md` for the full status table.
