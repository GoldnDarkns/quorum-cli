"""Tests for Federal Reserve FSR plausibility benchmark."""

from __future__ import annotations

from quorum.methods.spar_fsr_benchmark import (
    format_fsr_benchmark_summary,
    score_fsr_alignment,
)
from quorum.methods.spar_plausibility_gate import evaluate_plausibility_gate

TARIFF_CONSENSUS = {
    "type": "consensus_scenario",
    "plausibility_score": 78,
    "consensus_summary": (
        "Broad reciprocal tariffs raise trade policy uncertainty, disrupt supply chains, "
        "and trigger risk-off equity repricing with growth concerns."
    ),
    "primary_transmission_channels": ["Trade Policy Shock", "Inflation Shock"],
    "magnitude_pct": {"SP500": -4.0, "XLE": -5.0, "XLF": -3.0, "XLK": -6.0, "ITA": 1.0, "XLY": -4.0},
}


def test_fsr_alignment_high_for_tariff_scenario():
    result = score_fsr_alignment(TARIFF_CONSENSUS, "liberation_day_2025")
    assert result.alignment_score > 15.0
    assert result.matched_passages
    assert "fsr_trade" in result.matched_passages[0].passage_id


def test_fsr_summary_includes_citation():
    result = score_fsr_alignment(TARIFF_CONSENSUS, "liberation_day_2025")
    summary = format_fsr_benchmark_summary(result)
    assert "Federal Reserve FSR" in summary
    assert "federalreserve.gov" in summary


def test_gate_uses_composite_with_fsr():
    raw = """{"type": "consensus_scenario", "plausibility_score": 70, "consensus_summary": "Trade tariffs and supply chain disruption weigh on equities and raise policy uncertainty."}"""
    decision, fsr = evaluate_plausibility_gate(
        raw,
        threshold=60,
        scenario_id="liberation_day_2025",
        fsr_enabled=True,
    )
    assert fsr is not None
    assert decision.composite_score is not None
    assert decision.fsr_alignment_score is not None
