# Project Context

## Current State for New Agents (Claude Code Onboarding)
Before making changes, read:
1. `PROJECT_CONTEXT.md` (describes current project state)
2. `DECISION_LOG.md` (explains why important choices were made)
3. `discovery/TAXONOMY_REVIEW_GUIDE.md` (the authoritative annotation rulebook)
4. `CHECKLIST.md` (describes completion state)
5. `hiver_sde_takehome_strategy.md` (describes project philosophy/architecture/evaluation direction)
6. Relevant implementation files (code is the source of truth for current implementation behavior)

- **TAXONOMY_REVIEW_GUIDE.md** is authoritative for annotation. Primary support action is the classification principle. Model predictions must not determine gold labels.
- The 8-label taxonomy is **FROZEN** (confirmed post-golden; see `DECISION_LOG.md` #22).
- Discovery labels are historical evidence, not authoritative truth.
- Pilot work validates annotation protocol, not the final model; it was never human-annotated (deliberately).
- `UNKNOWN_OTHER` is a last resort.
- Context must use only preceding messages. `created_at` is the chronology authority. Post-target responses/resolution cannot be used for annotation.
- **The 200-example golden set is COMPLETE and its gold labels are IMMUTABLE.** `Human Final Label` in `golden_set/GOLDEN_ANNOTATION_200_labeled.xlsx` (cleanly exported to `golden_set/GOLDEN_200_FINAL.csv`) is the only authoritative gold source. Do not relabel it, do not resample it, do not use it for training/retrieval — it is evaluation-only.

## 1. Assignment Summary and Hard Requirements
**Goal**: Build an AI customer support agent for one brand from the TWCS dataset. Prove it works.
**Requirements**:
- Runnable repo, reproducible in < 15 minutes.
- 150-250 hand-labelled golden examples with sampling/labeling methodology.
- Automated evaluation metrics + LLM-as-a-judge rubric.
- Evidence of judge/human agreement.
- Report (max 6 pages) with problem framing, baselines (trivial + simple), top 5 failure modes, "misleading headline number", and next steps.
- Decision log (10-15 non-obvious decisions).
- Citations.

## 2. Current Project Phase and Status
- **CURRENT PHASE**: Complete. The full pipeline is built and evaluated end-to-end: golden set, all three intent classifiers, confidence calibration, retrieval index, response generator + LLM judge, the full k=0/1/3/5 retrieval-ablation sweep (800 conditions), a three-tier triage policy evaluated against a held-out 40-example human triage set (Part J), a judge-vs-human calibration study (Part I), and the final written report (`report/REPORT.md`).
- **COMPLETED (golden set / classification, as before)**: Dataset exploration, Spotify brand selection, thread reconstruction, split creation, leakage checks, taxonomy discovery, 300-example discovery review, annotation-guide refinement, taxonomy freeze, chronology bug discovery/fix, pilot preparation/protocol work (100-example workbook built, never human-annotated — deliberately deferred, see `DECISION_LOG.md` #24), golden-set candidate sampling (200 from TEST), full manual QA pass over all 200 candidates, blind annotation workbook, AI-assisted prelabeling pass, **human gold annotation of all 200 examples (complete)**, AI-vs-human agreement analysis, post-golden taxonomy review (taxonomy kept at exactly 8 intents), 7 approved guide wording clarifications applied to the frozen guide, discovery-300 compatibility audit against the frozen guide (`discovery/DISCOVERY_300_AUDIT_REPORT.md`), **intent-classification baselines** (majority-class + TF-IDF/Logistic Regression, trained on 296 of the 300 DEVELOPMENT discovery examples — 4 excluded as unparseable: Ex 70, 78, 164, 265 — evaluated on the 200 golden TEST examples; see `evaluation/BASELINE_RESULTS.md`), **LLM few-shot classifier** (gpt-5.4-mini; `evaluation/LLM_CLASSIFIER_RESULTS.md`), **exploratory confidence calibration** (classifier overconfident in every quantile bucket, ECE=0.14; `evaluation/CALIBRATION_RESULTS.md`).
- **COMPLETED (retrieval / generation / judge)**: **Retrieval index** built over a 3,000-pair sample of the 26,914-pair RETRIEVAL pool, `text-embedding-3-small`, leakage-checked (`evaluation/build_retrieval_index.py`, `evaluation/retrieval.py`). **Response generator + minimal LLM judge** (`GENERATE_MODEL=gpt-5.6-terra`, `JUDGE_MODEL=gpt-5.6-sol` — deliberately different models; `evaluation/generation.py`), including an evidence-cleaning step that strips stale agent sign-offs/uncued tracking URLs from retrieved historical replies before they reach the generator/judge. **Full k=0/1/3/5 sweep**: 200 examples x 4 conditions = 800 generate+judge pairs, 0 failures, all integrity checks passed; 12 pre-specified paired Wilcoxon comparisons (Holm-Bonferroni corrected) found retrieval significantly *raises* Groundedness and significantly *lowers* Relevance/Tone at every k (`evaluation/K_ABLATION_SWEEP_RESULTS.md`, `evaluation/results/k_ablation_sweep.json`). **20-example manual retrieval inspection** independently human-graded (`evaluation/results/retrieval_inspection_annotations.csv`).
- **COMPLETED (triage / Part J / Part I)**: **Three-tier triage policy** (`evaluation/triage.py`) — Tier 1 deterministic safety rules; Tier 2A confidence threshold explicitly tested and rejected (per the calibration finding above); Tier 2B ACCOUNT_ACCESS intent-specific rule, evidence-driven but found "plausible but fragile" by a follow-up Fisher's-exact audit (`evaluation/audit_triage_tier2.py`, p=0.094 vs. its closest competitor) and therefore **shipped disabled by default**; Tier 3 explicitly-unvalidated anger-keyword heuristic. **Part J** (`evaluation/run_part_j_triage_eval.py`) evaluated the shipped-default policy against `golden_set/TRIAGE_ANNOTATION_40.csv`: 32/40 (80.0%) agreement, 3/40 dangerous false-auto-handles, 5/40 false-escalates, under the realistic (LLM-predicted-intent) condition. **Part I** (`evaluation/build_judge_human_calibration_workbook.py`, `evaluation/analyze_judge_human_agreement.py`) found weak judge-vs-human agreement on all 4 rubric dimensions at k=3 (weighted Cohen's kappa 0.09-0.23, most 95% CIs include zero) — this is the single most important caveat on the k-ablation "retrieval helps Groundedness" finding above, since it means the judge's own scores are not yet validated as trustworthy.
- **IMMEDIATE NEXT STEP**: None outstanding for the assignment itself — the final report is written (`report/REPORT.md`, `implementation_plan.md` §12 row #25) and cites everything above. The one remaining disclosed item is the golden-set-generation-scripts reproducibility gap (§9 below) — known, not blocking, and does not affect the validity of the already-committed golden set. What remains is submission per `assignment.text`.
- **Final golden artifacts**: `golden_set/CANDIDATE_MANIFEST_200.csv` (sampling manifest, provisional labels — NOT gold), `golden_set/GOLDEN_ANNOTATION_200_labeled.xlsx` (completed annotation workbook — source of truth for gold), `golden_set/GOLDEN_200_FINAL.csv` (clean gold export: candidate_id, tweet_id, thread_id, customer_id, target_message, human_gold_label, human_notes), `golden_set/GOLDEN_200_ANALYSIS.md` (validation + AI-agreement analysis), `golden_set/PROPOSED_GUIDE_CLARIFICATIONS.md` and `golden_set/GUIDE_CHANGELOG_AFTER_GOLD.md` (post-golden guide review and changelog).
- **Baseline artifacts**: `evaluation/BASELINE_RESULTS.md` (report) and `evaluation/results/baseline_results.json` (machine-readable metrics) — trained on 296 of 300 DEVELOPMENT discovery examples (Ex 70, 78, 164, 265 excluded as unparseable), evaluated on `golden_set/GOLDEN_200_FINAL.csv`.
- **Retrieval/generation/triage artifacts**: `evaluation/K_ABLATION_SWEEP_RESULTS.md` + `evaluation/results/k_ablation_sweep.json` (the 800-condition sweep, committed), `evaluation/results/retrieval_inspection_annotations.csv` (committed), `evaluation/results/triage_tier2_dm_redirect_analysis.json` + `evaluation/results/triage_tier2_audit.json` (gitignored), `evaluation/results/part_j_triage_eval.json` (gitignored), `evaluation/results/JUDGE_HUMAN_CALIBRATION_40.xlsx` (committed) + `evaluation/results/judge_human_agreement.json` (gitignored). Most `evaluation/results/*.json` files are gitignored (execution artifacts) — see `README.md`'s reproduction section for which are committed vs. regenerable vs. require API credit to regenerate.

## 3. Dataset Facts
- **Brand**: SpotifyCares
- **Dataset**: Customer Support on Twitter / `twcs.csv`
- **Current split**: DEVELOPMENT / RETRIEVAL / TEST separation already established.
- **DEVELOPMENT size**: 6,481 customer->brand pairs.
- **Historical Retrieval Terminology**: The actual historical data consists of customer-support interactions and SpotifyCares responses, with resolution evidence where observable. We do NOT broadly describe the RAG corpus as "resolved cases."

## 4. Current Architecture
The intended system is deliberately simple:
```text
Customer message
    ↓
Intent classification
    ↓
Deterministic triage / escalation decision
    ↓
Historical interaction retrieval
    ↓
Evidence sufficiency check
    ↓
AUTO-HANDLE → grounded response
        OR
HUMAN ESCALATION → reason
```
*Note: Sentiment and information extraction are NOT mandatory independent subsystems unless the actual implementation later demonstrates a concrete need for them. Do not describe an unnecessarily complex multi-agent architecture.*

## 5. Data Boundaries & Golden-Set Isolation
- **DEVELOPMENT (4,242 threads / 6,481 pairs)**: Taxonomy discovery (300-example review). TF-IDF training for the baseline milestone is **complete**, using 296 of these 300 discovery examples as the training substitution (4 excluded as unparseable — Ex 70, 78, 164, 265; see `DECISION_LOG.md` #24 and #13).
- **RETRIEVAL (18,382 threads / 27,903 pairs)**: Historical retrieval index. Retrieval evidence for response generation must come ONLY from this pool — never from TEST/golden (see `DECISION_LOG.md` #18).
- **TEST (5,656 threads / 8,708 pairs)**: Sealed source pool for the golden evaluation set.
- **Golden Set**: 200 examples (within the required 150-250), sampled entirely from TEST. Representative base, deliberate boundary coverage, rare-intent coverage, genuine UNKNOWN coverage, not dominated by hard cases, not simply random, not artificially balanced across all intents, isolated from retrieval/development leakage (verified programmatically) and from retrieval-pool text duplication (verified via exact + normalized-text checks).
- **Golden Set Status: COMPLETE AND FINAL.** All 200 examples have a human gold label (`Human Final Label` in `golden_set/GOLDEN_ANNOTATION_200_labeled.xlsx`, exported cleanly to `golden_set/GOLDEN_200_FINAL.csv`). **These 200 labels are immutable and evaluation-only** — see `DECISION_LOG.md` #17. Do not relabel them, do not use them for training/few-shot selection, and do not insert them into the RAG/retrieval corpus.
- **Development labels vs. final gold**: The 300-example discovery review (`discovery/HUMAN_REVIEW_labeled.md`) and the AI Suggested Label column in the golden workbook are **not** authoritative — they informed taxonomy design and accelerated review, but only `Human Final Label` in the completed golden workbook is gold.

### Leakage/isolation checks: real, executed functions

`implementation_plan.md` §13's `verify_all_isolation()` is planning-stage
pseudocode, superseded by the real functions below (not deleted or rewritten
here). Each row is a function that actually exists and actually runs:

| Function | Checks | File | Invoked from |
|---|---|---|---|
| `assert_no_overlap` | Generic tweet_id/thread_id set-overlap primitive, raises `LeakageError` | `evaluation/leakage_checks.py:13` | Called by the two `assert_no_leakage`/`assert_hard_leakage_free`/`assert_fewshot_no_golden_leakage` wrappers below |
| `assert_no_leakage` | Pairwise tweet_id/thread_id overlap across DEV (training)/golden (TEST)/RETRIEVAL pools (6 checks) | `evaluation/leakage_checks.py:22` | `evaluation/run_baselines.py:55`, before training; `evaluation/test_baseline_milestone.py:108` |
| `assert_hard_leakage_free` | Zero tweet_id/thread_id overlap between the golden 200 and the sampled retrieval index | `evaluation/build_retrieval_index.py:265` | `evaluation/build_retrieval_index.py:333` (index build, main flow); `evaluation/test_retrieval.py:101,116` |
| `near_duplicate_check` | Warning-level (not a hard stop): flags golden/retrieval-pair text with cosine similarity above threshold | `evaluation/build_retrieval_index.py:241` | `evaluation/build_retrieval_index.py:325` (index build, main flow) |
| `assert_fewshot_no_golden_leakage` | Zero tweet_id/thread_id overlap between selected few-shot demonstrations and the golden 200 | `evaluation/fewshot_selection.py:92` | `evaluation/run_llm_classifier.py:81`, before classification; `evaluation/test_llm_classifier_milestone.py:167,173` |

## 6. Intent Taxonomy
- **STATUS**: The 8-label taxonomy is FROZEN — confirmed to remain exactly 8 intents even after a post-golden review of all 17 AI/human disagreements on the completed golden set (see `DECISION_LOG.md` #22). No intent has been added, removed, merged, or split at any point.
- **TAXONOMY**: 
  1. ACCOUNT_ACCESS
  2. SUBSCRIPTION_BILLING
  3. APP_TECH_ISSUE
  4. CONTENT_CATALOG
  5. FEATURE_FEEDBACK
  6. ARTIST_SUPPORT
  7. GENERAL_HOW_TO_INFO
  8. UNKNOWN_OTHER
- **Post-golden guide clarifications**: 7 wording/example clarifications were applied to `discovery/TAXONOMY_REVIEW_GUIDE.md` after golden annotation, each tagged inline `(post-golden clarification)` and each motivated by a specific golden-set disagreement. 3 proposed clarifications were deliberately left unresolved (internally inconsistent or single-case evidence) rather than force-resolved. Full detail: `golden_set/GUIDE_CHANGELOG_AFTER_GOLD.md`.

## 7. Discovery & Pilot & Golden Phase State
- **DISCOVERY PHASE (complete)**: The 300-example human review was a DISCOVERY / TAXONOMY REFINEMENT exercise to discover recurring intents, boundary cases, refine rules. It is NOT the final golden benchmark. Some historical discovery labels may be inconsistent with the latest frozen guide and therefore must not be blindly reused as gold.
- **PILOT PHASE (deferred, not completed)**: The 100-example pilot workbook (`discovery/PILOT_ANNOTATION_100*.xlsx`) tested whether the annotation rules, context presentation, and interface were usable. It was NEVER human-annotated — deliberately deferred once the golden-set pipeline itself validated the same things directly (see `DECISION_LOG.md` #24). It is NOT model training, final evaluation, or a source of gold labels.
- **GOLDEN PHASE (complete)**: All 200 golden examples have been sampled from TEST, QA'd, blind-annotated, AI-prelabeled for review acceleration, and human-labeled. `Human Final Label` in `golden_set/GOLDEN_ANNOTATION_200_labeled.xlsx` is the sole gold reference (see `DECISION_LOG.md` #21 for why gold lives in that column and not the originally-planned `Human Gold Label` column). The 200 labels are locked — no further relabeling (`DECISION_LOG.md` #17).
- **Chronology**: `created_at` timestamps are the authority for strict chronology, NOT numeric `tweet_id`. Centralized in `discovery/chronology.py`, regression-tested in `discovery/test_chronology.py`, used consistently across the pilot workbook and the golden-set `THREAD_VIEW` sheet.

## 8. Evaluation Plan State
Evaluation is a first-class project concern.
- **A. Intent classification — COMPLETE.** Accuracy, Macro F1, per-intent precision/recall, confusion matrix, all three classifiers. `evaluation/LLM_CLASSIFIER_RESULTS.md`, `evaluation/BASELINE_RESULTS.md`.
- **B. Escalation / auto-handle — COMPLETE (Part J).** Evaluated against `golden_set/TRIAGE_ANNOTATION_40.csv`: 32/40 (80.0%) agreement, 3/40 false-auto-handle, 5/40 false-escalate (shipped-default policy, realistic LLM-predicted-intent condition; all 4 arm x intent-source conditions computed). `evaluation/run_part_j_triage_eval.py`, `evaluation/results/part_j_triage_eval.json`.
- **C. Response quality — COMPLETE.** LLM judge (Relevance/Groundedness/Helpfulness/Tone, 1-5) scored all 800 k-ablation conditions. `evaluation/generation.py`, `evaluation/K_ABLATION_SWEEP_RESULTS.md`.
- **D. Judge validation — COMPLETE, result is a caution not a pass (Part I).** 40 human-graded examples (k=3) vs. the same LLM judge scores: weighted Cohen's kappa 0.09-0.23 across the 4 dimensions, most 95% CIs include zero — agreement is not yet demonstrated to be reliably better than chance. Valid for k=3 only. `evaluation/analyze_judge_human_agreement.py`, `evaluation/results/judge_human_agreement.json`.
- **E. Baselines — COMPLETE.** Majority-class baseline, TF-IDF + Logistic Regression. `evaluation/BASELINE_RESULTS.md`.

## 9. Important Repository Files
- `config.py`: Centralized configuration (paths, seeds, brand, model names).
- `data/prepare.py`: Filters SpotifyCares, reconstructs threads.
- `data/split.py`: Performs 3-way split.
- `discovery/chronology.py`: Shared `created_at`-based chronology utility (see `DECISION_LOG.md` #8).
- `discovery/TAXONOMY_REVIEW_GUIDE.md`: The authoritative, frozen annotation rulebook (now includes 7 post-golden clarifications).
- `golden_set/GOLDEN_200_FINAL.csv`: The clean final gold export — candidate_id, tweet_id, thread_id, customer_id, target_message, human_gold_label, human_notes. **This is the file to load for evaluation.**
- `golden_set/GOLDEN_ANNOTATION_200_labeled.xlsx`: The completed annotation workbook (source of truth `Human Final Label` was exported from).
- `golden_set/GOLDEN_200_ANALYSIS.md`: Validation results, gold-label distribution, AI-prelabel-vs-gold agreement analysis, disagreement patterns.
- `golden_set/GUIDE_CHANGELOG_AFTER_GOLD.md`: What changed in the guide after golden annotation, and why.
- `hiver_sde_takehome_strategy.md`: Strategic North Star.
- `DECISION_LOG.md`: Full decision trail with human/AI attribution — read this for "why," not just "what."
- `evaluation/retrieval.py`, `evaluation/build_retrieval_index.py`: Brute-force cosine-similarity retrieval over the RETRIEVAL pool; index at `cache/retrieval_index/` (gitignored).
- `evaluation/generation.py`: Response generator + minimal LLM judge (`GENERATE_MODEL`/`JUDGE_MODEL` in `config.py`), including the evidence-cleaning step.
- `evaluation/run_k_ablation_sweep.py`, `evaluation/k_ablation_stats.py`, `evaluation/run_k_ablation_stats.py`: The full k=0/1/3/5 sweep and its 12-comparison Wilcoxon statistics. Results: `evaluation/K_ABLATION_SWEEP_RESULTS.md`.
- `evaluation/triage.py`, `evaluation/audit_triage_tier2.py`: The three-tier triage policy and its Fisher's-exact robustness audit.
- `evaluation/run_part_j_triage_eval.py`: Part J — triage policy vs. the human holdout (`golden_set/TRIAGE_ANNOTATION_40.csv`).
- `evaluation/build_judge_human_calibration_workbook.py`, `evaluation/analyze_judge_human_agreement.py`: Part I — judge-vs-human agreement study. Workbook: `evaluation/results/JUDGE_HUMAN_CALIBRATION_40.xlsx`.

### Known reproducibility gap (honest, not yet fixed)
The scripts used to sample the 200 golden candidates, run the manifest QA pass, build the annotation workbook, and generate the AI prelabels were written and executed interactively during this project's working sessions but are **not currently checked into this repository** — only their outputs are (`golden_set/CANDIDATE_MANIFEST_200.csv`, `golden_set/GOLDEN_ANNOTATION_200.xlsx`, `golden_set/ai_prelabels.csv`). The methodology is fully documented (this file, `DECISION_LOG.md`, `golden_set/GOLDEN_200_ANALYSIS.md`), and the outputs are reproducible in principle from `data/generated/test_pairs.jsonl` + `GOLDEN_SAMPLE_SEED=456` + `discovery/TAXONOMY_REVIEW_GUIDE.md`, but re-running the exact original scripts is not currently possible from a fresh clone. This does not affect the validity of the golden set itself (which is now a fixed, committed artifact), only the ability to regenerate it from scratch. Worth fixing before claiming full 15-minute reproducibility in the final README.
