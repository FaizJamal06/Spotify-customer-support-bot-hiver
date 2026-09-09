# Project Context

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
- **CURRENT PHASE**: Pre-execution / Phase 1 (Data Preparation) pending run.
- **COMPLETED**: Architecture design (v3 approved), project config (`config.py`), and Phase 1 scripts (`data/prepare.py`, `data/split.py`).
- **CURRENT BLOCKERS**: None, waiting for permission to execute Phase 1.

## 3. Dataset Facts
- **CONFIRMED FACT**: Dataset is Kaggle Customer Support on Twitter (~3M tweets).
- **CONFIRMED FACT**: SpotifyCares chosen as the brand (has ~43k outbound messages, 31.8% DM redirect rate, 77.2% unique responses).
- **DECISION**: No "resolved" labels exist in the dataset; corpus will be based purely on observed pairs.

## 4. Current Architecture
- **DECISION**: Single LLM pipeline for intent classification & generation + TF-IDF/LogReg and Majority baselines.
- **DECISION**: Embeddings via `all-MiniLM-L6-v2` + cosine similarity for historical retrieval.

## 5. Data Boundaries
- **DECISION**: Strict 3-way thread-level split to prevent leakage.
  - **DEVELOPMENT (~15%)**: Taxonomy discovery, pilot labeling, TF-IDF training.
  - **RETRIEVAL (~65%)**: Historical retrieval index.
  - **TEST (~20%)**: Golden evaluation set (sealed).

## 6. Intent Taxonomy
- **STATUS**: Not started.
- **HYPOTHESIS**: Initial estimate 6-8 intents, to be discovered bottom-up from 300 DEVELOPMENT messages.

## 7. Golden-Set Status
- **STATUS**: Not started. Will be sampled from TEST pool.

## 8. Baseline Status/Results
- **STATUS**: Not started.

## 9. Experiment Status/Results
- **STATUS**: Not started.

## 10. Retrieval Ablation Results
- **STATUS**: Not started. (Plan: compare k=0, 1, 3, 5).

## 11. Judge Calibration Results
- **STATUS**: Not started.

## 12. Triage Policy
- **DECISION**: Three tiers.
  - Tier 1: Hard safety rules (UNKNOWN intent -> escalate, Security -> escalate, Legal -> escalate).
  - Tier 2: Dataset-supported (to be determined by experiments).
  - Tier 3: Experimental assumptions (e.g., anger keywords -> escalate).

## 13. Important Design Decisions
- See `DECISION_LOG.md` (to be populated as we build).

## 14. Known Issues and Limitations
- The project is not yet a git repository.
- Windows encoding issues required forcing UTF-8 in `sys.stdout` for earlier exploratory scripts.

## 15. Open Questions
- None currently. Waiting to execute Phase 1.

## 16. Important Repository Files
- `config.py`: Centralized configuration.
- `data/prepare.py`: Filters SpotifyCares, reconstructs threads.
- `data/split.py`: Performs 3-way split.
- `implementation_plan.md`: The approved v3 design and ordered plan.

## 17. Environment/Setup Requirements
- `OPENAI_API_KEY` must be set in the environment.
- Python dependencies (pandas, scikit-learn, sentence-transformers) will be required.

## 18. Exact Next Action
- Run `git init`.
- Run `python data/prepare.py` followed by `python data/split.py` to complete Phase 1.
