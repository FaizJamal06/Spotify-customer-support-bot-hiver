"""
Centralized configuration for the Hiver Spotify Support Agent project.
All paths, seeds, and parameters in one place.
"""
import os
from pathlib import Path

# === Paths ===
PROJECT_ROOT = Path(__file__).parent
RAW_CSV_PATH = PROJECT_ROOT / "twcs.csv"

# Generated data directory (never modify raw CSV)
DATA_DIR = PROJECT_ROOT / "data" / "generated"
DISCOVERY_DIR = PROJECT_ROOT / "discovery"
GOLDEN_DIR = PROJECT_ROOT / "golden_set"
CACHE_DIR = PROJECT_ROOT / "cache"
EVAL_DIR = PROJECT_ROOT / "evaluation" / "results"

# Generated data files
SPOTIFY_THREADS_PATH = DATA_DIR / "spotify_threads.jsonl"
POOL_SPLIT_PATH = DATA_DIR / "pool_split.json"
DEV_PAIRS_PATH = DATA_DIR / "dev_pairs.jsonl"
RETRIEVAL_PAIRS_PATH = DATA_DIR / "retrieval_pairs.jsonl"
TEST_PAIRS_PATH = DATA_DIR / "test_pairs.jsonl"
SPLIT_STATS_PATH = DATA_DIR / "split_stats.json"
ISOLATION_REPORT_PATH = DATA_DIR / "isolation_report.json"

# Discovery / golden-set artifacts used by the baseline milestone
DISCOVERY_HUMAN_REVIEW_PATH = DISCOVERY_DIR / "HUMAN_REVIEW_labeled.md"  # frozen; never modify
DISCOVERY_AUDIT_CSV_PATH = DISCOVERY_DIR / "DISCOVERY_300_AUDIT.csv"    # frozen; read-only reference
GOLDEN_FINAL_CSV_PATH = GOLDEN_DIR / "GOLDEN_200_FINAL.csv"             # frozen; evaluation-only, never train on this

# === Brand ===
BRAND_AUTHOR_ID = "SpotifyCares"

# === Random Seeds ===
SPLIT_SEED = 42
DISCOVERY_SAMPLE_SEED = 123
GOLDEN_SAMPLE_SEED = 456
BASELINE_SEED = 42  # governs the TF-IDF+LogReg baseline's random_state

# === Frozen 8-intent taxonomy (discovery/TAXONOMY_REVIEW_GUIDE.md) ===
FROZEN_LABELS = [
    "ACCOUNT_ACCESS",
    "SUBSCRIPTION_BILLING",
    "APP_TECH_ISSUE",
    "CONTENT_CATALOG",
    "FEATURE_FEEDBACK",
    "ARTIST_SUPPORT",
    "GENERAL_HOW_TO_INFO",
    "UNKNOWN_OTHER",
]

# === Baseline milestone: documented, non-tuned hyperparameters ===
# Standard/default choices only -- no grid search, no tuning against golden-200 performance.
TFIDF_PARAMS = dict()                                   # sklearn TfidfVectorizer defaults
LOGREG_PARAMS = dict(max_iter=1000, random_state=BASELINE_SEED)  # max_iter raised only to reach convergence

# === Pool Fractions ===
DEV_FRACTION = 0.15
RETRIEVAL_FRACTION = 0.65
TEST_FRACTION = 0.20

# === LLM Configuration ===
# Never hardcode API keys. Use environment variables.
def get_api_key():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise EnvironmentError(
            "OPENAI_API_KEY not set. Export it before running LLM-dependent steps."
        )
    return key

CLASSIFY_MODEL = "gpt-5.4-mini"  # verified callable + accepts temperature/seed at default reasoning_effort="none"
GENERATE_MODEL = "gpt-5.6-terra"  # verified 2026-09-14 against developers.openai.com/api/docs/models/gpt-5.6-terra
                                   # + live API smoke test. $2/$12 per 1M input/output tokens ($0.20 cached
                                   # input), 1.05M context. temperature/seed are accepted ONLY at
                                   # reasoning_effort="none" (the family default is "medium", which rejects
                                   # temperature != 1) -- same pattern as CLASSIFY_MODEL. Strict JSON-schema
                                   # structured outputs confirmed working, including nested objects/arrays.
JUDGE_MODEL = "gpt-5.6-sol"       # verified 2026-09-14 against developers.openai.com/api/docs/models/gpt-5.6-sol
                                   # + live API smoke test. Deliberately a different, higher-tier model than
                                   # GENERATE_MODEL (flagship vs. mid-tier within the same GPT-5.6 family) to
                                   # reduce self-preference bias in judging, per implementation_plan.md §10.
                                   # $4/$20 per 1M input/output tokens ($0.40 cached input), 1.05M context.
                                   # Same reasoning_effort="none" requirement for temperature/seed as above.
REASONING_EFFORT_FOR_TEMPERATURE = "none"  # required by GENERATE_MODEL and JUDGE_MODEL (GPT-5.6 family) to
                                            # accept temperature=0 / seed at all; their default effort ("medium")
                                            # rejects any temperature other than 1. Empirically verified via the
                                            # live API, not assumed from docs (which don't state this explicitly).
LLM_TEMPERATURE = 0  # deterministic for reproducibility

# === LLM intent-classifier milestone (added; does not change any constant above) ===
LLM_SEED = 42  # OpenAI 'seed' param for the classify() calls, supplementing temperature=0
FEWSHOT_MIN_PER_INTENT = 3
FEWSHOT_MAX_PER_INTENT = 5

# === Retrieval ===
EMBEDDING_MODEL = "text-embedding-3-small"  # verified against official OpenAI docs (see evaluation/embeddings.py); OpenAI API, not a local/sentence-transformers model
NEAR_DUPLICATE_THRESHOLD = 0.95
MIN_CUSTOMER_MSG_LENGTH = 10  # chars; exclude very short messages from index

# === Retrieval index (added; additive only, does not change any constant above) ===
RETRIEVAL_SAMPLE_SIZE = 3000  # simple random sample of the deduplicated RETRIEVAL pairs
RETRIEVAL_SAMPLE_SEED = 42    # reuses the project's established seed=42 convention
RETRIEVAL_INDEX_DIR = CACHE_DIR / "retrieval_index"  # gitignored (under cache/); embeddings.npy + metadata.jsonl + manifest.json

# === Experiment 3 (k-ablation) sweep concurrency ===
# Verified 2026-09-15 via live x-ratelimit-* response headers on this account for the
# actual chat/completions calls made by GENERATE_MODEL and JUDGE_MODEL (not assumed from
# the embeddings endpoint or from generic docs): both gpt-5.6-terra and gpt-5.6-sol sit in
# a 500 requests/min, 500,000 tokens/min bucket (per model). SWEEP_MAX_WORKERS=8 keeps
# in-flight requests per model comfortably under both ceilings even at worst-case latency
# (measured pilot average ~3s/call): ~8 workers / ~3s ~= 160 req/min (~3x headroom under
# 500 rpm) and ~8 * ~700 tok / 3s ~= 112,000 tok/min (~4.5x headroom under 500,000 tpm).
# Configurable (not hard-coded into evaluation/run_k_ablation_sweep.py's business logic)
# so it can be tuned down (flaky network) or up (if a higher tier is confirmed) without
# touching the sweep logic itself.
SWEEP_MAX_WORKERS = 8

# === Manual retrieval-inspection scaffold (Part 5, implementation_plan.md §9) ===
RETRIEVAL_INSPECTION_SAMPLE_SIZE = 20
RETRIEVAL_INSPECTION_SEED = 20  # fixed, documented, distinct from other project seeds so this
                                 # 20-example human-review sample is independently reproducible

# === Ensure directories exist ===
def ensure_dirs():
    for d in [DATA_DIR, DISCOVERY_DIR, GOLDEN_DIR, CACHE_DIR, EVAL_DIR]:
        d.mkdir(parents=True, exist_ok=True)
