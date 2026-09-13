# Intent Classification Baseline Results

Generated: 2026-09-14T00:42:30

## Training / evaluation data

- **Training data**: 296 of 300 DEVELOPMENT-pool discovery examples
  (`discovery/HUMAN_REVIEW_labeled.md`, loaded via `discovery/DISCOVERY_300_AUDIT.csv`).
  **4 excluded**: Ex 70, Ex 78, Ex 164, Ex 265 —
  source label unparseable. Not relabeled, not imputed, not adjudicated; these
  4 IDs never appear in the fitted training set and never receive an inferred
  or default label anywhere in this code.
- **These are DISCOVERY-phase labels, not final golden annotation.** They were
  produced in a single human annotation pass with no blind workbook and no
  AI-prelabel-plus-adjudication step — unlike the golden-200 process. This
  baseline's training data was **not** held to the same annotation rigor as
  the evaluation set, and that difference is a limitation of this milestone's
  results, not an oversight.
- **This training set is a documented substitution** for the originally-planned
  but never-collected 100-example pilot-labeled set (`discovery/PILOT_ANNOTATION_100*.xlsx`
  was built and protocol-tested but never human-annotated — see `DECISION_LOG.md` #24).
- **Compatibility with the current frozen guide**: a full audit
  (`discovery/DISCOVERY_300_AUDIT_REPORT.md`) found a **2.0% strict mismatch
  rate (6/300)** and a **6.7% conservative rate (20/300, including 14 POSSIBLE
  cases)** between these discovery labels and `discovery/TAXONOMY_REVIEW_GUIDE.md`
  as it exists today. **By explicit human decision, all 300 labels were used
  AS-IS for training — none of the 6 MISMATCH or 14 POSSIBLE cases were
  corrected.** This training data was not cleaned against the audit; readers
  should not assume it was.
- **Evaluation data**: 200 golden TEST examples
  (`golden_set/GOLDEN_200_FINAL.csv`), used only for scoring. Never used for
  training, fitting, vocabulary construction, or any tuning decision.
- **Leakage checks**: zero tweet_id/thread_id overlap verified, pairwise,
  across training (DEVELOPMENT), evaluation (TEST), and the RETRIEVAL pool.
  Summary: `{'train_tweet_ids': 296, 'train_thread_ids': 285, 'golden_tweet_ids': 200, 'golden_thread_ids': 197, 'retrieval_tweet_ids': 26914, 'retrieval_thread_ids': 18380, 'checks_passed': 6}`.

### Training label distribution (296 examples)

- APP_TECH_ISSUE: 69
- UNKNOWN_OTHER: 64
- FEATURE_FEEDBACK: 49
- SUBSCRIPTION_BILLING: 33
- CONTENT_CATALOG: 27
- GENERAL_HOW_TO_INFO: 26
- ACCOUNT_ACCESS: 24
- ARTIST_SUPPORT: 4

---

## Baseline A — Majority class

Predicts **APP_TECH_ISSUE** (the most frequent training label,
69/296 of the
training set) for every evaluation example. The floor this milestone is meant
to clear.

| Metric | Value |
|---|---:|
| Accuracy | 20.0% |
| Macro precision | 0.025 |
| Macro recall | 0.125 |
| Macro F1 | 0.042 |

### Per-class

| Intent | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| ACCOUNT_ACCESS | 0.000 | 0.000 | 0.000 | 19 |
| SUBSCRIPTION_BILLING | 0.000 | 0.000 | 0.000 | 21 |
| APP_TECH_ISSUE | 0.200 | 1.000 | 0.333 | 40 |
| CONTENT_CATALOG | 0.000 | 0.000 | 0.000 | 15 |
| FEATURE_FEEDBACK | 0.000 | 0.000 | 0.000 | 40 |
| ARTIST_SUPPORT | 0.000 | 0.000 | 0.000 | 14 |
| GENERAL_HOW_TO_INFO | 0.000 | 0.000 | 0.000 | 28 |
| UNKNOWN_OTHER | 0.000 | 0.000 | 0.000 | 23 |

### Confusion matrix (rows = true label, columns = predicted label)

| True \ Pred | ACCOUNT ACCESS | SUBSCRIPTION B | APP TECH ISSUE | CONTENT CATALO | FEATURE FEEDBA | ARTIST SUPPORT | GENERAL HOW TO | UNKNOWN OTHER |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **ACCOUNT ACCESS** | 0 | 0 | 19 | 0 | 0 | 0 | 0 | 0 |
| **SUBSCRIPTION B** | 0 | 0 | 21 | 0 | 0 | 0 | 0 | 0 |
| **APP TECH ISSUE** | 0 | 0 | 40 | 0 | 0 | 0 | 0 | 0 |
| **CONTENT CATALO** | 0 | 0 | 15 | 0 | 0 | 0 | 0 | 0 |
| **FEATURE FEEDBA** | 0 | 0 | 40 | 0 | 0 | 0 | 0 | 0 |
| **ARTIST SUPPORT** | 0 | 0 | 14 | 0 | 0 | 0 | 0 | 0 |
| **GENERAL HOW TO** | 0 | 0 | 28 | 0 | 0 | 0 | 0 | 0 |
| **UNKNOWN OTHER** | 0 | 0 | 23 | 0 | 0 | 0 | 0 | 0 |

---

## Baseline B — TF-IDF + Logistic Regression

TF-IDF vocabulary size: 1408 (fit on the 296 training texts
only). Hyperparameters: `TfidfVectorizer({})`,
`LogisticRegression({'max_iter': 1000, 'random_state': 42})` — scikit-learn
defaults plus a fixed seed and a raised `max_iter` for convergence; no grid
search, nothing tuned against golden-200 performance.

| Metric | Value |
|---|---:|
| Accuracy | 42.0% |
| Macro precision | 0.371 |
| Macro recall | 0.351 |
| Macro F1 | 0.314 |

### Per-class

| Intent | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| ACCOUNT_ACCESS | 0.667 | 0.526 | 0.588 | 19 |
| SUBSCRIPTION_BILLING | 0.636 | 0.333 | 0.438 | 21 |
| APP_TECH_ISSUE | 0.369 | 0.775 | 0.500 | 40 |
| CONTENT_CATALOG | 0.000 | 0.000 | 0.000 | 15 |
| FEATURE_FEEDBACK | 0.488 | 0.525 | 0.506 | 40 |
| ARTIST_SUPPORT | 0.000 | 0.000 | 0.000 | 14 |
| GENERAL_HOW_TO_INFO | 0.500 | 0.036 | 0.067 | 28 |
| UNKNOWN_OTHER | 0.311 | 0.609 | 0.412 | 23 |

### Confusion matrix (rows = true label, columns = predicted label)

| True \ Pred | ACCOUNT ACCESS | SUBSCRIPTION B | APP TECH ISSUE | CONTENT CATALO | FEATURE FEEDBA | ARTIST SUPPORT | GENERAL HOW TO | UNKNOWN OTHER |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **ACCOUNT ACCESS** | 10 | 0 | 3 | 0 | 1 | 0 | 0 | 5 |
| **SUBSCRIPTION B** | 2 | 7 | 7 | 0 | 1 | 0 | 0 | 4 |
| **APP TECH ISSUE** | 1 | 1 | 31 | 0 | 2 | 0 | 0 | 5 |
| **CONTENT CATALO** | 0 | 0 | 5 | 0 | 7 | 0 | 0 | 3 |
| **FEATURE FEEDBA** | 0 | 0 | 15 | 0 | 21 | 0 | 0 | 4 |
| **ARTIST SUPPORT** | 0 | 0 | 7 | 0 | 3 | 0 | 1 | 3 |
| **GENERAL HOW TO** | 2 | 3 | 12 | 0 | 3 | 0 | 1 | 7 |
| **UNKNOWN OTHER** | 0 | 0 | 4 | 0 | 5 | 0 | 0 | 14 |

---

## Reproducing this report

```bash
python evaluation/run_baselines.py
```

Fixed seed: `BASELINE_SEED = 42` (`config.py`).
No part of the training data, hyperparameters, or evaluation is randomized
beyond this seed; the same code against the same repository state reproduces
identical results. Machine-readable results: `evaluation/results/baseline_results.json`.
