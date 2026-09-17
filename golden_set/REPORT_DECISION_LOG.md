# Curated Decision Log (for the final report)

A condensed selection of the most genuinely non-obvious decisions behind this
project, drawn from `DECISION_LOG.md` (Phase 1/2) and from Phase 3 work
(retrieval, generation, triage, judge calibration) that was designed and
decided through project conversation but never formally logged. Each item
cites the file where it can be independently verified. Full attribution and
reasoning for the Phase 1/2 items live in `DECISION_LOG.md`; this list is a
distilled, presentation-ready version, not a replacement for it.

## Golden-set / taxonomy (Phase 1/2)

- **Fixed a silent chronology bug by requiring one shared, tested utility instead of a one-off patch.** Numeric `tweet_id` comparison turned out to be an invalid ordering proxy (Snowflake ID inconsistencies); discovered by spot-checking, fixed by centralizing chronology in `discovery/chronology.py` with a regression suite, then reusing it everywhere threads needed ordering rather than re-deriving the logic per script. (`DECISION_LOG.md` #8)

- **Locked the 200 gold labels after annotation and refused to relabel, even when a later agreement analysis surfaced 17 disagreements.** A benchmark that keeps getting adjusted toward the system's own outputs stops being an independent benchmark. (`DECISION_LOG.md` #17)

- **Deliberately left 3 of 9 proposed post-golden guide clarifications unresolved** rather than write a confident-sounding rule over inconsistent or single-case evidence (e.g. two near-identical examples that got different gold labels). Recorded as an observed inconsistency instead of false precision. (`DECISION_LOG.md` #23)

## Retrieval / generation / triage (Phase 3)

- **Built a separate, additive 40-example triage annotation** (`golden_set/TRIAGE_ANNOTATION_40.csv`) rather than reopening the frozen intent labels or fabricating triage ground truth — the golden-200 set has intent labels only, no triage decisions. (`evaluation/run_part_j_triage_eval.py`)

- **Tested and rejected a hard confidence threshold for Tier-2 triage.** The classifier is overconfident in every one of 5 quantile buckets (ECE=0.14, Brier=0.166) — not defensible grounds for a cutoff, so triage carries confidence only as an advisory field, never a gate. (`evaluation/CALIBRATION_RESULTS.md`, `evaluation/triage.py` `CONFIDENCE_THRESHOLD_REJECTED`)

- **Locked the DM-redirect heuristic before computing any per-intent escalation rate**, specifically to prevent tuning the rule to fit a result after seeing it. (`evaluation/triage.py`, module docstring)

- **Shipped the ACCOUNT_ACCESS Tier-2 rule disabled by default after it failed a proper significance test.** It looked compelling on an informal non-overlapping-CI read, but a Fisher's exact test against its closest competitor was not significant (p=0.094), and the finding collapsed from 100% to 0% under one plausible alternate heuristic wording. Rather than ship it uncritically or discard the work, it was kept as an explicit, disabled-by-default, documented toggle. (`evaluation/results/triage_tier2_audit.json`, `evaluation/triage.py` `TIER2_ACCOUNT_ACCESS_RULE_ENABLED`)

- **Let direct corpus inspection overturn a plausible-sounding hypothesis about short messages.** Rather than guess that short customer messages were mostly "help/thanks"-style noise, the retrieval-corpus length filter was set only after inspecting the real pool: just 4 of 26,914 pairs were below the threshold, and all four were bare, content-free `@handle` mentions — not terse-but-real reactions, which the filter deliberately leaves untouched. (`evaluation/build_retrieval_index.py`, `filter_short_messages`)

- **An 8-example pilot caught the generator copying, and once fabricating, stale agent sign-off codes and tracking URLs from retrieved evidence before the full 800-condition run spent any real budget on it.** (`evaluation/GENERATION_JUDGE_PILOT_RESULTS.md`, `evaluation/generation.py` Part 1)

- **Rejected a pure-frequency URL-stripping rule because it would have deleted a genuine, correct answer** — a real Indonesian-support-email link that recurs 117 times in the retrieval corpus precisely because it's the correct canonical answer reused across similar requests. Used a referential-cue rule (is the URL introduced by "at"/"via"/"here"/a colon?) instead of raw frequency. (`evaluation/generation.py`, `clean_brand_text`)

- **THE CENTRAL FINDING, deliberately connected rather than reported as two unrelated results:** the k-ablation sweep's cleanest result — retrieval significantly *raises* Groundedness at every k, Holm-Bonferroni corrected across all 12 comparisons — cannot currently be trusted as validated against real human judgment. The judge-human calibration study found no dimension distinguishable from chance agreement at n=40, and Groundedness specifically has *negative* kappa with the judge systematically over-scoring by +0.275. (`evaluation/K_ABLATION_SWEEP_RESULTS.md`, `evaluation/results/judge_human_agreement.json`)

- **Scoped judge-human calibration to k=3 only, as a deliberate pre-specified choice**, and explicitly refused to generalize that result to k=0/1/5 without separate validation. (`evaluation/results/judge_human_agreement.json`, `scope_limitation` field)

- **A genuine clean-clone reproducibility test — not just working-directory testing — found the documented "fast/free" reproduction path actually had 38 test failures on a fresh clone, not the 2 originally believed**, because `requirements.txt` was missing real dependencies and several scripts silently depended on gitignored result files. Fixed by force-committing the specific artifacts those scripts legitimately need, not by weakening the README's claims. (`README.md`, `requirements.txt`)

## Close calls considered but not included

- **Retrieval embeds `customer_text` only, never `customer+reply`**, and the retrieval document unit is customer-brand pairs, not whole threads (`evaluation/retrieval.py`, `evaluation/build_retrieval_index.py`) — solid engineering choices, but narrower/more mechanical than the picks above.
- **Few-shot demonstrations restricted to audit-confirmed MATCH-status examples**, not the full 296-example training set used for the baselines (`evaluation/fewshot_selection.py`) — a real and correct risk distinction (literal exemplars vs. bulk statistical training data), but a smaller decision than the ones selected.
- **Part J computed both gold-intent and LLM-predicted-intent conditions separately** (`evaluation/run_part_j_triage_eval.py`) — methodologically sound but a natural consequence of wanting both an idealized and a realistic read, not itself a surprising call.
- **TEST pool (not DEVELOPMENT) as the golden-set source**, and **retrieval evidence restricted to the RETRIEVAL pool only** (`DECISION_LOG.md` #16, #18) — important leakage-discipline decisions, but follow directly from the three-way split already covered by the chronology-bug pick's surrounding context.
- **The AI-prelabeling workflow / `Human Final Label` column question** (`DECISION_LOG.md` #21) — a genuinely interesting attribution story, but more about process/attribution than about evaluation methodology, so it was left out in favor of items more defensible as *evaluation design* decisions.
