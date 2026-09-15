"""
Triage rule application (implementation_plan.md §8, "Triage Policy -- Three Tiers").

Implements the three-tier policy exactly as specified for this milestone: Tier 1
(deterministic safety rules), Tier 2 (evidence-driven -- one hypothesis tested and
REJECTED, one tested and PARTIALLY adopted from real evidence), and Tier 3 (an
explicitly unvalidated, optional heuristic). This module does NOT evaluate these
rules against golden_set/TRIAGE_ANNOTATION_40.csv -- that is Part J, out of scope
here, and that file's decision/reason columns were never read while writing this
module (see TIER2_DM_REDIRECT_ANALYSIS.md-equivalent notes below and the milestone
report for the explicit isolation confirmation).

=== TIER 1: deterministic policy rules (never empirical claims) ===
  1. UNKNOWN_OTHER intent -> HUMAN_ESCALATION
  2. Explicit account-compromise/security language -> HUMAN_ESCALATION
  3. Explicit legal/high-risk language -> HUMAN_ESCALATION

=== TIER 2A: confidence threshold -- TESTED AND REJECTED ===
evaluation/CALIBRATION_RESULTS.md (Experiment 2, n=200) found the classifier is
overconfident in every one of 5 quantile buckets (mean confidence exceeds empirical
accuracy everywhere; ECE=0.14, Brier=0.166; Wilson 95% CIs per bucket span
15-30 points). Conclusion #7 of that report: "this data does not support a
defensible hard confidence threshold for Tier-2 triage." No hard confidence
threshold is implemented here. `confidence`, if passed to apply_triage_rules(),
is carried through in the output purely as an ADVISORY field -- it is never
compared against a cutoff and never by itself forces AUTO_HANDLE or
HUMAN_ESCALATION. See CONFIDENCE_THRESHOLD_REJECTED below.

=== TIER 2B: intent-specific escalation via historical DM-redirect rate ===
Tested using ONLY the already-cached k=5 retrieval evidence for the 200 golden
examples in evaluation/results/k_ablation_sweep.json (built by a prior milestone;
zero new API/embedding calls made to produce or read this module -- see
check_no_api_spend_required() and the milestone report). The DM-redirect heuristic
(classify_historical_reply()) was written down BEFORE any per-intent rate was
computed and was not revised afterward.

Result (see the milestone report for the full per-intent table with Wilson 95% CIs
at both the per-retrieved-reply level, n=1000, and the per-golden-example level,
n=200, the latter correcting for the fact that a golden example's 5 retrieved
replies are correlated, not independent trials):

  ACCOUNT_ACCESS is the only intent whose Wilson CI does not overlap any other
  intent's CI at BOTH granularities (per-reply: 82.5% [0.747, 0.883], n=120;
  per-example majority: 100% [0.862, 1.000], n=24). SUBSCRIPTION_BILLING has a
  similarly high point estimate but its per-example CI [0.654, 0.950] marginally
  OVERLAPS GENERAL_HOW_TO_INFO's per-example CI [0.376, 0.716] -- not adopted, to
  avoid relying on a separation that vanishes under the more statistically correct
  (clustering-aware) analysis.

  ADOPTED AS AN EXPERIMENTAL CANDIDATE ONLY, DEFAULT OFF: ACCOUNT_ACCESS ->
  HUMAN_ESCALATION (TIER2_ACCOUNT_ACCESS_DM_HISTORY). NOT adopted for any other
  intent, including SUBSCRIPTION_BILLING and GENERAL_HOW_TO_INFO: "Tier-2
  intent-specific escalation: no defensible rule adopted" for those seven intents.

  A follow-up statistical/robustness audit (evaluation/audit_triage_tier2.py,
  evaluation/results/triage_tier2_audit.json) found this ACCOUNT_ACCESS rule
  PLAUSIBLE BUT FRAGILE, not clearly supported: a proper two-proportion test
  (Fisher's exact) against ACCOUNT_ACCESS's single strongest competitor
  (SUBSCRIPTION_BILLING) was NOT significant (p=0.094; risk-difference 95% CI
  [-0.024, 0.346] includes zero) -- the informal non-overlapping-Wilson-CI
  argument above does not survive a proper significance test against the closest
  rival, even though ACCOUNT_ACCESS remains clearly separated from the other six
  intents (p<0.001 each). The finding was also shown to be sensitive to a
  pre-specified, equally-reasonable alternative reading of the DM/inbox trigger
  (an "inbox"-only variant collapses ACCOUNT_ACCESS's rate from 100% to 0%).

  Consequently, the rule's IMPLEMENTATION and evidence basis are retained
  UNCHANGED (see TIER2_ESCALATE_INTENTS and check_tier2b() below) as an
  experimental candidate, but it is DISABLED by default:
  TIER2_ACCOUNT_ACCESS_RULE_ENABLED = False. It does not fire in
  apply_triage_rules() unless a caller explicitly sets this flag to True (e.g. to
  reproduce the "with the rule" arm of a later comparison). A separate,
  documentation-only TIER2_ACCOUNT_ACCESS_RULE_VALIDATED = False marker records
  that this rule has not been validated against the human triage holdout --
  Part J (out of scope here, and NOT run in producing this module) will later
  compare policy behavior with and without this rule enabled, using the 40-example
  human triage set. That comparison has not happened yet; VALIDATED will not be
  set to True by this module and does not affect ENABLED's behavior.

=== TIER 3: explicitly unvalidated anger/emotional-language heuristic ===
Retained per the original §8 hypothesis, exactly as the plan states it: a minimal
keyword heuristic, explicitly labeled UNVALIDATED_ASSUMPTION, not backed by any
measurement in this project. May produce false positives on quoted text or
sarcasm (the plan's own caveat, restated here).

Run `python evaluation/triage.py` to reproduce the Tier-2B analysis (reads only the
cached sweep JSON; makes no API calls) and print/write its results.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.calibration import wilson_interval

K_ABLATION_SWEEP_PATH = config.EVAL_DIR / "k_ablation_sweep.json"
TIER2_ANALYSIS_OUTPUT_PATH = config.EVAL_DIR / "triage_tier2_dm_redirect_analysis.json"

AUTO_HANDLE = "AUTO_HANDLE"
HUMAN_ESCALATION = "HUMAN_ESCALATION"

TIER_1 = "TIER_1"
TIER_2 = "TIER_2"
TIER_3 = "TIER_3"
TIER_NONE = "NONE"


# =============================================================================
# Tier 1 -- deterministic policy rules
# =============================================================================

# Rule 1: UNKNOWN_OTHER handled directly in apply_triage_rules() (a value check,
# not a regex) -- config.FROZEN_LABELS already defines UNKNOWN_OTHER as the taxonomy's
# catch-all category.

# Rule 2: explicit account-compromise/security language. Conservative and small on
# purpose (per instructions: "do not invent a large taxonomy of risk categories") --
# matches only unambiguous compromise/unauthorized-access phrasing.
SECURITY_LANGUAGE_RE = re.compile(
    r"\bhack(ed|er|ing)?\b"
    r"|\bcompromis(ed|e)\b"
    r"|\bunauthorized access\b"
    r"|\bstole(n)? my account\b"
    r"|\bsomeone (accessed|logged into|is in|got into) my account\b",
    re.IGNORECASE,
)

# Rule 3: explicit legal/high-risk language. Same conservative-and-small principle.
LEGAL_LANGUAGE_RE = re.compile(
    r"\bsue\b|\bsuing\b|\blawsuit\b|\blawyer\b|\battorney\b|\blegal action\b|\bsubpoena\b|\bgdpr\b",
    re.IGNORECASE,
)


def check_tier1(customer_text, classified_intent):
    """Returns a (decision, reason, rule_id) tuple if a Tier-1 rule fires, else None.
    Checked in a fixed order: UNKNOWN_OTHER, then security language, then legal
    language -- first match wins (all three map to the same decision, so order only
    affects which rule_id/reason is reported, not the outcome)."""
    if classified_intent == "UNKNOWN_OTHER":
        return (
            HUMAN_ESCALATION,
            "Classified intent is UNKNOWN_OTHER -- policy: do not auto-respond when uncertain.",
            "TIER1_UNKNOWN_INTENT",
        )
    if SECURITY_LANGUAGE_RE.search(customer_text or ""):
        return (
            HUMAN_ESCALATION,
            "Customer message contains explicit account-compromise/security language -- "
            "security issues require human judgment (universal safety policy).",
            "TIER1_SECURITY_LANGUAGE",
        )
    if LEGAL_LANGUAGE_RE.search(customer_text or ""):
        return (
            HUMAN_ESCALATION,
            "Customer message contains explicit legal/high-risk language -- legal risk "
            "requires human judgment (universal safety policy).",
            "TIER1_LEGAL_LANGUAGE",
        )
    return None


# =============================================================================
# Tier 2A -- confidence threshold: TESTED AND REJECTED (documented, not implemented)
# =============================================================================

CONFIDENCE_THRESHOLD_REJECTED = True  # left in place as an explicit, inspectable
# marker (not a knob) that this hypothesis was tested, not silently skipped. See
# evaluation/CALIBRATION_RESULTS.md section 7 for the full evidence and reasoning:
# the classifier is overconfident in every one of 5 quantile buckets (n=40 each),
# with Wilson 95% CIs spanning 15-30 points and ECE=0.14 / Brier=0.166 -- not
# defensible grounds for a hard cutoff. Confidence is accepted as an optional
# advisory input to apply_triage_rules() but is NEVER compared against a threshold
# and NEVER by itself determines the decision.


# =============================================================================
# Tier 2B -- intent-specific escalation via historical DM-redirect rate
# =============================================================================

# --- The heuristic (written down BEFORE any per-intent rate was computed; not
# revised after seeing results -- see the milestone report for the corpus scan that
# informed this design and the two heuristics considered and rejected before
# settling on this one). ---
#
# Positive signal: the historical brand reply mentions "DM", "direct message", or
# "inbox" (case-insensitive) -- this is the dominant, near-universal phrasing this
# corpus uses for "contact us privately" (confirmed by a pre-analysis frequency scan:
# alternate phrasings like "private message", "PM", "message us", "reach out" were
# each found in <2% of the corpus and were excluded to keep the pattern small).
CONTACT_REDIRECT_RE = re.compile(r"\bdm\b|\bdirect message\b|\binbox\b", re.IGNORECASE)

# Override signal (DM mentioned, but reply is still SUBSTANTIVE): the reply also
# contains a t.co URL introduced by a referential cue (a colon, or "at"/"here"/"via"/
# "under"/"through" immediately before it) -- the same cue-based signal already
# established and tested in evaluation/generation.py's clean_brand_text() to
# distinguish a referenced, substantive resource link from a bare boilerplate
# tracking link. Restated here (not imported) to keep this module self-contained;
# the underlying logic and its rationale are identical -- see that module's
# docstring for the full corpus evidence behind it.
_TCO_URL_RE = re.compile(r"https?://t\.co/\S+")
_URL_CONTEXT_CUE_RE = re.compile(r"(:|\bat\b|\bhere\b|\bvia\b|\bunder\b|\bthrough\b)\s*$", re.IGNORECASE)

DM_REDIRECT = "DM_REDIRECT"
SUBSTANTIVE = "SUBSTANTIVE"


def classify_historical_reply(brand_text_raw):
    """Deterministic DM-redirect classifier for ONE historical brand reply.

    Rule (fixed, see module docstring for the pre-analysis that produced it):
      1. No DM/direct-message/inbox mention at all -> SUBSTANTIVE.
      2. DM/direct-message/inbox mentioned, AND the reply also contains a
         cue-introduced (referenced) URL -> SUBSTANTIVE (the DM ask is not the
         reply's only substantive content).
      3. DM/direct-message/inbox mentioned, no cue-introduced URL -> DM_REDIRECT.
    """
    text = brand_text_raw or ""
    if not CONTACT_REDIRECT_RE.search(text):
        return SUBSTANTIVE
    for m in _TCO_URL_RE.finditer(text):
        if _URL_CONTEXT_CUE_RE.search(text[: m.start()]):
            return SUBSTANTIVE
    return DM_REDIRECT


def check_no_api_spend_required():
    """This Tier-2B analysis reads ONLY the already-cached
    evaluation/results/k_ablation_sweep.json -- it never calls retrieve_top_k() or
    any embedding/LLM API. Raises FileNotFoundError with a clear message if that
    cached artifact is missing (nothing to recompute it with here -- recomputing it
    would require API calls, which this module refuses to make)."""
    if not K_ABLATION_SWEEP_PATH.exists():
        raise FileNotFoundError(
            f"{K_ABLATION_SWEEP_PATH} not found. This module reads ONLY this "
            "already-cached artifact for Tier-2B evidence and will not call any "
            "API to regenerate it. Zero-spend requirement: refusing to proceed."
        )
    return True


def compute_dm_redirect_breakdown(k=5):
    """Returns (per_reply_by_intent, per_example_by_intent): two dicts, each
    intent -> stats, computed from evaluation/results/k_ablation_sweep.json's
    k=<k> records ONLY (default k=5, the full top-5 retrieval -- already cached,
    zero API calls). per_reply_by_intent treats each retrieved reply as its own
    trial (n up to 5x the example count -- NOT statistically independent, reported
    for completeness/comparison). per_example_by_intent treats each GOLDEN EXAMPLE
    as one independent trial (majority-vote label across its up to 5 retrieved
    replies), which is the statistically correct unit for the per-intent Wilson CI
    used in the adoption decision.
    """
    check_no_api_spend_required()
    with open(K_ABLATION_SWEEP_PATH, encoding="utf-8") as f:
        sweep = json.load(f)
    records = [r for r in sweep["records"] if r["k"] == k]

    per_reply = defaultdict(lambda: {"n": 0, "dm": 0, "sub": 0})
    per_example = defaultdict(lambda: {"n": 0, "dm_majority": 0})

    for r in records:
        intent = r["classified_intent"]
        labels = [classify_historical_reply(ev["brand_text_raw"]) for ev in r["retrieved_evidence"]]
        n_items = len(labels)
        n_dm = sum(1 for l in labels if l == DM_REDIRECT)

        per_reply[intent]["n"] += n_items
        per_reply[intent]["dm"] += n_dm
        per_reply[intent]["sub"] += n_items - n_dm

        per_example[intent]["n"] += 1
        if n_items > 0 and n_dm >= (n_items / 2):  # majority of the retrieved replies
            per_example[intent]["dm_majority"] += 1

    def with_ci(d, dm_key):
        out = {}
        for intent, stats in d.items():
            n, dm = stats["n"], stats[dm_key]
            lo, hi = wilson_interval(dm, n)
            out[intent] = dict(stats, rate=(dm / n if n else float("nan")), wilson_lo=lo, wilson_hi=hi)
        return out

    return with_ci(per_reply, "dm"), with_ci(per_example, "dm_majority")


# The adopted Tier-2B rule, per the analysis above (see module docstring for the
# full evidentiary reasoning). Deliberately a short, explicit set -- easy to audit,
# easy to see this is NOT a learned/tuned rule. Rule text/heuristic/evidence basis
# are UNCHANGED from the original adoption -- only whether it FIRES is gated below.
TIER2_ESCALATE_INTENTS = {"ACCOUNT_ACCESS"}

# --- Experiment toggle (added after the Part H fragility audit) ---
#
# TIER2_ACCOUNT_ACCESS_RULE_ENABLED: the actual behavior switch. False (default) ->
# check_tier2b() never fires, regardless of TIER2_ESCALATE_INTENTS; True -> exactly
# the original, unmodified Tier-2B behavior. This is the ONLY thing that controls
# whether the rule fires -- see check_tier2b() below.
TIER2_ACCOUNT_ACCESS_RULE_ENABLED = False

# TIER2_ACCOUNT_ACCESS_RULE_VALIDATED: documentation/state only. Records whether
# this rule has been validated against the human triage holdout (Part J -- not run
# by this module). Must NOT be read by check_tier2b() or apply_triage_rules() and
# must NOT silently change behavior; it exists purely so a reviewer can see, next
# to ENABLED, that enabling this rule is not (yet) backed by holdout validation.
TIER2_ACCOUNT_ACCESS_RULE_VALIDATED = False


def check_tier2b(classified_intent):
    if not TIER2_ACCOUNT_ACCESS_RULE_ENABLED:
        return None
    if classified_intent in TIER2_ESCALATE_INTENTS:
        return (
            HUMAN_ESCALATION,
            "Historical retrieval evidence for ACCOUNT_ACCESS queries is overwhelmingly "
            "DM-redirect (100% of golden examples' majority-vote retrieved evidence, "
            "Wilson 95% CI [0.862, 1.000], n=24 examples; 82.5% at the individual-reply "
            "level, CI [0.747, 0.883], n=120) -- no other intent's CI overlaps this range "
            "at either granularity. There is essentially no historical precedent for a "
            "substantive public resolution for this intent. NOTE: a follow-up audit found "
            "this rule plausible but fragile (not significant vs. its closest competitor "
            "under Fisher's exact test, p=0.094); it is disabled by default and enabled "
            "here only because the caller explicitly set TIER2_ACCOUNT_ACCESS_RULE_ENABLED.",
            "TIER2_ACCOUNT_ACCESS_DM_HISTORY",
        )
    return None


# =============================================================================
# Tier 3 -- explicitly unvalidated anger/emotional-language heuristic
# =============================================================================

TIER3_RETAINED = True  # set False to disable this heuristic entirely

# UNVALIDATED_ASSUMPTION: per implementation_plan.md §8's own framing -- "Assumes
# keyword detection of extreme frustration is useful; may produce false positives on
# quoted text or sarcasm." No measurement in this project supports or refutes this.
# Kept deliberately minimal.
ANGER_LANGUAGE_RE = re.compile(
    r"\bfurious\b|\boutrageous\b|\bdisgusting\b|\bscam\b|\bridiculous\b",
    re.IGNORECASE,
)


def check_tier3(customer_text):
    if not TIER3_RETAINED:
        return None
    if ANGER_LANGUAGE_RE.search(customer_text or ""):
        return (
            HUMAN_ESCALATION,
            "UNVALIDATED_ASSUMPTION (Tier 3, per implementation_plan.md §8): customer "
            "message matches a minimal anger/emotional-language keyword list. This "
            "heuristic is NOT empirically validated in this project and may false-positive "
            "on quoted text or sarcasm.",
            "TIER3_ANGER_LANGUAGE_UNVALIDATED",
        )
    return None


# =============================================================================
# Main entry point
# =============================================================================

def apply_triage_rules(customer_text, classified_intent, confidence=None):
    """Applies Tier 1 -> Tier 2B -> Tier 3 in that fixed priority order, first match
    wins. Returns:
        {"decision": AUTO_HANDLE | HUMAN_ESCALATION,
         "reason": str,
         "tier": "TIER_1" | "TIER_2" | "TIER_3" | "NONE",
         "rule_id": str or None,
         "confidence_note": str}

    `confidence`, if given, is NEVER compared to a threshold and NEVER changes the
    decision by itself -- see CONFIDENCE_THRESHOLD_REJECTED. It is only echoed back
    as an advisory note for a human reviewer.

    The Tier-2B ACCOUNT_ACCESS rule is DISABLED BY DEFAULT
    (TIER2_ACCOUNT_ACCESS_RULE_ENABLED = False, module-level constant) -- a
    follow-up audit found it plausible but fragile (see module docstring). With
    the flag left at its default, this function's Tier-2B step never fires and
    behaves as if TIER2_ESCALATE_INTENTS were empty; flipping the module-level
    constant to True restores exactly the original Tier-2B behavior, unchanged.
    """
    confidence_note = (
        "No confidence signal provided." if confidence is None else
        f"Advisory only (Tier-2A confidence threshold tested and rejected -- see "
        f"evaluation/CALIBRATION_RESULTS.md): classifier confidence={confidence!r}. "
        f"This value did NOT influence the decision below."
    )

    tier1 = check_tier1(customer_text, classified_intent)
    if tier1:
        decision, reason, rule_id = tier1
        return dict(decision=decision, reason=reason, tier=TIER_1, rule_id=rule_id,
                    confidence_note=confidence_note)

    tier2b = check_tier2b(classified_intent)
    if tier2b:
        decision, reason, rule_id = tier2b
        return dict(decision=decision, reason=reason, tier=TIER_2, rule_id=rule_id,
                    confidence_note=confidence_note)

    tier3 = check_tier3(customer_text)
    if tier3:
        decision, reason, rule_id = tier3
        return dict(decision=decision, reason=reason, tier=TIER_3, rule_id=rule_id,
                    confidence_note=confidence_note)

    return dict(
        decision=AUTO_HANDLE,
        reason="No Tier 1, Tier 2, or Tier 3 escalation rule fired: intent is not "
               "UNKNOWN_OTHER, no security/legal language detected, no adopted "
               "intent-specific escalation rule applies, and no anger-language "
               "keyword matched.",
        tier=TIER_NONE,
        rule_id=None,
        confidence_note=confidence_note,
    )


# =============================================================================
# Reproducible Tier-2B analysis run
# =============================================================================

def main():
    per_reply, per_example = compute_dm_redirect_breakdown(k=5)

    print(f"{'intent':<22}{'n_reply':>9}{'dm_rate':>9}{'CI (per-reply)':>20}   "
          f"{'n_ex':>6}{'ex_rate':>9}{'CI (per-example)':>20}")
    for intent in sorted(per_reply):
        pr = per_reply[intent]
        pe = per_example[intent]
        print(f"{intent:<22}{pr['n']:>9}{pr['rate']:>9.3f}"
              f"   [{pr['wilson_lo']:.3f}, {pr['wilson_hi']:.3f}]"
              f"   {pe['n']:>6}{pe['rate']:>9.3f}"
              f"   [{pe['wilson_lo']:.3f}, {pe['wilson_hi']:.3f}]")

    print(f"\nExperimental Tier-2B intent-specific escalation rule (evidence basis): "
          f"{sorted(TIER2_ESCALATE_INTENTS)}")
    print(f"TIER2_ACCOUNT_ACCESS_RULE_ENABLED = {TIER2_ACCOUNT_ACCESS_RULE_ENABLED} "
          f"(default OFF -- see module docstring, Part H fragility audit)")
    print(f"TIER2_ACCOUNT_ACCESS_RULE_VALIDATED = {TIER2_ACCOUNT_ACCESS_RULE_VALIDATED} "
          f"(documentation only; Part J holdout comparison not yet run)")

    config.ensure_dirs()
    with open(TIER2_ANALYSIS_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dict(
            per_reply_by_intent=per_reply,
            per_example_by_intent=per_example,
            adopted_tier2_escalate_intents=sorted(TIER2_ESCALATE_INTENTS),
            tier2_account_access_rule_enabled=TIER2_ACCOUNT_ACCESS_RULE_ENABLED,
            tier2_account_access_rule_validated=TIER2_ACCOUNT_ACCESS_RULE_VALIDATED,
            heuristic="see evaluation/triage.py classify_historical_reply() docstring",
        ), f, indent=2)
    print(f"\nWrote {TIER2_ANALYSIS_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
