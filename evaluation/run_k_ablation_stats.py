"""
Reads the completed full-sweep results (evaluation/results/k_ablation_sweep.json, produced
by evaluation/run_k_ablation_sweep.py) and produces:
  - the 12 pre-specified paired Wilcoxon comparisons (evaluation.k_ablation_stats), with
    Holm-Bonferroni-adjusted p-values
  - descriptive per-k judge-score summaries
  - evidence-cleaning (Part 1) prevalence stats across the real sweep
  - the final report: evaluation/K_ABLATION_SWEEP_RESULTS.md

Does NOT select a "best k" before the full 12-comparison table is written; does not touch
golden_set/GOLDEN_200_FINAL.csv or make any additional API calls.

Usage:
    python evaluation/run_k_ablation_stats.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.k_ablation_stats import DIMENSIONS, TREATMENT_KS, run_all_comparisons

SWEEP_RESULTS_PATH = config.EVAL_DIR / "k_ablation_sweep.json"
STATS_RESULTS_PATH = config.EVAL_DIR / "k_ablation_stats_results.json"
REPORT_MD_PATH = config.PROJECT_ROOT / "evaluation" / "K_ABLATION_SWEEP_RESULTS.md"


def descriptive_by_k(records):
    sums = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(int)
    for r in records:
        counts[r["k"]] += 1
        for dim, val in r["judge_scores"].items():
            sums[r["k"]][dim] += val
    out = {}
    for k in sorted(counts):
        out[k] = dict(n=counts[k], **{dim: sums[k][dim] / counts[k] for dim in DIMENSIONS})
    return out


def evidence_cleaning_stats(records):
    total_items = 0
    removed_by_kind = defaultdict(int)
    for r in records:
        for ev in r["retrieved_evidence"]:
            total_items += 1
            for art in ev["removed_artifacts"]:
                removed_by_kind[art["kind"]] += 1
    return dict(total_evidence_items=total_items, removed_by_kind=dict(removed_by_kind))


def _comparisons_table_md(comparisons):
    lines = [
        "| k vs 0 | Dimension | n | Mean k=0 | Mean k | Statistic | z | Effect r | p (raw) | p (Holm) | Direction |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for c in comparisons:
        lines.append(
            f"| k={c['k']} | {c['dimension']} | {c['n']} | {c['baseline_mean']:.3f} | {c['treatment_mean']:.3f} | "
            f"{c['statistic']:.1f} | {c['zstatistic']:.3f} | {c['effect_size_r']:.3f} | "
            f"{c['pvalue']:.6f} | {c['pvalue_holm_adjusted']:.6f} | {c['direction']} |"
        )
    return "\n".join(lines)


def _descriptive_table_md(desc):
    lines = ["| k | n | Relevance | Groundedness | Helpfulness | Tone |", "|---|---:|---:|---:|---:|---:|"]
    for k, row in desc.items():
        lines.append(f"| {k} | {row['n']} | {row['relevance']:.3f} | {row['groundedness']:.3f} | "
                      f"{row['helpfulness']:.3f} | {row['tone']:.3f} |")
    return "\n".join(lines)


def main():
    with open(SWEEP_RESULTS_PATH, encoding="utf-8") as f:
        sweep = json.load(f)
    records = sweep["records"]

    if sweep["n_failures"] != 0 or not sweep["integrity"]["all_checks_passed"]:
        print("STOP: sweep did not complete cleanly (failures or failed integrity checks). "
              "Not computing statistics on a compromised result set.")
        sys.exit(1)

    desc = descriptive_by_k(records)
    cleaning_stats = evidence_cleaning_stats(records)
    comparisons = run_all_comparisons(records)  # all 12, fixed order, no post-hoc selection

    stats_results = dict(
        n_comparisons=len(comparisons),
        dimensions=list(DIMENSIONS),
        treatment_ks=list(TREATMENT_KS),
        baseline_k=0,
        multiple_comparisons_method="Holm-Bonferroni (family-wise error rate, step-down)",
        descriptive_by_k=desc,
        evidence_cleaning_stats=cleaning_stats,
        comparisons=comparisons,
    )
    with open(STATS_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats_results, f, indent=2)
    print(f"Wrote {STATS_RESULTS_PATH}")

    n_sig_raw = sum(1 for c in comparisons if c["significant_raw_p_lt_05"])
    n_sig_holm = sum(1 for c in comparisons if c["significant_holm_adjusted_p_lt_05"])

    content = f"""# Retrieval k-Ablation: Full 200x4 Sweep Results

Generated from `evaluation/results/k_ablation_sweep.json` (800/800 conditions, 0 failures,
all integrity checks passed) via `evaluation/run_k_ablation_stats.py`.

## Sweep configuration

| Setting | Value |
|---|---|
| GENERATE_MODEL | `{sweep['config']['generate_model']}` |
| JUDGE_MODEL | `{sweep['config']['judge_model']}` |
| temperature / seed / reasoning_effort | {sweep['config']['temperature']} / {sweep['config']['seed']} / `{sweep['config']['reasoning_effort']}` |
| max_workers | {sweep['config']['max_workers']} |
| k conditions | {sweep['config']['k_conditions']} |
| n examples x k conditions | {sweep['n_examples']} x {len(sweep['config']['k_conditions'])} = {sweep['n_records']} |
| Elapsed (concurrent phase) | {sweep['elapsed_seconds']}s |

## Evidence-cleaning (Part 1) prevalence across the real sweep

Out of {cleaning_stats['total_evidence_items']} total retrieved evidence items shown to the
generator/judge across all k>0 conditions:

{chr(10).join(f"- **{kind}**: {count} removed ({count/cleaning_stats['total_evidence_items']*100:.1f}% of all evidence items)" for kind, count in cleaning_stats['removed_by_kind'].items())}

## Descriptive judge scores by k (all 200 examples, mean of 1-5 scale)

{_descriptive_table_md(desc)}

## Full 12-comparison paired Wilcoxon table

12 pre-specified comparisons (3 treatment k values x 4 judge dimensions), each a paired
Wilcoxon signed-rank test vs. the k=0 baseline over the same 200 examples. All 12 are
reported below in the fixed order they were run -- no post-hoc "best k" selection.

{_comparisons_table_md(comparisons)}

**{n_sig_raw}/12 comparisons significant at raw p<0.05; {n_sig_holm}/12 remain significant after
Holm-Bonferroni adjustment.**

## Multiple comparisons

12 non-independent tests were run (4 judge dimensions scored from the same call are
correlated; k=1/3/5 all share the same k=0 baseline scores). Holm-Bonferroni was applied
across all 12 raw p-values to control the family-wise error rate; it does not require
independence between tests (unlike some alternatives) and is less conservative than plain
Bonferroni. Both raw and Holm-adjusted p-values are reported for every comparison above --
neither is hidden.
"""
    with open(REPORT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote {REPORT_MD_PATH}")
    return stats_results


if __name__ == "__main__":
    main()
