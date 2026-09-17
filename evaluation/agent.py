"""
Single orchestration entry point wiring together the four already-built,
already-evaluated components into one call, for a single incoming customer
message: classify, then -- independently, exactly as each was evaluated --
classify->triage (evaluation/run_part_j_triage_eval.py's path) and
classify->retrieve->generate (evaluation/run_k_ablation_sweep.py's path).
Per ARCHITECTURE.md, there is no hidden classify->retrieve->generate->triage
chain: triage's output does not feed into retrieval or generation, and
generation does not see the triage decision, matching every evaluated call
site exactly. Both paths' outputs are combined only in the dict this
function returns to its caller. This module contains ZERO new model logic,
ZERO new retrieval logic, and ZERO new triage rules -- it only calls the
existing functions in evaluation/llm_classifier.py, evaluation/triage.py,
evaluation/retrieval.py, and evaluation/generation.py exactly as they
already exist.

This does NOT re-run, re-evaluate, or change the conclusions of any
completed experiment (k-ablation, Part I, Part J, the calibration study).
Those experiments evaluated each component (or component-pair) independently
against frozen golden data, with their own scripts and their own committed
results -- none of that is touched here. This module exists only to
demonstrate that the pieces are wireable into one call for a single live
message; it is not itself a new evaluation.

Calling handle_message() makes REAL API calls (classification and generation
both call the LLM). Do not call it at import time or inside a test -- tests
in test_agent.py inject a mocked provider instead.

=== Default k = 3 ===
The k-ablation sweep (evaluation/K_ABLATION_SWEEP_RESULTS.md) found k=3 has
this project's best per-k Helpfulness score (3.950, the highest of all four
k values including k=0's 3.815) and near-best Groundedness (4.910, vs. k=5's
4.940 -- a negligible difference for double the retrieved context and cost).
k=3 is also the ONLY k value the judge-human calibration study (Part I) ever
actually graded -- it is the single condition with any human-agreement
evidence behind it at all, weak as that evidence is
(evaluation/results/judge_human_agreement.json). k=0 and k=5 remain
available via the `k` parameter; DEFAULT_K is a default, not a hard-coded
requirement.

=== Triage configuration ===
Calls evaluation/triage.py's apply_triage_rules() exactly as shipped.
TIER2_ACCOUNT_ACCESS_RULE_ENABLED stays at its module-level default (False)
-- this module does not read, set, or override that flag. A caller who wants
the disabled experimental rule can monkeypatch evaluation.triage's module
state themselves, exactly as evaluation/run_part_j_triage_eval.py already
does for its Arm B condition; this file does not do that on anyone's behalf.
"""
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.fewshot_selection import select_fewshot_demonstrations
from evaluation.llm_classifier import load_intent_definitions, render_fewshot_block
from evaluation.generation import ExperimentLLMProvider
from evaluation.retrieval import retrieve_top_k
from evaluation.triage import apply_triage_rules

DEFAULT_K = 3  # see module docstring for the evidence behind this default


@lru_cache(maxsize=1)
def _fixed_classifier_inputs():
    """The few-shot block and intent-definitions block every classify() call uses,
    computed once and reused. Identical inputs to what evaluation/run_llm_classifier.py
    builds before scoring the golden 200 -- not re-derived, re-selected, or altered
    here. Cached because both are pure file reads/parses (no API calls) that would
    otherwise be redone on every handle_message() call."""
    demonstrations, _selection_log = select_fewshot_demonstrations()
    fewshot_block = render_fewshot_block(demonstrations)
    intent_definitions = load_intent_definitions()
    return fewshot_block, intent_definitions


def build_default_provider():
    """One ExperimentLLMProvider (evaluation/generation.py) -- inherits .classify()
    unchanged from LLMProvider (evaluation/llm_classifier.py) and implements
    .generate_reply()/.judge(). Same three models this project uses everywhere else
    (config.py) -- not reconfigured or overridden here."""
    return ExperimentLLMProvider(
        classify_model=config.CLASSIFY_MODEL,
        generate_model=config.GENERATE_MODEL,
        judge_model=config.JUDGE_MODEL,
        api_key=config.get_api_key(),
    )


def handle_message(customer_text, k=DEFAULT_K, provider=None):
    """
    Runs one customer message through the full wired pipeline and returns a
    single combined dict:

        {
            "customer_text": str,
            "intent": str,
            "confidence": float,
            "classifier_reasoning": str,
            "triage_decision": "AUTO_HANDLE" | "HUMAN_ESCALATION",
            "triage_reason": str,
            "triage_tier": "TIER_1" | "TIER_2" | "TIER_3" | "NONE",
            "retrieved_evidence": [{"customer_text": str, "brand_text": str,
                                     "similarity": float}, ...],  # [] if k=0
            "generated_reply": str,
            "grounding_notes": {"grounded_in_evidence": [...],
                                 "grounded_in_customer_message": [...],
                                 "unsupported_or_generic": [...]},
        }

    Order of operations (matches how a real incoming message would actually
    flow through this project's separately-evaluated components):
      1. classify() -- evaluation/llm_classifier.py's LLMProvider.classify(),
         inherited unchanged by ExperimentLLMProvider.
      2. apply_triage_rules() -- evaluation/triage.py, called exactly as
         shipped, using the classified intent and confidence from step 1.
      3. retrieve_top_k() -- evaluation/retrieval.py, k=`k` (default 3, see
         module docstring for why).
      4. generate_reply() -- evaluation/generation.py's ExperimentLLMProvider,
         given the retrieved evidence from step 3. The triage_decision
         parameter is passed as `None`, exactly as every evaluated call site
         passes it (evaluation/run_k_ablation_sweep.py:110-112 calls
         `provider.generate_reply(customer_text, classified_intent, None,
         retrieved)` -- literal `None`, not a placeholder). Retrieval/
         generation and triage are two separately-evaluated paths
         (ARCHITECTURE.md: "no hidden classify->retrieve->generate->triage
         chain") that share only the classified intent as input -- this
         function preserves that separation internally and only combines
         both paths' outputs at the point of returning a single result to
         the caller, not by feeding one path's output into the other's
         untested code path.

    A generated reply is always produced regardless of the triage decision
    (including HUMAN_ESCALATION) -- this function demonstrates the full
    wiring and always returns all four required outputs together, per this
    task's spec. A real production system might skip or downgrade generation
    on escalation; that policy choice is out of scope for this wrapper.

    Makes real API calls (classify + generate) unless `provider` is a
    pre-built/mocked object supplied by the caller (see test_agent.py).
    """
    if provider is None:
        provider = build_default_provider()

    fewshot_block, intent_definitions = _fixed_classifier_inputs()

    classification = provider.classify(customer_text, fewshot_block, intent_definitions)
    intent = classification["intent"]
    confidence = classification["confidence"]

    triage = apply_triage_rules(customer_text, intent, confidence=confidence)

    retrieved_pairs = retrieve_top_k(customer_text, k)
    retrieved_evidence = [
        dict(customer_text=cust, brand_text=brand, similarity=sim)
        for cust, brand, sim, _meta in retrieved_pairs
    ]

    generation = provider.generate_reply(
        customer_text, intent, None, retrieved_pairs,
    )

    return dict(
        customer_text=customer_text,
        intent=intent,
        confidence=confidence,
        classifier_reasoning=classification["reasoning"],
        triage_decision=triage["decision"],
        triage_reason=triage["reason"],
        triage_tier=triage["tier"],
        retrieved_evidence=retrieved_evidence,
        generated_reply=generation["reply"],
        grounding_notes=generation["grounding_notes"],
    )
