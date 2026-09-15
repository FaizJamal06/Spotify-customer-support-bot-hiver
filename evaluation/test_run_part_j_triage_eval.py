"""
Tests for evaluation/run_part_j_triage_eval.py's four-condition computation logic.

Uses a small SYNTHETIC set of examples (never golden_set/TRIAGE_ANNOTATION_40.csv)
to keep this fast and fully independent of the real holdout content -- per the
task's explicit instruction not to use the real 40 labels in any test. Zero API
calls anywhere; evaluation/triage.py's TIER2_ACCOUNT_ACCESS_RULE_ENABLED default
is restored after every test that touches it (run_condition() already does this
internally via try/finally, verified below).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import evaluation.triage as triage_mod
from evaluation.run_part_j_triage_eval import (
    effective_arm_comparison_size,
    run_condition,
    summarize,
)


def _synthetic_examples():
    """4 fabricated examples covering: (a) ACCOUNT_ACCESS with no Tier-1 trigger
    (the toggle should matter here), (b) ACCOUNT_ACCESS WITH security language
    (Tier 1 pre-empts, toggle irrelevant), (c) a plain low-risk case, (d) a case
    where gold and llm intent deliberately disagree."""
    return [
        dict(
            example_id="SYN_1", tweet_id="1", customer_text="how do I unlink my account from facebook",
            gold_intent="ACCOUNT_ACCESS", llm_intent="ACCOUNT_ACCESS",
            human_decision="AUTO_HANDLE", human_reason="",
        ),
        dict(
            example_id="SYN_2", tweet_id="2", customer_text="my account was hacked please help",
            gold_intent="ACCOUNT_ACCESS", llm_intent="ACCOUNT_ACCESS",
            human_decision="HUMAN_ESCALATION", human_reason="security",
        ),
        dict(
            example_id="SYN_3", tweet_id="3", customer_text="how do I make a playlist collaborative",
            gold_intent="GENERAL_HOW_TO_INFO", llm_intent="GENERAL_HOW_TO_INFO",
            human_decision="AUTO_HANDLE", human_reason="",
        ),
        dict(
            example_id="SYN_4", tweet_id="4", customer_text="why is my premium not activated",
            gold_intent="SUBSCRIPTION_BILLING", llm_intent="ACCOUNT_ACCESS",  # deliberately disagree
            human_decision="HUMAN_ESCALATION", human_reason="billing issue",
        ),
    ]


@pytest.fixture(autouse=True)
def restore_triage_flag():
    """Extra safety net on top of run_condition()'s own try/finally -- guarantees
    no test in this file can leak a changed flag value to any other test file."""
    original = triage_mod.TIER2_ACCOUNT_ACCESS_RULE_ENABLED
    yield
    triage_mod.TIER2_ACCOUNT_ACCESS_RULE_ENABLED = original


# ============================================================
# Arm A/B toggling: only affects ACCOUNT_ACCESS examples not already Tier-1'd
# ============================================================

def test_arm_toggle_changes_decision_only_for_eligible_account_access_example():
    examples = _synthetic_examples()
    records_off = run_condition(examples, enabled=False, intent_source="llm")
    records_on = run_condition(examples, enabled=True, intent_source="llm")

    by_id_off = {r["example_id"]: r for r in records_off}
    by_id_on = {r["example_id"]: r for r in records_on}

    # SYN_1: ACCOUNT_ACCESS, no Tier-1 trigger -> toggle DOES change the decision.
    assert by_id_off["SYN_1"]["system_decision"] == "AUTO_HANDLE"
    assert by_id_on["SYN_1"]["system_decision"] == "HUMAN_ESCALATION"
    assert by_id_on["SYN_1"]["system_tier"] == "TIER_2"
    assert by_id_on["SYN_1"]["system_rule_id"] == "TIER2_ACCOUNT_ACCESS_DM_HISTORY"

    # SYN_2: ACCOUNT_ACCESS but security language -> Tier 1 pre-empts; toggle irrelevant.
    assert by_id_off["SYN_2"]["system_decision"] == "HUMAN_ESCALATION"
    assert by_id_on["SYN_2"]["system_decision"] == "HUMAN_ESCALATION"
    assert by_id_off["SYN_2"]["system_tier"] == by_id_on["SYN_2"]["system_tier"] == "TIER_1"

    # SYN_3: not ACCOUNT_ACCESS at all -> toggle irrelevant.
    assert by_id_off["SYN_3"]["system_decision"] == by_id_on["SYN_3"]["system_decision"] == "AUTO_HANDLE"


def test_run_condition_restores_triage_module_flag_after_call():
    examples = _synthetic_examples()
    original = triage_mod.TIER2_ACCOUNT_ACCESS_RULE_ENABLED
    run_condition(examples, enabled=(not original), intent_source="llm")
    assert triage_mod.TIER2_ACCOUNT_ACCESS_RULE_ENABLED == original


# ============================================================
# Gold vs. LLM intent source: must produce different results when they disagree
# ============================================================

def test_gold_vs_llm_intent_source_diverges_when_synthetically_disagreeing():
    examples = _synthetic_examples()  # SYN_4: gold=SUBSCRIPTION_BILLING, llm=ACCOUNT_ACCESS
    records_gold = run_condition(examples, enabled=True, intent_source="gold")
    records_llm = run_condition(examples, enabled=True, intent_source="llm")

    syn4_gold = next(r for r in records_gold if r["example_id"] == "SYN_4")
    syn4_llm = next(r for r in records_llm if r["example_id"] == "SYN_4")

    assert syn4_gold["intent_used"] == "SUBSCRIPTION_BILLING"
    assert syn4_llm["intent_used"] == "ACCOUNT_ACCESS"
    # gold: SUBSCRIPTION_BILLING has no adopted Tier-2 rule -> falls through to AUTO_HANDLE.
    assert syn4_gold["system_decision"] == "AUTO_HANDLE"
    # llm: ACCOUNT_ACCESS + rule enabled -> escalates.
    assert syn4_llm["system_decision"] == "HUMAN_ESCALATION"
    assert syn4_gold["system_decision"] != syn4_llm["system_decision"]


def test_gold_and_llm_intent_source_agree_when_intents_match():
    examples = _synthetic_examples()
    records_gold = run_condition(examples, enabled=False, intent_source="gold")
    records_llm = run_condition(examples, enabled=False, intent_source="llm")
    for gold_r, llm_r in zip(records_gold, records_llm):
        if gold_r["example_id"] == "SYN_4":
            continue  # the one deliberately-disagreeing example
        assert gold_r["intent_used"] == llm_r["intent_used"]
        assert gold_r["system_decision"] == llm_r["system_decision"]


# ============================================================
# False-auto-handle vs. false-escalate correctly distinguished
# ============================================================

def test_summarize_distinguishes_false_auto_handle_from_false_escalate():
    examples = _synthetic_examples()
    records = run_condition(examples, enabled=False, intent_source="llm")
    summary = summarize(records)

    # SYN_1: system AUTO_HANDLE, human AUTO_HANDLE -> true agreement, not a false-anything.
    # SYN_2: system HUMAN_ESCALATION, human HUMAN_ESCALATION -> true agreement.
    # SYN_3: system AUTO_HANDLE, human AUTO_HANDLE -> true agreement.
    # SYN_4 (rule disabled, llm intent=ACCOUNT_ACCESS, no Tier-1/Tier-3 trigger):
    #   system AUTO_HANDLE, human HUMAN_ESCALATION -> FALSE_AUTO_HANDLE (dangerous).
    assert summary["n"] == 4
    assert summary["false_auto_handle_count"] == 1
    assert summary["false_escalate_count"] == 0
    assert summary["agreement_count"] == 3
    assert summary["disagreements"][0]["example_id"] == "SYN_4"
    assert summary["disagreements"][0]["system_decision"] == "AUTO_HANDLE"
    assert summary["disagreements"][0]["human_decision"] == "HUMAN_ESCALATION"


def test_summarize_false_escalate_case():
    """A dedicated false-escalate (system over-escalates, human said AUTO_HANDLE)
    example, to confirm the OTHER direction is also correctly classified, not
    lumped together with false-auto-handle as generic 'disagreement'."""
    examples = [dict(
        example_id="SYN_5", tweet_id="5", customer_text="this is unrelated to anything risky",
        gold_intent="UNKNOWN_OTHER", llm_intent="UNKNOWN_OTHER",
        human_decision="AUTO_HANDLE", human_reason="",
    )]
    records = run_condition(examples, enabled=False, intent_source="llm")
    summary = summarize(records)
    assert summary["false_escalate_count"] == 1
    assert summary["false_auto_handle_count"] == 0
    assert summary["disagreements"][0]["system_tier"] == "TIER_1"
    assert summary["disagreements"][0]["system_rule_id"] == "TIER1_UNKNOWN_INTENT"


def test_summarize_rates_are_fractions_of_n_and_sum_correctly():
    examples = _synthetic_examples()
    records = run_condition(examples, enabled=False, intent_source="llm")
    summary = summarize(records)
    assert summary["agreement_rate"] + summary["false_auto_handle_rate_of_n"] + summary["false_escalate_rate_of_n"] == pytest.approx(1.0)


def test_summarize_perfect_agreement_has_zero_false_rates():
    examples = [
        dict(example_id="P1", tweet_id="p1", customer_text="hello", gold_intent="GENERAL_HOW_TO_INFO",
             llm_intent="GENERAL_HOW_TO_INFO", human_decision="AUTO_HANDLE", human_reason=""),
        dict(example_id="P2", tweet_id="p2", customer_text="i was hacked", gold_intent="ACCOUNT_ACCESS",
             llm_intent="ACCOUNT_ACCESS", human_decision="HUMAN_ESCALATION", human_reason="security"),
    ]
    records = run_condition(examples, enabled=False, intent_source="llm")
    summary = summarize(records)
    assert summary["agreement_rate"] == 1.0
    assert summary["false_auto_handle_count"] == 0
    assert summary["false_escalate_count"] == 0
    assert summary["disagreements"] == []


# ============================================================
# Effective Arm A/B comparison size
# ============================================================

def test_effective_arm_comparison_size_excludes_tier1_preempted_examples():
    examples = _synthetic_examples()
    eligible_llm = effective_arm_comparison_size(examples, "llm")
    # SYN_1 (ACCOUNT_ACCESS, no Tier-1 trigger) and SYN_4 (llm intent=ACCOUNT_ACCESS,
    # no Tier-1 trigger) are eligible; SYN_2 (ACCOUNT_ACCESS + "hacked") is NOT,
    # since Tier 1 already decides it regardless of the toggle.
    assert set(eligible_llm) == {"SYN_1", "SYN_4"}


def test_effective_arm_comparison_size_differs_by_intent_source():
    examples = _synthetic_examples()
    eligible_gold = effective_arm_comparison_size(examples, "gold")
    eligible_llm = effective_arm_comparison_size(examples, "llm")
    # SYN_4 is ACCOUNT_ACCESS only under llm intent, not gold -> must differ.
    assert "SYN_4" in eligible_llm
    assert "SYN_4" not in eligible_gold


# ============================================================
# Zero network/API behavior
# ============================================================

def test_part_j_module_has_no_openai_or_retrieval_import():
    import evaluation.run_part_j_triage_eval as mod
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "import openai" not in src
    assert "from openai" not in src
    assert "from evaluation.retrieval" not in src
    assert "from evaluation.embeddings" not in src
