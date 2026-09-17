# Decision Log

## How to read this document

This is my (the candidate's) record of the non-obvious decisions behind this
project and why I made them. A note on attribution, since this project was
built with AI coding assistants (per the assignment's explicit rules):

- **The methodology and product decisions below are mine.** Taxonomy design,
  data-split boundaries, sampling philosophy, what counts as gold, when to
  freeze something, and when to leave something unresolved were my calls.
- **AI tools (Claude Code) did assistance work**: exploring the data,
  writing/running scripts, drafting candidate wording, running QA/consistency
  checks, summarizing large amounts of text, and proposing alternatives for
  me to accept, reject, or modify.
- Where an AI-proposed option is what I went with, I say so and explain why I
  accepted it — that acceptance is still my decision. Where I overrode or
  narrowed an AI proposal, I say that too.
- I'm not claiming to have hand-typed scripts or manually re-read all 43,092
  pairs myself — I didn't. I directed the analysis, reviewed what came back,
  and made the calls on what to keep, reject, freeze, or leave open.

---

## Core project decisions

1. **Brand Selection: SpotifyCares**
   - *Why we chose it*: High response diversity (77.2% unique), moderate DM redirect rate (31.8%), rich interaction depth.
   - *Evidence*: `analyze_brands.py` run on a subset.
   - *Attribution*: I picked the brand-selection criteria (diversity, DM-redirect rate, interaction depth) and made the final call; the scripted analysis across brands was AI-assisted.

2. **Thread-Level Splitting & Leakage Prevention**
   - *Why we chose it*: Prevents leakage where a customer's follow-up tweet in the test set has context embedded in the retrieval index. Guarantees clean isolation.
   - *Attribution*: My requirement (no leakage across pools); AI-assisted implementation in `data/split.py` and verification.

3. **Three-Way Data Split (Development / Retrieval / Test)**
   - *Why we chose it*: Ensures the taxonomy discovery and pilot labeling are done on "seen" data without contaminating the retrieval index or the sealed golden evaluation set.
   - *Current sizes* (from `data/generated/split_stats.json`): DEVELOPMENT 4,242 threads / 6,481 pairs; RETRIEVAL 18,382 threads / 27,903 pairs; TEST 5,656 threads / 8,708 pairs. Split seed: `SPLIT_SEED=42` (`config.py`).
   - *Attribution*: My design; AI-assisted implementation and stat verification.

4. **UNKNOWN Intent as Last Resort**
   - *Why we chose it*: Improves safety. Ambiguous, off-topic, or non-English messages map to a safe "escalate" action, rather than forcing an unreliable label.
   - *Validation*: In the final 200-example golden set, UNKNOWN_OTHER accounts for 23/200 (11.5%) of human gold labels — present but not dominant, consistent with "last resort, not a dumping ground."
   - *Attribution*: My design principle; AI-assisted guide wording and empirical check against the final gold distribution.

5. **Removal of PLAN_PROMOTION as a Top-Level Intent**
   - *Why we removed it*: Too few clearly distinct examples justified a separate class (120/6,481 ≈ 1.9% of DEVELOPMENT, 4/300 in the discovery sample). Plan-related messages split cleanly into GENERAL_HOW_TO_INFO (informational) or SUBSCRIPTION_BILLING (payment/entitlement problem).
   - *Attribution*: My decision after reviewing the 300-example discovery sample; AI-assisted the frequency analysis (`discovery/DEVELOPMENT_DIVERSITY_AUDIT.md`) that made the case concrete.
   - *Note*: This entry's number (5) is referenced directly from `discovery/TAXONOMY_REVIEW_GUIDE.md` ("Decision Log #5") and `discovery/DEVELOPMENT_DIVERSITY_AUDIT.md` — kept stable here so those cross-references stay valid.

6. **Freeze the 8-label Taxonomy and Annotation Guide**
   - *Why we made it*: To establish a stable, unambiguous standard for labeling the golden evaluation set. Edge cases are handled via documented operational rules rather than structural taxonomy changes.
   - *Attribution*: My decision to freeze at this point (after the 300-example discovery review and pilot-protocol dress rehearsal); AI-assisted drafting of the guide text itself, which I reviewed and approved.

7. **Edge-Case Resolutions for Annotation Guide**
   - *Why we made it*: Adopted operational rules for account compromise + billing, vague "fix your app", non-English messages, and closure + feedback wording to ensure inter-annotator consistency.
   - *Attribution*: I identified these four as the recurring structural gaps worth resolving explicitly (they kept coming up while reviewing the discovery sample); AI drafted the specific rule text and examples, which I approved into the frozen guide.

8. **Chronology Using `created_at` Instead of `tweet_id`**
   - *Why we made it*: Discovered a chronology bug where numeric `tweet_id` comparison (`tweet_id < target_tweet_id`) was invalid for ordering across tweets due to Snowflake ID inconsistencies. Rebuilt thread context using actual `created_at` timestamps.
   - *How it was found*: Surfaced while building the pilot annotation workbook, when spot-checking preceding-context ordering. Fixed by centralizing chronology logic in `discovery/chronology.py` with a regression test suite (`discovery/test_chronology.py`), then reusing that single utility everywhere a thread needs to be ordered (pilot workbook, golden-set candidate context, golden-set `THREAD_VIEW` sheet) instead of re-deriving ordering logic per script.
   - *Attribution*: I flagged the ordering discrepancy during spot-checking and required a single shared, tested utility instead of a one-off patch (to prevent the same bug recurring in a different script); AI implemented the fix, the tests, and the call sites.

9. **Keeping ARTIST_SUPPORT**
   - *Why we made it*: Although low-frequency (25/6,481 ≈ 0.4% of DEVELOPMENT), it is structurally distinct from listener-facing content issues — it represents creator-side support, which is operationally different from the rest of the taxonomy. The golden set uses deliberate rare-intent oversampling so this category isn't invisible to evaluation.
   - *Attribution*: My call to keep it despite the low base rate; AI-assisted frequency analysis and the golden-set oversampling mechanics.

10. **Discovery vs Pilot vs Golden Distinction**
    - *Why we made it*: Discovery (300 examples) is for taxonomy refinement. Pilot (100 examples, `discovery/PILOT_ANNOTATION_100*.xlsx`) is a protocol dress rehearsal. Golden (200 examples) is the isolated final evaluation. This prevents overfitting the taxonomy to the same examples it's evaluated on, and separates "does the workbook/interface work" from "is this a valid benchmark."
    - *Attribution*: My scoping decision; AI-assisted building each artifact to that scope.

11. **Golden Isolation**
    - *Why we made it*: The golden set must not overlap with retrieval corpus, discovery examples, or pilot examples, and must never be inserted into the RAG corpus, ensuring a pure evaluation benchmark rather than a set the system could have partially "seen."
    - *Verification performed*: thread/tweet-level disjointness between DEVELOPMENT/RETRIEVAL/TEST verified programmatically; the 200 golden candidates were checked against the 300-example discovery sample (0 overlap) and against the retrieval pool for exact and normalized-text near-duplicates (0 overlap after one replacement — see entry 19).
    - *Attribution*: My requirement; AI-assisted the overlap-detection scripts and reported the results for my review.

12. **Representative + Boundary Sampling Philosophy**
    - *Why we made it*: Golden sampling must not be purely random or artificially balanced across intents. It requires a representative base, deliberate boundary coverage, rare-intent coverage, and genuine UNKNOWN coverage to test real-world agent situations, without letting hard/boundary cases dominate the set.
    - *Attribution*: My sampling philosophy (stated as an explicit constraint before any sampling happened: "do not let boundary/hard-case examples dominate"); AI-assisted the stratified draw and the diversity constraints (max 2 examples per thread/customer), which I then reviewed row-by-row.

13. **Simple Baseline Strategy**
    - *Why we made it*: To prove AI utility, use a majority-class baseline (Trivial) and a TF-IDF + Logistic Regression baseline (Simple). Sophistication is not the goal; proving improvement is.
    - *Status*: **Complete.** Both baselines were trained on the 296-example discovery substitution (296 of the 300 DEVELOPMENT discovery examples, 4 excluded as unparseable), not the originally-planned 100 pilot-labeled examples, which were never collected — see entry #24. Evaluated on the 200 golden TEST examples. Results: `evaluation/BASELINE_RESULTS.md`, `evaluation/results/baseline_results.json`.

14. **Avoiding Over-engineering**
    - *Why we made it*: The intended system deliberately relies on a simple, modular architecture (Intent → Triage → Retrieval → Check → Grounded Reply). Sentiment, information extraction, FAISS, rerankers, and complex multi-agent setups are excluded unless proven necessary.
    - *Attribution*: My scoping decision, made explicit up front to avoid scope creep during AI-assisted implementation.

---

## Golden-set construction, annotation, and post-golden decisions

*(Added at this documentation checkpoint — these decisions were made across the golden-set sampling, human annotation, and post-annotation guide-review sessions, and were not yet written down here.)*

15. **Dataset Source: Customer Support on Twitter (Kaggle, TWCS)**
    - *Why this dataset*: It was the assignment's specified primary dataset (`assignment.text`: "Primary: Customer Support on Twitter... ~3M tweets, multi-turn threads, dozens of brands"). The actual decision I made within that constraint was which single brand to build for (entry 1) and how to structure isolation within it (entries 2–3) — the dataset itself wasn't a choice among alternatives, it was the given substrate.
    - *Attribution*: Not a discretionary decision; recorded here for completeness since the task asked why this dataset/source was used.

16. **TEST Pool (not DEVELOPMENT) as the Source of the Final 200-Example Golden Set**
    - *Why*: DEVELOPMENT was used for taxonomy discovery and the pilot dress rehearsal — the taxonomy and guide were shaped by looking at DEVELOPMENT examples. Any golden set drawn from DEVELOPMENT would risk measuring "does the taxonomy fit the examples it was built from" rather than "does the taxonomy generalize." TEST was sealed from the start specifically so it could serve as an unseen benchmark once the taxonomy stabilized.
    - *Attribution*: My requirement, stated before golden-set sampling began; AI verified programmatically that every golden candidate's `thread_id` resolves to TEST and that none match DEVELOPMENT or the 300-example discovery sample.

17. **Golden Set Immutability — Before and After Annotation**
    - *Before annotation*: The 200 candidates, once sampled, were fixed except for concrete QA-rule failures (e.g., two candidates were swapped out during QA for exact/near-duplicate overlap with the retrieval pool — documented in `golden_set/CANDIDATE_MANIFEST_200.csv`'s `review_notes` column). I explicitly forbade full resampling to fix minor issues, to avoid iterating the set toward "easy" examples.
    - *After annotation*: Once I completed human labeling, I decided the 200 gold labels are locked — no further relabeling based on AI disagreement, taxonomy discussion, or guide changes. I stated this explicitly and repeatedly across the post-annotation sessions ("Human Final Label ... immutable," "do NOT change any Human Gold Label").
    - *Why*: The golden set is meant to function as a fixed evaluation benchmark ("final exam," per `implementation_plan.md`). If I kept adjusting gold labels every time an analysis surfaced a disagreement, the benchmark would stop being independent of the system being evaluated against it, and every future evaluation run would be measured against a moving target.
    - *Attribution*: My decision, both times. AI's role was limited to flagging concrete rule violations (duplicate overlap, tweet-ID bugs) for my decision, and to running the post-annotation agreement analysis that could have suggested relabeling but was explicitly not used that way.

18. **Retrieval Evidence Must Come Only From the Retrieval Pool**
    - *Why*: If the system's grounding evidence could be pulled from TEST (or DEVELOPMENT), the "historical resolution" a generated reply is grounded in could itself be a golden example — making the evaluation partially circular. Restricting the retrieval index to the RETRIEVAL pool keeps "what evidence the system can cite" and "what we evaluate against" strictly separate, which matters once response-generation work starts.
    - *Attribution*: My requirement, following from the same leakage logic as entries 2–3, made explicit now because it will govern the retrieval-index build in the next milestone.

19. **Multi-Intent Messages Reduced to a Single Primary Intent**
    - *Why*: A message can plausibly touch two categories (e.g., "hacked AND billed"). Rather than allow multi-label annotation (which complicates both labeling consistency and downstream evaluation), the guide requires exactly one primary intent, chosen by "what should drive the next support action" — with an explicit tie-breaker order (security/access → billing → technical → feature/info) used *only* when two issues are genuinely equally explicit, not as an automatic precedence rule.
    - *Attribution*: My decision to require single-label annotation (simplicity for both annotators and evaluation) and to reject "just use the tie-breaker order as the primary rule" (too mechanical — it produced wrong answers on cases where one issue was clearly secondary); AI drafted the "primary requested action" framing and the worked examples, which I reviewed.

20. **Multilingual Examples: Translate First, Then Classify**
    - *Why*: Early on, non-English messages were at risk of being reflexively dumped into UNKNOWN_OTHER because they were "hard to read" rather than because they were genuinely ambiguous. The guide's Edge Case 3 requires translating the target message and *only the preceding customer context* (never the brand's response or later messages) before applying the same taxonomy rules as English messages.
    - *Validation*: 6 multilingual examples (Portuguese, Indonesian ×3, Turkish, and others) were deliberately included in the final 200 for coverage, and classified using this rule rather than defaulted to UNKNOWN_OTHER.
    - *Attribution*: My rule (don't let language be a proxy for "can't classify"); AI executed translation-assisted classification for the multilingual candidates under that rule, which I reviewed.

21. **AI-Assisted Prelabeling Workflow, and Why Final Gold Lives in `Human Final Label`**
    - *What happened*: After the blind annotation workbook (`GOLDEN_ANNOTATION_200.xlsx`, with a blank `Human Gold Label`/`Human Notes` pair) was built, I asked for an AI-prelabeling pass to speed up my own review: AI Suggested Label, AI Reasoning, and AI Confidence columns were added, plus a separate `Human Final Label` / `Human Review Notes` pair for me to record my adjudicated decision against — explicitly kept distinct from the original blind `Human Gold Label` column, with an instruction banner stating the AI columns are suggestions only.
    - *The column question*: When I returned the completed workbook (`GOLDEN_ANNOTATION_200_labeled.xlsx`), the original `Human Gold Label` column was blank for all 200 rows — I had done my review directly in `Human Final Label` instead (the column literally described as "record your final adjudicated label here"). Before treating anything as gold, this was flagged back to me rather than silently assumed, and I confirmed `Human Final Label` is the authoritative column.
    - *Why this is recorded here*: This is exactly the kind of place a "Claude decided X" narrative would misrepresent what happened. To be precise: I made the labeling decisions (all 200 of them, including 17 where I overrode the AI suggestion); I decided which column counts as gold when asked; AI did not decide, infer, or default this on its own.

22. **Post-Golden Taxonomy Review: Keep Exactly 8 Intents**
    - *Why*: After completing human annotation, I asked for an AI-vs-human agreement analysis (91.5% exact agreement, 17 disagreements) and a review of whether any disagreement pattern pointed to a genuine taxonomy gap rather than a wording problem. All 17 disagreements, once inspected, were boundary/wording-level (e.g., "does 'started after an update' imply a design change," "is a sarcastic thank-you closure or a complaint") — none described a support need that didn't fit any of the 8 categories. I decided to keep the taxonomy at exactly 8 intents and treat all 9 proposed changes as wording/example-level clarifications, not intent redesign.
    - *Attribution*: My decision. AI produced the agreement analysis and the 9 candidate clarifications (`golden_set/PROPOSED_GUIDE_CLARIFICATIONS.md`) for me to evaluate; I did not run a formal three-way "guide clarification vs. intent expansion vs. new intent" classification pass on each item before deciding this (I made the call directly, because none of the 9 items were framed as new-intent candidates in the first place — all 9 were already guide-wording proposals).

23. **Which Post-Golden Guide Clarifications Were Applied, and Which Were Deliberately Left Open**
    - *Applied (7 of 9)*: ACCESS-vs-BILLING cancellation/access-blocker distinction; Edge Case 1 blocker-vs-demand tie-break; ACCESS-vs-HOW_TO incidental-access-mention rule; CONTENT_CATALOG curated-playlist-placement rule; APP_TECH_ISSUE update-timing-≠-design-change rule; Edge Case 4 sarcasm rule; UNKNOWN_OTHER short-but-concrete-question example. Each is tagged inline in `discovery/TAXONOMY_REVIEW_GUIDE.md` as `(post-golden clarification)` and documented with its motivating example(s) in `golden_set/GUIDE_CHANGELOG_AFTER_GOLD.md`.
    - *Deliberately not applied (3 of 9)*: (a) the recommendation/personalization "is there a way to..." phrasing rule — two near-identical golden examples (`CAND_0177`, `CAND_0186`) received different gold labels, and I chose not to paper over that with a rule that would only describe one of them; (b) the CONTENT_CATALOG-vs-FEATURE_FEEDBACK "blacklist" wording — one golden example (`CAND_0147`) conflicts with an existing worked example already in the frozen guide, and I chose to record that as an observed inconsistency rather than rewrite an already-unambiguous rule around a single contradiction; (c) the short-continuation operational rule — two golden examples (`CAND_0064`, `CAND_0133`) diverge from the existing rule with no annotator notes explaining why, so I left them as open questions instead of guessing at a justification.
    - *Why leaving things unresolved is itself a decision*: I could have asked for a rule that "resolved" all 9 patterns. I chose not to, on the 3 above, because the evidence for those was internally inconsistent or single-case — writing a confident-sounding rule would have created false precision, not real consistency. This is a deliberate scope decision, not an oversight.
    - *Attribution*: My decision on every apply/leave-open call, row by row; AI drafted the specific wording for the 7 applied changes and the classification of all 9, which I approved or rejected individually before any edit was made to the frozen guide.

24. **Why the Pilot Was Not Used as a Labeled Gold Set**
    - *What the pilot was*: `discovery/PILOT_ANNOTATION_100*.xlsx` (4 iterations) tested whether the annotation workbook, context presentation, and chronology handling actually worked in practice — a dress rehearsal for the *process*, not a labeling exercise. Per `CHECKLIST.md`, the 100 examples were never human-annotated.
    - *Why it stayed that way*: By the time the golden-set methodology and the 200-example annotation pipeline were validated directly (through the golden set's own QA passes and my actual labeling of all 200), hand-labeling a separate, smaller, workbook-mechanics-only set added cost without adding confidence in the taxonomy — the 300-example discovery review had already done that job. I deferred it rather than spend more time on a set that wouldn't become part of the evaluation benchmark either way.
    - *Attribution*: My scoping decision to defer, not an oversight; `CHECKLIST.md` has carried this as "DEFERRED" since the pilot-preparation phase.

25. **Other Methodology Decisions Affecting Validity/Reproducibility**
    - *Fan-out thread exclusion from context*: 13 DEVELOPMENT/TEST threads with >20 messages and ≥3 distinct customer authors were identified as "mega-threads" where attaching preceding context risks pulling in a different customer's unrelated conversation. I required that any candidate drawn from such a thread be usable only if it needs no preceding context at all — never given fabricated or cross-customer context.
    - *Retrieval-overlap checks as a second, empirical safety net*: Beyond pool-level (thread/tweet ID) isolation, every golden candidate was checked for exact and normalized-text duplication against the retrieval pool before annotation, since near-identical short messages (e.g., generic "thanks!" closures) can recur verbatim across unrelated threads even when their thread IDs are correctly isolated. Two candidates were replaced after this check found overlaps.
    - *AI suggestions kept structurally non-binding*: The `Human Gold Label` dropdown defaulted to blank (not pre-filled with the AI suggestion), and the workbook carried an explicit instruction banner that AI columns are prelabels only. This was a deliberate anti-anchoring-bias design choice, made before I did any labeling.
    - *Fixed seeds for reproducibility*: `SPLIT_SEED=42`, `DISCOVERY_SAMPLE_SEED=123`, `GOLDEN_SAMPLE_SEED=456` (`config.py`) govern every random draw in the pipeline (pool split, discovery sample, golden candidate sampling), so the same code against the same raw `twcs.csv` reproduces the same splits and candidate pool.
    - *Attribution*: All four were my requirements, set before the relevant sampling/checking work ran; AI implemented the checks and reported results against them.

---

## Retrieval, generation, and triage decisions (Phase 3)

*(Added at this documentation checkpoint — these decisions were made across the retrieval, generation, triage, and judge-calibration work sessions and were not yet written down here; only their evidence trail existed in code docstrings and result files until now.)*

26. **Separate, Additive Triage Ground Truth Instead of Reusing or Fabricating It**
    - *Why we made it*: The golden-200 set has intent labels only (`human_gold_label`) — no triage ground truth was ever collected as part of that annotation. Rather than reopen the frozen golden-200 labels or derive triage labels from the intent labels, a separate, additive 40-example annotation (`golden_set/TRIAGE_ANNOTATION_40.csv`) was built specifically for triage evaluation, leaving the golden-200 intent gold completely untouched.
    - *Attribution*: My requirement (do not touch frozen gold to backfill a different label type); AI-assisted building and structuring the separate annotation file.

27. **Confidence Threshold for Triage: Tested and Explicitly Rejected**
    - *Why we made it*: `evaluation/CALIBRATION_RESULTS.md` found the LLM classifier overconfident in every one of 5 quantile buckets (ECE=0.14). Rather than silently omit a confidence-based Tier-2 rule, `evaluation/triage.py` carries an explicit `CONFIDENCE_THRESHOLD_REJECTED = True` marker — a visible, inspectable record that the hypothesis was tested and rejected on evidence, not simply never considered.
    - *Attribution*: My requirement that the rejection be recorded as a marker rather than silently omitted; AI ran the calibration analysis and implemented the marker.

28. **DM-Redirect Heuristic Locked Before Computing Any Per-Intent Rate**
    - *Why we made it*: `classify_historical_reply()` in `evaluation/triage.py` was written down before any per-intent DM-redirect rate was computed, and was not revised after seeing the results — specifically to prevent tuning the rule to fit a result after the fact.
    - *Attribution*: My requirement (pre-registration discipline for a rule that would otherwise be easy to quietly adjust); AI implemented and ran the analysis against the already-locked rule.

29. **ACCOUNT_ACCESS Tier-2 Rule: Shipped Disabled by Default After Failing a Formal Significance Test**
    - *Why we made it*: The rule initially looked statistically compelling on an informal read (non-overlapping Wilson 95% CIs vs. every other intent). A follow-up audit (`evaluation/audit_triage_tier2.py`, `evaluation/results/triage_tier2_audit.json`) ran a proper two-proportion test against the closest competitor (SUBSCRIPTION_BILLING): Fisher's exact p=0.094 (not significant), risk-difference 95% CI includes zero. The rule's rate also collapsed from 100% to 0% under one equally-plausible alternate heuristic wording (an "inbox"-only trigger variant). Rather than ship the rule uncritically or discard the work, it was kept as an explicit, disabled-by-default toggle (`TIER2_ACCOUNT_ACCESS_RULE_ENABLED = False`) with a separate `TIER2_ACCOUNT_ACCESS_RULE_VALIDATED = False` marker recording that it has not been validated against the human triage holdout.
    - *Attribution*: My requirement that a rule this fragile not ship live by default, and that its fragility be recorded rather than hidden; AI ran the significance test and the robustness-variant check and implemented both markers.

30. **Corpus Inspection Overturned a Plausible Hypothesis About Short Customer Messages**
    - *Why we made it*: Rather than assume short customer messages in the retrieval corpus were mostly low-content chat noise, `MIN_CUSTOMER_MSG_LENGTH`'s filter threshold was set only after directly inspecting the actual deduplicated pool. Only 4 of 26,914 pairs fell below it, and all four were bare, content-free `@handle`-only mentions — not terse-but-real reactions (e.g. "how?", "Srsly?"), which the filter deliberately leaves untouched.
    - *Attribution*: My requirement to check the corpus before filtering rather than filter on assumption; AI ran the inspection and reported the actual composition of what would be excluded.

31. **An 8-Example Pilot Caught a Real Generation Failure Before the Full-Scale Spend**
    - *Why we made it*: Before committing to the full 200x4 generate+judge sweep, an 8-example pilot (`evaluation/GENERATION_JUDGE_PILOT_RESULTS.md`) was run specifically to catch problems cheaply. It found the generator copying, and at k=5 outright fabricating, a stale agent sign-off code that did not appear in any of that example's retrieved evidence — fixed (the evidence-cleaning step in `evaluation/generation.py`) before the real 800-condition run spent any budget on it.
    - *Attribution*: My requirement to pilot before the full spend; AI ran the pilot, identified the artifact-copying pattern in the output, and implemented the fix.

32. **Rejected a Naive Frequency-Based URL-Stripping Rule Because It Would Have Deleted a Real, Correct Answer**
    - *Why we made it*: A simple "strip URLs that recur often" rule was considered and rejected after checking it against the actual corpus: the genuinely substantive Indonesian-support-email URL recurs 117 times in the 3,000-pair retrieval sample, precisely because it is the correct canonical answer reused across many similar requests. Stripping by raw frequency would have deleted it. `clean_brand_text()` instead uses a referential-cue rule (is the URL introduced by "at"/"via"/"here"/a colon?) to distinguish a referenced, substantive resource link from a bare boilerplate tracking link.
    - *Attribution*: My requirement to check a candidate heuristic against real data before adopting it; AI ran the frequency check, found the case it would have broken, and implemented the cue-based rule instead.

33. **Customer-Message-Only Embeddings for Retrieval**
    - *Why we made it*: The retrieval index embeds only `customer_text` for each sampled pair, never the paired brand reply. This finds similar customer *problems*, not similar full conversations, so reply-side boilerplate (sign-offs, generic phrasing) cannot dominate similarity — `brand_text` is returned as grounding evidence at query time but is never itself searched on.
    - *Attribution*: My design requirement; AI implemented the embedding/indexing pipeline accordingly.

34. **Checked for Already-Cached Judge Scores Before Running Part I, Avoiding Unnecessary API Spend**
    - *Why we made it*: Before building the judge-human calibration workbook (Part I), it was checked whether the LLM judge's scores for the 40-example calibration subset already existed from the earlier k-ablation sweep — the subset is a subset of the 200 already scored at k=3. `evaluation/build_judge_human_calibration_workbook.py`'s `validate_source_completeness()` confirmed all 40 examples' k=3 judge scores (and generated replies) were already present in `evaluation/results/k_ablation_sweep.json`, so zero new LLM API calls were needed for the entire LLM side of Part I — only the human grading itself was new work.
    - *Attribution*: My requirement to reuse already-paid-for API output rather than re-spend; AI verified completeness against the cache and built the workbook from it.

35. **THE CENTRAL FINDING: The K-Ablation's Cleanest Result Is Deliberately Connected to the Judge-Calibration Caveat, Not Reported Separately**
    - *Why we made it*: The k-ablation sweep's cleanest, most statistically clean-looking result is that retrieval significantly raises Groundedness at every k, Holm-Bonferroni corrected (`evaluation/K_ABLATION_SWEEP_RESULTS.md`). The judge-human calibration study (`evaluation/results/judge_human_agreement.json`, n=40, k=3) found no dimension distinguishable from chance-level agreement, and Groundedness specifically has negative weighted kappa (-0.037) with the judge over-scoring relative to the human by +0.275 on average. These two results were deliberately reported as one connected finding, not two unrelated ones: the Groundedness result is a real, correctly-computed statistical finding about the judge's scoring behavior — it is **not independently human-validated**, which is different from being invalid or disproven. The distinction matters and must not be collapsed in either direction.
    - *Attribution*: My requirement that the two results be connected rather than left as separate footnotes a reader would have to link themselves, and that the framing stay precise (unvalidated, not invalid); AI ran both analyses and drafted the connected framing for review.

36. **Judge-Human Calibration Deliberately Scoped to k=3 Only**
    - *Why we made it*: The 40-example judge-human calibration study was pre-specified to run at the k=3 condition only, not all four k-values. The result explicitly does not generalize to k=0/1/5 without a separate calibration pass at those conditions — stated directly in the result file rather than left implicit.
    - *Attribution*: My scoping decision (a smaller, well-defined calibration claim over a larger, unsupported one); AI implemented the scope limitation and its explicit statement in the output.

37. **Part J Computed Both Gold-Intent and LLM-Predicted-Intent Conditions Separately**
    - *Why we made it*: The triage holdout evaluation (`evaluation/run_part_j_triage_eval.py`) computes both an idealized condition (using the gold intent label) and a realistic condition (using Experiment 1's actual LLM-predicted intent) as separate, explicitly labeled arms, since they test different things — idealized rule behavior in isolation vs. the real end-to-end pipeline including classifier error.
    - *Attribution*: My requirement that both be reported rather than only the more flattering one; AI implemented both conditions.

38. **Holm-Bonferroni Correction Applied Across All 12 K-Ablation Comparisons**
    - *Why we made it*: The k-ablation sweep runs 12 non-independent paired Wilcoxon tests (3 treatment k-values x 4 judge dimensions). Rather than report 12 raw p-values as if they were independent evidence, Holm-Bonferroni was applied across the full family to control the family-wise error rate, with both raw and adjusted p-values reported for every comparison — neither hidden.
    - *Attribution*: My requirement for a real multiple-comparisons correction rather than reporting raw p-values; AI implemented the correction and the full reporting table.

39. **A Genuine Clean-Clone Reproducibility Test Found the Documented "Fast/Free" Path Was Actually Broken**
    - *Why we made it*: Working-directory testing is not sufficient evidence that a fresh clone reproduces what's documented. A genuine clean-clone test (cloning the repo into an isolated directory with no cache, no untracked files, no carried-over environment state) found `requirements.txt` was missing 6 of 8 real dependencies (only `pandas`/`openpyxl` were listed), and that the test suite had 38 real failures on a fresh clone — not the 2 originally documented — traced to 2 result files (`evaluation/results/k_ablation_sweep.json`, `evaluation/results/retrieval_inspection_scaffold.csv`) that several fast/free-path scripts depended on but that were gitignored rather than committed. Fixed by adding the missing dependencies and force-committing those two specific files (the same precedent already used for `baseline_results.json`/`llm_classifier_results.json`), then re-verified against a second clean clone (299 passed / 16 failed, all 16 individually explained). Fixed by correcting the actual gaps, not by softening the documentation's claims to match the broken state.
    - *Attribution*: My requirement for an actual clean-clone test rather than trusting working-directory state, and that the fix be a real fix (dependencies + committed artifacts) rather than a rewritten claim; AI ran the clean-clone test, diagnosed the root causes, and implemented the fix.

40. **Prompt-Injection / Untrusted-Input Defenses Are Out of Scope for This Evaluation, Not Solved**
    - *Why this is recorded*: Identified during report preparation, not as a Phase 3 design decision. The evaluation runs only against static historical public tweets, never live adversarial traffic, and `evaluation/generation.py` has no tool or function-calling of any kind — `generate_reply()`/`judge()` call the chat completions API with a fixed `messages` list and a strict JSON-schema `response_format` (`GENERATION_JSON_SCHEMA`, `JUDGE_JSON_SCHEMA`, both `"strict": True`), nothing more. No code anywhere in this repository auto-sends or auto-posts a generated reply to any external system; every generated reply is written to a local result file for human review. These properties (no tools, schema-constrained output, human-in-the-loop) are incidental to this milestone's own design goals, not deliberate prompt-injection mitigations, and must not be described as such. One concrete, unaddressed gap: `GEN_SYSTEM_PREAMBLE` ("You are a customer support agent for Spotify on Twitter.") and the judge's system prompt ("You are an impartial evaluator of customer-support reply quality...") never frame `customer_text` or retrieved historical `brand_text` as untrusted data rather than instructions — an adversarial customer message or a poisoned historical reply is not defended against here. This is a scope limitation to state plainly in the report, not a claim that the risk has been tested, ruled out, or solved; live-deployment-grade prompt-injection defenses were not built and are not evaluated by anything in this repository.
    - *Attribution*: Identified by me during report preparation, not part of the original Phase 3 work; AI verified the absence of tool-calling, auto-send code, and untrusted-data framing against the current source before this entry was written.

41. **Independent External Reproducibility Verification, Beyond the AI-Run Clean-Clone Tests**
    - *Why this is recorded*: Every clean-clone reproducibility test up to this point was AI-initiated and AI-run within this same working session. To get a genuinely independent check, two human-initiated reviews were run against the completed repository: one by a friend on a separate machine (Windows, Python 3.12) using a different AI agent with no access to this project's development history; one self-run (macOS, Python 3.14). Both cloned fresh, followed only what `README.md` documents, and independently re-derived every cited metric — zero discrepancies found in any number. This process itself surfaced one real, previously-uncommitted gap that no prior automated task had flagged: `README.md`/`CHECKLIST.md`/`PROJECT_CONTEXT.md` were still describing the final report as "not yet written" after `report/REPORT.md` had actually been completed and committed. This was caught by manual `git status`/content inspection, not by any script, and fixed in commit `1f4670e`. The two review documents themselves (a friend's `EVALUATION_README.md` and a self-run `evaluation_report.md`) are deliberately not committed to this repository — they are external verification artifacts, not project deliverables.
    - *Attribution*: Initiated and reviewed by me — I arranged both external checks and read their results; AI verified the cited commit hash (`1f4670e`) and cross-checked its actual diff against the claimed fix before this entry was written, rather than taking the description on faith.
