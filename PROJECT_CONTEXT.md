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
- **CURRENT PHASE**: Golden set complete; majority-class and TF-IDF+LogReg baselines complete; about to start the remaining pipeline/LLM work.
- **COMPLETED**: Dataset exploration, Spotify brand selection, thread reconstruction, split creation, leakage checks, taxonomy discovery, 300-example discovery review, annotation-guide refinement, taxonomy freeze, chronology bug discovery/fix, pilot preparation/protocol work (100-example workbook built, never human-annotated — deliberately deferred, see `DECISION_LOG.md` #24), golden-set candidate sampling (200 from TEST), full manual QA pass over all 200 candidates, blind annotation workbook, AI-assisted prelabeling pass, **human gold annotation of all 200 examples (complete)**, AI-vs-human agreement analysis, post-golden taxonomy review (taxonomy kept at exactly 8 intents), 7 approved guide wording clarifications applied to the frozen guide, discovery-300 compatibility audit against the frozen guide (`discovery/DISCOVERY_300_AUDIT_REPORT.md`), **intent-classification baselines** (majority-class + TF-IDF/Logistic Regression, trained on 296 of the 300 DEVELOPMENT discovery examples — 4 excluded as unparseable: Ex 70, 78, 164, 265 — evaluated on the 200 golden TEST examples; see `evaluation/BASELINE_RESULTS.md`).
- **IMMEDIATE NEXT STEP**: Per `implementation_plan.md` §12 row #10 ("LLM provider (classify, generate, judge)") — the one remaining precondition, alongside the already-complete #8/#11/#12, for row #16 ("Exp 1: Run all 3 classifiers on golden 200"). The LLM few-shot classifier's example source is still an open decision (see `implementation_plan.md` §6 "LLM Few-Shot") and must be resolved before Exp 1 can run all three classifiers.
- **Final golden artifacts**: `golden_set/CANDIDATE_MANIFEST_200.csv` (sampling manifest, provisional labels — NOT gold), `golden_set/GOLDEN_ANNOTATION_200_labeled.xlsx` (completed annotation workbook — source of truth for gold), `golden_set/GOLDEN_200_FINAL.csv` (clean gold export: candidate_id, tweet_id, thread_id, customer_id, target_message, human_gold_label, human_notes), `golden_set/GOLDEN_200_ANALYSIS.md` (validation + AI-agreement analysis), `golden_set/PROPOSED_GUIDE_CLARIFICATIONS.md` and `golden_set/GUIDE_CHANGELOG_AFTER_GOLD.md` (post-golden guide review and changelog).
- **Baseline artifacts**: `evaluation/BASELINE_RESULTS.md` (report) and `evaluation/results/baseline_results.json` (machine-readable metrics) — trained on 296 of 300 DEVELOPMENT discovery examples (Ex 70, 78, 164, 265 excluded as unparseable), evaluated on `golden_set/GOLDEN_200_FINAL.csv`.

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
Evaluation is a first-class project concern. The intended evaluation includes:
- **A. Intent classification**: Accuracy, Macro F1, Per-intent precision, Per-intent recall, Confusion matrix.
- **B. Escalation / auto-handle**: escalation precision, escalation recall, false auto-handle rate, false escalation rate.
- **C. Response quality**: LLM judge using a defined rubric.
- **D. Judge validation**: compare LLM judge scores against human judgments (approx 40 human-graded examples).
- **E. Baselines**: majority-class baseline, TF-IDF + Logistic Regression.

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

### Known reproducibility gap (honest, not yet fixed)
The scripts used to sample the 200 golden candidates, run the manifest QA pass, build the annotation workbook, and generate the AI prelabels were written and executed interactively during this project's working sessions but are **not currently checked into this repository** — only their outputs are (`golden_set/CANDIDATE_MANIFEST_200.csv`, `golden_set/GOLDEN_ANNOTATION_200.xlsx`, `golden_set/ai_prelabels.csv`). The methodology is fully documented (this file, `DECISION_LOG.md`, `golden_set/GOLDEN_200_ANALYSIS.md`), and the outputs are reproducible in principle from `data/generated/test_pairs.jsonl` + `GOLDEN_SAMPLE_SEED=456` + `discovery/TAXONOMY_REVIEW_GUIDE.md`, but re-running the exact original scripts is not currently possible from a fresh clone. This does not affect the validity of the golden set itself (which is now a fixed, committed artifact), only the ability to regenerate it from scratch. Worth fixing before claiming full 15-minute reproducibility in the final README.
