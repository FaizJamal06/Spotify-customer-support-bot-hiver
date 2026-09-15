"""
Response generator + minimal LLM judge for Experiment 3 (retrieval k-ablation,
implementation_plan.md §9). Implements the .generate_reply() and .judge() methods
of the LLMProvider interface specified in §10.

evaluation/llm_classifier.py is FROZEN (a previously-completed module) and is not
modified by this file. Its LLMProvider class already ships .classify() (implemented)
and .generate_reply() / .judge() (NotImplementedError stubs). Rather than editing that
file, ExperimentLLMProvider below SUBCLASSES it: .classify() and the DiskCache /
OpenAI-client plumbing from __init__ are inherited unchanged; .generate_reply() and
.judge() are overridden here with real implementations that follow the exact same
pattern already established there (cache key = hash of the full request payload,
strict JSON-schema response_format, defense-in-depth validate_*_output()).

Data-access discipline (implementation_plan.md §3, Experiment 3):
  - generate_reply() sees: customer text, classified intent, retrieved pairs.
  - judge() sees: customer text, the generated reply, the SAME retrieved evidence
    that was given to generate_reply() (so it can independently check grounding).
  - Neither ever sees, nor accepts as a parameter, the gold SpotifyCares response,
    the gold intent label, or the gold triage label. See strip_gold_fields() below,
    used by the pilot/eval scripts to build inputs from golden_set/GOLDEN_200_FINAL.csv
    without ever reading its human_gold_label / human_notes columns into memory as
    part of the generation/judging path.

Model verification (2026-09-14, see config.py and DECISION_LOG.md): GENERATE_MODEL
and JUDGE_MODEL are deliberately different models (config.GENERATE_MODEL = "gpt-5.6-terra",
config.JUDGE_MODEL = "gpt-5.6-sol") to reduce self-preference bias in judging, per §10.
Both require reasoning_effort=config.REASONING_EFFORT_FOR_TEMPERATURE ("none") to accept
temperature=0 / seed at all -- empirically verified against the live API, same pattern
already used for CLASSIFY_MODEL.
"""
import json
import re
import sys
import threading
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.llm_classifier import LLMProvider

GENERATOR_PROMPT_VERSION = "v2"  # v1 -> v2: evidence cleaning added (see clean_brand_text below);
                                  # bumping the version deliberately invalidates old cache entries
                                  # so the k>0 pilot re-runs against the API rather than serving
                                  # stale pre-fix cached responses.
JUDGE_PROMPT_VERSION = "v2"

# ============================================================
# Part 1: evidence-cleaning (stale presentation-artifact removal)
# ============================================================
#
# Problem (found in the pilot -- evaluation/GENERATION_JUDGE_PILOT_RESULTS.md,
# tweet_id=44426, k=1/3/5): retrieved historical brand_text replies end with a
# trailing "signature block" appended by the social-support tooling of the era
# (confirmed empirically: 156 distinct 2-3 letter codes like "/GU", "/CH", "/DR",
# each preceded by a "/", present at or near the very end of ~72% of the 3,000
# indexed brand_text messages -- see the frequency scan run during investigation).
# The generator was observed COPYING these codes verbatim into a brand-new reply
# for an unrelated customer, and at k=5 for tweet_id=44426 it went further and
# FABRICATED a code ("/SP") that does not appear in any of that example's 5
# retrieved pairs -- i.e. the pattern is imitated even when not present, which
# means it is being read as "this is how a reply ends" rather than as evidence.
# A trailing t.co URL glued directly to a sign-off with no informative context is
# the same phenomenon: many such URLs are a content-free per-platform "click here"
# tracking link reused verbatim across hundreds of unrelated cases (frequency scan
# of the 3,000-pair index: the single URL "https://t.co/ldFdZRiNAt" appears 722
# times, always attached to a content-free "we'll take a look backstage" tail).
#
# What must NOT be removed: a t.co URL that the reply text actually refers to as a
# specific resource -- e.g. "...Indonesian support via email at https://t.co/...",
# "...info about Spotify content here: https://t.co/...", "...steps under 'X' at
# https://t.co/...". Frequency alone does not distinguish these two cases (the
# genuinely substantive content-info URL above recurs 117 times in the same 3,000-
# pair sample, because it is the correct canonical answer reused across many
# similar requests -- stripping by raw frequency would have deleted it, which was
# checked and rejected). The reliable, data-grounded signal instead is whether the
# URL is *referenced* by the preceding text (a colon, or "at"/"here"/"via"/"under"/
# "through" immediately before it) versus merely *appended* after a complete,
# self-contained sentence with no linking word.
#
# clean_brand_text() therefore does exactly two things, and only at the trailing
# end of the message (never touching customer_text, never touching the stored
# retrieval index, never touching mid-message content):
#   1. Strip a trailing agent sign-off token ("/" + 2-3 uppercase letters).
#   2. Strip a trailing t.co URL ONLY if it is NOT introduced by a referential cue
#      immediately before it. A cued URL stops the trim entirely (nothing further
#      upstream is touched), since that is exactly the "substantive evidence" case
#      the task requires be preserved.
# The loop alternates because sign-off and URL can appear in either order at the
# tail ("...backstage /GU https://t.co/..." vs "...at https://t.co/... /NQ").

_SIGNOFF_TAIL_RE = re.compile(r"\s*/[A-Z]{2,3}\s*$")
_URL_TAIL_RE = re.compile(r"\s*https?://t\.co/\S+\s*$")
_URL_CONTEXT_CUE_RE = re.compile(r"(:|\bat\b|\bhere\b|\bvia\b|\bunder\b|\bthrough\b)\s*$", re.IGNORECASE)


def clean_brand_text(text):
    """Removes trailing presentation artifacts (agent sign-off codes, uncued tracking
    URLs) from one retrieved historical brand_text reply. See the module-level comment
    above for the full rationale and the specific pilot case this addresses.

    Deterministic, narrow (trailing end only), and reversible-by-design: if trimming
    would ever reduce the text to nothing, the ORIGINAL text is returned untouched
    instead (an empty evidence line is worse than an unstripped artifact -- "minimum
    defensible treatment", not aggressive sanitization).

    Returns (cleaned_text, removed) where removed is a list of
    {"kind": "agent_signoff" | "uncued_trailing_url", "value": str} dicts, in the
    order they were stripped, for audit purposes -- removed == [] means the text was
    left exactly as retrieved.
    """
    cleaned = text
    removed = []
    while True:
        m_signoff = _SIGNOFF_TAIL_RE.search(cleaned)
        if m_signoff:
            removed.append(dict(kind="agent_signoff", value=m_signoff.group().strip()))
            cleaned = cleaned[:m_signoff.start()]
            continue

        m_url = _URL_TAIL_RE.search(cleaned)
        if m_url:
            preceding = cleaned[:m_url.start()]
            if _URL_CONTEXT_CUE_RE.search(preceding):
                break  # referenced/substantive URL -- stop trimming, preserve as-is
            removed.append(dict(kind="uncued_trailing_url", value=m_url.group().strip()))
            cleaned = cleaned[:m_url.start()]
            continue

        break

    cleaned = cleaned.strip()
    if not cleaned:
        return text, []  # never emit an empty evidence line
    return cleaned, removed


def build_evidence_records(retrieved_pairs):
    """retrieved_pairs: evaluation.retrieval.retrieve_top_k() output as-is -- a list of
    (customer_text, brand_text, similarity, metadata) tuples ([] for k=0). Applies
    clean_brand_text() to each brand_text and returns a list of dicts carrying BOTH the
    raw and the shown (cleaned) text, so callers can audit exactly what was removed:

      {customer_text, brand_text_raw, brand_text_shown, removed_artifacts, similarity, metadata}

    This is the single place cleaning happens; both the prompt-formatting path
    (_render_evidence_block, used by generate_reply()/judge()) and the full-sweep
    audit-record builder (evaluation/run_k_ablation_sweep.py) call this same function,
    so "what was shown" and "what was audited" can never drift apart.
    """
    records = []
    for cust, brand, sim, meta in retrieved_pairs:
        shown, removed = clean_brand_text(brand)
        records.append(dict(
            customer_text=cust, brand_text_raw=brand, brand_text_shown=shown,
            removed_artifacts=removed, similarity=sim, metadata=meta,
        ))
    return records

GEN_SYSTEM_PREAMBLE = "You are a customer support agent for Spotify on Twitter."

GEN_INSTRUCTIONS_GROUNDING_NOTES = (
    "Also produce grounding_notes, a structured breakdown of every substantive claim "
    "in your reply. Put each claim under exactly one of:\n"
    "- grounded_in_evidence: claims directly supported by one of the historical examples "
    "above (following the same suggested action, process, or stated fact)\n"
    "- grounded_in_customer_message: claims that restate or directly follow from what the "
    "customer themselves said\n"
    "- unsupported_or_generic: anything else -- generic troubleshooting suggestions, offers "
    "to help, or any claim not tied to a specific fact from the evidence or the customer's "
    "message. This list should ideally be short; it is not itself an error, but it flags "
    "exactly what in the reply is not directly traceable to evidence."
)

GEN_USER_TEMPLATE_K0 = """CUSTOMER MESSAGE: {customer_text}
CLASSIFIED INTENT: {intent}

Draft a helpful, friendly reply under 280 characters.
If you cannot resolve the issue directly, suggest the customer send a DM for private assistance.
Do not fabricate specific URLs or troubleshooting steps -- no historical evidence was retrieved \
for this query, so any suggested next step must stay generic (e.g. "try reinstalling the app" is \
fine; a specific version number, a specific URL, or a claim that a fix already exists is not).
Never state or imply that this issue, or a similar one, has already been resolved, fixed, or \
looked into -- you have no evidence that it has.

{grounding_instructions}"""

GEN_USER_TEMPLATE_KGT0 = """CUSTOMER MESSAGE: {customer_text}
CLASSIFIED INTENT: {intent}

SIMILAR PAST CONVERSATIONS (how Spotify support has handled similar issues):
{evidence_block}

Draft a reply consistent with how Spotify support historically responds.
Use the examples above as evidence for your response style and content.
Keep it under 280 characters.
Do not fabricate information not supported by the historical examples or the customer's own message.
Each historical example shows only a single customer message and a single support reply -- you do \
not know whether that customer's issue was ultimately resolved. Never describe a past case, or this \
one, as "resolved," "fixed," or "solved" unless the support reply text itself says so explicitly.

{grounding_instructions}"""

GENERATION_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "generation_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "reply": {"type": "string"},
                "grounding_notes": {
                    "type": "object",
                    "properties": {
                        "grounded_in_evidence": {"type": "array", "items": {"type": "string"}},
                        "grounded_in_customer_message": {"type": "array", "items": {"type": "string"}},
                        "unsupported_or_generic": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "grounded_in_evidence", "grounded_in_customer_message", "unsupported_or_generic",
                    ],
                    "additionalProperties": False,
                },
            },
            "required": ["reply", "grounding_notes"],
            "additionalProperties": False,
        },
    },
}

GROUNDING_NOTES_KEYS = (
    "grounded_in_evidence", "grounded_in_customer_message", "unsupported_or_generic",
)


def validate_generation_output(obj):
    """Defense-in-depth schema validation for generate_reply() output. Raises ValueError
    on any violation; returns obj unchanged on success."""
    if not isinstance(obj, dict):
        raise ValueError(f"Generation output is not a dict: {type(obj)}")
    for key in ("reply", "grounding_notes"):
        if key not in obj:
            raise ValueError(f"Generation output missing required key: {key!r}")
    if not isinstance(obj["reply"], str) or not obj["reply"].strip():
        raise ValueError("Generation output 'reply' must be a non-empty string")

    notes = obj["grounding_notes"]
    if not isinstance(notes, dict):
        raise ValueError(f"grounding_notes must be a dict, got {type(notes)}")
    for key in GROUNDING_NOTES_KEYS:
        if key not in notes:
            raise ValueError(f"grounding_notes missing required key: {key!r}")
        if not isinstance(notes[key], list) or not all(isinstance(x, str) for x in notes[key]):
            raise ValueError(f"grounding_notes[{key!r}] must be a list of strings")
    return obj


DEFAULT_JUDGE_RUBRIC = """Score the generated reply on each dimension from 1 (worst) to 5 (best):

RELEVANCE: Does the reply directly address what the customer actually said or asked?
  1 = ignores or misunderstands the customer's message; 5 = squarely on-topic and specific to their issue.

GROUNDEDNESS: Is every specific factual claim in the reply (a stated cause, a specific step, a URL, a \
claim about policy, a reference to a prior case) actually supported by the retrieved evidence or by the \
customer's own message, with nothing fabricated?
  1 = invents specifics with no support; 5 = every specific claim is traceable to the evidence or the \
customer's message. A generic, non-specific reply (e.g. "please DM us" or "try restarting the app") that \
makes no unsupported specific claims should score in the middle-to-high range, not be penalized as if it \
had fabricated something.

HELPFULNESS: Would this reply meaningfully move the customer's issue forward -- a concrete next step, \
real information, or a clear acknowledgment plus escalation path?
  1 = useless or evasive; 5 = clearly moves the issue forward given the constraints of a short public reply.

TONE: Is the reply friendly, professional, and appropriate for a brand's public Twitter support account?
  1 = rude, robotic, or inappropriate; 5 = warm and on-brand.

You will be given the customer's message, the generated reply, and (if any) the historical support \
examples the reply-writer was allowed to draw on. You will NOT be given -- and must not assume -- any \
information about what actually happened in this customer's case, the "correct" answer, or any internal \
label. Judge only from what is shown to you below."""

JUDGE_USER_TEMPLATE = """CUSTOMER MESSAGE: {customer_text}

GENERATED REPLY: {generated_reply}

RETRIEVED HISTORICAL EVIDENCE AVAILABLE TO THE REPLY-WRITER:
{evidence_section}

Score the GENERATED REPLY on relevance, groundedness, helpfulness, and tone as defined above, and give \
a brief reasoning."""

JUDGE_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "judge_output",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "relevance": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                "groundedness": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                "helpfulness": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                "tone": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                "reasoning": {"type": "string"},
            },
            "required": ["relevance", "groundedness", "helpfulness", "tone", "reasoning"],
            "additionalProperties": False,
        },
    },
}

JUDGE_SCORE_KEYS = ("relevance", "groundedness", "helpfulness", "tone")


def validate_judge_output(obj):
    """Defense-in-depth schema + score-range validation for judge() output. Raises
    ValueError on any violation; returns obj unchanged on success."""
    if not isinstance(obj, dict):
        raise ValueError(f"Judge output is not a dict: {type(obj)}")
    for key in (*JUDGE_SCORE_KEYS, "reasoning"):
        if key not in obj:
            raise ValueError(f"Judge output missing required key: {key!r}")
    for key in JUDGE_SCORE_KEYS:
        value = obj[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Judge output {key!r} must be an int, got {type(value)}")
        if value < 1 or value > 5:
            raise ValueError(f"Judge output {key!r}={value} out of range 1-5")
    if not isinstance(obj["reasoning"], str):
        raise ValueError(f"Judge output 'reasoning' must be a string, got {type(obj['reasoning'])}")
    return obj


def _render_evidence_block(retrieved_pairs):
    """retrieved_pairs is exactly what evaluation.retrieval.retrieve_top_k() returns:
    a list of (customer_text, brand_text, similarity_score, metadata) tuples. Returns
    None for an empty list (k=0), so callers can distinguish "no evidence" from "".

    brand_text is passed through clean_brand_text() (via build_evidence_records()) before
    being rendered -- this is the "presentation boundary" where stale sign-off/tracking-
    URL artifacts are stripped before the generator/judge ever sees them. customer_text
    is never touched.
    """
    if not retrieved_pairs:
        return None
    records = build_evidence_records(retrieved_pairs)
    lines = []
    for i, r in enumerate(records, start=1):
        lines.append(f"Example {i}:\n  Customer: {r['customer_text']}\n  Spotify support: {r['brand_text_shown']}")
    return "\n\n".join(lines)


def _build_generate_messages(customer_text, intent, retrieved_pairs):
    evidence_block = _render_evidence_block(retrieved_pairs)
    if evidence_block is None:
        user_prompt = GEN_USER_TEMPLATE_K0.format(
            customer_text=customer_text, intent=intent,
            grounding_instructions=GEN_INSTRUCTIONS_GROUNDING_NOTES,
        )
    else:
        user_prompt = GEN_USER_TEMPLATE_KGT0.format(
            customer_text=customer_text, intent=intent, evidence_block=evidence_block,
            grounding_instructions=GEN_INSTRUCTIONS_GROUNDING_NOTES,
        )
    return GEN_SYSTEM_PREAMBLE, user_prompt


def _build_judge_messages(customer_text, generated_reply, retrieved_evidence, rubric):
    evidence_block = _render_evidence_block(retrieved_evidence)
    evidence_section = evidence_block or "(none -- k=0 condition, no retrieval was performed for this query)"
    system_prompt = "You are an impartial evaluator of customer-support reply quality.\n\n" + rubric
    user_prompt = JUDGE_USER_TEMPLATE.format(
        customer_text=customer_text, generated_reply=generated_reply, evidence_section=evidence_section,
    )
    return system_prompt, user_prompt


def strip_gold_fields(golden_row):
    """Takes one raw row dict from golden_set/GOLDEN_200_FINAL.csv (as read by
    csv.DictReader -- keys: candidate_id, tweet_id, thread_id, customer_id,
    target_message, human_gold_label, human_notes) and returns a dict containing
    ONLY the fields the generator/judge pipeline is allowed to see: tweet_id,
    thread_id, customer_id, customer_text. human_gold_label and human_notes are
    never copied, per implementation_plan.md §3 Experiment 3's data-access rule.
    """
    return dict(
        tweet_id=golden_row["tweet_id"],
        thread_id=golden_row["thread_id"],
        customer_id=golden_row["customer_id"],
        customer_text=golden_row["target_message"],
    )


class _KeyedLock:
    """Per-cache-key lock for Part 3 (concurrency) cache safety.

    evaluation.llm_classifier.DiskCache (frozen) is a bare read-file / write-file pair
    with no locking: .get() does a plain open()+json.load(), .set() does a plain
    open(mode="w")+json.dump(). Two DIFFERENT cache keys always resolve to two different
    filenames (SHA-256 of the full request payload), so concurrent set() calls for
    different keys touch different files and are safe as-is. But if two threads ever
    computed the SAME key concurrently (e.g. a retry racing the original attempt), both
    would miss the cache, both would call the API, and both would open() the SAME file
    for writing at once -- json.dump() issues multiple write() calls, so two interleaved
    writers can corrupt that one file (last-writer-wins is not guaranteed; a torn/mixed
    write is possible). This class prevents that by serializing the ENTIRE
    get-check-call-set sequence per key: same-key callers block and the second one gets
    a clean cache hit; different-key callers never contend, so the ThreadPoolExecutor
    concurrency in evaluation/run_k_ablation_sweep.py is not affected in practice (real
    sweep keys are effectively always distinct -- each (example, k) pair produces a
    unique prompt).
    """

    def __init__(self):
        self._locks = defaultdict(threading.Lock)
        self._guard = threading.Lock()

    def __call__(self, key):
        with self._guard:
            return self._locks[key]


class ExperimentLLMProvider(LLMProvider):
    """Extends the frozen evaluation.llm_classifier.LLMProvider with real
    .generate_reply() and .judge() implementations for Experiment 3. .classify()
    and all __init__/cache/client plumbing are inherited unchanged from the parent.

    Adds a per-cache-key lock (_KeyedLock) around the cache get/API-call/cache-set
    sequence in generate_reply()/judge() so this provider is safe to share across
    threads in a ThreadPoolExecutor (Part 3) -- see _KeyedLock's docstring.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache_lock = _KeyedLock()

    def generate_reply(self, customer_text, intent, triage_decision, retrieved_pairs) -> dict:
        """Returns {"reply": str, "grounding_notes": {...}}.

        retrieved_pairs: output of evaluation.retrieval.retrieve_top_k() as-is (a list
            of (customer_text, brand_text, similarity, metadata) tuples; [] for k=0).
        triage_decision: accepted for interface parity with implementation_plan.md §10's
            LLMProvider.generate_reply() signature. Experiment 3's prompt templates (§9)
            do not reference a triage decision (triage rules are a later, separate
            experiment -- not built here), so this is appended only as an optional
            reference note when the caller supplies one; it is None for every Experiment
            3 call in this milestone.
        """
        system_prompt, user_prompt = _build_generate_messages(customer_text, intent, retrieved_pairs)
        if triage_decision:
            user_prompt += f"\n\n(Triage decision for reference: {triage_decision})"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        cache_key = json.dumps(dict(
            model=self.generate_model,
            prompt_version=GENERATOR_PROMPT_VERSION,
            messages=messages,
            temperature=config.LLM_TEMPERATURE,
            seed=config.LLM_SEED,
            reasoning_effort=config.REASONING_EFFORT_FOR_TEMPERATURE,
        ), sort_keys=True)

        with self._cache_lock(cache_key):
            cached = self.cache.get(cache_key)
            if cached is not None:
                return validate_generation_output(cached)

            response = self.client.chat.completions.create(
                model=self.generate_model,
                messages=messages,
                temperature=config.LLM_TEMPERATURE,
                seed=config.LLM_SEED,
                reasoning_effort=config.REASONING_EFFORT_FOR_TEMPERATURE,
                response_format=GENERATION_JSON_SCHEMA,
            )
            parsed = json.loads(response.choices[0].message.content)
            validate_generation_output(parsed)
            self.cache.set(cache_key, parsed)
            return parsed

    def judge(self, customer_text, generated_reply, retrieved_evidence, rubric=None) -> dict:
        """Returns {"relevance": int, "groundedness": int, "helpfulness": int,
        "tone": int, "reasoning": str}, each score in 1-5.

        retrieved_evidence: the SAME retrieved_pairs list passed to generate_reply()
            for this example/k -- the judge independently re-examines it rather than
            trusting the generator's self-reported grounding_notes.
        rubric: defaults to DEFAULT_JUDGE_RUBRIC when not supplied.
        """
        rubric = rubric or DEFAULT_JUDGE_RUBRIC
        system_prompt, user_prompt = _build_judge_messages(
            customer_text, generated_reply, retrieved_evidence, rubric,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        cache_key = json.dumps(dict(
            model=self.judge_model,
            prompt_version=JUDGE_PROMPT_VERSION,
            messages=messages,
            temperature=config.LLM_TEMPERATURE,
            seed=config.LLM_SEED,
            reasoning_effort=config.REASONING_EFFORT_FOR_TEMPERATURE,
        ), sort_keys=True)

        with self._cache_lock(cache_key):
            cached = self.cache.get(cache_key)
            if cached is not None:
                return validate_judge_output(cached)

            response = self.client.chat.completions.create(
                model=self.judge_model,
                messages=messages,
                temperature=config.LLM_TEMPERATURE,
                seed=config.LLM_SEED,
                reasoning_effort=config.REASONING_EFFORT_FOR_TEMPERATURE,
                response_format=JUDGE_JSON_SCHEMA,
            )
            parsed = json.loads(response.choices[0].message.content)
            validate_judge_output(parsed)
            self.cache.set(cache_key, parsed)
            return parsed
