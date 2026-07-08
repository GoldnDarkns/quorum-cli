"""Integration tests for SPAR debate orchestration (mocked LLM)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quorum.agents import get_role_assignments
from quorum.methods.base import PhaseMarker, SynthesisResult, TeamTextMessage
from quorum.methods.spar import SparMethod, format_moderator_synthesis

ROUND1_JSON = json.dumps(
    {
        "agent_id": "test_agent",
        "round": 1,
        "event": "russia_ukraine_invasion_20220224",
        "direction": "negative",
        "magnitude_pct": {"SP500": -4.0, "XLE": 5.0, "XLF": -3.0, "XLK": -5.0, "ITA": 2.0, "XLY": -6.0},
        "confidence": 0.7,
        "key_assumption": "Oil sustains above $100",
        "supporting_evidence": ["WTI $92.10", "CPI 7.5%", "VIX 31.0"],
        "transmission_channels": [
            "Energy/Commodity Shock → WTI spike → XLE re-rating",
            "Inflation Shock → Fed constraint",
            "Geopolitical Risk Premium → equity de-rating",
        ],
        "channel_assessment": {
            "primary_channel": "Energy / Commodity Price Shock",
            "channel_adjustments": "High CPI amplifies energy pass-through vs 1990",
        },
    }
)


def _mock_spar_settings(**overrides):
    base = dict(
        spar_dcs_enabled=False,
        spar_dcs_threshold=0.35,
        spar_max_debate_rounds=5,
        spar_plausibility_gate_enabled=False,
        spar_plausibility_threshold=60.0,
        spar_human_review_block=True,
        spar_fsr_benchmark_enabled=False,
        spar_fsr_moderator_weight=0.55,
        spar_fsr_weight=0.45,
        spar_layer3_enabled=False,
    )
    base.update(overrides)
    return MagicMock(**base)


async def _collect_spar_stream(task: str) -> list[Any]:
    roles = get_role_assignments("spar", ["mock-model"])
    method = SparMethod(model_ids=["mock-model"], role_assignments=roles)
    call_idx = 0

    async def fake_response(_model_id: str, system: str, user_message: str) -> str:
        nonlocal call_idx
        call_idx += 1
        # Layer 0 is deterministic — no LLM. First call is Round 1 Political.
        if call_idx <= 5:
            assert "TRANSMISSION-CHANNEL EVIDENCE" in system or "Layer 0" in system
            assert "AGENT-SPECIFIC EVIDENCE PACKET" in system
            assert "analogue_assessment" not in system.lower() or "channel" in system.lower()
            return ROUND1_JSON
        if call_idx <= 10:
            assert "LIVE DEBATE" in user_message
            assert "ROUND 1" in user_message
            if call_idx > 6:
                assert "speaking now" in user_message or "ROUND 2" in user_message
            return f"Live debate speech from agent call {call_idx}. Economic agent, I disagree on oil."
        return json.dumps(
            {
                "type": "consensus_scenario",
                "plausibility_score": 72,
                "primary_transmission_channels": ["energy_commodity_shock"],
            }
        )

    with patch.object(SparMethod, "_get_model_response", new=AsyncMock(side_effect=fake_response)), patch(
        "quorum.methods.spar.maybe_persist_spar_run", return_value=None
    ), patch(
        "quorum.methods.spar.get_settings",
        return_value=_mock_spar_settings(),
    ):
        return [msg async for msg in method.run_stream(task)]


@pytest.mark.asyncio
async def test_spar_four_phases_with_layer0_and_live_debate():
    task = "Russia full-scale invasion of Ukraine"
    messages = await _collect_spar_stream(task)

    phases = [m for m in messages if isinstance(m, PhaseMarker)]
    assert len(phases) == 4
    assert phases[0].phase == 1
    assert phases[-1].phase == 4

    layer0_msgs = [m for m in messages if isinstance(m, TeamTextMessage) and m.round_type == "layer0"]
    assert len(layer0_msgs) == 1
    assert "Layer 0" in layer0_msgs[0].content
    assert "Activated for debate" in layer0_msgs[0].content

    round1 = [m for m in messages if isinstance(m, TeamTextMessage) and m.round_type == "round1"]
    round2 = [m for m in messages if isinstance(m, TeamTextMessage) and m.round_type == "round2"]
    assert len(round1) == 5
    assert len(round2) == 5

    assert any("Primary channel" in m.content for m in round1)
    assert all("LIVE DEBATE" not in m.content for m in round1)

    synthesis = [m for m in messages if isinstance(m, SynthesisResult)]
    assert len(synthesis) == 1
    assert synthesis[0].method == "spar"
    assert synthesis[0].consensus == "CLEARED"
    assert "Moderator synthesis" in synthesis[0].synthesis
    assert "SPAR pipeline summary" in synthesis[0].differences


def test_format_moderator_synthesis_readable():
    raw = """{"type": "consensus_scenario", "direction": "negative", "plausibility_score": 85,
    "magnitude_pct": {"SP500": -2.5}, "consensus_summary": "Mild risk-off."}

    {"type": "minority_dissent", "dissenting_agents": ["Social Agent"],
    "preserved_dissent_summary": "Energy resilience possible."}"""
    formatted = format_moderator_synthesis(raw)
    assert "Consensus scenario" in formatted
    assert "Minority dissent" in formatted
    assert "Social Agent" in formatted


@pytest.mark.asyncio
async def test_spar_human_review_when_plausibility_gate_fails():
    task = "Russia full-scale invasion of Ukraine"
    roles = get_role_assignments("spar", ["mock-model"])
    method = SparMethod(model_ids=["mock-model"], role_assignments=roles)
    call_idx = 0

    async def fake_response(_model_id: str, _system: str, _user_message: str) -> str:
        nonlocal call_idx
        call_idx += 1
        if call_idx <= 5:
            return ROUND1_JSON
        if call_idx <= 10:
            return "Live debate speech."
        return """{"type": "consensus_scenario", "plausibility_score": 40, "consensus_summary": "weak"}"""

    with patch.object(SparMethod, "_get_model_response", new=AsyncMock(side_effect=fake_response)), patch(
        "quorum.methods.spar.maybe_persist_spar_run", return_value=None
    ), patch(
        "quorum.methods.spar.get_settings",
        return_value=_mock_spar_settings(
            spar_plausibility_gate_enabled=True,
            spar_fsr_benchmark_enabled=False,
        ),
    ):
        messages = [msg async for msg in method.run_stream(task)]

    from quorum.methods.base import HumanReviewRequired, SynthesisResult

    gate_msgs = [
        m
        for m in messages
        if isinstance(m, TeamTextMessage) and m.round_type == "plausibility_gate"
    ]
    assert len(gate_msgs) == 1
    assert any(isinstance(m, HumanReviewRequired) for m in messages)
    synthesis = [m for m in messages if isinstance(m, SynthesisResult)]
    assert synthesis[0].consensus == "HUMAN_REVIEW"


@pytest.mark.asyncio
async def test_spar_shows_dcs_when_enabled():
    task = "Russia full-scale invasion of Ukraine"
    roles = get_role_assignments("spar", ["mock-model"])
    method = SparMethod(model_ids=["mock-model"], role_assignments=roles)
    call_idx = 0

    async def fake_response(_model_id: str, _system: str, _user_message: str) -> str:
        nonlocal call_idx
        call_idx += 1
        if call_idx <= 5:
            return ROUND1_JSON
        if call_idx <= 10:
            return "Live debate speech with new tariff and oil arguments."
        return json.dumps({"plausibility_score": 72})

    with patch.object(SparMethod, "_get_model_response", new=AsyncMock(side_effect=fake_response)), patch(
        "quorum.methods.spar.maybe_persist_spar_run", return_value=None
    ), patch(
        "quorum.methods.spar.get_settings",
        return_value=_mock_spar_settings(
            spar_dcs_enabled=True,
            spar_fsr_benchmark_enabled=False,
        ),
    ), patch(
        "quorum.methods.spar.compute_dcs",
        return_value=MagicMock(
            to_dict=lambda: {"action": "exploit", "dcs_score": 0.2},
            action="exploit",
            round_number=2,
            score=0.2,
            threshold=0.35,
            max_rounds=5,
            reason="mock exploit",
            components=MagicMock(
                disagreement=0.3,
                info_gain=0.2,
                rag_exhaustion=0.1,
                disagreement_detail="",
                info_gain_detail="",
                rag_exhaustion_detail="",
            ),
        ),
    ), patch(
        "quorum.methods.spar.format_dcs_summary", return_value="**DCS** exploit"
    ):
        messages = [msg async for msg in method.run_stream(task)]

    dcs_msgs = [m for m in messages if isinstance(m, TeamTextMessage) and m.round_type == "dcs"]
    assert len(dcs_msgs) == 1
    assert "DCS" in dcs_msgs[0].content or "exploit" in dcs_msgs[0].content.lower()


@pytest.mark.asyncio
async def test_spar_system_prompts_include_channel_packets():
    from quorum.methods.spar_layer0 import run_layer0_pipeline

    layer0 = run_layer0_pipeline("Russia invasion of Ukraine")
    method = SparMethod(model_ids=["mock-model"])
    economic = method._system_for_agent(
        layer0, "Economic", "agent2_economic_fiscal_market.txt", "Russia invasion of Ukraine"
    )

    assert "TRANSMISSION-CHANNEL EVIDENCE" in economic
    assert "AGENT-SPECIFIC EVIDENCE PACKET" in economic
    assert "Energy" in economic or "Commodity" in economic
    assert "channel_assessment" in economic or "channel-first" in economic.lower()
