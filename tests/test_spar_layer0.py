"""Tests for SPAR Layer 0 transmission-channel-first pipeline."""

from quorum.methods.spar_layer0 import (
    ChannelPriority,
    detect_scenario_id,
    run_layer0_pipeline,
    score_channel,
    TRANSMISSION_CHANNELS,
)


def test_ukraine_primary_channels_activated():
    layer0 = run_layer0_pipeline("Russia invasion of Ukraine full-scale military escalation")
    active = [a for a in layer0.activations if a.priority == ChannelPriority.PRIMARY]
    active_ids = {a.channel_id for a in active}

    assert "geopolitical_risk_premium" in active_ids
    assert "energy_commodity_shock" in active_ids
    assert "inflation_shock" in active_ids
    assert "monetary_policy_constraint" in active_ids
    assert len(active) >= 5


def test_relief_rally_secondary_not_primary():
    layer0 = run_layer0_pipeline("Russia invasion of Ukraine")
    by_id = {a.channel_id: a for a in layer0.activations}
    relief = by_id["relief_rally_priced_in"]
    assert relief.priority in (ChannelPriority.SECONDARY, ChannelPriority.WATCHLIST)


def test_agent_packets_routed():
    layer0 = run_layer0_pipeline("Russia invasion of Ukraine")
    assert "Political" in layer0.agent_packets
    assert "Economic" in layer0.agent_packets
    assert "Energy" in layer0.agent_packets["Economic"] or "Commodity" in layer0.agent_packets["Economic"]
    assert "relief" in layer0.agent_packets["DevilsAdvocate"].lower() or "Priced" in layer0.agent_packets["DevilsAdvocate"]


def test_evidence_per_channel_not_single_analogue_block():
    layer0 = run_layer0_pipeline("Russia invasion of Ukraine")
    economic_packet = layer0.agent_packets["Economic"]
    assert "AGENT-SPECIFIC EVIDENCE PACKET" in economic_packet
    assert "[PRIMARY]" in economic_packet or "[primary]" in economic_packet
    assert economic_packet.count("•") >= 3


def test_layer0_summary_for_ui():
    layer0 = run_layer0_pipeline("Russia invasion of Ukraine")
    assert "Layer 0" in layer0.summary_text
    assert "Activated channels" in layer0.summary_text


def test_score_channel_deterministic():
    channel = next(ch for ch in TRANSMISSION_CHANNELS if ch.channel_id == "energy_commodity_shock")
    shock = "Russia oil gas invasion Ukraine energy supply"
    parsed = {"entities": ["Russia"], "event_type": ["military_escalation"], "scenario_id": "ukraine_2022"}
    regime = {"inflation": "HIGH AND RISING", "liquidity": "TIGHTENING", "volatility": "ELEVATED"}
    score, reason = score_channel(channel, shock, parsed, regime)
    assert score >= 75
    assert reason


LIBERATION_DAY_SHOCK = (
    "On April 2, 2025, the United States announced broad reciprocal tariffs under the "
    "'Liberation Day' trade policy package with sector-specific rates and immediate timelines."
)


def test_liberation_day_scenario_detected():
    assert detect_scenario_id(LIBERATION_DAY_SHOCK) == "liberation_day_2025"


def test_liberation_day_trade_channels_primary():
    layer0 = run_layer0_pipeline(LIBERATION_DAY_SHOCK)
    assert layer0.shock_parsed["scenario_id"] == "liberation_day_2025"
    assert "trade_policy_shock" in layer0.shock_parsed["event_type"]
    assert "Russia" not in layer0.shock_parsed["entities"]

    by_id = {a.channel_id: a for a in layer0.activations}
    trade = by_id["sanctions_trade_policy"]
    assert trade.priority == ChannelPriority.PRIMARY
    assert trade.score >= 75
    assert any("Liberation Day" in item or "tariff" in item.lower() for item in trade.evidence)

    assert "geopolitical" not in layer0.summary_text.lower() or "Scenario: liberation_day_2025" in layer0.summary_text


def test_liberation_day_agent_packets_use_trade_evidence():
    layer0 = run_layer0_pipeline(LIBERATION_DAY_SHOCK)
    economic = layer0.agent_packets["Economic"]
    assert "Trade" in economic or "trade" in economic or "tariff" in economic.lower()
    assert economic.count("•") >= 3
