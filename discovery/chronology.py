"""
Shared chronology utility for constructing target-message context.

Background
----------
`data/generated/spotify_threads.jsonl` stores each thread's `messages` list
sorted by `tweet_id` (see `data/prepare.py::build_thread_records`), NOT by
`created_at`. Twitter's numeric tweet IDs are only approximately chronological
(Snowflake ID generation can produce out-of-order IDs across tweets), so
consumers must NOT assume list order in `spotify_threads.jsonl` is
chronological order. Any code that needs "what did the customer/brand know
before this message" must sort by `created_at` explicitly, using this module.

This is the corrected logic originally implemented directly inside
`discovery/create_pilot.py`. It is now centralized here so future consumers
(e.g. a golden-set sampler) reuse a single, tested implementation instead of
re-deriving it.

Rules enforced by `get_target_context`:
- Only messages from the same thread are considered (the caller passes in
  that thread's `messages` list; this function does not cross thread
  boundaries).
- The target message itself is excluded from its own context.
- A message is included only if it occurs strictly before the target by
  `created_at`.
- `created_at` is the primary chronology key. `tweet_id` is used only as a
  deterministic tiebreak for messages with an identical `created_at`.
- No message occurring at or after the target's `created_at` is ever
  included — this excludes later customer messages, later brand messages,
  the brand's response to the target, the eventual resolution, and any
  other future thread messages.
"""
from datetime import datetime

TWITTER_TIME_FORMAT = "%a %b %d %H:%M:%S %z %Y"


def parse_time(ts_str):
    """Parse a TWCS `created_at` string (e.g. 'Wed Nov 29 00:25:40 +0000 2017')."""
    return datetime.strptime(ts_str, TWITTER_TIME_FORMAT)


def get_target_context(messages, target_tweet_id):
    """
    Return the messages from `messages` that are valid context for
    `target_tweet_id`: strictly before the target by `created_at`, with
    `tweet_id` as a tiebreak for identical timestamps.

    `messages` must be the message list for a single thread (the one
    containing `target_tweet_id`). The target message is looked up by
    `tweet_id` and excluded from the returned context.

    Returns messages sorted chronologically (created_at, then tweet_id).
    Returns [] if the target tweet id is not found in `messages`.
    """
    target_msg = next((m for m in messages if m["tweet_id"] == target_tweet_id), None)
    if not target_msg:
        return []
    target_time = parse_time(target_msg["created_at"])

    ctx = []
    for m in messages:
        if m["tweet_id"] == target_tweet_id:
            continue
        m_time = parse_time(m["created_at"])
        # Include strictly before, or same time but lower tweet ID as tiebreaker
        if m_time < target_time or (m_time == target_time and m["tweet_id"] < target_tweet_id):
            ctx.append(m)

    ctx.sort(key=lambda m: (parse_time(m["created_at"]), m["tweet_id"]))
    return ctx


# Backwards-compatible alias matching the original name used in create_pilot.py.
get_context = get_target_context
