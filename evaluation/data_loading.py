"""
Data loading for the intent-classification baseline milestone.

Loads:
  - the 296 usable DISCOVERY-phase training labels (from discovery/DISCOVERY_300_AUDIT.csv
    if present, else by re-parsing discovery/HUMAN_REVIEW_labeled.md directly)
  - the 200 golden TEST examples (evaluation-only)
  - the RETRIEVAL pool's tweet/thread IDs (for leakage checks only -- never used as data)

Nothing in this module modifies discovery/HUMAN_REVIEW_labeled.md,
discovery/DISCOVERY_300_AUDIT.csv, golden_set/GOLDEN_200_FINAL.csv, or
discovery/TAXONOMY_REVIEW_GUIDE.md. All of those are read-only inputs.

Per explicit human decision, the 300 discovery labels are used AS-IS for
training -- this module never corrects, adjudicates, or imputes a label.
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

# The known-verified result of the Step 1 parsing rule (see discovery/DISCOVERY_300_AUDIT_REPORT.md).
# Training must not proceed if re-deriving this split yields anything different.
EXPECTED_TOTAL = 300
EXPECTED_VALID_COUNT = 296
EXPECTED_EXCLUDED_IDS = {"70", "78", "164", "265"}


class DiscoverySplitMismatch(AssertionError):
    """Raised when the discovery label split does not match the known-verified result."""


def _load_from_audit_csv(path):
    """Path 1: discovery/DISCOVERY_300_AUDIT.csv exists -- use its existing_human_label column."""
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        raw = list(csv.reader(f))
    # First physical row is a leading comment (see discovery/DISCOVERY_300_AUDIT_REPORT.md);
    # the real header is the second row.
    header = raw[1]
    for r in raw[2:]:
        d = dict(zip(header, r))
        example_id = d["example_id"]
        label = d["existing_human_label"]
        if label == "UNPARSEABLE":
            rows.append(dict(example_id=example_id, tweet_id=d["tweet_id"], label=None))
        else:
            rows.append(dict(example_id=example_id, tweet_id=d["tweet_id"], label=label))
    return rows


def _split_row_cells(block_text):
    """Backtick-aware pipe splitter (a literal '|' inside a backtick-quoted cell is not a delimiter)."""
    cells, cur, in_bt = [], [], False
    for ch in block_text:
        if ch == "`":
            in_bt = not in_bt
            cur.append(ch)
        elif ch == "|" and not in_bt:
            cells.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    cells.append("".join(cur))
    return cells


def _load_from_human_review_md(path):
    """
    Path 2: re-parse discovery/HUMAN_REVIEW_labeled.md directly (used only if the audit CSV
    is absent). Table rows can span multiple physical lines (embedded blank lines inside a
    cell), so rows are located by a row-start marker and read as one block, not line-by-line.
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    row_start_re = re.compile(r"(?m)^\|\s*\d+\s*\|")
    starts = [m.start() for m in row_start_re.finditer(content)]
    blocks = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(content)
        blocks.append(content[s:e].rstrip("\n"))

    rows = []
    for block in blocks:
        cells = _split_row_cells(block)
        if cells and cells[0].strip() == "":
            cells = cells[1:]
        if cells and cells[-1].strip() == "":
            cells = cells[:-1]
        cells = [c.strip() for c in cells]
        # Columns: Ex | Tweet ID | Prior Context | Customer Message | Provisional Group |
        #          Potential Issue/Boundary | UNKNOWN Subtype Flags | Human Decision / Gold Label
        example_id, tweet_id = cells[0], cells[1]
        unknown_subtype_flags, human_decision = cells[6], cells[7]

        # Preference order: Human Decision / Gold Label first, then UNKNOWN Subtype Flags.
        # Provisional Group and Potential Issue/Boundary are never label candidates.
        label = None
        if human_decision in config.FROZEN_LABELS:
            label = human_decision
        elif unknown_subtype_flags in config.FROZEN_LABELS:
            label = unknown_subtype_flags

        rows.append(dict(example_id=example_id, tweet_id=tweet_id, label=label))
    return rows


def load_discovery_rows():
    """
    Implements the deterministic loading rule:
      1. Use discovery/DISCOVERY_300_AUDIT.csv if present.
      2. Otherwise re-parse discovery/HUMAN_REVIEW_labeled.md directly.
    Returns a list of dicts: {example_id, tweet_id, label} where label is None for excluded rows.
    """
    if config.DISCOVERY_AUDIT_CSV_PATH.exists():
        rows = _load_from_audit_csv(config.DISCOVERY_AUDIT_CSV_PATH)
        source = "discovery/DISCOVERY_300_AUDIT.csv"
    else:
        rows = _load_from_human_review_md(config.DISCOVERY_HUMAN_REVIEW_PATH)
        source = "discovery/HUMAN_REVIEW_labeled.md (re-parsed)"
    return rows, source


def assert_expected_split(rows):
    """
    Hard assertion (Step 3 of the loading rule): exactly 296/300 rows must resolve to a
    valid label, and the excluded set must be exactly {Ex 70, Ex 78, Ex 164, Ex 265}.
    Raises DiscoverySplitMismatch with the actual counts/IDs if this does not hold --
    callers must not proceed with training in that case.
    """
    if len(rows) != EXPECTED_TOTAL:
        raise DiscoverySplitMismatch(
            f"Expected {EXPECTED_TOTAL} discovery rows, found {len(rows)}."
        )
    excluded_ids = {r["example_id"] for r in rows if r["label"] is None}
    valid_count = len(rows) - len(excluded_ids)
    if valid_count != EXPECTED_VALID_COUNT or excluded_ids != EXPECTED_EXCLUDED_IDS:
        raise DiscoverySplitMismatch(
            f"Discovery label split does not match the known-verified result.\n"
            f"  Expected: {EXPECTED_VALID_COUNT} valid / excluded={sorted(EXPECTED_EXCLUDED_IDS, key=int)}\n"
            f"  Found:    {valid_count} valid / excluded={sorted(excluded_ids, key=int)}"
        )
    bad_labels = {r["label"] for r in rows if r["label"] is not None} - set(config.FROZEN_LABELS)
    if bad_labels:
        raise DiscoverySplitMismatch(f"Non-frozen labels found in discovery rows: {bad_labels}")


def _load_dev_pairs_index():
    """tweet_id -> {customer_text, thread_id} for every DEVELOPMENT-pool pair."""
    index = {}
    with open(config.DEV_PAIRS_PATH, encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            index[str(p["customer_tweet_id"])] = dict(
                customer_text=p["customer_text"], thread_id=str(p["thread_id"])
            )
    return index


def load_training_examples():
    """
    Returns (examples, excluded, source) where:
      examples = list of dicts {example_id, tweet_id, thread_id, text, label} for the
                 296 usable discovery examples (label != None), text/thread_id joined in
                 from data/generated/dev_pairs.jsonl by tweet_id.
      excluded = list of example_ids excluded because their source label was unparseable
                 (never given an inferred/default label).
      source   = which loading path was used, for the results report.
    Raises DiscoverySplitMismatch if the split does not match the known-verified result.
    """
    rows, source = load_discovery_rows()
    assert_expected_split(rows)

    dev_index = _load_dev_pairs_index()
    examples = []
    excluded = []
    for r in rows:
        if r["label"] is None:
            excluded.append(r["example_id"])
            continue
        info = dev_index.get(r["tweet_id"])
        if info is None:
            raise DiscoverySplitMismatch(
                f"Ex {r['example_id']} (tweet {r['tweet_id']}) has a label but was not found "
                f"in data/generated/dev_pairs.jsonl -- cannot build a training example for it."
            )
        examples.append(dict(
            example_id=r["example_id"], tweet_id=r["tweet_id"], thread_id=info["thread_id"],
            text=info["customer_text"], label=r["label"],
        ))

    assert len(examples) == EXPECTED_VALID_COUNT
    assert set(excluded) == EXPECTED_EXCLUDED_IDS
    return examples, sorted(excluded, key=int), source


def load_golden_examples():
    """Returns list of dicts {tweet_id, thread_id, text, label} for the 200 golden TEST examples.
    Evaluation-only: never used for fitting/training/vocabulary/tuning."""
    with open(config.GOLDEN_FINAL_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 200, f"Expected 200 golden examples, found {len(rows)}"
    examples = []
    for r in rows:
        examples.append(dict(
            tweet_id=r["tweet_id"], thread_id=r["thread_id"],
            text=r["target_message"], label=r["human_gold_label"],
        ))
    bad = {e["label"] for e in examples} - set(config.FROZEN_LABELS)
    assert not bad, f"Non-frozen labels found in golden set: {bad}"
    return examples


def load_retrieval_ids():
    """Returns (tweet_ids: set[str], thread_ids: set[str]) for the RETRIEVAL pool.
    Used only for leakage checks -- the RETRIEVAL pool itself is never loaded as data."""
    tweet_ids, thread_ids = set(), set()
    with open(config.RETRIEVAL_PAIRS_PATH, encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            tweet_ids.add(str(p["customer_tweet_id"]))
            thread_ids.add(str(p["thread_id"]))
    return tweet_ids, thread_ids
