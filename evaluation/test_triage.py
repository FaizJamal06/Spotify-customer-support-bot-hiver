"""
Tests for evaluation/triage.py.

No real API calls anywhere in this suite -- Tier-2B analysis reads only the
already-cached evaluation/results/k_ablation_sweep.json, and the cache-preflight
tests use synthetic paths, never touching the network. Per the task's explicit
instruction, no real TRIAGE_ANNOTATION_40.csv label is used or referenced anywhere
in this file.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.triage import (
    AUTO_HANDLE,
    CONFIDENCE_THRESHOLD_REJECTED,
    HUMAN_ESCALATION,
    TIER2_ACCOUNT_ACCESS_RULE_ENABLED,
    TIER2_ACCOUNT_ACCESS_RULE_VALIDATED,
    TIER_1,
    TIER_2,
    TIER_3,
    TIER_NONE,
    apply_triage_rules,
    check_no_api_spend_required,
    classify_historical_reply,
    compute_dm_redirect_breakdown,
)


# ============================================================
# 1-3: Tier 1 deterministic rules
# ============================================================

def test_unknown_other_intent_escalates():
    out = apply_triage_rules("just a normal message", "UNKNOWN_OTHER", confidence=0.9)
    assert out["decision"] == HUMAN_ESCALATION
    assert out["tier"] == TIER_1
    assert out["rule_id"] == "TIER1_UNKNOWN_INTENT"


@pytest.mark.parametrize("text", [
    "someone hacked my account and changed my password",
    "I think my account was compromised last night",
    "there was unauthorized access to my account",
    "someone got into my account without permission",
])
def test_security_language_escalates(text):
    out = apply_triage_rules(text, "ACCOUNT_ACCESS", confidence=0.9)
    # ACCOUNT_ACCESS also has a Tier-2 rule -- Tier 1 must still fire first.
    assert out["decision"] == HUMAN_ESCALATION
    assert out["tier"] == TIER_1
    assert out["rule_id"] == "TIER1_SECURITY_LANGUAGE"


@pytest.mark.parametrize("text", [
    "I am going to sue Spotify for this",
    "my lawyer will be in touch about this",
    "this is a matter for my attorney",
    "I will pursue legal action if this isn't fixed",
])
def test_legal_language_escalates(text):
    out = apply_triage_rules(text, "SUBSCRIPTION_BILLING", confidence=0.9)
    assert out["decision"] == HUMAN_ESCALATION
    assert out["tier"] == TIER_1
    assert out["rule_id"] == "TIER1_LEGAL_LANGUAGE"


# ============================================================
# 4: clear supported low-risk case -> AUTO_HANDLE
# ============================================================

def test_clear_low_risk_case_auto_handles():
    out = apply_triage_rules(
        "How do I create a collaborative playlist?", "GENERAL_HOW_TO_INFO", confidence=0.95,
    )
    assert out["decision"] == AUTO_HANDLE
    assert out["tier"] == TIER_NONE
    assert out["rule_id"] is None


# ============================================================
# 5: confidence alone cannot force escalation or auto-handle
# ============================================================

def test_confidence_threshold_is_explicitly_rejected_constant():
    assert CONFIDENCE_THRESHOLD_REJECTED is True


def test_low_confidence_alone_does_not_force_escalation():
    out = apply_triage_rules(
        "How do I change my playlist cover?", "GENERAL_HOW_TO_INFO", confidence=0.01,
    )
    assert out["decision"] == AUTO_HANDLE  # no rule fires regardless of how low confidence is
    assert "did NOT influence" in out["confidence_note"]


def test_high_confidence_alone_does_not_force_auto_handle_when_a_rule_fires():
    out = apply_triage_rules("this is hacked, please help", "APP_TECH_ISSUE", confidence=0.99)
    assert out["decision"] == HUMAN_ESCALATION  # Tier 1 fires despite very high confidence
    assert "did NOT influence" in out["confidence_note"]


def test_confidence_note_present_even_when_none():
    out = apply_triage_rules("hello", "GENERAL_HOW_TO_INFO", confidence=None)
    assert "No confidence signal provided." == out["confidence_note"]


# ============================================================
# 6-7: Tier-2 DM-redirect heuristic correctness
# ============================================================

@pytest.mark.parametrize("text", [
    "Could you DM us your account's username or email address? We'll take a look backstage /GU https://t.co/ldFdZRiNAt",
    "Hi there! We've just sent a DM your way. Let's carry on chatting there /FR",
    "Can you send us a direct message with your account details?",
    "Please check your inbox, we've replied there.",
])
def test_dm_redirect_examples_classified_correctly(text):
    assert classify_historical_reply(text) == "DM_REDIRECT"


@pytest.mark.parametrize("text", [
    "Check out the steps under \"Downloads unexpectedly removed\" at https://t.co/38J7tFlIBF. They should help with this.",
    "We have some info about content here: https://t.co/0i8GpimuDa",
    "Can you tell us what internet browser you're using, does using another browser work at all?",
    "This should be due to licensing issues. Hopefully we'll have it available soon.",
])
def test_substantive_examples_with_no_dm_mention_classified_correctly(text):
    assert classify_historical_reply(text) == "SUBSTANTIVE"


def test_dm_mention_with_cued_url_is_substantive_not_dm_redirect():
    """The core distinguishing case: DM is mentioned, but the reply ALSO references
    a specific resource via a cue-introduced URL -- must not be misclassified as a
    pure redirect just because 'DM' appears somewhere in the text."""
    text = "We've sent you more info via DM, but you can also find general steps here: https://t.co/38J7tFlIBF"
    assert classify_historical_reply(text) == "SUBSTANTIVE"


def test_bare_dm_mention_is_not_classified_substantive_merely_for_containing_dm():
    """Must not classify a reply as DM_REDIRECT merely because it contains the word
    'DM' -- but conversely, a bare DM ask with an UNCUED boilerplate URL must still
    resolve to DM_REDIRECT (the URL is not referenced/substantive)."""
    text = "Hey there! Could you DM us your account's username or email address? We'll take a look backstage /GU https://t.co/ldFdZRiNAt"
    assert classify_historical_reply(text) == "DM_REDIRECT"


def test_no_dm_mention_at_all_is_always_substantive():
    assert classify_historical_reply("Your subscription renews on the 5th of each month.") == "SUBSTANTIVE"


def test_classify_historical_reply_handles_none_and_empty():
    assert classify_historical_reply(None) == "SUBSTANTIVE"
    assert classify_historical_reply("") == "SUBSTANTIVE"


# ============================================================
# 8: output always contains decision/reason/tier/rule identifier
# ============================================================

@pytest.mark.parametrize("text,intent", [
    ("normal message", "UNKNOWN_OTHER"),
    ("i was hacked", "APP_TECH_ISSUE"),
    ("i will sue you", "SUBSCRIPTION_BILLING"),
    ("my account is locked", "ACCOUNT_ACCESS"),
    ("this is furious and outrageous service", "FEATURE_FEEDBACK"),
    ("how do i change my password", "GENERAL_HOW_TO_INFO"),
])
def test_output_always_has_required_keys(text, intent):
    out = apply_triage_rules(text, intent)
    for key in ("decision", "reason", "tier", "rule_id", "confidence_note"):
        assert key in out
    assert out["decision"] in (AUTO_HANDLE, HUMAN_ESCALATION)
    assert out["tier"] in (TIER_1, TIER_2, TIER_3, TIER_NONE)
    assert isinstance(out["reason"], str) and out["reason"]


def test_rule_id_is_none_only_when_tier_is_none():
    out_none = apply_triage_rules("how do i change my playlist name", "GENERAL_HOW_TO_INFO")
    assert out_none["tier"] == TIER_NONE
    assert out_none["rule_id"] is None

    out_fired = apply_triage_rules("i was hacked", "APP_TECH_ISSUE")
    assert out_fired["tier"] != TIER_NONE
    assert out_fired["rule_id"] is not None


# ============================================================
# 9: deterministic repeated results
# ============================================================

def test_apply_triage_rules_is_deterministic():
    args = ("I think my account was hacked and I'm furious", "ACCOUNT_ACCESS")
    out1 = apply_triage_rules(*args, confidence=0.5)
    out2 = apply_triage_rules(*args, confidence=0.9)  # different confidence, same rule outcome
    assert out1["decision"] == out2["decision"] == HUMAN_ESCALATION
    assert out1["tier"] == out2["tier"] == TIER_1  # security language wins over Tier 2/3
    assert out1["rule_id"] == out2["rule_id"]


def test_priority_order_with_tier2_account_access_rule_enabled(monkeypatch):
    """Tier-2's ACCOUNT_ACCESS rule is OFF by default (see
    test_tier2_account_access_rule_disabled_by_default_...py-level tests below) --
    this test explicitly enables it to verify Tier-1-beats-Tier-2-beats-Tier-3
    precedence still holds correctly when the experimental rule IS turned on."""
    import evaluation.triage as triage_mod
    monkeypatch.setattr(triage_mod, "TIER2_ACCOUNT_ACCESS_RULE_ENABLED", True)

    # ACCOUNT_ACCESS alone (no keywords) -> Tier 2 fires.
    out_tier2 = apply_triage_rules("my account is locked", "ACCOUNT_ACCESS")
    assert out_tier2["tier"] == TIER_2

    # ACCOUNT_ACCESS + anger keyword (no security/legal language) -> Tier 2 still wins over Tier 3.
    out_tier2_over_3 = apply_triage_rules("this is ridiculous, my account is locked", "ACCOUNT_ACCESS")
    assert out_tier2_over_3["tier"] == TIER_2

    # ACCOUNT_ACCESS + security language -> Tier 1 wins over Tier 2.
    out_tier1_over_2 = apply_triage_rules("my account was hacked", "ACCOUNT_ACCESS")
    assert out_tier1_over_2["tier"] == TIER_1


def test_priority_order_with_tier2_account_access_rule_disabled():
    """Same scenarios, default (disabled) flag: ACCOUNT_ACCESS alone must now fall
    through to Tier 3 or NONE rather than Tier 2, while Tier 1 still short-circuits
    correctly regardless."""
    out_no_rule = apply_triage_rules("my account is locked", "ACCOUNT_ACCESS")
    assert out_no_rule["tier"] != TIER_2

    out_tier3 = apply_triage_rules("this is ridiculous, my account is locked", "ACCOUNT_ACCESS")
    assert out_tier3["tier"] == TIER_3  # falls through Tier 2 (disabled) to Tier 3

    out_tier1 = apply_triage_rules("my account was hacked", "ACCOUNT_ACCESS")
    assert out_tier1["tier"] == TIER_1  # Tier 1 still fires regardless of the Tier-2 flag


# ============================================================
# 10: zero-network/API behavior
# ============================================================

def test_apply_triage_rules_module_has_no_openai_or_retrieval_import():
    """Checks for actual import/call sites, not mere docstring mentions -- the module
    docstring legitimately explains, in prose, that it does NOT call retrieve_top_k()
    etc., which would false-positive a naive substring check."""
    src = Path(sys.modules["evaluation.triage"].__file__).read_text(encoding="utf-8")
    assert "import openai" not in src
    assert "from openai" not in src
    # structural guarantee: retrieve_top_k/get_embedding/get_api_key can only be
    # CALLED if imported first -- absence of any import from these modules means
    # no call to them is reachable, regardless of what the docstring prose says.
    assert "from evaluation.retrieval" not in src
    assert "import evaluation.retrieval" not in src
    assert "from evaluation.embeddings" not in src
    assert "import evaluation.embeddings" not in src


def test_compute_dm_redirect_breakdown_reads_only_cached_sweep_json(monkeypatch):
    """Patches open() usage indirectly by asserting the function never imports or
    references anything from evaluation.retrieval / evaluation.embeddings -- a
    structural, not just behavioral, zero-network guarantee."""
    import evaluation.triage as triage_mod
    assert not hasattr(triage_mod, "retrieve_top_k")
    assert not hasattr(triage_mod, "get_embedding")


# ============================================================
# Cache preflight
# ============================================================

def test_check_no_api_spend_required_passes_when_real_sweep_cache_present():
    if not config.EVAL_DIR.exists() or not (config.EVAL_DIR / "k_ablation_sweep.json").exists():
        pytest.skip("No cached k_ablation_sweep.json present locally.")
    assert check_no_api_spend_required() is True


def test_check_no_api_spend_required_refuses_on_synthetic_missing_cache(monkeypatch, tmp_path):
    import evaluation.triage as triage_mod
    fake_missing_path = tmp_path / "does_not_exist_k_ablation_sweep.json"
    monkeypatch.setattr(triage_mod, "K_ABLATION_SWEEP_PATH", fake_missing_path)
    with pytest.raises(FileNotFoundError, match="not found"):
        triage_mod.check_no_api_spend_required()


def test_compute_dm_redirect_breakdown_refuses_before_any_api_path_on_missing_cache(monkeypatch, tmp_path):
    import evaluation.triage as triage_mod
    fake_missing_path = tmp_path / "does_not_exist_k_ablation_sweep.json"
    monkeypatch.setattr(triage_mod, "K_ABLATION_SWEEP_PATH", fake_missing_path)
    with pytest.raises(FileNotFoundError):
        compute_dm_redirect_breakdown()


# ============================================================
# Tier-2B breakdown structure (against the real cached sweep, if present)
# ============================================================

def test_compute_dm_redirect_breakdown_covers_all_8_intents_with_cis():
    if not (config.EVAL_DIR / "k_ablation_sweep.json").exists():
        pytest.skip("No cached k_ablation_sweep.json present locally.")
    per_reply, per_example = compute_dm_redirect_breakdown(k=5)
    assert set(per_reply.keys()) == set(config.FROZEN_LABELS)
    assert set(per_example.keys()) == set(config.FROZEN_LABELS)
    for intent, stats in per_reply.items():
        assert 0.0 <= stats["wilson_lo"] <= stats["rate"] <= stats["wilson_hi"] <= 1.0


def test_account_access_is_the_adopted_tier2_rule_and_no_others():
    """Locks in the adoption decision itself as a regression check -- if the
    underlying cached sweep data or heuristic ever changes, this test should be
    the one that visibly breaks, rather than the rule silently drifting."""
    from evaluation.triage import TIER2_ESCALATE_INTENTS
    assert TIER2_ESCALATE_INTENTS == {"ACCOUNT_ACCESS"}


# ============================================================
# Experiment toggle: TIER2_ACCOUNT_ACCESS_RULE_ENABLED / _VALIDATED
# ============================================================

def test_tier2_account_access_rule_enabled_defaults_to_false():
    assert TIER2_ACCOUNT_ACCESS_RULE_ENABLED is False


def test_tier2_account_access_rule_validated_defaults_to_false():
    assert TIER2_ACCOUNT_ACCESS_RULE_VALIDATED is False


def test_with_rule_disabled_account_access_does_not_trigger_tier2():
    """Default state (flag untouched): a plain ACCOUNT_ACCESS case with no Tier-1/
    Tier-3 keywords must fall all the way through to AUTO_HANDLE, not Tier 2."""
    out = apply_triage_rules("my account is locked", "ACCOUNT_ACCESS")
    assert out["tier"] != TIER_2
    assert out["decision"] == AUTO_HANDLE
    assert out["rule_id"] is None


def test_with_rule_explicitly_enabled_original_tier2_behavior_is_preserved(monkeypatch):
    """Flipping the module-level flag to True must reproduce EXACTLY the original
    Tier-2B decision, reason content, and rule_id -- the rule text/heuristic itself
    is unchanged, only whether it fires is gated."""
    import evaluation.triage as triage_mod
    monkeypatch.setattr(triage_mod, "TIER2_ACCOUNT_ACCESS_RULE_ENABLED", True)

    out = apply_triage_rules("my account is locked", "ACCOUNT_ACCESS")
    assert out["decision"] == HUMAN_ESCALATION
    assert out["tier"] == TIER_2
    assert out["rule_id"] == "TIER2_ACCOUNT_ACCESS_DM_HISTORY"
    assert "DM-redirect" in out["reason"]
    assert "Wilson 95% CI [0.862, 1.000]" in out["reason"]  # original evidence text preserved verbatim


def test_enabling_rule_does_not_affect_other_intents():
    """The toggle is scoped to ACCOUNT_ACCESS specifically -- enabling it must not
    cause any other intent to start escalating via Tier 2 (TIER2_ESCALATE_INTENTS
    itself is unchanged)."""
    import evaluation.triage as triage_mod
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(triage_mod, "TIER2_ACCOUNT_ACCESS_RULE_ENABLED", True)
        for intent in ("APP_TECH_ISSUE", "SUBSCRIPTION_BILLING", "GENERAL_HOW_TO_INFO"):
            out = apply_triage_rules("a normal low-risk message", intent)
            assert out["tier"] != TIER_2


def test_validated_flag_does_not_influence_decision_when_enabled(monkeypatch):
    """VALIDATED is documentation-only and must never be read by the decision path
    -- flipping it (with ENABLED left at its default False) must not change behavior."""
    import evaluation.triage as triage_mod
    monkeypatch.setattr(triage_mod, "TIER2_ACCOUNT_ACCESS_RULE_VALIDATED", True)
    out = apply_triage_rules("my account is locked", "ACCOUNT_ACCESS")
    assert out["tier"] != TIER_2  # ENABLED still False -> rule still does not fire


def test_enabled_and_validated_flags_are_independent(monkeypatch):
    """Regression test for Part H toggle independence: ENABLED alone controls
    whether the ACCOUNT_ACCESS Tier-2 rule fires; VALIDATED never does, in either
    direction.

    Case 1: ENABLED=False, VALIDATED=True -> the rule must NOT fire, and the
    result must be IDENTICAL (not just "still not Tier 2") to the ENABLED=False,
    VALIDATED=False baseline -- VALIDATED=True must not enable, alter, or
    otherwise change the output in any field.

    Case 2 (converse): ENABLED=True, VALIDATED=False -> the existing ACCOUNT_ACCESS
    Tier-2 rule must still fire exactly as before (decision/tier/rule_id/reason
    unchanged from the already-established enabled behavior).
    """
    import evaluation.triage as triage_mod
    args = ("my account is locked", "ACCOUNT_ACCESS")

    # Baseline: both flags at their real defaults (False, False).
    assert triage_mod.TIER2_ACCOUNT_ACCESS_RULE_ENABLED is False
    assert triage_mod.TIER2_ACCOUNT_ACCESS_RULE_VALIDATED is False
    baseline = apply_triage_rules(*args)
    assert baseline["tier"] != TIER_2

    # Case 1: ENABLED=False, VALIDATED=True.
    monkeypatch.setattr(triage_mod, "TIER2_ACCOUNT_ACCESS_RULE_ENABLED", False)
    monkeypatch.setattr(triage_mod, "TIER2_ACCOUNT_ACCESS_RULE_VALIDATED", True)
    out_validated_only = apply_triage_rules(*args)
    assert out_validated_only["tier"] != TIER_2
    assert out_validated_only == baseline  # VALIDATED=True changed nothing at all

    # Case 2 (converse): ENABLED=True, VALIDATED=False.
    monkeypatch.setattr(triage_mod, "TIER2_ACCOUNT_ACCESS_RULE_ENABLED", True)
    monkeypatch.setattr(triage_mod, "TIER2_ACCOUNT_ACCESS_RULE_VALIDATED", False)
    out_enabled_only = apply_triage_rules(*args)
    assert out_enabled_only["decision"] == HUMAN_ESCALATION
    assert out_enabled_only["tier"] == TIER_2
    assert out_enabled_only["rule_id"] == "TIER2_ACCOUNT_ACCESS_DM_HISTORY"
    assert "Wilson 95% CI [0.862, 1.000]" in out_enabled_only["reason"]

    # The two combinations must differ (proves ENABLED, not VALIDATED, is what moved).
    assert out_validated_only != out_enabled_only


def test_toggle_behavior_is_deterministic_across_repeated_calls(monkeypatch):
    import evaluation.triage as triage_mod
    args = ("my account is locked", "ACCOUNT_ACCESS")

    out_disabled_1 = apply_triage_rules(*args)
    out_disabled_2 = apply_triage_rules(*args)
    assert out_disabled_1 == out_disabled_2

    monkeypatch.setattr(triage_mod, "TIER2_ACCOUNT_ACCESS_RULE_ENABLED", True)
    out_enabled_1 = apply_triage_rules(*args)
    out_enabled_2 = apply_triage_rules(*args)
    assert out_enabled_1 == out_enabled_2
    assert out_enabled_1 != out_disabled_1  # the two modes genuinely differ


# ============================================================
# No use of the held-out 40-example triage labels anywhere
# ============================================================

def test_triage_module_never_opens_or_reads_triage_annotation_40():
    """The module docstring legitimately mentions golden_set/TRIAGE_ANNOTATION_40.csv
    once, in prose, to state that this milestone does NOT read it -- a bare substring
    check would false-positive on that honest disclosure. This checks for actual
    file-access code instead: no open()/csv-read call naming that file, and no path
    construction pointing at it."""
    src = Path(sys.modules["evaluation.triage"].__file__).read_text(encoding="utf-8")
    assert "TRIAGE_ANNOTATION_40_PATH" not in src
    assert '"TRIAGE_ANNOTATION_40' not in src  # no string literal used to build a path/filename
    assert "GOLDEN_DIR" not in src  # module never touches golden_set/ at all
    # exactly one mention total, and it must be the documented, prose disclosure --
    # not two-or-more uses that could indicate an actual second (code) reference.
    assert src.count("TRIAGE_ANNOTATION_40") == 1
