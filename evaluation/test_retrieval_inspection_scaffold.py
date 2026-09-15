"""
Tests for evaluation/build_retrieval_inspection_scaffold.py: deterministic sampling and
the "qualitative judgment fields must remain genuinely blank" rule (Part 5).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.build_retrieval_inspection_scaffold import (
    QUALITATIVE_COLUMNS,
    build_scaffold_rows,
    load_golden_rows_raw,
    select_inspection_sample,
)


def test_select_inspection_sample_size_and_determinism():
    golden_rows = load_golden_rows_raw()
    sample1 = select_inspection_sample(golden_rows)
    sample2 = select_inspection_sample(golden_rows)
    assert len(sample1) == config.RETRIEVAL_INSPECTION_SAMPLE_SIZE == 20
    assert sample1 == sample2
    assert len(set(sample1)) == 20  # no duplicates


def test_select_inspection_sample_uses_configured_seed_not_hardcoded():
    golden_rows = load_golden_rows_raw()
    default_sample = select_inspection_sample(golden_rows)
    different_seed_sample = select_inspection_sample(golden_rows, seed=config.RETRIEVAL_INSPECTION_SEED + 1)
    assert default_sample != different_seed_sample  # proves the seed actually drives the outcome


def test_select_inspection_sample_all_ids_are_real_golden_tweet_ids():
    golden_rows = load_golden_rows_raw()
    sample = select_inspection_sample(golden_rows)
    all_ids = {r["tweet_id"] for r in golden_rows}
    assert set(sample).issubset(all_ids)


def test_select_inspection_sample_independent_of_row_order():
    """The sample must not depend on the incidental order rows are read from the CSV --
    only on the sorted tweet_id sequence."""
    golden_rows = load_golden_rows_raw()
    shuffled = list(reversed(golden_rows))
    assert select_inspection_sample(golden_rows) == select_inspection_sample(shuffled)


@pytest.mark.skipif(
    not (config.RETRIEVAL_INDEX_DIR / "manifest.json").exists(),
    reason="No real retrieval index at cache/retrieval_index/",
)
def test_qualitative_columns_are_genuinely_blank_in_built_rows():
    golden_rows = load_golden_rows_raw()
    selected = select_inspection_sample(golden_rows)[:2]  # keep the API-touching test small
    rows = build_scaffold_rows(golden_rows, selected)
    assert rows, "expected at least one retrieved row for the sampled examples"
    for row in rows:
        for col in QUALITATIVE_COLUMNS:
            assert row[col] == "", f"qualitative column {col!r} was pre-filled: {row[col]!r}"


@pytest.mark.skipif(
    not (config.RETRIEVAL_INDEX_DIR / "manifest.json").exists(),
    reason="No real retrieval index at cache/retrieval_index/",
)
def test_scaffold_rows_never_contain_gold_fields():
    golden_rows = load_golden_rows_raw()
    selected = select_inspection_sample(golden_rows)[:2]
    rows = build_scaffold_rows(golden_rows, selected)
    for row in rows:
        assert "human_gold_label" not in row
        assert "human_notes" not in row


@pytest.mark.skipif(
    not (config.RETRIEVAL_INDEX_DIR / "manifest.json").exists(),
    reason="No real retrieval index at cache/retrieval_index/",
)
def test_scaffold_uses_raw_brand_text_not_cleaned():
    """This scaffold judges retrieval quality itself, not the generator's presentation --
    it must show the RAW brand_text (agent sign-offs and all), not the Part-1-cleaned
    version used inside evaluation.generation."""
    golden_rows = load_golden_rows_raw()
    selected = select_inspection_sample(golden_rows)[:3]
    rows = build_scaffold_rows(golden_rows, selected)
    # at least one row's raw text should retain a trailing agent sign-off pattern
    # somewhere in this small sample (empirically true for ~72% of the corpus)
    import re
    signoff_re = re.compile(r"/[A-Z]{2,3}\s*$")
    assert any(signoff_re.search(r["retrieved_brand_text_raw"].rstrip()) for r in rows), (
        "expected at least one raw retrieved reply in this sample to still carry its "
        "original trailing sign-off (this scaffold must not clean brand_text)"
    )
