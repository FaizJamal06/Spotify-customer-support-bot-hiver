# Golden 200 — Final Analysis

Source of truth: `golden_set/GOLDEN_ANNOTATION_200_labeled.xlsx` (`GOLDEN_200` sheet).
Clean export: `golden_set/GOLDEN_200_FINAL.csv`.

**Note on the gold-label column.** In the labeled workbook, the original blind
`Human Gold Label` / `Human Notes` columns (G/H) were left blank; the annotator
instead completed the `Human Final Label` / `Human Review Notes` columns (L/M,
added for the AI-prelabel workflow) for all 200 rows. Per explicit user
confirmation, **`Human Final Label` is treated as the authoritative final gold
label** for this analysis and export, and `Human Review Notes` as the
corresponding human notes field. No label value was altered, normalized, or
reinterpreted — only the column read as "gold" was clarified.

---

## 1. Validation result

All 10 checks pass:

| # | Check | Result |
|---|---|---|
| 1 | Exactly 200 candidates | ✅ 200 rows |
| 2 | Every candidate has exactly one valid gold label | ✅ 200/200 non-blank |
| 3 | No invalid labels | ✅ all 200 values are in the frozen 8-label set |
| 4 | No duplicate Candidate IDs | ✅ 200 unique IDs |
| 5 | Candidate ID / Tweet ID / Thread ID / Customer ID / Target Message match the finalized manifest | ✅ 0 mismatches vs `CANDIDATE_MANIFEST_200.csv` |
| 6 | No AI label written into / substituted for the gold column | ✅ gold cells are literal values (no formulas referencing the AI column); AI Suggested Label and gold agree on 183/200 rows because the AI was right most of the time, not because of a copy — see §3 |
| 7 | Gold label is the only authoritative evaluation label | ✅ documented above; `AI Suggested Label` is explicitly advisory only (see `SAMPLING_INFO` / `AI_PRELABEL_SUMMARY` sheets) |
| 8 | Human Notes preserved exactly | ✅ all 20 non-blank `Human Review Notes` values copied verbatim into `GOLDEN_200_FINAL.csv` |
| 9 | Workbook opens successfully | ✅ loads cleanly via openpyxl, all 5 sheets present (`GOLDEN_200`, `THREAD_VIEW`, `GUIDE`, `SAMPLING_INFO`, `AI_PRELABEL_SUMMARY`) |
| 10 | Taxonomy remains the frozen 8-label taxonomy | ✅ all 200 gold values fall in `{ACCOUNT_ACCESS, SUBSCRIPTION_BILLING, APP_TECH_ISSUE, CONTENT_CATALOG, FEATURE_FEEDBACK, ARTIST_SUPPORT, GENERAL_HOW_TO_INFO, UNKNOWN_OTHER}`; `discovery/TAXONOMY_REVIEW_GUIDE.md` hash unchanged (`2e5666478a7c01f10dc9dc39f4df0654`), `GUIDE` sheet intact (60 rows) |

No human gold label, target message, Candidate/Tweet/Thread/Customer ID, or taxonomy content was modified at any point in this pass.

---

## 2. Final human gold label distribution (n=200)

| Intent | Count | % |
|---|---:|---:|
| APP_TECH_ISSUE | 40 | 20.0% |
| FEATURE_FEEDBACK | 40 | 20.0% |
| GENERAL_HOW_TO_INFO | 28 | 14.0% |
| UNKNOWN_OTHER | 23 | 11.5% |
| SUBSCRIPTION_BILLING | 21 | 10.5% |
| ACCOUNT_ACCESS | 19 | 9.5% |
| CONTENT_CATALOG | 15 | 7.5% |
| ARTIST_SUPPORT | 14 | 7.0% |

As documented in `SAMPLING_INFO`, this is a deliberately balanced evaluation sample (representative base + targeted boundary/rare-case coverage), **not** a prevalence estimate of real SpotifyCares traffic.

---

## 3. AI prelabel agreement with human gold

**Framing note (per instructions): this is "AI prelabel agreement with human gold," not "AI accuracy."** The human gold labels in `Human Final Label` are the sole evaluation reference; the AI prelabel is a suggestion that was reviewed and could be, and in 17 cases was, overridden. Agreement is a description of how well the prelabels matched the adjudicated ground truth, not a claim about a validated classifier.

**Overall exact agreement: 183 / 200 = 91.5%**

- Rows human accepted (AI label == gold label): **183**
- Rows human changed (AI label != gold label): **17**
- Rows with Human Review Notes: **20** (11 on rows where the human agreed with the AI anyway, 9 on rows where the human changed the label)

### Agreement by AI confidence

| AI Confidence | Agreement | n |
|---|---|---:|
| HIGH | 81/84 = 96.4% | 84 |
| MEDIUM | 89/103 = 86.4% | 103 |
| LOW | 13/13 = 100.0% | 13 |

The confidence tiers behave sensibly at the top (HIGH is the most reliable) but the **LOW tier is not the least reliable** — all 13 LOW-confidence rows (the deliberately hardest/most ambiguous cases, including the 5 previously-flagged hard boundary cases) were confirmed by the human exactly as suggested. This is a meaningful result: it suggests the AI's *self-assessed* uncertainty on those 13 cases was well-calibrated as "hard but resolvable," and that the human, working independently, converged on the same resolution — not that LOW-confidence suggestions are trustworthy in general (n=13 is small, and every one of those rows was written with explicit reasoning about a named competing intent, which may have primed a careful reviewer toward the same reading the AI reached). The 17 actual disagreements are concentrated entirely in MEDIUM confidence (14 of 17) and HIGH confidence (3 of 17); see §4.

### Confusion matrix (AI Suggested Label → Human Gold Label)

| AI \ Human | ACCESS | BILLING | TECH | CONTENT | FEATURE | ARTIST | HOWTO | UNKNOWN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **ACCOUNT_ACCESS** | 18 | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| **SUBSCRIPTION_BILLING** | 1 | 19 | 0 | 0 | 0 | 0 | 1 | 0 |
| **APP_TECH_ISSUE** | 0 | 0 | 39 | 0 | 2 | 0 | 1 | 0 |
| **CONTENT_CATALOG** | 0 | 0 | 1 | 12 | 0 | 1 | 0 | 0 |
| **FEATURE_FEEDBACK** | 0 | 0 | 0 | 2 | 38 | 0 | 1 | 0 |
| **ARTIST_SUPPORT** | 0 | 0 | 0 | 0 | 0 | 13 | 0 | 0 |
| **GENERAL_HOW_TO_INFO** | 0 | 0 | 0 | 0 | 0 | 0 | 21 | 0 |
| **UNKNOWN_OTHER** | 0 | 1 | 0 | 1 | 0 | 0 | 3 | 23 |

(Rows = AI suggestion, columns = human gold; diagonal = agreement.)

### Per-intent agreement (of human-gold rows in each intent, % where AI matched — recall-style)

| Human Gold Intent | Agreement | n |
|---|---|---:|
| UNKNOWN_OTHER | 23/23 = 100.0% | 23 |
| APP_TECH_ISSUE | 39/40 = 97.5% | 40 |
| FEATURE_FEEDBACK | 38/40 = 95.0% | 40 |
| ACCOUNT_ACCESS | 18/19 = 94.7% | 19 |
| ARTIST_SUPPORT | 13/14 = 92.9% | 14 |
| SUBSCRIPTION_BILLING | 19/21 = 90.5% | 21 |
| CONTENT_CATALOG | 12/15 = 80.0% | 15 |
| GENERAL_HOW_TO_INFO | 21/28 = 75.0% | 28 |

GENERAL_HOW_TO_INFO and CONTENT_CATALOG are the two weakest cells — both are "landing zones" that other intents (ACCOUNT_ACCESS, SUBSCRIPTION_BILLING, UNKNOWN_OTHER, FEATURE_FEEDBACK, APP_TECH_ISSUE) resolve into when a message turns out to be more informational or more about existing-catalog placement than the AI's first read suggested. See §4/§5.

### Per-AI-label precision (of AI-suggested rows in each intent, % where human agreed)

| AI Suggested Label | Precision | n |
|---|---|---:|
| ARTIST_SUPPORT | 13/13 = 100.0% | 13 |
| GENERAL_HOW_TO_INFO | 21/21 = 100.0% | 21 |
| APP_TECH_ISSUE | 39/42 = 92.9% | 42 |
| FEATURE_FEEDBACK | 38/41 = 92.7% | 41 |
| SUBSCRIPTION_BILLING | 19/21 = 90.5% | 21 |
| ACCOUNT_ACCESS | 18/20 = 90.0% | 20 |
| CONTENT_CATALOG | 12/14 = 85.7% | 14 |
| UNKNOWN_OTHER | 23/28 = 82.1% | 28 |

Every AI-suggested GENERAL_HOW_TO_INFO and ARTIST_SUPPORT was confirmed by the human. UNKNOWN_OTHER is the least precise AI suggestion (5 of 28 AI-flagged-as-UNKNOWN rows were reclassified by the human into a substantive intent) — consistent with the guide's own repeated warning that UNKNOWN is over-used by keyword/length heuristics and should be a last resort.

### Biggest disagreement pairs (AI → Human)

| AI → Human | Count |
|---|---:|
| UNKNOWN_OTHER → GENERAL_HOW_TO_INFO | 3 |
| APP_TECH_ISSUE → FEATURE_FEEDBACK | 2 |
| FEATURE_FEEDBACK → CONTENT_CATALOG | 2 |
| (10 other pairs) | 1 each |

### Representative disagreement examples

**Pattern: UNKNOWN_OTHER → GENERAL_HOW_TO_INFO (AI under-classified a terse/off-topic-looking message)**
- `CAND_0127` — *"@115888 You work with Alexa, right??"* — AI read this as idle chit-chat (no stated problem); human read it as a genuine compatibility question.
- `CAND_0133` — *"It's working now, nvm. I tried a different browser and it was the same issue."* — AI read this as pure self-resolved closure (matching the guide's own closure examples almost verbatim); human labeled it GENERAL_HOW_TO_INFO with no notes explaining the departure.

**Pattern: APP_TECH_ISSUE → FEATURE_FEEDBACK (malfunction that coincides with an app update)**
- `CAND_0106` — *"So this didn't happen before I updated my phone yesterday. Is there any way around this?"* — human notes: *"issue faced after update, so this is not primarily reporting an unexpected technical malfunction anymore... objecting to the design/behavior."*
- `CAND_0098` — *"can't play anything that isn't downloaded... iPhone 7 with the latest app update"* (AI HIGH confidence) — human gave no notes, but the pattern (new problem coincides with an update) matches CAND_0106 exactly.

**Pattern: FEATURE_FEEDBACK → CONTENT_CATALOG (existing content, placement/curation request)**
- `CAND_0136` — wants an already-catalogued song added to Spotify's editorial "Today's Top Hits" playlist — human notes: *"more of a recommendation... personal request to add a song into a playlist."*
- `CAND_0147` — *"wish there was a function to block an artist... avoid them popping up in your generated playlists and radios"* (AI HIGH confidence, and near-identical to a positive FEATURE_FEEDBACK example given in the frozen guide itself) — human labeled CONTENT_CATALOG with no notes. This one is flagged separately in §4 as a likely straightforward disagreement rather than a guide gap, since the guide already gives an on-point example.

---

## 4. Human disagreement pattern analysis

All 17 disagreement rows, grouped by the boundary categories requested, with a judgment on cause. "Guide issue" = the frozen guide's wording doesn't clearly resolve this case type; "Annotation disagreement" = the guide's rule is reasonably clear but the human (or the AI) read the evidence differently; "Genuinely ambiguous" = a reasonable reader could go either way even with a perfectly-worded guide.

### ACCOUNT_ACCESS vs SUBSCRIPTION_BILLING — 2 cases
- `CAND_0024` (AI: SUBSCRIPTION_BILLING → Human: ACCOUNT_ACCESS). *"someone's hacked my account and apparently there's no way for me to change my password! #crock #fixthis #givememumoneyback"*. Human notes: *"helping them recover their account works better in this situation security > billing."* The message carries two explicit signals pointing in different directions — a stated blocker ("no way to change my password") and an explicit monetary demand (the hashtag). **Cause: guide issue.** Edge Case 1 says to classify by "primary requested action," but doesn't say how to weigh a stated blocker against an explicit-but-informally-styled demand when both are present. See `PROPOSED_GUIDE_CLARIFICATIONS.md` #3.
- `CAND_0059` (AI: ACCOUNT_ACCESS → Human: SUBSCRIPTION_BILLING). *"I need to cancel a prime account but I can't login at all... How can I cancel if I can't even log in?"*. Human notes: *"Primary request is to cancel the Premium/Prime subscription; inability to log in is the obstacle preventing cancellation."* **Cause: guide issue, with direct internal-inconsistency evidence** — `CAND_0060`, an almost word-for-word twin in this same golden set (*"need to cancel my account. Problem is no idea what email was used... How can I cancel"*), was labeled **ACCOUNT_ACCESS** by the same human. The "cancel-blocked-by-login" pattern was resolved two different ways in the same 200-example set. See `PROPOSED_GUIDE_CLARIFICATIONS.md` #1.

### BILLING vs HOW_TO — 1 case
- `CAND_0174` (AI: SUBSCRIPTION_BILLING, HIGH confidence → Human: GENERAL_HOW_TO_INFO). *"Please can someone help me upgrade to a multiple device account?"*. Human notes: *"asking how to change/upgrade their plan. No charge dispute, billing error, or claim that a payment/entitlement is wrong."* **Cause: AI-reasoning miss, not a guide gap.** The guide's SUBSCRIPTION_BILLING boundary rule already draws exactly this line (a plan-change *request* with no disputed charge is GENERAL_HOW_TO_INFO); the AI over-weighted the word "upgrade" as inherently billing-flavored. No clarification proposed.

### TECH vs FEATURE — 2 cases
- `CAND_0106` and `CAND_0098` (both AI: APP_TECH_ISSUE → Human: FEATURE_FEEDBACK; both center on a new problem that appeared "after an app update"). **Cause: guide issue.** The guide's Edge Case 2 / Removed-vs-Malfunction rule already says a malfunction defaults to APP_TECH_ISSUE *unless there is explicit design criticism*, and neither message explicitly criticizes a design choice — yet both were independently moved to FEATURE_FEEDBACK, apparently on the strength of "started right after an update" alone. This is a **recurring (2/2), well-evidenced** case for tightening the wording. See `PROPOSED_GUIDE_CLARIFICATIONS.md` #4.

### CONTENT vs TECH — 1 case
- `CAND_0017` (AI: CONTENT_CATALOG → Human: APP_TECH_ISSUE). Human notes: *"based on the previous messages the user has reported a button issue Initially, then asks about song and band name."* This turns on a specific earlier-context message (a "report a mistake" button) not obviously determinative from the target message alone. **Cause: genuinely ambiguous / single-case** — only one occurrence, and it depends on a subtle context-weighting judgment rather than a general wording gap. No guide clarification proposed for this alone (per instructions, not inventing a gap from one unusual example).

### CONTENT vs FEATURE — 2 cases
- `CAND_0136` (AI: FEATURE_FEEDBACK → Human: CONTENT_CATALOG). Wants an existing, already-catalogued song added to a specific editorial playlist. **Cause: guide issue.** The guide's CONTENT_CATALOG "wants specific content added" examples are all about content *missing from Spotify entirely*; there is no explicit coverage of "content that exists, but I want it placed on a specific curated/editorial playlist." See `PROPOSED_GUIDE_CLARIFICATIONS.md` #5.
- `CAND_0147` (AI: FEATURE_FEEDBACK, HIGH confidence → Human: CONTENT_CATALOG). *"wish there was a function to block an artist... avoid them popping up in your generated playlists and radios"*. **Cause: annotation disagreement, not a guide gap** — the frozen guide contains a near-identical worked example (*"Can I blacklist certain bands from shuffle and radios?"* → FEATURE_FEEDBACK). This looks like a straightforward inconsistency with an explicit guide example rather than evidence the guide needs clarifying. Flagged here for visibility, not proposed as a wording change.

### ARTIST vs CONTENT/TECH — 1 case
- `CAND_0129` (AI: CONTENT_CATALOG → Human: ARTIST_SUPPORT). A fan (not self-identified as the artist) asks for a corrected group photo on an artist's Spotify profile. **Cause: guide issue.** ARTIST_SUPPORT is defined around the customer acting *as or on behalf of* the artist; this message doesn't self-identify that way, yet was labeled ARTIST_SUPPORT — suggesting visual/asset-correction requests on an artist's own page may be intended to route to ARTIST_SUPPORT regardless of requester identity, which the guide doesn't currently say. See `PROPOSED_GUIDE_CLARIFICATIONS.md` #7.

### HOW_TO vs ACCOUNT — 1 case
- `CAND_0062` (AI: ACCOUNT_ACCESS → Human: GENERAL_HOW_TO_INFO). *"how can I know which address is set up in my account? ...some of the members can not sign in."* **Cause: guide issue.** The access problem ("can not sign in") is mentioned but secondary to the stated question (an address lookup); the guide doesn't say how to treat an incidentally-mentioned access issue that isn't the customer's actual ask. See `PROPOSED_GUIDE_CLARIFICATIONS.md` #2.

### UNKNOWN vs classifiable intent — 2 cases
- `CAND_0127` and `CAND_0133` (both AI: UNKNOWN_OTHER → Human: GENERAL_HOW_TO_INFO). **Cause: AI-reasoning miss, not a guide gap.** The guide is already explicit and repeated on this point ("short/terse ≠ UNKNOWN," "self-resolved closure is UNKNOWN only when no actionable ask remains"); these look like cases where the AI was too quick to default to UNKNOWN rather than a wording problem. No clarification proposed; this is exactly the failure mode the guide already warns about, and the human catching it is the review process working as intended.

### Recommendation / personalization / playlist / curation — 1 case (plus overlap with CONTENT vs FEATURE above)
- `CAND_0186` (AI: FEATURE_FEEDBACK → Human: GENERAL_HOW_TO_INFO). *"is there a way to exclude songs in some certain languages from getting into my Discover weekly playlist?"*. **Cause: guide issue.** The message simultaneously matches the FEATURE_FEEDBACK "personalization-control request" rule and the GENERAL_HOW_TO_INFO "is there a way to...?" signal phrase — the guide doesn't state which one governs when both are literally present. See `PROPOSED_GUIDE_CLARIFICATIONS.md` #6.

### Short diagnostic replies (device/OS/app-version strings) — 0 disagreements
All device-info continuation replies (e.g. `CAND_0088`–`CAND_0107`) that the AI resolved via preceding context were confirmed by the human. This pattern is not a source of disagreement in this set.

### Terse context-dependent replies — 1 case
- `CAND_0064` (AI: APP_TECH_ISSUE → Human: GENERAL_HOW_TO_INFO). *"Still does it after reinstall. @SpotifyCares any help on this?"*, continuing an iPhone-volume-malfunction thread. **Cause: genuinely ambiguous / possible annotation inconsistency** — no notes were left, and "still does it" reads as a continued malfunction report rather than a how-to question; this is flagged for visibility but not asserted as a guide problem, since the guide's short-continuation rule is already fairly explicit about using preceding context toward the established topic.

### Sarcasm / closure / actionable feedback — 1 clear case (plus a related metadata miss)
- `CAND_0130` (AI: UNKNOWN_OTHER → Human: SUBSCRIPTION_BILLING). *"Would like to thank @SpotifyCares for being nice enough to credit the month we weren't able to use the service due to #HurricaneMaria."* Human notes: *"Customer sarcastically refers to receiving a credit... implying a billing/subscription charge for unavailable service."* **Cause: guide issue.** The message is phrased exactly like the guide's own closure/gratitude examples, but the human read it as sarcasm concealing a billing complaint. The guide's Edge Case 4 has no sarcasm-detection guidance at all. See `PROPOSED_GUIDE_CLARIFICATIONS.md` #8.
- `CAND_0078` (AI: UNKNOWN_OTHER → Human: CONTENT_CATALOG) is related but distinct: a customer points out a typo in a track title ("Big White Gate"), which the AI read as idle observation but is literally a content-metadata error under the guide's own CONTENT_CATALOG definition (the human notes quote the guide's definition directly). **Cause: AI-reasoning miss, not a guide gap** — the guide already covers "wrong lyrics/tracklist/artwork" as CONTENT_CATALOG; a title typo is the same kind of error. No clarification proposed.

### Other — premium-linked third-party perks — 1 case
- `CAND_0161` (AI: UNKNOWN_OTHER → Human: GENERAL_HOW_TO_INFO). *"what do I gotta do to get the DVSN presale code? Outside of already paying a premium monthly service?"* Human notes state directly: *"the guide does not explicitly cover concert presale-code requests."* **Cause: guide issue, human-acknowledged.** See `PROPOSED_GUIDE_CLARIFICATIONS.md` #9.

---

## 5. Taxonomy / guide gaps and proposed clarifications

Nine clarifications are proposed, each backed by concrete disagreement evidence (never a single unusual example alone). Full detail — observed example, current guide wording, why it's insufficient, and the smallest proposed fix — is in **`golden_set/PROPOSED_GUIDE_CLARIFICATIONS.md`**. Summary:

1. Access-blocked billing/cancellation actions (`CAND_0059` vs `CAND_0060` — same pattern, opposite gold labels within this set).
2. How-to questions with an incidentally-mentioned access problem (`CAND_0062`).
3. Edge Case 1 tie-break between a stated blocker and an explicit-but-informal demand (`CAND_0024`).
4. "Started after an update" is not itself evidence of a deliberate design change (`CAND_0098`, `CAND_0106`).
5. Curated/editorial playlist placement requests for already-catalogued content (`CAND_0136`).
6. Recommendation/personalization control requests phrased as a "is there a way to" how-to question (`CAND_0186`).
7. Artist-page visual/asset correction requested by a non-self-identified fan (`CAND_0129`).
8. Sarcasm handling under the Edge Case 4 closure rule (`CAND_0130`).
9. Premium-linked third-party perks/presale codes (`CAND_0161`).

These are **proposals only**. `discovery/TAXONOMY_REVIEW_GUIDE.md` was not modified, and no human gold label was changed as a result of this analysis.

---

## 6. Confirmations

- **No human gold labels were modified.** `Human Final Label` (200/200) and `Human Review Notes` (20/20) were read and copied verbatim into `GOLDEN_200_FINAL.csv`; none were edited, normalized, or reinterpreted.
- **No candidate examples were modified.** Candidate IDs, Tweet IDs, Thread IDs, Customer IDs, and Target Messages all match `CANDIDATE_MANIFEST_200.csv` exactly (0 mismatches across all 200 rows). No example was added, removed, reordered, or resampled.
- **No taxonomy changes were applied.** `discovery/TAXONOMY_REVIEW_GUIDE.md` is unmodified (hash-verified: `2e5666478a7c01f10dc9dc39f4df0654`). All proposed clarifications live only in `golden_set/PROPOSED_GUIDE_CLARIFICATIONS.md`, clearly marked `PROPOSED ONLY`.
- No model was trained or tuned from these labels.
- Nothing in this pass was committed to git.
