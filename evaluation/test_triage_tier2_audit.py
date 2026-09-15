"""
Tests for evaluation/audit_triage_tier2.py -- the Part H Tier-2B audit.

No real API calls anywhere; no real TRIAGE_ANNOTATION_40.csv label is used or
referenced. evaluation/triage.py's frozen classify_historical_reply() and adopted
rule set are used UNMODIFIED and are not touched by this test file either.
"""
import sys
from pathlib import Path

import pytest
from scipy.stats import fisher_exact
from statsmodels.stats.proportion import confint_proportions_2indep

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.audit_triage_tier2 import (
    classify_variant_a,
    classify_variant_b,
    load_k5_records,
    per_example_majority_labels,
    run_all_pairwise_from_account_access,
    run_variant,
    summarize,
    two_proportion_comparison,
)
from evaluation.triage import apply_triage_rules, classify_historical_reply

requires_real_sweep = pytest.mark.skipif(
    not (config.EVAL_DIR / "k_ablation_sweep.json").exists(),
    reason="No cached k_ablation_sweep.json present locally.",
)


# ============================================================
# Statistical calculation correctness
# ============================================================

def test_two_proportion_comparison_matches_direct_scipy_fisher_call():
    """Cross-check against calling scipy.stats.fisher_exact directly on the same
    2x2 table -- proves the wrapper is a faithful pass-through, not testing scipy."""
    n1, dm1, n2, dm2 = 24, 24, 21, 18
    result = two_proportion_comparison(n1, dm1, n2, dm2, "A", "B")

    expected_table = [[dm1, n1 - dm1], [dm2, n2 - dm2]]
    expected_or, expected_p = fisher_exact(expected_table, alternative="two-sided")
    assert result["p_value"] == pytest.approx(expected_p)
    assert result["odds_ratio"] == pytest.approx(expected_or)
    assert result["contingency_table"] == expected_table


def test_two_proportion_comparison_matches_direct_statsmodels_ci_call():
    n1, dm1, n2, dm2 = 24, 24, 21, 18
    result = two_proportion_comparison(n1, dm1, n2, dm2, "A", "B")
    expected_lo, expected_hi = confint_proportions_2indep(dm1, n1, dm2, n2, method="newcomb", compare="diff")
    assert result["diff_ci_lo"] == pytest.approx(expected_lo)
    assert result["diff_ci_hi"] == pytest.approx(expected_hi)


def test_two_proportion_comparison_identical_rates_gives_p_near_1():
    result = two_proportion_comparison(20, 10, 20, 10, "A", "B")
    assert result["p_value"] == pytest.approx(1.0)
    assert result["risk_difference"] == pytest.approx(0.0)
    assert result["diff_ci_lo"] < 0 < result["diff_ci_hi"]


def test_two_proportion_comparison_extreme_difference_gives_small_p():
    """20/20 vs 0/20 -- an unambiguous, maximal difference -- must be significant."""
    result = two_proportion_comparison(20, 20, 20, 0, "A", "B")
    assert result["p_value"] < 0.001
    assert result["risk_difference"] == pytest.approx(1.0)


def test_fisher_exact_chosen_because_zero_cell_present_in_account_access_row():
    """Documents/verifies WHY Fisher's exact was chosen for the real ACCOUNT_ACCESS
    comparison: the contingency table has a zero cell (24/24 -> 0 failures), where a
    normal-approximation two-proportion z-test is not reliable."""
    result = two_proportion_comparison(24, 24, 21, 18, "ACCOUNT_ACCESS", "SUBSCRIPTION_BILLING")
    assert 0 in result["contingency_table"][0]
    assert result["test"] == "Fisher's exact test (two-sided)"


# ============================================================
# ACCOUNT_ACCESS vs strongest-competitor comparison (real cached data)
# ============================================================

@requires_real_sweep
def test_account_access_vs_subscription_billing_is_not_significant_at_p05():
    """Locks in the audit's central, surprising finding as a regression check: the
    informal non-overlapping-CI argument from the original report does NOT survive
    a proper two-proportion test against the single strongest competitor."""
    records = load_k5_records()
    by_intent = per_example_majority_labels(records, classify_historical_reply)
    summary = summarize(by_intent)
    aa, sb = summary["ACCOUNT_ACCESS"], summary["SUBSCRIPTION_BILLING"]
    assert aa["n"] == 24 and aa["dm"] == 24
    assert sb["n"] == 21 and sb["dm"] == 18

    result = two_proportion_comparison(aa["n"], aa["dm"], sb["n"], sb["dm"], "ACCOUNT_ACCESS", "SUBSCRIPTION_BILLING")
    assert result["p_value"] > 0.05
    assert result["diff_ci_lo"] < 0  # CI includes zero -> cannot rule out no difference


@requires_real_sweep
def test_account_access_pairwise_comparisons_applied_uniformly_to_all_other_intents():
    """Confirms the SAME test/logic was run against every other intent, not just a
    cherry-picked favorable one -- exactly 7 comparisons (8 intents - ACCOUNT_ACCESS),
    all using the identical two_proportion_comparison() function."""
    records = load_k5_records()
    by_intent = per_example_majority_labels(records, classify_historical_reply)
    summary = summarize(by_intent)
    all_pairwise = run_all_pairwise_from_account_access(summary)

    assert set(all_pairwise.keys()) == set(config.FROZEN_LABELS) - {"ACCOUNT_ACCESS"}
    assert len(all_pairwise) == 7
    for intent, comp in all_pairwise.items():
        assert comp["test"] == "Fisher's exact test (two-sided)"
        assert comp["label1"] == "ACCOUNT_ACCESS"
        assert comp["label2"] == intent


@requires_real_sweep
def test_account_access_significantly_separated_from_most_other_intents():
    """The 6 intents with the lowest rates should all be clearly significant --
    ACCOUNT_ACCESS's fragility is specifically against its ONE closest competitor,
    not against the whole field."""
    records = load_k5_records()
    by_intent = per_example_majority_labels(records, classify_historical_reply)
    summary = summarize(by_intent)
    all_pairwise = run_all_pairwise_from_account_access(summary)

    n_significant = sum(1 for comp in all_pairwise.values() if comp["p_value"] < 0.05)
    assert n_significant == 6  # all except SUBSCRIPTION_BILLING


# ============================================================
# Robustness variants (Part 2) -- determinism + correctness
# ============================================================

def test_variant_a_classify_matches_inbox_only_semantics():
    assert classify_variant_a("Please check your inbox, we've replied there.") == "DM_REDIRECT"
    # no "inbox" present -- must be SUBSTANTIVE under variant A even though it
    # mentions "DM", since variant A's trigger deliberately excludes dm/direct message.
    assert classify_variant_a("Could you DM us your account's username or email address?") == "SUBSTANTIVE"


def test_variant_b_classify_no_longer_treats_via_as_a_substantive_cue():
    text = "We've sent you more info via https://t.co/38J7tFlIBF, DM us if you need more."
    # under the ORIGINAL heuristic, "via <URL>" is a substantive cue -> SUBSTANTIVE
    assert classify_historical_reply(text) == "SUBSTANTIVE"
    # under variant B, "via" is removed from the cue list -> no cue found -> DM_REDIRECT
    assert classify_variant_b(text) == "DM_REDIRECT"


def test_variant_b_unaffected_case_matches_original_heuristic():
    text = "Check out the steps under \"Downloads unexpectedly removed\" at https://t.co/38J7tFlIBF."
    assert classify_historical_reply(text) == classify_variant_b(text) == "SUBSTANTIVE"


@requires_real_sweep
def test_variant_results_are_deterministic_across_two_runs():
    records = load_k5_records()
    result_a1 = run_variant(records, classify_variant_a, "A")
    result_a2 = run_variant(records, classify_variant_a, "A")
    assert result_a1["per_intent"] == result_a2["per_intent"]
    assert result_a1["account_access_rank"] == result_a2["account_access_rank"]

    result_b1 = run_variant(records, classify_variant_b, "B")
    result_b2 = run_variant(records, classify_variant_b, "B")
    assert result_b1["per_intent"] == result_b2["per_intent"]


@requires_real_sweep
def test_variant_a_collapses_account_access_rate_to_zero():
    """Regression-locks the audit's other headline finding: under variant A
    (inbox-only trigger), ACCOUNT_ACCESS's DM-redirect signal vanishes entirely --
    demonstrating the original finding's sensitivity to the exact trigger wording."""
    records = load_k5_records()
    result = run_variant(records, classify_variant_a, "A")
    assert result["per_intent"]["ACCOUNT_ACCESS"]["dm"] == 0
    assert result["per_intent"]["ACCOUNT_ACCESS"]["rate"] == 0.0


@requires_real_sweep
def test_variant_b_leaves_account_access_result_unchanged():
    records = load_k5_records()
    result = run_variant(records, classify_variant_b, "B")
    assert result["per_intent"]["ACCOUNT_ACCESS"]["dm"] == 24
    assert result["per_intent"]["ACCOUNT_ACCESS"]["n"] == 24


@requires_real_sweep
def test_all_variants_report_complete_per_intent_breakdown():
    """Both variants must report every intent, not just ACCOUNT_ACCESS -- per the
    instruction to report all variants/intents regardless of outcome."""
    records = load_k5_records()
    for fn in (classify_variant_a, classify_variant_b):
        result = run_variant(records, fn, "x")
        assert set(result["per_intent"].keys()) == set(config.FROZEN_LABELS)


# ============================================================
# Tier precedence (Part 4) -- exact three synthetic combinations
# ============================================================

def test_precedence_security_language_plus_account_access_intent():
    """security + ACCOUNT_ACCESS: Tier 1 (security) must win over the adopted
    Tier-2 ACCOUNT_ACCESS rule, even though both would independently escalate."""
    out = apply_triage_rules("my account was hacked", "ACCOUNT_ACCESS", confidence=0.9)
    assert out["decision"] == "HUMAN_ESCALATION"
    assert out["tier"] == "TIER_1"
    assert out["rule_id"] == "TIER1_SECURITY_LANGUAGE"


def test_precedence_unknown_intent_plus_emotional_language():
    """UNKNOWN + emotional language: Tier 1 (UNKNOWN_OTHER) must win over Tier 3
    (anger keywords), even though both would independently escalate."""
    out = apply_triage_rules("this is ridiculous and outrageous", "UNKNOWN_OTHER", confidence=0.5)
    assert out["decision"] == "HUMAN_ESCALATION"
    assert out["tier"] == "TIER_1"
    assert out["rule_id"] == "TIER1_UNKNOWN_INTENT"


def test_precedence_security_language_plus_unknown_intent():
    """security + UNKNOWN: both are Tier-1 rules -- the fixed check order
    (UNKNOWN_OTHER checked first) determines which specific rule_id is reported,
    but the tier and decision must be identical either way."""
    out = apply_triage_rules("someone hacked my account", "UNKNOWN_OTHER", confidence=0.5)
    assert out["decision"] == "HUMAN_ESCALATION"
    assert out["tier"] == "TIER_1"
    assert out["rule_id"] == "TIER1_UNKNOWN_INTENT"  # UNKNOWN_OTHER checked before security language


# ============================================================
# Zero network/API behavior
# ============================================================

def test_audit_module_has_no_openai_or_retrieval_import():
    src = Path(sys.modules["evaluation.audit_triage_tier2"].__file__).read_text(encoding="utf-8")
    assert "import openai" not in src
    assert "from openai" not in src
    assert "from evaluation.retrieval" not in src
    assert "import evaluation.retrieval" not in src
    assert "from evaluation.embeddings" not in src
    assert "import evaluation.embeddings" not in src


def test_load_k5_records_refuses_before_any_api_path_on_missing_cache(monkeypatch, tmp_path):
    import evaluation.audit_triage_tier2 as audit_mod
    fake_missing_path = tmp_path / "does_not_exist_k_ablation_sweep.json"
    monkeypatch.setattr(audit_mod, "K_ABLATION_SWEEP_PATH", fake_missing_path)
    with pytest.raises(FileNotFoundError):
        audit_mod.load_k5_records()


# ============================================================
# Holdout isolation
# ============================================================

def test_audit_module_never_opens_or_reads_triage_annotation_40():
    """The module docstring legitimately mentions golden_set/TRIAGE_ANNOTATION_40.csv
    once, in prose, to state the holdout isolation guarantee -- a bare substring
    check would false-positive on that honest disclosure. Checks for actual
    file-access code instead, and that the mention count is exactly the one
    expected prose disclosure (not a second, real reference)."""
    src = Path(sys.modules["evaluation.audit_triage_tier2"].__file__).read_text(encoding="utf-8")
    assert '"TRIAGE_ANNOTATION_40' not in src  # no string literal used to build a path/filename
    assert "GOLDEN_DIR" not in src  # module never touches golden_set/ at all
    assert src.count("TRIAGE_ANNOTATION_40") == 1


def test_triage_module_itself_still_untouched_by_this_audit():
    """evaluation/triage.py's adopted rule set must be exactly what the prior
    milestone set -- this audit reports on it, it does not change it."""
    from evaluation.triage import TIER2_ESCALATE_INTENTS
    assert TIER2_ESCALATE_INTENTS == {"ACCOUNT_ACCESS"}
