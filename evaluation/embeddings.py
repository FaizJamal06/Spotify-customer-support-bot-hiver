"""
Minimal OpenAI embedding utility.

Not the retrieval index -- that is Part E, a separate future task. This
module only provides a single function to get an embedding for one string,
reusing the exact same DiskCache pattern already established in
evaluation/llm_classifier.py (cache/ directory, SHA-256-hashed request
payload as the key) rather than inventing a second caching mechanism.

Model verified against official OpenAI documentation (developers.openai.com,
the current canonical home for platform.openai.com/docs/* after a 301
redirect) -- see the milestone report for exact sources: config.EMBEDDING_MODEL
= "text-embedding-3-small", 1536 dimensions by default, $0.02 / 1M tokens,
8192 token max input, dedicated /v1/embeddings endpoint via
client.embeddings.create().
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.llm_classifier import DiskCache


def get_embedding(text: str) -> list:
    """Returns the embedding for `text` as a list[float], using config.EMBEDDING_MODEL.

    Reuses config.get_api_key() (raises EnvironmentError if OPENAI_API_KEY is not
    set, same as the existing classifier code) and the same DiskCache class used
    for classifier calls (cache/ directory), keyed by a hash of {model, input}.
    Identical repeated calls never re-hit the API.
    """
    api_key = config.get_api_key()

    cache = DiskCache(config.CACHE_DIR)
    cache_key = json.dumps(dict(model=config.EMBEDDING_MODEL, input=text), sort_keys=True)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached["embedding"]

    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(model=config.EMBEDDING_MODEL, input=text)
    embedding = response.data[0].embedding

    cache.set(cache_key, {"embedding": embedding})
    return embedding
