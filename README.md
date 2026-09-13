# Hiver SDE Take-Home — SpotifyCares Support Agent

An AI customer-support agent built on the [Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter)
(TWCS) dataset, for the **SpotifyCares** brand. Classifies incoming customer
messages into an 8-intent taxonomy, will draft grounded replies from
historical resolutions, and will decide auto-handle vs. escalate.

**Status: golden evaluation set complete; majority-class and TF-IDF+LogReg
baselines complete (trained on the 296-example DEVELOPMENT discovery
substitution, evaluated on the 200 golden TEST examples); LLM classifier and
later milestones not yet started.** See [CHECKLIST.md](CHECKLIST.md) for the
full status table.

## Start here

| Doc | What it's for |
|---|---|
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | Current project state, hard requirements, dataset facts — read this first |
| [DECISION_LOG.md](DECISION_LOG.md) | Why the non-obvious decisions were made, with explicit human-vs-AI-assistance attribution |
| [discovery/TAXONOMY_REVIEW_GUIDE.md](discovery/TAXONOMY_REVIEW_GUIDE.md) | The frozen, authoritative annotation rulebook |
| [CHECKLIST.md](CHECKLIST.md) | What's done vs. not started, against the assignment requirements |
| [REPOSITORY_STRUCTURE.md](REPOSITORY_STRUCTURE.md) | What every file/directory is for |
| [hiver_sde_takehome_strategy.md](hiver_sde_takehome_strategy.md) | Strategic north-star doc (architecture, evaluation philosophy) |

## What's done

- SpotifyCares selected from TWCS; thread-level DEVELOPMENT/RETRIEVAL/TEST split built and leakage-checked (`data/prepare.py`, `data/split.py`).
- 8-intent taxonomy derived empirically from a 300-example discovery review, frozen, and documented in `discovery/TAXONOMY_REVIEW_GUIDE.md`.
- **200-example golden evaluation set complete**: sampled from the sealed TEST pool only, individually QA'd, blindly annotated, AI-prelabeled to speed review, and fully human-labeled. Gold export: [`golden_set/GOLDEN_200_FINAL.csv`](golden_set/GOLDEN_200_FINAL.csv). **These labels are final and immutable** (`DECISION_LOG.md` #17) — not used for training, not inserted into retrieval.
- Post-golden review: an AI-prelabel-vs-human-gold agreement analysis (91.5% exact agreement) was run as a validity check, and the taxonomy was re-confirmed to need exactly 8 intents (no new intent). 7 small guide wording clarifications were approved and applied; 3 were deliberately left open rather than force-resolved on weak evidence. Full detail in `golden_set/GOLDEN_200_ANALYSIS.md` and `golden_set/GUIDE_CHANGELOG_AFTER_GOLD.md`.
- **Intent-classification baselines complete**: majority-class and TF-IDF + Logistic Regression, trained on 296 of the 300 DEVELOPMENT-pool discovery examples (4 excluded as unparseable — Ex 70, 78, 164, 265; see `DECISION_LOG.md` #24), evaluated on the 200 golden TEST examples. Full metrics: [`evaluation/BASELINE_RESULTS.md`](evaluation/BASELINE_RESULTS.md) and `evaluation/results/baseline_results.json`.

## What's NOT done yet (by design, not oversight)

- LLM-based intent classifier, retrieval index, response generation, triage/escalation logic.
- Evaluation harness and LLM-as-judge rubric.
- The final report (problem framing, baseline comparison, failure analysis, "misleading headline number," next steps).

This repo is mid-project. The sections above will be filled in as those
milestones land — this README will be updated to give exact reproduction
commands for the headline results once they exist. Overclaiming "reproducible
in 15 minutes" before that work exists would be misleading, so this section
intentionally stays honest about what's runnable today.

## What you can reproduce today

```bash
pip install -r requirements.txt

# 1. Place the raw Kaggle TWCS CSV at the repo root as twcs.csv (not committed — ~500MB).
# 2. Filter to SpotifyCares and reconstruct threads:
python data/prepare.py

# 3. Build the deterministic 3-way DEVELOPMENT/RETRIEVAL/TEST split (seed=42):
python data/split.py
```

This regenerates `data/generated/*.jsonl` (gitignored — large, derived data).
The golden set itself does **not** need to be regenerated — it's already
committed at `golden_set/GOLDEN_200_FINAL.csv` and is the fixed evaluation
artifact for all future baseline/classifier work.

**Known gap**: the interactive scripts that produced `golden_set/CANDIDATE_MANIFEST_200.csv`,
the annotation workbooks, and `golden_set/ai_prelabels.csv` are not yet
checked into this repo (only their outputs are). See `PROJECT_CONTEXT.md` §9.
This doesn't affect the validity of the golden set — it's already a committed,
fixed artifact — only the ability to regenerate it from scratch.

## Citations / AI assistance

Per the assignment's rules ("You may use AI coding assistants freely... cite
anything you borrowed"): this project was built with Claude Code as a coding
assistant across exploration, scripting, QA checks, and drafting. See
`DECISION_LOG.md` for a detailed accounting of which decisions were mine and
where AI assistance was used, including the AI-assisted prelabeling workflow
used to speed up (not replace) human annotation of the golden set.
