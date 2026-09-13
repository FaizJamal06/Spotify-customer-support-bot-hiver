# Discovery 300 — Guide-Consistency Audit

**Status: FORMAL AUDIT ONLY.** No model was trained, no example was relabeled, and no
recommendation on training-data suitability is made in this document. This report
produces evidence for a human decision-maker to review. The `existing_human_label`
column (and `discovery/HUMAN_REVIEW_labeled.md` itself) remains the only
authoritative label for each example; `guide_assessment` is an audit opinion
against the current frozen guide, nothing more.

Source files (read-only, unmodified — hashes verified before and after this audit):
`discovery/HUMAN_REVIEW_labeled.md`, `discovery/TAXONOMY_REVIEW_GUIDE.md`.
Machine-readable artifact: `discovery/DISCOVERY_300_AUDIT.csv`.

---

## 1. Parsing result

**300 of 300 rows were successfully located and parsed to 8 table columns each** (rows in the source markdown table are not always single physical lines — some `Customer Message` cells contain embedded blank lines that split a logical row across multiple physical lines; a block-based, backtick-aware parser was used instead of naive line-splitting to handle both this and literal `|` characters inside the backtick-quoted `Prior Context` cells).

Applying the Step 1 rule (existing_human_label = the last of the `UNKNOWN Subtype Flags` / `Human Decision / Gold Label` columns whose value exactly matches one of the 8 frozen labels):

- **296 of 300 rows** resolved to exactly one frozen label (256 from the normal `Human Decision / Gold Label` column position, 40 from the `UNKNOWN Subtype Flags` column position due to the column-shift issue described in the task — i.e. an empty `Potential Issue/Boundary` cell caused the label to land one column to the left).
- **4 of 300 rows are UNPARSEABLE** — neither of the two candidate columns contained a value matching one of the 8 frozen labels:

| Example | Tweet ID | Issue |
|---|---|---|
| Ex 70 | 2456257 | Both candidate columns contain non-label text (`irrelevant/off-topic` appears in both the Provisional Group and UNKNOWN Subtype Flags columns; no cell in either candidate column matches a frozen label). |
| Ex 78 | 141145 | `UNKNOWN Subtype Flags` contains `ambiguous/insufficient_context` (not one of the 4 standard diagnostic flags, and not a top-level label); `Human Decision / Gold Label` is empty. |
| Ex 164 | 2836 | Same pattern as Ex 78 — `ambiguous/insufficient_context` in the flags column, empty decision column. (This example is also directly cited by the guide as `Ex 164` under the `ambiguous` diagnostic flag — see §4 — but the row itself carries no parseable existing label to compare against.) |
| Ex 265 | 590142 | Both candidate columns are empty; no existing label recorded anywhere in the row. |

No row was silently dropped or given an invented label. All 4 unparseable rows are marked `UNRESOLVABLE` with `basis_tier = NONE` in the CSV artifact, per the task's explicit instruction not to guess.

**300/300 parsed — no STOP condition triggered** (row count is exactly 300; no existing label falls outside the 8 frozen values; nothing required modifying any frozen file).

---

## 2. Overall counts

| Status | Count | % of 300 |
|---|---:|---:|
| MATCH | 276 | 92.0% |
| POSSIBLE | 14 | 4.7% |
| MISMATCH | 6 | 2.0% |
| UNRESOLVABLE | 4 | 1.3% |
| **Total** | **300** | **100%** |

- **Strict mismatch rate** = MISMATCH / 300 = 6 / 300 = **2.0%**
- **Conservative mismatch rate** = (MISMATCH + POSSIBLE) / 300 = 20 / 300 = **6.7%**

Of the 300, 75 were directly cited by number in the frozen guide (`Ex N`) — the
highest-confidence evidence tier. All 75 were checked; 74 were parseable and every
one of those 74 MATCHed the guide's own stated label for that example (0
mismatches in this tier); the 75th (Ex 164) is one of the 4 unparseable rows.
The remaining 225 examples were assessed against the guide's general rules
(decision tree, per-intent definitions, boundary rules, 4 original edge cases,
7 post-golden clarifications).

---

## 3. existing_human_label distribution (296 parseable rows)

| Intent | Count | % of 296 |
|---|---:|---:|
| APP_TECH_ISSUE | 69 | 23.3% |
| UNKNOWN_OTHER | 64 | 21.6% |
| FEATURE_FEEDBACK | 49 | 16.6% |
| SUBSCRIPTION_BILLING | 33 | 11.1% |
| CONTENT_CATALOG | 27 | 9.1% |
| GENERAL_HOW_TO_INFO | 26 | 8.8% |
| ACCOUNT_ACCESS | 24 | 8.1% |
| ARTIST_SUPPORT | 4 | 1.4% |

## 4. guide_assessment distribution (where determinable, 296 rows)

| Intent | Count |
|---|---:|
| APP_TECH_ISSUE | 69 |
| UNKNOWN_OTHER | 62 |
| FEATURE_FEEDBACK | 55 |
| GENERAL_HOW_TO_INFO | 31 |
| SUBSCRIPTION_BILLING | 30 |
| ACCOUNT_ACCESS | 24 |
| CONTENT_CATALOG | 22 |
| ARTIST_SUPPORT | 4 |

The net movement is small and concentrated in a few classes: FEATURE_FEEDBACK
gains 6 (49→55), GENERAL_HOW_TO_INFO gains 5 (26→31), SUBSCRIPTION_BILLING loses
3 (33→30), CONTENT_CATALOG loses 5 (27→22), UNKNOWN_OTHER loses 2 (64→62). No
class moves by more than 6 examples out of 296.

## 5. Per-intent breakdown of POSSIBLE/MISMATCH (by existing_human_label)

| existing_human_label | POSSIBLE | MISMATCH | Total flagged | % of that class |
|---|---:|---:|---:|---:|
| SUBSCRIPTION_BILLING | 4 | 1 | 5 / 33 | 15.2% |
| CONTENT_CATALOG | 3 | 2 | 5 / 27 | 18.5% |
| APP_TECH_ISSUE | 3 | 2 | 5 / 69 | 7.2% |
| UNKNOWN_OTHER | 3 | 1 | 4 / 64 | 6.3% |
| FEATURE_FEEDBACK | 1 | 0 | 1 / 49 | 2.0% |
| ACCOUNT_ACCESS | 0 | 0 | 0 / 24 | 0% |
| GENERAL_HOW_TO_INFO | 0 | 0 | 0 / 26 | 0% |
| ARTIST_SUPPORT | 0 | 0 | 0 / 4 | 0% |

CONTENT_CATALOG and SUBSCRIPTION_BILLING are the two classes most affected in
relative terms (18.5% and 15.2% of their own examples flagged, respectively).
ACCOUNT_ACCESS, GENERAL_HOW_TO_INFO, and ARTIST_SUPPORT have zero flagged
examples each — every one of their 54 combined existing labels matched the
current guide's general application with no cited ambiguity.

---

## 6. Findings against the 7 post-golden clarification rules

Each of the 7 rule-clusters tagged `(post-golden clarification)` in
`discovery/TAXONOMY_REVIEW_GUIDE.md`, and which of the 300 discovery examples it touches:

1. **ACCESS-vs-BILLING cancellation/access-blocker distinction** (§1 boundary rule) — **0 discovery examples directly match this pattern.** No example in the 300 combines an explicit cancellation/billing-action request with an access problem stated as the blocker, the way golden-set `CAND_0059`/`CAND_0060` did.
2. **Edge Case 1 blocker-vs-demand tie-break** — **0 discovery examples directly match.** Several examples combine hacking/account-compromise with a billing element (Ex 14, Ex 139, Ex 153 — all MATCH, all correctly SUBSCRIPTION_BILLING per the original Edge Case 1 rule), but none present the specific "stated blocker vs. informally-styled demand" tension this clarification addresses.
3. **ACCESS-vs-HOWTO incidental-access-mention rule** (§1 "Do NOT use when") — **0 discovery examples directly match.** The general ACCESS-vs-HOWTO boundary area is present (Ex 44, Ex 121, Ex 169 — all MATCH, all correctly GENERAL_HOW_TO_INFO), but none of them mention an access symptom as background the way golden `CAND_0062` did.
4. **CONTENT_CATALOG curated-playlist-placement rule** — **0 discovery examples directly match.** No example in the 300 requests placing an already-available song onto a specific existing/editorial playlist.
5. **APP_TECH_ISSUE update-timing-≠-design-change rule** — **1 discovery example touches this rule, and it is consistent with it**: Ex 54 (tweet 2435831) — *"it's the 6S with iOS 11.0.3. It just started happening with the most recent app update"* — remained correctly APP_TECH_ISSUE (MATCH), exactly as this rule prescribes (update timing alone did not get read as a design-change signal here).
6. **Edge Case 4 sarcasm rule** — **1 discovery example was considered but not flagged**: Ex 94 (tweet 1770729) — *"A+ Service, Spotify, for responding to my original tweet... Still no response from [X]"* — has a sarcastic tone similar in spirit to the golden-set Hurricane Maria example, but no specific alternate substantive label could be identified with confidence (it's unclear what the "still no response" complaint is actually about), so it was left MATCH rather than forced into POSSIBLE without a citable specific rule, per the hard constraint.
7. **UNKNOWN_OTHER short-but-concrete-question rule** — **2 discovery examples directly match and are flagged POSSIBLE**: Ex 2 (*"when are the presale emails being sent out for billie eilish"*) and Ex 111 (*"send Majid Jordan presale code pls"*) — both name a concrete, answerable topic rather than being pure chatter, the same pattern this post-golden example addresses.

**Summary**: of the 7 post-golden rules, 2 are directly touched by discovery examples (rules 5 and 7), and rule 5 is a confirming MATCH while rule 7 accounts for 2 of the 14 POSSIBLE flags. The other 5 rules have no directly-matching example in this 300-example set — they were written to address patterns observed specifically in the golden 200, which is a different (TEST-pool) sample, so this is not unexpected.

---

## 7. Full table of POSSIBLE and MISMATCH cases

### MISMATCH (6)

| Example | Tweet ID | Target message | Existing label | Guide assessment | Basis |
|---|---|---|---|---|---|
| Ex 35 | 2439911 | *"also what happened to previewing songs as you drag your finger across your phone?"* | APP_TECH_ISSUE | FEATURE_FEEDBACK | Near-identical to guide's own quoted "What happened to preview?" example (Removed/Changed vs Malfunction rule) |
| Ex 37 | 249056 | *"did you remove the functionality to put one song on repeat?"* | APP_TECH_ISSUE | FEATURE_FEEDBACK | Near-verbatim match to guide's own quoted "Did you remove one-song-repeat?" example |
| Ex 175 | 2912388 | *"fix ya servers"* | UNKNOWN_OTHER | APP_TECH_ISSUE | Structurally identical to Edge Case 2's own "fix your app please" → APP_TECH_ISSUE default example |
| Ex 237 | 1694974 | *"can't activate hulu because I can not load up the web page"* | SUBSCRIPTION_BILLING | APP_TECH_ISSUE | Matches guide's own "the signup page crashes every time I try to continue" → APP_TECH_ISSUE worked example |
| Ex 246 | 1850755 | *"this whole album won't play even when I put it in a playlist"* | CONTENT_CATALOG | APP_TECH_ISSUE | Direct match to guide's own "song exists but won't play" → APP_TECH_ISSUE near-miss example |
| Ex 278 | 1173243 | *"why would there be a song in full Spanish in my Discover Weekly playlist?!"* | CONTENT_CATALOG | FEATURE_FEEDBACK | Matches the recommendation/personalization boundary rule ("complaints about algorithmic recommendations... are FEATURE_FEEDBACK") |

### POSSIBLE (14)

| Example | Tweet ID | Target message | Existing label | Guide assessment | Basis (brief) |
|---|---|---|---|---|---|
| Ex 1 | 2565911 | *"sneakily trying to get customers off...have to cancel account first"* | SUBSCRIPTION_BILLING | FEATURE_FEEDBACK | Pricing-policy-complaint rule; no disputed charge stated |
| Ex 2 | 2912378 | *"when are the presale emails being sent out for billie eilish"* | UNKNOWN_OTHER | GENERAL_HOW_TO_INFO | Post-golden "short but concrete topic" clarification |
| Ex 30 | 2009942 | *"removal of songs and cap on downloads is annoying"* | CONTENT_CATALOG | FEATURE_FEEDBACK | Matches Ex 47's download-cap pattern; genuine multi-intent tension |
| Ex 40 | 653091 | *"Why can't I join the Premium-family-group... form says something went wrong"* | APP_TECH_ISSUE | SUBSCRIPTION_BILLING | Section 3 technical-flow-error rule (subscription/entitlement task) |
| Ex 55 | 272733 | *"sound quality... awful. Sounds very distorted"* | CONTENT_CATALOG | APP_TECH_ISSUE | CONTENT vs TECH boundary; no guide example for distorted-audio reports |
| Ex 68 | 2407013 | *"card from a non-spotify country. How can it be done?"* | SUBSCRIPTION_BILLING | GENERAL_HOW_TO_INFO | No disputed charge; "how can it be done" framing |
| Ex 111 | 1830133 | *"send Majid Jordan presale code pls"* | UNKNOWN_OTHER | GENERAL_HOW_TO_INFO | Post-golden presale-code clarification (same pattern as golden CAND_0161) |
| Ex 122 | 1665434 | *"get a receipt every 3 months... charged every month"* | SUBSCRIPTION_BILLING | GENERAL_HOW_TO_INFO | No disputed amount; billing-frequency process question |
| Ex 135 | 2828705 | *"why don't you have Top 50 India in your trending charts"* | CONTENT_CATALOG | FEATURE_FEEDBACK | Whole chart-feature not launched regionally, not a missing song |
| Ex 148 | 2633304 | *"premium family invite process... 'Please match requested format'"* | APP_TECH_ISSUE | SUBSCRIPTION_BILLING | Same pattern as Ex 40 |
| Ex 191 | 206559 | *"is there a way to stop particular ads"* | FEATURE_FEEDBACK | GENERAL_HOW_TO_INFO | Mirrors the deliberately-unresolved golden CAND_0177/CAND_0186 tension |
| Ex 215 | 2198057 | *"dont waste money advertising to me... give me dank tunez"* | SUBSCRIPTION_BILLING | FEATURE_FEEDBACK | No disputed charge stated at all |
| Ex 222 | 2507517 | *"spent an hour searching... nothing seems to be working. Thank you though"* | APP_TECH_ISSUE | UNKNOWN_OTHER | Edge Case 4 closure signal ("Thank you though") |
| Ex 242 | 925101 | *"Still doesn't work"* | UNKNOWN_OTHER | APP_TECH_ISSUE | Mirrors the deliberately-unresolved golden CAND_0064 short-continuation case |

(Full `rule_reference` text and `notes` for every row above are in `discovery/DISCOVERY_300_AUDIT.csv`.)

---

## 8. Unparseable / UNRESOLVABLE rows

See §1 table above for the specific parsing issue per row (Ex 70, Ex 78, Ex 164, Ex 265). All four have `guide_assessment` left blank and `basis_tier = NONE` in the CSV — no label was invented for them.

---

## 9. Risk-assessment observations (factual only — not a recommendation)

These are observations about what the numbers show. **No conclusion about whether
to use the 300 for baseline training is stated or implied** — that decision is
reserved for the human reviewer, per the task's explicit instruction.

- **The strict mismatch rate (2.0%) is small in absolute terms**, and every one of
  the 6 MISMATCH cases is backed by a guide worked example that is a near-verbatim
  or structurally-identical match — not an inference. Two of the six (Ex 35, Ex 37)
  are both instances of the exact same "what happened to/did you remove [existing
  feature]?" pattern, meaning the 6 mismatches reflect roughly 5 distinct rule
  applications, not 6 independent judgment calls.
- **The conservative rate (6.7%) is driven mostly by boundary areas the guide
  itself acknowledges are hard**: technical-flow-errors in subscription contexts
  (Ex 40, Ex 148 — 2 of 14), no-disputed-charge billing-adjacent questions (Ex 1,
  Ex 68, Ex 122, Ex 215 — 4 of 14), and two patterns explicitly already known to be
  internally inconsistent in the golden 200 itself (Ex 191 mirrors CAND_0177/
  CAND_0186; Ex 242 mirrors CAND_0064) — meaning roughly half of the POSSIBLE
  flags reflect *already-known* open questions rather than new ones this audit
  discovered.
- **Class concentration**: CONTENT_CATALOG and SUBSCRIPTION_BILLING are the two
  classes with the highest *relative* flag rate (18.5% and 15.2% of their own
  examples respectively), both driven by the SUBSCRIPTION_BILLING-vs-
  GENERAL_HOW_TO_INFO "no disputed charge" boundary and the CONTENT_CATALOG-vs-
  APP_TECH_ISSUE "won't play" boundary. ARTIST_SUPPORT (n=4), ACCOUNT_ACCESS
  (n=24), and GENERAL_HOW_TO_INFO (n=26) have zero flagged examples each — the
  smallest class (ARTIST_SUPPORT) is not disproportionately affected, which is
  relevant if training-data quality for the rare class is a specific concern.
- **Severity is uneven within the flagged set**: the 6 MISMATCH cases each rest on
  a single, specific, quotable guide passage (GUIDE_WORKED_EXAMPLE or
  GUIDE_EX_CITATION-adjacent tier); the 14 POSSIBLE cases are, by construction,
  cases where a reasonable guide-literate reviewer could still land on either
  label — they are evidence of genuine boundary difficulty, not evidence that the
  existing label is wrong.
- **No systemic pattern by original annotation source**: the 75 guide-cited
  examples (the ones the taxonomy authors presumably drew from most carefully)
  had a 0% mismatch rate among the 74 that could be parsed, which is consistent
  with — but does not prove — general labeling care across the full 300, since
  those 75 were plausibly the examples most likely to already agree with the
  guide almost by construction.

---

## 10. Confirmations

- `discovery/HUMAN_REVIEW_labeled.md` was read only; no label in it was changed.
- `discovery/TAXONOMY_REVIEW_GUIDE.md` was read only; hash-verified unchanged (`d3fa5491a1d422df0d4afeff5aa8a93f`) before and after this audit.
- `golden_set/GOLDEN_200_FINAL.csv` and `golden_set/CANDIDATE_MANIFEST_200.csv` were not touched (verified by hash) — this audit did not reference or use golden-set labels as ground truth anywhere; the only two places golden-set examples are mentioned (Ex 191, Ex 242) are noted as *analogous, already-known-ambiguous patterns*, not as a substitute reference for what the discovery label "should" be.
- The 8-intent taxonomy was not modified, redesigned, or reinterpreted.
- No model was trained. No baseline, classifier, retrieval, or judge work was started.
- Nothing in this pass was committed to git.
