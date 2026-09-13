# LLM Intent Classifier Results

Generated: 2026-09-14T02:39:34
Prompt version: `v1`

## Few-shot demonstration source and selection method

- **Source**: discovery/DISCOVERY_300_AUDIT.csv existing_human_label, status == MATCH only.
- **Selection method**: sorted by example_id ascending per intent, deterministic, min=3 max=5.
- **Total demonstrations**: 39 (fixed for the entire evaluation run -- the same set is used for every one of the 200 golden queries; never varied per query, never selected/tuned/validated using the golden-200 examples).
- **Leakage check**: zero tweet_id/thread_id overlap between demonstration IDs and golden-set IDs, verified explicitly. Summary: `{'demo_tweet_ids': 39, 'demo_thread_ids': 39, 'golden_tweet_ids': 200, 'golden_thread_ids': 197, 'checks_passed': 2}`.

### Exact selected example_ids by intent

- **ACCOUNT_ACCESS** (5): Ex 11, Ex 46, Ex 60, Ex 75, Ex 89
- **SUBSCRIPTION_BILLING** (5): Ex 3, Ex 7, Ex 12, Ex 14, Ex 22
- **APP_TECH_ISSUE** (5): Ex 8, Ex 13, Ex 15, Ex 16, Ex 20
- **CONTENT_CATALOG** (5): Ex 9, Ex 28, Ex 33, Ex 50, Ex 63
- **FEATURE_FEEDBACK** (5): Ex 18, Ex 21, Ex 25, Ex 26, Ex 38
- **ARTIST_SUPPORT** (4): Ex 10, Ex 43, Ex 281, Ex 298
- **GENERAL_HOW_TO_INFO** (5): Ex 4, Ex 36, Ex 41, Ex 44, Ex 64
- **UNKNOWN_OTHER** (5): Ex 5, Ex 6, Ex 17, Ex 19, Ex 24

## Model / configuration

| Setting | Value |
|---|---|
| Model | `gpt-5.4-mini` |
| Temperature | 0 |
| Seed | 42 |
| Determinism mechanism | temperature=0 and seed (both empirically verified supported by gpt-5.4-mini at its default reasoning_effort='none'); response_format is a strict JSON schema constraining 'intent' to the 8 frozen labels |
| Output schema | Strict JSON schema (`response_format`), `intent` constrained to the 8 frozen labels by the API itself |
| Intent definitions | Extracted verbatim from `discovery/TAXONOMY_REVIEW_GUIDE.md` at run time (sections 1-8) -- not hand-summarized |
| Few-shot content | Customer text + frozen label only (no reasoning, no boundary tags, no golden-set content) |
| Caching | Disk-cached by hash of (model, prompt version, messages, temperature, seed) -- reruns are free |

## Evaluation

- **Data**: golden_set/GOLDEN_200_FINAL.csv (TEST (evaluation-only)), n=200.
- **Wall time**: 630.7s for this run (cached calls are near-instant on reruns).

### Full metrics

| Metric | Value |
|---|---:|
| Accuracy | 81.0% |
| Macro precision | 0.803 |
| Macro recall | 0.819 |
| Macro F1 | 0.808 |

### Per-class

| Intent | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| ACCOUNT_ACCESS | 0.708 | 0.895 | 0.791 | 19 |
| SUBSCRIPTION_BILLING | 0.810 | 0.810 | 0.810 | 21 |
| APP_TECH_ISSUE | 0.844 | 0.675 | 0.750 | 40 |
| CONTENT_CATALOG | 0.786 | 0.733 | 0.759 | 15 |
| FEATURE_FEEDBACK | 0.878 | 0.900 | 0.889 | 40 |
| ARTIST_SUPPORT | 0.812 | 0.929 | 0.867 | 14 |
| GENERAL_HOW_TO_INFO | 0.759 | 0.786 | 0.772 | 28 |
| UNKNOWN_OTHER | 0.826 | 0.826 | 0.826 | 23 |

### Confusion matrix (rows = true label, columns = predicted label)

| True \ Pred | ACCOUNT ACCESS | SUBSCRIPTION B | APP TECH ISSUE | CONTENT CATALO | FEATURE FEEDBA | ARTIST SUPPORT | GENERAL HOW TO | UNKNOWN OTHER |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **ACCOUNT ACCESS** | 17 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| **SUBSCRIPTION B** | 3 | 17 | 0 | 0 | 0 | 0 | 1 | 0 |
| **APP TECH ISSUE** | 2 | 2 | 27 | 3 | 0 | 1 | 2 | 3 |
| **CONTENT CATALO** | 0 | 0 | 0 | 11 | 1 | 1 | 1 | 1 |
| **FEATURE FEEDBA** | 0 | 0 | 2 | 0 | 36 | 1 | 1 | 0 |
| **ARTIST SUPPORT** | 0 | 0 | 0 | 0 | 1 | 13 | 0 | 0 |
| **GENERAL HOW TO** | 2 | 1 | 2 | 0 | 1 | 0 | 22 | 0 |
| **UNKNOWN OTHER** | 0 | 0 | 0 | 0 | 2 | 0 | 2 | 19 |

## Three-way comparison

| Classifier | Accuracy | Macro Precision | Macro Recall | Macro F1 |
|---|---:|---:|---:|---:|
| Majority class | 20.0% | 0.025 | 0.125 | 0.042 |
| TF-IDF + LogReg | 42.0% | 0.371 | 0.351 | 0.314 |
| LLM (gpt-5.4-mini) | 81.0% | 0.803 | 0.819 | 0.808 |

(Majority-class and TF-IDF+LogReg figures are read directly from `evaluation/results/baseline_results.json`, not recomputed.)

## Limitation

Few-shot demonstrations are restricted to audit-confirmed MATCH-status discovery examples, which removes known guide-inconsistent labels from the demonstration set. This does not fully equalize demonstration quality with the golden-200 evaluation set: these labels came from a single-pass discovery-phase annotation process, not the golden set's blind-workbook-plus-AI-prelabel-plus-human-adjudication process. The few-shot demonstrations reflect discovery-phase annotation rigor, not golden-set-grade rigor.

## Reproducing this report

```bash
python evaluation/run_llm_classifier.py
```

Requires `OPENAI_API_KEY` to be set. Cached responses under `cache/` make
reruns free and byte-identical unless the prompt version, model, or
demonstration set changes.
