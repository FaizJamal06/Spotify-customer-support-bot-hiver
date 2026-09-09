"""
Phase 1: Data Preparation

Filters the TWCS dataset to SpotifyCares conversations,
reconstructs conversation threads, and produces a clean
JSONL file of all Spotify threads with their messages.

Usage:
    python data/prepare.py
"""
import sys
import json
import time
from pathlib import Path
from collections import defaultdict

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def load_raw_data():
    """Load the raw TWCS CSV."""
    print(f"Loading {config.RAW_CSV_PATH} ...")
    t0 = time.time()
    df = pd.read_csv(config.RAW_CSV_PATH)
    print(f"  Loaded {len(df):,} rows in {time.time()-t0:.1f}s")
    return df


def extract_spotify_related(df):
    """
    Extract all tweets that are part of a SpotifyCares conversation.
    
    Strategy:
    1. Find all SpotifyCares outbound tweets
    2. Find all customer tweets that SpotifyCares replied to
    3. Find all tweets that replied to SpotifyCares tweets
    4. Iteratively expand to capture full threads
    """
    brand = config.BRAND_AUTHOR_ID
    
    # Step 1: All SpotifyCares tweets
    spotify_tweets = set(df[df["author_id"] == brand]["tweet_id"].tolist())
    print(f"  SpotifyCares tweets: {len(spotify_tweets):,}")
    
    # Step 2: Customer tweets SpotifyCares replied to
    spotify_out = df[df["author_id"] == brand]
    replied_to_ids = set(
        spotify_out["in_response_to_tweet_id"].dropna().astype(int).tolist()
    )
    
    # Step 3: Tweets replying to SpotifyCares
    replies_to_spotify = set(
        df[df["in_response_to_tweet_id"].isin(spotify_tweets)]["tweet_id"].tolist()
    )
    
    # Combine initial set
    related_ids = spotify_tweets | replied_to_ids | replies_to_spotify
    
    # Step 4: Iteratively expand (follow parent/child links until stable)
    # Build lookup structures first
    print("  Building parent/child maps...")
    parent_of = {}   # tweet_id -> parent_tweet_id
    children_of = defaultdict(list)  # tweet_id -> [child_tweet_ids]
    
    for tweet_id, parent_id in zip(
        df["tweet_id"], df["in_response_to_tweet_id"]
    ):
        if pd.notna(parent_id):
            pid = int(parent_id)
            parent_of[tweet_id] = pid
            children_of[pid].append(tweet_id)
    
    # Expand: for any tweet in related_ids, also include its full
    # parent chain (to root) and its children
    print("  Expanding to full threads...")
    prev_size = 0
    iteration = 0
    while len(related_ids) != prev_size:
        prev_size = len(related_ids)
        iteration += 1
        new_ids = set()
        for tid in related_ids:
            # Follow parent chain
            if tid in parent_of:
                new_ids.add(parent_of[tid])
            # Follow children
            for child in children_of.get(tid, []):
                new_ids.add(child)
        related_ids |= new_ids
        print(f"    Iteration {iteration}: {len(related_ids):,} tweets")
        if iteration > 20:
            print("    WARNING: >20 iterations, stopping expansion")
            break
    
    # Filter dataframe to related tweets
    spotify_df = df[df["tweet_id"].isin(related_ids)].copy()
    print(f"  Total Spotify-related tweets: {len(spotify_df):,}")
    return spotify_df, parent_of, children_of


def reconstruct_threads(spotify_df, parent_of):
    """
    Reconstruct conversation threads.
    
    A thread is identified by its root tweet (the tweet with no parent,
    or whose parent is not in the dataset).
    
    Returns a dict: {root_tweet_id: [list of tweet_ids in thread]}
    """
    tweet_ids_in_data = set(spotify_df["tweet_id"].tolist())
    
    # Find root for each tweet
    def find_root(tweet_id):
        visited = set()
        current = tweet_id
        while current in parent_of and parent_of[current] in tweet_ids_in_data:
            if current in visited:
                break  # cycle protection
            visited.add(current)
            current = parent_of[current]
        return current
    
    print("  Finding thread roots...")
    tweet_to_root = {}
    for tid in tweet_ids_in_data:
        tweet_to_root[tid] = find_root(tid)
    
    # Group by root
    threads = defaultdict(list)
    for tid, root in tweet_to_root.items():
        threads[root].append(tid)
    
    print(f"  Reconstructed {len(threads):,} threads")
    return dict(threads), tweet_to_root


def build_thread_records(threads, spotify_df, tweet_to_root):
    """
    Build structured thread records with message details.
    
    Each thread record contains:
    - thread_id (root tweet_id)
    - messages: list of {tweet_id, author_id, inbound, created_at, text,
                         in_response_to_tweet_id}
      sorted by tweet_id (proxy for chronological order)
    - customer_brand_pairs: list of (customer_msg, brand_reply) dicts
    """
    # Build tweet lookup
    tweet_data = {}
    for _, row in spotify_df.iterrows():
        tweet_data[row["tweet_id"]] = {
            "tweet_id": int(row["tweet_id"]),
            "author_id": str(row["author_id"]),
            "inbound": bool(row["inbound"]),
            "created_at": str(row["created_at"]) if pd.notna(row["created_at"]) else None,
            "text": str(row["text"]) if pd.notna(row["text"]) else "",
            "in_response_to_tweet_id": (
                int(row["in_response_to_tweet_id"])
                if pd.notna(row["in_response_to_tweet_id"])
                else None
            ),
        }
    
    print("  Building thread records...")
    records = []
    brand = config.BRAND_AUTHOR_ID
    
    for root_id, tweet_ids in threads.items():
        # Sort messages by tweet_id (monotonically increasing ~ chronological)
        msgs = sorted(
            [tweet_data[tid] for tid in tweet_ids if tid in tweet_data],
            key=lambda m: m["tweet_id"]
        )
        
        # Extract customer→brand pairs
        pairs = []
        for msg in msgs:
            if msg["author_id"] == brand and msg["in_response_to_tweet_id"] is not None:
                parent_id = msg["in_response_to_tweet_id"]
                if parent_id in tweet_data:
                    parent = tweet_data[parent_id]
                    if parent["inbound"]:
                        pairs.append({
                            "customer_tweet_id": parent["tweet_id"],
                            "customer_author_id": parent["author_id"],
                            "customer_text": parent["text"],
                            "brand_tweet_id": msg["tweet_id"],
                            "brand_text": msg["text"],
                        })
        
        records.append({
            "thread_id": int(root_id),
            "num_messages": len(msgs),
            "num_pairs": len(pairs),
            "has_brand_response": any(m["author_id"] == brand for m in msgs),
            "messages": msgs,
            "customer_brand_pairs": pairs,
        })
    
    # Filter to threads that actually involve SpotifyCares
    records = [r for r in records if r["has_brand_response"]]
    print(f"  Threads with SpotifyCares response: {len(records):,}")
    
    return records


def save_threads(records):
    """Save thread records to JSONL."""
    config.ensure_dirs()
    path = config.SPOTIFY_THREADS_PATH
    
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    print(f"  Saved {len(records):,} thread records to {path}")


def print_summary(records):
    """Print summary statistics."""
    num_threads = len(records)
    total_messages = sum(r["num_messages"] for r in records)
    total_pairs = sum(r["num_pairs"] for r in records)
    thread_lengths = [r["num_messages"] for r in records]
    pair_counts = [r["num_pairs"] for r in records]
    
    tl = pd.Series(thread_lengths)
    pc = pd.Series(pair_counts)
    
    print("\n=== SPOTIFY THREAD SUMMARY ===")
    print(f"  Total threads: {num_threads:,}")
    print(f"  Total messages: {total_messages:,}")
    print(f"  Total customer→brand pairs: {total_pairs:,}")
    print(f"\n  Thread length distribution:")
    print(f"    Mean: {tl.mean():.1f}")
    print(f"    Median: {tl.median():.0f}")
    print(f"    Min: {tl.min()}, Max: {tl.max()}")
    for length in range(1, min(11, int(tl.max()) + 1)):
        count = (tl == length).sum()
        print(f"    Length {length}: {count:,} ({count/num_threads*100:.1f}%)")
    if tl.max() > 10:
        count = (tl > 10).sum()
        print(f"    Length >10: {count:,} ({count/num_threads*100:.1f}%)")
    
    print(f"\n  Pairs per thread distribution:")
    print(f"    Mean: {pc.mean():.1f}")
    print(f"    Median: {pc.median():.0f}")
    print(f"    Threads with 0 pairs: {(pc == 0).sum():,}")
    print(f"    Threads with 1 pair: {(pc == 1).sum():,}")
    print(f"    Threads with 2+ pairs: {(pc >= 2).sum():,}")


def inspect_sample_threads(records, n=5):
    """Print a few threads for manual verification of reconstruction."""
    import random
    random.seed(config.SPLIT_SEED)
    
    # Pick threads of different lengths
    short = [r for r in records if r["num_messages"] == 2]
    medium = [r for r in records if 3 <= r["num_messages"] <= 5]
    long = [r for r in records if r["num_messages"] >= 6]
    
    samples = []
    if short:
        samples.append(random.choice(short))
    if medium:
        samples.extend(random.sample(medium, min(2, len(medium))))
    if long:
        samples.extend(random.sample(long, min(2, len(long))))
    
    print(f"\n=== SAMPLE THREADS FOR MANUAL INSPECTION ===")
    for i, thread in enumerate(samples):
        print(f"\n--- Thread {i+1} (root={thread['thread_id']}, "
              f"{thread['num_messages']} msgs, {thread['num_pairs']} pairs) ---")
        for msg in thread["messages"]:
            role = "BRAND" if msg["author_id"] == config.BRAND_AUTHOR_ID else "CUSTOMER"
            parent = msg.get("in_response_to_tweet_id", "none")
            print(f"  [{role}] (id={msg['tweet_id']}, reply_to={parent}) "
                  f"{msg['text'][:200]}")


def main():
    df = load_raw_data()
    spotify_df, parent_of, children_of = extract_spotify_related(df)
    threads, tweet_to_root = reconstruct_threads(spotify_df, parent_of)
    records = build_thread_records(threads, spotify_df, tweet_to_root)
    save_threads(records)
    print_summary(records)
    inspect_sample_threads(records)
    print("\nPhase 1a (prepare) complete.")


if __name__ == "__main__":
    main()
