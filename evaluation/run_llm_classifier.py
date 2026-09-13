"""
LLM intent classifier milestone: gpt-5.4-mini few-shot classification,
evaluated on the 200 golden TEST examples, compared against the completed
Majority and TF-IDF+LogReg baselines.

Usage (one command reproduces everything -- cached after first run):
    python evaluation/run_llm_classifier.py

Writes:
    evaluation/results/llm_classifier_results.json
    evaluation/LLM_CLASSIFIER_RESULTS.md

Does not modify discovery/DISCOVERY_300_AUDIT.csv, discovery/HUMAN_REVIEW_labeled.md,
golden_set/GOLDEN_200_FINAL.csv, discovery/TAXONOMY_REVIEW_GUIDE.md, or any of the
frozen baseline-milestone files. Does not train/tune anything against golden-200 --
the few-shot set and prompt are fixed before any golden example is scored.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.data_loading import load_golden_examples
from evaluation.fewshot_selection import (
    select_fewshot_demonstrations, assert_fewshot_no_golden_leakage,
    FewShotSelectionError,
)
from evaluation.leakage_checks import LeakageError
from evaluation.llm_classifier import (
    LLMProvider, load_intent_definitions, render_fewshot_block,
    INTENT_CLASSIFIER_PROMPT_VERSION,
)
from evaluation.metrics import compute_metrics

RESULTS_JSON_PATH = config.EVAL_DIR / "llm_classifier_results.json"
REPORT_MD_PATH = config.PROJECT_ROOT / "evaluation" / "LLM_CLASSIFIER_RESULTS.md"
BASELINE_RESULTS_PATH = config.EVAL_DIR / "baseline_results.json"

LIMITATION_STATEMENT = (
    "Few-shot demonstrations are restricted to audit-confirmed MATCH-status discovery "
    "examples, which removes known guide-inconsistent labels from the demonstration set. "
    "This does not fully equalize demonstration quality with the golden-200 evaluation "
    "set: these labels came from a single-pass discovery-phase annotation process, not "
    "the golden set's blind-workbook-plus-AI-prelabel-plus-human-adjudication process. "
    "The few-shot demonstrations reflect discovery-phase annotation rigor, not "
    "golden-set-grade rigor."
)


def main():
    config.ensure_dirs()

    # ---- API key check (hard stop, no workaround) ----
    try:
        api_key = config.get_api_key()
    except EnvironmentError as e:
        print("STOP:", e)
        sys.exit(1)

    # ---- Few-shot demonstration selection (hard stop if any intent has <3 MATCH rows) ----
    try:
        demonstrations, selection_log = select_fewshot_demonstrations()
    except FewShotSelectionError as e:
        print("STOP: few-shot selection failed.")
        print(str(e))
        sys.exit(1)

    total_demos = sum(len(v) for v in selection_log.values())
    print(f"Selected {total_demos} few-shot demonstrations across "
          f"{len(selection_log)} intents (MATCH-status only, deterministic).")
    for label, ids in selection_log.items():
        print(f"  {label}: {len(ids)} -> {ids}")

    golden_examples = load_golden_examples()
    print(f"Loaded {len(golden_examples)} golden evaluation examples.")

    # ---- Hard leakage check: demo IDs vs golden IDs ----
    try:
        leak_summary = assert_fewshot_no_golden_leakage(demonstrations, golden_examples)
    except LeakageError as e:
        print("STOP: leakage check failed.")
        print(str(e))
        sys.exit(1)
    print(f"Leakage check passed: {leak_summary}")

    # ---- Build fixed prompt components (same for every one of the 200 queries) ----
    intent_definitions = load_intent_definitions()
    fewshot_block = render_fewshot_block(demonstrations)

    provider = LLMProvider(
        classify_model=config.CLASSIFY_MODEL,
        generate_model=config.GENERATE_MODEL,
        judge_model=config.JUDGE_MODEL,
        api_key=api_key,
    )

    # ---- Classify all 200 golden examples (cached -- cheap to re-run) ----
    y_true, y_pred, predictions = [], [], []
    t0 = time.time()
    for i, ex in enumerate(golden_examples):
        result = provider.classify(ex["text"], fewshot_block, intent_definitions)
        y_true.append(ex["label"])
        y_pred.append(result["intent"])
        predictions.append(dict(
            tweet_id=ex["tweet_id"], gold_label=ex["label"],
            predicted_intent=result["intent"], confidence=result["confidence"],
            reasoning=result["reasoning"],
        ))
        if (i + 1) % 50 == 0 or (i + 1) == len(golden_examples):
            print(f"  classified {i + 1}/{len(golden_examples)}")
    elapsed = time.time() - t0
    print(f"Classification complete in {elapsed:.1f}s.")

    llm_metrics = compute_metrics(y_true, y_pred, config.FROZEN_LABELS)

    # ---- Read (not recompute) the existing baseline results for the 3-way comparison ----
    with open(BASELINE_RESULTS_PATH, encoding="utf-8") as f:
        baseline_results = json.load(f)
    majority_metrics = baseline_results["majority_class_baseline"]["metrics"]
    tfidf_metrics = baseline_results["tfidf_logreg_baseline"]["metrics"]

    results = dict(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        prompt_version=INTENT_CLASSIFIER_PROMPT_VERSION,
        config=dict(
            classify_model=config.CLASSIFY_MODEL,
            temperature=config.LLM_TEMPERATURE,
            seed=config.LLM_SEED,
            determinism_mechanism="temperature=0 and seed (both empirically verified supported "
                                   "by gpt-5.4-mini at its default reasoning_effort='none'); "
                                   "response_format is a strict JSON schema constraining "
                                   "'intent' to the 8 frozen labels",
            frozen_labels=config.FROZEN_LABELS,
        ),
        fewshot=dict(
            source="discovery/DISCOVERY_300_AUDIT.csv existing_human_label, status == MATCH only",
            selection_method="sorted by example_id ascending per intent, deterministic, "
                              f"min={config.FEWSHOT_MIN_PER_INTENT} max={config.FEWSHOT_MAX_PER_INTENT}",
            total_demonstrations=total_demos,
            selected_example_ids_by_intent=selection_log,
            leakage_check_summary=leak_summary,
        ),
        evaluation=dict(
            source="golden_set/GOLDEN_200_FINAL.csv",
            pool="TEST (evaluation-only)",
            n=len(golden_examples),
            elapsed_seconds=round(elapsed, 1),
        ),
        llm_classifier=dict(metrics=llm_metrics),
        comparison=dict(
            majority_class=dict(
                accuracy=majority_metrics["accuracy"], macro_precision=majority_metrics["macro_precision"],
                macro_recall=majority_metrics["macro_recall"], macro_f1=majority_metrics["macro_f1"],
            ),
            tfidf_logreg=dict(
                accuracy=tfidf_metrics["accuracy"], macro_precision=tfidf_metrics["macro_precision"],
                macro_recall=tfidf_metrics["macro_recall"], macro_f1=tfidf_metrics["macro_f1"],
            ),
            llm_classifier=dict(
                accuracy=llm_metrics["accuracy"], macro_precision=llm_metrics["macro_precision"],
                macro_recall=llm_metrics["macro_recall"], macro_f1=llm_metrics["macro_f1"],
            ),
        ),
        limitation_statement=LIMITATION_STATEMENT,
        predictions=predictions,
    )

    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Wrote {RESULTS_JSON_PATH}")

    write_report(results)
    print(f"Wrote {REPORT_MD_PATH}")

    print("\n=== SUMMARY ===")
    print(f"Majority-class : accuracy={majority_metrics['accuracy']:.3f}  macro_f1={majority_metrics['macro_f1']:.3f}")
    print(f"TF-IDF+LogReg  : accuracy={tfidf_metrics['accuracy']:.3f}  macro_f1={tfidf_metrics['macro_f1']:.3f}")
    print(f"LLM ({config.CLASSIFY_MODEL}): accuracy={llm_metrics['accuracy']:.3f}  macro_f1={llm_metrics['macro_f1']:.3f}")
    return results


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
    fs = results["fewshot"]
    llm_m = results["llm_classifier"]["metrics"]
    comp = results["comparison"]

    demo_lines = []
    for label, ids in fs["selected_example_ids_by_intent"].items():
        demo_lines.append(f"- **{label}** ({len(ids)}): " + ", ".join(f"Ex {i}" for i in ids))

    content = f"""# LLM Intent Classifier Results

Generated: {results['generated_at']}
Prompt version: `{results['prompt_version']}`

## Few-shot demonstration source and selection method

- **Source**: {fs['source']}.
- **Selection method**: {fs['selection_method']}.
- **Total demonstrations**: {fs['total_demonstrations']} (fixed for the entire evaluation run -- the same set is used for every one of the {results['evaluation']['n']} golden queries; never varied per query, never selected/tuned/validated using the golden-200 examples).
- **Leakage check**: zero tweet_id/thread_id overlap between demonstration IDs and golden-set IDs, verified explicitly. Summary: `{fs['leakage_check_summary']}`.

### Exact selected example_ids by intent

{chr(10).join(demo_lines)}

## Model / configuration

| Setting | Value |
|---|---|
| Model | `{results['config']['classify_model']}` |
| Temperature | {results['config']['temperature']} |
| Seed | {results['config']['seed']} |
| Determinism mechanism | {results['config']['determinism_mechanism']} |
| Output schema | Strict JSON schema (`response_format`), `intent` constrained to the 8 frozen labels by the API itself |
| Intent definitions | Extracted verbatim from `discovery/TAXONOMY_REVIEW_GUIDE.md` at run time (sections 1-8) -- not hand-summarized |
| Few-shot content | Customer text + frozen label only (no reasoning, no boundary tags, no golden-set content) |
| Caching | Disk-cached by hash of (model, prompt version, messages, temperature, seed) -- reruns are free |

## Evaluation

- **Data**: {results['evaluation']['source']} ({results['evaluation']['pool']}), n={results['evaluation']['n']}.
- **Wall time**: {results['evaluation']['elapsed_seconds']}s for this run (cached calls are near-instant on reruns).

### Full metrics

| Metric | Value |
|---|---:|
| Accuracy | {llm_m['accuracy']*100:.1f}% |
| Macro precision | {llm_m['macro_precision']:.3f} |
| Macro recall | {llm_m['macro_recall']:.3f} |
| Macro F1 | {llm_m['macro_f1']:.3f} |

### Per-class

{_per_class_table(llm_m)}

### Confusion matrix (rows = true label, columns = predicted label)

{_confusion_matrix_table(llm_m)}

## Three-way comparison

| Classifier | Accuracy | Macro Precision | Macro Recall | Macro F1 |
|---|---:|---:|---:|---:|
| Majority class | {comp['majority_class']['accuracy']*100:.1f}% | {comp['majority_class']['macro_precision']:.3f} | {comp['majority_class']['macro_recall']:.3f} | {comp['majority_class']['macro_f1']:.3f} |
| TF-IDF + LogReg | {comp['tfidf_logreg']['accuracy']*100:.1f}% | {comp['tfidf_logreg']['macro_precision']:.3f} | {comp['tfidf_logreg']['macro_recall']:.3f} | {comp['tfidf_logreg']['macro_f1']:.3f} |
| LLM ({results['config']['classify_model']}) | {comp['llm_classifier']['accuracy']*100:.1f}% | {comp['llm_classifier']['macro_precision']:.3f} | {comp['llm_classifier']['macro_recall']:.3f} | {comp['llm_classifier']['macro_f1']:.3f} |

(Majority-class and TF-IDF+LogReg figures are read directly from `evaluation/results/baseline_results.json`, not recomputed.)

## Limitation

{results['limitation_statement']}

## Reproducing this report

```bash
python evaluation/run_llm_classifier.py
```

Requires `OPENAI_API_KEY` to be set. Cached responses under `cache/` make
reruns free and byte-identical unless the prompt version, model, or
demonstration set changes.
"""
    with open(REPORT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    main()
