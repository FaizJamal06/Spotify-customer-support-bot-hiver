# Proposed Guide Clarifications — PROPOSED ONLY

**Status: PROPOSED ONLY. Nothing in this document has been applied.
`discovery/TAXONOMY_REVIEW_GUIDE.md` has not been modified and remains frozen.**

These 9 clarifications are derived from concrete disagreements between the AI
prelabel and the final human gold label on the completed 200-example golden
set (see `golden_set/GOLDEN_200_ANALYSIS.md` §3–4 for the full agreement
analysis). Each one is backed by a recurring pattern or a direct
within-set inconsistency — none is proposed on the strength of a single
unusual example alone. Each proposes the smallest possible wording addition;
none of these change any existing rule, example, or boundary already in the
guide.

---

## 1. Access-blocked billing/cancellation requests

**Observed examples:** `CAND_0059` (tweet 2622906) — *"I need to cancel a prime account but I can't login at all because my Facebook associated with it is gone. How can I cancel if I can't even log in to the setting or account page?"* → human gold: **SUBSCRIPTION_BILLING**.
`CAND_0060` (tweet 540363) — *"need to cancel my account. Problem is no idea what email was used. Tried them all. How can I cancel."* → human gold: **ACCOUNT_ACCESS**.

**What the guide currently says:** The Multi-Intent Rule says to classify by "the issue that should drive the next support action" and gives a tie-breaker order (security/access before billing) to be used "ONLY when two issues are genuinely equally explicit." Section 2 (SUBSCRIPTION_BILLING) doesn't address cancellation requests blocked by an access problem; Section 1 (ACCOUNT_ACCESS) doesn't either.

**Why the current wording is insufficient:** These two examples are structurally identical — an explicit cancellation request, blocked by an explicit access/login failure — yet they received opposite gold labels in this same golden set. This is not one annotator's one-off judgment call; it's the same rule pattern resolved two different ways, which means the guide does not currently give annotators enough to converge on a consistent answer for "X action blocked by access."

**Proposed clarification (smallest possible):** Add one sentence to the Multi-Intent Rule or to Section 1's boundary-rule block: *"When the customer's stated primary requested action is a billing action (e.g., cancel, refund, downgrade) and an access/login problem is mentioned only as the obstacle preventing that action, classify by the requested action (SUBSCRIPTION_BILLING) unless restoring access is itself part of what the customer is asking for."*

**PROPOSED ONLY.**

---

## 2. How-to questions with an incidentally-mentioned access problem

**Observed example:** `CAND_0062` (tweet 540359) — *"how can I know which address is set up in my account? I have signed up in a family plan but some of the members can not sign in. Not sure if they are writing it incorrectly"* → AI: ACCOUNT_ACCESS, human gold: **GENERAL_HOW_TO_INFO**.

**What the guide currently says:** Section 1's "Do NOT use this when" list covers the case where the word "account" appears but the real problem is billing or a how-to question — but it does not cover the reverse: a how-to question that *also* mentions a real access symptom (family members failing to sign in) as a secondary, non-primary detail.

**Why the current wording is insufficient:** The stated question here ("how can I know which address is set up") is a pure how-to/info request; the access symptom is offered as color, not as the ask. Nothing in the guide currently tells an annotator how much weight an incidentally-mentioned access symptom should carry when it isn't the customer's actual question.

**Proposed clarification (smallest possible):** Add to Section 1's "Do NOT use this when" list: *"The customer's actual question is informational (how something works, what is set up, etc.) and an access symptom is mentioned only as background, not as the thing they're asking to be fixed."*

**PROPOSED ONLY.**

---

## 3. Edge Case 1 tie-break between a stated blocker and an explicit-but-informal demand

**Observed example:** `CAND_0024` (tweet 1659831) — *"someone's hacked my account and apparently there's no way for me to change my password! #crock #fixthis #givememumoneyback"* → AI: SUBSCRIPTION_BILLING, human gold: **ACCOUNT_ACCESS**.

**What the guide currently says:** Edge Case 1 instructs classifying by "the customer's primary requested action, not the root cause," with examples where the requested action is stated plainly in prose (e.g., "stop the charge").

**Why the current wording is insufficient:** This message has *two* explicit signals pointing in different directions: a stated blocker in ordinary prose ("no way for me to change my password") and an explicit monetary demand styled as a hashtag ("#givememumoneyback"). Edge Case 1's existing examples all have one clear textual "ask"; none address what to do when a stated blocker and a stated demand compete, or whether a hashtag-styled demand should be weighted the same as a prose demand.

**Proposed clarification (smallest possible):** Add to Edge Case 1: *"When the message states both a blocker (e.g., 'I can't reset my password') and a demand (e.g., a refund/compensation request, however informally styled, such as a hashtag), the stated blocker — the concrete thing preventing the customer from resolving their own situation — takes precedence, since resolving it is the more direct next support action."*

**PROPOSED ONLY.**

---

## 4. "Started after an update" is not itself evidence of a deliberate design change

**Observed examples:** `CAND_0106` (tweet 2757619) — *"So this didn't happen before I updated my phone yesterday. Is there any way around this? If my phone is on silent surely this shouldn't happen?"* → AI: APP_TECH_ISSUE, human gold: **FEATURE_FEEDBACK**, with human notes: *"issue faced after update, so this is not primarily reporting an unexpected technical malfunction anymore. The customer is objecting to the design/behavior."*
`CAND_0098` (tweet 2913925) — *"can't play anything that isn't downloaded... iPhone 7 with the latest app update"* → AI: APP_TECH_ISSUE (HIGH confidence), human gold: **FEATURE_FEEDBACK**.

**What the guide currently says:** The Removed/Changed vs Malfunction rule (Section 3, and Edge Case 2) says a malfunction defaults to APP_TECH_ISSUE *unless there is explicit design-criticism language*; an update coinciding with new broken behavior is exactly the kind of thing the guide's own positive examples describe as a malfunction (e.g., "the app self-launches on startup," "playback stops after one song").

**Why the current wording is insufficient:** Both examples were independently moved from APP_TECH_ISSUE to FEATURE_FEEDBACK apparently on the strength of "this started right after an update," even though neither message contains explicit design criticism — the guide's own stated trigger for FEATURE_FEEDBACK. This is a recurring pattern (2 of 2 "after an update" disagreements went the same direction), suggesting annotators are reading "coincided with an update" as itself a signal of intentional change, which the guide does not currently endorse or rule out.

**Proposed clarification (smallest possible):** Add one sentence to the Removed/Changed vs Malfunction rule: *"A new problem that started right after an app update is, by itself, still presumptively a malfunction/regression (APP_TECH_ISSUE), not evidence of an intentional design change — apply FEATURE_FEEDBACK only when the customer explicitly objects to the new behavior as a choice (e.g., asks for it to be reverted or made optional), not merely because the timing coincides with an update."*

**PROPOSED ONLY.**

---

## 5. Curated/editorial playlist placement requests for already-catalogued content

**Observed example:** `CAND_0136` (tweet 508845) — *"I think that N.E.R.D & Rihanna's 'Lemon' would be perfect on the 'Today's Top Hits' Playlist. Please can you add it on behalf of all the navy?"* → AI: FEATURE_FEEDBACK, human gold: **CONTENT_CATALOG**, with human notes: *"more of a recommendation rather than a feedback or issue and it's a personal request to add a song into a playlist."*

**What the guide currently says:** CONTENT_CATALOG's "wants specific content added to Spotify's catalog" examples (e.g., "When's lemonade going on Spotify?") are all about a song that is missing from Spotify entirely. FEATURE_FEEDBACK's boundary rule against CONTENT_CATALOG says "a new way to browse, sort, filter, or manage content" is FEATURE_FEEDBACK.

**Why the current wording is insufficient:** This request is neither — the song already exists on Spotify (it's not missing from the catalog), and the customer isn't asking for a new browsing/sorting/filtering *capability*; they're asking for one specific song to be placed on one specific existing editorial playlist. That doesn't cleanly match either rule as currently written, which is presumably why the AI and the human read it differently.

**Proposed clarification (smallest possible):** Add to the CONTENT_CATALOG vs FEATURE_FEEDBACK boundary rule: *"A request to place a specific, already-available song onto a specific existing (often editorial/curated) playlist is CONTENT_CATALOG — a curation/placement request about that content — distinct from a request for a new general capability (e.g., 'let me exclude songs by language' or 'let me sort playlists alphabetically'), which remains FEATURE_FEEDBACK."*

**PROPOSED ONLY.**

---

## 6. Recommendation/personalization control requests phrased as a how-to question

**Observed example:** `CAND_0186` (tweet 1658868) — *"Hi, is there a way to exclude songs in some certain languages from getting into my Discover weekly playlist?"* → AI: FEATURE_FEEDBACK, human gold: **GENERAL_HOW_TO_INFO**.

**What the guide currently says:** FEATURE_FEEDBACK's recommendation/personalization boundary rule says explicit requests for control over algorithmic output (e.g., "let me control what appears in Release Radar") are FEATURE_FEEDBACK. Separately, GENERAL_HOW_TO_INFO's "use this when" list includes the literal signal phrase "Is it possible to...?" / "Is there a way to...?".

**Why the current wording is insufficient:** This single message matches both rules simultaneously — it's phrased with the GENERAL_HOW_TO_INFO signal phrase ("is there a way to") while asking for exactly the kind of personalization control the FEATURE_FEEDBACK rule describes. The guide doesn't say which one wins when a personalization-control request happens to be phrased as a "how do I" / "is there a way to" question rather than an imperative ("let me...", "give us an option to...").

**Proposed clarification (smallest possible):** Add to the FEATURE_FEEDBACK recommendation/personalization boundary rule: *"This applies regardless of phrasing — a request for a new control over algorithmic/recommended content is FEATURE_FEEDBACK even when phrased as a question ('is there a way to...?', 'how do I stop...?'), because the underlying ask is for a capability that does not yet exist, not an explanation of an existing one."*

**PROPOSED ONLY.**

---

## 7. Artist-page visual/asset correction requested by a non-self-identified fan

**Observed example:** `CAND_0129` (tweet 2049949) — *"hi~ can i ask if we can get a photo of [artist] that fits all the 7 members in the Spotify profile?"* → AI: CONTENT_CATALOG, human gold: **ARTIST_SUPPORT**.

**What the guide currently says:** ARTIST_SUPPORT's definition requires the customer to be "acting as or on behalf of an artist/creator" with a creator-side issue; its boundary rule against CONTENT_CATALOG says "an artist being mentioned is NOT enough... the support action must concern the artist's creator-side presence or workflow."

**Why the current wording is insufficient:** This message doesn't self-identify the customer as the artist or as acting on the artist's behalf ("can i ask if we can get..." reads as a fan request), yet it was labeled ARTIST_SUPPORT rather than CONTENT_CATALOG. This suggests that, in practice, a request to correct or add a visual asset (photo/image) specifically on an artist's own official Spotify profile may be intended to route to ARTIST_SUPPORT regardless of who is asking — a distinction the guide's current wording (built around requester identity) doesn't make.

**Proposed clarification (smallest possible):** Add to the ARTIST_SUPPORT vs CONTENT_CATALOG boundary rule: *"A request to correct or add a visual/profile asset (photo, image) specifically on an artist's own official page routes to ARTIST_SUPPORT even when the requester does not self-identify as the artist, since it concerns the artist's page presentation rather than catalog availability. A request about the artist's music/tracklist/availability (not the page's visual presentation) remains CONTENT_CATALOG."* — Alternative: keep this as CONTENT_CATALOG-unless-self-identified (i.e., the guide's rule as written) and treat this one example as a disagreement rather than a rule change. Both directions are defensible; this is presented as a genuine open question for whoever owns the taxonomy, not a recommendation of one answer over the other.

**PROPOSED ONLY.**

---

## 8. Sarcasm handling under the Edge Case 4 closure rule

**Observed example:** `CAND_0130` (tweet 326809) — *"Would like to thank @SpotifyCares for being nice enough to credit the month we weren't able to use the service due to #HurricaneMaria."* → AI: UNKNOWN_OTHER (conversational/closure), human gold: **SUBSCRIPTION_BILLING**, with human notes: *"Customer sarcastically refers to receiving a credit... implying a billing/subscription charge for unavailable service."*

**What the guide currently says:** Edge Case 4 says a message that "primarily closes or acknowledges the conversation... even if it mentions a past feature or expresses disappointment" is UNKNOWN_OTHER + conversational/closure. Its worked examples (e.g., "Aw man I used to love that feature 😔 thanks tho") are all genuine, non-sarcastic gratitude.

**Why the current wording is insufficient:** This message is grammatically identical in form to the guide's own closure examples ("thank you for X"), but reads as sarcastic once the underlying fact (an un-refunded/under-refunded outage) is considered. Edge Case 4 has no guidance at all on detecting or handling sarcasm, so an annotator applying the rule literally (as the AI did) reaches the opposite answer from an annotator who reads the tone as sarcastic (as the human did).

**Proposed clarification (smallest possible):** Add to Edge Case 4: *"Gratitude phrased with an edge of sarcasm or irony (e.g., thanking the company for a partial/minimal remedy to an ongoing billing or service problem) is not genuine closure — classify by the underlying substantive issue being sarcastically referenced (e.g., a billing/credit complaint), not as UNKNOWN_OTHER."*

**PROPOSED ONLY.**

---

## 9. Premium-linked third-party perks / presale codes

**Observed example:** `CAND_0161` (tweet 2125232) — *"what do I gotta do to get the DVSN presale code? Outside of already paying a premium monthly service?"* → AI: UNKNOWN_OTHER, human gold: **GENERAL_HOW_TO_INFO**, with human notes: *"Asking how to obtain a presale code/benefit associated with Premium; no billing dispute. Medium confidence because the guide does not explicitly cover concert presale-code requests."*

**What the guide currently says:** Nothing directly. GENERAL_HOW_TO_INFO covers "how do I...?" questions and eligibility/promotion enrollment questions in general terms; there is no example or rule addressing non-Spotify perks (concert presale codes, partner benefits) that are gated behind a Premium subscription.

**Why the current wording is insufficient:** This is a human-acknowledged gap (the annotator's own note says so directly), not an inference from disagreement alone. Spotify Premium has historically bundled various third-party perks (presale codes, partner offers); the guide gives no explicit steer on whether "how do I redeem/qualify for a Premium-linked perk" is GENERAL_HOW_TO_INFO (an eligibility/how-to question) or something else.

**Proposed clarification (smallest possible):** Add one example to GENERAL_HOW_TO_INFO's "Use this when" list: *"Asking how to redeem or qualify for a Premium-linked benefit or perk (e.g., a concert presale code) with no billing dispute → GENERAL_HOW_TO_INFO, following the same logic as other eligibility/enrollment questions."*

**PROPOSED ONLY.**

---

## Summary table

| # | Pattern | Candidate ID(s) | Evidence strength |
|---|---|---|---|
| 1 | Access-blocked billing/cancellation | CAND_0059 vs CAND_0060 | Direct within-set inconsistency |
| 2 | How-to with incidental access mention | CAND_0062 | Single case, clear rule gap |
| 3 | Edge Case 1: blocker vs informal demand | CAND_0024 | Single case, clear rule gap |
| 4 | "After an update" ≠ design change | CAND_0098, CAND_0106 | Recurring (2/2) |
| 5 | Curated playlist placement | CAND_0136 | Single case, clear rule gap |
| 6 | Personalization control phrased as how-to | CAND_0186 | Single case, clear rule gap |
| 7 | Artist-page asset correction by a fan | CAND_0129 | Single case, open question (two defensible answers) |
| 8 | Sarcasm under Edge Case 4 | CAND_0130 | Single case, clear rule gap |
| 9 | Premium-linked third-party perks | CAND_0161 | Single case, human-acknowledged gap |

**All nine items above are PROPOSED ONLY. No changes have been made to `discovery/TAXONOMY_REVIEW_GUIDE.md` or to any Human Gold Label.**
