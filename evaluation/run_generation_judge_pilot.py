"""
Pilot run for Experiment 3 (retrieval k-ablation, implementation_plan.md §9): the
generate -> judge pipeline (evaluation/generation.py) across all four k conditions
(0, 1, 3, 5) on a small, hand-readable pilot sample, to sanity-check the pipeline
BEFORE committing to the full 200-example x 4-condition sweep.

This script deliberately does NOT run the full sweep, does NOT do the 20-example
manual-retrieval-inspection data prep, and does NOT compute the paired Wilcoxon
comparison -- those are separate, later steps that need a human look at the pilot
output first.

Pilot sample selection (deterministic, no randomness):
  - Reuses evaluation/results/llm_classifier_results.json's existing predictions
    (Experiment 1's output) for the CLASSIFIED intent of each golden example --
    classify() is not re-invoked here. This is exactly the "classified intent from
    Exp 1" input Experiment 3 is specified to use (implementation_plan.md §3).
  - For each of the 8 frozen intents, picks the lowest-tweet_id golden example whose
    Exp-1 PREDICTED intent equals that label (never the gold label), giving 8
    examples spanning all 8 intents with a fixed, reproducible selection rule.
  - Gold fields (human_gold_label, human_notes) are stripped immediately on load via
    evaluation.generation.strip_gold_fields() and never touch the generation/judge
    pipeline -- see that module's docstring for the full data-access rule.

Usage:
    python evaluation/run_generation_judge_pilot.py

Writes:
    evaluation/results/generation_judge_pilot.json
    evaluation/GENERATION_JUDGE_PILOT_RESULTS.md
"""
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.generation import ExperimentLLMProvider, strip_gold_fields
from evaluation.retrieval import retrieve_top_k

RESULTS_JSON_PATH = config.EVAL_DIR / "generation_judge_pilot.json"
REPORT_MD_PATH = config.PROJECT_ROOT / "evaluation" / "GENERATION_JUDGE_PILOT_RESULTS.md"
CLASSIFIER_RESULTS_PATH = config.EVAL_DIR / "llm_classifier_results.json"

K_CONDITIONS = [0, 1, 3, 5]


def load_golden_rows_raw():
    with open(config.GOLDEN_FINAL_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 200, f"Expected 200 golden rows, found {len(rows)}"
    return rows


def load_exp1_predicted_intents():
    """tweet_id -> predicted_intent, read from Experiment 1's already-computed output.
    Never reads gold_label out of this file into the returned mapping."""
    with open(CLASSIFIER_RESULTS_PATH, encoding="utf-8") as f:
        results = json.load(f)
    return {p["tweet_id"]: p["predicted_intent"] for p in results["predictions"]}


def select_pilot_examples(golden_rows, predicted_intents):
    """Deterministic: for each of the 8 frozen labels, the lowest-tweet_id golden row
    whose Experiment-1 PREDICTED intent equals that label. Returns a list of dicts
    (already gold-stripped via strip_gold_fields) each carrying its classified_intent.
    Raises AssertionError if any intent has zero predicted examples (would make the
    pilot's intent coverage silently incomplete).
    """
    by_intent = {label: [] for label in config.FROZEN_LABELS}
    for row in golden_rows:
        predicted = predicted_intents.get(row["tweet_id"])
        if predicted in by_intent:
            by_intent[predicted].append(row)

    missing = [label for label, rows in by_intent.items() if not rows]
    assert not missing, f"No golden example has predicted_intent in {missing}; cannot cover all intents."

    selected = []
    for label in config.FROZEN_LABELS:
        rows_for_label = sorted(by_intent[label], key=lambda r: int(r["tweet_id"]))
        chosen_row = rows_for_label[0]
        example = strip_gold_fields(chosen_row)
        example["classified_intent"] = label
        selected.append(example)
    return selected


def run_pilot():
    config.ensure_dirs()
    try:
        api_key = config.get_api_key()
    except EnvironmentError as e:
        print("STOP:", e)
        sys.exit(1)

    golden_rows = load_golden_rows_raw()
    predicted_intents = load_exp1_predicted_intents()
    pilot_examples = select_pilot_examples(golden_rows, predicted_intents)

    print(f"Pilot sample: {len(pilot_examples)} examples, one per frozen intent "
          f"(classified via cached Experiment-1 output, never the gold label).")
    for ex in pilot_examples:
        print(f"  tweet_id={ex['tweet_id']}  intent={ex['classified_intent']}  "
              f"text={ex['customer_text'][:60]!r}")

    provider = ExperimentLLMProvider(
        classify_model=config.CLASSIFY_MODEL,
        generate_model=config.GENERATE_MODEL,
        judge_model=config.JUDGE_MODEL,
        api_key=api_key,
    )

    records = []
    t0 = time.time()
    total_calls = len(pilot_examples) * len(K_CONDITIONS)
    done = 0
    for ex in pilot_examples:
        for k in K_CONDITIONS:
            retrieved = retrieve_top_k(ex["customer_text"], k=k)  # k=0 -> [] , no embedding call
            generation = provider.generate_reply(
                ex["customer_text"], ex["classified_intent"], None, retrieved,
            )
            judgment = provider.judge(ex["customer_text"], generation["reply"], retrieved)

            records.append(dict(
                tweet_id=ex["tweet_id"],
                classified_intent=ex["classified_intent"],
                k=k,
                customer_text=ex["customer_text"],
                retrieved_evidence=[
                    dict(customer=c, reply=r, similarity=round(s, 4))
                    for c, r, s, _m in retrieved
                ],
                generated_reply=generation["reply"],
                grounding_notes=generation["grounding_notes"],
                judge_scores=dict(
                    relevance=judgment["relevance"],
                    groundedness=judgment["groundedness"],
                    helpfulness=judgment["helpfulness"],
                    tone=judgment["tone"],
                ),
                judge_reasoning=judgment["reasoning"],
            ))
            done += 1
            print(f"  [{done}/{total_calls}] tweet_id={ex['tweet_id']} k={k} done")
    elapsed = time.time() - t0

    results = dict(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        generator_prompt_version="v1",
        judge_prompt_version="v1",
        config=dict(
            generate_model=config.GENERATE_MODEL,
            judge_model=config.JUDGE_MODEL,
            temperature=config.LLM_TEMPERATURE,
            seed=config.LLM_SEED,
            reasoning_effort=config.REASONING_EFFORT_FOR_TEMPERATURE,
            k_conditions=K_CONDITIONS,
        ),
        pilot_size=len(pilot_examples),
        n_records=len(records),
        elapsed_seconds=round(elapsed, 1),
        leakage_note=(
            "Gold fields (human_gold_label, human_notes) were stripped at load time via "
            "evaluation.generation.strip_gold_fields() and never passed into generate_reply() "
            "or judge(). Classified intent came from evaluation/results/llm_classifier_results.json "
            "predicted_intent (Experiment 1 output), not from the gold column."
        ),
        records=records,
    )

    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {RESULTS_JSON_PATH}")

    write_report(results)
    print(f"Wrote {REPORT_MD_PATH}")
    return results


def _mean_scores_by_k(records):
    from collections import defaultdict
    sums = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(int)
    for r in records:
        counts[r["k"]] += 1
        for dim, val in r["judge_scores"].items():
            sums[r["k"]][dim] += val
    out = {}
    for k in sorted(counts):
        out[k] = {dim: sums[k][dim] / counts[k] for dim in ("relevance", "groundedness", "helpfulness", "tone")}
    return out


def write_report(results):
    records = results["records"]
    means = _mean_scores_by_k(records)

    lines = [
        "# Generation + Judge Pilot Results (Experiment 3 pilot)",
        "",
        f"Generated: {results['generated_at']}",
        f"Pilot size: {results['pilot_size']} golden examples x {len(results['config']['k_conditions'])} "
        f"k-conditions = {results['n_records']} generate+judge pairs.",
        f"Wall time: {results['elapsed_seconds']}s.",
        "",
        "## Models / config",
        "",
        f"| Setting | Value |",
        f"|---|---|",
        f"| GENERATE_MODEL | `{results['config']['generate_model']}` |",
        f"| JUDGE_MODEL | `{results['config']['judge_model']}` |",
        f"| temperature | {results['config']['temperature']} |",
        f"| seed | {results['config']['seed']} |",
        f"| reasoning_effort | {results['config']['reasoning_effort']} |",
        f"| k conditions | {results['config']['k_conditions']} |",
        "",
        "## Data access",
        "",
        results["leakage_note"],
        "",
        "## Mean judge scores per k (pilot only -- n is far too small to draw a conclusion; "
        "see the full-run estimate in the milestone report for the real comparison)",
        "",
        "| k | Relevance | Groundedness | Helpfulness | Tone |",
        "|---|---:|---:|---:|---:|",
    ]
    for k, dims in means.items():
        lines.append(
            f"| {k} | {dims['relevance']:.2f} | {dims['groundedness']:.2f} | "
            f"{dims['helpfulness']:.2f} | {dims['tone']:.2f} |"
        )

    lines += ["", "## Full pilot output", ""]
    for r in records:
        lines.append(f"### tweet_id={r['tweet_id']}  intent={r['classified_intent']}  k={r['k']}")
        lines.append("")
        lines.append(f"**Customer message:** {r['customer_text']}")
        lines.append("")
        if r["retrieved_evidence"]:
            lines.append("**Retrieved evidence:**")
            for i, ev in enumerate(r["retrieved_evidence"], start=1):
                lines.append(f"{i}. (sim={ev['similarity']}) Customer: {ev['customer']}")
                lines.append(f"   Spotify support: {ev['reply']}")
        else:
            lines.append("**Retrieved evidence:** none (k=0)")
        lines.append("")
        lines.append(f"**Generated reply:** {r['generated_reply']}")
        lines.append("")
        gn = r["grounding_notes"]
        lines.append(f"**Grounding notes:**")
        lines.append(f"- grounded_in_evidence: {gn['grounded_in_evidence']}")
        lines.append(f"- grounded_in_customer_message: {gn['grounded_in_customer_message']}")
        lines.append(f"- unsupported_or_generic: {gn['unsupported_or_generic']}")
        lines.append("")
        js = r["judge_scores"]
        lines.append(
            f"**Judge scores:** relevance={js['relevance']} groundedness={js['groundedness']} "
            f"helpfulness={js['helpfulness']} tone={js['tone']}"
        )
        lines.append(f"**Judge reasoning:** {r['judge_reasoning']}")
        lines.append("")

    with open(REPORT_MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    run_pilot()
