"""
Deterministic few-shot demonstration selection for the LLM intent classifier.

Per the human decision on record: demonstrations are drawn from the 296-example
DEVELOPMENT discovery training set (discovery/HUMAN_REVIEW_labeled.md via
discovery/DISCOVERY_300_AUDIT.csv), restricted to rows where the audit's
`status` column equals "MATCH". Up to 5 (minimum 3) per intent, sorted by
example_id ascending -- no randomness. The resulting set is FIXED for the
entire evaluation run; it is never varied per query and never touches the
200 golden TEST examples.

Reuses evaluation/data_loading.py's existing text/label join (frozen,
unmodified) for the underlying 296 examples; this module only adds the
MATCH-status filtering and per-intent selection on top of that.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.data_loading import load_training_examples
from evaluation.leakage_checks import assert_no_overlap  # frozen module, reused not modified


class FewShotSelectionError(AssertionError):
    """Raised when an intent does not have enough MATCH-status candidates."""


def _load_audit_status_map():
    """example_id -> status ("MATCH"/"POSSIBLE"/"MISMATCH"/"UNRESOLVABLE"), read directly
    from discovery/DISCOVERY_300_AUDIT.csv (frozen; read-only). The first physical row is
    a leading comment; the real header is the second row (same layout as data_loading.py)."""
    with open(config.DISCOVERY_AUDIT_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        raw = list(csv.reader(f))
    header = raw[1]
    status_map = {}
    for r in raw[2:]:
        d = dict(zip(header, r))
        status_map[d["example_id"]] = d["status"]
    return status_map


def select_fewshot_demonstrations():
    """
    Returns (demonstrations, selection_log) where:
      demonstrations = dict: intent_label -> ordered list of
                        {example_id, tweet_id, thread_id, text, label} dicts
                        (sorted by example_id ascending, len in [FEWSHOT_MIN_PER_INTENT,
                        FEWSHOT_MAX_PER_INTENT]).
      selection_log   = dict: intent_label -> ordered list of example_id strings
                        (for the auditable results artifact).

    Raises FewShotSelectionError (without proceeding) if any of the 8 frozen intents
    has fewer than config.FEWSHOT_MIN_PER_INTENT MATCH-status candidates available.
    """
    examples, _excluded, _source = load_training_examples()  # the 296, frozen loader, reused as-is
    status_map = _load_audit_status_map()

    by_intent = {label: [] for label in config.FROZEN_LABELS}
    for ex in examples:
        status = status_map.get(ex["example_id"])
        if status != "MATCH":
            continue
        by_intent[ex["label"]].append(ex)

    # Deterministic order: sort by example_id ascending, numerically.
    for label in by_intent:
        by_intent[label].sort(key=lambda e: int(e["example_id"]))

    shortfalls = {
        label: len(rows) for label, rows in by_intent.items()
        if len(rows) < config.FEWSHOT_MIN_PER_INTENT
    }
    if shortfalls:
        raise FewShotSelectionError(
            "Cannot select few-shot demonstrations -- the following intent(s) have fewer "
            f"than {config.FEWSHOT_MIN_PER_INTENT} MATCH-status candidates available: "
            f"{shortfalls}. Not proceeding; no substitution of POSSIBLE/MISMATCH rows was made."
        )

    demonstrations = {}
    selection_log = {}
    for label in config.FROZEN_LABELS:
        chosen = by_intent[label][:config.FEWSHOT_MAX_PER_INTENT]
        demonstrations[label] = chosen
        selection_log[label] = [e["example_id"] for e in chosen]

    return demonstrations, selection_log


def assert_fewshot_no_golden_leakage(demonstrations, golden_examples):
    """
    Explicit leakage assertion (extends evaluation/leakage_checks.py's existing pattern,
    without modifying that frozen module): zero tweet_id/thread_id overlap between the
    selected few-shot demonstration IDs and the 200 golden_set IDs. This is expected to
    already hold structurally (demonstrations are a subset of the 296 DEVELOPMENT-pool
    training examples, and DEVELOPMENT/TEST are disjoint pools), but is asserted here
    explicitly rather than assumed. Raises LeakageError (from evaluation.leakage_checks)
    on violation. Returns a small summary dict on success.
    """
    flat = flatten(demonstrations)
    demo_tweet_ids = {e["tweet_id"] for e in flat}
    demo_thread_ids = {e["thread_id"] for e in flat}
    golden_tweet_ids = {e["tweet_id"] for e in golden_examples}
    golden_thread_ids = {e["thread_id"] for e in golden_examples}

    assert_no_overlap(demo_tweet_ids, golden_tweet_ids, "few-shot demos", "golden (TEST)", "tweet_id")
    assert_no_overlap(demo_thread_ids, golden_thread_ids, "few-shot demos", "golden (TEST)", "thread_id")

    return dict(
        demo_tweet_ids=len(demo_tweet_ids), demo_thread_ids=len(demo_thread_ids),
        golden_tweet_ids=len(golden_tweet_ids), golden_thread_ids=len(golden_thread_ids),
        checks_passed=2,
    )


def flatten(demonstrations):
    """Flat list of all selected demonstration dicts, in FROZEN_LABELS then example_id order."""
    flat = []
    for label in config.FROZEN_LABELS:
        flat.extend(demonstrations[label])
    return flat
