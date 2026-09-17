"""
Tests for evaluation/analyze_judge_human_agreement.py.

No API calls anywhere; extraction/validation tests use small SYNTHETIC data
(never the real 40-example workbook) so they stay fast and independent. The
kappa computation is cross-checked directly against sklearn.metrics.
cohen_kappa_score (the same library the module itself uses) plus hand-verifiable
edge cases (perfect agreement, and quadratic-vs-unweighted sensitivity to gap
size), matching this project's established "cross-check the wrapper against a
direct library call" testing convention (see e.g. evaluation/test_k_ablation_stats.py).
"""
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook
from scipy.stats import spearmanr
from sklearn.metrics import cohen_kappa_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.analyze_judge_human_agreement import (
    AGREEMENT_OUTPUT_PATH,
    AgreementAnalysisError,
    bootstrap_kappa_ci,
    compute_dimension_stats,
    find_large_disagreements,
    read_workbook_rows,
    validate_context_matches_ground_truth,
    validate_human_scores,
)
from evaluation.build_judge_human_calibration_workbook import K_ABLATION_SWEEP_PATH, XLSX_PATH


# ---------------------------------------------------------------------------
# Synthetic workbook fixture (never the real 40)
# ---------------------------------------------------------------------------

def _write_synthetic_workbook(path, rows, tamper=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "CALIBRATION_REVIEW"
    headers = ["Example ID", "Tweet ID", "Customer Message", "Generated Reply (k=3)"]
    for i in range(1, 4):
        headers += [f"Retrieved Example {i} - Customer", f"Retrieved Example {i} - Spotify Support Reply"]
    headers += ["human_relevance (1-5)", "human_groundedness (1-5)", "human_helpfulness (1-5)",
                "human_tone (1-5)", "human_notes (optional)"]
    for c, h in enumerate(headers, start=1):
        ws.cell(row=1, column=c, value=h)

    for r_idx, row in enumerate(rows, start=2):
        ws.cell(row=r_idx, column=1, value=row["example_id"])
        ws.cell(row=r_idx, column=2, value=row["tweet_id"])
        ws.cell(row=r_idx, column=3, value=row["customer_text"])
        ws.cell(row=r_idx, column=4, value=row["generated_reply"])
        for i, ev in enumerate(row["retrieved"]):
            base = ord("E") + i * 2
            ws[f"{chr(base)}{r_idx}"] = ev["customer"]
            ws[f"{chr(base + 1)}{r_idx}"] = ev["reply"]
        ws[f"K{r_idx}"] = row.get("human_relevance")
        ws[f"L{r_idx}"] = row.get("human_groundedness")
        ws[f"M{r_idx}"] = row.get("human_helpfulness")
        ws[f"N{r_idx}"] = row.get("human_tone")
        ws[f"O{r_idx}"] = row.get("human_notes")

    if tamper is not None:
        tamper(ws)
    wb.save(path)
    return path


def _synthetic_row(example_id="SYN_0001", tweet_id="9001", **scores):
    return dict(
        example_id=example_id, tweet_id=tweet_id,
        customer_text="synthetic customer message", generated_reply="synthetic generated reply",
        retrieved=[dict(customer=f"hist cust {i}", reply=f"hist reply {i}") for i in range(1, 4)],
        human_relevance=scores.get("human_relevance", 4),
        human_groundedness=scores.get("human_groundedness", 4),
        human_helpfulness=scores.get("human_helpfulness", 4),
        human_tone=scores.get("human_tone", 4),
        human_notes=scores.get("human_notes"),
    )


# ---------------------------------------------------------------------------
# Extraction + human-score validation (synthetic)
# ---------------------------------------------------------------------------

def test_read_workbook_rows_extracts_known_synthetic_values(tmp_path):
    row = _synthetic_row(human_relevance=3, human_groundedness=5, human_helpfulness=2, human_tone=4,
                          human_notes="a note")
    path = tmp_path / "synthetic.xlsx"
    _write_synthetic_workbook(path, [row])
    rows = read_workbook_rows(path)
    assert len(rows) == 1
    assert rows[0]["human_relevance"] == 3
    assert rows[0]["human_groundedness"] == 5
    assert rows[0]["human_helpfulness"] == 2
    assert rows[0]["human_tone"] == 4
    assert rows[0]["human_notes"] == "a note"
    assert len(rows[0]["retrieved"]) == 3


def test_validate_human_scores_passes_on_complete_valid_rows():
    rows = [_synthetic_row(), _synthetic_row(example_id="SYN_0002", tweet_id="9002", human_relevance=1)]
    assert validate_human_scores(rows) is True


def test_validate_human_scores_reports_blank_field():
    row = _synthetic_row()
    row["human_tone"] = None
    with pytest.raises(AgreementAnalysisError, match="human_tone is blank"):
        validate_human_scores([row])


def test_validate_human_scores_reports_out_of_range():
    row = _synthetic_row()
    row["human_relevance"] = 6
    with pytest.raises(AgreementAnalysisError, match="out of range"):
        validate_human_scores([row])


def test_validate_human_scores_reports_non_whole_number():
    row = _synthetic_row()
    row["human_groundedness"] = 3.5
    with pytest.raises(AgreementAnalysisError, match="not a whole number"):
        validate_human_scores([row])


def test_validate_human_scores_reports_non_numeric():
    row = _synthetic_row()
    row["human_helpfulness"] = "high"
    with pytest.raises(AgreementAnalysisError, match="not numeric"):
        validate_human_scores([row])


def test_validate_human_scores_does_not_drop_or_impute_incomplete_rows():
    """A row missing one field must cause an explicit error naming that row --
    never be silently skipped while other rows are scored."""
    complete_row = _synthetic_row(example_id="SYN_OK", tweet_id="1")
    incomplete_row = _synthetic_row(example_id="SYN_BAD", tweet_id="2")
    incomplete_row["human_relevance"] = None
    with pytest.raises(AgreementAnalysisError, match="SYN_BAD"):
        validate_human_scores([complete_row, incomplete_row])


# ---------------------------------------------------------------------------
# Context re-derivation against ground truth (synthetic tamper cases)
# ---------------------------------------------------------------------------

requires_real_data = pytest.mark.skipif(
    not (XLSX_PATH.exists() and K_ABLATION_SWEEP_PATH.exists()),
    reason="Real calibration workbook or sweep JSON not present locally.",
)


@requires_real_data
def test_validate_context_matches_ground_truth_passes_on_real_workbook():
    rows = read_workbook_rows(XLSX_PATH)
    assert validate_context_matches_ground_truth(rows) is True


@requires_real_data
def test_validate_context_matches_ground_truth_rejects_tampered_copy(tmp_path):
    import shutil
    tampered = tmp_path / "tampered.xlsx"
    shutil.copy(XLSX_PATH, tampered)
    from openpyxl import load_workbook
    wb = load_workbook(tampered)
    ws = wb["CALIBRATION_REVIEW"]
    ws["D2"] = "this generated reply was tampered with"
    wb.save(tampered)

    rows = read_workbook_rows(tampered)
    with pytest.raises(AgreementAnalysisError, match="generated_reply"):
        validate_context_matches_ground_truth(rows)


# ---------------------------------------------------------------------------
# Kappa computation -- cross-checked against sklearn directly + hand-verifiable cases
# ---------------------------------------------------------------------------

def test_compute_dimension_stats_perfect_agreement_gives_kappa_1():
    human = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
    llm = list(human)
    stats = compute_dimension_stats(human, llm)
    assert stats["exact_agreement_rate"] == 1.0
    assert stats["within_1_agreement_rate"] == 1.0
    assert stats["weighted_kappa"] == pytest.approx(1.0)
    assert stats["mean_signed_diff_human_minus_llm"] == 0.0


def test_compute_dimension_stats_kappa_matches_direct_sklearn_call():
    human = [1, 2, 3, 4, 5, 3, 2, 4, 1, 5, 2, 3, 4, 5, 1]
    llm =   [1, 3, 3, 4, 4, 2, 2, 5, 1, 5, 3, 3, 3, 5, 2]
    stats = compute_dimension_stats(human, llm)
    expected = cohen_kappa_score(human, llm, weights="quadratic", labels=[1, 2, 3, 4, 5])
    assert stats["weighted_kappa"] == pytest.approx(expected)


def test_compute_dimension_stats_spearman_matches_direct_scipy_call():
    human = [1, 2, 3, 4, 5, 3, 2, 4, 1, 5, 2, 3, 4, 5, 1]
    llm =   [1, 3, 3, 4, 4, 2, 2, 5, 1, 5, 3, 3, 3, 5, 2]
    stats = compute_dimension_stats(human, llm)
    expected_rho, _ = spearmanr(human, llm)
    assert stats["spearman_rho"] == pytest.approx(expected_rho)


def test_spearman_handles_tied_ranks_correctly():
    """Hand-verifiable tied-rank case: three tied 3's in human and three tied 2's in
    llm each collapse to the same average rank (2), so both sequences co-vary in rank
    exactly -- verified directly against scipy.stats.spearmanr's own tie-handling
    (average-rank method) rather than assumed."""
    human = [3, 3, 3, 4, 5]
    llm =   [2, 2, 2, 4, 5]
    stats = compute_dimension_stats(human, llm)
    expected_rho, _ = spearmanr(human, llm)
    assert stats["spearman_rho"] == pytest.approx(expected_rho)
    assert stats["spearman_rho"] == pytest.approx(1.0)


def test_quadratic_weighting_penalizes_large_gaps_more_than_small_ones():
    """A single large (4-point) miss should hurt weighted kappa more than the same
    NUMBER of small (1-point) misses -- the defining property of quadratic weights,
    verified directly rather than assumed."""
    human_big_gap = [1, 5, 3, 3, 3, 3, 3, 3, 3, 3]
    llm_big_gap =   [1, 1, 3, 3, 3, 3, 3, 3, 3, 3]  # one miss, off by 4
    human_small_gap = [1, 2, 3, 3, 3, 3, 3, 3, 3, 3]
    llm_small_gap =   [1, 1, 3, 3, 3, 3, 3, 3, 3, 3]  # one miss, off by 1

    kappa_big = compute_dimension_stats(human_big_gap, llm_big_gap)["weighted_kappa"]
    kappa_small = compute_dimension_stats(human_small_gap, llm_small_gap)["weighted_kappa"]
    assert kappa_big < kappa_small


def test_mean_signed_diff_detects_systematic_over_or_under_scoring():
    human = [3, 3, 3, 3]
    llm = [5, 5, 5, 5]  # judge consistently scores 2 points higher than human
    stats = compute_dimension_stats(human, llm)
    assert stats["mean_signed_diff_human_minus_llm"] == pytest.approx(-2.0)


def test_confusion_matrix_counts_are_correct():
    human = [5, 5, 3, 4]
    llm = [5, 4, 3, 4]
    stats = compute_dimension_stats(human, llm)
    cm = stats["confusion_matrix"]
    assert cm["human=5_llm=5"] == 1
    assert cm["human=5_llm=4"] == 1
    assert cm["human=3_llm=3"] == 1
    assert cm["human=4_llm=4"] == 1
    assert sum(cm.values()) == 4


def test_bootstrap_kappa_ci_contains_point_estimate_direction():
    human = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
    llm = human
    lo, hi, n_valid = bootstrap_kappa_ci(human, llm, n_resamples=500)
    assert lo <= 1.0 <= hi + 1e-9  # perfect agreement -> CI should sit at/near 1.0
    assert n_valid > 0


def test_bootstrap_kappa_ci_is_deterministic_for_a_fixed_seed():
    human = [1, 3, 5, 2, 4, 3, 1, 5, 2, 4]
    llm =   [1, 2, 5, 2, 3, 3, 1, 4, 2, 5]
    lo1, hi1, _ = bootstrap_kappa_ci(human, llm, n_resamples=500, seed=42)
    lo2, hi2, _ = bootstrap_kappa_ci(human, llm, n_resamples=500, seed=42)
    assert (lo1, hi1) == (lo2, hi2)


# ---------------------------------------------------------------------------
# 2+-point disagreements
# ---------------------------------------------------------------------------

def test_find_large_disagreements_identifies_only_2_point_gaps():
    rows = [
        _synthetic_row(example_id="SMALL_GAP", tweet_id="1", human_relevance=4),   # llm default via fixture below
        _synthetic_row(example_id="BIG_GAP", tweet_id="2", human_relevance=5),
        _synthetic_row(example_id="NO_GAP", tweet_id="3", human_relevance=3),
    ]
    llm_scores_by_tweet = {
        "1": dict(relevance=3, groundedness=4, helpfulness=4, tone=4, reasoning="r1"),  # diff=1, not flagged
        "2": dict(relevance=2, groundedness=4, helpfulness=4, tone=4, reasoning="r2"),  # diff=3, flagged
        "3": dict(relevance=3, groundedness=4, helpfulness=4, tone=4, reasoning="r3"),  # diff=0, not flagged
    }
    disagreements = find_large_disagreements(rows, llm_scores_by_tweet, threshold=2)
    assert len(disagreements) == 1
    assert disagreements[0]["example_id"] == "BIG_GAP"
    assert disagreements[0]["dimensions"]["relevance"]["diff"] == 3
    assert disagreements[0]["llm_reasoning"] == "r2"


def test_find_large_disagreements_includes_full_context():
    row = _synthetic_row(example_id="CTX", tweet_id="1", human_helpfulness=5, human_notes="my note")
    llm_scores_by_tweet = {"1": dict(relevance=4, groundedness=4, helpfulness=2, tone=4, reasoning="detailed reasoning")}
    disagreements = find_large_disagreements([row], llm_scores_by_tweet, threshold=2)
    d = disagreements[0]
    assert d["customer_text"] == row["customer_text"]
    assert d["generated_reply"] == row["generated_reply"]
    assert d["human_notes"] == "my note"
    assert d["llm_reasoning"] == "detailed reasoning"


# ---------------------------------------------------------------------------
# Zero API calls / no source mutation
# ---------------------------------------------------------------------------

def test_module_has_no_openai_or_retrieval_import():
    import evaluation.analyze_judge_human_agreement as mod
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "import openai" not in src
    assert "from openai" not in src
    assert "from evaluation.retrieval" not in src
    assert "from evaluation.embeddings" not in src
    assert "get_api_key()" not in src


@requires_real_data
def test_source_workbook_is_never_written_by_analysis():
    before = XLSX_PATH.stat().st_mtime
    read_workbook_rows(XLSX_PATH)
    after = XLSX_PATH.stat().st_mtime
    assert before == after


@requires_real_data
def test_source_sweep_json_is_never_written_by_analysis():
    before = K_ABLATION_SWEEP_PATH.stat().st_mtime
    validate_context_matches_ground_truth(read_workbook_rows(XLSX_PATH))
    after = K_ABLATION_SWEEP_PATH.stat().st_mtime
    assert before == after
