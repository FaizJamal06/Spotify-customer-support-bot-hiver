"""
Builds the 20-example manual retrieval-inspection scaffold (implementation_plan.md §9,
"Manual retrieval inspection"). This produces a CSV for Faiz to fill in BY HAND -- it does
NOT compute, infer, or pre-fill any of the four qualitative judgment columns.

Sampling procedure (fixed, documented, reproducible):
  1. Take all 200 tweet_ids from golden_set/GOLDEN_200_FINAL.csv, sorted ascending as
     integers (deterministic order -- never relies on file/dict iteration order).
  2. random.Random(config.RETRIEVAL_INSPECTION_SEED).sample(sorted_tweet_ids, config.RETRIEVAL_INSPECTION_SAMPLE_SIZE)
     -- seed=20, sample size=20, both in config.py.
This is independent of, and uses a different seed than, every other sampling step in the
project (golden-200 sampling, discovery sampling, retrieval-index subsampling, etc.).

For each of the 20 selected examples, the RAW top-5 retrieved pairs (evaluation.retrieval.
retrieve_top_k(), unmodified -- i.e. NOT passed through evaluation.generation.clean_brand_text(),
since this scaffold is about judging RETRIEVAL quality itself, not what the generator was
shown) are written out with similarity scores and identifiers.

Does NOT read golden_set/GOLDEN_200_FINAL.csv's human_gold_label or human_notes columns into
the output -- this is a human review of retrieval quality and is deliberately kept blind to
the gold intent label, to avoid anchoring the reviewer's judgment.

Usage:
    python evaluation/build_retrieval_inspection_scaffold.py

Writes:
    evaluation/results/retrieval_inspection_scaffold.csv
"""
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.retrieval import retrieve_top_k

SCAFFOLD_CSV_PATH = config.EVAL_DIR / "retrieval_inspection_scaffold.csv"

QUALITATIVE_COLUMNS = [
    "same_issue_yes_no",              # Is the retrieved customer message about the same issue? (yes/no + notes)
    "same_issue_notes",
    "response_type",                  # substantive / DM-redirect / other
    "would_agent_use_as_evidence",    # yes / partially / no
    "similarity_correlates_with_usefulness_notes",  # qualitative observation
]

FIELDNAMES = [
    "golden_tweet_id", "golden_customer_text",
    "rank", "similarity_score",
    "retrieved_customer_tweet_id", "retrieved_customer_text",
    "retrieved_brand_tweet_id", "retrieved_brand_text_raw",
    "retrieved_thread_id",
] + QUALITATIVE_COLUMNS


def load_golden_rows_raw():
    with open(config.GOLDEN_FINAL_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 200, f"Expected 200 golden rows, found {len(rows)}"
    return rows


def select_inspection_sample(golden_rows, seed=None, n=None):
    """Deterministic: sort all 200 tweet_ids ascending (int), then
    random.Random(seed).sample(sorted_ids, n). Returns the list of selected tweet_ids."""
    seed = config.RETRIEVAL_INSPECTION_SEED if seed is None else seed
    n = config.RETRIEVAL_INSPECTION_SAMPLE_SIZE if n is None else n
    sorted_ids = sorted((r["tweet_id"] for r in golden_rows), key=int)
    rng = random.Random(seed)
    return rng.sample(sorted_ids, n)


def build_scaffold_rows(golden_rows, selected_tweet_ids):
    by_id = {r["tweet_id"]: r for r in golden_rows}
    rows = []
    for tweet_id in selected_tweet_ids:
        golden_row = by_id[tweet_id]
        customer_text = golden_row["target_message"]
        retrieved = retrieve_top_k(customer_text, k=5)  # RAW retrieved pairs, unmodified
        for rank, (cust, brand, sim, meta) in enumerate(retrieved, start=1):
            row = dict(
                golden_tweet_id=tweet_id,
                golden_customer_text=customer_text,
                rank=rank,
                similarity_score=round(sim, 4),
                retrieved_customer_tweet_id=meta.get("customer_tweet_id"),
                retrieved_customer_text=cust,
                retrieved_brand_tweet_id=meta.get("brand_tweet_id"),
                retrieved_brand_text_raw=brand,
                retrieved_thread_id=meta.get("thread_id"),
            )
            for col in QUALITATIVE_COLUMNS:
                row[col] = ""  # genuinely blank -- for human review, never pre-filled
            rows.append(row)
    return rows


def main():
    config.ensure_dirs()
    golden_rows = load_golden_rows_raw()
    selected = select_inspection_sample(golden_rows)
    print(f"Selected {len(selected)} golden examples for manual retrieval inspection "
          f"(seed={config.RETRIEVAL_INSPECTION_SEED}): {selected}")

    rows = build_scaffold_rows(golden_rows, selected)
    print(f"Built {len(rows)} retrieval rows (top-5 per example; some examples may have fewer "
          f"than 5 if the index has fewer eligible matches).")

    with open(SCAFFOLD_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {SCAFFOLD_CSV_PATH}")
    print("\nAll five qualitative columns are blank, for Faiz's manual review -- "
          "nothing was pre-filled or inferred.")
    return rows


if __name__ == "__main__":
    main()
