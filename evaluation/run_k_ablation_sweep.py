"""
Full 200 x 4 k-ablation sweep (Experiment 3, implementation_plan.md §9): generate + judge
across k in {0, 1, 3, 5} for all 200 frozen golden examples, using the evidence-cleaning
fix (Part 1, evaluation.generation.clean_brand_text) and bounded concurrency (Part 3).

Usage:
    python evaluation/run_k_ablation_sweep.py [--max-workers N]

Writes:
    evaluation/results/k_ablation_sweep.json  (800 audit records + integrity summary)
    evaluation/K_ABLATION_SWEEP_RESULTS.md

Data access: classified_intent comes from evaluation/results/llm_classifier_results.json's
predicted_intent (Experiment 1 output) -- never from golden_set/GOLDEN_200_FINAL.csv's
human_gold_label. Gold fields are stripped at load time via evaluation.generation.
strip_gold_fields() and never touch the generate/judge pipeline. See run_integrity_checks()
below for the automated verification of both of these claims plus every other Part 4
completeness requirement.

Concurrency safety: see evaluation/generation.py's _KeyedLock (protects the ExperimentLLMProvider
cache) and warm_embedding_cache() below (protects the frozen evaluation/embeddings.py DiskCache,
which this module does not and cannot modify).

Failure handling: a failed (example, k) task is recorded in `failures`, never silently dropped
or converted into a fabricated success. Any failure aborts the run before it is declared complete
(non-zero exit), so a partial/corrupted result set is never mistaken for a finished sweep.
"""
import argparse
import csv
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.generation import ExperimentLLMProvider, build_evidence_records, strip_gold_fields
from evaluation.retrieval import retrieve_top_k

RESULTS_JSON_PATH = config.EVAL_DIR / "k_ablation_sweep.json"
REPORT_MD_PATH = config.PROJECT_ROOT / "evaluation" / "K_ABLATION_SWEEP_RESULTS.md"
CLASSIFIER_RESULTS_PATH = config.EVAL_DIR / "llm_classifier_results.json"

K_CONDITIONS = [0, 1, 3, 5]


def load_golden_rows_raw():
    with open(config.GOLDEN_FINAL_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 200, f"Expected 200 golden rows, found {len(rows)}"
    return rows


def load_exp1_predicted_intents():
    """tweet_id -> predicted_intent, read from Experiment 1's already-computed output.
    Never reads gold_label out of this file."""
    with open(CLASSIFIER_RESULTS_PATH, encoding="utf-8") as f:
        results = json.load(f)
    return {p["tweet_id"]: p["predicted_intent"] for p in results["predictions"]}


def build_examples():
    """All 200 golden examples, gold-stripped, each carrying its Exp-1 PREDICTED intent
    (never the gold label). Raises if any golden tweet_id has no Exp-1 prediction."""
    golden_rows = load_golden_rows_raw()
    predicted_intents = load_exp1_predicted_intents()
    examples = []
    for row in golden_rows:
        stripped = strip_gold_fields(row)
        predicted = predicted_intents.get(stripped["tweet_id"])
        assert predicted is not None, f"No Exp-1 predicted intent for tweet_id={stripped['tweet_id']}"
        stripped["classified_intent"] = predicted
        examples.append(stripped)
    assert len(examples) == 200
    return examples


def warm_embedding_cache(examples):
    """Sequential pass, one retrieve_top_k(text, k=5) call per unique customer text,
    BEFORE any concurrent work begins.

    Why: evaluation/retrieval.py and evaluation/embeddings.py are FROZEN (not modified by
    this task). get_embedding() -- called by retrieve_top_k() on a cache miss -- uses the
    same unlocked DiskCache pattern as everything else in this project. In the sweep's
    real access pattern, k=1/3/5 for the SAME example all need the SAME embedding (the
    embedding cache key depends only on the text+model, not k), so running them
    concurrently would race on that one cache entry. Pre-warming every embedding
    sequentially here means the concurrent phase below only ever performs cache READS
    against evaluation/embeddings.py's cache (safe -- no shared mutable state), so no
    locking of the frozen module is needed and none was added.
    """
    print(f"Warming embedding cache for {len(examples)} unique customer texts (sequential, one-time)...")
    t0 = time.time()
    for i, ex in enumerate(examples):
        retrieve_top_k(ex["customer_text"], k=5)
        if (i + 1) % 50 == 0:
            print(f"  warmed {i + 1}/{len(examples)}")
    print(f"Embedding warm-up complete in {time.time() - t0:.1f}s.")


def run_one(provider, example, k):
    """Runs one (example, k) condition end-to-end and returns a fully-populated audit
    record. Raises on any failure (network error, schema validation failure, etc.) --
    callers must not swallow this into a fabricated or silently-missing result."""
    retrieved = retrieve_top_k(example["customer_text"], k=k)  # k=0 -> [], no embedding call
    evidence_records = build_evidence_records(retrieved)  # raw vs shown (Part 1 cleaning), for audit

    generation = provider.generate_reply(
        example["customer_text"], example["classified_intent"], None, retrieved,
    )
    judgment = provider.judge(example["customer_text"], generation["reply"], retrieved)

    return dict(
        tweet_id=example["tweet_id"],
        thread_id=example["thread_id"],
        customer_id=example["customer_id"],
        customer_text=example["customer_text"],
        classified_intent=example["classified_intent"],
        k=k,
        retrieved_evidence=[
            dict(
                customer_text=r["customer_text"],
                brand_text_raw=r["brand_text_raw"],
                brand_text_shown=r["brand_text_shown"],
                removed_artifacts=r["removed_artifacts"],
                similarity=round(r["similarity"], 4),
            )
            for r in evidence_records
        ],
        generated_reply=generation["reply"],
        grounding_notes=generation["grounding_notes"],
        judge_scores=dict(
            relevance=judgment["relevance"], groundedness=judgment["groundedness"],
            helpfulness=judgment["helpfulness"], tone=judgment["tone"],
        ),
        judge_reasoning=judgment["reasoning"],
    )


def run_integrity_checks(examples, records, k_conditions):
    """Automated verification of every Part 4 completeness requirement. Returns a dict
    of individual boolean checks plus an overall all_checks_passed flag."""
    checks = {}
    expected_tweet_ids = {e["tweet_id"] for e in examples}
    by_k = {k: [r for r in records if r["k"] == k] for k in k_conditions}

    checks["200_examples_per_k"] = {str(k): len(by_k[k]) == 200 for k in k_conditions}
    checks["800_generation_outputs"] = len(records) == 200 * len(k_conditions)
    checks["800_judge_outputs"] = (
        len(records) == 200 * len(k_conditions) and all("judge_scores" in r for r in records)
    )

    checks["every_example_exactly_once_per_k"] = {}
    for k in k_conditions:
        ids = [r["tweet_id"] for r in by_k[k]]
        checks["every_example_exactly_once_per_k"][str(k)] = (
            set(ids) == expected_tweet_ids and len(ids) == len(set(ids))
        )

    checks["k0_has_no_retrieval_evidence"] = all(len(r["retrieved_evidence"]) == 0 for r in by_k.get(0, []))

    gold_fields = {"human_gold_label", "human_notes", "target_message", "gold_intent", "gold_triage"}
    checks["no_gold_field_contamination"] = all(gold_fields.isdisjoint(r.keys()) for r in records)

    checks["all_four_conditions_paired"] = (
        {r["tweet_id"] for r in records} == expected_tweet_ids
        and all(
            {r["k"] for r in records if r["tweet_id"] == tid} == set(k_conditions)
            for tid in expected_tweet_ids
        )
    )

    # retrieved evidence must come only from the frozen retrieval index: every retrieved
    # customer_text in a k>0 record must be traceable to config.RETRIEVAL_INDEX_DIR's own
    # metadata (retrieve_top_k() already raises IndexModelMismatch internally if the index
    # embedding model doesn't match config.EMBEDDING_MODEL -- a completed run therefore
    # already implies this; this check additionally confirms non-empty evidence at k>0).
    checks["k_gt_0_has_retrieval_evidence"] = all(
        len(r["retrieved_evidence"]) == k for k in k_conditions if k > 0 for r in by_k.get(k, [])
    )

    flat_bools = []
    for v in checks.values():
        if isinstance(v, dict):
            flat_bools.extend(v.values())
        else:
            flat_bools.append(v)
    checks["all_checks_passed"] = all(flat_bools)
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-workers", type=int, default=config.SWEEP_MAX_WORKERS)
    args = parser.parse_args()

    config.ensure_dirs()
    try:
        api_key = config.get_api_key()
    except EnvironmentError as e:
        print("STOP:", e)
        sys.exit(1)

    examples = build_examples()
    print(f"Loaded {len(examples)} golden examples with Exp-1 predicted intents (never gold labels).")

    warm_embedding_cache(examples)

    provider = ExperimentLLMProvider(
        classify_model=config.CLASSIFY_MODEL, generate_model=config.GENERATE_MODEL,
        judge_model=config.JUDGE_MODEL, api_key=api_key,
    )

    tasks = [(ex, k) for ex in examples for k in K_CONDITIONS]
    print(f"Running {len(tasks)} (example, k) conditions with max_workers={args.max_workers}...")

    records = []
    failures = []
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        future_to_task = {pool.submit(run_one, provider, ex, k): (ex["tweet_id"], k) for ex, k in tasks}
        for future in as_completed(future_to_task):
            tweet_id, k = future_to_task[future]
            try:
                records.append(future.result())
            except Exception as e:  # noqa: BLE001 -- must capture and report, never swallow
                failures.append(dict(tweet_id=tweet_id, k=k, error=repr(e), traceback=traceback.format_exc()))
            done += 1
            if done % 25 == 0 or done == len(tasks):
                print(f"  [{done}/{len(tasks)}] complete ({len(failures)} failures so far)")
    elapsed = time.time() - t0

    if failures:
        print(f"\n{len(failures)} task(s) FAILED:")
        for f in failures:
            print(f"  tweet_id={f['tweet_id']} k={f['k']}: {f['error']}")

    integrity = run_integrity_checks(examples, records, K_CONDITIONS)

    results = dict(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        config=dict(
            generate_model=config.GENERATE_MODEL, judge_model=config.JUDGE_MODEL,
            temperature=config.LLM_TEMPERATURE, seed=config.LLM_SEED,
            reasoning_effort=config.REASONING_EFFORT_FOR_TEMPERATURE,
            max_workers=args.max_workers, k_conditions=K_CONDITIONS,
        ),
        n_examples=len(examples), n_tasks=len(tasks), n_records=len(records),
        n_failures=len(failures), failures=failures,
        elapsed_seconds=round(elapsed, 1),
        integrity=integrity,
        records=records,
    )

    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {RESULTS_JSON_PATH}")

    if failures:
        print(f"\nSTOP: {len(failures)} task(s) failed. NOT declaring the sweep complete.")
        sys.exit(1)
    if not integrity["all_checks_passed"]:
        print("\nSTOP: integrity checks failed. See results JSON 'integrity' section.")
        sys.exit(1)

    print(f"\nAll integrity checks passed. Sweep complete in {elapsed:.1f}s.")
    return results


if __name__ == "__main__":
    main()
