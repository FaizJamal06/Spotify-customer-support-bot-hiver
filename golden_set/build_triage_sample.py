"""
Builds the single, shared, deterministic 40-example stratified subset of
golden_set/GOLDEN_200_FINAL.csv, used for the triage annotation scaffold
(golden_set/TRIAGE_ANNOTATION_40.csv) and intended to be reused later for
judge calibration too (do not draw a second, different sample for that).

Stratified by human_gold_label, proportional to each class's share of the
200 golden examples, using the largest-remainder (Hamilton) apportionment
method so the 8 per-class counts sum to exactly 40. Ties in the remainder
step are broken deterministically by each label's position in
config.FROZEN_LABELS. The specific rows within each class are chosen with a single seeded RNG
(SEED=42, matching this project's existing seed convention -- see
config.BASELINE_SEED / config.LLM_SEED), consumed once per class in
config.FROZEN_LABELS order, applied to each class's rows sorted by
candidate_id, so the result is exactly reproducible.

Read-only with respect to golden_set/GOLDEN_200_FINAL.csv: this script only
reads that file. It writes golden_set/TRIAGE_ANNOTATION_40.csv (with
triage_decision / escalation_reason left blank -- never populated by this
or any other script) and prints the sample manifest for
TRIAGE_ANNOTATION_PROTOCOL.md.

Run: python golden_set/build_triage_sample.py
"""
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

SEED = 42
TARGET_TOTAL = 40

GOLDEN_CSV = Path(__file__).resolve().parent / "GOLDEN_200_FINAL.csv"
OUTPUT_CSV = Path(__file__).resolve().parent / "TRIAGE_ANNOTATION_40.csv"

HEADER_COMMENT = """\
# TRIAGE_ANNOTATION_40.csv
#
# This is a SEPARATE, ADDITIVE annotation layer on top of the frozen intent
# gold set (golden_set/GOLDEN_200_FINAL.csv). It does NOT modify that file
# or any of its 200 human_gold_label values.
#
# example_id, tweet_id, target_message, human_gold_label are copied
# read-only from GOLDEN_200_FINAL.csv, shown here per explicit approval --
# this is an additive triage layer on top of the existing intent gold, not
# a re-judgment of intent.
#
# triage_decision and escalation_reason are INTENTIONALLY BLANK. They are to
# be filled in by the human annotator (Faiz) only. No automated process may
# write to these columns, as a draft, suggestion, or inferred default, now
# or in any future run of this or any other script.
#
# notes is blank and optional, for the annotator's own use.
#
# Sampling method, seed, and the full example_id list are documented in
# golden_set/TRIAGE_ANNOTATION_PROTOCOL.md.
"""


def load_golden_rows():
    # utf-8-sig: GOLDEN_200_FINAL.csv is saved with a UTF-8 BOM (Excel export);
    # plain "utf-8" would leave the BOM glued onto the first header name
    # ("﻿candidate_id"), silently breaking every r["candidate_id"] lookup.
    with open(GOLDEN_CSV, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def compute_per_class_counts(rows_by_label, total, target_total=TARGET_TOTAL):
    """Largest-remainder (Hamilton) apportionment, proportional to class size,
    ties broken by position in config.FROZEN_LABELS."""
    exact = {lab: target_total * len(rows_by_label[lab]) / total for lab in config.FROZEN_LABELS}
    floors = {lab: int(exact[lab]) for lab in config.FROZEN_LABELS}
    remainders = {lab: exact[lab] - floors[lab] for lab in config.FROZEN_LABELS}
    allocated = sum(floors.values())
    remaining = target_total - allocated

    order = sorted(
        config.FROZEN_LABELS,
        key=lambda lab: (-remainders[lab], config.FROZEN_LABELS.index(lab)),
    )
    counts = dict(floors)
    for lab in order[:remaining]:
        counts[lab] += 1
    return counts, exact


def select_sample(rows, seed=SEED, target_total=TARGET_TOTAL):
    rows_by_label = defaultdict(list)
    for r in rows:
        rows_by_label[r["human_gold_label"]].append(r)

    for lab in config.FROZEN_LABELS:
        if lab not in rows_by_label or len(rows_by_label[lab]) == 0:
            raise ValueError(f"No golden examples found for label {lab!r} -- cannot stratify.")

    counts, exact = compute_per_class_counts(rows_by_label, len(rows), target_total)

    for lab, n in counts.items():
        available = len(rows_by_label[lab])
        if n > available:
            raise ValueError(
                f"Stratified target of {n} examples for label {lab!r} exceeds the "
                f"{available} available in golden-200 -- cannot stratify cleanly."
            )

    rng = random.Random(seed)
    selected = []
    for lab in config.FROZEN_LABELS:
        class_rows = sorted(rows_by_label[lab], key=lambda r: r["candidate_id"])
        chosen = rng.sample(class_rows, counts[lab])
        selected.extend(chosen)

    selected.sort(key=lambda r: r["candidate_id"])
    return selected, counts, exact


def write_triage_csv(selected, path=OUTPUT_CSV):
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(HEADER_COMMENT)
        writer = csv.writer(f)
        writer.writerow([
            "example_id", "tweet_id", "target_message", "human_gold_label",
            "triage_decision", "escalation_reason", "notes",
        ])
        for r in selected:
            writer.writerow([
                r["candidate_id"], r["tweet_id"], r["target_message"], r["human_gold_label"],
                "", "", "",
            ])


def main():
    rows = load_golden_rows()
    selected, counts, exact = select_sample(rows)

    print(f"Total golden rows: {len(rows)}")
    print(f"Per-class exact proportional targets: {exact}")
    print(f"Per-class final (largest-remainder) counts: {counts}, sum={sum(counts.values())}")
    print(f"Selected {len(selected)} example_ids (sorted): {[r['candidate_id'] for r in selected]}")

    write_triage_csv(selected)
    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
