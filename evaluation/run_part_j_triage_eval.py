"""
Part J: the one-time, held-out evaluation of the triage policy
(evaluation/triage.py's apply_triage_rules(), used EXACTLY AS-IS -- not edited by
this script) against golden_set/TRIAGE_ANNOTATION_40.csv's human triage_decision
column. This is the FIRST script in this project permitted to read that column
(and escalation_reason) -- for EVALUATION ONLY. Nothing here feeds back into
evaluation/triage.py: no rule, regex, heuristic, or default (including
TIER2_ACCOUNT_ACCESS_RULE_ENABLED's shipped default) is changed as a result of
what this script finds.

Zero new API/embedding calls: every input is already local --
golden_set/TRIAGE_ANNOTATION_40.csv (human labels + human_gold_label, both
already on disk), evaluation/results/llm_classifier_results.json (Experiment 1's
already-cached predicted_intent per tweet_id), and apply_triage_rules() itself
(pure Python, no I/O). No embedding, retrieval, or LLM call of any kind is made.

Four conditions (2 arms x 2 intent sources), all computed from the above:
  - Arm A: TIER2_ACCOUNT_ACCESS_RULE_ENABLED=False (current shipped default)
  - Arm B: TIER2_ACCOUNT_ACCESS_RULE_ENABLED=True
  - Intent source "gold": human_gold_label (idealized -- assumes a perfect classifier)
  - Intent source "llm": Experiment 1's actual predicted_intent (the real,
    end-to-end pipeline, including classifier error)
The arm is toggled via monkeypatch-style attribute set on the evaluation.triage
module AT CALL TIME in this script only -- evaluation/triage.py's own file on
disk, including its default value for TIER2_ACCOUNT_ACCESS_RULE_ENABLED, is
never modified.

Run: python evaluation/run_part_j_triage_eval.py
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
import evaluation.triage as triage_mod
from evaluation.triage import apply_triage_rules, check_tier1

TRIAGE_40_CSV_PATH = config.GOLDEN_DIR / "TRIAGE_ANNOTATION_40.csv"
LLM_CLASSIFIER_RESULTS_PATH = config.EVAL_DIR / "llm_classifier_results.json"
PART_J_OUTPUT_PATH = config.EVAL_DIR / "part_j_triage_eval.json"

ARMS = [("Arm A (shipped default, rule OFF)", False), ("Arm B (rule ON)", True)]
INTENT_SOURCES = ["llm", "gold"]  # order matches "headline first" emphasis (llm = realistic pipeline)


def load_triage_40_rows():
    with open(TRIAGE_40_CSV_PATH, encoding="utf-8") as f:
        lines = f.readlines()
    data_lines = [ln for ln in lines if not ln.startswith("#")]
    rows = list(csv.DictReader(data_lines))
    assert len(rows) == 40, f"Expected 40 rows in {TRIAGE_40_CSV_PATH}, found {len(rows)}"
    for r in rows:
        assert r["triage_decision"] in ("AUTO_HANDLE", "HUMAN_ESCALATION"), (
            f"{r['example_id']}: unexpected triage_decision {r['triage_decision']!r}"
        )
    return rows


def load_llm_predicted_intents():
    with open(LLM_CLASSIFIER_RESULTS_PATH, encoding="utf-8") as f:
        results = json.load(f)
    return {p["tweet_id"]: p["predicted_intent"] for p in results["predictions"]}


def build_examples():
    """Joins the 40 human-annotated rows with their Exp-1 LLM-predicted intent.
    Returns a list of dicts: example_id, tweet_id, customer_text, gold_intent,
    llm_intent, human_decision, human_reason."""
    rows = load_triage_40_rows()
    predicted_by_tweet = load_llm_predicted_intents()
    examples = []
    for r in rows:
        tweet_id = r["tweet_id"]
        assert tweet_id in predicted_by_tweet, f"No Exp-1 prediction for tweet_id={tweet_id}"
        examples.append(dict(
            example_id=r["example_id"],
            tweet_id=tweet_id,
            customer_text=r["target_message"],
            gold_intent=r["human_gold_label"],
            llm_intent=predicted_by_tweet[tweet_id],
            human_decision=r["triage_decision"],
            human_reason=r["escalation_reason"],
        ))
    return examples


def run_condition(examples, enabled, intent_source):
    """Runs apply_triage_rules() for all 40 examples under one (arm, intent_source)
    condition. Toggles evaluation.triage.TIER2_ACCOUNT_ACCESS_RULE_ENABLED at call
    time only (restored immediately after) -- the module's on-disk default is
    never changed by this script."""
    original = triage_mod.TIER2_ACCOUNT_ACCESS_RULE_ENABLED
    triage_mod.TIER2_ACCOUNT_ACCESS_RULE_ENABLED = enabled
    try:
        records = []
        for ex in examples:
            intent = ex["gold_intent"] if intent_source == "gold" else ex["llm_intent"]
            out = apply_triage_rules(ex["customer_text"], intent, confidence=None)
            records.append(dict(
                example_id=ex["example_id"], tweet_id=ex["tweet_id"],
                customer_text=ex["customer_text"], intent_used=intent,
                human_decision=ex["human_decision"], human_reason=ex["human_reason"],
                system_decision=out["decision"], system_reason=out["reason"], system_tier=out["tier"],
                system_rule_id=out["rule_id"],
            ))
        return records
    finally:
        triage_mod.TIER2_ACCOUNT_ACCESS_RULE_ENABLED = original


def summarize(records):
    n = len(records)
    true_auto = sum(1 for r in records if r["system_decision"] == "AUTO_HANDLE" and r["human_decision"] == "AUTO_HANDLE")
    true_escalate = sum(1 for r in records if r["system_decision"] == "HUMAN_ESCALATION" and r["human_decision"] == "HUMAN_ESCALATION")
    false_auto = sum(1 for r in records if r["system_decision"] == "AUTO_HANDLE" and r["human_decision"] == "HUMAN_ESCALATION")
    false_escalate = sum(1 for r in records if r["system_decision"] == "HUMAN_ESCALATION" and r["human_decision"] == "AUTO_HANDLE")
    assert true_auto + true_escalate + false_auto + false_escalate == n

    n_human_escalate = sum(1 for r in records if r["human_decision"] == "HUMAN_ESCALATION")
    n_human_auto = n - n_human_escalate

    return dict(
        n=n,
        agreement_count=true_auto + true_escalate, agreement_rate=(true_auto + true_escalate) / n,
        false_auto_handle_count=false_auto, false_auto_handle_rate_of_n=false_auto / n,
        false_auto_handle_rate_of_human_escalate=(false_auto / n_human_escalate) if n_human_escalate else float("nan"),
        false_escalate_count=false_escalate, false_escalate_rate_of_n=false_escalate / n,
        false_escalate_rate_of_human_auto=(false_escalate / n_human_auto) if n_human_auto else float("nan"),
        true_auto_handle_count=true_auto, true_escalate_count=true_escalate,
        n_human_escalate=n_human_escalate, n_human_auto=n_human_auto,
        disagreements=[r for r in records if r["system_decision"] != r["human_decision"]],
    )


def effective_arm_comparison_size(examples, intent_source):
    """Counts, for the given intent_source, how many of the 40 examples are (a)
    classified ACCOUNT_ACCESS under that intent source AND (b) do NOT already trip
    a Tier-1 rule (since Tier 1 runs before Tier 2B and would make the ENABLED
    toggle irrelevant for that example either way)."""
    eligible = []
    for ex in examples:
        intent = ex["gold_intent"] if intent_source == "gold" else ex["llm_intent"]
        if intent != "ACCOUNT_ACCESS":
            continue
        tier1_result = check_tier1(ex["customer_text"], intent)
        if tier1_result is not None:
            continue  # Tier 1 already decides this example; the toggle can't matter
        eligible.append(ex["example_id"])
    return eligible


def main():
    examples = build_examples()
    print(f"Loaded {len(examples)} human-annotated examples with Exp-1 LLM-predicted intent joined in.")

    results = {}
    for arm_label, enabled in ARMS:
        for intent_source in INTENT_SOURCES:
            key = f"{'ArmA' if not enabled else 'ArmB'}_{intent_source}"
            records = run_condition(examples, enabled, intent_source)
            results[key] = dict(arm_label=arm_label, enabled=enabled, intent_source=intent_source,
                                 summary=summarize(records))

    print("\n=== HEADLINE: Arm A (shipped default), LLM-predicted intent ===")
    hs = results["ArmA_llm"]["summary"]
    print(f"n={hs['n']}  agreement={hs['agreement_count']}/{hs['n']} ({hs['agreement_rate']:.1%})")
    print(f"false_auto_handle (DANGEROUS)={hs['false_auto_handle_count']}/{hs['n']} "
          f"({hs['false_auto_handle_rate_of_n']:.1%} of all 40; "
          f"{hs['false_auto_handle_rate_of_human_escalate']:.1%} of the {hs['n_human_escalate']} human-ESCALATE cases)")
    print(f"false_escalate (inefficiency)={hs['false_escalate_count']}/{hs['n']} ({hs['false_escalate_rate_of_n']:.1%})")

    print("\n=== Full 4-condition table ===")
    print(f"{'condition':<20}{'agree':>10}{'false_auto':>12}{'false_escalate':>16}")
    for key, r in results.items():
        s = r["summary"]
        print(f"{key:<20}{s['agreement_rate']:>10.1%}{s['false_auto_handle_rate_of_n']:>12.1%}{s['false_escalate_rate_of_n']:>16.1%}")

    print("\n=== Effective Arm A/B comparison size ===")
    eff = {}
    for intent_source in INTENT_SOURCES:
        eligible = effective_arm_comparison_size(examples, intent_source)
        eff[intent_source] = eligible
        print(f"  intent_source={intent_source}: {len(eligible)} example(s) actually reach Tier 2B as ACCOUNT_ACCESS: {eligible}")

    config.ensure_dirs()
    with open(PART_J_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dict(
            n_examples=len(examples),
            conditions=results,
            effective_arm_comparison_size=eff,
        ), f, indent=2)
    print(f"\nWrote {PART_J_OUTPUT_PATH}")
    return results, eff


if __name__ == "__main__":
    main()
