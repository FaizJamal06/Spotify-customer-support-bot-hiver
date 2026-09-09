"""
Phase 1: Three-Way Thread-Level Split

Splits Spotify threads into DEVELOPMENT, RETRIEVAL, and TEST pools.
Also extracts (customer_message, brand_reply) pairs per pool.

Usage:
    python data/split.py
"""
import sys
import json
import random
from pathlib import Path
from collections import Counter

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def load_threads():
    """Load reconstructed Spotify threads."""
    threads = []
    with open(config.SPOTIFY_THREADS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            threads.append(json.loads(line))
    print(f"Loaded {len(threads):,} threads")
    return threads


def split_threads(threads):
    """
    Split threads into three disjoint pools.
    
    DEVELOPMENT (15%): taxonomy discovery, pilot labeling, few-shot selection
    RETRIEVAL   (65%): historical retrieval index
    TEST        (20%): golden evaluation set (sealed until final evaluation)
    """
    thread_ids = [t["thread_id"] for t in threads]
    
    random.seed(config.SPLIT_SEED)
    random.shuffle(thread_ids)
    
    n = len(thread_ids)
    dev_end = int(n * config.DEV_FRACTION)
    ret_end = dev_end + int(n * config.RETRIEVAL_FRACTION)
    
    dev_ids = set(thread_ids[:dev_end])
    ret_ids = set(thread_ids[dev_end:ret_end])
    test_ids = set(thread_ids[ret_end:])
    
    # Verify disjointness
    assert dev_ids.isdisjoint(ret_ids), "LEAK: dev ∩ retrieval"
    assert dev_ids.isdisjoint(test_ids), "LEAK: dev ∩ test"
    assert ret_ids.isdisjoint(test_ids), "LEAK: retrieval ∩ test"
    assert len(dev_ids) + len(ret_ids) + len(test_ids) == n, "Missing threads"
    
    print(f"Split: DEV={len(dev_ids):,} ({len(dev_ids)/n*100:.1f}%), "
          f"RET={len(ret_ids):,} ({len(ret_ids)/n*100:.1f}%), "
          f"TEST={len(test_ids):,} ({len(test_ids)/n*100:.1f}%)")
    
    return dev_ids, ret_ids, test_ids


def extract_pairs(threads, pool_ids, pool_name):
    """Extract (customer_msg, brand_reply) pairs from a pool."""
    pairs = []
    pool_threads = [t for t in threads if t["thread_id"] in pool_ids]
    
    for thread in pool_threads:
        for pair in thread["customer_brand_pairs"]:
            pairs.append({
                "thread_id": thread["thread_id"],
                "customer_tweet_id": pair["customer_tweet_id"],
                "customer_author_id": pair["customer_author_id"],
                "customer_text": pair["customer_text"],
                "brand_tweet_id": pair["brand_tweet_id"],
                "brand_text": pair["brand_text"],
            })
    
    print(f"  {pool_name}: {len(pool_threads):,} threads, {len(pairs):,} pairs")
    return pairs


def save_pool_pairs(pairs, path):
    """Save pairs to JSONL."""
    with open(path, "w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")


def save_split_metadata(dev_ids, ret_ids, test_ids):
    """Save the split assignment so it can be reproduced."""
    metadata = {
        "seed": config.SPLIT_SEED,
        "dev_fraction": config.DEV_FRACTION,
        "retrieval_fraction": config.RETRIEVAL_FRACTION,
        "test_fraction": config.TEST_FRACTION,
        "dev_thread_ids": sorted(dev_ids),
        "retrieval_thread_ids": sorted(ret_ids),
        "test_thread_ids": sorted(test_ids),
    }
    with open(config.POOL_SPLIT_PATH, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Split metadata saved to {config.POOL_SPLIT_PATH}")


def compute_stats(threads, dev_ids, ret_ids, test_ids,
                  dev_pairs, ret_pairs, test_pairs):
    """Compute and save summary statistics."""
    
    def pool_stats(pool_threads, pool_pairs, name):
        thread_lengths = [t["num_messages"] for t in pool_threads]
        pair_counts = [t["num_pairs"] for t in pool_threads]
        tl = pd.Series(thread_lengths) if thread_lengths else pd.Series([0])
        pc = pd.Series(pair_counts) if pair_counts else pd.Series([0])
        
        # Customer text length in pairs
        cust_lengths = [len(p["customer_text"]) for p in pool_pairs]
        brand_lengths = [len(p["brand_text"]) for p in pool_pairs]
        cl = pd.Series(cust_lengths) if cust_lengths else pd.Series([0])
        bl = pd.Series(brand_lengths) if brand_lengths else pd.Series([0])
        
        return {
            "name": name,
            "num_threads": len(pool_threads),
            "num_pairs": len(pool_pairs),
            "total_messages": sum(thread_lengths),
            "unique_customers": len(set(p["customer_author_id"] for p in pool_pairs)),
            "thread_length_mean": round(tl.mean(), 2),
            "thread_length_median": round(tl.median(), 2),
            "thread_length_max": int(tl.max()),
            "pairs_per_thread_mean": round(pc.mean(), 2),
            "customer_text_length_mean": round(cl.mean(), 1),
            "brand_text_length_mean": round(bl.mean(), 1),
        }
    
    dev_threads = [t for t in threads if t["thread_id"] in dev_ids]
    ret_threads = [t for t in threads if t["thread_id"] in ret_ids]
    test_threads = [t for t in threads if t["thread_id"] in test_ids]
    
    stats = {
        "total_threads": len(threads),
        "total_pairs": sum(t["num_pairs"] for t in threads),
        "pools": {
            "development": pool_stats(dev_threads, dev_pairs, "DEVELOPMENT"),
            "retrieval": pool_stats(ret_threads, ret_pairs, "RETRIEVAL"),
            "test": pool_stats(test_threads, test_pairs, "TEST"),
        }
    }
    
    with open(config.SPLIT_STATS_PATH, "w") as f:
        json.dump(stats, f, indent=2)
    
    # Print summary
    print("\n=== POOL STATISTICS ===")
    for pool_name, ps in stats["pools"].items():
        print(f"\n  {pool_name.upper()}:")
        print(f"    Threads: {ps['num_threads']:,}")
        print(f"    Customer→Brand pairs: {ps['num_pairs']:,}")
        print(f"    Total messages: {ps['total_messages']:,}")
        print(f"    Unique customers: {ps['unique_customers']:,}")
        print(f"    Thread length: mean={ps['thread_length_mean']}, "
              f"median={ps['thread_length_median']}, max={ps['thread_length_max']}")
        print(f"    Pairs/thread: mean={ps['pairs_per_thread_mean']}")
        print(f"    Customer msg length: mean={ps['customer_text_length_mean']} chars")
        print(f"    Brand msg length: mean={ps['brand_text_length_mean']} chars")
    
    return stats


def main():
    config.ensure_dirs()
    
    threads = load_threads()
    dev_ids, ret_ids, test_ids = split_threads(threads)
    
    print("\nExtracting pairs per pool:")
    dev_pairs = extract_pairs(threads, dev_ids, "DEVELOPMENT")
    ret_pairs = extract_pairs(threads, ret_ids, "RETRIEVAL")
    test_pairs = extract_pairs(threads, test_ids, "TEST")
    
    # Verify tweet-level disjointness
    dev_tweets = set()
    for t in threads:
        if t["thread_id"] in dev_ids:
            dev_tweets.update(m["tweet_id"] for m in t["messages"])
    ret_tweets = set()
    for t in threads:
        if t["thread_id"] in ret_ids:
            ret_tweets.update(m["tweet_id"] for m in t["messages"])
    test_tweets = set()
    for t in threads:
        if t["thread_id"] in test_ids:
            test_tweets.update(m["tweet_id"] for m in t["messages"])
    
    assert dev_tweets.isdisjoint(ret_tweets), "LEAK: dev ∩ retrieval tweets"
    assert dev_tweets.isdisjoint(test_tweets), "LEAK: dev ∩ test tweets"
    assert ret_tweets.isdisjoint(test_tweets), "LEAK: retrieval ∩ test tweets"
    print(f"\n✓ Tweet-level disjointness verified "
          f"(dev={len(dev_tweets):,}, ret={len(ret_tweets):,}, test={len(test_tweets):,})")
    
    # Save everything
    print("\nSaving pool data:")
    save_pool_pairs(dev_pairs, config.DEV_PAIRS_PATH)
    save_pool_pairs(ret_pairs, config.RETRIEVAL_PAIRS_PATH)
    save_pool_pairs(test_pairs, config.TEST_PAIRS_PATH)
    save_split_metadata(dev_ids, ret_ids, test_ids)
    
    # Compute and save stats
    stats = compute_stats(threads, dev_ids, ret_ids, test_ids,
                          dev_pairs, ret_pairs, test_pairs)
    
    print("\nPhase 1b (split) complete.")


if __name__ == "__main__":
    main()
