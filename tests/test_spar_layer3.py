"""Tests for SPAR Layer 3 quantification and portfolio recommendation."""

from __future__ import annotations

from quorum.methods.spar_layer3 import (
    format_layer3_summary,
    format_portfolio_recommendation,
    run_layer3_quantification,
    save_layer3_artifacts,
)

MODERATOR_SAMPLE = """```json
{
  "type": "consensus_scenario",
  "direction": "negative",
  "magnitude_pct": {"SP500": -4.0, "XLE": -6.0, "XLF": -3.0, "XLK": -5.0, "ITA": 1.0, "XLY": -3.5},
  "confidence": 0.8,
  "primary_transmission_channels": ["Trade Policy Shock", "Inflation Shock"],
  "plausibility_score": 75,
  "consensus_summary": "Tariff shock weighs on growth-sensitive sectors."
}
```

```json
{
  "type": "minority_dissent",
  "direction": "negative",
  "magnitude_pct": {"SP500": -6.0, "XLE": -8.0, "XLF": -4.0, "XLK": -7.0, "ITA": 0.5, "XLY": -5.0},
  "plausibility_score": 62,
  "preserved_dissent_summary": "Tail risk from retaliation."
}
```"""


def test_layer3_computes_var_and_hedge():
    result = run_layer3_quantification(MODERATOR_SAMPLE)
    assert result.consensus_returns["SP500"] != 0
    assert result.consensus_portfolio_pnl_pct < 0
    assert result.var_95_pct > 0
    assert result.hedge_weights["GLD"] > 0 or result.hedge_weights["TLT"] > 0
    assert result.factor_implied_returns
    assert result.factor_shocks


def test_layer3_portfolio_recommendation_trades():
    result = run_layer3_quantification(MODERATOR_SAMPLE)
    rec = result.portfolio_recommendation
    assert rec.trades
    assert any(t.action == "REDUCE" for t in rec.trades)
    assert any(t.action == "ADD_HEDGE" for t in rec.trades)
    assert rec.var_before_pct > 0
    assert rec.recommended_equity_weights


def test_layer3_summary_readable():
    result = run_layer3_quantification(MODERATOR_SAMPLE)
    summary = format_layer3_summary(result)
    assert "VaR" in summary
    assert "Fama-French" in summary
    assert "Hedge Fund Portfolio Recommendation" in summary
    assert "GLD" in summary or "TLT" in summary


def test_format_portfolio_recommendation_standalone():
    result = run_layer3_quantification(MODERATOR_SAMPLE)
    block = format_portfolio_recommendation(result.portfolio_recommendation)
    assert "Recommended trades" in block
    assert "Target equity weights" in block


def test_layer3_confidence_bands_from_round1():
    round1 = {
        "a": {
            "confidence": 0.7,
            "magnitude_pct": {"SP500": -3.0, "XLE": -5.0, "XLF": -2.0, "XLK": -4.0, "ITA": 2.0, "XLY": -2.0},
        },
        "b": {
            "confidence": 0.85,
            "magnitude_pct": {"SP500": -5.0, "XLE": -7.0, "XLF": -4.0, "XLK": -6.0, "ITA": 0.0, "XLY": -5.0},
        },
    }
    result = run_layer3_quantification(MODERATOR_SAMPLE, round1_results=round1, moderator_plausibility=75)
    assert result.confidence_bands is not None
    assert result.confidence_bands.var_95_low_pct != result.confidence_bands.var_95_high_pct
    assert "Sector P&L heatmap" in result.sector_heatmap_text
    assert "confidence bands" in result.sector_heatmap_text.lower()


def test_save_layer3_artifacts_writes_heatmap(tmp_path):
    result = run_layer3_quantification(MODERATOR_SAMPLE)
    save_layer3_artifacts(tmp_path, result)
    assert (tmp_path / "sector_pnl_heatmap.txt").exists()
    text = (tmp_path / "sector_pnl_heatmap.txt").read_text(encoding="utf-8")
    assert "Consens" in text


def test_layer3_positive_scenario_minimal_hedge():
    raw = """{"type": "consensus_scenario", "direction": "positive",
    "magnitude_pct": {"SP500": 2.0, "XLE": 3.0, "XLF": 1.5, "XLK": 2.5, "ITA": 1.0, "XLY": 2.0}}"""
    result = run_layer3_quantification(raw)
    assert result.consensus_portfolio_pnl_pct > 0
    assert sum(result.hedge_weights.values()) == 0
