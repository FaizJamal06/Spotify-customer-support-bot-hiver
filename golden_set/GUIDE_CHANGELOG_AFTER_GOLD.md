# Guide Changelog — Post-Golden Clarifications

Applied to `discovery/TAXONOMY_REVIEW_GUIDE.md`.
Guide hash before this pass: `2e5666478a7c01f10dc9dc39f4df0654` (632 lines).
Guide hash after this pass: `d3fa5491a1d422df0d4afeff5aa8a93f` (649 lines).

Every added line is tagged **"(post-golden clarification)"** inline in the
guide, so all changes made in this pass remain individually identifiable and
distinguishable from the original frozen text.

**Taxonomy confirmation:** the guide still contains exactly 8 top-level intent
sections (`## 1. ACCOUNT_ACCESS` through `## 8. UNKNOWN_OTHER`), unchanged in
name, number, and order:
`ACCOUNT_ACCESS, SUBSCRIPTION_BILLING, APP_TECH_ISSUE, CONTENT_CATALOG, FEATURE_FEEDBACK, ARTIST_SUPPORT, GENERAL_HOW_TO_INFO, UNKNOWN_OTHER`.
No intent was added, removed, renamed, merged, or split. All 7 changes below
are wording/example additions to existing rules only.

---

## Applied changes

### 1. ACCOUNT_ACCESS vs SUBSCRIPTION_BILLING — cancellation/access boundary

**Section:** §1 ACCOUNT_ACCESS, "Boundary rule vs SUBSCRIPTION_BILLING."

**Change:** Added a sub-rule distinguishing two kinds of obstacle when a
billing action (cancel, downgrade, refund) is blocked by an access problem:
- Obstacle requires Spotify to perform an identity/access-verification step → ACCOUNT_ACCESS (that step is itself the next support action).
- Obstacle is outside Spotify's control (e.g., a deleted third-party linked account) → SUBSCRIPTION_BILLING (the customer's stated request is the next support action).

Also added two contrasting examples to the "Positive/Near-miss examples" list.

**Motivating human-gold examples:**
- `CAND_0060` (tweet 540363) — *"need to cancel my account. Problem is no idea what email was used. Tried them all. How can I cancel."* → human gold **ACCOUNT_ACCESS**.
- `CAND_0059` (tweet 2622906) — *"I need to cancel a prime account but I can't login at all because my Facebook associated with it is gone."* → human gold **SUBSCRIPTION_BILLING**.

These two near-identical "cancel-blocked-by-access" messages received opposite
gold labels in the completed 200-example set. The new sub-rule gives a
principled distinction (Spotify-resolvable identity question vs.
Spotify-uncontrollable external obstacle) consistent with both outcomes as
observed, rather than declaring one of them wrong.

---

### 2. Edge Case 1 — blocker vs stated demand

**Section:** Edge Case 1 — Account Compromise + Billing.

**Change:** Added a "Blocker vs demand" paragraph: when a message states both
a concrete blocker preventing self-resolution and a demand (however
informally styled, e.g. a hashtag), the concrete blocker takes precedence.
Added one example.

**Motivating human-gold example:**
- `CAND_0024` (tweet 1659831) — *"someone's hacked my account and apparently there's no way for me to change my password! #crock #fixthis #givememumoneyback"* → human gold **ACCOUNT_ACCESS**, despite the explicit "#givememumoneyback" billing demand.

---

### 3. ACCOUNT_ACCESS vs GENERAL_HOW_TO_INFO — incidental access mention

**Section:** §1 ACCOUNT_ACCESS, "Do NOT use this when."

**Change:** Added a bullet: an informational question with an access symptom
mentioned only as background (not as the actual ask) → GENERAL_HOW_TO_INFO.
Added one example to the Positive/Near-miss list.

**Motivating human-gold example:**
- `CAND_0062` (tweet 540359) — *"how can I know which address is set up in my account? I have signed up in a family plan but some of the members can not sign in."* → human gold **GENERAL_HOW_TO_INFO** (AI had suggested ACCOUNT_ACCESS).

---

### 4. CONTENT_CATALOG vs FEATURE_FEEDBACK — curated/editorial playlist placement

**Section:** §4 CONTENT_CATALOG, "Use this when" list, and "Boundary rule vs FEATURE_FEEDBACK."

**Change:** Added a bullet to "Use this when": a request to place an
already-available song onto a specific existing (e.g. curated/editorial)
playlist is CONTENT_CATALOG. Extended the FEATURE_FEEDBACK boundary rule with
the same distinction (placement request about existing content vs. a new
general capability, which stays FEATURE_FEEDBACK) plus an example.

**Motivating human-gold example:**
- `CAND_0136` (tweet 508845) — *"I think that N.E.R.D & Rihanna's 'Lemon' would be perfect on the 'Today's Top Hits' Playlist. Please can you add it..."* → human gold **CONTENT_CATALOG** (AI had suggested FEATURE_FEEDBACK).

---

### 5. APP_TECH_ISSUE vs FEATURE_FEEDBACK — update timing is not itself a design signal

**Section:** §3 APP_TECH_ISSUE, "Boundary rule vs FEATURE_FEEDBACK (Removed/Changed vs Malfunction)."

**Change:** Added a bullet: a problem that started right after an app update
is, by itself, still presumptively a malfunction (APP_TECH_ISSUE) — not
evidence of a deliberate design change — unless the customer explicitly
objects to the new behavior as a choice (asks for reversion/optionality).
Added one example.

**Motivating human-gold examples:**
- `CAND_0098` (tweet 2913925) — *"can't play anything that isn't downloaded... iPhone 7 with the latest app update"* → human gold **FEATURE_FEEDBACK** (AI HIGH-confidence suggested APP_TECH_ISSUE).
- `CAND_0106` (tweet 2757619) — *"So this didn't happen before I updated my phone yesterday. Is there any way around this?"* → human gold **FEATURE_FEEDBACK**, with human notes: *"issue faced after update, so this is not primarily reporting an unexpected technical malfunction anymore."*

Both examples were moved to FEATURE_FEEDBACK on the strength of "started
after an update," despite neither containing explicit design-criticism
language. The new sentence is worded to preserve the *existing* default
(malfunction unless explicit design criticism) rather than encode the
observed human outcome as the new rule — i.e., this clarification
strengthens the existing rule's wording; it does not assert that `CAND_0098`
or `CAND_0106` were labeled "correctly" against it. See the "Unresolved
cases" section below for related residual disagreements this change does
not fully explain.

---

### 6. Edge Case 4 — sarcasm is not genuine closure

**Section:** Edge Case 4 — Conversational Closure with Feedback Signal.

**Change:** Added a "Sarcasm" paragraph: gratitude referencing an unresolved
or only-partially-resolved billing/service problem should be read as the
underlying substantive complaint, not genuine closure. Added a new "Examples
— sarcastic (not genuine closure)" subsection with one example.

**Motivating human-gold example:**
- `CAND_0130` (tweet 326809) — *"Would like to thank @SpotifyCares for being nice enough to credit the month we weren't able to use the service due to #HurricaneMaria."* → human gold **SUBSCRIPTION_BILLING**, with human notes: *"Customer sarcastically refers to receiving a credit... implying a billing/subscription charge for unavailable service."* (AI had read this as genuine closure → UNKNOWN_OTHER.)

---

### 7. UNKNOWN_OTHER — short but concretely classifiable questions

**Section:** §8 UNKNOWN_OTHER, "Negative examples (things that are NOT UNKNOWN)."

**Change:** Added one example: a short, casually-phrased question that names
a specific, concrete topic (an integration/compatibility question) is
classifiable, not UNKNOWN.

**Motivating human-gold example:**
- `CAND_0127` (tweet 2878323) — *"@115888 You work with Alexa, right??"* → human gold **GENERAL_HOW_TO_INFO** (AI defaulted to UNKNOWN_OTHER).

---

## Explicitly NOT changed (per your instructions)

- **Row 6 — Recommendation/personalization rule** (FEATURE_FEEDBACK vs GENERAL_HOW_TO_INFO for "is there a way to..." phrasing). Not modified. `CAND_0177` ("is there a way to make shuffle simply random?" → gold FEATURE_FEEDBACK) and `CAND_0186` ("is there a way to exclude songs by language from Discover Weekly?" → gold GENERAL_HOW_TO_INFO) are near-identical in phrasing and substance but produced different gold outcomes. This is recorded as an **unresolved annotation ambiguity** — no wording change was made to resolve it, and no gold label was touched.
- **Row 7 — CONTENT_CATALOG vs FEATURE_FEEDBACK "blacklist" example.** Not modified. `CAND_0147` ("wish there was a function to block an artist... in your generated playlists and radios" → gold CONTENT_CATALOG) is nearly word-for-word the guide's own existing FEATURE_FEEDBACK example ("Can I blacklist certain bands from shuffle and radios?", Ex 38). This is recorded as an **observed inconsistency between the completed annotation and an existing guide example** — the guide was not rewritten around this single case, per your instruction not to rewrite the guide around one contradiction.
- **Row 9 — Short-continuation operational rule.** Not modified. `CAND_0064` ("Still does it after reinstall... any help on this?" → gold GENERAL_HOW_TO_INFO, continuing an established malfunction thread) and `CAND_0133` ("It's working now, nvm. I tried a different browser and it was the same issue." → gold GENERAL_HOW_TO_INFO, reading as closure) both diverge from the existing short-continuation rule with no explanatory human notes. Recorded as **unresolved post-golden inconsistencies** — no rule change was applied.

These three items remain open questions for the taxonomy owner, not resolved
by this pass.

---

## Confirmations

- **Taxonomy unchanged:** exactly 8 intents remain, same names, same order. Verified programmatically (`## 1.` through `## 8.` headers all present, no others added).
- **No human gold labels were changed.** `golden_set/GOLDEN_200_FINAL.csv` and the underlying `Human Final Label` values in `GOLDEN_ANNOTATION_200_labeled.xlsx` were not read-write touched in this pass (file timestamps confirm no modification); this changelog only cites existing gold values as evidence for the wording changes.
- **No candidate examples were changed.** `golden_set/CANDIDATE_MANIFEST_200.csv` was not modified.
- **No taxonomy-level change was applied.** All 7 edits are additive wording/example clarifications to existing rules; none renamed, merged, split, or added an intent.
- Every added line is tagged "(post-golden clarification)" so the diff from the original frozen guide is fully traceable.
- Nothing in this pass was committed to git.
