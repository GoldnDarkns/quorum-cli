"""Tests for SPAR Layer 0 transmission-channel-first pipeline."""

from quorum.methods.spar_layer0 import (
    ChannelPriority,
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
    parsed = {"entities": ["Russia"], "event_type": ["military_escalation"]}
    regime = {"inflation": "HIGH AND RISING", "liquidity": "TIGHTENING", "volatility": "ELEVATED"}
    score, reason = score_channel(channel, shock, parsed, regime)
    assert score >= 75
    assert reason
