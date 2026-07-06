"""Integration tests for SPAR debate orchestration (mocked LLM)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from quorum.agents import get_role_assignments
from quorum.methods.base import PhaseMarker, SynthesisResult, TeamTextMessage
from quorum.methods.spar import SparMethod

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
        return json.dumps({"plausibility_score": 72, "primary_transmission_channels": ["energy_commodity_shock"]})

    with patch.object(SparMethod, "_get_model_response", new=AsyncMock(side_effect=fake_response)):
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
    assert "Activated channels" in layer0_msgs[0].content

    round1 = [m for m in messages if isinstance(m, TeamTextMessage) and m.round_type == "round1"]
    round2 = [m for m in messages if isinstance(m, TeamTextMessage) and m.round_type == "round2"]
    assert len(round1) == 5
    assert len(round2) == 5

    assert any("Primary channel" in m.content for m in round1)
    assert all("LIVE DEBATE" not in m.content for m in round1)

    synthesis = [m for m in messages if isinstance(m, SynthesisResult)]
    assert len(synthesis) == 1
    assert synthesis[0].method == "spar"


@pytest.mark.asyncio
async def test_spar_system_prompts_include_channel_packets():
    from quorum.methods.spar_layer0 import run_layer0_pipeline

    layer0 = run_layer0_pipeline("Russia invasion of Ukraine")
    method = SparMethod(model_ids=["mock-model"])
    economic = method._system_for_agent(layer0, "Economic", "agent2_economic_fiscal_market.txt")

    assert "TRANSMISSION-CHANNEL EVIDENCE" in economic
    assert "AGENT-SPECIFIC EVIDENCE PACKET" in economic
    assert "Energy" in economic or "Commodity" in economic
    assert "channel_assessment" in economic or "channel-first" in economic.lower()
