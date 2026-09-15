"""
Tests for evaluation/generation.py (response generator + minimal LLM judge,
Experiment 3 milestone) and the pilot's gold-isolation selection logic in
evaluation/run_generation_judge_pilot.py.

Covers: generator output-schema validation, judge output-schema + score-range
validation, k=0 short-circuiting to no retrieval call (reusing retrieve_top_k's
own guarantee, already tested in evaluation/test_retrieval.py), and the
gold-data-isolation rule (generator/judge inputs never contain gold fields).

No real API calls are made in this suite -- generate_reply()/judge() are exercised
against a stubbed self.client.chat.completions.create, matching the mocking style
already used for baselines/classifier tests in this project.
"""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.generation import (
    ExperimentLLMProvider,
    GENERATION_JSON_SCHEMA,
    JUDGE_JSON_SCHEMA,
    build_evidence_records,
    clean_brand_text,
    strip_gold_fields,
    validate_generation_output,
    validate_judge_output,
)
from evaluation.retrieval import retrieve_top_k
from evaluation.run_generation_judge_pilot import (
    load_exp1_predicted_intents,
    load_golden_rows_raw,
    select_pilot_examples,
)


def _valid_generation_dict(reply="Sorry to hear that! Please DM us your device model."):
    return {
        "reply": reply,
        "grounding_notes": {
            "grounded_in_evidence": [],
            "grounded_in_customer_message": ["customer reported an issue"],
            "unsupported_or_generic": ["offered to help via DM"],
        },
    }


def _valid_judge_dict():
    return {
        "relevance": 4, "groundedness": 3, "helpfulness": 4, "tone": 5,
        "reasoning": "On-topic, mostly generic, friendly.",
    }


# ============================================================
# Part 1: evidence-cleaning (stale presentation-artifact removal)
# ============================================================
# Fixtures below are taken verbatim from the pilot run (evaluation/GENERATION_JUDGE_
# PILOT_RESULTS.md) and from the corpus frequency scan performed while diagnosing the
# problem (cache/retrieval_index/metadata.jsonl, read-only) -- not invented text.

def test_strips_trailing_agent_signoff_with_no_url():
    cleaned, removed = clean_brand_text(
        "Thanks for letting us know! We're currently looking into this at the moment. "
        "Hopefully we'll have a fix soon \U0001f642 /CG"
    )
    assert cleaned == (
        "Thanks for letting us know! We're currently looking into this at the moment. "
        "Hopefully we'll have a fix soon \U0001f642"
    )
    assert removed == [{"kind": "agent_signoff", "value": "/CG"}]


def test_strips_uncued_trailing_url_and_its_signoff_pilot_case():
    """The exact tweet_id=44426 k=1 retrieved pair that the generator copied verbatim
    into a fabricated-looking DM link + agent code for an unrelated (Indonesian-language)
    customer. Both the sign-off and the bare, uncued tracking URL must be stripped."""
    raw = ("@729407 Hey there! Could you DM us your account's username or email address? "
           "We'll take a look backstage /GU https://t.co/ldFdZRiNAt")
    cleaned, removed = clean_brand_text(raw)
    assert cleaned == (
        "@729407 Hey there! Could you DM us your account's username or email address? "
        "We'll take a look backstage"
    )
    kinds = [r["kind"] for r in removed]
    assert kinds == ["uncued_trailing_url", "agent_signoff"]
    assert "https://t.co/ldFdZRiNAt" not in cleaned
    assert "/GU" not in cleaned


def test_preserves_url_introduced_by_at_cue_pilot_case():
    """The tweet_id=44402 (Indonesian billing) retrieved pair: the URL IS the substantive
    evidence (the actual Indonesian-language support email link) -- must survive."""
    raw = ("@118266 min lagi gangguan kah pembayaran spotify via doku dan pulsa?? "
           "Hey there! We can help out in English via Twitter, but we also have Indonesian "
           "support via email at https://t.co/ZgU70TbP8M /DR")
    cleaned, removed = clean_brand_text(raw)
    assert "https://t.co/ZgU70TbP8M" in cleaned
    assert removed == [{"kind": "agent_signoff", "value": "/DR"}]


def test_preserves_url_introduced_by_here_colon_cue():
    raw = "Hey! We'd love to have all of their stuff available, but we have some info about content here: https://t.co/0i8GpimuDa /TB"
    cleaned, removed = clean_brand_text(raw)
    assert "https://t.co/0i8GpimuDa" in cleaned
    assert removed == [{"kind": "agent_signoff", "value": "/TB"}]


def test_preserves_url_introduced_by_reach_out_here_cue():
    raw = "Hey! Our friends in Artist Support are the right folks to help with this. You can reach out to them here: https://t.co/p1wbtdELHu /MQ"
    cleaned, removed = clean_brand_text(raw)
    assert "https://t.co/p1wbtdELHu" in cleaned
    assert removed == [{"kind": "agent_signoff", "value": "/MQ"}]


def test_strips_uncued_url_when_signoff_precedes_url_order():
    """Covers the other tail ordering (URL after sign-off, not before)."""
    raw = "@331476 Got it. Can you DM us your account's email address or username? We'll take a look backstage /MT https://t.co/ldFdZRiNAt"
    cleaned, removed = clean_brand_text(raw)
    assert "https://t.co/ldFdZRiNAt" not in cleaned
    assert "/MT" not in cleaned
    assert cleaned.endswith("backstage")


def test_never_produces_empty_string_falls_back_to_original():
    cleaned, removed = clean_brand_text("/FR")
    assert cleaned == "/FR"
    assert removed == []


def test_text_with_no_artifacts_is_returned_unchanged():
    text = "We're afraid we don't have any info to share right now, but our developers are working on it."
    cleaned, removed = clean_brand_text(text)
    assert cleaned == text
    assert removed == []


def test_customer_text_is_never_touched_by_evidence_cleaning():
    retrieved_pairs = [
        ("@user Still does it after reinstall /XX https://t.co/fakeXXXXXX",
         "Thanks. It would be best if you delete previous tweets and send us a DM instead /JU https://t.co/ldFdZRiNAt",
         0.67, {}),
    ]
    records = build_evidence_records(retrieved_pairs)
    assert records[0]["customer_text"] == "@user Still does it after reinstall /XX https://t.co/fakeXXXXXX"
    assert records[0]["brand_text_raw"] == (
        "Thanks. It would be best if you delete previous tweets and send us a DM instead /JU https://t.co/ldFdZRiNAt"
    )
    assert "https://t.co/ldFdZRiNAt" not in records[0]["brand_text_shown"]
    assert "/JU" not in records[0]["brand_text_shown"]
    assert len(records[0]["removed_artifacts"]) == 2


def test_build_evidence_records_empty_for_k_zero():
    assert build_evidence_records([]) == []


def test_clean_brand_text_is_idempotent():
    raw = "We'll take a look backstage /GU https://t.co/ldFdZRiNAt"
    once, _ = clean_brand_text(raw)
    twice, removed_twice = clean_brand_text(once)
    assert once == twice
    assert removed_twice == []


def test_evidence_cleaning_against_real_retrieval_index_corpus():
    """Regression check against the actual frozen index (read-only): the single most
    frequent boilerplate URL (722/3000 occurrences, all attached to a content-free
    'DM us / take a look backstage' tail -- see investigation notes) must always be
    stripped; a clearly substantive, cue-introduced URL must never be stripped, even
    though both recur frequently in the corpus (frequency alone was checked and
    rejected as a discriminator during investigation)."""
    if not (config.RETRIEVAL_INDEX_DIR / "metadata.jsonl").exists():
        pytest.skip("No real retrieval index at cache/retrieval_index/")

    import json as _json
    boilerplate_seen = substantive_seen = False
    with open(config.RETRIEVAL_INDEX_DIR / "metadata.jsonl", encoding="utf-8") as f:
        for line in f:
            m = _json.loads(line)
            brand = m["brand_text"]
            if "https://t.co/ldFdZRiNAt" in brand and not boilerplate_seen:
                cleaned, removed = clean_brand_text(brand)
                assert "https://t.co/ldFdZRiNAt" not in cleaned
                boilerplate_seen = True
            if "https://t.co/0i8GpimuDa" in brand and "here:" in brand.lower() and not substantive_seen:
                cleaned, removed = clean_brand_text(brand)
                assert "https://t.co/0i8GpimuDa" in cleaned
                substantive_seen = True
            if boilerplate_seen and substantive_seen:
                break
    assert boilerplate_seen, "expected to find at least one occurrence of the known boilerplate URL"
    assert substantive_seen, "expected to find at least one occurrence of the known substantive URL"


# ============================================================
# Generator output-schema validation
# ============================================================

def test_validate_generation_output_accepts_valid_dict():
    out = validate_generation_output(_valid_generation_dict())
    assert out["reply"]


def test_validate_generation_output_rejects_missing_top_level_keys():
    with pytest.raises(ValueError):
        validate_generation_output({"reply": "hi"})
    with pytest.raises(ValueError):
        validate_generation_output({"grounding_notes": _valid_generation_dict()["grounding_notes"]})


def test_validate_generation_output_rejects_empty_reply():
    d = _valid_generation_dict(reply="   ")
    with pytest.raises(ValueError):
        validate_generation_output(d)


def test_validate_generation_output_rejects_missing_grounding_notes_subkeys():
    d = _valid_generation_dict()
    del d["grounding_notes"]["unsupported_or_generic"]
    with pytest.raises(ValueError):
        validate_generation_output(d)


def test_validate_generation_output_rejects_non_string_list_items():
    d = _valid_generation_dict()
    d["grounding_notes"]["grounded_in_evidence"] = [123]
    with pytest.raises(ValueError):
        validate_generation_output(d)


def test_generation_json_schema_is_strict_and_matches_validator_keys():
    schema = GENERATION_JSON_SCHEMA["json_schema"]["schema"]
    assert GENERATION_JSON_SCHEMA["json_schema"]["strict"] is True
    assert set(schema["required"]) == {"reply", "grounding_notes"}
    gn_schema = schema["properties"]["grounding_notes"]
    assert set(gn_schema["required"]) == {
        "grounded_in_evidence", "grounded_in_customer_message", "unsupported_or_generic",
    }


# ============================================================
# Judge output-schema + score-range validation
# ============================================================

def test_validate_judge_output_accepts_valid_dict():
    out = validate_judge_output(_valid_judge_dict())
    assert out["relevance"] == 4


def test_validate_judge_output_rejects_missing_keys():
    d = _valid_judge_dict()
    del d["tone"]
    with pytest.raises(ValueError):
        validate_judge_output(d)


@pytest.mark.parametrize("bad_value", [0, 6, -1, 100])
def test_validate_judge_output_rejects_out_of_range_scores(bad_value):
    d = _valid_judge_dict()
    d["relevance"] = bad_value
    with pytest.raises(ValueError):
        validate_judge_output(d)


def test_validate_judge_output_rejects_non_int_scores():
    d = _valid_judge_dict()
    d["groundedness"] = "3"
    with pytest.raises(ValueError):
        validate_judge_output(d)
    d2 = _valid_judge_dict()
    d2["tone"] = True  # bool is technically an int subclass in Python -- must be rejected explicitly
    with pytest.raises(ValueError):
        validate_judge_output(d2)


def test_judge_json_schema_enums_are_1_to_5_for_every_score_dimension():
    props = JUDGE_JSON_SCHEMA["json_schema"]["schema"]["properties"]
    for dim in ("relevance", "groundedness", "helpfulness", "tone"):
        assert props[dim]["enum"] == [1, 2, 3, 4, 5]


# ============================================================
# k=0 short-circuits to no retrieval call
# ============================================================

def test_k_zero_never_calls_get_embedding(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("get_embedding must not be called when k=0")
    monkeypatch.setattr("evaluation.retrieval.get_embedding", fail_if_called)

    retrieved = retrieve_top_k("this text should never be embedded", k=0)
    assert retrieved == []


def test_generate_reply_with_k_zero_produces_no_evidence_prompt_section(tmp_path):
    """With retrieved_pairs=[] (the k=0 case), the rendered prompt must not contain
    a 'SIMILAR PAST CONVERSATIONS' evidence block."""
    provider = ExperimentLLMProvider(
        classify_model=config.CLASSIFY_MODEL, generate_model=config.GENERATE_MODEL,
        judge_model=config.JUDGE_MODEL, api_key="fake-key", cache_dir=tmp_path,
    )
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        msg = MagicMock()
        msg.message.content = json.dumps(_valid_generation_dict())
        resp = MagicMock()
        resp.choices = [msg]
        return resp

    provider._client = MagicMock()
    provider._client.chat.completions.create = fake_create
    provider.generate_reply("my app crashes", "APP_TECH_ISSUE", None, [])

    user_message = captured["messages"][1]["content"]
    assert "SIMILAR PAST CONVERSATIONS" not in user_message
    assert "no historical evidence was retrieved" in user_message.lower()


# ============================================================
# Gold-data isolation
# ============================================================

def test_strip_gold_fields_drops_gold_label_and_notes():
    raw_row = {
        "candidate_id": "CAND_0001", "tweet_id": "123", "thread_id": "123",
        "customer_id": "555", "target_message": "help me",
        "human_gold_label": "ACCOUNT_ACCESS", "human_notes": "some secret annotator note",
    }
    stripped = strip_gold_fields(raw_row)
    assert "human_gold_label" not in stripped
    assert "human_notes" not in stripped
    assert set(stripped.keys()) == {"tweet_id", "thread_id", "customer_id", "customer_text"}
    assert stripped["customer_text"] == "help me"


def test_select_pilot_examples_output_never_contains_gold_fields():
    golden_rows = load_golden_rows_raw()
    predicted_intents = load_exp1_predicted_intents()
    pilot_examples = select_pilot_examples(golden_rows, predicted_intents)

    assert len(pilot_examples) == len(config.FROZEN_LABELS)
    for ex in pilot_examples:
        assert "human_gold_label" not in ex
        assert "human_notes" not in ex
        assert set(ex.keys()) == {"tweet_id", "thread_id", "customer_id", "customer_text", "classified_intent"}


def test_select_pilot_examples_intent_comes_from_exp1_predictions_not_gold():
    """The classified_intent attached to each pilot example must equal the Exp-1
    PREDICTED intent for that tweet_id, sourced from llm_classifier_results.json --
    never read directly from golden_set/GOLDEN_200_FINAL.csv's human_gold_label."""
    golden_rows = load_golden_rows_raw()
    predicted_intents = load_exp1_predicted_intents()
    pilot_examples = select_pilot_examples(golden_rows, predicted_intents)

    for ex in pilot_examples:
        assert predicted_intents[ex["tweet_id"]] == ex["classified_intent"]


def test_select_pilot_examples_covers_every_frozen_intent_exactly_once():
    golden_rows = load_golden_rows_raw()
    predicted_intents = load_exp1_predicted_intents()
    pilot_examples = select_pilot_examples(golden_rows, predicted_intents)
    intents_seen = [ex["classified_intent"] for ex in pilot_examples]
    assert sorted(intents_seen) == sorted(config.FROZEN_LABELS)


def test_select_pilot_examples_is_deterministic_across_runs():
    golden_rows = load_golden_rows_raw()
    predicted_intents = load_exp1_predicted_intents()
    run1 = select_pilot_examples(golden_rows, predicted_intents)
    run2 = select_pilot_examples(golden_rows, predicted_intents)
    assert [e["tweet_id"] for e in run1] == [e["tweet_id"] for e in run2]


# ============================================================
# Part 3: concurrency / cache safety
# ============================================================

def test_concurrent_same_key_requests_call_api_exactly_once(tmp_path):
    """N threads all requesting the SAME (customer_text, intent, retrieved_pairs) --
    i.e. an identical cache key -- must result in exactly ONE underlying API call and
    a single valid cache file; every thread must get back the correct, identical result.
    Demonstrates _KeyedLock prevents both duplicate API spend and concurrent writes to
    the same cache file on an accidental key collision."""
    provider = ExperimentLLMProvider(
        classify_model=config.CLASSIFY_MODEL, generate_model=config.GENERATE_MODEL,
        judge_model=config.JUDGE_MODEL, api_key="fake-key", cache_dir=tmp_path,
    )
    call_count = {"n": 0}
    call_lock = threading.Lock()

    def fake_create(**kwargs):
        with call_lock:
            call_count["n"] += 1
        time.sleep(0.05)  # widen the race window so a real bug would actually race
        msg = MagicMock()
        msg.message.content = json.dumps(_valid_generation_dict(reply="the one true reply"))
        resp = MagicMock()
        resp.choices = [msg]
        return resp

    provider._client = MagicMock()
    provider._client.chat.completions.create = fake_create

    results = []
    errors = []

    def worker():
        try:
            results.append(provider.generate_reply("same text", "APP_TECH_ISSUE", None, []))
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"unexpected errors under concurrency: {errors}"
    assert call_count["n"] == 1, f"expected exactly 1 API call for a shared cache key, got {call_count['n']}"
    assert len(results) == 20
    assert all(r["reply"] == "the one true reply" for r in results)

    cache_files = list(Path(tmp_path).glob("*.json"))
    assert len(cache_files) == 1
    with open(cache_files[0], encoding="utf-8") as f:
        on_disk = json.load(f)  # must be valid, uncorrupted JSON
    assert on_disk["reply"] == "the one true reply"


def test_concurrent_different_key_requests_do_not_corrupt_each_other(tmp_path):
    """N threads with N DISTINCT cache keys (different customer_text) must each get their
    own correct result, each API-called exactly once, with no cross-contamination and no
    corrupted cache files -- different keys must not block each other either (this must
    complete quickly, not serialize to N * per-call latency)."""
    provider = ExperimentLLMProvider(
        classify_model=config.CLASSIFY_MODEL, generate_model=config.GENERATE_MODEL,
        judge_model=config.JUDGE_MODEL, api_key="fake-key", cache_dir=tmp_path,
    )
    call_counts = {}
    call_counts_lock = threading.Lock()

    def fake_create(**kwargs):
        # identify which request this is by inspecting the user message content
        user_text = kwargs["messages"][1]["content"]
        with call_counts_lock:
            call_counts[user_text] = call_counts.get(user_text, 0) + 1
        time.sleep(0.05)
        msg = MagicMock()
        msg.message.content = json.dumps(_valid_generation_dict(reply=f"reply for: {user_text[:80]}"))
        resp = MagicMock()
        resp.choices = [msg]
        return resp

    provider._client = MagicMock()
    provider._client.chat.completions.create = fake_create

    n = 15
    results = {}
    results_lock = threading.Lock()

    def worker(i):
        customer_text = f"distinct customer message number {i}"
        out = provider.generate_reply(customer_text, "APP_TECH_ISSUE", None, [])
        with results_lock:
            results[i] = out

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n) as ex:
        list(ex.map(worker, range(n)))
    elapsed = time.time() - t0

    assert len(results) == n
    for i in range(n):
        assert f"distinct customer message number {i}" in results[i]["reply"], (
            f"result {i} does not match its own request: {results[i]['reply']!r}"
        )
    # every one of the n distinct keys triggered exactly one API call (no duplicate work, no lost work)
    assert len(call_counts) == n
    assert all(c == 1 for c in call_counts.values())
    # ran concurrently, not serially: n * 0.05s serial would be >= 0.75s; concurrent should be well under that
    assert elapsed < 0.4, f"requests for different keys appear to have serialized (took {elapsed:.2f}s)"

    cache_files = list(Path(tmp_path).glob("*.json"))
    assert len(cache_files) == n
    for f in cache_files:
        with open(f, encoding="utf-8") as fh:
            json.load(fh)  # every cache file must be valid, uncorrupted JSON


def test_select_pilot_examples_raises_when_an_intent_has_no_predictions():
    golden_rows = [
        {"candidate_id": "C1", "tweet_id": "1", "thread_id": "1", "customer_id": "1",
         "target_message": "x", "human_gold_label": "ACCOUNT_ACCESS", "human_notes": ""},
    ]
    predicted_intents = {"1": "ACCOUNT_ACCESS"}  # only 1 of 8 intents covered
    with pytest.raises(AssertionError):
        select_pilot_examples(golden_rows, predicted_intents)
