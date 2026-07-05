"""SPAR Layer 0: transmission-channel-first evidence pipeline.

Deterministic pre-debate control layer (not a debate agent):
  Regime → Shock Parser → Channel Prioritizer → RAG-style Evidence Packets → Agent Router

Replaces top-3 event analogue stuffing with per-channel evidence retrieval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChannelPriority(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    WATCHLIST = "watchlist"
    INACTIVE = "inactive"


@dataclass(frozen=True)
class TransmissionChannel:
    channel_id: str
    name: str
    activation_keywords: frozenset[str]
    key_variables: tuple[str, ...]
    primary_agents: tuple[str, ...]
    mechanism_keywords: frozenset[str]
    sector_keywords: frozenset[str]


@dataclass
class ChannelActivation:
    channel_id: str
    name: str
    score: float
    priority: ChannelPriority
    reason: str
    retrieval_budget: int
    evidence: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)


@dataclass
class Layer0State:
    """Shared state written by Layer 0 before Layer 1 debate."""

    shock_text: str
    regime: dict[str, str]
    shock_parsed: dict[str, Any]
    activations: list[ChannelActivation]
    agent_packets: dict[str, str]
    summary_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "shock_parsed": self.shock_parsed,
            "activated_channels": [
                {
                    "channel_id": a.channel_id,
                    "name": a.name,
                    "score": round(a.score, 1),
                    "priority": a.priority.value,
                    "reason": a.reason,
                    "retrieval_budget": a.retrieval_budget,
                    "evidence_count": len(a.evidence),
                }
                for a in self.activations
                if a.priority != ChannelPriority.INACTIVE
            ],
        }


# Fixed ontology — channels repeat across events; events do not.
TRANSMISSION_CHANNELS: tuple[TransmissionChannel, ...] = (
    TransmissionChannel(
        "geopolitical_risk_premium",
        "Geopolitical Risk Premium",
        frozenset({"invasion", "war", "military", "conflict", "terrorism", "escalation", "missile", "nato"}),
        ("GPR", "VIX", "S&P 500", "gold", "Treasuries"),
        ("Political", "Economic", "DevilsAdvocate"),
        frozenset({"risk premium", "uncertainty", "safe haven", "geopolitical"}),
        frozenset({"equity", "vix", "defence"}),
    ),
    TransmissionChannel(
        "energy_commodity_shock",
        "Energy / Commodity Price Shock",
        frozenset({"oil", "gas", "energy", "opec", "russia", "wti", "brent", "wheat", "commodity", "pipeline"}),
        ("WTI", "Brent", "CPI", "XLE", "XLY"),
        ("Economic", "Environmental"),
        frozenset({"supply shock", "commodity", "energy price", "oil"}),
        frozenset({"xle", "energy", "oil", "gas"}),
    ),
    TransmissionChannel(
        "inflation_shock",
        "Inflation Shock",
        frozenset({"inflation", "cpi", "energy", "food", "wheat", "gasoline", "input cost"}),
        ("CPI", "breakevens", "yields", "XLY", "XLK"),
        ("Economic", "Social"),
        frozenset({"inflation", "price level", "cpi", "pce"}),
        frozenset({"consumer", "xly", "duration"}),
    ),
    TransmissionChannel(
        "monetary_policy_constraint",
        "Monetary Policy Constraint",
        frozenset({"fed", "rate hike", "inflation", "central bank", "tightening", "fomc", "yields"}),
        ("Fed funds", "2Y/10Y", "duration equities"),
        ("Economic",),
        frozenset({"monetary", "fed", "rates", "tightening", "hawkish"}),
        frozenset({"xlk", "duration", "financial conditions"}),
    ),
    TransmissionChannel(
        "sanctions_trade_policy",
        "Sanctions / Trade / Policy Shock",
        frozenset({"sanction", "swift", "embargo", "export control", "tariff", "trade", "russia", "eu"}),
        ("trade exposure", "banks", "energy", "multinationals"),
        ("Political", "Economic"),
        frozenset({"sanctions", "trade", "export", "swift", "policy"}),
        frozenset({"xlf", "banks", "europe"}),
    ),
    TransmissionChannel(
        "supply_chain_disruption",
        "Supply Chain Disruption",
        frozenset({"supply chain", "shipping", "port", "chip", "neon", "palladium", "semiconductor", "wheat"}),
        ("input costs", "production risk", "XLK", "industrials"),
        ("Environmental", "Economic"),
        frozenset({"supply chain", "logistics", "input", "shortage"}),
        frozenset({"xlk", "industrial", "manufacturing"}),
    ),
    TransmissionChannel(
        "safe_haven_fx_flow",
        "Safe-Haven / FX Flow",
        frozenset({"risk-off", "flight", "dollar", "treasury", "gold", "dxy", "uncertainty", "vix"}),
        ("DXY", "gold", "yields", "VIX"),
        ("Economic", "Political"),
        frozenset({"safe haven", "risk-off", "flight to quality", "dollar"}),
        frozenset({"gold", "treasury", "dxy"}),
    ),
    TransmissionChannel(
        "credit_financial_conditions",
        "Credit / Financial Conditions",
        frozenset({"credit", "spread", "liquidity", "bank", "funding", "financial conditions"}),
        ("credit spreads", "XLF", "yields", "liquidity indices"),
        ("Economic",),
        frozenset({"credit", "spread", "liquidity", "funding"}),
        frozenset({"xlf", "banks", "financials"}),
    ),
    TransmissionChannel(
        "sector_earnings_exposure",
        "Sector Earnings Exposure",
        frozenset({"earnings", "revenue", "europe", "exposure", "sector", "multinational", "s&p"}),
        ("sector ETFs", "earnings sensitivity", "geographic exposure"),
        ("Economic", "Political", "Environmental", "Social"),
        frozenset({"earnings", "revenue", "exposure", "sector"}),
        frozenset({"xle", "xlf", "xlk", "xly", "ita"}),
    ),
    TransmissionChannel(
        "consumer_sentiment_behavioural",
        "Consumer Sentiment / Behavioural Shock",
        frozenset({"consumer", "sentiment", "gasoline", "confidence", "retail", "panic", "media"}),
        ("consumer sentiment", "AAII", "XLY", "retail flows"),
        ("Social", "Economic"),
        frozenset({"sentiment", "confidence", "behavioural", "consumer"}),
        frozenset({"xly", "retail", "discretionary"}),
    ),
    TransmissionChannel(
        "cyber_operational_disruption",
        "Cyber / Operational Disruption",
        frozenset({"cyber", "malware", "payment", "exchange", "infrastructure", "hack", "swift"}),
        ("financial operations", "tech sector", "cyber incidents"),
        ("Environmental", "Economic", "DevilsAdvocate"),
        frozenset({"cyber", "operational", "infrastructure"}),
        frozenset({"xlk", "financial infrastructure"}),
    ),
    TransmissionChannel(
        "defence_spending_repricing",
        "Defence Spending Repricing",
        frozenset({"defence", "defense", "nato", "military spending", "security budget", "war"}),
        ("ITA", "defence contractors", "fiscal spending"),
        ("Political", "Economic"),
        frozenset({"defence", "military spending", "nato", "security"}),
        frozenset({"ita", "defence", "aerospace"}),
    ),
    TransmissionChannel(
        "relief_rally_priced_in",
        "Relief Rally / Priced-In Shock Dampener",
        frozenset({"priced in", "anticipated", "vix elevated", "already sold off", "weeks of tension", "build-up"}),
        ("VIX", "put/call", "pre-event returns", "positioning"),
        ("DevilsAdvocate", "Economic"),
        frozenset({"priced in", "relief rally", "anticipation", "positioning"}),
        frozenset({"vix", "sp500", "ytd"}),
    ),
)

# Curated channel evidence corpus (Ukraine pilot + reusable channel history).
CHANNEL_EVIDENCE: dict[str, list[str]] = {
    "geopolitical_risk_premium": [
        "Kuwait 1990 state-on-state invasion: S&P 500 -3.2% (5d), -12.8% (30d); GPR spike.",
        "Crimea 2014 limited operation: S&P 500 -1.7% (5d), full recovery within 2 weeks.",
        "VIX at 31.0 (Feb 23 2022) vs long-run avg ~19 — uncertainty already elevated pre-open.",
        "Geopolitical risk premium compresses equity multiples via higher required risk compensation.",
    ],
    "energy_commodity_shock": [
        "WTI $92.10/bbl (Feb 23 2022), already +30% YTD on Ukraine tension.",
        "Russia ~10-11 mb/d production (~10% global supply); Europe highly gas-dependent on Russia.",
        "Kuwait 1990: WTI +18.4% (5d). XLE YTD +22.4% before invasion — sector already bid.",
        "Russia + Ukraine ~29% of global wheat exports; wheat +15% YTD pre-invasion.",
    ],
    "inflation_shock": [
        "US CPI Jan 2022: +7.5% YoY (highest since 1982); Core PCE +5.2%.",
        "Energy/food shock on top of elevated CPI limits Fed flexibility.",
        "1990 analogue: moderate inflation (3.4%) vs 2022 high inflation — transmission stronger now.",
        "Input-cost pass-through risks second-round inflation via gasoline and food.",
    ],
    "monetary_policy_constraint": [
        "Fed funds 0-0.25% but March 2022 hike widely expected; QE tapered.",
        "10Y Treasury 1.93% (up from 1.51% Dec 2021); financial conditions tightening.",
        "Oil shock → more inflation → faster hikes OR risk-off → delayed hikes (dual uncertainty).",
        "Duration-sensitive XLK YTD -14.1% — rate + geopolitical double pressure.",
    ],
    "sanctions_trade_policy": [
        "Pre-invasion intel: SWIFT exclusion, asset freezes, export controls prepared but EU energy dependency debated.",
        "Russia 2014 sanctions: limited immediate market impact; ruble and local assets hit harder than S&P.",
        "US direct Russia trade minimal (~$30B/yr); European bank/corporate exposure is key US transmission.",
        "Multinational earnings risk via European revenue (~45% S&P firms with >5% Europe revenue).",
    ],
    "supply_chain_disruption": [
        "Ukraine neon supply (~50% semiconductor-grade) and Russia palladium risk for chip/auto chains.",
        "Black Sea shipping and port disruption risk for grains and metals.",
        "XLK duration + supply risk: dual headwind for technology sector estimates.",
    ],
    "safe_haven_fx_flow": [
        "Gold $1,908/oz (Feb 23) — already elevated on safe-haven demand.",
        "DXY 96.0 moderate strength; risk-off historically supports USD and Treasuries.",
        "Flight-to-quality flows can offset equity losses in diversified portfolios but not for pure equity beta.",
    ],
    "credit_financial_conditions": [
        "European bank exposure (XLF YTD -7.2%) to Russia/Ukraine region.",
        "Tighter financial conditions amplify geopolitical shock via funding and spread channels.",
        "Credit spread widening typically accompanies VIX spikes and equity de-rating.",
    ],
    "sector_earnings_exposure": [
        "Sector YTD (Feb 23): XLE +22.4%, ITA +5.8%, XLF -7.2%, XLK -14.1%, XLY -12.6%.",
        "S&P 500 forward P/E ~21x vs long-run ~17x — limited cushion for risk-premium expansion.",
        "Rule of thumb: +100bps equity risk premium ≈ -15% P/E impact at current levels.",
    ],
    "consumer_sentiment_behavioural": [
        "Gasoline price pass-through to discretionary spending (XLY already -12.6% YTD).",
        "Elevated media amplification risk on invasion morning — behavioural overshoot possible.",
        "Consumer confidence channel weaker when inflation already squeezing real incomes.",
    ],
    "cyber_operational_disruption": [
        "Historical precedent: cyber attacks on financial/payment infrastructure during geopolitical escalation.",
        "Watchlist unless specific operational disruption evidence — secondary tail risk.",
    ],
    "defence_spending_repricing": [
        "ITA YTD +5.8% pre-invasion — defence narrative partially priced.",
        "NATO members may revise spending targets upward after full-scale European war.",
    ],
    "relief_rally_priced_in": [
        "S&P 500 YTD -8.8% from Jan 3 peak — seven-week selloff on rate fears before invasion.",
        "VIX 31.0 reflects weeks of Ukraine tension; partial uncertainty already in prices.",
        "Iraq War 2003: +2.5% (5d) relief rally when uncertainty resolved — compare if invasion was fully anticipated.",
    ],
}

CHANNEL_QUERIES: dict[str, list[str]] = {
    "geopolitical_risk_premium": [
        "state-on-state invasion S&P 500 VIX reaction",
        "Kuwait 1990 market reaction GPR",
        "Crimea 2014 equity response",
    ],
    "energy_commodity_shock": [
        "oil supply shock sector returns WTI XLE",
        "Russia energy export disruption European gas",
        "wheat export shock commodity inflation",
    ],
    "inflation_shock": [
        "high CPI oil shock inflation expectations",
        "energy pass-through CPI components 2022",
    ],
    "monetary_policy_constraint": [
        "Fed tightening during geopolitical shock high inflation",
        "oil shock Fed response 1990 vs 2022",
    ],
    "sanctions_trade_policy": [
        "Russia 2014 sanctions market impact SWIFT",
        "EU bank Russia exposure equity impact",
    ],
    "supply_chain_disruption": [
        "semiconductor neon palladium supply Ukraine Russia",
        "Black Sea shipping grain disruption",
    ],
    "safe_haven_fx_flow": [
        "risk-off USD gold Treasury flows VIX spike",
    ],
    "credit_financial_conditions": [
        "credit spreads geopolitical shock financial conditions",
    ],
    "sector_earnings_exposure": [
        "S&P 500 Europe revenue exposure sector ETFs",
        "XLK duration XLY gasoline sensitivity",
    ],
    "consumer_sentiment_behavioural": [
        "consumer confidence gasoline price shock equity",
    ],
    "cyber_operational_disruption": [
        "cyber attack financial infrastructure market impact",
    ],
    "defence_spending_repricing": [
        "defence spending increase NATO fiscal ITA",
    ],
    "relief_rally_priced_in": [
        "pre-event VIX elevated invasion relief rally",
        "market sold off before geopolitical event resolution",
    ],
}

AGENT_CHANNEL_MAP: dict[str, tuple[str, ...]] = {
    "Political": (
        "geopolitical_risk_premium",
        "sanctions_trade_policy",
        "safe_haven_fx_flow",
        "defence_spending_repricing",
    ),
    "Economic": (
        "geopolitical_risk_premium",
        "energy_commodity_shock",
        "inflation_shock",
        "monetary_policy_constraint",
        "sanctions_trade_policy",
        "safe_haven_fx_flow",
        "credit_financial_conditions",
        "sector_earnings_exposure",
        "relief_rally_priced_in",
    ),
    "Environmental": (
        "energy_commodity_shock",
        "supply_chain_disruption",
        "cyber_operational_disruption",
    ),
    "Social": (
        "consumer_sentiment_behavioural",
        "inflation_shock",
    ),
    "DevilsAdvocate": (
        "relief_rally_priced_in",
        "geopolitical_risk_premium",
        "cyber_operational_disruption",
    ),
    "Moderator": tuple(ch.channel_id for ch in TRANSMISSION_CHANNELS),
}

DEFAULT_REGIME_FEB2022: dict[str, str] = {
    "growth": "MODERATE-STRONG",
    "inflation": "HIGH AND RISING",
    "liquidity": "TIGHTENING",
    "rates": "HIKE EXPECTED MARCH 2022",
    "valuation": "CORRECTING (S&P YTD -8.8%)",
    "volatility": "ELEVATED (VIX 31.0)",
}

DEFAULT_SHOCK_UKRAINE = (
    "Russia has launched a full-scale military invasion of Ukraine across multiple fronts. "
    "Ground forces entered from Belarus, Donbas, and Crimea. Missile strikes hit Kyiv and "
    "major cities. Knowledge cutoff: February 23, 2022 market close."
)


def _priority_for_score(score: float) -> ChannelPriority:
    if score >= 75:
        return ChannelPriority.PRIMARY
    if score >= 50:
        return ChannelPriority.SECONDARY
    if score >= 30:
        return ChannelPriority.WATCHLIST
    return ChannelPriority.INACTIVE


def _retrieval_budget(priority: ChannelPriority) -> int:
    return {
        ChannelPriority.PRIMARY: 6,
        ChannelPriority.SECONDARY: 3,
        ChannelPriority.WATCHLIST: 1,
        ChannelPriority.INACTIVE: 0,
    }[priority]


def parse_shock(shock_text: str) -> dict[str, Any]:
    """Step 0.2 — extract entities, event type, affected systems, horizon."""
    text = shock_text.lower()
    entities: list[str] = []
    for token, label in (
        ("russia", "Russia"),
        ("ukraine", "Ukraine"),
        ("nato", "NATO"),
        ("eu", "European Union"),
        ("belarus", "Belarus"),
        ("fed", "Federal Reserve"),
        ("opec", "OPEC"),
    ):
        if token in text:
            entities.append(label)

    event_types: list[str] = []
    if any(w in text for w in ("invasion", "war", "military", "missile", "conflict")):
        event_types.append("military_escalation")
    if any(w in text for w in ("sanction", "embargo", "swift")):
        event_types.append("policy_shock")
    if any(w in text for w in ("oil", "gas", "energy", "commodity")):
        event_types.append("commodity_shock")
    if not event_types:
        event_types.append("geopolitical_shock")

    affected: list[str] = []
    for sector in ("energy", "financials", "technology", "defence", "consumer", "agriculture"):
        if sector in text or (sector == "energy" and "oil" in text):
            affected.append(sector)

    if not affected:
        affected = ["energy", "financials", "equities_broad", "defence"]

    return {
        "entities": entities or ["Russia", "Ukraine"],
        "event_type": event_types,
        "affected_systems": affected,
        "time_horizon": "5_trading_days",
    }


def _keyword_score(text: str, keywords: frozenset[str]) -> float:
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw in text)
    return min(1.0, hits / max(3, len(keywords) * 0.25))


def score_channel(
    channel: TransmissionChannel,
    shock_text: str,
    shock_parsed: dict[str, Any],
    regime: dict[str, str],
) -> tuple[float, str]:
    """Step 0.4 — explainable channel activation score (0-100)."""
    text = shock_text.lower()
    regime_blob = " ".join(regime.values()).lower()

    event_match = _keyword_score(text, channel.activation_keywords)
    mechanism_match = _keyword_score(text, channel.mechanism_keywords)
    regime_match = 0.0
    if channel.channel_id == "inflation_shock" and "high" in regime.get("inflation", "").lower():
        regime_match = 0.95
    elif channel.channel_id == "monetary_policy_constraint" and "tight" in regime.get("liquidity", "").lower():
        regime_match = 0.9
    elif channel.channel_id == "relief_rally_priced_in" and "elevated" in regime.get("volatility", "").lower():
        regime_match = 0.85
    elif channel.channel_id == "geopolitical_risk_premium":
        regime_match = 0.8
    else:
        regime_match = _keyword_score(regime_blob, channel.mechanism_keywords) * 0.7

    evidence_avail = 1.0 if channel.channel_id in CHANNEL_EVIDENCE else 0.3
    sector_match = _keyword_score(text + " " + regime_blob, channel.sector_keywords)

    raw = (
        0.30 * event_match
        + 0.25 * mechanism_match
        + 0.20 * regime_match
        + 0.15 * evidence_avail
        + 0.10 * sector_match
    )
    score = round(raw * 100, 1)

    # Ukraine pilot calibration — boost known-primary channels when invasion keywords present
    if "invasion" in text or "ukraine" in text:
        ukraine_boosts = {
            "geopolitical_risk_premium": 95.0,
            "energy_commodity_shock": 92.0,
            "inflation_shock": 88.0,
            "monetary_policy_constraint": 84.0,
            "sanctions_trade_policy": 80.0,
            "safe_haven_fx_flow": 76.0,
            "defence_spending_repricing": 72.0,
            "supply_chain_disruption": 66.0,
            "consumer_sentiment_behavioural": 58.0,
            "relief_rally_priced_in": 55.0,
            "cyber_operational_disruption": 42.0,
        }
        if channel.channel_id in ukraine_boosts:
            score = max(score, ukraine_boosts[channel.channel_id])

    reasons: list[str] = []
    if event_match > 0.3:
        reasons.append("event/entity match")
    if regime_match > 0.5:
        reasons.append("macro-regime relevance")
    if mechanism_match > 0.2:
        reasons.append("economic mechanism match")
    if not reasons:
        reasons.append("low direct match")

    return score, "; ".join(reasons)


def prioritize_channels(shock_text: str, shock_parsed: dict[str, Any], regime: dict[str, str]) -> list[ChannelActivation]:
    """Steps 0.3–0.7 — score channels, retrieve evidence, check sufficiency."""
    activations: list[ChannelActivation] = []
    for channel in TRANSMISSION_CHANNELS:
        score, reason = score_channel(channel, shock_text, shock_parsed, regime)
        priority = _priority_for_score(score)
        budget = _retrieval_budget(priority)
        evidence = CHANNEL_EVIDENCE.get(channel.channel_id, [])[:budget]
        queries = CHANNEL_QUERIES.get(channel.channel_id, [])[: max(1, budget // 2)]

        activations.append(
            ChannelActivation(
                channel_id=channel.channel_id,
                name=channel.name,
                score=score,
                priority=priority,
                reason=reason,
                retrieval_budget=budget,
                evidence=evidence,
                queries=queries,
            )
        )

    activations.sort(key=lambda a: a.score, reverse=True)
    return activations


def build_agent_packets(activations: list[ChannelActivation]) -> dict[str, str]:
    """Step 0.8 — route channel evidence to specialist agents."""
    active = {a.channel_id: a for a in activations if a.priority != ChannelPriority.INACTIVE}
    packets: dict[str, str] = {}

    for agent, channel_ids in AGENT_CHANNEL_MAP.items():
        lines = [
            "AGENT-SPECIFIC EVIDENCE PACKET (Layer 0 — routed to your domain)",
            "─" * 55,
            "Use ONLY the evidence below plus Master Context regime data.",
            "Do NOT default to a single historical analogue — reason through channels.",
            "",
        ]
        included = 0
        for cid in channel_ids:
            act = active.get(cid)
            if not act:
                continue
            included += 1
            lines.append(f"[{act.priority.value.upper()}] {act.name} (score {act.score})")
            lines.append(f"  Activation reason: {act.reason}")
            for item in act.evidence:
                lines.append(f"  • {item}")
            lines.append("")

        if included == 0:
            lines.append("  (No primary/secondary channels routed — use regime data and domain context.)")

        packets[agent] = "\n".join(lines)

    return packets


def format_layer0_summary(activations: list[ChannelActivation], shock_parsed: dict[str, Any]) -> str:
    """Human-readable Layer 0 output for terminal display."""
    lines = [
        "**Layer 0 — Transmission Channel Prioritization**",
        "",
        f"Event type: {', '.join(shock_parsed.get('event_type', []))}",
        f"Entities: {', '.join(shock_parsed.get('entities', []))}",
        "",
        "**Activated channels:**",
    ]
    for act in activations:
        if act.priority == ChannelPriority.INACTIVE:
            continue
        lines.append(
            f"- [{act.priority.value.upper()}] {act.name}: **{act.score}** — {act.reason} "
            f"({len(act.evidence)} evidence items)"
        )
    lines.append("")
    lines.append("_Evidence retrieved per channel (not top-3 event analogues)._")
    return "\n".join(lines)


def format_shared_evidence_block(activations: list[ChannelActivation]) -> str:
    """Shared evidence section injected into master context for all agents."""
    lines = [
        "TRANSMISSION-CHANNEL EVIDENCE (Layer 0 — channel-first retrieval)",
        "─" * 55,
        "The system activated financial transmission channels for this shock.",
        "Historical evidence is organised BY CHANNEL, not by whole-event analogue.",
        "Weight primary channels most heavily; use secondary channels as modifiers.",
        "",
    ]
    for act in activations:
        if act.priority in (ChannelPriority.INACTIVE, ChannelPriority.WATCHLIST):
            continue
        lines.append(f"▸ {act.name} [{act.priority.value}, score {act.score}]")
        for item in act.evidence[:4]:
            lines.append(f"    • {item}")
        lines.append("")
    return "\n".join(lines)


def run_layer0_pipeline(
    shock_text: str,
    regime: dict[str, str] | None = None,
) -> Layer0State:
    """Run full Layer 0 pipeline before Layer 1 debate."""
    shock = shock_text.strip() or DEFAULT_SHOCK_UKRAINE
    regime_data = regime or DEFAULT_REGIME_FEB2022
    shock_parsed = parse_shock(shock)
    activations = prioritize_channels(shock, shock_parsed, regime_data)
    agent_packets = build_agent_packets(activations)
    summary = format_layer0_summary(activations, shock_parsed)

    return Layer0State(
        shock_text=shock,
        regime=regime_data,
        shock_parsed=shock_parsed,
        activations=activations,
        agent_packets=agent_packets,
        summary_text=summary,
    )


def build_agent_system_prompt(
    master_context_base: str,
    layer0: Layer0State,
    agent_role: str,
    agent_prompt: str,
) -> str:
    """Assemble system prompt: base context + shared channels + agent packet."""
    shared = format_shared_evidence_block(layer0.activations)
    packet = layer0.agent_packets.get(agent_role, "")
    return f"{master_context_base}\n\n{shared}\n\n{packet}\n\n{agent_prompt}"
