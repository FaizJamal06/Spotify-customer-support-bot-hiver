"""
LLM intent classifier (Phase 2 / Experiment 1's third classifier).

Implements the LLMProvider interface exactly as specified in
implementation_plan.md §10 -- only .classify() is implemented in this
milestone; .generate_reply() and .judge() are out of scope (later
milestones) and are left as explicit NotImplementedError stubs so the
interface shape matches the plan without pretending those are done.

Determinism: empirically verified against the live API before writing this
module (see the milestone report) -- config.CLASSIFY_MODEL ("gpt-5.4-mini")
accepts both `temperature` and `seed` at its default reasoning_effort
("none"). Both are passed on every call: config.LLM_TEMPERATURE (0, frozen,
unchanged) and config.LLM_SEED (new constant, added for this milestone).
Structured output is enforced via a strict JSON-schema response_format
constraining `intent` to exactly the 8 frozen labels, so the API itself
cannot return an out-of-taxonomy value.

Few-shot examples are rendered as customer text + frozen label only -- no
golden-set text or label is ever included in any prompt, for any query.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

INTENT_CLASSIFIER_PROMPT_VERSION = "v1"

_SECTION_HEADER_RE = re.compile(r"(?m)^## (\d+)\. ([A-Z_]+)\s*$")


def load_intent_definitions():
    """
    Extracts the 8 per-intent definition sections (## 1. ACCOUNT_ACCESS ... ## 8.
    UNKNOWN_OTHER) verbatim from discovery/TAXONOMY_REVIEW_GUIDE.md -- the frozen,
    authoritative rulebook -- at call time, so the prompt can never drift from the
    guide's actual current wording (no hand-transcription, no re-summarizing).
    Returns a single formatted string, in config.FROZEN_LABELS order.
    """
    with open(config.DISCOVERY_DIR / "TAXONOMY_REVIEW_GUIDE.md", encoding="utf-8") as f:
        content = f.read()

    matches = list(_SECTION_HEADER_RE.finditer(content))
    sections = {}
    for i, m in enumerate(matches):
        num, label = m.group(1), m.group(2)
        if label not in config.FROZEN_LABELS:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections[label] = content[start:end].strip()

    missing = set(config.FROZEN_LABELS) - set(sections)
    if missing:
        raise RuntimeError(
            f"Could not extract guide sections for: {missing}. "
            "discovery/TAXONOMY_REVIEW_GUIDE.md may have changed format."
        )

    blocks = []
    for label in config.FROZEN_LABELS:
        blocks.append(f"### {label}\n{sections[label]}")
    return "\n\n".join(blocks)


def render_fewshot_block(demonstrations):
    """
    Renders the fixed few-shot demonstrations as customer text + frozen label only
    (no reasoning, no boundary tags, no golden-set content -- ever).
    `demonstrations`: dict label -> list of {text, ...} dicts, as returned by
    evaluation.fewshot_selection.select_fewshot_demonstrations().
    """
    lines = []
    for label in config.FROZEN_LABELS:
        for ex in demonstrations[label]:
            text = ex["text"].replace("\n", " ").strip()
            lines.append(f'Customer message: "{text}"\nIntent: {label}')
    return "\n\n".join(lines)


RESPONSE_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "intent_classification",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "enum": list(config.FROZEN_LABELS)},
                "confidence": {"type": "number"},
                "reasoning": {"type": "string"},
            },
            "required": ["intent", "confidence", "reasoning"],
            "additionalProperties": False,
        },
    },
}


def validate_classification_output(obj):
    """
    Defense-in-depth schema validation (the API's strict json_schema response_format
    should already guarantee this, but callers -- including tests -- must not trust
    that blindly). Raises ValueError on any violation. Returns obj unchanged on success.
    """
    if not isinstance(obj, dict):
        raise ValueError(f"Classification output is not a dict: {type(obj)}")
    for key in ("intent", "confidence", "reasoning"):
        if key not in obj:
            raise ValueError(f"Classification output missing required key: {key!r}")
    if obj["intent"] not in config.FROZEN_LABELS:
        raise ValueError(f"intent {obj['intent']!r} is not one of the 8 frozen labels")
    if not isinstance(obj["confidence"], (int, float)):
        raise ValueError(f"confidence must be numeric, got {type(obj['confidence'])}")
    if not isinstance(obj["reasoning"], str):
        raise ValueError(f"reasoning must be a string, got {type(obj['reasoning'])}")
    return obj


class DiskCache:
    """Minimal disk cache for LLM responses, keyed by a hash of the full request payload
    (model + prompt version + messages + temperature + seed). Reruns with an unchanged
    prompt/model/demonstration-set never re-call the API."""

    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key):
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def get(self, key):
        p = self._path(key)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        return None

    def set(self, key, value):
        p = self._path(key)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)


class LLMProvider:
    """Single interface for all LLM calls (implementation_plan.md §10). Only .classify()
    is implemented in this milestone; .generate_reply() and .judge() are later milestones
    and are intentionally left unimplemented, not stubbed with fake behavior."""

    def __init__(self, classify_model, generate_model, judge_model, api_key, cache_dir=None):
        self.classify_model = classify_model
        self.generate_model = generate_model
        self.judge_model = judge_model
        self.api_key = api_key
        self.cache = DiskCache(cache_dir if cache_dir is not None else config.CACHE_DIR)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def classify(self, customer_text, few_shot_examples, intent_definitions) -> dict:
        """Returns {"intent": str, "confidence": float, "reasoning": str}.

        few_shot_examples: pre-rendered string block (see render_fewshot_block) --
            customer text + frozen label only, fixed for the whole evaluation run.
        intent_definitions: pre-rendered string block (see load_intent_definitions) --
            the frozen guide's actual per-intent definitions, verbatim.
        """
        system_prompt = (
            "You are an intent classifier for SpotifyCares customer support messages. "
            "Classify the customer's PRIMARY SUPPORT NEED using the frozen 8-label taxonomy "
            "defined below. Follow the taxonomy's actual definitions and boundary rules "
            "exactly; do not invent categories outside the 8 listed. UNKNOWN_OTHER is a "
            "valid, sometimes-correct answer, not a fallback of last resort to avoid.\n\n"
            "=== FROZEN TAXONOMY DEFINITIONS ===\n" + intent_definitions + "\n\n"
            "=== LABELED EXAMPLES (fixed reference set, same for every query) ===\n" + few_shot_examples
        )
        user_prompt = f'Classify this customer message:\n"{customer_text}"'

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        cache_key = json.dumps(dict(
            model=self.classify_model,
            prompt_version=INTENT_CLASSIFIER_PROMPT_VERSION,
            messages=messages,
            temperature=config.LLM_TEMPERATURE,
            seed=config.LLM_SEED,
        ), sort_keys=True)

        cached = self.cache.get(cache_key)
        if cached is not None:
            return validate_classification_output(cached)

        response = self.client.chat.completions.create(
            model=self.classify_model,
            messages=messages,
            temperature=config.LLM_TEMPERATURE,
            seed=config.LLM_SEED,
            response_format=RESPONSE_JSON_SCHEMA,
        )
        parsed = json.loads(response.choices[0].message.content)
        validate_classification_output(parsed)
        self.cache.set(cache_key, parsed)
        return parsed

    def generate_reply(self, customer_text, intent, triage_decision, retrieved_pairs) -> dict:
        """Later milestone (response generation). Not implemented here."""
        raise NotImplementedError("generate_reply() is out of scope for this milestone.")

    def judge(self, customer_text, generated_reply, retrieved_evidence, rubric) -> dict:
        """Later milestone (LLM-as-judge). Not implemented here."""
        raise NotImplementedError("judge() is out of scope for this milestone.")
