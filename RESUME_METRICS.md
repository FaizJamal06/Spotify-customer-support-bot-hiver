# Resume Metrics: SpotifyCares Support Agent

**Project Summary:** An AI customer-support agent for Twitter that classifies messages into an 8-intent taxonomy, triages cases (auto-handle vs escalate), and generates grounded replies using `gpt-5.4-mini` and `gpt-5.6-terra`.

## 1. Metrics Table

| Metric | Value | Evidence | Status | Ownership |
|---|---|---|---|---|
| **LLM Intent Classifier Accuracy** | 81.0% | `evaluation/LLM_CLASSIFIER_RESULTS.md` (Tested on 200 golden examples) | Verified | Mine (FaizJamal06) |
| **LLM Intent Classifier Macro F1** | 0.808 | `evaluation/LLM_CLASSIFIER_RESULTS.md` | Verified | Mine |
| **Baseline Accuracy (TF-IDF + LogReg)** | 42.0% | `evaluation/BASELINE_RESULTS.md` | Verified | Mine |
| **Triage Policy Human Agreement** | 80.0% (32/40) | `report/REPORT.md`, `evaluation/results/part_j_triage_eval.json` | Verified | Mine |
| **K-Ablation Sweep Reliability** | 800/800 conditions, 0 failures | `evaluation/K_ABLATION_SWEEP_RESULTS.md` | Verified | Mine |
| **Codebase Size** | 11,837 Python LOC | Measured via `Get-ChildItem ... \| Measure-Object -Line` | Verified | Mine |
| **Test Suite Quality** | 328 tests (301 passed) | `README.md` (fast/free verification section) | Verified | Mine |
| **False-auto-handle rate** | 3/40 cases | `report/REPORT.md` (Triage Part J) | Verified | Mine |
| **Retrieval Index Size** | 3,000-pair sample | `README.md` (Retrieval index built) | Verified | Mine |
| **LLM Judge / Human Calibration (Kappa)** | -0.037 (Groundedness) | `report/REPORT.md` | Verified | Mine |

## 2. Ask Me (To Strengthen Resume)
- **Latency / RPS:** There is a "wall time: 630.7s" for 200 calls in `LLM_CLASSIFIER_RESULTS.md`, which is ~3.15s per query. If you have metrics for end-to-end latency, throughput (requests per second), or concurrency performance, we should add them.
- **Cost Efficiency:** `K_ABLATION_SWEEP_RESULTS.md` mentions the 800-condition sweep only cost ~$6.21. Adding average cost-per-query optimizations would look great for Forward Deployed / AI Engineering roles.
- **CI/CD & Deployments:** There are no GitHub Action workflows or live URLs listed. Did you deploy this anywhere, or was it purely local/take-home? If deployed, what's the uptime or scaling capability?

## 3. Do Not Use
- **"Retrieval significantly improves Groundedness"**: Do **NOT** use this as a positive metric without heavy caveats. Your own report (`report/REPORT.md`) explicitly states this is a "misleading headline number." The LLM judge's scores went up, but a human calibration study found the judge completely disagrees with human raters on Groundedness (Cohen's kappa = -0.037). Presenting this as a pure win on a resume would contradict your own rigorous analysis.
- **Confidence Threshold Rules**: Do not claim the system routes based on confidence scores. The calibration study (ECE=0.140) proved the model is overconfident, so you explicitly rejected thresholding (`DECISION_LOG.md`).

## 4. Resume Bullets (Action + Built + Measurable Result)
- Designed an LLM intent classifier (gpt-5.4-mini) using a 39-example few-shot prompt, doubling baseline macro F1 (0.808 vs 0.314) and achieving 81.0% accuracy.
- Engineered a 3-tier triage rule-engine, reaching 80.0% agreement with held-out human labels while securely escalating complex support cases.
- Built a concurrent 800-condition k-ablation experiment pipeline for a retrieval-augmented generator, processing 1,800 context items with 0 failures.
- Developed a comprehensive evaluation suite with 328 tests, catching critical LLM-judge blind spots via bootstrap Cohen's kappa calibration vs human raters.

## 5. Interview Notes (Talking Points)
- **The "Misleading" Metric Story:** The best thing to talk about in an interview is how you didn't trust your own "good" results. The LLM judge showed retrieval massively boosted groundedness, but you took the extra step to run a human-calibration check. Finding out the judge completely disagreed with humans (kappa = -0.037) and choosing *not* to report the fake win shows incredible maturity and rigorous AI engineering.
- **The Fragile Triage Rule:** Talk about the Tier-2 ACCOUNT_ACCESS rule. Non-overlapping confidence intervals made it look like a sure thing. But when you ran a proper Fisher's exact test (p=0.094) and robustness check, it fell apart. You chose to ship it *disabled by default*. This is a perfect example of prioritizing system safety over shipping brittle heuristics.
