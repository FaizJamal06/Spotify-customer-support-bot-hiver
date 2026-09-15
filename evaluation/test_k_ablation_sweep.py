"""
Tests for evaluation/run_k_ablation_sweep.py: the gold-isolation example builder and the
integrity-check logic used to verify the full 200x4 sweep before it is declared complete.

No real API calls are made -- run_integrity_checks() is exercised against synthetic record
sets (both passing and deliberately broken), and build_examples()/load_exp1_predicted_intents()
are exercised against the real, already-committed data/results files (frozen, read-only).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluation.run_k_ablation_sweep import (
    K_CONDITIONS,
    build_examples,
    load_exp1_predicted_intents,
    load_golden_rows_raw,
    run_integrity_checks,
)


# ============================================================
# Gold isolation / example construction
# ============================================================

def test_build_examples_covers_all_200_with_no_gold_fields():
    examples = build_examples()
    assert len(examples) == 200
    for ex in examples:
        assert "human_gold_label" not in ex
        assert "human_notes" not in ex
        assert set(ex.keys()) == {"tweet_id", "thread_id", "customer_id", "customer_text", "classified_intent"}


def test_build_examples_intent_matches_exp1_predictions():
    examples = build_examples()
    predicted = load_exp1_predicted_intents()
    for ex in examples:
        assert ex["classified_intent"] == predicted[ex["tweet_id"]]


def test_build_examples_tweet_ids_match_golden_csv():
    examples = build_examples()
    golden_rows = load_golden_rows_raw()
    assert {e["tweet_id"] for e in examples} == {r["tweet_id"] for r in golden_rows}


# ============================================================
# Integrity checks -- synthetic pass case
# ============================================================

def _synthetic_examples(n=5):
    return [
        dict(tweet_id=str(i), thread_id=str(i), customer_id=str(i), customer_text=f"text {i}")
        for i in range(n)
    ]


def _synthetic_records(examples, k_conditions, evidence_count_fn=None):
    """evidence_count_fn(k) -> number of retrieved_evidence items for that k; default k itself."""
    evidence_count_fn = evidence_count_fn or (lambda k: k)
    records = []
    for ex in examples:
        for k in k_conditions:
            records.append(dict(
                tweet_id=ex["tweet_id"], thread_id=ex["thread_id"], customer_id=ex["customer_id"],
                customer_text=ex["customer_text"], classified_intent="APP_TECH_ISSUE", k=k,
                retrieved_evidence=[{"similarity": 0.5}] * evidence_count_fn(k),
                generated_reply="a reply", grounding_notes={}, judge_scores={"relevance": 4}, judge_reasoning="ok",
            ))
    return records


def test_integrity_checks_internal_consistency_passes_at_small_scale():
    """At n=5 (not 200), the fixed '200 examples' / '800 outputs' checks correctly read
    False -- run_integrity_checks() is not hardcoded to always pass. Every OTHER check
    (pairing, no duplicates, k=0 empty evidence, k>0 evidence present, no gold
    contamination) must still read True for this well-formed small set."""
    examples = _synthetic_examples(5)
    records = _synthetic_records(examples, K_CONDITIONS)
    result = run_integrity_checks(examples, records, K_CONDITIONS)

    assert result["all_checks_passed"] is False  # correctly fails only because n=5 != 200
    assert all(result["200_examples_per_k"][str(k)] is False for k in K_CONDITIONS)
    assert result["800_generation_outputs"] is False

    assert all(result["every_example_exactly_once_per_k"][str(k)] for k in K_CONDITIONS)
    assert result["all_four_conditions_paired"] is True
    assert result["k0_has_no_retrieval_evidence"] is True
    assert result["k_gt_0_has_retrieval_evidence"] is True
    assert result["no_gold_field_contamination"] is True


def test_integrity_checks_flags_missing_example_for_one_k():
    examples = _synthetic_examples(5)
    records = _synthetic_records(examples, K_CONDITIONS)
    # drop the k=3 record for the first example
    records = [r for r in records if not (r["tweet_id"] == "0" and r["k"] == 3)]
    result = run_integrity_checks(examples, records, K_CONDITIONS)
    assert result["all_checks_passed"] is False
    assert result["every_example_exactly_once_per_k"]["3"] is False
    assert result["all_four_conditions_paired"] is False


def test_integrity_checks_flags_duplicate_example_for_one_k():
    examples = _synthetic_examples(5)
    records = _synthetic_records(examples, K_CONDITIONS)
    # duplicate the k=0 record for the first example
    dup = dict(records[0])
    records.append(dup)
    result = run_integrity_checks(examples, records, K_CONDITIONS)
    assert result["all_checks_passed"] is False
    assert result["every_example_exactly_once_per_k"]["0"] is False


def test_integrity_checks_flags_nonempty_evidence_at_k_zero():
    examples = _synthetic_examples(5)
    # deliberately give k=0 records 2 pieces of "retrieved evidence" (should never happen)
    records = _synthetic_records(examples, K_CONDITIONS, evidence_count_fn=lambda k: 2 if k == 0 else k)
    result = run_integrity_checks(examples, records, K_CONDITIONS)
    assert result["all_checks_passed"] is False
    assert result["k0_has_no_retrieval_evidence"] is False


def test_integrity_checks_flags_missing_evidence_at_k_greater_than_zero():
    examples = _synthetic_examples(5)
    # k=3 records have only 1 piece of evidence instead of 3 (e.g. a truncated retrieval)
    records = _synthetic_records(examples, K_CONDITIONS, evidence_count_fn=lambda k: 1 if k == 3 else k)
    result = run_integrity_checks(examples, records, K_CONDITIONS)
    assert result["all_checks_passed"] is False
    assert result["k_gt_0_has_retrieval_evidence"] is False


def test_integrity_checks_flags_gold_field_contamination():
    examples = _synthetic_examples(3)
    records = _synthetic_records(examples, K_CONDITIONS)
    records[0]["human_gold_label"] = "ACCOUNT_ACCESS"  # simulated leakage
    result = run_integrity_checks(examples, records, K_CONDITIONS)
    assert result["all_checks_passed"] is False
    assert result["no_gold_field_contamination"] is False


def test_integrity_checks_pass_at_realistic_200x4_scale():
    examples = _synthetic_examples(200)
    records = _synthetic_records(examples, K_CONDITIONS)
    result = run_integrity_checks(examples, records, K_CONDITIONS)
    assert result["all_checks_passed"] is True
    assert result["800_generation_outputs"] is True
    assert result["800_judge_outputs"] is True
    assert all(result["200_examples_per_k"][str(k)] for k in K_CONDITIONS)
