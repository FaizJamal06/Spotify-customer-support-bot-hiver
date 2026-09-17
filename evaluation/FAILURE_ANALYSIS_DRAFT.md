# Failure Analysis Draft (top 5, for the final report)

Draft for Faiz to edit into the report. Clear, not necessarily polished. Every
example below is a real record pulled from the cited result file — none are
hypothetical.

---

## 1. The central failure mode: the headline retrieval result is not validated against human judgment

**Name:** Unvalidated judge, unvalidated headline.

**What the numbers say, read separately:** The k-ablation sweep's cleanest, most
statistically clean-looking result is that retrieval significantly *raises*
Groundedness at every k (k=1/3/5), Holm-Bonferroni corrected across all 12
paired-comparison tests (`evaluation/K_ABLATION_SWEEP_RESULTS.md`: mean
Groundedness 4.295 at k=0 vs. 4.730/4.910/4.940 at k=1/3/5, all p<0.000001 after
correction). Read on its own, this looks like the strongest, most defensible
finding in the whole project — the kind of result someone would want to put in
a headline slide.

**Why it can't be reported that way:** The judge-human calibration study
(`evaluation/results/judge_human_agreement.json`, n=40, k=3 only) directly
undermines it. Groundedness is the *one* dimension where the judge and a human
rater actively diverge in a systematic direction: weighted Cohen's kappa =
**-0.037** (negative — worse than chance-level agreement), and the judge
over-scores relative to the human by a mean of **+0.275** points
(`mean_signed_diff_human_minus_llm: -0.275`). Its 95% bootstrap CI for kappa is
[-0.117, 0.000] — entirely at or below zero. Every other dimension also shows
weak agreement (Relevance kappa 0.09, Helpfulness 0.22, Tone 0.23, all with CIs
crossing zero), but Groundedness is the dimension the headline result actually
depends on, and it's the worst-agreeing one, in the wrong direction (judge
higher than human, not lower).

**The connected story:** The project's strongest-looking quantitative result
(retrieval → higher Groundedness) is measured by exactly the judge dimension
that shows the least trustworthy — and directionally biased — agreement with
a human rater. This isn't two unrelated findings; it's one finding undercutting
the other. The honest headline is not "retrieval improves Groundedness," it's
"the judge says retrieval improves Groundedness, and we have direct evidence
the judge over-scores Groundedness specifically, so this cannot yet be reported
as a validated result."

**Hypothesis for why it happens:** The judge is instructed to check whether
"every specific factual claim is traceable to the evidence or the customer's
message" (`evaluation/generation.py`, `DEFAULT_JUDGE_RUBRIC`). With retrieved
evidence physically present in its context window, the judge may be
pattern-matching "evidence was shown and reply resembles it" as sufficient
grounding, rather than verifying each specific claim against that evidence the
way a human reads more skeptically/holistically.

**Citations:** `evaluation/K_ABLATION_SWEEP_RESULTS.md`, `evaluation/results/judge_human_agreement.json`

---

## 2. Judge over-literalism vs. human holistic reading

**Name:** Judge penalizes implicit-but-adequate answers.

**Real example — CAND_0151** (`evaluation/results/judge_human_agreement.json`,
`large_disagreements`): customer asks "If i buy spotify gift cards, does it
work for the family plan?" The generated reply explains gift cards give
Premium access for the card's value and links to more info, but never
explicitly says the word "family plan." The judge scored **Relevance=2,
Helpfulness=2** — reasoning that the reply "does not directly answer the
customer's specific question about whether Spotify gift cards work for the
Family plan." The human rater scored both dimensions **5/5**, treating the
answer as adequately implied (a gift card that funds Premium time functions
the same way regardless of plan type, and nothing in the reply excludes Family
plan).

**Broader pattern:** Across the same file's per-dimension confusion matrices,
the judge clusters heavily at 4-5 (e.g. Relevance: 20 of 40 examples are
human=5/llm=5, but the judge drops to 2-4 on several examples humans rated 4-5)
while the human rater is more willing to use the middle of the 1-5 range when a
reply is *adequate but incomplete* rather than penalizing it as if it were
wrong.

**Hypothesis:** The judge appears to require an explicit, literal statement
that resolves the customer's exact phrasing, while the human rater accepts a
correct implication as a full answer — a classic over-literal-grader vs.
holistic-reader gap.

**Citation:** `evaluation/results/judge_human_agreement.json` (`large_disagreements`, CAND_0151)

---

## 3. Triage false-auto-handles on calm, substantive disputes

**Name:** Politeness is not a safety signal, and the system relies on it anyway.

**Real examples — Part J, Arm A (shipped default), LLM-predicted intent**
(`evaluation/results/part_j_triage_eval.json`, `conditions.ArmA_llm.summary.disagreements`):

- **CAND_0059**: "serious question, I need to cancel a prime account but I
  can't login at all because my Facebook associated with it is gone. How can I
  cancel if I can't even log in to the setting or account page?" — human
  decision: **HUMAN_ESCALATION** ("no access to account"). System decision:
  **AUTO_HANDLE** — no Tier-1/2/3 rule fired (classified ACCOUNT_ACCESS,
  no security/legal/anger keyword present).
- **CAND_0165**: "I've been charged for premium family but am not getting it
  on my app; already tried updating app and logging out/back in" — human
  decision: **HUMAN_ESCALATION** ("customer is being charged but not getting
  the service"). System decision: **AUTO_HANDLE**, again with no rule firing.

Both are genuinely dangerous misses (a customer stuck paying for a service they
can't access, and a customer who cannot even reach account settings to cancel)
stated calmly, without any keyword the system's safety net is built to catch.

**Hypothesis:** The current safety net (Tier 1: UNKNOWN_OTHER / security
language / legal language; Tier 3: anger keywords) is built entirely around
*loud* or *lexically flagged* distress. These two cases are quietly stated,
substantively serious disputes — "charged but not receiving service" and
"locked out with no recovery path" are exactly the situations where a wrong
auto-handled reply causes real harm, but neither trips any existing rule
because neither uses charged language.

**Citation:** `evaluation/results/part_j_triage_eval.json`

---

## 4. Tier-1 UNKNOWN_OTHER over-triggers false-escalates on benign messages

**Name:** The safety net's most aggressive rule is also its noisiest.

**Real examples — Part J, Arm A, LLM-predicted intent**
(`evaluation/results/part_j_triage_eval.json`, same disagreements list): four of
the eight total Arm-A/LLM disagreements are false-escalates driven by the
classifier landing on UNKNOWN_OTHER for messages a human immediately reads as
benign:

- **CAND_0071**: "I'm stupid and I just needed to restart my phone, spotify is
  working fine now." (self-resolved, no action needed) — human: AUTO_HANDLE;
  system: HUMAN_ESCALATION (TIER1_UNKNOWN_INTENT).
- **CAND_0072**: "Haha, thank you for being here for your users!" (a
  compliment) — same outcome.
- **CAND_0080**: "Germany i guess" (a one-word answer to what was presumably a
  clarifying question) — same outcome.
- **CAND_0088**: "Thanks! Windows 10 Pro version 1703. Spotify
  1.0.66.478.g1296534d" (a follow-up detail, not a new request) — same
  outcome.

**Hypothesis:** This traces to classifier behavior, not the triage policy
itself — Tier 1's UNKNOWN_OTHER rule is doing exactly what it's designed to do
(escalate on uncertainty). The actual problem is upstream: these four messages
are short, context-dependent follow-ups or closures that the intent classifier
apparently cannot confidently place into any of the 8 substantive categories,
so they fall into the safe-but-costly catch-all. Every one of these
false-escalates represents wasted human-queue capacity, and the pattern
suggests the classifier specifically struggles with short continuation/closure
messages that only make sense in thread context.

**Citation:** `evaluation/results/part_j_triage_eval.json`

---

## 5. The ACCOUNT_ACCESS Tier-2 rule's own fragility as a methodology-level failure mode

**Name:** Informal statistical reasoning nearly shipped a fragile rule.

**What happened:** The ACCOUNT_ACCESS Tier-2B escalation rule initially looked
statistically compelling on an informal read — its Wilson 95% CI for
DM-redirect rate (100%, CI [0.862, 1.000], n=24 golden examples) did not
overlap any other intent's CI, including its closest competitor
SUBSCRIPTION_BILLING (85.7%, CI [0.654, 0.950]). That non-overlap is the kind
of evidence that's easy to treat as "clearly significant" without a formal
test.

**The failure it reveals, once tested properly**
(`evaluation/results/triage_tier2_audit.json`): a Fisher's exact test between
ACCOUNT_ACCESS and SUBSCRIPTION_BILLING was **not significant** (p=0.094; risk
difference 95% CI [-0.024, 0.346], includes zero) — the "non-overlapping CIs"
read does not survive a proper two-proportion test against the closest rival.
Worse, the finding was shown to be **sensitive to how the rule itself is
defined**: an equally-plausible alternate reading of the DM-redirect trigger
(an "inbox"-only variant, `triage_tier2_audit.json`'s `variant_a`) collapses
ACCOUNT_ACCESS's rate from 100% to **0%** and its rank from 1st to 4th among
the 8 intents.

**Why this belongs in the failure analysis, not just the decision log:** this
isn't a system behavior bug — it's a methodology-level warning. A rule that
looked obviously correct from non-overlapping confidence intervals failed both
a formal significance test and a robustness check against one reasonable
alternative wording. It was caught before shipping only because a follow-up
audit was explicitly run rather than trusting the informal read
(`evaluation/triage.py`'s `TIER2_ACCOUNT_ACCESS_RULE_ENABLED = False`,
disabled by default as a direct result). The general lesson: "the confidence
intervals don't overlap" is not, by itself, a significance test, and a rule's
apparent strength can be an artifact of one specific way of operationalizing
the underlying heuristic.

**Citation:** `evaluation/results/triage_tier2_audit.json`, `evaluation/triage.py`
