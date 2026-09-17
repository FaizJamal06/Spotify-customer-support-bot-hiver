"""
Tests for evaluation/agent.py.

No real API calls anywhere in this suite. classify()/generate_reply() are
exercised against a mocked provider (matching this project's established
mocking style for evaluation/generation.py's tests); retrieve_top_k() is
monkeypatched to avoid a real embedding call. evaluation/triage.py's
apply_triage_rules() is used for real -- it is pure Python with no
API/network dependency, so mocking it would test less, not more, and this
lets these tests confirm the wiring actually reaches the shipped triage
rules rather than a stub.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluation.agent import DEFAULT_K, handle_message


def _mock_provider(intent="APP_TECH_ISSUE", confidence=0.9, reply="Mock reply."):
    provider = MagicMock()
    provider.classify.return_value = dict(
        intent=intent, confidence=confidence, reasoning="mock reasoning",
    )
    provider.generate_reply.return_value = dict(
        reply=reply,
        grounding_notes=dict(
            grounded_in_evidence=[], grounded_in_customer_message=[], unsupported_or_generic=[],
        ),
    )
    return provider


def _fake_retrieved_pairs(n):
    return [
        (f"cust {i}", f"brand {i}", 0.5 + i * 0.01, dict(tweet_id=str(i)))
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Schema of the returned dict
# ---------------------------------------------------------------------------

def test_returns_all_required_keys():
    provider = _mock_provider()
    with patch("evaluation.agent.retrieve_top_k", return_value=_fake_retrieved_pairs(3)):
        result = handle_message("my app keeps crashing", provider=provider)

    assert set(result.keys()) == {
        "customer_text", "intent", "confidence", "classifier_reasoning",
        "triage_decision", "triage_reason", "triage_tier",
        "retrieved_evidence", "generated_reply", "grounding_notes",
    }


def test_types_are_correct():
    provider = _mock_provider()
    with patch("evaluation.agent.retrieve_top_k", return_value=_fake_retrieved_pairs(3)):
        result = handle_message("my app keeps crashing", provider=provider)

    assert isinstance(result["customer_text"], str)
    assert isinstance(result["intent"], str)
    assert isinstance(result["confidence"], (int, float))
    assert isinstance(result["classifier_reasoning"], str)
    assert result["triage_decision"] in ("AUTO_HANDLE", "HUMAN_ESCALATION")
    assert isinstance(result["triage_reason"], str)
    assert result["triage_tier"] in ("TIER_1", "TIER_2", "TIER_3", "NONE")
    assert isinstance(result["retrieved_evidence"], list)
    assert isinstance(result["generated_reply"], str)
    assert isinstance(result["grounding_notes"], dict)


def test_retrieved_evidence_shape_matches_k():
    provider = _mock_provider()
    with patch("evaluation.agent.retrieve_top_k", return_value=_fake_retrieved_pairs(3)) as mock_retrieve:
        result = handle_message("hello", k=3, provider=provider)

    assert len(result["retrieved_evidence"]) == 3
    for item in result["retrieved_evidence"]:
        assert set(item.keys()) == {"customer_text", "brand_text", "similarity"}
    mock_retrieve.assert_called_once_with("hello", 3)


def test_k0_returns_empty_evidence():
    provider = _mock_provider()
    with patch("evaluation.agent.retrieve_top_k", return_value=[]) as mock_retrieve:
        result = handle_message("hello", k=0, provider=provider)

    assert result["retrieved_evidence"] == []
    mock_retrieve.assert_called_once_with("hello", 0)


# ---------------------------------------------------------------------------
# Call order / wiring -- each component called correctly, in the right order
# ---------------------------------------------------------------------------

def test_classify_called_with_customer_text_and_fixed_blocks():
    provider = _mock_provider()
    with patch("evaluation.agent.retrieve_top_k", return_value=[]):
        handle_message("please help me log in", provider=provider)

    provider.classify.assert_called_once()
    args = provider.classify.call_args[0]
    assert args[0] == "please help me log in"
    assert isinstance(args[1], str) and len(args[1]) > 0  # few-shot block
    assert isinstance(args[2], str) and len(args[2]) > 0  # intent definitions block


def test_triage_uses_classified_intent_and_confidence():
    provider = _mock_provider(intent="UNKNOWN_OTHER", confidence=0.4)
    with patch("evaluation.agent.retrieve_top_k", return_value=[]):
        result = handle_message("???", provider=provider)

    # UNKNOWN_OTHER always escalates via Tier 1 -- confirms triage actually ran
    # against classify()'s real returned intent, not a hard-coded value.
    assert result["triage_decision"] == "HUMAN_ESCALATION"
    assert result["triage_tier"] == "TIER_1"


def test_generate_reply_receives_retrieved_pairs_and_no_triage_coupling():
    provider = _mock_provider(intent="APP_TECH_ISSUE", confidence=0.9)
    pairs = _fake_retrieved_pairs(2)
    with patch("evaluation.agent.retrieve_top_k", return_value=pairs):
        handle_message("crash on startup", provider=provider)

    provider.generate_reply.assert_called_once()
    call_args = provider.generate_reply.call_args[0]
    assert call_args[0] == "crash on startup"
    assert call_args[1] == "APP_TECH_ISSUE"
    assert call_args[2] is None  # decoupled from triage -- matches every evaluated call site
    # (run_k_ablation_sweep.py:110-112 calls generate_reply(..., None, retrieved))
    assert call_args[3] == pairs


def test_retrieve_runs_before_generate_and_triage_stays_decoupled():
    """apply_triage_rules() is real (pure Python), so it can't be tracked in the
    same mock call log as classify/retrieve/generate -- instead this asserts the
    orderable fact that DOES prove sequencing: generate_reply() receives the SAME
    retrieved_pairs object retrieve_top_k() returned (proving retrieve ran before
    generate). It also confirms triage's real decision is still computed and
    returned to the caller while explicitly NOT reaching generate_reply() -- the
    two evaluated paths (classify->triage, classify->retrieve->generate) stay
    separate internally and are combined only in the returned dict, per
    ARCHITECTURE.md's "no hidden classify->retrieve->generate->triage chain"."""
    provider = _mock_provider(intent="UNKNOWN_OTHER", confidence=0.5)
    pairs = _fake_retrieved_pairs(1)
    with patch("evaluation.agent.retrieve_top_k", return_value=pairs) as mock_retrieve:
        result = handle_message("???", provider=provider)

    mock_retrieve.assert_called_once()
    generate_call = provider.generate_reply.call_args[0]
    assert generate_call[3] == pairs                          # retrieve ran before generate
    assert generate_call[2] is None                           # triage's output never reaches generate_reply()
    assert result["triage_decision"] == "HUMAN_ESCALATION"    # triage still ran and is in the output
    assert result["triage_tier"] == "TIER_1"                  # real triage rule, not a stub


# ---------------------------------------------------------------------------
# Default k
# ---------------------------------------------------------------------------

def test_default_k_is_3():
    assert DEFAULT_K == 3


def test_default_k_used_when_not_specified():
    provider = _mock_provider()
    with patch("evaluation.agent.retrieve_top_k", return_value=[]) as mock_retrieve:
        handle_message("hello", provider=provider)

    mock_retrieve.assert_called_once_with("hello", DEFAULT_K)
