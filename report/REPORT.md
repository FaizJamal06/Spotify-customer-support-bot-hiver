# SpotifyCares Support Agent — Take-Home Report

Brand: **SpotifyCares** (Customer Support on Twitter / TWCS dataset). Full methodology, decision trail, and reproduction instructions live in the repo (`README.md`, `DECISION_LOG.md`, `PROJECT_CONTEXT.md`); this report is the required 6-page summary.

**As-built architecture** (`ARCHITECTURE.md`): the system is two independently-evaluated paths sharing one classification input, not one unified runtime pipeline — deliberately, to avoid orchestration complexity that would add no evaluation value (`DECISION_LOG.md` #14).

- **Path A** — classify → retrieve → generate → judge (`evaluation/run_k_ablation_sweep.py`), evaluated on all 200 golden examples × k∈{0,1,3,5}.
- **Path B** — classify → triage (`evaluation/run_part_j_triage_eval.py`), evaluated on a separate 40-example human triage holdout. Triage never sees retrieved evidence.

---

## 1. Problem Framing

**What "good" means here**: a system that (a) sorts an incoming message into a small, empirically-derived intent taxonomy reliably enough to route it correctly; (b) drafts a reply that is *grounded* — traceable to a real historical resolution, not invented — when it responds directly; and (c) makes a conservative, explainable auto-handle/escalate call, biased toward escalating when uncertain rather than guessing. Critically, "good" also means the evaluation itself has to be trustworthy: an LLM judge that scores reply quality is only useful if it's been checked against a human, and this report treats that check as a first-class result, not an afterthought (see §4).

**What was deliberately not built, and why** (`implementation_plan.md` §15, `DECISION_LOG.md` #14):

- No FAISS/vector database — the retrieval index is 3,000 vectors; brute-force cosine similarity is sufficient and simpler to audit.
- No fine-tuned classifier — no labeled set large enough to justify it; the few-shot LLM approach was tested against classical baselines instead (§2).
- No separate sentiment model or information-extraction stage — a minimal, explicitly-unvalidated anger-keyword heuristic (Tier 3 of triage) stands in, labeled as such rather than dressed up as a real model.
- No cross-encoder reranker — retrieval's actual value had to be proven first (§4 shows why that proof is incomplete).
- No multi-provider LLM abstraction, no Banking77 integration, no web UI, no self-critique/reflection loops — none were needed to answer the assignment's actual questions.
- **No live-deployment-grade prompt-injection defenses** (`DECISION_LOG.md` #40): the evaluation runs only against static historical tweets, never live adversarial traffic, and the generator/judge use no tool-calling and auto-send nothing. This was scoped as an explicit, disclosed limitation — neither ignored nor over-built into an unrequested defense system — with a firm rule that fixing it must not reopen the already-completed, already-paid-for k-ablation or triage experiments. It is a concrete next-step item (§5), not a solved problem.

A confidence-threshold rule for triage was also explicitly tested and rejected rather than built by default: `evaluation/CALIBRATION_RESULTS.md` found the classifier overconfident in every one of 5 quantile buckets (ECE=0.140, Brier=0.166), so no hard confidence cutoff is used anywhere in the shipped triage policy — a deliberate absence, recorded as a rejected hypothesis (`DECISION_LOG.md` #27), not an oversight.

---

## 2. Results vs. Baselines

### Intent classification (three-way comparison, golden-200)

| Classifier | Accuracy | Macro F1 |
|---|---:|---:|
| Majority-class (trivial) | 20.0% | 0.042 |
| TF-IDF + Logistic Regression (simple) | 42.0% | 0.314 |
| LLM few-shot (gpt-5.4-mini) | **81.0%** | **0.808** |

*(`evaluation/BASELINE_RESULTS.md`, `evaluation/LLM_CLASSIFIER_RESULTS.md`.)* Both baselines and the LLM classifier train/prompt from the same 296-example DEVELOPMENT-pool discovery substitution (4 of 300 excluded as unparseable), never golden-200. The LLM classifier's few-shot set is further restricted to 39 audit-confirmed MATCH-status examples, selected deterministically before any golden-200 example was scored. The LLM more than doubles TF-IDF+LogReg's macro F1 — a real, substantial improvement, not a marginal one.

### Confidence calibration

Overconfident in every one of 5 quantile buckets (mean confidence exceeds empirical accuracy everywhere; worst gap +0.276 in the lowest-confidence bucket). ECE=0.140, Brier=0.166. Conclusion: this data does not support a defensible hard confidence threshold for triage (`evaluation/CALIBRATION_RESULTS.md`).

### Retrieval + generation (k-ablation, 800 generate+judge pairs, 0 failures)

| k | Relevance | Groundedness | Helpfulness | Tone |
|---|---:|---:|---:|---:|
| 0 (no retrieval) | 4.825 | 4.295 | 3.815 | **4.985** |
| 1 | 4.360 | 4.730 | 3.515 | 4.565 |
| 3 | 4.700 | 4.910 | 3.950 | 4.795 |
| 5 | 4.690 | **4.940** | 3.940 | 4.860 |

12 pre-specified paired Wilcoxon comparisons (3 treatment k's × 4 dimensions), Holm-Bonferroni corrected: **12/12 significant**. Retrieval significantly *raises* Groundedness and significantly *lowers* Relevance and Tone at every k — a genuine tradeoff, not a clean win (`evaluation/K_ABLATION_SWEEP_RESULTS.md`). See §4 for why the Groundedness result specifically needs a major caveat.

### Triage (Part J, shipped-default policy vs. 40-example human holdout, realistic LLM-predicted-intent condition)

32/40 (80.0%) agreement with the human triage decision; **3/40 dangerous false-auto-handles** (42.9% of the 7 human-ESCALATE cases); 5/40 false-escalates (`evaluation/results/part_j_triage_eval.json`). The one evidence-driven Tier-2 rule (ACCOUNT_ACCESS→escalate) ships **disabled by default**: a follow-up Fisher's exact test against its closest competitor was not significant (p=0.094; 95% CI on the risk difference includes zero), and the finding collapsed from 100% to 0% under one equally-plausible alternate heuristic wording (`evaluation/results/triage_tier2_audit.json`).

### Judge-human calibration (Part I, 40 shared examples, k=3 only)

| Dimension | Exact | Within-1 | Weighted κ | κ 95% CI | Spearman ρ | ρ 95% CI |
|---|---:|---:|---:|---:|---:|---:|
| Relevance | 57.5% | 95.0% | 0.091 | [−0.170, 0.421] | 0.131 | [−0.191, 0.457] |
| **Groundedness** | 72.5% | 95.0% | **−0.037** | [−0.117, 0.000] | **−0.092** | **[−0.192, −0.061]** |
| Helpfulness | 57.5% | 90.0% | 0.223 | [−0.130, 0.556] | 0.292 | [−0.086, 0.613] |
| Tone | 65.0% | 97.5% | 0.234 | [−0.073, 0.522] | 0.255 | [−0.074, 0.562] |

*(`evaluation/results/judge_human_agreement.json`.)* Every dimension's kappa CI spans zero except Groundedness, whose CI sits at-or-below zero on both metrics — the one dimension with the least trustworthy judge-human agreement is exactly the one the headline retrieval result depends on. Full treatment in §4.

---

## 3. Top-5 Failure Analysis

*(Full detail, real examples, and citations: `evaluation/FAILURE_ANALYSIS_DRAFT.md`.)*

**1. The headline Groundedness result is not independently validated against human judgment.** Retrieval's strongest, cleanest-looking win (Groundedness, Holm-corrected across every k) is measured by the one judge dimension with negative kappa and a systematic +0.275 over-scoring bias relative to a human rater. Treated fully in §4.

**2. Judge over-literalism vs. human holistic reading.** CAND_0151: customer asks whether gift cards work for the Family plan; the reply explains gift-card mechanics without using the words "Family plan." The judge scored Relevance/Helpfulness 2/2 ("does not directly answer..."); the human scored both 5/5 (adequately implied). Pattern, not a one-off: the judge clusters at 4–5 while humans use more of the 3–5 range for adequate-but-incomplete answers.

**3. Triage false-auto-handles on calmly-worded, substantive disputes.** CAND_0059 ("need to cancel, can't even log in to the settings page") and CAND_0165 ("charged for premium family but not getting the service") — both human=ESCALATE, system=AUTO_HANDLE, and neither trips any current rule because neither uses charged language. The system's safety net is built around *loud* distress signals; these are quiet, serious ones.

**4. UNKNOWN_OTHER over-triggers false-escalates on benign messages.** Four of eight Arm-A/LLM Part-J disagreements are false-escalates where the classifier landed on UNKNOWN_OTHER for a self-resolved issue ("just needed to restart my phone"), a compliment, a one-word location answer, and a version-number follow-up. This traces to classifier behavior on short, context-dependent continuation messages, not to the triage policy itself, which is doing exactly what it's designed to do.

**5. The ACCOUNT_ACCESS Tier-2 rule's own fragility, as a methodology-level lesson.** The rule looked obviously correct from non-overlapping Wilson confidence intervals — until a proper Fisher's exact test found p=0.094 (not significant), and a robustness check found the finding evaporates (100%→0%) under one equally-reasonable alternate definition of the underlying heuristic. This surfaced only because a second AI's critique of the original statistical reasoning was explicitly required to be evaluated on its technical merits — not trusted by default because it came from the same pipeline, and not dismissed by default because it was a second opinion — which is what led to running the formal test at all. The general lesson: "the CIs don't overlap" is not itself a significance test.

---

## 4. What Is Misleading About My Headline Number?

**The headline number**: *"Retrieval significantly improves Groundedness at every tested k, with all 12 Holm-Bonferroni-corrected paired Wilcoxon comparisons significant."* This is the cleanest, most statistically decisive-looking result in the whole project (`evaluation/K_ABLATION_SWEEP_RESULTS.md`), and it would be an easy, tempting thing to lead a pitch with.

**Why it's misleading if reported alone**: the LLM judge that produced every one of those Groundedness scores has not itself been shown to agree with a human on Groundedness. The Part I calibration study (40 examples, k=3, `evaluation/results/judge_human_agreement.json`) found:

- Weighted Cohen's kappa on Groundedness: **−0.037**, 95% bootstrap CI **[−0.117, 0.000]** — at or below zero, i.e. not distinguishable from chance-level agreement (and the point estimate is negative).
- Spearman's rank correlation on Groundedness: **−0.092**, 95% CI **[−0.192, −0.061]** — entirely below zero. This was computed specifically to check whether the judge might still preserve *rank* agreement with the human even given its calibration bias (a different failure mode than kappa measures: absolute miscalibration vs. relative ordering). It does not. The two independent metrics agree, in the same direction, that there is no signal here.
- A systematic **+0.275** over-scoring bias (judge higher than human, on average) on Groundedness specifically — the largest mean bias of any of the four rubric dimensions.

**What this does and does not mean.** The Groundedness improvement is a real, correctly-computed statistical finding *about the judge's own scoring behavior*: retrieval genuinely, reliably causes the judge to assign higher Groundedness scores, every time, at every k. That part of the claim is solid. What is **not** established is whether that judge behavior tracks actual human perception of groundedness — the one calibration check run on that exact dimension found no reliable agreement, in either the absolute (kappa) or relative (Spearman) sense. The correct, precise description is: **the Groundedness result is real but not independently human-validated** — not "invalid," not "disproven," not "wrong." A negative kappa does not mean retrieval fails to improve grounding; it means this project does not yet have evidence that the *judge's* verdict on grounding matches a *human's*.

**Scope of the caveat**: Part I is valid for k=3 only and does not generalize to k=0/1/5 without a separate calibration pass (`DECISION_LOG.md` #36) — so even the caveat itself should not be over-extended. The other three dimensions (Relevance, Helpfulness, Tone) show weak-but-positive kappa and Spearman with CIs spanning zero — inconclusive, not contradictory, but also not validated.

**The honest one-line version for a pitch**: *"Retrieval measurably changes what the judge rewards — more Groundedness, less Relevance and Tone — but we have not yet confirmed the judge's Groundedness verdict matches a human's, and the one check we ran on that specific dimension found no reliable agreement."*

---

## 5. What I'd Do With One More Week

1. **Frame customer text and retrieved historical replies as untrusted data, not instructions, in the generator/judge system prompts, and add a small adversarial prompt-injection test suite before any live deployment** (`DECISION_LOG.md` #40) — the single concrete, disclosed gap from §1, not yet addressed.
2. **Extend judge-human calibration beyond k=3.** Part I is explicitly scoped to one k value; since the judge's scoring behavior is known to move differently across dimensions as k changes (§4), the Groundedness caveat itself needs checking at k=0/1/5 before the full k-ablation result can be reported without qualification.
3. **Grow the judge-human calibration set past n=40.** Every kappa and Spearman CI this week is wide (roughly 0.3–0.7 points across the range) — not enough data to distinguish "the judge is unreliable" from "we can't tell yet." A larger set, or a second human rater for inter-rater agreement, would sharpen this.
4. **Resolve the ACCOUNT_ACCESS Tier-2 rule's fate with more evidence**, rather than leaving it permanently disabled-but-implemented. p=0.094 is close enough to conventional significance that more golden examples (or a dedicated follow-up sample) could plausibly resolve it either way.
5. **Investigate the UNKNOWN_OTHER false-escalate driver** (failure mode 4): the classifier's uncertainty on short, context-dependent continuation/closure messages is costing triage-queue capacity even though the triage policy itself is behaving correctly.
6. **Design and validate a rule for calmly-worded substantive disputes** (failure mode 3) — the two dangerous false-auto-handles suggest a genuine gap, but any new rule must go through the same significance-test-and-robustness-check discipline that caught the ACCOUNT_ACCESS rule's fragility, not be added on an informal read.
7. **Check the golden-set candidate-sampling scripts into the repo** — a known, disclosed reproducibility gap (`PROJECT_CONTEXT.md` §9): only the outputs are committed, not the interactive scripts that produced them.

---

## 6. Decision Log (14 non-obvious decisions)

Full attribution and reasoning: `DECISION_LOG.md`; this is the presentation-ready excerpt (`golden_set/REPORT_DECISION_LOG.md`), plus one addition (#14 below). Before any Part I work began, an explicit cost-minimization discipline treated triage decisions and response-quality judgments as separate evaluation concerns — concretely, this is why Part I needed its own dedicated human-grading scaffold (`evaluation/build_judge_human_calibration_workbook.py`) rather than reusing Part J's triage annotations, and why that scaffold first checked whether the needed LLM judge scores already existed in the cached k-ablation sweep before doing anything else (item 9 below).

- **Fixed a silent chronology bug** (`created_at` vs. numeric `tweet_id`) by requiring one shared, tested utility instead of a one-off patch, after spot-checking surfaced Snowflake-ID ordering inconsistencies.
- **Locked the 200 gold labels after annotation** and refused to relabel them even after a later agreement analysis surfaced 17 disagreements — a benchmark that keeps moving toward the system's own outputs stops being independent.
- **Deliberately left 3 of 9 proposed guide clarifications unresolved** rather than write a confident-sounding rule over inconsistent or single-case evidence.
- **Built a separate, additive 40-example triage annotation** rather than reopening the frozen golden-200 intent labels or deriving triage ground truth from them.
- **Tested and explicitly rejected a confidence threshold** for triage (§1) rather than silently omitting it — `CONFIDENCE_THRESHOLD_REJECTED` remains an inspectable marker in the code.
- **Locked the DM-redirect triage heuristic before computing any per-intent rate**, specifically to prevent post-hoc tuning to a result.
- **Shipped the ACCOUNT_ACCESS Tier-2 rule disabled by default** after it failed a formal significance test and a robustness check — kept as a documented, disabled toggle rather than shipped uncritically or discarded outright (failure mode 5).
- **Rejected an AI-proposed word-count/chat-noise filter for short retrieval messages** and required the actual corpus be inspected first: the hypothesized pattern (casual chat noise) was wrong — the real short messages were 4 bare `@handle`-only mentions out of 26,914, and the existing simple character threshold was correct as-is without modification.
- **An 8-example pilot caught the generator copying, and once fabricating, a stale agent sign-off code** before the full 800-condition sweep spent any real budget on it.
- **Rejected a naive frequency-based URL-stripping rule** because it would have deleted a real, correct answer (an Indonesian-support-email link recurring 117 times in the corpus, precisely because it's the correct canonical answer) — used a referential-cue rule instead.
- **Checked for already-cached judge scores before running Part I**, confirming all 40 examples' k=3 scores already existed in the k-ablation sweep — zero new LLM API calls were needed for the LLM side of Part I.
- **Connected the k-ablation Groundedness finding to the judge-calibration caveat deliberately**, as one story rather than two unrelated footnotes (§4) — and, on the same question, specifically requested Spearman's rho be computed alongside kappa to test whether rank-agreement might survive despite the calibration bias kappa measures. It didn't: both metrics agree Groundedness shows no signal beyond chance. A negative confirmatory result from a second, independently-reasoned check is itself meaningful evidence, not a wasted step.
- **Applied Holm-Bonferroni correction across all 12 k-ablation comparisons** rather than reporting 12 raw p-values as independent evidence.
- **Scoped prompt-injection defenses as an explicit, disclosed out-of-scope limitation** (§1, §5) rather than either ignoring the question or over-building an unrequested defense — with a firm rule that addressing it later must not reopen the already-completed, already-paid-for k-ablation or triage experiments.
