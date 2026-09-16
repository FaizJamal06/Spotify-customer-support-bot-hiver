"""
Part I, Stage 1: builds the human response-quality calibration workbook --

    evaluation/results/JUDGE_HUMAN_CALIBRATION_40.xlsx

-- for the 40-example shared calibration subset (the same 40 example_ids as
golden_set/TRIAGE_ANNOTATION_40.csv, per implementation_plan.md's "Judge
calibration subset ... intended to be reused later for judge calibration as
well" -- see golden_set/TRIAGE_ANNOTATION_PROTOCOL.md), at the k=3 generated-
response condition only (a deliberate pre-specified choice per this milestone's
instructions -- NOT changed after inspecting results).

This is a PRESENTATION/SCAFFOLD layer only. It makes ZERO API calls: it reads
ONLY two already-local files --

  - golden_set/TRIAGE_ANNOTATION_40.csv, used SOLELY to identify the 40 shared
    example_id/tweet_id pairs. Its triage_decision, escalation_reason, and notes
    columns are NEVER read into this script (see load_shared_example_ids() --
    those fields are not even present in the dict it returns).
  - evaluation/results/k_ablation_sweep.json, filtered to k=3 records for those
    40 tweet_ids, for customer_text, generated_reply, and the 3 retrieved-
    evidence pairs ACTUALLY SHOWN to the generator/judge (brand_text_shown --
    the same cleaned text both saw, per evaluation/generation.py's
    _render_evidence_block(); never brand_text_raw).

validate_source_completeness() is run BEFORE any workbook content is built: it
asserts, for all 40 shared examples, that a k=3 record exists with a non-empty
generated_reply, exactly 3 retrieved_evidence items, and complete judge_scores
(relevance/groundedness/helpfulness/tone) + judge_reasoning -- confirming the
LLM side is fully present in the cache (see PART 2 of the milestone report).
It raises loudly and refuses to build anything if any of that is missing --
this script never calls an API to fill a gap.

CRITICAL: judge_scores, judge_reasoning, and generation's grounding_notes are
read ONLY for this completeness check -- their VALUES are never written into
the workbook, a cell comment, a sheet, or anywhere else the human annotator
could see them. The human grades independently. See build_rows() and
build_review_sheet() below: neither ever touches those three keys after the
completeness check.

Run: python evaluation/build_judge_human_calibration_workbook.py
"""
import csv
import json
import math
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.protection import SheetProtection

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

TRIAGE_40_CSV_PATH = config.GOLDEN_DIR / "TRIAGE_ANNOTATION_40.csv"
K_ABLATION_SWEEP_PATH = config.EVAL_DIR / "k_ablation_sweep.json"
XLSX_PATH = config.EVAL_DIR / "JUDGE_HUMAN_CALIBRATION_40.xlsx"

CALIBRATION_K = 3  # frozen for this milestone -- see module docstring
EXPECTED_N_EXAMPLES = 40
EXPECTED_RETRIEVED_EVIDENCE_COUNT = 3  # == CALIBRATION_K

REQUIRED_JUDGE_SCORE_FIELDS = ("relevance", "groundedness", "helpfulness", "tone")

# Same rubric text the LLM judge was actually given (evaluation/generation.py's
# DEFAULT_JUDGE_RUBRIC, read here verbatim -- NOT the judge's scores or reasoning
# for any specific example) -- per implementation_plan.md §3 Experiment 4: "Human
# grader | Same inputs as LLM judge ...; same rubric."
RUBRIC_TEXT = """Score the generated reply on each dimension from 1 (worst) to 5 (best):

RELEVANCE: Does the reply directly address what the customer actually said or asked?
  1 = ignores or misunderstands the customer's message; 5 = squarely on-topic and specific to their issue.

GROUNDEDNESS: Is every specific factual claim in the reply (a stated cause, a specific step, a URL, a claim about policy, a reference to a prior case) actually supported by the retrieved evidence or by the customer's own message, with nothing fabricated?
  1 = invents specifics with no support; 5 = every specific claim is traceable to the evidence or the customer's message. A generic, non-specific reply (e.g. "please DM us" or "try restarting the app") that makes no unsupported specific claims should score in the middle-to-high range, not be penalized as if it had fabricated something.

HELPFULNESS: Would this reply meaningfully move the customer's issue forward -- a concrete next step, real information, or a clear acknowledgment plus escalation path?
  1 = useless or evasive; 5 = clearly moves the issue forward given the constraints of a short public reply.

TONE: Is the reply friendly, professional, and appropriate for a brand's public Twitter support account?
  1 = rude, robotic, or inappropriate; 5 = warm and on-brand.

Judge only from the customer message, the generated reply, and the retrieved historical examples shown to you on this sheet. You have NOT been given -- and must not assume -- any information about what actually happened in this customer's case, the "correct" answer, any internal label, or any other rating of this reply. Make your own independent judgment."""

HEADER_FILL = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
SOURCE_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
RETRIEVED_FILL = PatternFill(start_color="EAF1F8", end_color="EAF1F8", fill_type="solid")
GENERATED_FILL = PatternFill(start_color="EFE6F7", end_color="EFE6F7", fill_type="solid")
EDIT_FILL = PatternFill(start_color="FFF8DC", end_color="FFF8DC", fill_type="solid")
THIN_GRAY = Side(style="thin", color="BFBFBF")
THICK_SEP = Side(style="medium", color="1F3864")
TOP_LEFT = Alignment(vertical="top", horizontal="left", wrap_text=False)
TOP_LEFT_WRAP = Alignment(vertical="top", horizontal="left", wrap_text=True)
TOP_CENTER = Alignment(vertical="top", horizontal="center", wrap_text=False)

# (letter, header, width, wrap, kind) -- kind in {"source", "generated", "retrieved", "edit"}
COLUMNS = [
    ("A", "Example ID", 12, False, "source"),
    ("B", "Tweet ID", 13, False, "source"),
    ("C", "Customer Message", 40, True, "source"),
    ("D", "Generated Reply (k=3)", 40, True, "generated"),
    ("E", "Retrieved Example 1 - Customer", 30, True, "retrieved"),
    ("F", "Retrieved Example 1 - Spotify Support Reply", 30, True, "retrieved"),
    ("G", "Retrieved Example 2 - Customer", 30, True, "retrieved"),
    ("H", "Retrieved Example 2 - Spotify Support Reply", 30, True, "retrieved"),
    ("I", "Retrieved Example 3 - Customer", 30, True, "retrieved"),
    ("J", "Retrieved Example 3 - Spotify Support Reply", 30, True, "retrieved"),
    ("K", "human_relevance (1-5)", 12, False, "edit"),
    ("L", "human_groundedness (1-5)", 14, False, "edit"),
    ("M", "human_helpfulness (1-5)", 13, False, "edit"),
    ("N", "human_tone (1-5)", 10, False, "edit"),
    ("O", "human_notes (optional)", 36, True, "edit"),
]
LAST_COL_LETTER = "O"
SCORE_COLUMNS = ("K", "L", "M", "N")


# ---------------------------------------------------------------------------
# Loading (zero API calls -- two local files only)
# ---------------------------------------------------------------------------

def load_shared_example_ids():
    """Reads golden_set/TRIAGE_ANNOTATION_40.csv SOLELY for the shared
    example_id/tweet_id pairs. Returns a list of {example_id, tweet_id} dicts,
    in file order. Deliberately does NOT read triage_decision, escalation_reason,
    or notes -- those are not part of the returned dicts at all, so they cannot
    leak into anything built from this function's output."""
    with open(TRIAGE_40_CSV_PATH, encoding="utf-8") as f:
        lines = f.readlines()
    data_lines = [ln for ln in lines if not ln.startswith("#")]
    rows = list(csv.DictReader(data_lines))
    assert len(rows) == EXPECTED_N_EXAMPLES, (
        f"Expected {EXPECTED_N_EXAMPLES} rows in {TRIAGE_40_CSV_PATH}, found {len(rows)}"
    )
    return [dict(example_id=r["example_id"], tweet_id=r["tweet_id"]) for r in rows]


def load_k3_records_by_tweet_id():
    with open(K_ABLATION_SWEEP_PATH, encoding="utf-8") as f:
        sweep = json.load(f)
    records = [r for r in sweep["records"] if r["k"] == CALIBRATION_K]
    return {r["tweet_id"]: r for r in records}


def validate_source_completeness(shared_examples, k3_by_tweet):
    """Hard assertions, run BEFORE any workbook content is generated. Raises
    AssertionError (never proceeds) if any of the 40 shared examples is missing
    its k=3 record or any required field -- see module docstring. This is the
    Part 2 completeness check, re-verified programmatically (not just eyeballed)
    every time this script runs."""
    missing_record, incomplete = [], []
    for ex in shared_examples:
        r = k3_by_tweet.get(ex["tweet_id"])
        if r is None:
            missing_record.append(ex["tweet_id"])
            continue
        if not r.get("generated_reply"):
            incomplete.append((ex["tweet_id"], "generated_reply"))
        if len(r.get("retrieved_evidence", [])) != EXPECTED_RETRIEVED_EVIDENCE_COUNT:
            incomplete.append((ex["tweet_id"], f"retrieved_evidence (found {len(r.get('retrieved_evidence', []))})"))
        judge_scores = r.get("judge_scores", {})
        for field in REQUIRED_JUDGE_SCORE_FIELDS:
            if judge_scores.get(field) is None:
                incomplete.append((ex["tweet_id"], f"judge_scores.{field}"))
        if not r.get("judge_reasoning"):
            incomplete.append((ex["tweet_id"], "judge_reasoning"))

    if missing_record or incomplete:
        raise AssertionError(
            f"Source data incomplete -- refusing to build the workbook (zero-API-call "
            f"policy: this script cannot regenerate missing data). "
            f"Missing k={CALIBRATION_K} record entirely for tweet_id(s): {missing_record}. "
            f"Incomplete fields: {incomplete}"
        )
    return True


def build_rows():
    """Returns a list of 40 dicts (one per shared example), each with ONLY the
    fields the human-facing workbook is allowed to show: example_id, tweet_id,
    customer_text, generated_reply, and 3 retrieved (customer, brand_reply) pairs
    -- the SAME cleaned text (brand_text_shown) actually shown to the generator
    and the judge, never brand_text_raw. judge_scores/judge_reasoning/
    grounding_notes are read only inside validate_source_completeness() above and
    never touched again after that check -- they do not appear in this function's
    output at all.
    """
    shared_examples = load_shared_example_ids()
    k3_by_tweet = load_k3_records_by_tweet_id()
    validate_source_completeness(shared_examples, k3_by_tweet)

    rows = []
    for ex in shared_examples:
        r = k3_by_tweet[ex["tweet_id"]]
        retrieved = [
            dict(customer=ev["customer_text"], reply=ev["brand_text_shown"])
            for ev in r["retrieved_evidence"]
        ]
        rows.append(dict(
            example_id=ex["example_id"],
            tweet_id=ex["tweet_id"],
            customer_text=r["customer_text"],
            generated_reply=r["generated_reply"],
            retrieved=retrieved,
        ))
    return rows


# ---------------------------------------------------------------------------
# Row height estimation
# ---------------------------------------------------------------------------

def _lines_needed(text, col_width_chars):
    if not text:
        return 1
    chars_per_line = max(15, col_width_chars - 2)
    return max(1, math.ceil(len(text) / chars_per_line)) + 1


def estimate_row_height(wrapped_texts_and_widths, min_h=45, max_h=300):
    max_lines = max((_lines_needed(t, w) for t, w in wrapped_texts_and_widths), default=1)
    return max(min_h, min(max_h, 15 * max_lines + 10))


# ---------------------------------------------------------------------------
# Sheet builders
# ---------------------------------------------------------------------------

def build_review_sheet(wb, rows):
    ws = wb.active
    ws.title = "CALIBRATION_REVIEW"
    ws.sheet_view.showGridLines = False

    for letter, header, width, wrap, kind in COLUMNS:
        ws.column_dimensions[letter].width = width

    ws.row_dimensions[1].height = 40
    for letter, header, width, wrap, kind in COLUMNS:
        cell = ws[f"{letter}1"]
        cell.value = header
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)

    header_comments = {
        "K": "1 (worst) - 5 (best). See rubric on the Instructions sheet.",
        "L": "1 (worst) - 5 (best). Judge only claims traceable to the retrieved evidence or the customer's own message.",
        "M": "1 (worst) - 5 (best). Does the reply meaningfully move the issue forward?",
        "N": "1 (worst) - 5 (best). Friendly, professional, on-brand for public Twitter support?",
    }
    for letter, text in header_comments.items():
        ws[f"{letter}1"].comment = Comment(text, "Judge-Human Calibration")

    for row_idx, row in enumerate(rows, start=2):
        ws[f"A{row_idx}"] = row["example_id"]
        ws[f"B{row_idx}"] = row["tweet_id"]
        ws[f"C{row_idx}"] = row["customer_text"]
        ws[f"D{row_idx}"] = row["generated_reply"]

        wrapped = [(row["customer_text"], 40), (row["generated_reply"], 40)]
        for i, ev in enumerate(row["retrieved"]):
            base = ord("E") + i * 2
            cust_col, reply_col = chr(base), chr(base + 1)
            ws[f"{cust_col}{row_idx}"] = ev["customer"]
            ws[f"{reply_col}{row_idx}"] = ev["reply"]
            wrapped.append((ev["customer"], 30))
            wrapped.append((ev["reply"], 30))

        for letter, header, width, wrap, kind in COLUMNS:
            if kind == "edit":
                ws[f"{letter}{row_idx}"] = None  # genuinely blank

        for letter, header, width, wrap, kind in COLUMNS:
            cell = ws[f"{letter}{row_idx}"]
            if letter in ("A", "B") + SCORE_COLUMNS:
                cell.alignment = TOP_CENTER
            else:
                cell.alignment = TOP_LEFT_WRAP if wrap else TOP_LEFT
            fill = {"source": SOURCE_FILL, "generated": GENERATED_FILL,
                    "retrieved": RETRIEVED_FILL, "edit": EDIT_FILL}[kind]
            cell.fill = fill
            left_side = THICK_SEP if letter == "K" else THIN_GRAY
            cell.border = Border(top=THIN_GRAY, bottom=THIN_GRAY, left=left_side, right=THIN_GRAY)
            cell.protection = Protection(locked=(kind != "edit"))

        ws.row_dimensions[row_idx].height = estimate_row_height(wrapped)

    n = len(rows)
    last_row = n + 1

    for col in SCORE_COLUMNS:
        dv = DataValidation(
            type="whole", operator="between", formula1=1, formula2=5,
            allow_blank=True, showErrorMessage=True,
            errorTitle="Invalid score", error="Enter a whole number from 1 to 5.",
            showInputMessage=True, promptTitle="Score 1-5",
            prompt="Whole number, 1 (worst) to 5 (best). See the Instructions sheet for the rubric.",
        )
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}{last_row}")
    # human_notes (O) intentionally has NO data validation -- free text only.

    ws.auto_filter.ref = f"A1:{LAST_COL_LETTER}{last_row}"
    ws.freeze_panes = "A2"  # header row only -- no frozen columns, per this milestone's instruction
    ws.sheet_view.zoomScale = 100

    ws.protection = SheetProtection(
        sheet=True, formatCells=False, formatColumns=False, formatRows=False,
        autoFilter=False, sort=False, selectLockedCells=False, selectUnlockedCells=False,
        insertRows=True, insertColumns=True, deleteRows=True, deleteColumns=True, password=None,
    )
    return ws


def build_instructions_sheet(wb):
    ws = wb.create_sheet("Instructions")
    ws.column_dimensions["A"].width = 110
    ws.sheet_view.showGridLines = False

    title_font = Font(bold=True, size=15, color="1F3864")
    section_font = Font(bold=True, size=12, color="1F3864")
    body_font = Font(size=11)
    rubric_font = Font(size=10, name="Consolas")

    lines = [
        ("title", "Judge-Human Calibration (k=3) -- Instructions"),
        ("body", ""),
        ("section", "1. Purpose"),
        ("body", "This workbook lets you independently rate 40 generated customer-support "
                  "replies (all drawn from the k=3 retrieval condition) on the same four "
                  "dimensions an LLM judge already scored them on. Your ratings will later be "
                  "compared to the LLM judge's ratings to check whether the judge is reliable "
                  "enough to trust for the rest of this project's evaluation."),
        ("body", ""),
        ("section", "2. What you will NOT see, and why"),
        ("body", "The LLM judge's own scores and its written reasoning for each example are "
                  "deliberately NOT shown anywhere in this workbook -- seeing them first would "
                  "anchor your rating toward the judge's, defeating the purpose of an "
                  "independent check. You also will not see the gold SpotifyCares response, "
                  "the gold intent label, or any triage decision -- score only from what's on "
                  "this sheet."),
        ("body", ""),
        ("section", "3. What you ARE given, per row"),
        ("body", "Customer Message (the real customer's tweet), the Generated Reply (what the "
                  "k=3 pipeline produced), and up to 3 historical (Customer, Spotify support) "
                  "pairs -- the SAME retrieved evidence the generator and the judge both had "
                  "access to when this reply was produced."),
        ("body", ""),
        ("section", "4. Rubric (identical to what the LLM judge was given)"),
        ("rubric", RUBRIC_TEXT),
        ("body", ""),
        ("section", "5. How to use this workbook"),
        ("body", "1. Go to the CALIBRATION_REVIEW sheet."),
        ("body", "2. Columns A-J (gray/blue/purple, locked) are read-only context -- the "
                  "customer message, generated reply, and retrieved evidence."),
        ("body", "3. Columns K-N (pale yellow) are whole-number dropdowns, 1-5. Column O is "
                  "optional free-text notes."),
        ("body", "4. Score each row independently -- do not try to guess what the LLM judge "
                  "scored, and do not aim for a particular distribution across the 40 rows."),
    ]

    r = 1
    for kind, text in lines:
        cell = ws.cell(row=r, column=1, value=text)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if kind == "title":
            cell.font = title_font
            ws.row_dimensions[r].height = 26
        elif kind == "section":
            cell.font = section_font
            ws.row_dimensions[r].height = 20
        elif kind == "rubric":
            cell.font = rubric_font
            ws.row_dimensions[r].height = 320
        else:
            cell.font = body_font
            ws.row_dimensions[r].height = max(16, 15 * (1 + len(text) // 108)) if text else 8
        r += 1

    ws.freeze_panes = "A2"
    return ws


def main():
    rows = build_rows()  # raises AssertionError internally if source data is incomplete
    assert len(rows) == EXPECTED_N_EXAMPLES

    wb = Workbook()
    build_review_sheet(wb, rows)
    build_instructions_sheet(wb)

    config.ensure_dirs()
    wb.save(XLSX_PATH)
    print(f"Wrote {XLSX_PATH} ({len(rows)} examples, k={CALIBRATION_K}, all human score cells blank)")
    return rows


if __name__ == "__main__":
    main()
