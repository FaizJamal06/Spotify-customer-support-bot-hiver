"""
Minimal regression test for discovery/chronology.py.

Guards against the known chronology bug: numeric tweet_id is only
approximately chronological (Snowflake ID generation can produce
out-of-order IDs across tweets), so target-message context must be built
from `created_at`, not `tweet_id`. This test proves a message that occurs
AFTER the target in real time (created_at) is excluded from context even
when its tweet_id is numerically SMALLER than the target's tweet_id, and
that a message occurring BEFORE the target is included even when its
tweet_id is numerically LARGER.

Run with:
    python discovery/test_chronology.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from chronology import get_target_context


class ChronologyTests(unittest.TestCase):
    def test_future_message_with_smaller_tweet_id_is_excluded(self):
        # Target has a HIGH tweet_id but an EARLY created_at.
        # A "future" message has a LOW tweet_id but a LATER created_at.
        # Naive tweet_id-based ordering would wrongly treat the future
        # message as prior context; created_at-based ordering must not.
        messages = [
            {
                "tweet_id": 100,  # numerically smaller than target (999)
                "inbound": False,
                "created_at": "Wed Nov 29 10:00:00 +0000 2017",  # AFTER target's time
                "text": "SpotifyCares: glad it's sorted now!",
            },
            {
                "tweet_id": 999,  # target
                "inbound": True,
                "created_at": "Wed Nov 29 09:00:00 +0000 2017",
                "text": "Customer: still broken, please help",
            },
            {
                "tweet_id": 500,  # numerically smaller than target, and earlier in time
                "inbound": True,
                "created_at": "Wed Nov 29 08:00:00 +0000 2017",  # BEFORE target's time
                "text": "Customer: app keeps crashing",
            },
        ]

        ctx = get_target_context(messages, target_tweet_id=999)
        ctx_tweet_ids = [m["tweet_id"] for m in ctx]

        self.assertNotIn(
            100, ctx_tweet_ids,
            "Future message (later created_at) leaked into context despite "
            "having a numerically smaller tweet_id than the target.",
        )
        self.assertIn(
            500, ctx_tweet_ids,
            "Genuinely prior message (earlier created_at) was wrongly excluded.",
        )
        self.assertEqual(ctx_tweet_ids, [500])

    def test_same_timestamp_tiebreaks_on_tweet_id(self):
        messages = [
            {
                "tweet_id": 999,  # target
                "inbound": True,
                "created_at": "Wed Nov 29 09:00:00 +0000 2017",
                "text": "Customer: target message",
            },
            {
                "tweet_id": 998,  # identical created_at, smaller tweet_id -> included
                "inbound": True,
                "created_at": "Wed Nov 29 09:00:00 +0000 2017",
                "text": "Customer: same-second earlier message",
            },
            {
                "tweet_id": 1000,  # identical created_at, larger tweet_id -> excluded
                "inbound": False,
                "created_at": "Wed Nov 29 09:00:00 +0000 2017",
                "text": "SpotifyCares: same-second later message",
            },
        ]

        ctx = get_target_context(messages, target_tweet_id=999)
        ctx_tweet_ids = [m["tweet_id"] for m in ctx]

        self.assertEqual(ctx_tweet_ids, [998])

    def test_unknown_target_returns_empty_context(self):
        messages = [
            {"tweet_id": 1, "inbound": True, "created_at": "Wed Nov 29 09:00:00 +0000 2017", "text": "x"},
        ]
        self.assertEqual(get_target_context(messages, target_tweet_id=404), [])


if __name__ == "__main__":
    unittest.main()
