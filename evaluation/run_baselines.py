"""
Intent-classification baseline milestone: majority-class + TF-IDF/LogReg,
trained on the 296 usable DISCOVERY-phase labels, evaluated on the 200 golden
TEST examples.

Usage (one command reproduces everything):
    python evaluation/run_baselines.py

Writes:
    evaluation/results/baseline_results.json
    evaluation/BASELINE_RESULTS.md

Does not train/tune on golden-200. Does not touch the RETRIEVAL pool as data.
Does not modify any frozen file. Does not commit or push anything.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.data_loading import (
    load_training_examples, load_golden_examples, load_retrieval_ids,
    DiscoverySplitMismatch, EXPECTED_VALID_COUNT, EXPECTED_EXCLUDED_IDS,
)
from evaluation.leakage_checks import assert_no_leakage, LeakageError
from evaluation.baselines import MajorityClassBaseline, TfidfLogRegBaseline
from evaluation.metrics import compute_metrics

RESULTS_JSON_PATH = config.EVAL_DIR / "baseline_results.json"
REPORT_MD_PATH = config.PROJECT_ROOT / "evaluation" / "BASELINE_RESULTS.md"


def main():
    config.ensure_dirs()

    # ---- Load data (raises DiscoverySplitMismatch if the known-verified split doesn't hold) ----
    try:
        train_examples, excluded_ids, source = load_training_examples()
    except DiscoverySplitMismatch as e:
        print("STOP: discovery label split assertion failed. Not proceeding with training.")
        print(str(e))
        sys.exit(1)

    golden_examples = load_golden_examples()
    retrieval_tweet_ids, retrieval_thread_ids = load_retrieval_ids()

    print(f"Loaded {len(train_examples)} training examples from {source} "
          f"(excluded: {excluded_ids}).")
    print(f"Loaded {len(golden_examples)} golden evaluation examples.")

    # ---- Hard leakage/boundary checks -- must pass before any training happens ----
    try:
        leak_summary = assert_no_leakage(
            train_examples, golden_examples, retrieval_tweet_ids, retrieval_thread_ids
        )
    except LeakageError as e:
        print("STOP: leakage check failed. Not proceeding with training.")
        print(str(e))
        sys.exit(1)
    print(f"Leakage checks passed: {leak_summary}")

    train_texts = [e["text"] for e in train_examples]
    train_labels = [e["label"] for e in train_examples]
    golden_texts = [e["text"] for e in golden_examples]
    golden_labels = [e["label"] for e in golden_examples]

    # ---- Baseline A: majority class ----
    majority = MajorityClassBaseline().fit(train_labels)
    majority_preds = majority.predict(golden_texts)
    majority_metrics = compute_metrics(golden_labels, majority_preds, config.FROZEN_LABELS)

    # ---- Baseline B: TF-IDF + Logistic Regression ----
    tfidf_logreg = TfidfLogRegBaseline().fit(train_texts, train_labels)
    tfidf_preds = tfidf_logreg.predict(golden_texts)
    tfidf_metrics = compute_metrics(golden_labels, tfidf_preds, config.FROZEN_LABELS)

    # ---- Assemble results ----
    results = dict(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        config=dict(
            baseline_seed=config.BASELINE_SEED,
            tfidf_params=config.TFIDF_PARAMS,
            logreg_params=config.LOGREG_PARAMS,
            frozen_labels=config.FROZEN_LABELS,
        ),
        data=dict(
            training_source=source,
            training_pool="DEVELOPMENT (discovery-phase labels, not final golden annotation)",
            training_n=len(train_examples),
            training_excluded_ids=excluded_ids,
            training_excluded_reason="source label unparseable (see discovery/DISCOVERY_300_AUDIT_REPORT.md); not relabeled, not imputed, not adjudicated",
            training_label_distribution=dict(sorted(
                {l: train_labels.count(l) for l in set(train_labels)}.items())),
            evaluation_source="golden_set/GOLDEN_200_FINAL.csv",
            evaluation_pool="TEST (final human gold labels, evaluation-only)",
            evaluation_n=len(golden_examples),
            leakage_check_summary=leak_summary,
        ),
        majority_class_baseline=dict(
            majority_label=majority.majority_label_,
            training_label_counts=dict(majority.label_counts_),
            metrics=majority_metrics,
        ),
        tfidf_logreg_baseline=dict(
            vocabulary_size=len(tfidf_logreg.vectorizer.vocabulary_),
            metrics=tfidf_metrics,
        ),
    )

    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Wrote {RESULTS_JSON_PATH}")

    write_report(results)
    print(f"Wrote {REPORT_MD_PATH}")

    print("\n=== SUMMARY ===")
    print(f"Majority-class : accuracy={majority_metrics['accuracy']:.3f}  macro_f1={majority_metrics['macro_f1']:.3f}")
    print(f"TF-IDF+LogReg  : accuracy={tfidf_metrics['accuracy']:.3f}  macro_f1={tfidf_metrics['macro_f1']:.3f}")
    return results


def _fmt_pct(x):
    return f"{x*100:.1f}%"


def _per_class_table(metrics):
    lines = ["| Intent | Precision | Recall | F1 | Support |", "|---|---:|---:|---:|---:|"]
    for label, m in metrics["per_class"].items():
        lines.append(f"| {label} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {m['support']} |")
    return "\n".join(lines)


def _confusion_matrix_table(metrics):
    labels = metrics["confusion_matrix"]["labels"]
    matrix = metrics["confusion_matrix"]["matrix"]
    short = {l: l.replace("_", " ")[:14] for l in labels}
    header = "| True \\ Pred | " + " | ".join(short[l] for l in labels) + " |"
    sep = "|---|" + "|".join(["---:"] * len(labels)) + "|"
    lines = [header, sep]
    for i, l in enumerate(labels):
        row = " | ".join(str(v) for v in matrix[i])
        lines.append(f"| **{short[l]}** | {row} |")
    return "\n".join(lines)


def write_report(results):
    d = results["data"]
    mc = results["majority_class_baseline"]
    tf = results["tfidf_logreg_baseline"]
    mc_m, tf_m = mc["metrics"], tf["metrics"]

    content = f"""# Intent Classification Baseline Results

Generated: {results['generated_at']}

## Training / evaluation data

- **Training data**: {d['training_n']} of 300 DEVELOPMENT-pool discovery examples
  (`discovery/HUMAN_REVIEW_labeled.md`, loaded via `{d['training_source']}`).
  **4 excluded**: {', '.join('Ex ' + i for i in d['training_excluded_ids'])} —
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
- **Evaluation data**: {d['evaluation_n']} golden TEST examples
  (`golden_set/GOLDEN_200_FINAL.csv`), used only for scoring. Never used for
  training, fitting, vocabulary construction, or any tuning decision.
- **Leakage checks**: zero tweet_id/thread_id overlap verified, pairwise,
  across training (DEVELOPMENT), evaluation (TEST), and the RETRIEVAL pool.
  Summary: `{d['leakage_check_summary']}`.

### Training label distribution (296 examples)

{chr(10).join(f"- {k}: {v}" for k, v in sorted(d['training_label_distribution'].items(), key=lambda kv: -kv[1]))}

---

## Baseline A — Majority class

Predicts **{mc['majority_label']}** (the most frequent training label,
{mc['training_label_counts'][mc['majority_label']]}/{d['training_n']} of the
training set) for every evaluation example. The floor this milestone is meant
to clear.

| Metric | Value |
|---|---:|
| Accuracy | {_fmt_pct(mc_m['accuracy'])} |
| Macro precision | {mc_m['macro_precision']:.3f} |
| Macro recall | {mc_m['macro_recall']:.3f} |
| Macro F1 | {mc_m['macro_f1']:.3f} |

### Per-class

{_per_class_table(mc_m)}

### Confusion matrix (rows = true label, columns = predicted label)

{_confusion_matrix_table(mc_m)}

---

## Baseline B — TF-IDF + Logistic Regression

TF-IDF vocabulary size: {tf['vocabulary_size']} (fit on the 296 training texts
only). Hyperparameters: `TfidfVectorizer({results['config']['tfidf_params']})`,
`LogisticRegression({results['config']['logreg_params']})` — scikit-learn
defaults plus a fixed seed and a raised `max_iter` for convergence; no grid
search, nothing tuned against golden-200 performance.

| Metric | Value |
|---|---:|
| Accuracy | {_fmt_pct(tf_m['accuracy'])} |
| Macro precision | {tf_m['macro_precision']:.3f} |
| Macro recall | {tf_m['macro_recall']:.3f} |
| Macro F1 | {tf_m['macro_f1']:.3f} |

### Per-class

{_per_class_table(tf_m)}

### Confusion matrix (rows = true label, columns = predicted label)

{_confusion_matrix_table(tf_m)}

---

## Reproducing this report

```bash
python evaluation/run_baselines.py
```

Fixed seed: `BASELINE_SEED = {results['config']['baseline_seed']}` (`config.py`).
No part of the training data, hyperparameters, or evaluation is randomized
beyond this seed; the same code against the same repository state reproduces
identical results. Machine-readable results: `evaluation/results/baseline_results.json`.
"""
    with open(REPORT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    main()
