"""
Tests for evaluation/export_retrieval_inspection.py.

Uses small synthetic/fixture workbooks (never the real RETRIEVAL_INSPECTION_20.xlsx)
for the fast, isolated structural/validation tests, so these stay independent of the
real annotation content and don't need the retrieval index. The one test that
exercises the REAL xlsx + real ground-truth re-derivation is skipped automatically if
the real files aren't present, and it re-checks the cache-hit-only guarantee itself
(no test in this file ever risks a live API call).
"""
import csv
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.export_retrieval_inspection import (
    RetrievalInspectionExportError,
    _normalize_best_rank,
    _normalize_text,
    check_no_api_spend_required,
    export,
    rederive_ground_truth,
    read_workbook_rows,
    validate_and_extract,
    write_canonical_csv,
)
from evaluation.build_retrieval_inspection_workbook import XLSX_PATH

SHEET_NAME = "RETRIEVAL_REVIEW"


# ---------------------------------------------------------------------------
# Synthetic fixture workbook (fast, independent of real annotation content)
# ---------------------------------------------------------------------------

def _make_fixture_ground_truth():
    """Two synthetic golden examples with fabricated but internally-consistent
    ground truth (never touches the real retrieval index)."""
    return (
        ["111", "222"],
        {
            "111": dict(
                candidate_id="CAND_TEST1", customer_text="my account is locked",
                predicted_intent="ACCOUNT_ACCESS",
                ranked_evidence=[
                    dict(rank=i, similarity=round(0.9 - 0.05 * i, 4),
                         hist_customer=f"hist cust {i}", hist_brand=f"hist brand {i}")
                    for i in range(1, 6)
                ],
            ),
            "222": dict(
                candidate_id="CAND_TEST2", customer_text="how do I cancel premium",
                predicted_intent="SUBSCRIPTION_BILLING",
                ranked_evidence=[
                    dict(rank=i, similarity=round(0.8 - 0.05 * i, 4),
                         hist_customer=f"other cust {i}", hist_brand=f"other brand {i}")
                    for i in range(1, 6)
                ],
            ),
        },
    )


def _write_fixture_workbook(path, ground_truth, judgments=None, tamper=None):
    """Builds a minimal xlsx with the same column layout as the real workbook
    (A-D context, E-X five rank blocks, Y-AC judgments) for exactly the rows in
    ground_truth. `judgments`: tweet_id -> dict of the 5 judgment fields (defaults
    to a valid filled-in set). `tamper`: optional fn(ws) applied after writing
    correct data, to deliberately corrupt one cell for negative tests."""
    judgments = judgments or {}
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    headers = ["Example ID", "Customer Tweet ID", "Customer Message", "Predicted Intent"]
    for rank in range(1, 6):
        headers += [f"Rank {rank}", f"Rank {rank} Similarity",
                    f"Rank {rank} Historical Customer", f"Rank {rank} Historical Brand Reply"]
    headers += ["Retrieval Usefulness", "Best Rank", "Relevance Problem", "Grounding Value",
                "Overall Observation (optional)"]
    for c, h in enumerate(headers, start=1):
        ws.cell(row=1, column=c, value=h)

    row_idx = 2
    for tweet_id, gt in ground_truth.items():
        ws.cell(row=row_idx, column=1, value=gt["candidate_id"])
        ws.cell(row=row_idx, column=2, value=tweet_id)
        ws.cell(row=row_idx, column=3, value=gt["customer_text"])
        ws.cell(row=row_idx, column=4, value=gt["predicted_intent"])
        for ev in gt["ranked_evidence"]:
            base = ord("E") + (ev["rank"] - 1) * 4
            rank_col, sim_col, cust_col, brand_col = (chr(base), chr(base + 1), chr(base + 2), chr(base + 3))
            ws[f"{rank_col}{row_idx}"] = ev["rank"]
            ws[f"{sim_col}{row_idx}"] = ev["similarity"]
            ws[f"{cust_col}{row_idx}"] = ev["hist_customer"]
            ws[f"{brand_col}{row_idx}"] = ev["hist_brand"]

        j = judgments.get(tweet_id, dict(
            retrieval_usefulness="USEFUL", best_rank="1",
            relevance_problem="NONE", grounding_value="STRONG", overall_observation="",
        ))
        ws[f"Y{row_idx}"] = j["retrieval_usefulness"]
        ws[f"Z{row_idx}"] = j["best_rank"]
        ws[f"AA{row_idx}"] = j["relevance_problem"]
        ws[f"AB{row_idx}"] = j["grounding_value"]
        ws[f"AC{row_idx}"] = j["overall_observation"]
        row_idx += 1

    if tamper is not None:
        tamper(ws)

    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def test_normalize_text_handles_none_and_crlf():
    assert _normalize_text(None) == ""
    assert _normalize_text("a\r\nb\r") == "a\nb"
    assert _normalize_text("  padded  ") == "padded"


def test_normalize_best_rank_handles_int_float_string_none():
    assert _normalize_best_rank(None) == ""
    assert _normalize_best_rank(1) == "1"
    assert _normalize_best_rank(4.0) == "4"
    assert _normalize_best_rank("NONE") == "NONE"
    assert _normalize_best_rank(" 3 ") == "3"


# ---------------------------------------------------------------------------
# read_workbook_rows against a synthetic fixture
# ---------------------------------------------------------------------------

def test_read_workbook_rows_reads_known_fixture_values(tmp_path):
    _, ground_truth = _make_fixture_ground_truth()
    xlsx = tmp_path / "fixture.xlsx"
    _write_fixture_workbook(xlsx, ground_truth, judgments={
        "111": dict(retrieval_usefulness="USEFUL", best_rank="2",
                    relevance_problem="NONE", grounding_value="MODERATE", overall_observation="fine"),
        "222": dict(retrieval_usefulness="NOT_USEFUL", best_rank="NONE",
                    relevance_problem="WRONG_INTENT", grounding_value="NONE", overall_observation=""),
    })

    rows = read_workbook_rows(xlsx)
    assert len(rows) == 2
    by_tid = {r["tweet_id"]: r for r in rows}

    assert by_tid["111"]["candidate_id"] == "CAND_TEST1"
    assert by_tid["111"]["retrieval_usefulness"] == "USEFUL"
    assert by_tid["111"]["best_rank"] == "2"
    assert by_tid["111"]["grounding_value"] == "MODERATE"
    assert by_tid["111"]["overall_observation"] == "fine"

    assert by_tid["222"]["retrieval_usefulness"] == "NOT_USEFUL"
    assert by_tid["222"]["best_rank"] == "NONE"
    assert by_tid["222"]["relevance_problem"] == "WRONG_INTENT"


# ---------------------------------------------------------------------------
# validate_and_extract: success path + every mismatch type
# ---------------------------------------------------------------------------

def test_validate_and_extract_succeeds_on_matching_fixture(tmp_path):
    expected_ids, ground_truth = _make_fixture_ground_truth()
    xlsx = tmp_path / "fixture.xlsx"
    _write_fixture_workbook(xlsx, ground_truth)
    rows = read_workbook_rows(xlsx)

    extracted = validate_and_extract(rows, expected_ids, ground_truth)
    assert len(extracted) == 2
    assert extracted[0]["tweet_id"] == "111"  # sorted ascending by tweet_id
    assert extracted[1]["tweet_id"] == "222"
    assert extracted[0]["example_id"] == "CAND_TEST1"
    assert extracted[0]["retrieval_usefulness"] == "USEFUL"


def test_validate_and_extract_rejects_modified_customer_text(tmp_path):
    expected_ids, ground_truth = _make_fixture_ground_truth()
    xlsx = tmp_path / "fixture.xlsx"

    def tamper(ws):
        ws["C2"] = "this was edited by accident"
    _write_fixture_workbook(xlsx, ground_truth, tamper=tamper)
    rows = read_workbook_rows(xlsx)

    with pytest.raises(RetrievalInspectionExportError, match="customer_text"):
        validate_and_extract(rows, expected_ids, ground_truth)


def test_validate_and_extract_rejects_modified_similarity(tmp_path):
    expected_ids, ground_truth = _make_fixture_ground_truth()
    xlsx = tmp_path / "fixture.xlsx"

    def tamper(ws):
        ws["F2"] = 0.9999  # rank-1 similarity for row 2 (tweet 111)
    _write_fixture_workbook(xlsx, ground_truth, tamper=tamper)
    rows = read_workbook_rows(xlsx)

    with pytest.raises(RetrievalInspectionExportError, match="similarity"):
        validate_and_extract(rows, expected_ids, ground_truth)


def test_validate_and_extract_rejects_modified_retrieved_brand_text(tmp_path):
    expected_ids, ground_truth = _make_fixture_ground_truth()
    xlsx = tmp_path / "fixture.xlsx"

    def tamper(ws):
        ws["H2"] = "fabricated brand reply text"  # rank-1 historical brand reply
    _write_fixture_workbook(xlsx, ground_truth, tamper=tamper)
    rows = read_workbook_rows(xlsx)

    with pytest.raises(RetrievalInspectionExportError, match="brand-reply"):
        validate_and_extract(rows, expected_ids, ground_truth)


def test_validate_and_extract_rejects_modified_candidate_id(tmp_path):
    expected_ids, ground_truth = _make_fixture_ground_truth()
    xlsx = tmp_path / "fixture.xlsx"

    def tamper(ws):
        ws["A2"] = "CAND_WRONG"
    _write_fixture_workbook(xlsx, ground_truth, tamper=tamper)
    rows = read_workbook_rows(xlsx)

    with pytest.raises(RetrievalInspectionExportError, match="candidate_id"):
        validate_and_extract(rows, expected_ids, ground_truth)


def test_validate_and_extract_rejects_missing_row():
    expected_ids, ground_truth = _make_fixture_ground_truth()
    partial_rows = [dict(
        row_number=2, candidate_id=ground_truth["111"]["candidate_id"], tweet_id="111",
        customer_text=ground_truth["111"]["customer_text"], predicted_intent=ground_truth["111"]["predicted_intent"],
        ranked_evidence=ground_truth["111"]["ranked_evidence"],
        retrieval_usefulness="USEFUL", best_rank="1", relevance_problem="NONE",
        grounding_value="STRONG", overall_observation="",
    )]
    with pytest.raises(RetrievalInspectionExportError, match="Expected exactly"):
        validate_and_extract(partial_rows, expected_ids, ground_truth)


def test_validate_and_extract_rejects_invalid_enum_value(tmp_path):
    expected_ids, ground_truth = _make_fixture_ground_truth()
    xlsx = tmp_path / "fixture.xlsx"
    _write_fixture_workbook(xlsx, ground_truth, judgments={
        "111": dict(retrieval_usefulness="SORT_OF", best_rank="1",
                    relevance_problem="NONE", grounding_value="STRONG", overall_observation=""),
        "222": dict(retrieval_usefulness="USEFUL", best_rank="1",
                    relevance_problem="NONE", grounding_value="STRONG", overall_observation=""),
    })
    rows = read_workbook_rows(xlsx)
    with pytest.raises(RetrievalInspectionExportError, match="invalid retrieval_usefulness"):
        validate_and_extract(rows, expected_ids, ground_truth)


def test_validate_and_extract_allows_blank_judgment_fields(tmp_path):
    """Partial annotation must be valid -- blank judgment fields are not an error."""
    expected_ids, ground_truth = _make_fixture_ground_truth()
    xlsx = tmp_path / "fixture.xlsx"
    _write_fixture_workbook(xlsx, ground_truth, judgments={
        "111": dict(retrieval_usefulness="", best_rank="", relevance_problem="", grounding_value="", overall_observation=""),
        "222": dict(retrieval_usefulness="USEFUL", best_rank="1", relevance_problem="NONE", grounding_value="STRONG", overall_observation=""),
    })
    rows = read_workbook_rows(xlsx)
    extracted = validate_and_extract(rows, expected_ids, ground_truth)
    row111 = next(r for r in extracted if r["tweet_id"] == "111")
    assert row111["retrieval_usefulness"] == ""
    assert row111["best_rank"] == ""


# ---------------------------------------------------------------------------
# Granularity: one row per example, never duplicated across rank-rows
# ---------------------------------------------------------------------------

def test_output_has_one_row_per_example_not_per_retrieved_pair(tmp_path):
    """The core Step-1 requirement: a single per-example judgment must appear
    exactly once in the output -- never repeated/duplicated per retrieved pair,
    which would misrepresent a summary judgment as 5 independent rank judgments."""
    expected_ids, ground_truth = _make_fixture_ground_truth()
    xlsx = tmp_path / "fixture.xlsx"
    _write_fixture_workbook(xlsx, ground_truth)
    rows = read_workbook_rows(xlsx)
    extracted = validate_and_extract(rows, expected_ids, ground_truth)

    # exactly 2 output rows for 2 examples (10 retrieved pairs total across both) --
    # NOT 10 rows, and no tweet_id appears more than once.
    assert len(extracted) == 2
    tweet_ids = [r["tweet_id"] for r in extracted]
    assert len(tweet_ids) == len(set(tweet_ids))


def test_write_canonical_csv_produces_exactly_one_row_per_example(tmp_path):
    expected_ids, ground_truth = _make_fixture_ground_truth()
    xlsx = tmp_path / "fixture.xlsx"
    _write_fixture_workbook(xlsx, ground_truth)
    rows = read_workbook_rows(xlsx)
    extracted = validate_and_extract(rows, expected_ids, ground_truth)

    out_path = tmp_path / "out.csv"
    write_canonical_csv(extracted, out_path)

    with open(out_path, encoding="utf-8") as f:
        lines = f.readlines()
    data_lines = [ln for ln in lines if not ln.startswith("#")]
    written_rows = list(csv.DictReader(data_lines))
    assert len(written_rows) == 2  # one row per example, not per retrieved pair
    assert {r["tweet_id"] for r in written_rows} == {"111", "222"}


# ---------------------------------------------------------------------------
# API-spend safety
# ---------------------------------------------------------------------------

def test_check_no_api_spend_required_raises_for_uncached_text():
    with pytest.raises(RetrievalInspectionExportError, match="NOT already cached"):
        check_no_api_spend_required([f"definitely never embedded text {id(object())}"])


def test_check_no_api_spend_required_passes_for_already_cached_real_queries():
    """Uses the REAL 20 golden query texts -- these were embedded during the original
    scaffold build and prior verification task, so this must be a pure cache-hit
    check with no API call. Skipped if the retrieval index isn't present locally."""
    if not (config.RETRIEVAL_INDEX_DIR / "manifest.json").exists():
        pytest.skip("No real retrieval index at cache/retrieval_index/")
    from evaluation.build_retrieval_inspection_scaffold import load_golden_rows_raw, select_inspection_sample
    golden_rows = load_golden_rows_raw()
    selected = select_inspection_sample(golden_rows)
    by_id = {r["tweet_id"]: r for r in golden_rows}
    texts = [by_id[t]["target_message"] for t in selected]
    check_no_api_spend_required(texts)  # must not raise


# ---------------------------------------------------------------------------
# End-to-end against the REAL xlsx (skipped if not present; never risks API spend)
# ---------------------------------------------------------------------------

requires_real_workbook_and_index = pytest.mark.skipif(
    not (XLSX_PATH.exists() and (config.RETRIEVAL_INDEX_DIR / "manifest.json").exists()),
    reason="Real RETRIEVAL_INSPECTION_20.xlsx or retrieval index not present.",
)


@requires_real_workbook_and_index
def test_rederive_ground_truth_is_cache_hit_only_and_returns_20_examples():
    expected_ids, ground_truth = rederive_ground_truth()
    assert len(expected_ids) == 20
    assert len(ground_truth) == 20
    for tid, gt in ground_truth.items():
        assert len(gt["ranked_evidence"]) == 5


@requires_real_workbook_and_index
def test_export_against_real_workbook_produces_20_rows_with_no_pair_duplication(tmp_path):
    out_path = tmp_path / "real_export.csv"
    extracted = export(xlsx_path=XLSX_PATH, output_csv=out_path)
    assert len(extracted) == 20
    assert len({r["tweet_id"] for r in extracted}) == 20  # no duplicates
    assert out_path.exists()


@requires_real_workbook_and_index
def test_real_workbook_source_is_never_written():
    before = XLSX_PATH.stat().st_mtime
    rederive_ground_truth()
    read_workbook_rows(XLSX_PATH)
    after = XLSX_PATH.stat().st_mtime
    assert before == after
