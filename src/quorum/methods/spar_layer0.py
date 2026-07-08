"""SPAR Layer 0: transmission-channel-first evidence pipeline.

Deterministic pre-debate control layer (not a debate agent):
  Regime → Shock Parser → Channel Prioritizer → RAG-style Evidence Packets → Agent Router

Replaces top-3 event analogue stuffing with per-channel evidence retrieval.
"""

from __future__ import annotations

import re
from pathlib import Path
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
    score_components: dict[str, float] = field(default_factory=dict)


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
            "channel_rankings": [
                {
                    "channel_id": a.channel_id,
                    "name": a.name,
                    "score": round(a.score, 1),
                    "priority": a.priority.value,
                    "reason": a.reason,
                    "retrieval_budget": a.retrieval_budget,
                    "evidence_count": len(a.evidence),
                    "score_components": a.score_components,
                }
                for a in self.activations
            ],
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

DEFAULT_REGIME_APR2025: dict[str, str] = {
    "growth": "MODERATE — Q1 2025 GDP tracking ~2.3% annualised",
    "inflation": "MODERATING BUT STICKY — CPI ~3.1% YoY (Mar 2025)",
    "liquidity": "NEUTRAL — Fed funds 4.25-4.50%; QT continuing at reduced pace",
    "rates": "PATIENT — FOMC on hold; cuts priced H2 2025 if growth softens",
    "valuation": "FULL — S&P 500 near YTD highs; forward P/E ~21x",
    "volatility": "ELEVATED ON POLICY RISK — VIX ~22 pre-announcement; trade headlines dominant",
    "trade": "UNCERTAIN — reciprocal tariff framework debated for weeks; positioning cautious",
}

DEFAULT_REGIME_GENERIC: dict[str, str] = {
    "growth": "MODERATE",
    "inflation": "MODERATING",
    "liquidity": "NEUTRAL",
    "rates": "DATA-DEPENDENT",
    "valuation": "FAIR TO FULL",
    "volatility": "NORMAL TO ELEVATED",
}

SCENARIO_REGIMES: dict[str, dict[str, str]] = {
    "ukraine_2022": DEFAULT_REGIME_FEB2022,
    "liberation_day_2025": DEFAULT_REGIME_APR2025,
    "generic": DEFAULT_REGIME_GENERIC,
}

# Scenario-specific channel score floors (applied after base scoring).
SCENARIO_CHANNEL_BOOSTS: dict[str, dict[str, float]] = {
    "ukraine_2022": {
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
    },
    "liberation_day_2025": {
        "sanctions_trade_policy": 96.0,
        "sector_earnings_exposure": 90.0,
        "inflation_shock": 88.0,
        "supply_chain_disruption": 86.0,
        "consumer_sentiment_behavioural": 82.0,
        "safe_haven_fx_flow": 80.0,
        "credit_financial_conditions": 78.0,
        "monetary_policy_constraint": 74.0,
        "geopolitical_risk_premium": 68.0,
        "energy_commodity_shock": 62.0,
        "relief_rally_priced_in": 58.0,
        "defence_spending_repricing": 45.0,
        "cyber_operational_disruption": 35.0,
    },
}

# Scenario-specific evidence prepended to base channel corpus (most relevant first).
SCENARIO_CHANNEL_EVIDENCE: dict[str, dict[str, list[str]]] = {
    "liberation_day_2025": {
        "sanctions_trade_policy": [
            "Liberation Day Apr 2025: broad reciprocal tariffs on major trading partners; sector-specific rates; immediate implementation timeline.",
            "2018-19 US-China tariff rounds: S&P 500 -6.8% peak-to-trough over tariff escalation window; XLF and XLK underperformed.",
            "Smoot-Hawley analogue: trade-war escalation compresses multinationals' earnings via input costs and retaliation risk.",
            "US direct import exposure concentrated in consumer (XLY), tech supply chain (XLK), and industrials — tariff pass-through risk high.",
        ],
        "inflation_shock": [
            "Tariff shock = negative supply shock: import prices rise → goods CPI pressure even when headline inflation moderating.",
            "Apr 2025 CPI ~3.1% YoY — less buffer than 2022; Fed may face stagflation-lite trade-off if growth slows AND prices re-accelerate.",
            "Breakevens typically rise on tariff headlines unless growth scare dominates (yields fell Apr 2 on growth concern).",
        ],
        "supply_chain_disruption": [
            "Reciprocal tariffs disrupt just-in-time inventory and semiconductor/industrial input chains (XLK, ITA supply links).",
            "2018 tariff episode: supply-chain re-routing costs hit margins before consumer pass-through fully visible.",
        ],
        "sector_earnings_exposure": [
            "Pre-event sector sensitivity: XLK (import inputs + China revenue), XLY (consumer pass-through), XLF (credit + trade finance), XLE (less direct unless energy retaliation).",
            "Equity futures fell sharply overnight Apr 2 2025 — broad beta risk-off across sectors except potential short-term defensives.",
        ],
        "consumer_sentiment_behavioural": [
            "Trade-policy uncertainty elevates AAII bearish readings and retail risk-off; discretionary (XLY) most sentiment-sensitive.",
            "Media amplification of tariff rates → faster behavioural overshoot vs fundamentals (social channel).",
        ],
        "safe_haven_fx_flow": [
            "Apr 2 2025: USD strengthened overnight; classic risk-off FX pattern alongside falling equity futures.",
            "Bond yields moved lower on growth concerns — flight-to-quality in Treasuries despite inflation fears.",
        ],
        "relief_rally_priced_in": [
            "Weeks of tariff headline risk pre-Apr 2 — partial positioning for policy shock; VIX ~22 not crisis-level.",
            "Devil's Advocate channel: if retaliation muted or exemptions broad, relief rally possible after initial gap-down.",
        ],
        "monetary_policy_constraint": [
            "Fed on hold Apr 2025 but cannot ease if tariff inflation re-accelerates; limits put under risk assets.",
        ],
    },
}

MASTER_CONTEXT_FILES: dict[str, str] = {
    "ukraine_2022": "master_context.txt",
    "liberation_day_2025": "master_context_liberation_day_2025.txt",
    "generic": "master_context.txt",
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


def _retrieval_budget(priority: ChannelPriority, compact: bool = False) -> int:
    if compact:
        return {
            ChannelPriority.PRIMARY: 2,
            ChannelPriority.SECONDARY: 1,
            ChannelPriority.WATCHLIST: 0,
            ChannelPriority.INACTIVE: 0,
        }[priority]
    return {
        ChannelPriority.PRIMARY: 6,
        ChannelPriority.SECONDARY: 3,
        ChannelPriority.WATCHLIST: 1,
        ChannelPriority.INACTIVE: 0,
    }[priority]


def detect_scenario_id(shock_text: str) -> str:
    """Classify shock into a scenario profile for regime, evidence, and boosts."""
    text = shock_text.lower()
    if any(
        k in text
        for k in ("liberation day", "reciprocal tariff", "tariff", "trade policy", "trade war")
    ):
        return "liberation_day_2025"
    if any(k in text for k in ("ukraine", "invasion", "russia", "belarus", "crimea", "donbas")):
        return "ukraine_2022"
    return "generic"


def get_regime_for_shock(shock_text: str) -> dict[str, str]:
    return dict(SCENARIO_REGIMES.get(detect_scenario_id(shock_text), DEFAULT_REGIME_GENERIC))


def _merged_channel_evidence(scenario_id: str) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {k: list(v) for k, v in CHANNEL_EVIDENCE.items()}
    for channel_id, items in SCENARIO_CHANNEL_EVIDENCE.get(scenario_id, {}).items():
        merged[channel_id] = items + merged.get(channel_id, [])
    return merged


def resolve_master_context(shock_text: str, prompts_dir: Path) -> str:
    """Load scenario-appropriate master context (event + regime + JSON schema)."""
    scenario_id = detect_scenario_id(shock_text)
    fname = MASTER_CONTEXT_FILES.get(scenario_id, "master_context.txt")
    path = prompts_dir / fname
    if not path.exists():
        path = prompts_dir / "master_context.txt"
    return path.read_text(encoding="utf-8")


def parse_shock(shock_text: str) -> dict[str, Any]:
    """Step 0.2 — extract entities, event type, affected systems, horizon."""
    text = shock_text.lower()
    scenario_id = detect_scenario_id(shock_text)
    entities: list[str] = []

    entity_map = (
        ("united states", "United States"),
        ("u.s.", "United States"),
        ("us ", "United States"),
        ("china", "China"),
        ("european union", "European Union"),
        ("eu ", "European Union"),
        ("mexico", "Mexico"),
        ("canada", "Canada"),
        ("russia", "Russia"),
        ("ukraine", "Ukraine"),
        ("nato", "NATO"),
        ("belarus", "Belarus"),
        ("fed", "Federal Reserve"),
        ("opec", "OPEC"),
    )
    for token, label in entity_map:
        if token in text and label not in entities:
            entities.append(label)

    event_types: list[str] = []
    if any(w in text for w in ("tariff", "trade policy", "trade war", "reciprocal", "liberation day")):
        event_types.append("trade_policy_shock")
    if any(w in text for w in ("invasion", "war", "military", "missile", "conflict")):
        event_types.append("military_escalation")
    if any(w in text for w in ("sanction", "embargo", "swift", "export control")):
        event_types.append("sanctions_shock")
    if any(w in text for w in ("oil", "gas", "energy", "commodity")):
        event_types.append("commodity_shock")
    if not event_types:
        if scenario_id == "liberation_day_2025":
            event_types.append("trade_policy_shock")
        elif scenario_id == "ukraine_2022":
            event_types.append("military_escalation")
        else:
            event_types.append("macro_policy_shock")

    affected: list[str] = []
    sector_keywords = (
        ("energy", ("energy", "oil", "gas", "xle")),
        ("financials", ("financial", "bank", "xlf", "credit")),
        ("technology", ("technology", "semiconductor", "xlk", "chip")),
        ("defence", ("defence", "defense", "ita", "military spending")),
        ("consumer", ("consumer", "retail", "xly", "discretionary")),
        ("industrials", ("industrial", "manufacturing", "supply chain")),
        ("agriculture", ("agriculture", "wheat", "food")),
    )
    for sector, keywords in sector_keywords:
        if any(kw in text for kw in keywords):
            affected.append(sector)

    if not affected:
        if scenario_id == "liberation_day_2025":
            affected = ["technology", "consumer", "financials", "industrials", "equities_broad"]
        elif scenario_id == "ukraine_2022":
            affected = ["energy", "financials", "equities_broad", "defence"]
        else:
            affected = ["equities_broad", "financials"]

    if not entities:
        if scenario_id == "liberation_day_2025":
            entities = ["United States", "Trading partners"]
        elif scenario_id == "ukraine_2022":
            entities = ["Russia", "Ukraine"]
        else:
            entities = ["United States"]

    return {
        "scenario_id": scenario_id,
        "entities": entities,
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
) -> tuple[float, str, dict[str, float]]:
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
    elif channel.channel_id == "sanctions_trade_policy" and "trade" in regime.get("trade", "").lower():
        regime_match = 0.92
    elif channel.channel_id == "geopolitical_risk_premium" and detect_scenario_id(shock_text) == "ukraine_2022":
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
    base_score = round(raw * 100, 1)
    score = base_score

    scenario_id = detect_scenario_id(shock_text)
    boosts = SCENARIO_CHANNEL_BOOSTS.get(scenario_id, {})
    scenario_floor = boosts.get(channel.channel_id)
    if scenario_floor is not None and scenario_floor > score:
        score = scenario_floor

    components: dict[str, float] = {
        "event_pct": round(event_match * 100, 1),
        "mechanism_pct": round(mechanism_match * 100, 1),
        "regime_pct": round(regime_match * 100, 1),
        "evidence_pct": round(evidence_avail * 100, 1),
        "sector_pct": round(sector_match * 100, 1),
        "base_score": base_score,
    }
    if scenario_floor is not None and scenario_floor > base_score:
        components["scenario_floor"] = scenario_floor

    reasons: list[str] = []
    if scenario_floor is not None and scenario_floor > base_score:
        reasons.append("scenario profile floor applied")
    if event_match > 0.3:
        reasons.append("event/entity match")
    if regime_match > 0.5:
        reasons.append("macro-regime relevance")
    if mechanism_match > 0.2:
        reasons.append("economic mechanism match")
    if not reasons:
        reasons.append("low direct match")

    return score, "; ".join(reasons), components


def prioritize_channels(
    shock_text: str,
    shock_parsed: dict[str, Any],
    regime: dict[str, str],
    channel_evidence: dict[str, list[str]] | None = None,
    compact: bool = False,
) -> list[ChannelActivation]:
    """Steps 0.3–0.7 — score channels, retrieve evidence, check sufficiency."""
    evidence_corpus = channel_evidence or _merged_channel_evidence(
        shock_parsed.get("scenario_id", detect_scenario_id(shock_text))
    )
    activations: list[ChannelActivation] = []
    for channel in TRANSMISSION_CHANNELS:
        score, reason, components = score_channel(channel, shock_text, shock_parsed, regime)
        priority = _priority_for_score(score)
        budget = _retrieval_budget(priority, compact=compact)
        evidence = evidence_corpus.get(channel.channel_id, [])[:budget]
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
                score_components=components,
            )
        )

    activations.sort(key=lambda a: a.score, reverse=True)
    return activations


def build_agent_packets(activations: list[ChannelActivation], compact: bool = False) -> dict[str, str]:
    """Step 0.8 — route channel evidence to specialist agents."""
    active = {a.channel_id: a for a in activations if a.priority != ChannelPriority.INACTIVE}
    packets: dict[str, str] = {}
    max_channels = 2 if compact else 99
    max_bullets = 2 if compact else 99

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
            if included >= max_channels:
                break
            act = active.get(cid)
            if not act:
                continue
            included += 1
            lines.append(f"[{act.priority.value.upper()}] {act.name} (score {act.score})")
            lines.append(f"  Activation reason: {act.reason}")
            for item in act.evidence[:max_bullets]:
                lines.append(f"  • {item}")
            lines.append("")

        if included == 0:
            lines.append("  (No primary/secondary channels routed — use regime data and domain context.)")

        packets[agent] = "\n".join(lines)

    return packets


def _format_score_drivers(components: dict[str, float]) -> str:
    """One-line interpretable breakdown of what drove the channel score."""
    drivers: list[str] = []
    for key, label in (
        ("event_pct", "shock keywords"),
        ("mechanism_pct", "transmission mechanism"),
        ("regime_pct", "macro regime fit"),
        ("evidence_pct", "historical corpus depth"),
        ("sector_pct", "sector/asset exposure"),
    ):
        value = components.get(key, 0.0)
        if value >= 20:
            drivers.append(f"{label} {value:.0f}%")
    floor = components.get("scenario_floor")
    base = components.get("base_score")
    if floor is not None and base is not None and floor > base:
        drivers.append(f"scenario floor raised {base:.0f} -> {floor:.0f}")
    return "; ".join(drivers) if drivers else "minimal overlap with shock text and regime"


def _count_by_priority(activations: list[ChannelActivation]) -> dict[ChannelPriority, int]:
    counts = {p: 0 for p in ChannelPriority}
    for act in activations:
        counts[act.priority] += 1
    return counts


def format_layer0_summary(
    activations: list[ChannelActivation],
    shock_parsed: dict[str, Any],
    regime: dict[str, str] | None = None,
    evidence_corpus: dict[str, list[str]] | None = None,
) -> str:
    """Human-readable Layer 0 output for terminal display."""
    counts = _count_by_priority(activations)
    total = len(activations)
    scenario_id = shock_parsed.get("scenario_id", "generic")

    lines = [
        "**Layer 0 — Transmission Channel Prioritization**",
        "",
        f"Scenario profile: **{scenario_id}**",
        f"Event type: {', '.join(shock_parsed.get('event_type', []))}",
        f"Entities: {', '.join(shock_parsed.get('entities', []))}",
        f"Affected systems: {', '.join(shock_parsed.get('affected_systems', []))}",
        f"Horizon: {shock_parsed.get('time_horizon', '5_trading_days')}",
        "",
        f"**Channel ontology:** {total} transmission channels scored (not a single event analogue).",
        (
            f"**Activation tiers:** {counts[ChannelPriority.PRIMARY]} PRIMARY (>=70), "
            f"{counts[ChannelPriority.SECONDARY]} SECONDARY (>=50), "
            f"{counts[ChannelPriority.WATCHLIST]} WATCHLIST (>=30), "
            f"{counts[ChannelPriority.INACTIVE]} INACTIVE (<30)."
        ),
        "",
        "**How the score works (0-100):** keyword fit between your shock text and each channel's "
        "activation vocabulary, weighted by macro regime at cutoff (growth, inflation, liquidity, "
        "volatility, trade), plus whether we hold curated historical evidence for that channel. "
        "Known scenario profiles (Ukraine 2022, Liberation Day tariffs) apply score floors so "
        "channels with strong past analogues are not dropped when the shock text is brief.",
        "",
        "Weights: shock keywords 30% | mechanism 25% | regime 20% | evidence corpus 15% | sector 10%.",
        "Retrieval budget: PRIMARY up to 6 bullets | SECONDARY 3 | WATCHLIST 1 | INACTIVE 0.",
        "",
    ]

    if regime:
        lines.append("**Macro regime at cutoff (anchors scoring):**")
        for key in ("growth", "inflation", "liquidity", "rates", "valuation", "volatility", "trade"):
            if key in regime:
                lines.append(f"- {key.replace('_', ' ').title()}: {regime[key]}")
        lines.append("")

    active = [a for a in activations if a.priority != ChannelPriority.INACTIVE]
    inactive = [a for a in activations if a.priority == ChannelPriority.INACTIVE]

    if active:
        lines.append("**Activated for debate & evidence retrieval:**")
        lines.append("")
        for act in active:
            lines.append(f"**[{act.priority.value.upper()}] {act.name} — score {act.score}**")
            lines.append(f"Why: {act.reason}")
            lines.append(f"Drivers: {_format_score_drivers(act.score_components)}")
            preview = act.evidence
            if not preview and evidence_corpus:
                preview = evidence_corpus.get(act.channel_id, [])[:1]
            if preview:
                lines.append("Historical evidence (channel-specific, not whole-event analogue):")
                for item in preview[:3]:
                    lines.append(f"  • {item}")
            else:
                lines.append("  _(No evidence retrieved — score below watchlist threshold.)_")
            lines.append("")

    if inactive:
        lines.append(f"**Inactive this run ({len(inactive)} channels — score < 30, no RAG budget):**")
        for act in inactive:
            preview = ""
            if evidence_corpus:
                corpus_item = evidence_corpus.get(act.channel_id, [])
                if corpus_item:
                    preview = f" | e.g. {corpus_item[0][:90]}{'...' if len(corpus_item[0]) > 90 else ''}"
            lines.append(
                f"- {act.name}: **{act.score}** — {act.reason}{preview}"
            )
        lines.append("")

    if scenario_id == "generic":
        lines.append(
            "_Tip: name the event explicitly (e.g. Liberation Day Apr 2025 tariffs, Ukraine Feb 2022) "
            "to unlock the full scenario profile, regime snapshot, and channel score floors._"
        )
        lines.append("")

    lines.append(
        "_Evidence is organised by transmission channel so agents reason through mechanisms, "
        "not one blended historical event._"
    )
    return "\n".join(lines)


def format_shared_evidence_block(activations: list[ChannelActivation], compact: bool = False) -> str:
    """Shared evidence section injected into master context for all agents."""
    lines = [
        "TRANSMISSION-CHANNEL EVIDENCE (Layer 0 — channel-first retrieval)",
        "─" * 55,
        "The system activated financial transmission channels for this shock.",
        "Historical evidence is organised BY CHANNEL, not by whole-event analogue.",
        "Weight primary channels most heavily; use secondary channels as modifiers.",
        "",
    ]
    max_channels = 3 if compact else 99
    max_bullets = 2 if compact else 4
    shown = 0
    for act in activations:
        if act.priority in (ChannelPriority.INACTIVE, ChannelPriority.WATCHLIST):
            continue
        if compact and act.priority != ChannelPriority.PRIMARY:
            continue
        if shown >= max_channels:
            break
        shown += 1
        lines.append(f"▸ {act.name} [{act.priority.value}, score {act.score}]")
        for item in act.evidence[:max_bullets]:
            lines.append(f"    • {item}")
        lines.append("")
    return "\n".join(lines)


def run_layer0_pipeline(
    shock_text: str,
    regime: dict[str, str] | None = None,
    compact: bool = False,
) -> Layer0State:
    """Run full Layer 0 pipeline before Layer 1 debate."""
    shock = shock_text.strip() or DEFAULT_SHOCK_UKRAINE
    shock_parsed = parse_shock(shock)
    scenario_id = shock_parsed.get("scenario_id", "generic")
    regime_data = regime or get_regime_for_shock(shock)
    evidence_corpus = _merged_channel_evidence(scenario_id)
    activations = prioritize_channels(shock, shock_parsed, regime_data, evidence_corpus, compact=compact)
    agent_packets = build_agent_packets(activations, compact=compact)
    summary = format_layer0_summary(
        activations,
        shock_parsed,
        regime=regime_data,
        evidence_corpus=evidence_corpus,
    )

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
    compact: bool = False,
) -> str:
    """Assemble system prompt: base context + shared channels + agent packet."""
    shared = format_shared_evidence_block(layer0.activations, compact=compact)
    packet = layer0.agent_packets.get(agent_role, "")
    return f"{master_context_base}\n\n{shared}\n\n{packet}\n\n{agent_prompt}"
