"""
Builds evaluation/results/RETRIEVAL_INSPECTION_20.xlsx -- a polished, human-friendly
Excel annotation workbook for the 20-example manual retrieval-inspection scaffold
(implementation_plan.md §9), from the existing, frozen:

    evaluation/results/retrieval_inspection_scaffold.csv

This script is a PRESENTATION/ANNOTATION layer only. It does not call the OpenAI API,
does not re-run retrieval, does not change similarity scores, ranking, customer
messages, retrieved evidence, or any other source field. It reads two additional
ALREADY-COMPUTED, ALREADY-FROZEN project artifacts purely to join in existing
identifiers/context (never new judgments, never inferred data):

  - golden_set/GOLDEN_200_FINAL.csv           -> candidate_id, for the "Example ID"
    column (the scaffold CSV only carries tweet_id; candidate_id is the project's
    existing stable identifier scheme, e.g. "CAND_0163" -- joined by tweet_id).
  - evaluation/results/llm_classifier_results.json -> predicted_intent, for the
    "Predicted Intent" column (Experiment 1's already-computed classifier output,
    joined by tweet_id -- NOT the gold intent label, and not recomputed here).

All five human-judgment columns (Retrieval Usefulness, Best Rank, Relevance Problem,
Grounding Value, Overall Observation) are written BLANK -- nothing is inferred,
pre-filled, or guessed on the annotator's behalf.

validate_source_rows() is run before writing anything: it asserts the CSV has exactly
20 golden examples, each with exactly its top-5 retrieved evidence (ranks 1-5, in
order), before any workbook content is generated.

Run: python evaluation/build_retrieval_inspection_workbook.py
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

SCAFFOLD_CSV_PATH = config.EVAL_DIR / "retrieval_inspection_scaffold.csv"
XLSX_PATH = config.EVAL_DIR / "RETRIEVAL_INSPECTION_20.xlsx"
CLASSIFIER_RESULTS_PATH = config.EVAL_DIR / "llm_classifier_results.json"

EXPECTED_N_EXAMPLES = 20
EXPECTED_RANKS = [1, 2, 3, 4, 5]

RETRIEVAL_USEFULNESS_VALUES = ["USEFUL", "PARTIALLY_USEFUL", "NOT_USEFUL", "HARMFUL"]
BEST_RANK_VALUES = ["1", "2", "3", "4", "5", "NONE"]
RELEVANCE_PROBLEM_VALUES = [
    "NONE", "WRONG_INTENT", "SUPERFICIAL_SIMILARITY", "TOO_GENERIC", "MULTI_ISSUE_MISMATCH", "OTHER",
]
GROUNDING_VALUE_VALUES = ["STRONG", "MODERATE", "WEAK", "NONE"]

RETRIEVAL_USEFULNESS_DEFS = {
    "USEFUL": "At least one retrieved example is clearly relevant to the customer's actual "
              "issue and could reasonably help a response generator answer this customer.",
    "PARTIALLY_USEFUL": "Some relevant evidence exists, but retrieval is mixed, generic, "
                         "incomplete, or only useful for part of the issue.",
    "NOT_USEFUL": "The retrieved examples do not materially help answer this customer's "
                  "message, even if they are superficially similar.",
    "HARMFUL": "The retrieved examples are likely to push generation toward an incorrect, "
               "irrelevant, stale, misleading, or inappropriate response. High bar -- not "
               "just stylistically generic.",
}
RELEVANCE_PROBLEM_DEFS = {
    "NONE": "Retrieved examples are substantively relevant.",
    "WRONG_INTENT": "The retrieval is about a materially different support intent.",
    "SUPERFICIAL_SIMILARITY": "Words/topics overlap, but the underlying customer problem differs.",
    "TOO_GENERIC": "The example is so generic that it provides little useful case-specific evidence.",
    "MULTI_ISSUE_MISMATCH": "Customer's issue and retrieved case overlap on only one component "
                             "while the main support problem differs.",
    "OTHER": "A different clear relevance problem.",
}
GROUNDING_VALUE_DEFS = {
    "STRONG": "Historical response gives concrete, relevant evidence that could help "
              "constrain or inform a grounded answer.",
    "MODERATE": "Some useful evidence exists, but it is incomplete or somewhat generic.",
    "WEAK": "Mostly generic phrasing, weakly related evidence, or little actionable grounding.",
    "NONE": "No meaningful grounding value.",
}

HEADER_FILL = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
SOURCE_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
RETRIEVED_FILL = PatternFill(start_color="EAF1F8", end_color="EAF1F8", fill_type="solid")
EDIT_FILL = PatternFill(start_color="FFF8DC", end_color="FFF8DC", fill_type="solid")
THIN_GRAY = Side(style="thin", color="BFBFBF")
THICK_SEP = Side(style="medium", color="1F3864")
TOP_LEFT = Alignment(vertical="top", horizontal="left", wrap_text=False)
TOP_LEFT_WRAP = Alignment(vertical="top", horizontal="left", wrap_text=True)
TOP_CENTER = Alignment(vertical="top", horizontal="center", wrap_text=False)
TOP_CENTER_WRAP = Alignment(vertical="top", horizontal="center", wrap_text=True)

# (letter, header, width, wrap, kind) -- kind in {"source", "retrieved", "edit"}
COLUMNS = [
    ("A", "Example ID", 12, False, "source"),
    ("B", "Customer Tweet ID", 15, False, "source"),
    ("C", "Customer Message", 46, True, "source"),
    ("D", "Predicted Intent", 20, False, "source"),
]
for rank in EXPECTED_RANKS:
    base = ord("E") + (rank - 1) * 4
    letters = [chr(base), chr(base + 1), chr(base + 2), chr(base + 3)]
    COLUMNS += [
        (letters[0], f"Rank {rank}", 7, False, "retrieved"),
        (letters[1], f"Rank {rank} Similarity", 10, False, "retrieved"),
        (letters[2], f"Rank {rank} Historical Customer", 42, True, "retrieved"),
        (letters[3], f"Rank {rank} Historical Brand Reply", 42, True, "retrieved"),
    ]
COLUMNS += [
    ("Y", "Retrieval Usefulness", 18, False, "edit"),
    ("Z", "Best Rank", 10, False, "edit"),
    ("AA", "Relevance Problem", 20, False, "edit"),
    ("AB", "Grounding Value", 14, False, "edit"),
    ("AC", "Overall Observation (optional)", 40, True, "edit"),
]

LAST_COL_LETTER = "AC"
FIRST_EDIT_COL_LETTER = "Y"


# ---------------------------------------------------------------------------
# Loading + validation (read-only)
# ---------------------------------------------------------------------------

def load_scaffold_rows():
    with open(SCAFFOLD_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_candidate_id_by_tweet_id():
    """golden_set/GOLDEN_200_FINAL.csv is frozen/read-only; this only reads it to join
    the existing candidate_id identifier by tweet_id -- no gold label/notes are read."""
    with open(config.GOLDEN_FINAL_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return {r["tweet_id"]: r["candidate_id"] for r in rows}


def load_predicted_intent_by_tweet_id():
    """Experiment 1's already-computed output (evaluation/results/llm_classifier_results.json),
    joined by tweet_id. This is the PREDICTED intent, not the gold label, and is not
    recomputed here -- purely a read of an existing artifact."""
    with open(CLASSIFIER_RESULTS_PATH, encoding="utf-8") as f:
        results = json.load(f)
    return {p["tweet_id"]: p["predicted_intent"] for p in results["predictions"]}


def group_by_example(rows):
    """golden_tweet_id -> list of its 5 rows, sorted by rank ascending."""
    by_example = {}
    for row in rows:
        by_example.setdefault(row["golden_tweet_id"], []).append(row)
    for tweet_id in by_example:
        by_example[tweet_id].sort(key=lambda r: int(r["rank"]))
    return by_example


def validate_source_rows(rows):
    """Hard assertions on the read-only source scaffold CSV, run BEFORE any workbook
    content is generated. Raises AssertionError with a clear message on any violation."""
    by_example = group_by_example(rows)
    assert len(by_example) == EXPECTED_N_EXAMPLES, (
        f"Expected {EXPECTED_N_EXAMPLES} golden examples in {SCAFFOLD_CSV_PATH}, "
        f"found {len(by_example)}."
    )
    for tweet_id, example_rows in by_example.items():
        ranks = [int(r["rank"]) for r in example_rows]
        assert ranks == EXPECTED_RANKS, (
            f"golden_tweet_id={tweet_id}: expected ranks {EXPECTED_RANKS}, found {ranks}."
        )
        # every message field must be non-empty (a genuinely present retrieval, not a gap)
        for r in example_rows:
            for field in ("golden_customer_text", "retrieved_customer_text", "retrieved_brand_text_raw"):
                assert r[field], f"golden_tweet_id={tweet_id} rank={r['rank']}: empty {field!r}."
    return by_example


# ---------------------------------------------------------------------------
# Row height estimation (accounts for every wrapped column in a row, not just one)
# ---------------------------------------------------------------------------

def _lines_needed(text, col_width_chars):
    if not text:
        return 1
    chars_per_line = max(15, col_width_chars - 2)
    return max(1, math.ceil(len(text) / chars_per_line)) + 1  # +1 headroom for word-break


def estimate_row_height(wrapped_texts_and_widths, min_h=45, max_h=300):
    max_lines = max((_lines_needed(text, width) for text, width in wrapped_texts_and_widths), default=1)
    height = 15 * max_lines + 10
    return max(min_h, min(max_h, height))


# ---------------------------------------------------------------------------
# Sheet builders
# ---------------------------------------------------------------------------

def build_review_sheet(wb, examples):
    """examples: list of dicts, one per golden example, each with keys example_id,
    tweet_id, customer_text, predicted_intent, and ranked_evidence (list of 5 dicts
    with rank/similarity/hist_customer/hist_brand)."""
    ws = wb.active
    ws.title = "RETRIEVAL_REVIEW"
    ws.sheet_view.showGridLines = False

    for letter, header, width, wrap, kind in COLUMNS:
        ws.column_dimensions[letter].width = width

    ws.row_dimensions[1].height = 46
    for letter, header, width, wrap, kind in COLUMNS:
        cell = ws[f"{letter}1"]
        cell.value = header
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)

    # Header tooltips for the four dropdown columns (defs are on the GUIDE/REFERENCE
    # sheets too; this puts a quick reminder right where the annotator is working).
    header_comments = {
        "Y": "USEFUL / PARTIALLY_USEFUL / NOT_USEFUL / HARMFUL -- see GUIDE and REFERENCE sheets for full definitions.",
        "Z": "Highest-ranked example that is genuinely USEFUL (not just highest similarity). Choose NONE if none are useful.",
        "AA": "Main relevance problem, if any. NONE if retrieval is substantively relevant.",
        "AB": "Usefulness of the historical reply AS EVIDENCE -- not whether it was factually correct.",
    }
    for letter, text in header_comments.items():
        ws[f"{letter}1"].comment = Comment(text, "Retrieval Inspection Guide")

    for row_idx, ex in enumerate(examples, start=2):
        ws[f"A{row_idx}"] = ex["example_id"]
        ws[f"B{row_idx}"] = ex["tweet_id"]
        ws[f"C{row_idx}"] = ex["customer_text"]
        ws[f"D{row_idx}"] = ex["predicted_intent"]

        wrapped_texts_and_widths = [(ex["customer_text"], 46)]

        for ev in ex["ranked_evidence"]:
            rank = ev["rank"]
            base = ord("E") + (rank - 1) * 4
            rank_col, sim_col, cust_col, brand_col = (chr(base), chr(base + 1), chr(base + 2), chr(base + 3))
            ws[f"{rank_col}{row_idx}"] = rank
            ws[f"{sim_col}{row_idx}"] = ev["similarity"]
            ws[f"{cust_col}{row_idx}"] = ev["hist_customer"]
            ws[f"{brand_col}{row_idx}"] = ev["hist_brand"]
            wrapped_texts_and_widths.append((ev["hist_customer"], 42))
            wrapped_texts_and_widths.append((ev["hist_brand"], 42))

        # Annotation columns Y-AC start genuinely blank.
        for letter, header, width, wrap, kind in COLUMNS:
            if kind != "edit":
                continue
            ws[f"{letter}{row_idx}"] = None

        for letter, header, width, wrap, kind in COLUMNS:
            cell = ws[f"{letter}{row_idx}"]
            if letter in ("A", "B", "D"):
                cell.alignment = TOP_CENTER_WRAP if wrap else TOP_CENTER
            elif letter in ("E", "F", "I", "J", "M", "N", "Q", "R", "U", "V", "Z"):
                cell.alignment = TOP_CENTER
            else:
                cell.alignment = TOP_LEFT_WRAP if wrap else TOP_LEFT

            fill = {"source": SOURCE_FILL, "retrieved": RETRIEVED_FILL, "edit": EDIT_FILL}[kind]
            cell.fill = fill

            left_side = THICK_SEP if letter == FIRST_EDIT_COL_LETTER else THIN_GRAY
            cell.border = Border(top=THIN_GRAY, bottom=THIN_GRAY, left=left_side, right=THIN_GRAY)
            cell.protection = Protection(locked=(kind != "edit"))

            if letter in ("F", "J", "N", "R", "V") and cell.value is not None:
                cell.number_format = "0.0000"

        ws.row_dimensions[row_idx].height = estimate_row_height(wrapped_texts_and_widths)

    n = len(examples)
    last_row = n + 1

    def add_dropdown(col_letter, values, title, prompt):
        dv = DataValidation(
            type="list",
            formula1='"' + ",".join(values) + '"',
            allow_blank=True,
            showDropDown=False,  # inverted XML flag: False actually SHOWS the dropdown arrow
            showErrorMessage=True,
            errorTitle=f"Invalid {title}",
            error=f"Please choose one of: {', '.join(values)}.",
            showInputMessage=True,
            promptTitle=title,
            prompt=prompt,
        )
        ws.add_data_validation(dv)
        dv.add(f"{col_letter}2:{col_letter}{last_row}")
        return dv

    add_dropdown("Y", RETRIEVAL_USEFULNESS_VALUES, "Retrieval Usefulness",
                 "USEFUL / PARTIALLY_USEFUL / NOT_USEFUL / HARMFUL. See GUIDE sheet.")
    add_dropdown("Z", BEST_RANK_VALUES, "Best Rank",
                 "Highest-ranked example that is genuinely useful (not highest similarity). NONE if none are useful.")
    add_dropdown("AA", RELEVANCE_PROBLEM_VALUES, "Relevance Problem",
                 "Main relevance problem, if any. NONE if substantively relevant.")
    add_dropdown("AB", GROUNDING_VALUE_VALUES, "Grounding Value",
                 "Usefulness of the historical reply as EVIDENCE, not whether it was factually correct.")
    # AC (Overall Observation) intentionally has NO data validation -- free text only.

    ws.auto_filter.ref = f"A1:{LAST_COL_LETTER}{last_row}"

    # Freeze only the header row -- no frozen columns. Freezing A:X (at Y) made
    # horizontal scrolling awkward across the 5 retrieved examples; row-only freeze
    # keeps the header visible while scrolling freely in both directions.
    ws.freeze_panes = "A2"

    ws.sheet_view.zoomScale = 100

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


def _write_lines(ws, lines, col_width=110):
    ws.column_dimensions["A"].width = col_width
    ws.sheet_view.showGridLines = False
    title_font = Font(bold=True, size=15, color="1F3864")
    section_font = Font(bold=True, size=12, color="1F3864")
    body_font = Font(size=11)
    bullet_font = Font(size=11, italic=True, color="333333")

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
        elif kind == "example":
            cell.font = bullet_font
            ws.row_dimensions[r].height = max(16, 15 * (1 + len(text) // (col_width - 2)))
        else:
            cell.font = body_font
            ws.row_dimensions[r].height = max(16, 15 * (1 + len(text) // (col_width - 2))) if text else 8
        r += 1


def build_guide_sheet(wb):
    ws = wb.create_sheet("GUIDE")

    lines = [
        ("title", "Retrieval Inspection -- Annotation Guide"),
        ("body", ""),
        ("section", "1. Purpose"),
        ("body", "We are inspecting whether semantic retrieval produced historical support "
                  "examples that are useful evidence for this customer's message."),
        ("body", ""),
        ("section", "2. What you are evaluating"),
        ("body", "Evaluate: substantive relevance; usefulness as historical evidence; whether "
                  "retrieval would help or hurt a response generator."),
        ("body", "Do NOT evaluate: whether the golden/predicted intent is correct; whether "
                  "Spotify's historical answer was objectively correct; whether the generated "
                  "response is good; whether the customer deserved the historical resolution; "
                  "model sophistication."),
        ("body", ""),
        ("section", "3. How to review each row"),
        ("body", "Step 1: Read the Customer Message carefully."),
        ("body", "Step 2: Look at Predicted Intent only as context. Do not correct it."),
        ("body", "Step 3: Read Rank 1 first, then the other retrieved examples."),
        ("body", "Step 4: Ask: \"Could these historical examples genuinely help answer THIS customer?\""),
        ("body", "Step 5: Choose Retrieval Usefulness."),
        ("body", "Step 6: Choose Best Rank."),
        ("body", "Step 7: Identify the main Relevance Problem, if any."),
        ("body", "Step 8: Rate Grounding Value."),
        ("body", "Step 9: Optionally write a short Overall Observation."),
        ("body", ""),
        ("section", "4. Important distinctions"),
        ("example", "\"Same topic\" is not the same as \"same support problem\"."),
        ("example", "\"Same keyword\" is not the same as \"useful retrieval\"."),
        ("example", "\"High cosine similarity\" is not the same as \"good retrieval\"."),
        ("example", "A generic DM redirect may be relevant but still provide weak grounding."),
        ("example", "A historical reply being useful does not mean it should be copied verbatim."),
        ("example", "A retrieval can be harmful if it encourages unsupported assumptions or "
                     "irrelevant historical policy/phrasing."),
        ("body", ""),
        ("section", "5. What counts as good retrieval?"),
        ("example", "The retrieved customer described the same underlying problem (not just "
                     "shared vocabulary), and the historical reply's action or information "
                     "would genuinely help this customer's specific case."),
        ("example", "Several of the top-5 examples independently point to the same course of "
                     "action for a matching problem -- convergent, substantive evidence."),
        ("example", "A retrieved reply gives a specific, actionable fact (a real explanation, a "
                     "concrete next step) that plausibly applies to this customer too."),
        ("example", "The single best-ranked example is a near-identical case, even if the "
                     "other four are weaker -- one strong match is enough for USEFUL."),
        ("body", ""),
        ("section", "6. What counts as bad retrieval?"),
        ("example", "All five examples share only surface keywords (e.g. \"@SpotifyCares\", "
                     "\"help\") with no real overlap in the customer's actual problem."),
        ("example", "The retrieved cases are about a different support intent entirely (e.g. "
                     "billing vs. playback), even if the wording is similar."),
        ("example", "Every retrieved reply is an interchangeable generic DM-redirect that would "
                     "apply to almost any message -- little case-specific value."),
        ("example", "The retrieved case matches only one minor detail while the customer's main "
                     "problem is something else entirely."),
        ("body", ""),
        ("section", "7. How to think about HARMFUL"),
        ("body", "HARMFUL is a high bar. Use it when the retrieved evidence could plausibly "
                  "make generation WORSE -- e.g. it would push a confident but wrong claim, an "
                  "outdated policy statement, or an assumption that doesn't hold for this "
                  "customer -- not merely because an example is mediocre or unhelpful. A "
                  "retrieval that is merely unhelpful is NOT_USEFUL, not HARMFUL."),
        ("body", ""),
        ("section", "8. Consistency rule"),
        ("body", "Judge each row independently. Do not try to make the 20 examples have a "
                  "balanced distribution across labels. Do not force a \"bad\" example to appear. "
                  "Do not change an annotation because it would make the final result look "
                  "better -- record what you actually observe."),
        ("body", ""),
        ("section", "How to use this workbook"),
        ("body", "1. Go to the RETRIEVAL_REVIEW sheet."),
        ("body", "2. Columns A-X (gray/blue, locked) are read-only source data -- the customer "
                  "message and the top-5 retrieved historical examples."),
        ("body", "3. Columns Y-AC (pale yellow) are yours to fill in. Y, Z, AA, AB are dropdowns; "
                  "AC is optional short free text."),
        ("body", "4. The view is frozen at column Y, so the annotation columns stay visible "
                  "while you scroll through the five retrieved examples."),
        ("body", "5. See the REFERENCE sheet for a compact lookup of every dropdown value's "
                  "definition while you work."),
    ]
    _write_lines(ws, lines)
    ws.freeze_panes = "A2"
    return ws


def build_reference_sheet(wb):
    ws = wb.create_sheet("REFERENCE")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 95

    r = 1
    ws.cell(row=r, column=1, value="Retrieval Inspection -- Reference").font = Font(bold=True, size=14, color="1F3864")
    ws.merge_cells(f"A{r}:B{r}")
    ws.row_dimensions[r].height = 22
    r += 2

    ws.cell(row=r, column=1, value="This is qualitative inspection, not a new model evaluation or "
                                    "relabeling pass.").font = Font(italic=True, size=11)
    ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True)
    ws.merge_cells(f"A{r}:B{r}")
    ws.row_dimensions[r].height = 20
    r += 1
    ws.cell(row=r, column=1, value="Similarity is evidence for ranking, not evidence that retrieval "
                                    "is useful.").font = Font(bold=True, italic=True, size=11, color="8B0000")
    ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True)
    ws.merge_cells(f"A{r}:B{r}")
    ws.row_dimensions[r].height = 20
    r += 2

    def write_section(title, definitions):
        nonlocal r
        ws.cell(row=r, column=1, value=title).font = Font(bold=True, size=12, color="1F3864")
        ws.merge_cells(f"A{r}:B{r}")
        ws.row_dimensions[r].height = 18
        r += 1
        header_row = r
        ws.cell(row=r, column=1, value="Value").font = HEADER_FONT
        ws.cell(row=r, column=2, value="Definition").font = HEADER_FONT
        for c in (1, 2):
            ws.cell(row=header_row, column=c).fill = HEADER_FILL
            ws.cell(row=header_row, column=c).alignment = Alignment(vertical="center")
        r += 1
        for value, definition in definitions.items():
            ws.cell(row=r, column=1, value=value).alignment = TOP_LEFT
            dcell = ws.cell(row=r, column=2, value=definition)
            dcell.alignment = TOP_LEFT_WRAP
            ws.row_dimensions[r].height = 32
            r += 1
        r += 1

    write_section("Retrieval Usefulness (column Y)", RETRIEVAL_USEFULNESS_DEFS)
    write_section("Relevance Problem (column AA)", RELEVANCE_PROBLEM_DEFS)
    write_section("Grounding Value (column AB)", GROUNDING_VALUE_DEFS)

    ws.cell(row=r, column=1, value="Best Rank (column Z)").font = Font(bold=True, size=12, color="1F3864")
    ws.merge_cells(f"A{r}:B{r}")
    ws.row_dimensions[r].height = 18
    r += 1
    ws.cell(row=r, column=1, value=(
        "Choose the highest-ranked retrieved example that is genuinely useful. This is NOT "
        "\"which has the highest similarity\" -- similarity is already provided in its own "
        "column. If none of the five are useful, choose NONE."
    )).alignment = TOP_LEFT_WRAP
    ws.merge_cells(f"A{r}:B{r}")
    ws.row_dimensions[r].height = 45

    ws.freeze_panes = "A4"
    return ws


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def build_examples(rows):
    """Joins in candidate_id and predicted_intent (both from existing, frozen
    project artifacts -- see module docstring), and shapes the validated scaffold
    rows into one dict per golden example, in a fixed order (sorted by tweet_id
    ascending -- deterministic)."""
    by_example = validate_source_rows(rows)
    candidate_id_by_tweet = load_candidate_id_by_tweet_id()
    predicted_intent_by_tweet = load_predicted_intent_by_tweet_id()

    examples = []
    for tweet_id in sorted(by_example.keys(), key=int):
        example_rows = by_example[tweet_id]
        first = example_rows[0]
        ranked_evidence = [
            dict(
                rank=int(r["rank"]),
                similarity=float(r["similarity_score"]),
                hist_customer=r["retrieved_customer_text"],
                hist_brand=r["retrieved_brand_text_raw"],
            )
            for r in example_rows
        ]
        examples.append(dict(
            example_id=candidate_id_by_tweet[tweet_id],
            tweet_id=tweet_id,
            customer_text=first["golden_customer_text"],
            predicted_intent=predicted_intent_by_tweet[tweet_id],
            ranked_evidence=ranked_evidence,
        ))
    return examples


def main():
    rows = load_scaffold_rows()
    validate_source_rows(rows)  # hard stop before any workbook content is generated
    examples = build_examples(rows)
    assert len(examples) == EXPECTED_N_EXAMPLES

    wb = Workbook()
    build_review_sheet(wb, examples)
    build_guide_sheet(wb)
    build_reference_sheet(wb)

    wb.save(XLSX_PATH)
    print(f"Wrote {XLSX_PATH} ({len(examples)} examples x 5 retrievals each, all annotation cells blank)")
    return examples


if __name__ == "__main__":
    main()
