"""Unit tests for SPAR Debate Continuation Score (DCS)."""

from __future__ import annotations

import json

from quorum.methods.spar_dcs import (
    compute_dcs,
    format_dcs_summary,
    score_disagreement,
    score_information_gain,
    score_rag_exhaustion,
)

ROUND1_DIVERSE = {
    "a": {
        "direction": "negative",
        "magnitude_pct": {"SP500": -6.0, "XLE": 8.0, "XLF": -4.0, "XLK": -7.0, "ITA": 3.0, "XLY": -5.0},
    },
    "b": {
        "direction": "positive",
        "magnitude_pct": {"SP500": 2.0, "XLE": -3.0, "XLF": 1.0, "XLK": 3.0, "ITA": -1.0, "XLY": 2.0},
    },
    "c": {
        "direction": "neutral",
        "magnitude_pct": {"SP500": -1.0, "XLE": 1.0, "XLF": 0.0, "XLK": -2.0, "ITA": 0.5, "XLY": -1.0},
    },
}


def test_score_disagreement_high_when_forecasts_diverge():
    score, detail = score_disagreement(ROUND1_DIVERSE)
    assert score > 0.5
    assert "SP500" in detail


def test_score_information_gain_novelty_between_rounds():
    prior = {"a": "Oil shock dominates via energy channel and WTI pass-through."}
    current = {
        "a": "Tariff retaliation and supply-chain rerouting dominate equity downside.",
        "b": "Consumer demand elasticity limits second-order inflation effects.",
    }
    score, detail = score_information_gain(prior, current)
    assert score > 0.2
    assert "novel" in detail.lower()


def test_score_information_gain_uses_round1_displays_after_round2():
    round1_displays = {
        "a": "**Direction:** negative\n**Magnitude estimates:**\n- SP500: -4.0%",
    }
    current = {"a": "After hearing Economic, I now weight tariff channels more than oil."}
    score, _ = score_information_gain(round1_displays, current)
    assert score > 0.1


def test_score_rag_exhaustion_rises_with_repetition():
    short = "agents debate tariffs growth inflation repeatedly " * 5
    repeated = (short + " ") * 20
    low, _ = score_rag_exhaustion(short)
    high, _ = score_rag_exhaustion(repeated)
    assert high >= low


def test_compute_dcs_explore_when_above_threshold():
    decision = compute_dcs(
        round_number=2,
        round1_results=ROUND1_DIVERSE,
        prior_live_speeches=None,
        current_live_speeches={
            "a": "Political agent, your escalation timeline ignores tariff retaliation risk.",
            "b": "Economic agent, oil pass-through is overstated under current inventory buffers.",
        },
        debate_transcript="round 2 transcript " * 40,
        threshold=0.20,
        max_rounds=5,
        round1_displays={"a": "Round 1 negative SP500 forecast"},
    )
    assert decision.action == "explore"
    assert decision.score > decision.threshold
    assert "explore" in format_dcs_summary(decision).lower() or "EXPLORE" in format_dcs_summary(decision)


def test_compute_dcs_exploit_at_max_rounds():
    decision = compute_dcs(
        round_number=5,
        round1_results=ROUND1_DIVERSE,
        prior_live_speeches={"a": "prior speech"},
        current_live_speeches={"a": "prior speech"},
        debate_transcript="same text " * 200,
        threshold=0.01,
        max_rounds=5,
    )
    assert decision.action == "exploit"
    assert "max cap" in decision.reason.lower()


def test_dcs_decision_serializes_to_dict():
    decision = compute_dcs(
        round_number=2,
        round1_results=ROUND1_DIVERSE,
        prior_live_speeches=None,
        current_live_speeches={"a": "new argument"},
        debate_transcript="debate",
        round1_displays={"a": "old"},
    )
    payload = decision.to_dict()
    json.dumps(payload)
    assert payload["round_number"] == 2
    assert "components" in payload
