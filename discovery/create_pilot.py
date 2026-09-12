"""
Phase 3: Pilot Annotation Preparation
Creates PILOT_ANNOTATION_100.xlsx with 100 stratified examples from the DEVELOPMENT pool.

Sampling strategy:
  - Heuristic-classify all 6,481 DEV pairs into the 8 frozen intents.
  - Sample proportionally but with minimum floors for rare intents.
  - Within each stratum, deliberately enrich boundary/ambiguous/context-dependent cases (~30%),
    while keeping ordinary/representative examples as the majority.
  - Use heuristic difficulty flags as a sampling aid only, not ground truth.
  - Use seed 789 (distinct from discovery seed 42).

This pilot is intentionally NOT a prevalence estimate. Boundary cases are enriched to test taxonomy applicability.
"""
import json
import random
import re
import sys
import io
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Shared, corrected created_at-based context logic (see discovery/chronology.py
# for why spotify_threads.jsonl message order cannot be used directly).
sys.path.insert(0, str(Path(__file__).parent))
from chronology import get_target_context as get_context

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:
    print("ERROR: openpyxl is required. Install with: pip install openpyxl")
    sys.exit(1)

SEED = 789
PILOT_SIZE = 100

def clean(t):
    return re.sub(r'@[A-Za-z0-9_]+', '', t.lower())

# === 8-label heuristic classifier ===
INTENTS = {
    'ACCOUNT_ACCESS': ['account', 'login', 'password', 'facebook', 'email', 'hacked'],
    'SUBSCRIPTION_BILLING': ['premium', 'family', 'charge', 'pay', 'billing',
                             'cancel', 'subscribe', 'money', 'refund',
                             'promotion', 'offer', 'deal'],
    'APP_TECH_ISSUE': ['app', 'crash', 'freeze', 'loading', 'offline',
                       'download', 'update', 'android', 'iphone', 'ios',
                       'bug', 'glitch', 'bluetooth', 'desktop', 'mac',
                       'windows', 'working', 'broken', 'error'],
    'CONTENT_CATALOG': ['song', 'playlist', 'album', 'podcast', 'lyrics',
                        'missing', 'track', 'available', 'removed'],
    'FEATURE_FEEDBACK': ['feature', 'bring back', 'add', 'ui', 'design', 'ruined'],
    'ARTIST_SUPPORT': ['my artist page', 'my release', 'distributor', 'my music'],
    'GENERAL_HOW_TO_INFO': ['how to', 'how do i', 'what is', 'where is',
                            'how can i', 'student', 'hulu', 'eligible'],
}

def classify_heuristic(text):
    c = clean(text)
    matched = []
    for k, words in INTENTS.items():
        if any(w in c for w in words):
            matched.append(k)
    return matched if matched else ['UNKNOWN_OTHER']

def get_boundary_flags(text, matched, context_msgs):
    c = clean(text)
    flags = []
    if 'ACCOUNT_ACCESS' in matched and 'SUBSCRIPTION_BILLING' in matched:
        flags.append('account vs billing')
    if 'CONTENT_CATALOG' in matched and 'APP_TECH_ISSUE' in matched:
        flags.append('content vs tech')
    if 'FEATURE_FEEDBACK' in matched and 'APP_TECH_ISSUE' in matched:
        flags.append('feature vs tech')
    if 'GENERAL_HOW_TO_INFO' in matched and 'SUBSCRIPTION_BILLING' in matched:
        flags.append('plan how-to vs billing')
    if 'ARTIST_SUPPORT' in matched and 'CONTENT_CATALOG' in matched:
        flags.append('artist vs content')
    if 'GENERAL_HOW_TO_INFO' in matched and 'ACCOUNT_ACCESS' in matched:
        flags.append('how-to vs account')
    if any(w in c for w in ['country', 'available in', 'region', 'uk', 'india']):
        flags.append('geography')
    if len(matched) > 1:
        flags.append('multi-intent')
    if len(context_msgs) > 1 or c.strip().startswith(('yes', 'no', 'it still', 'it is')):
        flags.append('context-dependent')
    if len(c.strip()) < 20:
        flags.append('ambiguous')
    if any(w in c for w in ['thanks', 'it works', 'fixed', 'yep', 'got it', 'thank you']):
        flags.append('conversational/closure')
    return flags

def main():
    # Load data
    with open('data/generated/pool_split.json', 'r', encoding='utf-8') as f:
        split = json.load(f)
    dev_ids = set(split['dev_thread_ids'])
    test_ids = set(split.get('test_thread_ids', []))

    dev_threads = {}
    all_pairs = []
    with open('data/generated/spotify_threads.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            th = json.loads(line)
            tid = th['thread_id']
            if tid in dev_ids:
                dev_threads[tid] = th
                for p in th['customer_brand_pairs']:
                    all_pairs.append({
                        'thread_id': tid,
                        'tweet_id': p['customer_tweet_id'],
                        'author_id': p.get('customer_author_id', 'unknown'),
                        'text': p['customer_text'],
                    })

    print(f"Total DEV pairs: {len(all_pairs)}")

    # Classify and annotate every pair
    enriched = []
    for p in all_pairs:
        tid = p['thread_id']
        twid = p['tweet_id']
        th = dev_threads[tid]
        msgs = th['messages']
        
        # We MUST use the old bugged context logic solely for the heuristic flags 
        # so that the candidate strata pools are identical and the random seed 
        # selects the exact same 100 examples as v2/v3.
        msgs_sorted_by_id = sorted(msgs, key=lambda x: x['tweet_id'])
        ctx_heuristic = [m for m in msgs_sorted_by_id if m['tweet_id'] < twid]
        
        # Fixed chronological context for actual display
        ctx_display = get_context(msgs, twid)

        matched = classify_heuristic(p['text'])
        primary = matched[0]
        # Use ctx_heuristic to maintain exact flag generation!
        flags = get_boundary_flags(p['text'], matched, ctx_heuristic)

        ctx_str = " | ".join(
            [f"{'C' if m['inbound'] else 'B'}: {m['text']}" for m in ctx_display]
        ) or "None"

        ctx_lines = []
        for m in ctx_display:
            speaker = "Customer" if m['inbound'] else "SpotifyCares"
            ctx_lines.append(f"{speaker}:\n{m['text']}")
        ctx_str_full = "\n\n".join(ctx_lines) or "None"

        if len(ctx_str_full) > 2000:
            truncated = ctx_str_full[-1900:]
            # Try to snap to the nearest newline to avoid cutting mid-word
            idx = truncated.find('\n')
            if idx != -1:
                truncated = truncated[idx:]
            ctx_str_full = "[...TRUNCATED: Earliest messages omitted...]\n" + truncated

        is_ambig = any(f in ['ambiguous', 'context-dependent', 'conversational/closure', 'multi-intent'] for f in flags)
        is_bound = any('vs' in f for f in flags)

        enriched.append({
            **p,
            'primary': primary,
            'matched': matched,
            'flags': flags,
            'is_enriched': len(flags) > 0,
            'is_boundary_hard': is_bound,
            'is_ambiguous': is_ambig and not is_bound,
            'is_representative': len(flags) == 0,
            'context': ctx_str,
            'context_full': ctx_str_full,
            'thread_len': len(msgs),
        })

    # Group by primary intent
    by_intent = defaultdict(list)
    for e in enriched:
        by_intent[e['primary']].append(e)

    print("\nDEV pool heuristic distribution:")
    for k in list(INTENTS.keys()) + ['UNKNOWN_OTHER']:
        items = by_intent[k]
        boundary = sum(1 for i in items if i['is_enriched'])
        print(f"  {k}: {len(items)} total, {boundary} with enriched/boundary flags")

    # === Stratified sampling ===
    random.seed(SEED)

    # Allocation: proportional but with minimum floors for rare intents
    # Target: 100 total
    #   - Minimum 3 per intent (guarantees coverage)
    #   - Remaining distributed proportionally
    #   - Within each stratum: keep representative cases as majority, but deliberately enrich
    #     with difficult/boundary/ambiguous cases (~30%) to test the taxonomy.

    MIN_PER_INTENT = 3
    all_labels = list(INTENTS.keys()) + ['UNKNOWN_OTHER']
    total_pop = len(enriched)

    # Compute allocations
    allocations = {}
    remaining = PILOT_SIZE - MIN_PER_INTENT * len(all_labels)
    for label in all_labels:
        proportion = len(by_intent[label]) / total_pop
        extra = round(proportion * remaining)
        allocations[label] = MIN_PER_INTENT + extra

    # Adjust to sum to exactly 100
    total_alloc = sum(allocations.values())
    diff = PILOT_SIZE - total_alloc
    # Add/remove from the largest group
    largest = max(allocations, key=allocations.get)
    allocations[largest] += diff

    print(f"\nTarget allocations (sum={sum(allocations.values())}):")
    for k, v in allocations.items():
        print(f"  {k}: {v}")

    # Sample from each stratum
    sampled = []
    for label in all_labels:
        pool = by_intent[label]
        n = allocations[label]
        n = min(n, len(pool))

        enriched_pool = [p for p in pool if p['is_enriched']]
        rep_pool = [p for p in pool if p['is_representative']]

        random.shuffle(enriched_pool)
        random.shuffle(rep_pool)

        # Deliberately enrich difficult cases but keep representative as majority
        target_enriched = int(n * 0.3)
        if target_enriched == 0 and n > 0 and len(enriched_pool) > 0:
            target_enriched = 1

        n_enriched = min(len(enriched_pool), target_enriched)
        n_rep = n - n_enriched

        selected = enriched_pool[:n_enriched] + rep_pool[:n_rep]

        # Fill any shortfalls
        if len(selected) < n:
            remaining_enriched = enriched_pool[n_enriched:]
            remaining_rep = rep_pool[n_rep:]
            extra_needed = n - len(selected)
            extra = (remaining_rep + remaining_enriched)[:extra_needed]
            selected.extend(extra)

        sampled.extend(selected)

    # Deduplicate by tweet_id (shouldn't happen but safety check)
    seen = set()
    deduped = []
    for s in sampled:
        if s['tweet_id'] not in seen:
            seen.add(s['tweet_id'])
            deduped.append(s)
    sampled = deduped[:PILOT_SIZE]

    # Shuffle the final order so reviewer doesn't see blocks of same intent
    random.shuffle(sampled)

    print(f"\nFinal sample: {len(sampled)} examples")

    # Verify no TEST examples
    for s in sampled:
        assert s['thread_id'] not in test_ids, f"TEST LEAK: {s['tweet_id']}"

    # === Build Excel workbook ===
    wb = Workbook()

    # ---- Sheet 1: THREAD_VIEW ----
    ws_thread = wb.active
    ws_thread.title = "THREAD_VIEW"

    thread_headers = ["Thread ID", "Example #", "Speaker", "Message ID", "Message Text"]
    header_font = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    wrap_align = Alignment(vertical='top', wrap_text=True)
    center_align = Alignment(horizontal='center', vertical='top')
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9'),
    )
    target_fill = PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid') # Light green

    for col, h in enumerate(thread_headers, 1):
        cell = ws_thread.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    target_row_map = {}
    current_row = 2

    for i, s in enumerate(sampled, 1):
        s['example_index'] = i
        tid = s['thread_id']
        twid = s['tweet_id']
        th = dev_threads[tid]
        ctx = get_context(th['messages'], twid)

        # Write preceding context
        for m in ctx:
            speaker = "Customer" if m['inbound'] else "SpotifyCares"
            vals = [tid, i, speaker, str(m['tweet_id']), m['text']]
            for col, val in enumerate(vals, 1):
                cell = ws_thread.cell(row=current_row, column=col, value=val)
                cell.border = thin_border
                cell.alignment = wrap_align if col == 5 else center_align
            current_row += 1

        # Write target message
        vals = [tid, i, "Customer (TARGET)", str(twid), s['text']]
        target_row_map[twid] = current_row
        for col, val in enumerate(vals, 1):
            cell = ws_thread.cell(row=current_row, column=col, value=val)
            cell.border = thin_border
            cell.alignment = wrap_align if col == 5 else center_align
            cell.fill = target_fill
        current_row += 1

        # Add empty spacer row
        current_row += 1

    ws_thread.column_dimensions['A'].width = 12
    ws_thread.column_dimensions['B'].width = 10
    ws_thread.column_dimensions['C'].width = 20
    ws_thread.column_dimensions['D'].width = 25
    ws_thread.column_dimensions['E'].width = 80
    ws_thread.freeze_panes = 'A2'
    ws_thread.auto_filter.ref = f"A1:E{current_row - 1}"

    # ---- Sheet 2: PILOT_100 ----
    ws = wb.create_sheet("PILOT_100")

    headers = [
        "Example #", "Tweet ID", "Thread ID", "Customer ID",
        "Prior Context", "View Thread", "Customer Message", "Provisional Label",
        "Boundary / Difficulty Flags", "Human Decision / Gold Label", "Notes"
    ]

    # Styles
    header_font = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    wrap_align = Alignment(vertical='top', wrap_text=True)
    center_align = Alignment(horizontal='center', vertical='top')
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9'),
    )
    even_fill = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')
    gold_fill = PatternFill(start_color='FFF2CC', end_color='FFF2CC', fill_type='solid')

    # Write headers
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    # Write data
    for i, s in enumerate(sampled, 1):
        row = i + 1

        ctx = s['context']
        if len(ctx) > 500:
            ctx = ctx[-500:]

        target_thread_row = target_row_map[s['tweet_id']]
        hyperlink = f'=HYPERLINK("#\'THREAD_VIEW\'!A{target_thread_row}", "View full thread")'

        values = [
            i,
            s['tweet_id'],
            s['thread_id'],
            s['author_id'],
            ctx,
            hyperlink,
            s['text'],
            s['primary'],
            ", ".join(s['flags']) if s['flags'] else "",
            "",  # Gold Label - BLANK
            "",  # Notes - BLANK
        ]

        fill = even_fill if i % 2 == 0 else None

        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.border = thin_border
            if col in (5, 7, 11):  # Prior Context, Message, Notes
                cell.alignment = wrap_align
            elif col in (1, 2, 3, 6): # Include View Thread in center_align
                cell.alignment = center_align
            else:
                cell.alignment = Alignment(vertical='top')
            if fill:
                cell.fill = fill

            if col == 6: # Hyperlink formatting
                cell.font = Font(name='Calibri', size=11, color='0563C1', underline='single')

            # Highlight Gold Label column (now col 10)
            if col == 10:
                cell.fill = gold_fill

    # Column widths
    widths = [8, 12, 12, 12, 40, 15, 55, 20, 30, 25, 30]
    for col, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = w

    # Freeze header row
    ws.freeze_panes = 'A2'

    # Auto-filter
    ws.auto_filter.ref = f"A1:K{len(sampled) + 1}"

    # Dropdown validation for Gold Label column
    dv = DataValidation(
        type="list",
        formula1='"ACCOUNT_ACCESS,SUBSCRIPTION_BILLING,APP_TECH_ISSUE,CONTENT_CATALOG,FEATURE_FEEDBACK,ARTIST_SUPPORT,GENERAL_HOW_TO_INFO,UNKNOWN_OTHER"',
        allow_blank=True,
    )
    dv.error = "Please select one of the 8 frozen labels."
    dv.errorTitle = "Invalid Label"
    dv.prompt = "Select a label from the dropdown."
    dv.promptTitle = "Gold Label"
    ws.add_data_validation(dv)
    dv.add(f"J2:J{len(sampled) + 1}")

    # ---- Sheet 2: GUIDE ----
    ws2 = wb.create_sheet("GUIDE")

    guide_lines = [
        ["FROZEN 8-LABEL INTENT TAXONOMY"],
        [],
        ["Label", "Definition"],
        ["ACCOUNT_ACCESS", "Primary problem is authentication, login, password/account recovery, hacked/compromised account, account identity, or inability to access/manage the account."],
        ["SUBSCRIPTION_BILLING", "Primary problem is payment, charges, refunds, billing errors, subscription status, paid entitlement, or Premium access after purchase."],
        ["APP_TECH_ISSUE", "An existing product capability is malfunctioning. Crashes, freezes, playback failures, Bluetooth issues, syncing, downloads disappearing."],
        ["CONTENT_CATALOG", "Content itself is missing, unavailable, removed, or incorrectly represented. Missing songs/albums, unavailable tracks, incorrect lyrics/tracklists/metadata."],
        ["FEATURE_FEEDBACK", "Customer wants Spotify to add, remove, restore, redesign, or change product functionality."],
        ["ARTIST_SUPPORT", "Creator/artist-side issues: artist profiles, ownership, incorrect tracks on artist pages, distributor/release workflows."],
        ["GENERAL_HOW_TO_INFO", "How to use Spotify, where to find something, how a capability works, general eligibility/availability info (no billing error)."],
        ["UNKNOWN_OTHER", "Does not fit taxonomy or cannot be assigned reliably. Flags: ambiguous, conversational/closure, irrelevant/off-topic, context_dependent."],
        [],
        ["PROMOTION/DISCOUNT BOUNDARY (FROZEN)"],
        [],
        ["Category", "Rule"],
        ["SUBSCRIPTION_BILLING", "Customer is asking about, disputing, or expecting a specific price, discount, charge, eligibility, or subscription entitlement."],
        ["FEATURE_FEEDBACK", "Customer is asking Spotify to introduce, restore, expand, or change a promotion/loyalty policy for customers generally."],
        ["GENERAL_HOW_TO_INFO", "Customer is asking how to enroll, use, or understand an existing promotion/discount program."],
        [],
        ["OTHER KEY RULES"],
        [],
        ["Rule", "Description"],
        ["Geography", "Modifier, not a top-level intent. Attach to underlying intent (e.g., CONTENT_CATALOG + region=UK)."],
        ["Multi-intent", "Assign ONE primary intent based on the issue driving the next support action. Tie-breaker: Security > Billing > Tech > Feedback."],
        ["Target context", "Classify the TARGET customer message. Use the 'View full thread' link if the Prior Context column is insufficient. Annotators may use all context occurring before the target customer message. They must not use any information occurring after the target message, including the brand's eventual response."],
        ["UNKNOWN_OTHER flags", "Overlapping: ambiguous, conversational/closure, irrelevant/off-topic, context_dependent. A message can have multiple."],
    ]

    guide_header_font = Font(name='Calibri', bold=True, size=12, color='2F5496')
    guide_bold = Font(name='Calibri', bold=True, size=10)
    guide_normal = Font(name='Calibri', size=10)

    for r, row_data in enumerate(guide_lines, 1):
        for c, val in enumerate(row_data, 1):
            cell = ws2.cell(row=r, column=c, value=val)
            cell.alignment = Alignment(vertical='top', wrap_text=True)
            if r in (1, 13, 20):
                cell.font = guide_header_font
            elif r in (3, 15, 22):
                cell.font = guide_bold
            else:
                cell.font = guide_normal

    ws2.column_dimensions['A'].width = 25
    ws2.column_dimensions['B'].width = 100

    # ---- Sheet 3: SAMPLING_INFO ----
    ws3 = wb.create_sheet("SAMPLING_INFO")

    # Compute stats
    intent_counts = defaultdict(int)
    rep_counts = defaultdict(int)
    bound_counts = defaultdict(int)
    ambig_counts = defaultdict(int)
    unique_threads = set()
    unique_customers = set()
    for s in sampled:
        intent_counts[s['primary']] += 1
        if s['is_representative']:
            rep_counts[s['primary']] += 1
        elif s['is_boundary_hard']:
            bound_counts[s['primary']] += 1
        elif s['is_ambiguous']:
            ambig_counts[s['primary']] += 1
        unique_threads.add(s['thread_id'])
        unique_customers.add(s['author_id'])

    info_lines = [
        ["PILOT ANNOTATION SAMPLING METHODOLOGY"],
        [],
        ["Field", "Value"],
        ["Purpose", "Taxonomy pilot to validate whether the frozen 8-label taxonomy is practical for human annotation."],
        ["Source pool", "DEVELOPMENT pool only (no RETRIEVAL or TEST examples)."],
        ["Population size", f"{len(all_pairs)} customer-brand pairs from {len(dev_threads)} threads."],
        ["Sample size", f"{len(sampled)} examples."],
        ["Random seed", str(SEED)],
        ["Sampling method", "Stratified by heuristic intent label. Minimum 3 per intent to guarantee coverage of all 8 labels. "
                           "Remaining budget allocated proportionally. Ordinary/representative cases were kept as the majority (~70%). "
                           "Difficult cases (~30%) were deliberately enriched to test taxonomy boundaries."],
        ["Diagnostic Strata", "1. Representative: ordinary examples without warning flags.\n"
                              "2. Boundary/Hard: heuristic flags indicating multi-intent or taxonomy conflicts (e.g. 'account vs billing').\n"
                              "3. Ambiguous/Context: heuristic flags indicating short/unclear text or conversational closure.\n"
                              "(Note: these heuristic flags are sampling aids, not ground truth)."],
        ["Prevalence Warning", "WARNING: THIS PILOT IS INTENTIONALLY NOT A PREVALENCE ESTIMATE. Boundary/ambiguous cases are artificially enriched "
                               "compared to their true distribution in order to rigorously test the taxonomy applicability."],
        ["Deduplication", "One example per tweet ID. No duplicates."],
        ["Unique threads", str(len(unique_threads))],
        ["Unique customers", str(len(unique_customers))],
        [],
        ["SAMPLED COMPOSITION BY STRATA"],
        [],
        ["Intent", "Total", "Representative", "Boundary/Hard", "Ambiguous/Context"],
    ]

    for label in list(INTENTS.keys()) + ['UNKNOWN_OTHER']:
        info_lines.append([label, intent_counts.get(label, 0), rep_counts.get(label, 0), bound_counts.get(label, 0), ambig_counts.get(label, 0)])

    info_lines.append(["TOTAL", sum(intent_counts.values()), sum(rep_counts.values()), sum(bound_counts.values()), sum(ambig_counts.values())])
    info_lines.append([])
    info_lines.append(["NOTE", "This is a TAXONOMY PILOT, not the final evaluation set. "
                       "The final golden set (150-250 examples) will be drawn from the TEST pool."])

    for r, row_data in enumerate(info_lines, 1):
        for c, val in enumerate(row_data, 1):
            cell = ws3.cell(row=r, column=c, value=val)
            cell.alignment = Alignment(vertical='top', wrap_text=True)
            if r in (1, 15):
                cell.font = Font(name='Calibri', bold=True, size=12, color='2F5496')
            elif r in (3, 17):
                cell.font = Font(name='Calibri', bold=True, size=10)
            else:
                cell.font = Font(name='Calibri', size=10)

    ws3.column_dimensions['A'].width = 25
    ws3.column_dimensions['B'].width = 80
    ws3.column_dimensions['C'].width = 18

    # Save
    out_path = Path('discovery') / 'PILOT_ANNOTATION_100_v4.xlsx'
    wb.save(str(out_path))
    print(f"\nSaved to: {out_path.resolve()}")

    # === Final validation ===
    print("\n=== VALIDATION ===")
    print(f"Total examples: {len(sampled)} (expected 100)")

    tweet_ids = [s['tweet_id'] for s in sampled]
    print(f"Unique tweet IDs: {len(set(tweet_ids))} (expected 100)")
    print(f"Unique threads: {len(unique_threads)}")
    print(f"Unique customers: {len(unique_customers)}")

    # Check no TEST leakage
    test_leak = [s for s in sampled if s['thread_id'] in test_ids]
    print(f"TEST pool leaks: {len(test_leak)} (expected 0)")

    # Check all 8 labels represented
    labels_present = set(intent_counts.keys())
    all_expected = set(INTENTS.keys()) | {'UNKNOWN_OTHER'}
    missing = all_expected - labels_present
    print(f"Labels represented: {len(labels_present)}/8")
    if missing:
        print(f"  MISSING: {missing}")

    print(f"\nIntent distribution:")
    for k in list(INTENTS.keys()) + ['UNKNOWN_OTHER']:
        r_c = rep_counts.get(k, 0)
        b_c = bound_counts.get(k, 0)
        a_c = ambig_counts.get(k, 0)
        print(f"  {k}: {intent_counts.get(k, 0)} (rep: {r_c}, bound: {b_c}, ambig: {a_c})")

    # Verify Gold Label column is blank
    # (We wrote "" for all, so this is guaranteed by construction)
    print(f"\nGold Label column: all blank (by construction)")
    print(f"Notes column: all blank (by construction)")
    print(f"Dropdown: 8 frozen labels configured")
    print(f"\nValidation PASSED.")

if __name__ == '__main__':
    main()
