# Assignment Requirements Checklist

| Phase / Requirement | Status | Notes |
|---|---|---|
| **COMPLETED** | | |
| Dataset exploration | COMPLETED | Kaggle TWCS dataset analyzed. |
| Spotify brand selection | COMPLETED | SpotifyCares chosen. |
| Thread reconstruction | COMPLETED | Handled in `data/prepare.py`. |
| Split creation | COMPLETED | DEV, RETRIEVAL, TEST splits done (4,242 / 18,382 / 5,656 threads). |
| Leakage checks | COMPLETED | Thread-level separation verified programmatically. |
| Taxonomy discovery | COMPLETED | 300-example human review completed (`discovery/HUMAN_REVIEW_labeled.md`). |
| Annotation-guide refinement | COMPLETED | 4 edge cases resolved during initial freeze; 7 more wording clarifications applied post-golden. |
| Taxonomy freeze | COMPLETED | Locked to 8 labels; reconfirmed unchanged after post-golden review. |
| Chronology bug discovery/fix | COMPLETED | `created_at` used everywhere via `discovery/chronology.py`, regression-tested. |
| Pilot workbook / protocol preparation | COMPLETED | Workbook generation, annotation-protocol/interface design, and context/chronology workflow prepared (4 iterations, `discovery/PILOT_ANNOTATION_100*.xlsx`). Human annotation of the 100 examples was deliberately DEFERRED, not performed — see `DECISION_LOG.md` #24. |
| Golden-set sampling design | COMPLETED | 200 examples sampled from TEST pool only; representative + targeted boundary/rare-intent coverage; `golden_set/CANDIDATE_MANIFEST_200.csv`. |
| Golden-set candidate QA | COMPLETED | Full individual QA pass over all 200 candidates (duplicate/isolation/retrieval-overlap checks, 2 candidates replaced). |
| Blind annotation workbook | COMPLETED | `golden_set/GOLDEN_ANNOTATION_200.xlsx` — 4 sheets (GOLDEN_200, THREAD_VIEW, GUIDE, SAMPLING_INFO), no provisional/AI content exposed. |
| AI-assisted prelabeling pass | COMPLETED | AI Suggested Label / Reasoning / Confidence added to accelerate human review; kept structurally non-binding (blank gold column, explicit "not gold" banner). `golden_set/ai_prelabels.csv`, `golden_set/AI_PRELABEL_SUMMARY` sheet. |
| **Final golden annotation (200/200 human gold labels)** | **COMPLETED** | `golden_set/GOLDEN_ANNOTATION_200_labeled.xlsx`; gold lives in `Human Final Label` (see `DECISION_LOG.md` #21); exported to `golden_set/GOLDEN_200_FINAL.csv`. Labels are locked — no further relabeling. |
| AI-prelabel vs. human-gold agreement analysis | COMPLETED | 91.5% exact agreement (183/200); confusion matrix, per-intent recall/precision, confidence calibration in `golden_set/GOLDEN_200_ANALYSIS.md`. |
| Post-golden taxonomy-level review | COMPLETED | Taxonomy kept at exactly 8 intents — no disagreement pattern indicated a genuine missing category. `DECISION_LOG.md` #22. |
| Post-golden guide clarifications | COMPLETED | 7 of 9 proposed wording/example clarifications applied to `discovery/TAXONOMY_REVIEW_GUIDE.md`; 3 deliberately left unresolved. `golden_set/GUIDE_CHANGELOG_AFTER_GOLD.md`. |
| Documentation / reproducibility checkpoint | COMPLETED | This checkpoint — `DECISION_LOG.md`, `PROJECT_CONTEXT.md`, `REPOSITORY_STRUCTURE.md`, `README.md` brought in sync with current state; git status inspected; commit pushed. |
| **NOT YET STARTED** | | |
| Trivial baseline (majority-class) | NOT STARTED | Next milestone. Intentionally not started this session. |
| Simple baseline (TF-IDF + Logistic Regression) | NOT STARTED | Next milestone. |
| LLM-based intent classifier | NOT STARTED | Pending baseline results for comparison. |
| Retrieval index + evaluation | NOT STARTED | Pending; must be built from RETRIEVAL pool only (`DECISION_LOG.md` #18). |
| Escalation / triage evaluation | NOT STARTED | Pending classifier + calibration. |
| Response generation evaluation | NOT STARTED | Pending retrieval + classifier. |
| LLM judge calibration | NOT STARTED | Pending ~40 human-graded examples. |
| Final failure analysis | NOT STARTED | Pending evaluation results. |
| Headline-number limitations analysis | NOT STARTED | Pending final report. |
| Golden-set generation scripts checked into repo | NOT STARTED | Known reproducibility gap — see `PROJECT_CONTEXT.md` §9. Outputs are committed; the interactive scripts that produced them are not yet. |
