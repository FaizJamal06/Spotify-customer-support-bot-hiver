# Assignment Requirements Checklist

| Phase / Requirement | Status | Notes |
|---|---|---|
| **COMPLETED** | | |
| Dataset exploration | COMPLETED | Kaggle TWCS dataset analyzed. |
| Spotify brand selection | COMPLETED | SpotifyCares chosen. |
| Thread reconstruction | COMPLETED | Handled in `data/prepare.py`. |
| Split creation | COMPLETED | DEV, RETRIEVAL, TEST splits done. |
| Leakage checks | COMPLETED | Thread-level separation verified. |
| Taxonomy discovery | COMPLETED | 300-example human review completed. |
| Annotation-guide refinement | COMPLETED | Edge cases resolved. |
| Taxonomy freeze | COMPLETED | Locked to 8 labels. |
| Chronology bug discovery/fix | COMPLETED | `created_at` used for target context. |
| Pilot workbook / protocol preparation | COMPLETED | Workbook generation, annotation-protocol/interface design, and context/chronology workflow prepared (4 iterations, `discovery/PILOT_ANNOTATION_100*.xlsx`). Human annotation of the 100 examples has NOT been performed. |
| **CURRENT** | | |
| Golden-set sampling design | IN PROGRESS | Inspecting DEV pool to produce a sampling proposal. |
| **NOT YET COMPLETED** | | |
| 100-example pilot human annotation | DEFERRED | Pilot workbook exists but contains no human-assigned gold labels. Deferred; not required to proceed with golden-set methodology design or taxonomy confidence, which rest on the completed 300-example discovery review. |
| Final 150-250 example selection | NOT STARTED | Pending sampling proposal. |
| Final golden annotation | NOT STARTED | Pending golden set creation. |
| Classifier implementation/evaluation| NOT STARTED | Pending golden labels. |
| Retrieval evaluation | NOT STARTED | Pending. |
| Escalation evaluation | NOT STARTED | Pending. |
| Response generation evaluation | NOT STARTED | Pending. |
| LLM judge calibration | NOT STARTED | Pending approx 40 human-graded examples. |
| Final failure analysis | NOT STARTED | Pending evaluation results. |
| Headline-number limitations analysis | NOT STARTED | Pending final report. |
