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

# === Brand ===
BRAND_AUTHOR_ID = "SpotifyCares"

# === Random Seeds ===
SPLIT_SEED = 42
DISCOVERY_SAMPLE_SEED = 123
GOLDEN_SAMPLE_SEED = 456

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

CLASSIFY_MODEL = "gpt-4o-mini"
GENERATE_MODEL = "gpt-4o-mini"
JUDGE_MODEL = "gpt-4o"
LLM_TEMPERATURE = 0  # deterministic for reproducibility

# === Retrieval ===
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
NEAR_DUPLICATE_THRESHOLD = 0.95
MIN_CUSTOMER_MSG_LENGTH = 10  # chars; exclude very short messages from index

# === Ensure directories exist ===
def ensure_dirs():
    for d in [DATA_DIR, DISCOVERY_DIR, GOLDEN_DIR, CACHE_DIR, EVAL_DIR]:
        d.mkdir(parents=True, exist_ok=True)
