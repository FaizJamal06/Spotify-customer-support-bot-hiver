"""
Focused tests for the LLM intent-classifier milestone: deterministic few-shot
selection, MATCH-status-only filtering, the >=3-per-intent hard assertion
(both the success and STOP paths), leakage assertion, and output-schema
validation. No real API calls are made in this test suite (classify() is
not exercised here -- see evaluation/LLM_CLASSIFIER_RESULTS.md for the
actual run's results).

Run with: pytest evaluation/test_llm_classifier_milestone.py -v
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from evaluation.fewshot_selection import (
    select_fewshot_demonstrations, assert_fewshot_no_golden_leakage,
    flatten, FewShotSelectionError, _load_audit_status_map,
)
from evaluation.leakage_checks import LeakageError
from evaluation.data_loading import load_golden_examples
from evaluation.llm_classifier import (
    validate_classification_output, load_intent_definitions,
    render_fewshot_block, RESPONSE_JSON_SCHEMA, INTENT_CLASSIFIER_PROMPT_VERSION,
)


# ============================================================
# Deterministic few-shot selection
# ============================================================

def test_selection_is_byte_identical_across_two_runs():
    demos1, log1 = select_fewshot_demonstrations()
    demos2, log2 = select_fewshot_demonstrations()
    assert log1 == log2
    for label in config.FROZEN_LABELS:
        ids1 = [e["example_id"] for e in demos1[label]]
        ids2 = [e["example_id"] for e in demos2[label]]
        assert ids1 == ids2, f"non-deterministic order for {label}"


def test_every_selected_demo_has_match_status():
    demos, _ = select_fewshot_demonstrations()
    status_map = _load_audit_status_map()
    for label, rows in demos.items():
        for ex in rows:
            assert status_map[ex["example_id"]] == "MATCH", (
                f"Ex {ex['example_id']} (intent {label}) does not have status MATCH"
            )


def test_every_intent_has_at_least_min_demonstrations():
    demos, log = select_fewshot_demonstrations()
    assert set(log.keys()) == set(config.FROZEN_LABELS)
    for label, ids in log.items():
        assert len(ids) >= config.FEWSHOT_MIN_PER_INTENT
        assert len(ids) <= config.FEWSHOT_MAX_PER_INTENT


def test_selection_sorted_ascending_by_example_id():
    demos, log = select_fewshot_demonstrations()
    for label, ids in log.items():
        int_ids = [int(i) for i in ids]
        assert int_ids == sorted(int_ids), f"{label} demo IDs not ascending: {ids}"


def test_stop_condition_raises_when_intent_has_too_few_candidates():
    """Simulate a shortfall (an intent with only 2 MATCH-status rows) and confirm the
    code raises FewShotSelectionError rather than silently proceeding or substituting
    a POSSIBLE/MISMATCH row."""
    fake_examples = []
    fake_excluded = []
    fake_source = "fake"
    # 7 intents get 5 examples each; ACCOUNT_ACCESS gets only 2 -> should trigger STOP.
    counter = 0
    for label in config.FROZEN_LABELS:
        n = 2 if label == "ACCOUNT_ACCESS" else 5
        for _ in range(n):
            counter += 1
            fake_examples.append(dict(
                example_id=str(counter), tweet_id=str(1000 + counter),
                thread_id=str(1000 + counter), text=f"text {counter}", label=label,
            ))

    fake_status_map = {e["example_id"]: "MATCH" for e in fake_examples}

    with patch("evaluation.fewshot_selection.load_training_examples",
               return_value=(fake_examples, fake_excluded, fake_source)), \
         patch("evaluation.fewshot_selection._load_audit_status_map",
               return_value=fake_status_map):
        with pytest.raises(FewShotSelectionError) as excinfo:
            select_fewshot_demonstrations()
        assert "ACCOUNT_ACCESS" in str(excinfo.value)
        assert "2" in str(excinfo.value)


def test_success_path_still_works_when_all_intents_sufficient():
    """Companion to the STOP-condition test: confirms the success path is not broken
    by the same patching mechanism when every intent has enough candidates."""
    fake_examples = []
    counter = 0
    for label in config.FROZEN_LABELS:
        for _ in range(5):
            counter += 1
            fake_examples.append(dict(
                example_id=str(counter), tweet_id=str(2000 + counter),
                thread_id=str(2000 + counter), text=f"text {counter}", label=label,
            ))
    fake_status_map = {e["example_id"]: "MATCH" for e in fake_examples}

    with patch("evaluation.fewshot_selection.load_training_examples",
               return_value=(fake_examples, [], "fake")), \
         patch("evaluation.fewshot_selection._load_audit_status_map",
               return_value=fake_status_map):
        demos, log = select_fewshot_demonstrations()
        for label in config.FROZEN_LABELS:
            assert len(log[label]) == 5


def test_possible_and_mismatch_rows_are_excluded_from_selection():
    """A POSSIBLE or MISMATCH row must never be substituted in, even if it would
    otherwise be the next-lowest example_id for that intent."""
    fake_examples = [
        dict(example_id="1", tweet_id="t1", thread_id="th1", text="a", label="ACCOUNT_ACCESS"),
        dict(example_id="2", tweet_id="t2", thread_id="th2", text="b", label="ACCOUNT_ACCESS"),
        dict(example_id="3", tweet_id="t3", thread_id="th3", text="c", label="ACCOUNT_ACCESS"),
        dict(example_id="4", tweet_id="t4", thread_id="th4", text="d", label="ACCOUNT_ACCESS"),
    ]
    counter = 100
    for label in config.FROZEN_LABELS:
        if label == "ACCOUNT_ACCESS":
            continue
        for _ in range(3):
            counter += 1
            fake_examples.append(dict(
                example_id=str(counter), tweet_id=f"t{counter}", thread_id=f"th{counter}",
                text="x", label=label,
            ))
    # Ex 2 is POSSIBLE, not MATCH -- must be excluded even though it's numerically earlier
    # than Ex 3/4.
    status_map = {"1": "MATCH", "2": "POSSIBLE", "3": "MATCH", "4": "MATCH"}
    for ex in fake_examples:
        status_map.setdefault(ex["example_id"], "MATCH")

    with patch("evaluation.fewshot_selection.load_training_examples",
               return_value=(fake_examples, [], "fake")), \
         patch("evaluation.fewshot_selection._load_audit_status_map",
               return_value=status_map):
        demos, log = select_fewshot_demonstrations()
        assert log["ACCOUNT_ACCESS"] == ["1", "3", "4"], (
            "POSSIBLE-status Ex 2 must be excluded; only MATCH rows 1/3/4 should be selected"
        )


# ============================================================
# Leakage assertion
# ============================================================

def test_leakage_assertion_detects_overlap():
    demos = {label: [] for label in config.FROZEN_LABELS}
    demos["ACCOUNT_ACCESS"] = [dict(example_id="1", tweet_id="SHARED_TWEET", thread_id="SHARED_THREAD", text="x", label="ACCOUNT_ACCESS")]
    golden = [dict(tweet_id="SHARED_TWEET", thread_id="SHARED_THREAD", text="y", label="ACCOUNT_ACCESS")]
    with pytest.raises(LeakageError):
        assert_fewshot_no_golden_leakage(demos, golden)


def test_leakage_assertion_passes_on_real_data():
    demos, _ = select_fewshot_demonstrations()
    golden = load_golden_examples()
    summary = assert_fewshot_no_golden_leakage(demos, golden)  # must not raise
    assert summary["checks_passed"] == 2
    assert summary["demo_tweet_ids"] == len(flatten(demos))


# ============================================================
# Output schema validation
# ============================================================

def test_validate_classification_output_accepts_valid_dict():
    for label in config.FROZEN_LABELS:
        out = validate_classification_output({"intent": label, "confidence": 0.5, "reasoning": "ok"})
        assert out["intent"] == label


def test_validate_classification_output_rejects_bad_intent():
    with pytest.raises(ValueError):
        validate_classification_output({"intent": "NOT_A_LABEL", "confidence": 0.5, "reasoning": "x"})


def test_validate_classification_output_rejects_missing_keys():
    with pytest.raises(ValueError):
        validate_classification_output({"intent": "ACCOUNT_ACCESS", "reasoning": "x"})
    with pytest.raises(ValueError):
        validate_classification_output({"intent": "ACCOUNT_ACCESS", "confidence": 0.5})


def test_validate_classification_output_rejects_wrong_types():
    with pytest.raises(ValueError):
        validate_classification_output({"intent": "ACCOUNT_ACCESS", "confidence": "high", "reasoning": "x"})
    with pytest.raises(ValueError):
        validate_classification_output({"intent": "ACCOUNT_ACCESS", "confidence": 0.5, "reasoning": 123})


def test_response_json_schema_enum_matches_frozen_labels():
    enum = RESPONSE_JSON_SCHEMA["json_schema"]["schema"]["properties"]["intent"]["enum"]
    assert enum == config.FROZEN_LABELS


# ============================================================
# Prompt construction sanity
# ============================================================

def test_intent_definitions_cover_all_8_labels_verbatim_from_guide():
    defs = load_intent_definitions()
    for label in config.FROZEN_LABELS:
        assert label in defs


def test_fewshot_block_contains_only_text_and_label_no_extra_fields():
    demos, _ = select_fewshot_demonstrations()
    block = render_fewshot_block(demos)
    # every demo's frozen label must appear; no boundary-tag/rule-coverage jargon should leak in
    for label in config.FROZEN_LABELS:
        assert f"Intent: {label}" in block
    for forbidden in ("boundary_tags", "rule_coverage_tags", "provisional", "MATCH", "POSSIBLE", "MISMATCH"):
        assert forbidden not in block


def test_prompt_version_is_a_nonempty_string_constant():
    assert isinstance(INTENT_CLASSIFIER_PROMPT_VERSION, str)
    assert len(INTENT_CLASSIFIER_PROMPT_VERSION) > 0
