"""
Tests for the triage annotation workbook (golden_set/TRIAGE_ANNOTATION_40.xlsx)
and its export utility (golden_set/export_triage_annotations.py).

Covers: workbook structure (sheets, row count, dropdown validation), that a
freshly-generated workbook's context fields match the canonical CSV, that the
xlsx -> csv export round-trips cleanly with blank annotations, and that the
export refuses (raises) when triage_decision is invalid or when a read-only
context field has been tampered with.
"""
import csv
import shutil
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.utils.cell import coordinate_from_string

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from golden_set.build_triage_workbook import (
    XLSX_PATH,
    build_annotation_sheet,
    build_instructions_sheet,
    build_reference_sheet,
    load_canonical_rows,
    main as build_main,
)
from golden_set.export_triage_annotations import (
    TriageExportError,
    export,
    load_expected_ids,
    load_golden_lookup,
    read_workbook_rows,
    validate_and_extract,
)

GOLDEN_SET_DIR = Path(__file__).resolve().parent
CANONICAL_CSV = GOLDEN_SET_DIR / "TRIAGE_ANNOTATION_40.csv"


def load_canonical_csv_rows():
    with open(CANONICAL_CSV, encoding="utf-8") as f:
        lines = f.readlines()
    data_lines = [ln for ln in lines if not ln.startswith("#")]
    return list(csv.DictReader(data_lines))


@pytest.fixture(scope="module")
def workbook_path():
    assert XLSX_PATH.exists(), f"{XLSX_PATH} does not exist -- run golden_set/build_triage_workbook.py first."
    return XLSX_PATH


@pytest.fixture
def blank_workbook_path(tmp_path):
    """
    Builds a fresh, isolated workbook with all annotation fields blank,
    entirely in a temp directory, using the same sheet-building functions
    as golden_set/build_triage_workbook.py. This never reads or writes the
    live golden_set/TRIAGE_ANNOTATION_40.xlsx, so it stays valid regardless
    of how far along the real annotation is.

    Context fields (example_id/tweet_id/human_gold_label/target_message)
    come from the canonical CSV -- those are validated elsewhere to match
    GOLDEN_200_FINAL.csv exactly, annotation or not. Only the three
    annotation fields are forced blank here.
    """
    rows = load_canonical_rows()
    blank_rows = []
    for row in rows:
        blank_row = dict(row)
        blank_row["triage_decision"] = ""
        blank_row["escalation_reason"] = ""
        blank_row["notes"] = ""
        blank_rows.append(blank_row)

    wb = Workbook()
    build_annotation_sheet(wb, blank_rows)
    build_instructions_sheet(wb)
    build_reference_sheet(wb)

    path = tmp_path / "blank_triage_workbook.xlsx"
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# Workbook structure
# ---------------------------------------------------------------------------

def test_workbook_exists_and_has_expected_sheets(workbook_path):
    wb = load_workbook(workbook_path)
    assert set(wb.sheetnames) == {"TRIAGE_ANNOTATION", "Instructions", "Reference"}


def test_exactly_40_annotation_rows(workbook_path):
    wb = load_workbook(workbook_path)
    ws = wb["TRIAGE_ANNOTATION"]
    data_rows = [r for r in range(2, ws.max_row + 1) if ws.cell(row=r, column=1).value]
    assert len(data_rows) == 40


def test_header_row_matches_expected_columns(workbook_path):
    wb = load_workbook(workbook_path)
    ws = wb["TRIAGE_ANNOTATION"]
    headers = [ws.cell(row=1, column=c).value for c in range(1, 8)]
    assert headers[0].startswith("Example ID")
    assert headers[1].startswith("Tweet ID")
    assert headers[2].startswith("Intent")
    assert headers[3].startswith("Customer Message")
    assert headers[4].startswith("Triage Decision")
    assert headers[5].startswith("Escalation Reason")
    assert headers[6].startswith("Annotator Notes")


def test_dropdown_data_validation_exists_for_triage_decision(workbook_path):
    wb = load_workbook(workbook_path)
    ws = wb["TRIAGE_ANNOTATION"]
    dvs = ws.data_validations.dataValidation
    assert len(dvs) >= 1

    e_col_dvs = [dv for dv in dvs if any(str(r).startswith("E") for r in dv.sqref.ranges)]
    assert len(e_col_dvs) == 1
    dv = e_col_dvs[0]
    assert dv.type == "list"
    assert "AUTO_HANDLE" in dv.formula1
    assert "HUMAN_ESCALATION" in dv.formula1


def test_no_dropdown_on_escalation_reason_column(workbook_path):
    # Escalation Reason (F) must stay free text -- protocol defines no
    # controlled vocabulary, so no list validation should target column F.
    wb = load_workbook(workbook_path)
    ws = wb["TRIAGE_ANNOTATION"]
    dvs = ws.data_validations.dataValidation
    f_col_dvs = [dv for dv in dvs if any(str(r).startswith("F") for r in dv.sqref.ranges)]
    assert f_col_dvs == []


def test_freeze_panes_and_autofilter_and_wrap_set(workbook_path):
    wb = load_workbook(workbook_path)
    ws = wb["TRIAGE_ANNOTATION"]

    # Assert the INTENDED freeze behavior, not the exact saved reference --
    # Excel rewrites freeze_panes' topLeftCell to the last-active cell on
    # save (e.g. "E35" instead of "E2"), which is a view-state detail, not
    # a defect. The structured pane data (xSplit/ySplit/state) is the
    # direct, non-string-parsed source of truth for what's actually frozen.
    pane = ws.sheet_view.pane
    assert pane is not None
    assert pane.state == "frozen"
    # xSplit=4 freezes columns A-D (the locked context columns), leaving
    # column E as the first scrollable column.
    assert pane.xSplit == 4
    # ySplit>=1 keeps the header row frozen/visible.
    assert pane.ySplit >= 1

    # Cross-check via the column/row components of freeze_panes itself:
    # column must be exactly "E"; row must be >=2 (header stays visible),
    # but no specific row number is asserted, since that reflects wherever
    # the file was last saved, not a defect.
    col_letters, row_number = coordinate_from_string(ws.freeze_panes)
    assert col_letters == "E"
    assert row_number >= 2

    assert ws.auto_filter.ref == "A1:G41"
    # Customer Message column should wrap
    assert ws["D2"].alignment.wrap_text is True
    assert ws["F2"].alignment.wrap_text is True
    assert ws["G2"].alignment.wrap_text is True
    # top vertical alignment
    assert ws["D2"].alignment.vertical == "top"


def test_column_widths_favor_customer_message(workbook_path):
    wb = load_workbook(workbook_path)
    ws = wb["TRIAGE_ANNOTATION"]
    width_a = ws.column_dimensions["A"].width
    width_d = ws.column_dimensions["D"].width
    assert width_d > width_a * 3


def test_row_heights_are_generous_for_reading(workbook_path):
    wb = load_workbook(workbook_path)
    ws = wb["TRIAGE_ANNOTATION"]
    for r in range(2, 42):
        assert ws.row_dimensions[r].height >= 30


def test_context_cells_locked_and_annotation_cells_unlocked(workbook_path):
    wb = load_workbook(workbook_path)
    ws = wb["TRIAGE_ANNOTATION"]
    assert ws.protection.sheet is True
    assert ws["A2"].protection.locked is True
    assert ws["D2"].protection.locked is True
    assert ws["E2"].protection.locked is False
    assert ws["F2"].protection.locked is False
    assert ws["G2"].protection.locked is False


def test_all_annotation_fields_blank_in_freshly_built_workbook(blank_workbook_path):
    # Deliberately built from an isolated, freshly-generated blank workbook
    # (never the live golden_set/TRIAGE_ANNOTATION_40.xlsx) -- this test
    # asserts what a NEW workbook looks like, not the current annotation
    # state, which is expected to have real decisions filled in.
    wb = load_workbook(blank_workbook_path)
    ws = wb["TRIAGE_ANNOTATION"]
    for r in range(2, 42):
        assert ws.cell(row=r, column=5).value in (None, "")
        assert ws.cell(row=r, column=6).value in (None, "")
        assert ws.cell(row=r, column=7).value in (None, "")


# ---------------------------------------------------------------------------
# Context fields match canonical CSV
# ---------------------------------------------------------------------------

def test_workbook_context_fields_match_canonical_csv_before_annotation(workbook_path):
    wb = load_workbook(workbook_path)
    ws = wb["TRIAGE_ANNOTATION"]
    csv_rows = {r["example_id"]: r for r in load_canonical_csv_rows()}

    for r in range(2, 42):
        example_id = ws.cell(row=r, column=1).value
        csv_row = csv_rows[example_id]
        assert str(ws.cell(row=r, column=2).value) == csv_row["tweet_id"]
        assert ws.cell(row=r, column=3).value == csv_row["human_gold_label"]
        assert ws.cell(row=r, column=4).value == csv_row["target_message"]


# ---------------------------------------------------------------------------
# Export round-trip
# ---------------------------------------------------------------------------

def test_export_round_trip_preserves_source_fields(tmp_path, workbook_path):
    out_csv = tmp_path / "roundtrip.csv"
    extracted = export(xlsx_path=workbook_path, output_csv=out_csv)
    assert len(extracted) == 40

    golden_lookup = load_golden_lookup()
    for r in extracted:
        golden = golden_lookup[r["example_id"]]
        assert r["tweet_id"] == golden["tweet_id"]
        assert r["human_gold_label"] == golden["human_gold_label"]
        assert r["target_message"] == golden["target_message"]

    with open(out_csv, encoding="utf-8") as f:
        content = f.read()
    assert "example_id,tweet_id,target_message,human_gold_label,triage_decision,escalation_reason,notes" in content


def test_export_blank_annotations_remain_valid(tmp_path, blank_workbook_path):
    # Same isolation rationale as test_all_annotation_fields_blank_in_freshly_built_workbook:
    # this exercises the export path against a workbook guaranteed blank,
    # independent of the live annotation state.
    out_csv = tmp_path / "blank.csv"
    extracted = export(xlsx_path=blank_workbook_path, output_csv=out_csv)
    assert all(r["triage_decision"] == "" for r in extracted)
    assert all(r["escalation_reason"] == "" for r in extracted)


def test_expected_ids_manifest_has_40_entries_matching_workbook_order(workbook_path):
    expected_ids = load_expected_ids()
    assert len(expected_ids) == 40
    wb = load_workbook(workbook_path)
    ws = wb["TRIAGE_ANNOTATION"]
    actual_ids = [ws.cell(row=r, column=1).value for r in range(2, 42)]
    assert actual_ids == expected_ids


# ---------------------------------------------------------------------------
# Rejection cases: invalid triage_decision / tampered context fields
# ---------------------------------------------------------------------------

def _copy_workbook(tmp_path, src):
    dst = tmp_path / "copy.xlsx"
    shutil.copy(src, dst)
    return dst


def test_invalid_triage_decision_is_rejected(tmp_path, workbook_path):
    dst = _copy_workbook(tmp_path, workbook_path)
    wb = load_workbook(dst)
    ws = wb["TRIAGE_ANNOTATION"]
    ws.cell(row=2, column=5, value="MAYBE_ESCALATE")
    wb.save(dst)

    with pytest.raises(TriageExportError, match="invalid triage_decision"):
        export(xlsx_path=dst, output_csv=tmp_path / "out.csv")


def test_valid_triage_decisions_are_accepted(tmp_path, workbook_path):
    dst = _copy_workbook(tmp_path, workbook_path)
    wb = load_workbook(dst)
    ws = wb["TRIAGE_ANNOTATION"]
    ws.cell(row=2, column=5, value="AUTO_HANDLE")
    ws.cell(row=3, column=5, value="HUMAN_ESCALATION")
    ws.cell(row=3, column=6, value="Angry customer, needs a human.")
    wb.save(dst)

    extracted = export(xlsx_path=dst, output_csv=tmp_path / "out.csv")
    by_id = {r["example_id"]: r for r in extracted}
    row2_id = load_expected_ids()[0]
    row3_id = load_expected_ids()[1]
    assert by_id[row2_id]["triage_decision"] == "AUTO_HANDLE"
    assert by_id[row3_id]["triage_decision"] == "HUMAN_ESCALATION"
    assert by_id[row3_id]["escalation_reason"] == "Angry customer, needs a human."


def test_modified_customer_message_is_rejected(tmp_path, workbook_path):
    dst = _copy_workbook(tmp_path, workbook_path)
    wb = load_workbook(dst)
    ws = wb["TRIAGE_ANNOTATION"]
    ws.cell(row=2, column=4, value="This message was tampered with.")
    wb.save(dst)

    with pytest.raises(TriageExportError, match="target_message"):
        export(xlsx_path=dst, output_csv=tmp_path / "out.csv")


def test_modified_intent_is_rejected(tmp_path, workbook_path):
    dst = _copy_workbook(tmp_path, workbook_path)
    wb = load_workbook(dst)
    ws = wb["TRIAGE_ANNOTATION"]
    ws.cell(row=2, column=3, value="SUBSCRIPTION_BILLING")
    wb.save(dst)

    with pytest.raises(TriageExportError, match="human_gold_label"):
        export(xlsx_path=dst, output_csv=tmp_path / "out.csv")


def test_modified_example_id_or_missing_row_is_rejected(tmp_path, workbook_path):
    dst = _copy_workbook(tmp_path, workbook_path)
    wb = load_workbook(dst)
    ws = wb["TRIAGE_ANNOTATION"]
    ws.cell(row=2, column=1, value="CAND_9999")
    wb.save(dst)

    with pytest.raises(TriageExportError):
        export(xlsx_path=dst, output_csv=tmp_path / "out.csv")


def test_reordered_rows_are_rejected(tmp_path, workbook_path):
    dst = _copy_workbook(tmp_path, workbook_path)
    wb = load_workbook(dst)
    ws = wb["TRIAGE_ANNOTATION"]

    row2 = [ws.cell(row=2, column=c).value for c in range(1, 8)]
    row3 = [ws.cell(row=3, column=c).value for c in range(1, 8)]
    for c, v in enumerate(row3, start=1):
        ws.cell(row=2, column=c, value=v)
    for c, v in enumerate(row2, start=1):
        ws.cell(row=3, column=c, value=v)
    wb.save(dst)

    with pytest.raises(TriageExportError, match="order"):
        export(xlsx_path=dst, output_csv=tmp_path / "out.csv")
