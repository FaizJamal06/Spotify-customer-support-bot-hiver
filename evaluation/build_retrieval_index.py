"""
One-time entry point: builds the brute-force retrieval index.

NOT part of any <15-minute reproduction path. This script makes real OpenAI
embedding API calls (requires OPENAI_API_KEY), embeds ~3,200 real texts
(3,000 sampled RETRIEVAL customer messages + the 200 golden queries for the
near-duplicate check), and takes materially longer than the data-prep/
baseline pipeline. Run it explicitly and separately:

    python evaluation/build_retrieval_index.py

Pipeline (see the milestone report for full reasoning):
  1. Deduplicate data/generated/retrieval_pairs.jsonl: for each customer_tweet_id
     appearing more than once, keep exactly the pair whose brand reply has the
     EARLIEST created_at (joined from data/generated/spotify_threads.jsonl by
     brand_tweet_id, using discovery/chronology.py's parse_time -- never
     tweet_id/brand_tweet_id magnitude as a chronology proxy).
  2. Simple random sample of config.RETRIEVAL_SAMPLE_SIZE pairs from the
     deduplicated set, seed=config.RETRIEVAL_SAMPLE_SEED.
  3. Embed ONLY customer_text for each sampled pair (brand_text is returned as
     grounding evidence at query time, never searched on), batched via the
     embeddings API's array-input support. Serialize to
     config.RETRIEVAL_INDEX_DIR (gitignored, under cache/).
  4. Embed the 200 golden queries (golden_set/GOLDEN_200_FINAL.csv,
     target_message column -- read-only, for this near-duplicate check only)
     and report (warning, not hard stop, per implementation_plan.md §13) any
     (golden, retrieval) pair with cosine similarity > config.NEAR_DUPLICATE_THRESHOLD.
     Separately, HARD-assert zero customer_tweet_id/thread_id overlap between
     the golden 200 and the sampled retrieval index (reusing
     evaluation.leakage_checks.assert_no_overlap).
"""
import csv
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from discovery.chronology import parse_time
from evaluation.leakage_checks import assert_no_overlap, LeakageError

BATCH_SIZE = 100  # texts per embeddings.create() call; keeps well under Tier-1 RPM/TPM


class DedupJoinError(RuntimeError):
    """Raised when the created_at join (Part 1) fails for any candidate pair."""


class EmbeddingFailure(RuntimeError):
    """Raised when a batched embedding call fails partway through."""


# ---------------------------------------------------------------------------
# Part 1: Deduplicate
# ---------------------------------------------------------------------------

def load_retrieval_pairs():
    pairs = []
    with open(config.RETRIEVAL_PAIRS_PATH, encoding="utf-8") as f:
        for line in f:
            pairs.append(json.loads(line))
    return pairs


def _build_brand_created_at_lookup(thread_ids_needed):
    """brand tweet_id -> created_at string, streamed from spotify_threads.jsonl,
    restricted to the specific threads that actually need it."""
    lookup = {}
    with open(config.SPOTIFY_THREADS_PATH, encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            if t["thread_id"] not in thread_ids_needed:
                continue
            for m in t["messages"]:
                if m["author_id"] == config.BRAND_AUTHOR_ID:
                    lookup[m["tweet_id"]] = m["created_at"]
    return lookup


def deduplicate_pairs(pairs):
    """
    For each customer_tweet_id appearing more than once, keep exactly one pair:
    the one whose brand reply has the EARLIEST created_at. created_at is joined
    from spotify_threads.jsonl by brand_tweet_id and parsed with
    discovery.chronology.parse_time -- tweet_id magnitude is never used as a
    chronology proxy (that is exactly the bug chronology.py exists to prevent).
    Ties (identical created_at) are broken by the lower brand_tweet_id, for a
    fully deterministic result.

    Returns (deduped_pairs, missing_join) -- missing_join lists any pair whose
    brand_tweet_id could not be found in spotify_threads.jsonl at all (should
    be empty; the caller must STOP if it is not).
    """
    by_customer = defaultdict(list)
    for p in pairs:
        by_customer[p["customer_tweet_id"]].append(p)

    duplicated = {cid: plist for cid, plist in by_customer.items() if len(plist) > 1}
    thread_ids_needed = {p["thread_id"] for plist in duplicated.values() for p in plist}
    created_at_lookup = _build_brand_created_at_lookup(thread_ids_needed)

    missing_join = []
    deduped = []
    for cid in sorted(by_customer.keys()):
        plist = by_customer[cid]
        if len(plist) == 1:
            deduped.append(plist[0])
            continue

        resolved = []
        for p in plist:
            created_at = created_at_lookup.get(p["brand_tweet_id"])
            if created_at is None:
                missing_join.append(p)
                continue
            resolved.append((parse_time(created_at), p["brand_tweet_id"], p))

        if resolved:
            resolved.sort(key=lambda x: (x[0], x[1]))
            deduped.append(resolved[0][2])

    return deduped, missing_join


# ---------------------------------------------------------------------------
# Corpus-quality filter (runs after dedup, before sampling)
# ---------------------------------------------------------------------------

def filter_short_messages(deduped_pairs, min_length=None):
    """
    Drops pairs whose customer_text is shorter than config.MIN_CUSTOMER_MSG_LENGTH
    (stripped length) from the sampling-eligible pool entirely -- not just
    deprioritized. Corpus-side only: this never touches query-time embedding
    (evaluation/retrieval.py's get_embedding() calls are unfiltered).

    Inspection of the real deduplicated pool (see the milestone report) found
    only 4/26,914 pairs below 10 chars, all of them a bare "@handle" with no
    other content -- not terse-but-real reactions like "how?" or "Srsly?",
    which sit safely above this threshold (12+ and 14 chars respectively) and
    are left untouched.
    """
    min_length = config.MIN_CUSTOMER_MSG_LENGTH if min_length is None else min_length
    return [p for p in deduped_pairs if len(p["customer_text"].strip()) >= min_length]


# ---------------------------------------------------------------------------
# Part 2: Sample
# ---------------------------------------------------------------------------

def sample_pairs(deduped_pairs, n=None, seed=None):
    import random
    n = config.RETRIEVAL_SAMPLE_SIZE if n is None else n
    seed = config.RETRIEVAL_SAMPLE_SEED if seed is None else seed
    ordered = sorted(deduped_pairs, key=lambda p: p["customer_tweet_id"])
    rng = random.Random(seed)
    return rng.sample(ordered, n)


# ---------------------------------------------------------------------------
# Part 3: Embed + serialize
# ---------------------------------------------------------------------------

def embed_batch(client, texts, batch_size=BATCH_SIZE, label="texts"):
    """Embeds `texts` via the array-input batching feature of the embeddings API.
    No retry logic (none established elsewhere in this project) -- fails loudly,
    reporting how many were embedded successfully before the failure."""
    all_embeddings = [None] * len(texts)
    embedded_so_far = 0
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            response = client.embeddings.create(model=config.EMBEDDING_MODEL, input=batch)
        except Exception as e:
            raise EmbeddingFailure(
                f"Embedding call failed on batch starting at index {i} "
                f"({embedded_so_far}/{len(texts)} {label} embedded successfully before this): {e}"
            ) from e
        for item in response.data:
            all_embeddings[i + item.index] = item.embedding
        embedded_so_far += len(batch)
        print(f"  embedded {embedded_so_far}/{len(texts)} {label}")
    return all_embeddings


def serialize_index(sample, embeddings, full_pool_count, deduped_count, out_dir=None):
    out_dir = config.RETRIEVAL_INDEX_DIR if out_dir is None else Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    emb_array = np.array(embeddings, dtype=np.float32)
    np.save(out_dir / "embeddings.npy", emb_array)

    with open(out_dir / "metadata.jsonl", "w", encoding="utf-8") as f:
        for p in sample:
            f.write(json.dumps({
                "customer_text": p["customer_text"],
                "brand_text": p["brand_text"],
                "customer_tweet_id": p["customer_tweet_id"],
                "brand_tweet_id": p["brand_tweet_id"],
                "thread_id": p["thread_id"],
            }, ensure_ascii=False) + "\n")

    manifest = dict(
        embedding_model=config.EMBEDDING_MODEL,
        dimensions=int(emb_array.shape[1]),
        sample_size=len(sample),
        seed=config.RETRIEVAL_SAMPLE_SEED,
        full_retrieval_pool_pair_count=full_pool_count,
        deduplicated_pair_count=deduped_count,
        built_at=datetime.now(timezone.utc).isoformat(),
        source_file=str(config.RETRIEVAL_PAIRS_PATH),
    )
    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return out_dir, manifest


# ---------------------------------------------------------------------------
# Part 4: Near-duplicate check + hard leakage assertion vs golden 200
# ---------------------------------------------------------------------------

def load_golden_queries():
    """Read-only access to golden_set/GOLDEN_200_FINAL.csv, for this
    near-duplicate/leakage check only -- not used as index content."""
    with open(config.GOLDEN_FINAL_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 200, f"Expected 200 golden examples, found {len(rows)}"
    return rows


def _l2_normalize_rows(arr):
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / norms


def near_duplicate_check(golden_rows, golden_embeddings, sample, index_embeddings, threshold=None):
    """Warning-level check (not a hard stop), per implementation_plan.md §13 #7:
    reports (golden_example, retrieval_pair) pairs with cosine similarity > threshold.
    Returns a list of dicts describing each match found."""
    threshold = config.NEAR_DUPLICATE_THRESHOLD if threshold is None else threshold

    g = _l2_normalize_rows(np.array(golden_embeddings, dtype=np.float32))
    idx = _l2_normalize_rows(np.array(index_embeddings, dtype=np.float32))
    sims = g @ idx.T  # (200, sample_size)

    matches = []
    rows_i, cols_j = np.where(sims > threshold)
    for i, j in zip(rows_i, cols_j):
        matches.append(dict(
            golden_tweet_id=golden_rows[i]["tweet_id"],
            golden_text=golden_rows[i]["target_message"],
            retrieval_customer_tweet_id=sample[j]["customer_tweet_id"],
            retrieval_text=sample[j]["customer_text"],
            similarity=float(sims[i, j]),
        ))
    matches.sort(key=lambda m: -m["similarity"])
    return matches


def assert_hard_leakage_free(golden_rows, sample):
    """HARD assertion (not a warning): zero customer_tweet_id/thread_id overlap
    between the golden 200 and the sampled retrieval index. Reuses the existing
    evaluation.leakage_checks.assert_no_overlap primitive. Raises LeakageError."""
    golden_tweet_ids = {str(r["tweet_id"]) for r in golden_rows}
    golden_thread_ids = {str(r["thread_id"]) for r in golden_rows}
    index_tweet_ids = {str(p["customer_tweet_id"]) for p in sample}
    index_thread_ids = {str(p["thread_id"]) for p in sample}

    assert_no_overlap(golden_tweet_ids, index_tweet_ids, "golden (TEST)", "retrieval index", "tweet_id")
    assert_no_overlap(golden_thread_ids, index_thread_ids, "golden (TEST)", "retrieval index", "thread_id")

    return dict(
        golden_tweet_ids=len(golden_tweet_ids), golden_thread_ids=len(golden_thread_ids),
        index_tweet_ids=len(index_tweet_ids), index_thread_ids=len(index_thread_ids),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    from openai import OpenAI

    print("=== Part 1: Deduplicate ===")
    pairs = load_retrieval_pairs()
    print(f"Full RETRIEVAL pool pairs: {len(pairs):,}")
    deduped, missing_join = deduplicate_pairs(pairs)
    if missing_join:
        raise DedupJoinError(
            f"STOP: created_at join failed for {len(missing_join)} candidate pair(s) during "
            f"dedup tie-breaking. Examples: {missing_join[:5]}"
        )
    print(f"Deduplicated pairs: {len(deduped):,} (expected ~26,914)")

    print("\n=== Corpus-quality filter (MIN_CUSTOMER_MSG_LENGTH) ===")
    eligible = filter_short_messages(deduped)
    print(f"Filtered {len(deduped) - len(eligible):,} pairs with customer_text shorter than "
          f"{config.MIN_CUSTOMER_MSG_LENGTH} chars (stripped). Eligible pool: {len(eligible):,}")

    print("\n=== Part 2: Sample ===")
    sample = sample_pairs(eligible)
    print(f"Sampled {len(sample):,} pairs (seed={config.RETRIEVAL_SAMPLE_SEED})")

    print("\n=== Part 3: Embed + serialize ===")
    client = OpenAI(api_key=config.get_api_key())
    customer_texts = [p["customer_text"] for p in sample]
    t0 = time.time()
    embeddings = embed_batch(client, customer_texts, label="retrieval customer messages")
    print(f"Embedded {len(embeddings):,} texts in {time.time() - t0:.1f}s")

    out_dir, manifest = serialize_index(sample, embeddings, len(pairs), len(deduped))
    print(f"Serialized index to {out_dir} (model={manifest['embedding_model']}, dims={manifest['dimensions']})")

    print("\n=== Part 4: Near-duplicate check + hard leakage assertion vs golden 200 ===")
    golden_rows = load_golden_queries()
    golden_texts = [r["target_message"] for r in golden_rows]
    golden_embeddings = embed_batch(client, golden_texts, label="golden queries")

    matches = near_duplicate_check(golden_rows, golden_embeddings, sample, embeddings)
    print(f"Near-duplicate WARNING (cosine > {config.NEAR_DUPLICATE_THRESHOLD}): "
          f"{len(matches)} (golden, retrieval) pair(s). Natural overlap, not a leak "
          f"(see implementation_plan.md §13).")
    for m in matches[:5]:
        print(f"  sim={m['similarity']:.4f}  golden={m['golden_text']!r}  retrieval={m['retrieval_text']!r}")

    try:
        leakage_summary = assert_hard_leakage_free(golden_rows, sample)
    except LeakageError:
        print("HARD LEAKAGE ASSERTION FAILED -- see exception above. STOP.")
        raise
    print(f"Hard leakage assertion PASSED: {leakage_summary}")

    print("\nDone.")


if __name__ == "__main__":
    main()
