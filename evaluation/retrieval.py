"""
Brute-force top-k retrieval over the serialized index at
config.RETRIEVAL_INDEX_DIR (built once, separately, by
evaluation/build_retrieval_index.py -- this module never rebuilds it).

Brute-force cosine similarity, no FAISS, per the existing project decision --
the index is only config.RETRIEVAL_SAMPLE_SIZE (3,000) vectors, trivially
fast to scan in full for a single query.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.embeddings import get_embedding


class IndexModelMismatch(RuntimeError):
    """Raised when the stored index's embedding model differs from
    config.EMBEDDING_MODEL at query time -- similarity scores across
    different embedding models are not comparable and would be meaningless."""


def load_index(index_dir=None):
    """Loads (manifest, embeddings, metadata) from the serialized index directory."""
    index_dir = config.RETRIEVAL_INDEX_DIR if index_dir is None else Path(index_dir)
    manifest_path = index_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"No retrieval index found at {index_dir}. "
            "Run evaluation/build_retrieval_index.py first."
        )

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    embeddings = np.load(index_dir / "embeddings.npy")

    metadata = []
    with open(index_dir / "metadata.jsonl", encoding="utf-8") as f:
        for line in f:
            metadata.append(json.loads(line))

    return manifest, embeddings, metadata


def retrieve_top_k(query_text, k, index_dir=None):
    """
    Returns up to k (customer_text, brand_text, similarity_score, metadata) tuples,
    ranked by cosine similarity descending, brute-force over the full serialized index.

    k=0 returns [] immediately -- no embedding call is made in that case (the
    k-ablation's k=0 condition does no retrieval at all).

    Raises IndexModelMismatch if the stored index's embedding model differs from
    config.EMBEDDING_MODEL, rather than silently returning meaningless scores.
    """
    if k == 0:
        return []

    manifest, embeddings, metadata = load_index(index_dir)

    if manifest["embedding_model"] != config.EMBEDDING_MODEL:
        raise IndexModelMismatch(
            f"Retrieval index at {index_dir or config.RETRIEVAL_INDEX_DIR} was built with "
            f"model {manifest['embedding_model']!r}, but config.EMBEDDING_MODEL is now "
            f"{config.EMBEDDING_MODEL!r}. Rebuild the index before querying."
        )

    query_vec = np.array(get_embedding(query_text), dtype=np.float32)
    query_norm = query_vec / np.linalg.norm(query_vec)
    index_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    sims = index_norm @ query_norm

    k = min(k, len(metadata))
    top_indices = np.argsort(-sims, kind="stable")[:k]

    results = []
    for idx in top_indices:
        m = metadata[idx]
        results.append((m["customer_text"], m["brand_text"], float(sims[idx]), m))
    return results
