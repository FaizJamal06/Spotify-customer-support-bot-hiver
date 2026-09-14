"""
Builds golden_set/TRIAGE_ANNOTATION_40.xlsx -- the human-facing annotation
workbook -- from the canonical golden_set/TRIAGE_ANNOTATION_40.csv.

The CSV remains the canonical, machine-readable annotation record (see
golden_set/TRIAGE_ANNOTATION_PROTOCOL.md and golden_set/export_triage_annotations.py,
which converts filled-in workbooks back to that CSV). This script is the
reverse direction: CSV -> polished xlsx interface. It is read-only with
respect to GOLDEN_200_FINAL.csv and does not invent, infer, or pre-fill any
triage_decision / escalation_reason value -- those columns are written blank
whenever the source CSV has them blank (which is always true at the time this
script is normally run, since annotation happens in the workbook, not here).

Dropdown values for "Triage Decision" (AUTO_HANDLE / HUMAN_ESCALATION) were
specified explicitly by the human annotator for this workbook. "Escalation
Reason" is deliberately left as free text with NO dropdown: golden_set/
TRIAGE_ANNOTATION_PROTOCOL.md defines no controlled vocabulary for escalation
reasons, so this script does not invent one.

Run: python golden_set/build_triage_workbook.py
"""
import csv
import math
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.protection import SheetProtection

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

CSV_PATH = Path(__file__).resolve().parent / "TRIAGE_ANNOTATION_40.csv"
XLSX_PATH = Path(__file__).resolve().parent / "TRIAGE_ANNOTATION_40.xlsx"

TRIAGE_DECISION_VALUES = ["AUTO_HANDLE", "HUMAN_ESCALATION"]

INTENT_DESCRIPTIONS = {
    "ACCOUNT_ACCESS": "Login, password, account lockout, or account-recovery issues.",
    "SUBSCRIPTION_BILLING": "Subscription plans, payments, charges, refunds, billing issues.",
    "APP_TECH_ISSUE": "App crashes, playback bugs, device/connectivity problems.",
    "CONTENT_CATALOG": "Missing, incorrect, or requested tracks/albums/content in the catalog.",
    "FEATURE_FEEDBACK": "Feature requests, suggestions, or general product feedback.",
    "ARTIST_SUPPORT": "Artist-profile issues: merges, mislabeled albums, artist-page problems.",
    "GENERAL_HOW_TO_INFO": "How-to questions and general informational requests.",
    "UNKNOWN_OTHER": "Does not fit cleanly into any other category.",
}

HEADER_FILL = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
CONTEXT_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
EDIT_FILL = PatternFill(start_color="FFF8DC", end_color="FFF8DC", fill_type="solid")
THIN_GRAY = Side(style="thin", color="BFBFBF")
THICK_SEP = Side(style="medium", color="1F3864")
TOP_LEFT = Alignment(vertical="top", horizontal="left", wrap_text=False)
TOP_LEFT_WRAP = Alignment(vertical="top", horizontal="left", wrap_text=True)
TOP_CENTER = Alignment(vertical="top", horizontal="center", wrap_text=False)

COLUMNS = [
    # (letter, header, width, wrap, editable)
    ("A", "Example ID", 13, False, False),
    ("B", "Tweet ID", 13, False, False),
    ("C", "Intent (context -- do not change)", 24, False, False),
    ("D", "Customer Message (context -- do not change)", 72, True, False),
    ("E", "Triage Decision *", 20, False, True),
    ("F", "Escalation Reason (free text) *", 34, True, True),
    ("G", "Annotator Notes (optional)", 34, True, True),
]


def load_canonical_rows(csv_path=CSV_PATH):
    with open(csv_path, encoding="utf-8") as f:
        lines = f.readlines()
    data_lines = [ln for ln in lines if not ln.startswith("#")]
    reader = csv.DictReader(data_lines)
    return list(reader)


def estimate_row_height(message, col_width_chars=72, min_h=30, max_h=140):
    chars_per_line = max(20, col_width_chars - 2)
    lines = max(1, math.ceil(len(message) / chars_per_line))
    # a couple of extra lines of headroom for wrapped word-breaks
    lines += 1
    height = 15 * lines + 8
    return max(min_h, min(max_h, height))


def build_annotation_sheet(wb, rows):
    ws = wb.active
    ws.title = "TRIAGE_ANNOTATION"

    # Column widths
    for letter, header, width, wrap, editable in COLUMNS:
        ws.column_dimensions[letter].width = width

    # Header row
    ws.row_dimensions[1].height = 34
    for letter, header, width, wrap, editable in COLUMNS:
        cell = ws[f"{letter}1"]
        cell.value = header
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)

    # Data rows
    for i, row in enumerate(rows, start=2):
        message = row["target_message"]
        ws[f"A{i}"] = row["example_id"]
        ws[f"B{i}"] = row["tweet_id"]
        ws[f"C{i}"] = row["human_gold_label"]
        ws[f"D{i}"] = message
        ws[f"E{i}"] = row.get("triage_decision") or None
        ws[f"F{i}"] = row.get("escalation_reason") or None
        ws[f"G{i}"] = row.get("notes") or None

        for letter, header, width, wrap, editable in COLUMNS:
            cell = ws[f"{letter}{i}"]
            cell.alignment = TOP_LEFT_WRAP if wrap else (TOP_CENTER if letter in ("A", "B") else TOP_LEFT)
            cell.fill = EDIT_FILL if editable else CONTEXT_FILL
            left_side = THICK_SEP if letter == "E" else THIN_GRAY
            cell.border = Border(top=THIN_GRAY, bottom=THIN_GRAY, left=left_side, right=THIN_GRAY)
            cell.protection = Protection(locked=not editable)

        ws.row_dimensions[i].height = estimate_row_height(message)

    n_rows = len(rows)
    last_row = n_rows + 1

    # Data validation dropdown for Triage Decision
    dv = DataValidation(
        type="list",
        formula1='"' + ",".join(TRIAGE_DECISION_VALUES) + '"',
        allow_blank=True,
        showDropDown=False,  # showDropDown=False means the arrow IS shown (inverted XML flag)
        showErrorMessage=True,
        errorTitle="Invalid Triage Decision",
        error="Please choose either AUTO_HANDLE or HUMAN_ESCALATION from the dropdown.",
        showInputMessage=True,
        promptTitle="Triage Decision",
        prompt="Choose AUTO_HANDLE or HUMAN_ESCALATION.",
    )
    ws.add_data_validation(dv)
    dv.add(f"E2:E{last_row}")

    # AutoFilter
    ws.auto_filter.ref = f"A1:G{last_row}"

    # Freeze header row + context columns (A:D): pane freezes above row 2 and left of column E
    ws.freeze_panes = "E2"

    # Zoom / view
    ws.sheet_view.zoomScale = 100
    ws.sheet_view.showGridLines = False

    # Sheet protection: lock context cells, leave annotation cells editable,
    # keep filtering/sorting/selecting fully open (this is UX scaffolding,
    # not security -- no password).
    ws.protection = SheetProtection(
        sheet=True,
        formatCells=False,
        formatColumns=False,
        formatRows=False,
        autoFilter=False,
        sort=False,
        selectLockedCells=False,
        selectUnlockedCells=False,
        insertRows=True,
        insertColumns=True,
        deleteRows=True,
        deleteColumns=True,
        password=None,
    )

    return ws


def build_instructions_sheet(wb):
    ws = wb.create_sheet("Instructions")
    ws.column_dimensions["A"].width = 110
    ws.sheet_view.showGridLines = False

    title_font = Font(bold=True, size=14, color="1F3864")
    section_font = Font(bold=True, size=11, color="1F3864")
    body_font = Font(size=11)

    lines = [
        ("title", "Triage Annotation -- Instructions"),
        ("body", ""),
        ("body", "This workbook is the human annotation interface for the 40-example"
                  " triage subset described in golden_set/TRIAGE_ANNOTATION_PROTOCOL.md."
                  " The content below is drawn only from that protocol -- no new policy"
                  " is introduced here."),
        ("body", ""),
        ("section", "1. What you are deciding"),
        ("body", "For each of the 40 customer messages, decide how it should be"
                  " triaged: handled automatically by the system, or escalated to a"
                  " human agent. This is an additive triage judgment layered on top"
                  " of the already-frozen intent label -- it is not a re-judgment of"
                  " intent."),
        ("body", ""),
        ("section", "2. What AUTO_HANDLE means"),
        ("body", "The message can be safely handled by the automated support system"
                  " without human review."),
        ("body", ""),
        ("section", "3. What HUMAN_ESCALATION means"),
        ("body", "The message should be routed to a human agent rather than handled"
                  " automatically."),
        ("body", ""),
        ("section", "4. How to choose Escalation Reason"),
        ("body", "Escalation Reason is free text. The protocol does not define a fixed"
                  " set of reason categories, so none is imposed here -- write a brief,"
                  " plain-language reason when you choose HUMAN_ESCALATION. Leave it"
                  " blank for AUTO_HANDLE if there is nothing to note."),
        ("body", ""),
        ("section", "5. What to put in Notes"),
        ("body", "Annotator Notes is optional free text for your own use -- caveats,"
                  " uncertainty, or anything else worth recording about the example."),
        ("body", ""),
        ("section", "6. Intent is context only"),
        ("body", "The Intent column is the existing, frozen human_gold_label from"
                  " golden_set/GOLDEN_200_FINAL.csv. It is shown for context because"
                  " triage is additive to intent, not a re-judgment of it. Do NOT"
                  " change it -- the cell is locked, and the source-of-truth intent"
                  " gold set is never modified by this workbook."),
        ("body", ""),
        ("section", "7. Make an independent judgment"),
        ("body", "Base each triage decision on your own reading of the customer"
                  " message and the provided intent context -- there is no other"
                  " model or automated suggestion behind these cells; they were left"
                  " blank deliberately for you to fill in."),
        ("body", ""),
        ("section", "8. This is additive, not a modification"),
        ("body", "This annotation layer is separate from and additive to the frozen"
                  " intent gold set. It does not modify golden_set/GOLDEN_200_FINAL.csv"
                  " or any human_gold_label / human_notes value in any way."),
        ("body", ""),
        ("section", "How to use this workbook"),
        ("body", "1. Go to the TRIAGE_ANNOTATION sheet."),
        ("body", "2. Read the Customer Message and Intent for each row (gray columns,"
                  " locked)."),
        ("body", "3. In the Triage Decision column, pick AUTO_HANDLE or"
                  " HUMAN_ESCALATION from the dropdown."),
        ("body", "4. Optionally fill in Escalation Reason and Annotator Notes"
                  " (pale-yellow columns)."),
        ("body", "5. Save the file. When you're done, run"
                  " golden_set/export_triage_annotations.py to regenerate the"
                  " canonical golden_set/TRIAGE_ANNOTATION_40.csv."),
    ]

    r = 1
    for kind, text in lines:
        cell = ws.cell(row=r, column=1, value=text)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if kind == "title":
            cell.font = title_font
            ws.row_dimensions[r].height = 24
        elif kind == "section":
            cell.font = section_font
            ws.row_dimensions[r].height = 18
        else:
            cell.font = body_font
            ws.row_dimensions[r].height = 30 if text else 8
        r += 1

    return ws


def build_reference_sheet(wb):
    ws = wb.create_sheet("Reference")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 90

    ws["A1"] = "Frozen Intent Taxonomy (read-only reference)"
    ws["A1"].font = Font(bold=True, size=13, color="1F3864")
    ws.row_dimensions[1].height = 22
    ws.merge_cells("A1:B1")

    ws["A2"] = ("Reference only -- copied from config.FROZEN_LABELS / "
                "discovery/TAXONOMY_REVIEW_GUIDE.md. No new taxonomy rules are"
                " introduced here, and nothing on this sheet is editable input.")
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[2].height = 32
    ws.merge_cells("A2:B2")

    ws["A3"] = "Intent"
    ws["B3"] = "Description"
    for col in ("A3", "B3"):
        ws[col].font = HEADER_FONT
        ws[col].fill = HEADER_FILL
        ws[col].alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[3].height = 18

    r = 4
    for label in config.FROZEN_LABELS:
        ws.cell(row=r, column=1, value=label).alignment = TOP_LEFT
        desc_cell = ws.cell(row=r, column=2, value=INTENT_DESCRIPTIONS.get(label, ""))
        desc_cell.alignment = TOP_LEFT_WRAP
        ws.row_dimensions[r].height = 30
        r += 1

    ws.freeze_panes = "A4"
    return ws


def main():
    rows = load_canonical_rows()
    if len(rows) != 40:
        raise ValueError(f"Expected exactly 40 rows in {CSV_PATH}, found {len(rows)}.")

    wb = Workbook()
    build_annotation_sheet(wb, rows)
    build_instructions_sheet(wb)
    build_reference_sheet(wb)

    wb.save(XLSX_PATH)
    print(f"Wrote {XLSX_PATH} ({len(rows)} annotation rows)")


if __name__ == "__main__":
    main()
