"""
Hard leakage/data-boundary assertions for the baseline milestone.

These are assertions, not prints: they raise LeakageError if violated, and
callers (evaluation/run_baselines.py, tests) must not proceed past a failure.
"""


class LeakageError(AssertionError):
    pass


def assert_no_overlap(id_set_a, id_set_b, name_a, name_b, id_kind):
    overlap = id_set_a & id_set_b
    if overlap:
        raise LeakageError(
            f"LEAKAGE: {len(overlap)} {id_kind}(s) shared between {name_a} and {name_b}: "
            f"{sorted(overlap)[:10]}{' ...' if len(overlap) > 10 else ''}"
        )


def assert_no_leakage(train_examples, golden_examples, retrieval_tweet_ids, retrieval_thread_ids):
    """
    Asserts zero tweet_id/thread_id overlap, pairwise, across:
      - the 296 training examples (DEVELOPMENT pool)
      - the 200 golden examples (TEST pool)
      - the RETRIEVAL pool

    Raises LeakageError on any violation. Returns a small summary dict on success.
    """
    train_tweet_ids = {e["tweet_id"] for e in train_examples}
    train_thread_ids = {e["thread_id"] for e in train_examples}
    golden_tweet_ids = {e["tweet_id"] for e in golden_examples}
    golden_thread_ids = {e["thread_id"] for e in golden_examples}

    checks = [
        (train_tweet_ids, golden_tweet_ids, "training (DEV)", "golden (TEST)", "tweet_id"),
        (train_thread_ids, golden_thread_ids, "training (DEV)", "golden (TEST)", "thread_id"),
        (train_tweet_ids, retrieval_tweet_ids, "training (DEV)", "RETRIEVAL", "tweet_id"),
        (train_thread_ids, retrieval_thread_ids, "training (DEV)", "RETRIEVAL", "thread_id"),
        (golden_tweet_ids, retrieval_tweet_ids, "golden (TEST)", "RETRIEVAL", "tweet_id"),
        (golden_thread_ids, retrieval_thread_ids, "golden (TEST)", "RETRIEVAL", "thread_id"),
    ]
    for a, b, name_a, name_b, kind in checks:
        assert_no_overlap(a, b, name_a, name_b, kind)

    return dict(
        train_tweet_ids=len(train_tweet_ids), train_thread_ids=len(train_thread_ids),
        golden_tweet_ids=len(golden_tweet_ids), golden_thread_ids=len(golden_thread_ids),
        retrieval_tweet_ids=len(retrieval_tweet_ids), retrieval_thread_ids=len(retrieval_thread_ids),
        checks_passed=len(checks),
    )
