"""
Audit of Part H's Tier-2B ACCOUNT_ACCESS evidence (implementation_plan.md §8), run
BEFORE committing that milestone. Does NOT redesign evaluation/triage.py's frozen
heuristic or adopted-rule set -- classify_historical_reply() is imported and used
UNMODIFIED throughout Part 1 and the ACCOUNT_ACCESS-vs-competitor test. Part 2's two
robustness variants are implemented as SEPARATE functions here, never by editing
evaluation/triage.py.

Zero new API/LLM/embedding calls: reads ONLY the already-cached
evaluation/results/k_ablation_sweep.json (same cache-preflight guard as
evaluation/triage.py -- see check_no_api_spend_required() there, reused here).

Hard holdout isolation: golden_set/TRIAGE_ANNOTATION_40.csv is never opened, read,
or referenced anywhere in this module.

Run: python evaluation/audit_triage_tier2.py
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from scipy.stats import fisher_exact
from statsmodels.stats.proportion import confint_proportions_2indep

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.calibration import wilson_interval
from evaluation.triage import K_ABLATION_SWEEP_PATH, check_no_api_spend_required, classify_historical_reply

AUDIT_OUTPUT_PATH = config.EVAL_DIR / "triage_tier2_audit.json"


# =============================================================================
# Shared loading (zero API calls -- cached sweep only)
# =============================================================================

def load_k5_records():
    check_no_api_spend_required()
    with open(K_ABLATION_SWEEP_PATH, encoding="utf-8") as f:
        sweep = json.load(f)
    return [r for r in sweep["records"] if r["k"] == 5]


def per_example_majority_labels(records, classify_fn):
    """intent -> list of 0/1 (1 = majority of its retrieved replies are DM_REDIRECT
    under classify_fn), one entry per golden example -- the genuinely independent
    unit used throughout this audit (per Part 1's instruction not to treat the 5
    correlated retrieved replies per example as independent trials)."""
    by_intent = defaultdict(list)
    for r in records:
        intent = r["classified_intent"]
        labels = [classify_fn(ev["brand_text_raw"]) for ev in r["retrieved_evidence"]]
        n = len(labels)
        n_dm = sum(1 for l in labels if l == "DM_REDIRECT")
        by_intent[intent].append(1 if (n > 0 and n_dm >= n / 2) else 0)
    return dict(by_intent)


def summarize(by_intent):
    out = {}
    for intent, vals in by_intent.items():
        n, dm = len(vals), sum(vals)
        lo, hi = wilson_interval(dm, n)
        out[intent] = dict(n=n, dm=dm, rate=dm / n if n else float("nan"), wilson_lo=lo, wilson_hi=hi)
    return out


# =============================================================================
# Two-proportion comparison (Part 1)
# =============================================================================

def two_proportion_comparison(n1, dm1, n2, dm2, label1, label2):
    """Fisher's exact test (chosen over a normal-approximation two-proportion
    z-test / chi-square because at least one cell in the observed contingency
    tables in this audit is 0 or near-0 with small n -- e.g. ACCOUNT_ACCESS's
    24/24 -- where the normal approximation underlying a z-test is not reliable;
    Fisher's exact test has no such requirement and is exact for any 2x2 table).
    Also reports the risk difference (dm1/n1 - dm2/n2) with a Newcombe-score 95%
    CI via statsmodels' confint_proportions_2indep (compare_type='diff'), which
    (unlike a Wald CI) stays well-behaved at proportions of exactly 0 or 1.
    """
    table = [[dm1, n1 - dm1], [dm2, n2 - dm2]]
    odds_ratio, p_value = fisher_exact(table, alternative="two-sided")

    rate1, rate2 = dm1 / n1, dm2 / n2
    diff = rate1 - rate2
    ci_lo, ci_hi = confint_proportions_2indep(
        dm1, n1, dm2, n2, method="newcomb", compare="diff",
    )

    return dict(
        label1=label1, n1=n1, dm1=dm1, rate1=rate1,
        label2=label2, n2=n2, dm2=dm2, rate2=rate2,
        contingency_table=table,
        test="Fisher's exact test (two-sided)",
        odds_ratio=float(odds_ratio), p_value=float(p_value),
        risk_difference=float(diff), diff_ci_lo=float(ci_lo), diff_ci_hi=float(ci_hi),
        diff_ci_method="Newcombe score interval (confint_proportions_2indep, compare='diff')",
    )


def run_all_pairwise_from_account_access(summary):
    """Runs the SAME Fisher's exact comparison between ACCOUNT_ACCESS and EVERY
    other intent (not just the strongest competitor) -- so the strongest-competitor
    comparison reported in Part 1 is demonstrably not a cherry-picked one-off."""
    aa = summary["ACCOUNT_ACCESS"]
    results = {}
    for intent, s in summary.items():
        if intent == "ACCOUNT_ACCESS":
            continue
        results[intent] = two_proportion_comparison(
            aa["n"], aa["dm"], s["n"], s["dm"], "ACCOUNT_ACCESS", intent,
        )
    return results


# =============================================================================
# Part 2: two PRE-SPECIFIED robustness variants of the frozen heuristic
# =============================================================================

# Variant A: "inbox" mention ALONE is sufficient for DM_REDIRECT -- the trigger no
# longer requires literal "dm" or "direct message" at all (narrows the base classify.py
# trigger set from {dm, direct message, inbox} down to {inbox} only). The substantive
# cue-override logic is otherwise UNCHANGED from evaluation.triage.classify_historical_reply.
_VARIANT_A_TRIGGER_RE = re.compile(r"\binbox\b", re.IGNORECASE)
_TCO_URL_RE = re.compile(r"https?://t\.co/\S+")
_URL_CONTEXT_CUE_RE_ORIGINAL = re.compile(r"(:|\bat\b|\bhere\b|\bvia\b|\bunder\b|\bthrough\b)\s*$", re.IGNORECASE)


def classify_variant_a(brand_text_raw):
    text = brand_text_raw or ""
    if not _VARIANT_A_TRIGGER_RE.search(text):
        return "SUBSTANTIVE"
    for m in _TCO_URL_RE.finditer(text):
        if _URL_CONTEXT_CUE_RE_ORIGINAL.search(text[: m.start()]):
            return "SUBSTANTIVE"
    return "DM_REDIRECT"


# Variant B: keep the original {dm, direct message, inbox} trigger, but remove ONE
# referential cue ("via") from the substantive-link override, so a "via <URL>" no
# longer counts as evidence the reply references specific substantive content.
_ORIGINAL_TRIGGER_RE = re.compile(r"\bdm\b|\bdirect message\b|\binbox\b", re.IGNORECASE)
_URL_CONTEXT_CUE_RE_VARIANT_B = re.compile(r"(:|\bat\b|\bhere\b|\bunder\b|\bthrough\b)\s*$", re.IGNORECASE)  # "via" removed


def classify_variant_b(brand_text_raw):
    text = brand_text_raw or ""
    if not _ORIGINAL_TRIGGER_RE.search(text):
        return "SUBSTANTIVE"
    for m in _TCO_URL_RE.finditer(text):
        if _URL_CONTEXT_CUE_RE_VARIANT_B.search(text[: m.start()]):
            return "SUBSTANTIVE"
    return "DM_REDIRECT"


def run_variant(records, classify_fn, variant_name):
    by_intent = per_example_majority_labels(records, classify_fn)
    summary = summarize(by_intent)
    ranked = sorted(summary.items(), key=lambda kv: kv[1]["rate"], reverse=True)
    aa_rank = next(i for i, (intent, _) in enumerate(ranked, start=1) if intent == "ACCOUNT_ACCESS")
    strongest_competitor = next(intent for intent, _ in ranked if intent != "ACCOUNT_ACCESS")

    aa = summary["ACCOUNT_ACCESS"]
    comp = summary[strongest_competitor]
    comparison = two_proportion_comparison(
        aa["n"], aa["dm"], comp["n"], comp["dm"], "ACCOUNT_ACCESS", strongest_competitor,
    )
    return dict(
        variant=variant_name,
        per_intent=summary,
        ranked_intents=[intent for intent, _ in ranked],
        account_access_rank=aa_rank,
        strongest_competitor=strongest_competitor,
        comparison_vs_strongest_competitor=comparison,
    )


# =============================================================================
# Main
# =============================================================================

def main():
    records = load_k5_records()

    # --- Part 1: original heuristic, ACCOUNT_ACCESS vs all others ---
    original_by_intent = per_example_majority_labels(records, classify_historical_reply)
    original_summary = summarize(original_by_intent)
    all_pairwise = run_all_pairwise_from_account_access(original_summary)

    strongest_competitor = max(
        (intent for intent in original_summary if intent != "ACCOUNT_ACCESS"),
        key=lambda intent: original_summary[intent]["rate"],
    )
    primary_comparison = all_pairwise[strongest_competitor]

    print("=== Part 1: ACCOUNT_ACCESS vs strongest competitor (original heuristic) ===")
    print(f"ACCOUNT_ACCESS: n={primary_comparison['n1']} dm={primary_comparison['dm1']} rate={primary_comparison['rate1']:.4f}")
    print(f"{strongest_competitor}: n={primary_comparison['n2']} dm={primary_comparison['dm2']} rate={primary_comparison['rate2']:.4f}")
    print(f"Test: {primary_comparison['test']}")
    print(f"p-value = {primary_comparison['p_value']:.4f}")
    print(f"Risk difference = {primary_comparison['risk_difference']:.4f}, "
          f"95% CI [{primary_comparison['diff_ci_lo']:.4f}, {primary_comparison['diff_ci_hi']:.4f}]")

    print("\n=== Part 1b: ACCOUNT_ACCESS vs every other intent (uniform application) ===")
    for intent, comp in sorted(all_pairwise.items(), key=lambda kv: kv[1]["p_value"]):
        print(f"  vs {intent:<22} p={comp['p_value']:.4f}  diff={comp['risk_difference']:.4f}  "
              f"CI=[{comp['diff_ci_lo']:.4f}, {comp['diff_ci_hi']:.4f}]")

    # --- Part 2: robustness variants ---
    variant_a_result = run_variant(records, classify_variant_a, "A_inbox_only_trigger")
    variant_b_result = run_variant(records, classify_variant_b, "B_no_via_cue")

    print("\n=== Part 2: Variant A (inbox-only trigger) ===")
    aa_a = variant_a_result["per_intent"]["ACCOUNT_ACCESS"]
    print(f"ACCOUNT_ACCESS: n={aa_a['n']} dm={aa_a['dm']} rate={aa_a['rate']:.4f}  "
          f"rank={variant_a_result['account_access_rank']}  "
          f"vs {variant_a_result['strongest_competitor']} "
          f"p={variant_a_result['comparison_vs_strongest_competitor']['p_value']:.4f}")

    print("\n=== Part 2: Variant B (no 'via' cue) ===")
    aa_b = variant_b_result["per_intent"]["ACCOUNT_ACCESS"]
    print(f"ACCOUNT_ACCESS: n={aa_b['n']} dm={aa_b['dm']} rate={aa_b['rate']:.4f}  "
          f"rank={variant_b_result['account_access_rank']}  "
          f"vs {variant_b_result['strongest_competitor']} "
          f"p={variant_b_result['comparison_vs_strongest_competitor']['p_value']:.4f}")

    config.ensure_dirs()
    with open(AUDIT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dict(
            original=dict(
                per_intent=original_summary,
                strongest_competitor=strongest_competitor,
                primary_comparison=primary_comparison,
                all_pairwise_from_account_access=all_pairwise,
            ),
            variant_a=variant_a_result,
            variant_b=variant_b_result,
        ), f, indent=2)
    print(f"\nWrote {AUDIT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
