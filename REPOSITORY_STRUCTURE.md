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

*Known gap*: the scripts that produced `CANDIDATE_MANIFEST_200.csv`, the workbooks, and `ai_prelabels.csv` were run interactively and are not yet checked into this repo — see `PROJECT_CONTEXT.md` §9.

---

## 📂 `evaluation/`

Contains the completed intent-classification baseline implementation:

- **`data_loading.py`**: Loads the 296 parseable DEVELOPMENT-pool discovery examples (4 excluded as unparseable — Ex 70, 78, 164, 265) as training data, and the 200 golden TEST examples as evaluation-only data.
- **`leakage_checks.py`**: Hard assertions that training, evaluation, and the RETRIEVAL pool share zero tweet_id/thread_id overlap.
- **`baselines.py`**: The majority-class and TF-IDF + Logistic Regression baseline models.
- **`metrics.py`**: Accuracy, macro/per-class precision/recall/F1, and confusion matrix computation.
- **`run_baselines.py`**: End-to-end entry point — trains both baselines on the 296 discovery examples and evaluates them on the 200 golden TEST examples.
- **`test_baseline_milestone.py`**: Tests for the data-loading/exclusion logic, leakage checks, and baseline sanity.
- **`BASELINE_RESULTS.md`**: The results report.
- **`results/baseline_results.json`**: Machine-readable metrics for both baselines.

**Status**: Majority-class and TF-IDF + Logistic Regression baselines are **complete**. LLM judge and later evaluation components (Exp 2-5, judge calibration, triage evaluation) remain pending.
