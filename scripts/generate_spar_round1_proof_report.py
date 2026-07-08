#!/usr/bin/env python3
"""Generate complete SPAR proof-of-work report (scrollable HTML + PDF)."""

from __future__ import annotations

import base64
import html
import json
import re
import textwrap
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIR = Path(r"C:\Users\madha\spar_outputs\run_20260708_003305")
ASSETS_SRC = ROOT.parent / "assets" if (ROOT.parent / "assets").exists() else ROOT / "assets"

NAVY = (20, 40, 100)
SLATE = (60, 70, 90)

SCREENSHOTS = [
    ("01_startup.png", "Session startup", "Quorum v1.1.4 initialized with six Ollama models, SPAR method, and scenario: Liberation Day Tariffs (Apr 2, 2025). Phase 1 begins Layer 0 channel prioritization."),
    ("02_benchmarks.png", "Model benchmark analysis (Phi4 Mini — Moderator)", "demo-diverse preset: stack ranking, frontier references, per-benchmark leaders, and role-swap recommendations before domain agents run."),
    ("03_layer0_start.png", "Layer 0 — channel prioritization (part 1)", "Scenario profile liberation_day_2025, macro regime anchors, and PRIMARY channels with scores and historical evidence."),
    ("04_layer0_end.png", "Layer 0 — channel prioritization (part 2)", "Remaining PRIMARY/SECONDARY/WATCHLIST channels; Layer 0 complete — awaiting Round 1 domain analysis."),
    ("05_political_r1.png", "Round 1 — Phi4 Mini Latest [POLITICAL]", "Domain analysis JSON: escalation trajectory, alliance responses, GPR implications, activated market mechanisms."),
    ("06_economic_r1.png", "Round 1 — Nemotron Mini 4b [ECONOMIC]", "Risk-off assessment with channel scores (Energy, Monetary Policy, Inflation, Relief Rally)."),
    ("07_environmental_r1.png", "Round 1 — Granite3.3 8b [ENVIRONMENTAL]", "Transmission channels: Supply Chain Disruption, Energy/Commodity, Cyber/Operational."),
    ("08_social_r1.png", "Round 1 — Llama3.1 8b [SOCIAL]", "Behavioural channel scores, predicted market impact, key indicators under pressure."),
    ("09_devils_advocate_r1.png", "Round 1 — Qwen2.5 7b [DEVIL'S ADVOCATE]", "Key assumption on priced-in shock; Round 1 Domain Analysis complete."),
    ("10_political_r2.png", "Round 2 — Phi4 Mini Latest [POLITICAL]", "Live cross-examination: responds to Economic Agent on energy/commodity shock, safe-haven flows, GPR, and social consumption effects."),
    ("11_economic_r2.png", "Round 2 — Nemotron Mini 4b [ECONOMIC]", "Disagrees that geopolitical tensions are fully priced in; argues GPR drives USD safe-haven flows over commodities."),
    ("12_environmental_r2.png", "Round 2 — Granite3.3 8b [ENVIRONMENTAL]", "Inflation pass-through via energy channel; cites 10Y Treasury 1.93%, pump $4.50/gal, falling real wages."),
    ("13_social_r2.png", "Round 2 — Llama3.1 8b [SOCIAL]", "Challenges Economic Agent on safe-haven USD flows; emphasizes GPR and consumer financial stress."),
    ("14_devils_advocate_dcs_r2.png", "Round 2 — Qwen2.5 7b [DEVIL'S ADVOCATE] + DCS", "Synthesizes political/economic/environmental/social channels; Phi4 Mini [DCS] scores debate continuation."),
    ("15_political_economic_r3.png", "Round 3 — Phi4 Mini [POLITICAL] + Nemotron Mini [ECONOMIC]", "Political shifts toward consumer behavior channels; Economic concedes price pass-through importance."),
    ("16_environmental_social_r3.png", "Round 3 — Granite3.3 [ENVIRONMENTAL] + Llama3.1 [SOCIAL]", "Environmental evolves to consumer purchasing power; Social challenges safe-haven assumptions and household debt."),
    ("17_devils_advocate_dcs_r3.png", "Round 3 — Qwen2.5 [DEVIL'S ADVOCATE] + DCS", "Devil's Advocate prioritizes consumer disposable income; DCS 0.746 EXPLORE to Round 4."),
    ("18_political_r4.png", "Round 4 — Phi4 Mini Latest [POLITICAL]", "Synthesizes peer responses; shifts to Consumer Behavior/Energy Inflation and Household Debt Dynamics channels."),
    ("19_economic_environmental_r4.png", "Round 4 — Nemotron Mini [ECONOMIC] + Granite3.3 [ENVIRONMENTAL]", "Economic agrees on consumption stress; Environmental proposes dual-thread framework (immediate shock + investor sentiment)."),
    ("20_social_devils_advocate_r4.png", "Round 4 — Llama3.1 [SOCIAL] + Qwen2.5 [DEVIL'S ADVOCATE]", "Social integrates shock + sentiment channels; Devil's Advocate re-emphasizes sustained GPR risk-off environment."),
    ("21_dcs_r4.png", "Round 4 — Phi4 Mini Latest [DCS]", "DCS 0.769 EXPLORE — final live round (Round 5) will run."),
    ("22_political_economic_r5.png", "Round 5 — Phi4 Mini [POLITICAL] + Nemotron Mini [ECONOMIC]", "Final round: balanced immediate shock vs GPR; Economic integrates all transmission channels."),
    ("23_environmental_social_r5.png", "Round 5 — Granite3.3 [ENVIRONMENTAL] + Llama3.1 [SOCIAL]", "Multi-pronged framework; Social rejects artificial shock-vs-GPR dichotomy."),
    ("24_devils_advocate_dcs_r5.png", "Round 5 — Qwen2.5 [DEVIL'S ADVOCATE] + DCS", "GPR anchored in Layer 0; DCS 0.761 EXPLOIT — debate stops, passes to Moderator."),
    ("25_moderator_synthesis.png", "Moderator — Gemma3 4b [MODERATOR] Layer 2", "Consensus + minority dissent synthesis with sector magnitude estimates."),
    ("26_plausibility_layer3_start.png", "Plausibility Gate + Layer 3 (part 1)", "Gate PROCEED (composite 70); portfolio P&L, VaR, factor shocks, sector shocks."),
    ("27_layer3_portfolio_detail.png", "Layer 3 — Portfolio Quantification (part 2)", "Sector heatmap, hedge weights, recommended trades, target weights."),
    ("28_portfolio_rec_artifacts.png", "Portfolio Recommendation + Artifacts", "Gemma3 4b [PORTFOLIO REC]; artifacts saved to run folder."),
    ("29_final_pipeline_summary.png", "Final SPAR Synthesis", "Plausibility CLEARED; full pipeline summary through Layer 3."),
]

SCREENSHOT_SRC = {
    "10_political_r2.png": "image-d9a736a9-043f-4118-87c6-eba9dfcc942f.png",
    "11_economic_r2.png": "image-ad601fcf-b4ba-4b37-ae8d-be138ff39378.png",
    "12_environmental_r2.png": "image-83ca45d0-0763-43f1-97cd-613ec1928910.png",
    "13_social_r2.png": "image-ec9ae631-c50b-4fcc-9c83-9e3720e0ba1f.png",
    "14_devils_advocate_dcs_r2.png": "image-f59ac787-7aab-4d47-803a-0b7cb2717065.png",
    "15_political_economic_r3.png": "image-ba002241-fc16-4e5b-b26a-8ffd7c32d480.png",
    "16_environmental_social_r3.png": "image-67d9a79d-afc3-4a63-8765-93225326b658.png",
    "17_devils_advocate_dcs_r3.png": "image-5ec2829c-231e-43e3-aa20-30072e700102.png",
    "18_political_r4.png": "image-26a2d907-b022-4713-adf3-b7d22233bdc5.png",
    "19_economic_environmental_r4.png": "image-23436d05-cb3f-4009-b37f-6c7a2e8a171b.png",
    "20_social_devils_advocate_r4.png": "image-3b2316d6-d0a5-4848-b56a-23e6f087bc78.png",
    "21_dcs_r4.png": "image-e59f5597-98b4-4e35-8b8d-0940f6f4ba2e.png",
    "22_political_economic_r5.png": "image-7e4babf0-24a0-4235-82bd-d1210d43592f.png",
    "23_environmental_social_r5.png": "image-cca0691a-c771-45cb-b4b7-6afc1290e977.png",
    "24_devils_advocate_dcs_r5.png": "image-efe4f0aa-6a6c-44b7-ae39-b48eeafdab19.png",
    "25_moderator_synthesis.png": "image-909b3890-93f4-4312-8acf-c6245c107757.png",
    "26_plausibility_layer3_start.png": "image-475548a3-8ff5-4fc5-a14d-e791dd66f1f2.png",
    "27_layer3_portfolio_detail.png": "image-f9f6e509-7811-4ed1-a721-7f85f5c3cb30.png",
    "28_portfolio_rec_artifacts.png": "image-fc90f73e-3d59-46e2-aec7-b5cd563bca85.png",
    "29_final_pipeline_summary.png": "image-57906374-63d1-4591-a374-a13f618be2ac.png",
}

ROUND2_AGENT_SUMMARIES = [
    (
        "Political — Phi4 Mini Latest",
        [
            "Acknowledges Economic Agent's Energy/Commodity Shock analysis (WTI fluctuations, inflation pass-through).",
            "Introduces Political Domain Analysis: energy markets inseparable from geopolitics (sanctions, military escalation).",
            "Highlights Safe Haven Flows: heightened uncertainty pushes investors toward USD over gold/Treasuries.",
            "Argues investor trepidation driven by Geopolitical Risk Premium jump, not just energy price trends.",
            "References Devil's Advocate on whether markets have priced-in tariff actions.",
            "Aligns with Social channel: inflation will retard retail consumption; urges focus on equities and bonds ripples.",
        ],
    ),
    (
        "Economic — Nemotron Mini 4b",
        [
            "Agrees inflation shock reduces consumer spending power via price pass-through.",
            "Disagrees that increased geopolitical tensions are fully priced into market expectations.",
            "GPR implications: investors seek safe havens (USD) away from gold/Treasuries during crises.",
            "Energy sectors face headwinds from rising commodity prices and US-EU escalation.",
            "Critiques Economic Agent (peer) for ignoring broader macro instability from elevated GPR.",
            "Maintains GPR leads investors toward safer assets rather than commodities under geopolitical tension.",
        ],
    ),
    (
        "Environmental — Granite3.3 8b",
        [
            "Appreciates Political Agent on market sensitivity to geopolitical risks and safe-haven flows.",
            "Maintains rising energy prices (Energy/Commodity transmission channel) affect spending via inflation pass-through.",
            "CPI rise as evidence reaching Social domain — impacts retail consumption patterns.",
            "Cites 10-year Treasury yield at 1.93% reflecting inflation expectations.",
            "References Social Agent data: pump prices $4.50/gallon, falling real wage growth.",
            "Proposes modeling scenarios where rapid risk-premium changes exaggerate short-term market reactions.",
            "Stresses temporal dynamics: immediate reactions vs subsequent broader macroeconomic impacts.",
        ],
    ),
    (
        "Social — Llama3.1 8b",
        [
            "Acknowledges Devil's Advocate on market expectations and investor sentiment complexity.",
            "Agrees Economic Agent on energy/spending link but flags missing safe-haven USD transmission channel.",
            "Directly questions Economic Agent on USD-driven asset flows during geopolitical crises.",
            "Supports Environmental Agent on Treasury 1.93% yield — GPR must not be overshadowed by energy shocks.",
            "Proposes analyzing rapid risk-premium change scenarios for short-term market exaggeration.",
            "Reiterates consumer financial stress: falling real wages + high pump prices fuel bearish investor perception.",
        ],
    ),
    (
        "Devil's Advocate — Qwen2.5 7b",
        [
            "Revisits Political Agent on GPR and safe-haven asset rotation (USD over commodities).",
            "Supports Economic Agent's price pass-through mechanisms as consumer-impact channels.",
            "Cites 10-year Treasury yield rise to 1.93% as inflation-expectation evidence.",
            "Echoes Environmental Agent on commodity prices → consumer spending power.",
            "Echoes Social Agent on retail consumption impact from real wages and pump prices.",
            "Agrees on multifaceted approach but prioritizes immediate consumer-life effects as economic backbone.",
        ],
    ),
]

DCS_ROUND2_TERMINAL = {
    "dcs_score": 0.793,
    "threshold": 0.35,
    "action": "EXPLORE",
    "reason": "DCS 0.793 > tau 0.35 — agents still disagree or produce new information.",
    "components": {
        "disagreement": {"weight": "34%", "value": 0.450, "detail": "Fewer than two valid SP500 forecasts — default moderate disagreement."},
        "info_gain": {"weight": "33%", "value": 1.000, "detail": "424 new token groups vs prior round (78% of current-round vocabulary is novel)."},
        "rag_exhaustion": {"weight": "33% (inverted)", "value": 0.059, "detail": "27 repeated 3-gram patterns in transcript (1% of unique phrases recur)."},
    },
    "formula": "DCS = w1·Disagreement + w2·InfoGain + w3·(1 - RAG_exhaustion)",
    "next_step": "Another live round will run (max round 5).",
}

ROUND3_AGENT_SUMMARIES = [
    (
        "Political — Phi4 Mini Latest",
        [
            "Acknowledges geopolitical risks shifting investor sentiment (USD vs commodities) but urges stronger focus on immediate consumer-behavior transmission channels.",
            "Agrees with Economic Agent on tension impacts; calls for Consumer Behavior / Employment / Energy-Inflation channel integration.",
            "Disagrees with over-emphasis on investor behavior vs price pass-through reducing consumer purchasing power.",
            "References Social Agent on falling real wages amplifying energy cost burden.",
            "Round 1 stance refined by Economic and Social Agent inputs in live debate.",
            "Calls all agents to emphasize spending impacts that could deepen retail sector downturns.",
        ],
    ),
    (
        "Economic — Nemotron Mini 4b",
        [
            "Synthesizes Environmental Agent on commodity prices and price pass-through affecting consumer spending power.",
            "Echoes Devil's Advocate on immediate impacts — energy costs reduce purchasing capacity.",
            "Acknowledges Political Agent on USD safe havens but reports view change after Economic/Social insights in Round 3.",
            "Concludes: monitor energy/inflation pass-through channels when assessing equities, bonds, and commodities.",
        ],
    ),
    (
        "Environmental — Granite3.3 8b",
        [
            "Deepens analysis of geopolitical risks × transmission channels with consumer behavior focus.",
            "Supports Political Agent on integrating consumption impacts from rising energy costs and price pass-through.",
            "Evolves Round 1 investor-centric view toward direct consumer purchasing power (influenced by Economic + Social).",
            "Agrees with Devil's Advocate on comprehensive transmission channel understanding.",
            "Proposes integrating immediate price pass-through with broader GPR-driven market sentiment.",
            "View shifted since Round 1 due to consumer financial stress and inflation — grounded in Layer 0 + Master Context.",
        ],
    ),
    (
        "Social — Llama3.1 8b",
        [
            "Agrees with Economic/Political on transmission channels impacting consumer behavior.",
            "Layer 0 evidence: falling real wages amplify negative effects of rising energy prices.",
            "Critiques Environmental Agent's safe-haven USD assumption — consumer financial stress also drives behavior.",
            "Challenges Economic Agent oil channel: consumers cannot simply adjust spending.",
            "Master Context: rising household debt, declining disposable income limit flexibility.",
            "Calls for holistic approach linking investor sentiment and consumer behavior across equities, bonds, commodities.",
        ],
    ),
    (
        "Devil's Advocate — Qwen2.5 7b",
        [
            "Challenges Economic Agent assumption that consumers can absorb higher energy costs.",
            "Master Context: rising household debt and declining disposable income reduce financial flexibility.",
            "Agrees with Environmental on commodity pass-through but emphasizes direct consumer wallet impact.",
            "Aligns with Social on falling real wages — rising energy prices are a broad economic issue, not investor-only.",
            "Urges prioritizing real-world consumer struggles to avoid underestimating economic downturn risk.",
        ],
    ),
]

DCS_ROUND3_TERMINAL = {
    "dcs_score": 0.746,
    "threshold": 0.35,
    "action": "EXPLORE",
    "reason": "DCS 0.746 > tau 0.35 — agents still disagree or produce new information.",
    "components": {
        "disagreement": {"weight": "34%", "value": 0.450, "detail": "Fewer than two valid SP500 forecasts — default moderate disagreement."},
        "info_gain": {"weight": "33%", "value": 0.912, "detail": "172 new token groups vs prior round (41% of current-round vocabulary is novel)."},
        "rag_exhaustion": {"weight": "33% (inverted)", "value": 0.115, "detail": "80 repeated 3-gram patterns in transcript (3% of unique phrases recur)."},
    },
    "formula": "DCS = w1·Disagreement + w2·InfoGain + w3·(1 - RAG_exhaustion)",
    "next_step": "Another live round will run (max round 5).",
}

ROUND4_AGENT_SUMMARIES = [
    (
        "Political — Phi4 Mini Latest",
        [
            "Synthesizes all peer inputs into structured responses to Political, Environmental, Social, and Devil's Advocate positions.",
            "Shifts emphasis to Consumer Behavior / Energy Inflation Channel as tensions drive investors away from commodities.",
            "Agrees with Social Agent: GPR heightens fear, pushing USD over volatile commodities and equities.",
            "Evolved from Household Debt Dynamics to immediate Consumer Behavior / Energy Inflation impacts.",
            "Incorporates Environmental Agent on safe-haven USD and GPR with Economic + Social interconnection.",
            "Acknowledges understating real wage dynamics and consumer fiscal health.",
            "Aligns with Social on rising debt and falling disposable income via Master Context real-wage evidence.",
            "Finds Devil's Advocate on consumer debt persuasive — balances investor sentiment with Consumer Debt Dynamics.",
        ],
    ),
    (
        "Economic — Nemotron Mini 4b",
        [
            "Concise agreement on system complexity and interdependencies.",
            "Stresses integrating transmission channels affecting both investor sentiment and consumer behavior.",
            "Highlights increased consumption stress on purchasing power from rising global energy prices.",
        ],
    ),
    (
        "Environmental — Granite3.3 8b",
        [
            "Synthesizes Political (immediate impacts), Social (real-wage declines), and Economic (integrative perspective).",
            "Aligns with Devil's Advocate on consumer reactions to sudden economic shocks.",
            "Maintains panel must not lose sight of broader GPR influencing investment behavior.",
            "Proposes dual-thread framework: Immediate Economic Shock + Investor Sentiment under geopolitical tension.",
        ],
    ),
    (
        "Social — Llama3.1 8b",
        [
            "Responds to Environmental Agent call for holistic investor + consumer integration.",
            "Agrees on GPR-driven market sentiment; cites Consumer Financial Health channel from Master Context.",
            "Proposes dual focus: Immediate Economic Shock channels + Investor Sentiment alongside geopolitical risks.",
        ],
    ),
    (
        "Devil's Advocate — Qwen2.5 7b",
        [
            "Challenges panel: long-term psychological impact on investor sentiment may be underplayed.",
            "GPR drives sustained shift to USD safe assets — not merely short-term reaction.",
            "Layer 0: Geopolitical Risk Premium Channel often underweighted in collective analysis.",
            "Persistent tensions create lasting risk-off environment affecting equities, bond yields, and strategies.",
        ],
    ),
]

DCS_ROUND4_TERMINAL = {
    "dcs_score": 0.769,
    "threshold": 0.35,
    "action": "EXPLORE",
    "reason": "DCS 0.769 > tau 0.35 — agents still disagree or produce new information.",
    "components": {
        "disagreement": {"weight": "34%", "value": 0.450, "detail": "Fewer than two valid SP500 forecasts — default moderate disagreement."},
        "info_gain": {"weight": "33%", "value": 1.000, "detail": "249 new token groups vs prior round (52% of current-round vocabulary is novel)."},
        "rag_exhaustion": {"weight": "33% (inverted)", "value": 0.135, "detail": "137 repeated 3-gram patterns in transcript (3% of unique phrases recur)."},
    },
    "formula": "DCS = w1·Disagreement + w2·InfoGain + w3·(1 - RAG_exhaustion)",
    "next_step": "Another live round will run (max round 5) — final debate round.",
}

ROUND5_AGENT_SUMMARIES = [
    (
        "Political — Phi4 Mini Latest",
        [
            "Final round synthesis: thanks panel for debate on global economic dynamics under rising geopolitical tensions.",
            "Acknowledges Devil's Advocate on long-term psychological impacts via Geopolitical Risk Premium (GRP) Channel.",
            "Diverges on prioritization: immediate energy-price shocks more palpable via Immediate Consumption Stress channels.",
            "Cites Layer 0 evidence and Kuwait 1990 — immediate shocks hit energy prices and consumer financial stress.",
            "Enhanced recognition: investor behavior driven by both immediate shocks and broader GRP shifts.",
            "Advocates balanced approach — long-term geopolitical impacts plus immediate consumer/investor responses.",
        ],
    ),
    (
        "Economic — Nemotron Mini 4b",
        [
            "Agrees with Environmental expert: geopolitical-driven investor sentiment is central.",
            "Links consumption stress, Immediate Financial Shock channels, and global market dynamics.",
            "Integrates Environmental (consumer health) + Social (real wage recession → household debt dynamics).",
            "Addresses Political advocate: geostrategy and safe-haven USD shift during volatility must be modeled.",
            "Agrees with Devil's Advocate: long-term investor sentiment shifts are key for market dynamics.",
            "Calls for transmission channel layers from Master Context for comprehensive predictions.",
        ],
    ),
    (
        "Environmental — Granite3.3 8b",
        [
            "Shared emphasis on immediate impacts (energy hikes) and long-term investor sentiment from geopolitical risks.",
            "Aligns with Social Agent on real wage declines → household debt (Layer 0 evidence).",
            "Stance evolved: now equal weight on long-term psychological shifts (Devil's Advocate, GPR Channel).",
            "Integrates energy inflation with Devil's Advocate risk-off environment framing.",
            "Immediate shocks must be complemented by lasting behavioral changes in investment strategies.",
            "Proposes multi-pronged approach for accurate modeling amid escalating global tensions.",
        ],
    ),
    (
        "Social — Llama3.1 8b",
        [
            "Agrees Devil's Advocate: long-term psychological impacts underweighted — but they don't supersede immediate shocks.",
            "Layer 0 evidence: immediate and long-term factors reinforce each other, not compete.",
            "Economic Agent: immediate macro impacts well-founded; Master Context shows short/long-term interplay.",
            "Political Agent: artificial dichotomy — persistent tensions alter expectations → sustained risk-off.",
            "Real wage decline focus gained significance alongside Economic Agent's safe-haven capital shift.",
            "Integrate immediate shocks + sustained GPR-driven sentiment for refined global dynamics view.",
        ],
    ),
    (
        "Devil's Advocate — Qwen2.5 7b",
        [
            "Addresses Economic perspective from Layer 0 packet.",
            "GPR Channel influences both investor behavior and consumer financial decisions.",
            "Kuwait 1990 analogue: persistent geopolitical risks create long-term sentiment shifts.",
            "Contrasts lasting GPR effects with immediate macroeconomic impacts using Layer 0/1/2 evidence.",
        ],
    ),
]

DCS_ROUND5_TERMINAL = {
    "dcs_score": 0.761,
    "threshold": 0.35,
    "action": "EXPLOIT",
    "reason": "Round 5 reached max cap (5) — stop debating.",
    "components": {
        "disagreement": {"weight": "34%", "value": 0.450, "detail": "Fewer than two valid SP500 forecasts — default moderate disagreement."},
        "info_gain": {"weight": "33%", "value": 0.984, "detail": "212 new token groups vs prior round (45% of current-round vocabulary is novel)."},
        "rag_exhaustion": {"weight": "33% (inverted)", "value": 0.142, "detail": "185 repeated 3-gram patterns in transcript (4% of unique phrases recur)."},
    },
    "formula": "DCS = w1·Disagreement + w2·InfoGain + w3·(1 - RAG_exhaustion)",
    "next_step": "Passing to Moderator for consensus + dissent synthesis. Live Debate + DCS complete → Moderator + Plausibility Gate.",
}

# Terminal display values from final-run screenshots (authoritative UI record)
MODERATOR_TERMINAL = {
    "model": "Gemma3 4b",
    "consensus": {
        "direction": "negative",
        "confidence": 0.85,
        "plausibility_score": 92,
        "channels": ["Geopolitical Risk Premium", "Inflation Pass-Through (Energy)", "Consumer Sentiment (Wage Decline)"],
        "magnitude_pct": {"SP500": -3.50, "XLE": -6.00, "XLF": -4.80, "XLK": -5.20, "ITA": -7.10, "XLY": -8.90},
        "summary": (
            "Broad market correction triggered by geopolitical risk and inflation. Shift toward safe-haven assets "
            "and downward pressure on consumer demand from rising costs and declining real wages."
        ),
    },
    "dissent": {
        "agents": ["Economic Agent", "DEVILS_ADVOCATE"],
        "direction": "negative",
        "plausibility_score": 68,
        "magnitude_pct": {"SP500": -7.00, "XLE": -12.00, "XLF": -8.00, "XLK": -9.00, "ITA": -14.00, "XLY": -20.00},
        "summary": (
            "Significantly more severe outcome — potentially uncontrolled inflation spirals, 10Y yield breaching 2.5%+. "
            "Majority view underplays runaway inflation and systemic crisis risk."
        ),
    },
}

PLAUSIBILITY_TERMINAL = {
    "decision": "PROCEED",
    "composite_score": 70,
    "threshold": 60,
    "moderator_score": 92.0,
    "dissent_score": 68.0,
    "fsr_score": 42.2,
    "composite_detail": 69.6,
    "moderator_weight": 0.55,
    "fsr_weight": 0.45,
    "scenario_id": "liberation_day_2025",
    "fsr_editions": ["2024-May", "2025-May"],
    "top_fsr_match": ("fsr_trade_inflation_2024", 46),
    "fsr_passages": [
        ("fsr_trade_inflation_2024", 46, "Trade restrictions pass through to consumer prices, complicate disinflation."),
        ("fsr_geopolitical_generic_2024", 40, "Geopolitical developments as tail risk source."),
        ("fsr_equity_correction_2024", 35, "Equity valuations sensitive to growth surprises and trade disruptions."),
    ],
}

LAYER3_TERMINAL = {
    "consensus_portfolio_pnl_pct": -5.66,
    "dissent_portfolio_pnl_pct": -10.35,
    "var_95_pct": 8.66,
    "expected_shortfall_pct": 8.94,
    "factor_shocks_pct": {"market": -6.14, "smb": -2.50, "hml": 4.00},
    "sector_shocks_pct": {
        "SP500": (-4.4, -6.1), "XLE": (-5.3, -4.1), "XLF": (-5.2, -6.1),
        "XLK": (-6.0, -7.6), "ITA": (-6.6, -5.6), "XLY": (-8.3, -7.3),
    },
    "hedge_weights": {"GLD": 17.2, "TLT": 17.8},
    "heatmap": {
        "consens": {"SP500": -4.4, "XLE": -5.3, "XLF": -5.2, "XLK": -6.0, "ITA": -6.6, "XLY": -8.3},
        "dissent": {"SP500": -7.0, "XLE": -12.0, "XLF": -8.0, "XLK": -9.0, "ITA": -14.0, "XLY": -20.0},
        "ff_implied": {"SP500": -6.1, "XLE": -4.1, "XLF": -6.1, "XLK": -7.6, "ITA": -5.6, "XLY": -7.3},
    },
}

PORTFOLIO_TERMINAL = {
    "var_before_pct": 6.78,
    "var_after_pct": 5.85,
    "expected_hedge_pnl_pct": 0.75,
    "cash_weight_pct": 10.7,
    "hedge_overlay_pct": 35.0,
    "trades": [
        ("REDUCE", "SP500", 35.0, 32.8, -2.2),
        ("REDUCE", "XLE", 10.0, 7.3, -2.7),
        ("REDUCE", "XLF", 15.0, 12.4, -2.6),
        ("REDUCE", "XLK", 20.0, 17.0, -3.0),
        ("REDUCE", "ITA", 5.0, 3.2, -1.8),
        ("REDUCE", "XLY", 15.0, 10.8, -4.2),
        ("ADD_HEDGE", "GLD", 0.0, 17.2, 17.2),
        ("ADD_HEDGE", "TLT", 0.0, 17.8, 17.8),
        ("INCREASE", "CASH", 5.0, 10.7, 5.7),
    ],
    "target_equity": {"SP500": 21.3, "XLE": 4.8, "XLF": 8.1, "XLK": 11.0, "ITA": 2.1, "XLY": 7.0},
    "hedge": {"GLD": 17.2, "TLT": 17.8},
    "artifacts_path": r"C:\Users\madha\spar_outputs\run_20260708_005317",
}

# ---------------------------------------------------------------------------
# Cross-model performance evaluation (rubric + per-round scores)
# ---------------------------------------------------------------------------
EVALUATION_RUBRIC = [
    ("scenario_fidelity", "Scenario Fidelity", 15, "Stays on liberation_day_2025 tariffs; avoids Ukraine/GPT hallucination bleed."),
    ("structure_quality", "Structure Quality", 15, "Valid JSON (R1), coherent paragraphs, actionable claims in debate."),
    ("peer_engagement", "Peer Engagement", 15, "Names peer agents; agrees/disagrees with specific prior points."),
    ("view_revision", "View Revision", 15, "Explicitly updates Round 1 stance when peer evidence warrants it."),
    ("channel_grounding", "Channel Grounding", 20, "Cites Layer 0, Master Context, transmission channels by name."),
    ("role_fit", "Role Fit", 10, "Behaves like assigned SPAR role (Political, Economic, Social, etc.)."),
    ("analytical_depth", "Analytical Depth", 10, "Quantitative anchors (yields, wages, VIX); mechanism not hand-waving."),
]

MODEL_EVALUATIONS = [
    {
        "model_id": "phi4-mini", "display": "Phi4 Mini Latest", "runtime_role": "Political", "preset_role": "Moderator",
        "benchmark_overall": 67.1, "benchmark_role_fit": 72.5,
        "round_totals": {1: 58, 2: 76, 3: 74, 4: 84, 5: 82}, "trajectory": "Improving (+26 pts R1 to R4 peak)",
        "composite": 74.8, "rank": 3,
        "agreements": {2: ["Economic on energy/inflation pass-through", "Social on consumption drag"],
            3: ["Economic on consumer sentiment", "Devil's Advocate on holistic view"],
            4: ["Social on household debt", "Devil's Advocate on consumer debt"], 5: ["Panel on dual-thread framework"]},
        "disagreements": {2: ["Economic: tensions NOT fully priced in"], 3: ["GPR vs immediate consumer priority"]},
        "revisions": ["R3: Balance GPR with consumer sentiment", "R4: Shift to Consumer Behavior/Energy Inflation",
            "R5: Accept dual-thread immediate shock + GPR"],
        "strengths": ["Strongest synthesizer R4", "Highest peer cross-reference density"],
        "weaknesses": ["R1 artifact nearly empty", "Ukraine bleed R2-R3"],
    },
    {
        "model_id": "nemotron-mini:4b", "display": "Nemotron Mini 4b", "runtime_role": "Economic", "preset_role": "Devil's Advocate",
        "benchmark_overall": 48.8, "benchmark_role_fit": 44.1,
        "round_totals": {1: 32, 2: 74, 3: 68, 4: 55, 5: 72}, "trajectory": "Volatile (R1 fail, R4 dip)",
        "composite": 60.2, "rank": 6,
        "agreements": {2: ["Political on GPR/safe-haven USD"], 3: ["Devil's Advocate on channel diversity"], 5: ["DA on long-term sentiment"]},
        "disagreements": {3: ["Social: macro indicators alone insufficient"], 4: ["GPR psychology underweighted"]},
        "revisions": ["R3: Concedes price pass-through", "R5: Integrates safe-haven + household debt"],
        "strengths": ["R2 GPR argument", "Named in moderator dissent"],
        "weaknesses": ["R1 JSON fail + GPT-4o/Ukraine hallucination", "R4 shortest response", "Role misfit vs preset"],
    },
    {
        "model_id": "granite3.3:8b", "display": "Granite3.3 8b", "runtime_role": "Environmental", "preset_role": "Political",
        "benchmark_overall": 62.9, "benchmark_role_fit": 61.2,
        "round_totals": {1: 88, 2: 78, 3: 80, 4: 82, 5: 84}, "trajectory": "Stable high (best R1)",
        "composite": 82.4, "rank": 1,
        "agreements": {2: ["Political on geopolitical risk"], 3: ["Devil's Advocate on comprehensive channels"],
            4: ["Social on real wages"], 5: ["Dual-thread convergence"]},
        "disagreements": {4: ["Must not lose GPR in consumer-only focus"]},
        "revisions": ["R3: Investor to consumer focus", "R4: Dual-thread framework architect", "R5: Equal GPR weight"],
        "strengths": ["Best R1 JSON (tariff supply chain)", "Framework architect R4-R5"],
        "weaknesses": ["Black Sea refs in R1", "Transcript role confusion R4"],
    },
    {
        "model_id": "llama3.1:8b", "display": "Llama3.1 8b", "runtime_role": "Social", "preset_role": "Social",
        "benchmark_overall": 57.5, "benchmark_role_fit": 54.7,
        "round_totals": {1: 68, 2: 76, 3: 84, 4: 78, 5: 82}, "trajectory": "Steady improvement (+14 R1 to R5)",
        "composite": 77.6, "rank": 2,
        "agreements": {2: ["Economic on energy/spending"], 3: ["Environmental on pass-through"],
            4: ["Holistic investor+consumer"], 5: ["Shock + GPR reinforce each other"]},
        "disagreements": {2: ["Economic: missing safe-haven channel"], 3: ["Consumers cannot adjust spending"]},
        "revisions": ["R3: Household debt + disposable income", "R5: Reject artificial GPR-vs-shock split"],
        "strengths": ["Best consumer metrics", "Best preset role alignment", "R3 peak"],
        "weaknesses": ["R1 partial JSON", "Limited R1 quantitative forecasts in artifact"],
    },
    {
        "model_id": "qwen2.5:7b", "display": "Qwen2.5 7b", "runtime_role": "Devil's Advocate", "preset_role": "Economic",
        "benchmark_overall": 63.5, "benchmark_role_fit": 68.5,
        "round_totals": {1: 76, 2: 82, 3: 78, 4: 80, 5: 86}, "trajectory": "Consistently strong; peak R5",
        "composite": 80.4, "rank": 2,
        "agreements": {2: ["Environmental/Social on consumer impact"], 3: ["Social on real wages"], 5: ["Dual-thread balance"]},
        "disagreements": {2: ["Relief rally under-weighted"], 4: ["GPR psychology underweighted by panel"]},
        "revisions": ["R2-R5: Relief-rally to consumer-wallet + GPR critique", "R5: Kuwait 1990 GPR anchor"],
        "strengths": ["Drove moderator dissent", "Re-introduced GPR R4", "Best contrarian consistency"],
        "weaknesses": ["R1 UI simplified vs JSON", "Role misfit (DA vs Economic preset)"],
    },
    {
        "model_id": "gemma3:4b", "display": "Gemma3 4b", "runtime_role": "Moderator", "preset_role": "Social",
        "benchmark_overall": 57.5, "benchmark_role_fit": 54.7,
        "round_totals": {1: None, 2: None, 3: None, 4: None, 5: None}, "synthesis_score": 90,
        "trajectory": "Moderator-only (post-debate)", "composite": 90.0, "rank": 1,
        "agreements": {"synthesis": ["Integrated all debate threads", "Preserved dissent tail risk"]},
        "disagreements": {"synthesis": ["N/A — synthesizes rather than debates"]},
        "revisions": ["Consensus -3.5% SP500 + severer dissent -7.0%"],
        "strengths": ["Plausibility 92/100", "Sector magnitudes + portfolio rec"],
        "weaknesses": ["Not in live debate rounds", "Role misfit vs preset"],
    },
]

PEER_AGREEMENT_MATRIX = [
    ("Phi4 Political", "Granite3 Environmental", "R2-R5", "R3", "Tariff macro transmission"),
    ("Phi4 Political", "Llama3 Social", "R2,R4,R5", "-", "Consumer financial stress"),
    ("Phi4 Political", "Qwen2.5 DA", "R3,R5", "R2,R5", "GPR vs immediate shock"),
    ("Nemotron Economic", "Qwen2.5 DA", "R2,R3,R5", "R4", "Long-term sentiment"),
    ("Nemotron Economic", "Llama3 Social", "R2,R3", "R3", "Consumer adjustment limits"),
    ("Granite3 Environmental", "Llama3 Social", "R3-R5", "R3", "Safe-haven USD debate"),
    ("Granite3 Environmental", "Qwen2.5 DA", "R3-R5", "-", "Risk-off + pass-through"),
    ("Llama3 Social", "Qwen2.5 DA", "R3,R5", "R4", "GPR priority tension"),
]

PIPELINE_SUMMARY_TERMINAL = {
    "plausibility_status": "CLEARED",
    "moderator_model": "Gemma3 4b",
    "live_debate_rounds": [2, 3, 4, 5],
    "dcs_round5": 0.761,
    "dcs_action": "EXPLOIT",
    "gate_score": 69.59,
    "gate_threshold": 60,
    "layer3_status": "ran",
    "artifacts_path": r"C:\Users\madha\spar_outputs\run_20260708_005317",
}

RUNTIME_MODEL_MAP = [
    ("Political", "phi4-mini", "Phi4 Mini Latest"),
    ("Economic", "nemotron-mini:4b", "Nemotron Mini 4b"),
    ("Environmental", "granite3.3:8b", "Granite3.3 8b"),
    ("Social", "llama3.1:8b", "Llama3.1 8b"),
    ("Devil's Advocate", "qwen2.5:7b", "Qwen2.5 7b"),
    ("Moderator", "gemma3:4b", "Gemma3 4b"),
]

BENCHMARK_PRESET_ROLES = [
    ("Moderator", "phi4-mini", "Microsoft", 67.12, 72.51),
    ("Economic", "qwen2.5:7b", "Alibaba", 63.50, 68.46),
    ("Political", "granite3.3:8b", "IBM", 62.90, 61.17),
    ("Social", "gemma3:4b", "Google", 57.50, 54.70),
    ("Devil's Advocate", "nemotron-mini:4b", "NVIDIA", 48.83, 44.10),
    ("Environmental", "mistral:7b", "Mistral", 47.37, 48.27),
]

FRONTIER_REFS = [
    ("claude-3-5-sonnet", "Anthropic", 83.17),
    ("gemini-1.5-pro", "Google", 80.00),
    ("gpt-4o-mini", "OpenAI", 77.20),
]

PER_BENCH_LEADERS = [
    ("MMLU", "qwen2.5:7b", 74.2),
    ("BIG-Bench Hard", "phi4-mini", 70.4),
    ("GSM8K", "phi4-mini", 88.6),
    ("IFEval", "phi4-mini", 72.0),
    ("TruthfulQA", "granite3.3:8b", 66.9),
    ("GPQA Diamond", "phi4-mini", 38.0),
]


def clean(text: str) -> str:
    return (
        str(text)
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2192", "->")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def img_b64(path: Path) -> str:
    if not path.exists():
        return ""
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def embed_screenshots(shot_dir: Path) -> dict[str, str]:
    embedded: dict[str, str] = {}
    for fname, _, _ in SCREENSHOTS:
        embedded[fname] = img_b64(shot_dir / fname)
    return embedded


def ensure_screenshots(run_dir: Path) -> Path:
    dest = run_dir / "report_screenshots"
    dest.mkdir(parents=True, exist_ok=True)
    prefix = "c__Users_madha_AppData_Roaming_Cursor_User_workspaceStorage_empty-window_images_"
    name_map = {fname: prefix + fname for fname, _, _ in SCREENSHOTS}
    name_map.update({k: prefix + v for k, v in SCREENSHOT_SRC.items()})
    for out_name, src_suffix in name_map.items():
        out = dest / out_name
        if out.exists():
            continue
        for base in [run_dir.parent.parent / "assets", ASSETS_SRC, ROOT / "assets"]:
            src = base / src_suffix
            if src.exists():
                out.write_bytes(src.read_bytes())
                break
    return dest


def dcs_for_round(dcs_scores: list, round_number: int) -> dict | None:
    for entry in dcs_scores:
        if entry.get("round_number") == round_number:
            return entry
    return None


def render_dcs_html(dcs_terminal: dict, dcs_artifact: dict | None, round_label: str) -> str:
    parts = [
        f'<div class="card"><h2>Debate Continuation Score (DCS) — After {round_label}</h2>',
        """<p>Phi4 Mini Latest [DCS] evaluates whether agents still disagree or produce novel information.
If DCS &gt; threshold (tau = 0.35), the system continues debating (EXPLORE). Maximum 5 rounds.</p>""",
        f"""<div class="meta">
<div><strong>DCS (terminal)</strong><br/>{dcs_terminal['dcs_score']:.3f}</div>
<div><strong>Threshold tau</strong><br/>{dcs_terminal['threshold']}</div>
<div><strong>Decision</strong><br/>{dcs_terminal['action']}</div>
<div><strong>Next step</strong><br/>{html.escape(dcs_terminal['next_step'])}</div>
</div>""",
        f"<p><strong>Reason:</strong> {html.escape(dcs_terminal['reason'])}</p>",
        f"<p><strong>Formula:</strong> <code>{html.escape(dcs_terminal['formula'])}</code></p>",
        "<h3>DCS Components (from terminal)</h3>",
        "<table><tr><th>Component</th><th>Weight</th><th>Value</th><th>Detail</th></tr>",
    ]
    for key, label in [("disagreement", "Disagreement"), ("info_gain", "Information gain"), ("rag_exhaustion", "RAG exhaustion")]:
        c = dcs_terminal["components"][key]
        parts.append(
            f"<tr><td>{label}</td><td>{c['weight']}</td><td>{c['value']:.3f}</td>"
            f"<td>{html.escape(c['detail'])}</td></tr>"
        )
    parts.append("</table>")
    if dcs_artifact:
        comps = dcs_artifact.get("components", {})
        parts.append("<h3>Persisted artifact cross-reference (dcs_scores.json)</h3>")
        parts.append(
            f"""<p>Artifact DCS: <strong>{dcs_artifact.get('dcs_score', 0):.4f}</strong> |
Action: {html.escape(str(dcs_artifact.get('action', '')))} |
Disagreement: {comps.get('disagreement', 'N/A')} |
Info gain: {comps.get('info_gain', 'N/A')} |
RAG exhaustion: {comps.get('rag_exhaustion', 'N/A')}</p>
<p><em>{html.escape(str(comps.get('info_gain_detail', '')))}</em></p>"""
        )
    parts.append("</div>")
    return "".join(parts)


def render_round_debate_html(round_label: str, agent_summaries: list[tuple[str, list[str]]], themes: list[str]) -> str:
    parts = [f'<div class="card"><h2>{round_label} — Live Cross-Examination</h2>']
    for agent_title, bullets in agent_summaries:
        parts.append(f"<h3>{html.escape(agent_title)}</h3><ul>")
        for b in bullets:
            parts.append(f"<li>{html.escape(b)}</li>")
        parts.append("</ul>")
    parts.append(f"<h3>{round_label} Debate Themes</h3><ul>")
    for t in themes:
        parts.append(f"<li>{html.escape(t)}</li>")
    parts.append("</ul></div>")
    return "".join(parts)


def _score_class(score: int | float | None) -> str:
    if score is None:
        return ""
    if score >= 80:
        return "score-high"
    if score >= 65:
        return "score-mid"
    return "score-low"


def render_model_evaluation_html() -> str:
    parts = [
        '<div class="card"><h2>Cross-Model Performance Evaluation</h2>',
        "<p>Quantitative rubric-based assessment of each Ollama model across Round 1 (domain analysis) "
        "and Rounds 2–5 (live debate). Scores are derived from terminal screenshots, persisted artifacts, "
        "and <code>live_debate_transcript.txt</code>. Higher = better SPAR contribution.</p>",
        "<h3>Evaluation Rubric (weights sum to 100%)</h3>",
        "<table><tr><th>Dimension</th><th>Weight</th><th>Criterion</th></tr>",
    ]
    for _key, label, weight, desc in EVALUATION_RUBRIC:
        parts.append(f"<tr><td>{html.escape(label)}</td><td>{weight}%</td><td>{html.escape(desc)}</td></tr>")
    parts.append("</table>")

    debate_models = [m for m in MODEL_EVALUATIONS if m["round_totals"].get(1) is not None]
    debate_sorted = sorted(debate_models, key=lambda m: m["composite"], reverse=True)

    parts.append("<h3>Debate Agent Leaderboard (Rounds 1–5 composite)</h3>")
    parts.append("<table><tr><th>Rank</th><th>Model</th><th>Runtime Role</th><th>Composite</th>"
                 "<th>Trajectory</th><th>Benchmark Role-Fit</th></tr>")
    for i, m in enumerate(debate_sorted, 1):
        parts.append(
            f"<tr><td>{i}</td><td>{html.escape(m['display'])}</td><td>{html.escape(m['runtime_role'])}</td>"
            f"<td class='{_score_class(m['composite'])}'><strong>{m['composite']:.1f}</strong></td>"
            f"<td>{html.escape(m['trajectory'])}</td><td>{m['benchmark_role_fit']:.1f} "
            f"(preset: {html.escape(m['preset_role'])})</td></tr>"
        )
    parts.append("</table>")

    parts.append("<h3>Per-Round Total Scores (0–100)</h3>")
    parts.append("<table><tr><th>Model</th><th>R1</th><th>R2</th><th>R3</th><th>R4</th><th>R5</th>"
                 "<th>Δ R1→R5</th></tr>")
    for m in debate_sorted:
        r = m["round_totals"]
        delta = r[5] - r[1]
        sign = "+" if delta >= 0 else ""
        parts.append(
            f"<tr><td>{html.escape(m['display'])}</td>"
            f"<td class='{_score_class(r[1])}'>{r[1]}</td>"
            f"<td class='{_score_class(r[2])}'>{r[2]}</td>"
            f"<td class='{_score_class(r[3])}'>{r[3]}</td>"
            f"<td class='{_score_class(r[4])}'>{r[4]}</td>"
            f"<td class='{_score_class(r[5])}'>{r[5]}</td>"
            f"<td>{sign}{delta}</td></tr>"
        )
    parts.append("</table>")

    parts.append("<h3>Runtime vs Benchmark Preset Role Mismatch</h3>")
    parts.append("<table><tr><th>Model</th><th>Runtime Role</th><th>Preset Role</th>"
                 "<th>Role-Fit Delta</th><th>Impact</th></tr>")
    mismatches = [
        ("phi4-mini", "Political", "Moderator", "+8.7", "Synthesis strength; R1 artifact weak"),
        ("nemotron-mini:4b", "Economic", "Devil's Advocate", "-18.8", "R1 failure; preset swap recommended"),
        ("granite3.3:8b", "Environmental", "Political", "+2.8", "Strong R1; framework leader"),
        ("llama3.1:8b", "Social", "Social", "0", "Best alignment — steady improver"),
        ("qwen2.5:7b", "Devil's Advocate", "Economic", "-6.0", "Strong DA; drove dissent"),
        ("gemma3:4b", "Moderator", "Social", "N/A", "Moderator synthesis 90/100"),
    ]
    for mid, runtime, preset, delta, impact in mismatches:
        parts.append(
            f"<tr><td>{mid}</td><td>{runtime}</td><td>{preset}</td><td>{delta}</td><td>{html.escape(impact)}</td></tr>"
        )
    parts.append("</table>")

    parts.append("<h3>Peer Agreement / Tension Matrix</h3>")
    parts.append("<table><tr><th>Agent A</th><th>Agent B</th><th>Agreement Rounds</th>"
                 "<th>Tension</th><th>Convergence Topic</th></tr>")
    for a, b, agree, tension, topic in PEER_AGREEMENT_MATRIX:
        parts.append(
            f"<tr><td>{html.escape(a)}</td><td>{html.escape(b)}</td><td>{html.escape(agree)}</td>"
            f"<td>{html.escape(tension)}</td><td>{html.escape(topic)}</td></tr>"
        )
    parts.append("</table>")

    for m in debate_sorted:
        parts.append(f"<h3>{html.escape(m['display'])} — {html.escape(m['runtime_role'])} "
                     f"(composite {m['composite']:.1f})</h3>")
        parts.append(f"<p><em>{html.escape(m['trajectory'])}</em></p>")
        parts.append("<p><strong>Strengths:</strong> " + "; ".join(html.escape(s) for s in m["strengths"]) + "</p>")
        parts.append("<p><strong>Weaknesses:</strong> " + "; ".join(html.escape(s) for s in m["weaknesses"]) + "</p>")
        parts.append("<p><strong>View revisions:</strong></p><ul>")
        for rev in m["revisions"]:
            parts.append(f"<li>{html.escape(rev)}</li>")
        parts.append("</ul>")
        for rnd in [2, 3, 4, 5]:
            if rnd in m["agreements"]:
                parts.append(f"<p><strong>R{rnd} agreed with:</strong> " +
                             "; ".join(html.escape(a) for a in m["agreements"][rnd]) + "</p>")
            if rnd in m.get("disagreements", {}):
                parts.append(f"<p><strong>R{rnd} pushed back on:</strong> " +
                             "; ".join(html.escape(d) for d in m["disagreements"][rnd]) + "</p>")

    mod = next(m for m in MODEL_EVALUATIONS if m["model_id"] == "gemma3:4b")
    parts.append(f"<h3>{html.escape(mod['display'])} — Moderator Synthesis (score {mod['synthesis_score']}/100)</h3>")
    parts.append("<p>Not scored in live debate rounds. Evaluated on Layer 2 synthesis quality, sector magnitude "
                 "granularity, dissent preservation, and plausibility self-score (92/100).</p>")
    parts.append("<p><strong>Strengths:</strong> " + "; ".join(html.escape(s) for s in mod["strengths"]) + "</p>")

    parts.append("<h3>Key Analytical Findings</h3><ul>")
    findings = [
        "Granite3.3 8b delivered the strongest Round 1 (valid tariff JSON) and architected the dual-thread framework by R4.",
        "Nemotron Mini 4b had the weakest Round 1 (JSON parse failure, GPT-4o hallucination) but recovered in R2 GPR debate.",
        "Qwen2.5 7b maintained the highest contrarian value — dissent preserved in moderator output at 68/100 plausibility.",
        "Llama3.1 8b showed the steadiest improvement trajectory (+14 pts) with best runtime/preset role alignment.",
        "Phi4 Mini Latest peaked as debate synthesizer in R4 but underperformed in R1 artifact persistence.",
        "All agents exhibited Ukraine-2022 scenario bleed from Layer 0 evidence corpus — fidelity penalty applied.",
        "View revision rate increased R2→R5: 3/5 agents explicitly revised stances by Round 3; 5/5 by Round 5.",
        "Benchmark role-fit scores weakly predicted debate performance — runtime role assignment mattered more.",
    ]
    for f in findings:
        parts.append(f"<li>{html.escape(f)}</li>")
    parts.append("</ul></div>")
    return "".join(parts)


def render_final_pipeline_html(gate: dict | None, layer3: dict | None, portfolio: dict | None) -> str:
    c = MODERATOR_TERMINAL["consensus"]
    d = MODERATOR_TERMINAL["dissent"]
    parts = [
        '<div class="card"><h2>Phase 4 — Moderator Synthesis (Layer 2)</h2>',
        f"<p><strong>Moderator model:</strong> {html.escape(MODERATOR_TERMINAL['model'])}</p>",
        "<h3>Consensus Scenario (majority view)</h3>",
        f"<p><strong>Direction:</strong> {c['direction']} | <strong>Confidence:</strong> {c['confidence']} | "
        f"<strong>Plausibility:</strong> {c['plausibility_score']}/100</p>",
        f"<p><strong>Channels:</strong> {', '.join(html.escape(ch) for ch in c['channels'])}</p>",
        "<table><tr><th>ETF</th><th>5-day move (%)</th></tr>",
    ]
    for etf, mv in c["magnitude_pct"].items():
        parts.append(f"<tr><td>{etf}</td><td>{mv:+.2f}%</td></tr>")
    parts.append(f"</table><p>{html.escape(c['summary'])}</p>")

    parts.append("<h3>Minority Dissent (tail risk preserved)</h3>")
    parts.append(
        f"<p><strong>Dissenting agents:</strong> {', '.join(d['agents'])} | "
        f"<strong>Direction:</strong> {d['direction']} | <strong>Plausibility:</strong> {d['plausibility_score']}/100</p>"
    )
    parts.append("<table><tr><th>ETF</th><th>Dissent 5-day (%)</th></tr>")
    for etf, mv in d["magnitude_pct"].items():
        parts.append(f"<tr><td>{etf}</td><td>{mv:+.2f}%</td></tr>")
    parts.append(f"</table><p>{html.escape(d['summary'])}</p></div>")

    pg = PLAUSIBILITY_TERMINAL
    parts.append('<div class="card"><h2>Plausibility Gate</h2>')
    parts.append(
        f"""<div class="meta">
<div><strong>Decision</strong><br/>{pg['decision']}</div>
<div><strong>Composite</strong><br/>{pg['composite_score']}/100</div>
<div><strong>Threshold</strong><br/>{pg['threshold']}</div>
<div><strong>Formula</strong><br/>{int(pg['moderator_weight']*100)}% mod + {int(pg['fsr_weight']*100)}% FSR = {pg['composite_detail']}</div>
</div>"""
    )
    parts.append(
        f"<p>Moderator: {pg['moderator_score']} | Dissent: {pg['dissent_score']} | "
        f"FSR alignment: {pg['fsr_score']}/100</p>"
    )
    parts.append(f"<p><strong>Scenario:</strong> {pg['scenario_id']} | FSR editions: {', '.join(pg['fsr_editions'])}</p>")
    parts.append(f"<p><strong>Top FSR match:</strong> {pg['top_fsr_match'][0]} ({pg['top_fsr_match'][1]}% overlap)</p>")
    parts.append("<ul>")
    for pid, pct, excerpt in pg["fsr_passages"]:
        parts.append(f"<li><strong>{pid}</strong> ({pct}%): {html.escape(excerpt)}</li>")
    parts.append("</ul>")
    if gate:
        parts.append(
            f"<p><em>Artifact (plausibility_gate.json): composite {gate.get('composite_score', 0):.2f}, "
            f"action {html.escape(str(gate.get('action', '')))}</em></p>"
        )
    parts.append("</div>")

    l3 = LAYER3_TERMINAL
    parts.append('<div class="card"><h2>Layer 3 — Portfolio Quantification</h2>')
    parts.append(
        f"""<div class="meta">
<div><strong>Consensus P&amp;L</strong><br/>{l3['consensus_portfolio_pnl_pct']:+.2f}%</div>
<div><strong>Dissent tail P&amp;L</strong><br/>{l3['dissent_portfolio_pnl_pct']:+.2f}%</div>
<div><strong>VaR (95%, 1d)</strong><br/>{l3['var_95_pct']:.2f}%</div>
<div><strong>Expected Shortfall</strong><br/>{l3['expected_shortfall_pct']:.2f}%</div>
</div>"""
    )
    parts.append("<h3>Fama-French Factor Shocks (%)</h3><ul>")
    for k, v in l3["factor_shocks_pct"].items():
        parts.append(f"<li><strong>{k.upper()}:</strong> {v:+.2f}%</li>")
    parts.append("</ul>")
    parts.append("<h3>Sector Shocks — Consensus (FF-implied)</h3>")
    parts.append("<table><tr><th>ETF</th><th>Consensus</th><th>FF-implied</th></tr>")
    for etf, (cons, ff) in l3["sector_shocks_pct"].items():
        parts.append(f"<tr><td>{etf}</td><td>{cons:+.1f}%</td><td>{ff:+.1f}%</td></tr>")
    parts.append("</table>")
    parts.append("<h3>Sector P&amp;L Heatmap (5-day, %)</h3>")
    parts.append("<table><tr><th>Row</th><th>SP500</th><th>XLE</th><th>XLF</th><th>XLK</th><th>ITA</th><th>XLY</th></tr>")
    for row_name, row_key in [("Consens", "consens"), ("Dissent", "dissent"), ("FF-implied", "ff_implied")]:
        row = l3["heatmap"][row_key]
        cells = "".join(f"<td>{row[e]:+.1f}</td>" for e in ["SP500", "XLE", "XLF", "XLK", "ITA", "XLY"])
        parts.append(f"<tr><td>{row_name}</td>{cells}</tr>")
    parts.append("</table>")
    if layer3:
        parts.append(
            f"<p><em>Artifact: consensus P&amp;L {layer3.get('consensus_portfolio_pnl_pct', 0):+.2f}%, "
            f"VaR {layer3.get('var_95_pct', 0):.2f}%</em></p>"
        )
    parts.append("</div>")

    pr = PORTFOLIO_TERMINAL
    parts.append('<div class="card"><h2>Hedge Fund Portfolio Recommendation</h2>')
    parts.append(
        f"<p>Rebalance equity toward defensives, deploy {pr['hedge_overlay_pct']:.1f}% hedge overlay "
        f"(GLD/TLT min-variance), hold {pr['cash_weight_pct']:.1f}% cash.</p>"
    )
    parts.append(
        f"<p><strong>VaR improvement:</strong> {pr['var_before_pct']:.2f}% → {pr['var_after_pct']:.2f}% | "
        f"<strong>Expected hedge P&amp;L (stress):</strong> {pr['expected_hedge_pnl_pct']:+.2f}%</p>"
    )
    parts.append("<h3>Recommended Trades</h3>")
    parts.append("<table><tr><th>Action</th><th>Asset</th><th>From</th><th>To</th><th>Delta (pp)</th></tr>")
    for action, asset, fr, to, delta in pr["trades"]:
        parts.append(f"<tr><td>{action}</td><td>{asset}</td><td>{fr:.1f}%</td><td>{to:.1f}%</td><td>{delta:+.1f}</td></tr>")
    parts.append("</table>")
    parts.append("<h3>Target Weights (post-rebalance)</h3><ul>")
    for etf, w in pr["target_equity"].items():
        parts.append(f"<li><strong>{etf}:</strong> {w:.1f}%</li>")
    parts.append(f"<li><strong>Hedge GLD:</strong> {pr['hedge']['GLD']:.1f}%</li>")
    parts.append(f"<li><strong>Hedge TLT:</strong> {pr['hedge']['TLT']:.1f}%</li>")
    parts.append(f"<li><strong>Cash:</strong> {pr['cash_weight_pct']:.1f}%</li></ul>")
    parts.append(f"<p><strong>Artifacts saved:</strong> <code>{html.escape(pr['artifacts_path'])}</code></p>")
    if portfolio:
        parts.append(f"<p><em>Artifact narrative: {html.escape(portfolio.get('narrative', ''))}</em></p>")
    parts.append("</div>")

    ps = PIPELINE_SUMMARY_TERMINAL
    parts.append('<div class="card"><h2>Complete Pipeline Summary</h2>')
    parts.append("<table><tr><th>Stage</th><th>Outcome</th></tr>")
    stages = [
        ("Layer 0", "13 channels scored — liberation_day_2025"),
        ("Round 1", "5 domain agents — independent analysis"),
        ("Live Debate", f"Rounds {ps['live_debate_rounds']} — DCS gates after each round"),
        ("DCS Round 5", f"{ps['dcs_round5']:.3f} — {ps['dcs_action']} (max cap)"),
        ("Moderator", f"{ps['moderator_model']} — consensus + dissent synthesis"),
        ("Plausibility Gate", f"{ps['plausibility_status']} — {ps['gate_score']:.2f}/100 (τ={ps['gate_threshold']})"),
        ("Layer 3", f"{ps['layer3_status']} — VaR, ES, Fama-French, heatmap"),
        ("Portfolio Rec", "GLD/TLT hedge overlay + rebalance trades"),
    ]
    for stage, outcome in stages:
        parts.append(f"<tr><td>{stage}</td><td>{html.escape(outcome)}</td></tr>")
    parts.append("</table>")
    parts.append(
        "<p>SPAR intentionally preserves minority tail-risk views alongside the majority scenario "
        "for robust planning rather than forcing single-point consensus.</p>"
    )
    parts.append(f"<p><strong>Research artifacts:</strong> <code>{html.escape(ps['artifacts_path'])}</code></p>")
    parts.append("</div>")
    return "".join(parts)


def parse_run_timestamp(run_dir: Path) -> datetime | None:
    m = re.search(r"run_(\d{8})_(\d{6})", run_dir.name)
    if not m:
        return None
    return datetime.strptime(f"{m.group(1)}{m.group(2)}", "%Y%m%d%H%M%S")


def format_json_block(data: object, indent: int = 2) -> str:
    return json.dumps(data, indent=indent, ensure_ascii=False)


def political_ui_excerpt() -> str:
    return format_json_block(
        {
            "political_military_escalation_trajectory": (
                "Escalation to Liberation Day with broad tariffs on major trading partners "
                "leading to significant retaliatory measures and subsequent tension escalation."
            ),
            "government_alliance_responses": [
                {
                    "US_EU": "Pre-prepared sanctions package including SWIFT exclusion, asset freezes, export controls. "
                    "Debate over EU energy dependency softens immediate full implementation.",
                },
                {
                    "NATO": "Limited military engagement confined to weapons supply; no deployment of troops but "
                    "expected increase in NATO member defence spending (e.g., Italy's ITA sector).",
                },
            ],
            "geopolitical_risk_premium_implications": (
                "Geopolitical Risk Premium would spike significantly as investors recalibrate risks associated "
                "with broad tariffs and retaliation, leading to a considerable downturn across major equity markets."
            ),
            "market_mechanisms_activated": [
                {"Sanctions_Uncertainty": "Direct impact on companies' earnings due to trade restrictions."},
                {
                    "Safe_Haven_Flows": {
                        "USD_Rallying": True,
                        "Gold_Increase": "Already elevated demand",
                        "Treasuries_Buyback": "Flight towards lower yields despite inflation",
                    }
                },
                {"Defence_Spending_Repricing": "NATO countries would likely increase military spending affecting ITA."},
            ],
        }
    )


def economic_ui_excerpt() -> str:
    return format_json_block(
        {
            "assessment": "Risk-off phase following immediate market impact.",
            "channel_scores": [
                {
                    "channel": "Energy / Commodity Price Shock",
                    "score": 98.0,
                    "key_data": "$92 WTI Crude Oil",
                    "evidence": {"current": "$92/barrel (Feb 23)", "sinceJan1YTD": "+30%"},
                },
                {
                    "channel": "Monetary Policy Constraint - Fed's boxed in",
                    "score": 82.0,
                    "evidence": {"current10yyield": "1.93%", "risingyield": "yes"},
                },
                {
                    "channel": "Inflation Shock - CPI 7.5% amplifies energy pass-through",
                    "score": 88.0,
                    "evidence": {"current": "7.5%", "amplifierenergyprice": "yes"},
                },
                {
                    "channel": "Relief Rally / Priced-In Shock",
                    "score": 68.0,
                    "evidence": {"vix31": "yes", "sppytd78": "-8.8%"},
                },
            ],
        }
    )


def social_ui_excerpt() -> str:
    return format_json_block(
        {
            "agent_id": "social_behavioural_deepseek",
            "round_number": 1,
            "sentiment_channel_weighted_importance_score": 84,
            "inflation_shock_weighted_importance_score": 81,
            "total_importance_score": 165,
            "predicted_market_impact": {
                "equity_downside_risk": 23.4,
                "energy_sector_outperformance_probability": 43,
                "spx_decrease_in_5_days": 26.2,
            },
            "justification": [
                {
                    "channel": "consumer_sentiment_behavioural_tension",
                    "score": 88,
                    "description": "Consumer sentiment already fragile due to inflation anxiety.",
                    "probability_amplified_effect": 85,
                },
                {
                    "channel": "tariff_and_trade_policy_uncertainty",
                    "score": 75,
                    "probability_amplified_effect": 82.5,
                },
                {
                    "channel": "media_narrative_speed_transmission",
                    "score": 76,
                    "probability_amplified_effect": 80,
                },
            ],
            "key_indicators_under_pressure": [
                {"indicator": "Real wage growth", "value": -2.8, "trend": "-"},
                {"indicator": "Pump price/gallon (Avg US Retail)", "value": 4.5, "trend": "+"},
            ],
        }
    )


def build_channel_table(layer0: dict) -> list[tuple[str, str, float, str]]:
    rows = []
    for ch in layer0.get("channel_rankings", []):
        rows.append(
            (
                ch.get("priority", "").upper(),
                ch.get("name", ""),
                float(ch.get("score", 0)),
                clean(ch.get("reason", "")),
            )
        )
    return rows


def build_html(
    run_dir: Path,
    shot_dir: Path,
    layer0: dict,
    round1: dict,
    bench: dict,
    dcs_scores: list,
    gate: dict | None = None,
    layer3: dict | None = None,
    portfolio: dict | None = None,
    embedded_images: dict[str, str] | None = None,
) -> str:
    run_ts = parse_run_timestamp(run_dir)
    ts_str = run_ts.strftime("%Y-%m-%d %H:%M:%S") if run_ts else "2026-07-08 00:33:05"
    regime = layer0.get("regime", {})
    shock = layer0.get("shock_parsed", {})
    channels = build_channel_table(layer0)
    images = embedded_images if embedded_images is not None else embed_screenshots(shot_dir)

    sections: list[str] = []

    sections.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SPAR Complete Proof of Work — Liberation Day Tariffs</title>
<style>
:root {{ --navy:#142864; --slate:#3c465a; --bg:#f4f6fa; --card:#fff; --accent:#2563eb; --border:#d8dee9; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Segoe UI,system-ui,sans-serif; background:var(--bg); color:#1a1a2e; line-height:1.55; }}
header {{ background:var(--navy); color:#fff; padding:2rem 1.5rem; }}
header h1 {{ margin:0 0 .5rem; font-size:1.6rem; }}
header p {{ margin:.25rem 0; opacity:.9; }}
main {{ max-width:920px; margin:0 auto; padding:1.5rem; }}
.card {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:1.25rem 1.5rem; margin-bottom:1.25rem; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
.card h2 {{ color:var(--navy); margin-top:0; font-size:1.15rem; border-bottom:2px solid var(--accent); padding-bottom:.4rem; }}
.card h3 {{ color:var(--slate); font-size:1rem; margin:1rem 0 .5rem; }}
.meta {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:.75rem; }}
.meta div {{ background:#eef2ff; padding:.6rem .8rem; border-radius:6px; font-size:.9rem; }}
table {{ width:100%; border-collapse:collapse; font-size:.85rem; margin:.75rem 0; }}
th,td {{ border:1px solid var(--border); padding:.45rem .55rem; text-align:left; }}
th {{ background:#eef2ff; }}
tr:nth-child(even) {{ background:#fafbfc; }}
.timeline {{ border-left:3px solid var(--accent); padding-left:1rem; margin:1rem 0; }}
.shot {{ margin:1.5rem 0; }}
.shot img {{ width:100%; border:1px solid var(--border); border-radius:8px; cursor:zoom-in; }}
.shot figcaption {{ font-size:.85rem; color:var(--slate); margin-top:.5rem; }}
.shot .step {{ display:inline-block; background:var(--accent); color:#fff; font-size:.75rem; padding:.15rem .5rem; border-radius:4px; margin-bottom:.35rem; }}
pre {{ background:#1e1e2e; color:#cdd6f4; padding:1rem; border-radius:8px; overflow-x:auto; font-size:.78rem; line-height:1.45; }}
.note {{ background:#fff8e6; border-left:4px solid #f59e0b; padding:.75rem 1rem; font-size:.9rem; }}
.tag {{ display:inline-block; padding:.1rem .45rem; border-radius:4px; font-size:.75rem; font-weight:600; }}
.tag-primary {{ background:#dcfce7; color:#166534; }}
.tag-secondary {{ background:#fef9c3; color:#854d0e; }}
.tag-watch {{ background:#e0e7ff; color:#3730a3; }}
.score-high {{ background:#dcfce7; }}
.score-mid {{ background:#fef9c3; }}
.score-low {{ background:#fee2e2; }}
</style>
</head>
<body>
<header>
<h1>SPAR Complete Proof of Work</h1>
<p><strong>Scenario:</strong> Liberation Day Tariffs (Apr 2, 2025) &nbsp;|&nbsp; <strong>Method:</strong> SPAR Scenario Planning</p>
<p><strong>Run ID:</strong> {html.escape(run_dir.name)} &nbsp;|&nbsp; <strong>Session start:</strong> {ts_str} (local)</p>
<p><strong>Platform:</strong> Quorum v1.1.4 &nbsp;|&nbsp; <strong>Hardware:</strong> RTX 4060 Ti 8GB, offline Ollama</p>
<p><strong>Team:</strong> SP Jain Group 3 Research Paper</p>
<p><strong>Format:</strong> Self-contained HTML — all {len(SCREENSHOTS)} terminal screenshots embedded (no external files required)</p>
</header>
<main>
""")

    sections.append("""
<div class="card">
<h2>Executive Summary</h2>
<p>This document is the complete proof-of-work record of a live SPAR (Scenario Planning via Agentic Reasoning) session:
<strong>Layer 0 → Round 1 → Live Debate (Rounds 2–5) → Moderator → Plausibility Gate → Layer 3 Portfolio</strong>.
Terminal screenshots appear in chronological order alongside structured metrics.
<strong>This file is fully portable</strong> — send it as a single attachment; recipients do not need the screenshot folder or any local paths.</p>
<p>The scenario <em>liberation_day_2025</em> models broad reciprocal US tariffs announced April 2, 2025.
Six offline Ollama models ran on RTX 4060 Ti 8GB via Quorum v1.1.4.</p>
<div class="note"><strong>Complete run:</strong> Plausibility gate CLEARED. Portfolio recommendation includes
GLD/TLT hedge overlay and sector rebalance trades. Full pipeline documented below.</div>
</div>
""")

    sections.append('<div class="card"><h2>Runtime Configuration</h2><div class="meta">')
    for label, model_id, display in RUNTIME_MODEL_MAP:
        sections.append(f'<div><strong>{html.escape(label)}</strong><br/>{html.escape(display)}<br/><code>{html.escape(model_id)}</code></div>')
    sections.append("</div>")
    sections.append("""<p><strong>Note on role assignment:</strong> The demo-diverse benchmark preset assigns roles by
fit score (e.g., phi4-mini → Moderator, qwen2.5:7b → Economic). In this live run, Quorum assigned models to roles
in session order, producing a different runtime mapping (e.g., phi4-mini ran as Political, nemotron-mini as Economic).
Benchmark tables below reflect the <em>preset</em>; screenshots reflect <em>actual runtime</em> labels.</p></div>""")

    sections.append('<div class="card"><h2>Model Benchmark Comparison (demo-diverse preset)</h2>')
    sections.append('<table><tr><th>SPAR Role (preset)</th><th>Model</th><th>Provider</th><th>Overall</th><th>Role-Fit</th></tr>')
    for role, mid, prov, overall, fit in BENCHMARK_PRESET_ROLES:
        sections.append(f"<tr><td>{role}</td><td>{mid}</td><td>{prov}</td><td>{overall:.1f}</td><td>{fit:.1f}</td></tr>")
    sections.append("</table>")

    sections.append("<h3>Frontier Reference (cloud — not in offline stack)</h3><table><tr><th>Model</th><th>Provider</th><th>Overall</th></tr>")
    for mid, prov, score in FRONTIER_REFS:
        sections.append(f"<tr><td>{mid}</td><td>{prov}</td><td>{score:.1f}</td></tr>")
    sections.append("</table>")

    sections.append("<h3>Per-Benchmark Leaders (offline stack)</h3><table><tr><th>Benchmark</th><th>Leader</th><th>Score</th></tr>")
    for bench_name, leader, score in PER_BENCH_LEADERS:
        sections.append(f"<tr><td>{bench_name}</td><td>{leader}</td><td>{score:.1f}</td></tr>")
    sections.append("</table>")

    swaps = bench.get("swap_recommendations", [])
    if swaps:
        sections.append("<h3>Role Swap Recommendations</h3><table><tr><th>Role</th><th>Current</th><th>Rec</th><th>Best</th><th>Delta</th><th>Reason</th></tr>")
        for s in swaps:
            rec = s.get("recommendation", "")
            tag = "keep" if rec == "keep" else "consider_swap"
            sections.append(
                f"<tr><td>{s.get('role','')}</td><td>{s.get('current_model','')}</td>"
                f"<td>{tag}</td><td>{s.get('best_model','')}</td><td>{s.get('delta',0):+.1f}</td>"
                f"<td>{html.escape(s.get('reason',''))}</td></tr>"
            )
        sections.append("</table>")
    sections.append("</div>")

    sections.append('<div class="card"><h2>Layer 0 — Transmission Channel Prioritization</h2>')
    sections.append(f"""<div class="meta">
<div><strong>Scenario ID</strong><br/>{html.escape(shock.get('scenario_id',''))}</div>
<div><strong>Event type</strong><br/>{', '.join(shock.get('event_type',[]))}</div>
<div><strong>Horizon</strong><br/>{html.escape(shock.get('time_horizon',''))}</div>
<div><strong>Tiers</strong><br/>7 PRIMARY / 4 SECONDARY / 2 WATCHLIST</div>
</div>""")
    sections.append("<h3>Macro Regime at Cutoff</h3><ul>")
    for k, v in regime.items():
        sections.append(f"<li><strong>{k.title()}:</strong> {html.escape(str(v))}</li>")
    sections.append("</ul>")
    sections.append("<h3>Scoring Methodology</h3>")
    sections.append("""<p>Scores 0–100 from: shock keywords 30% | mechanism 25% | regime 20% | evidence corpus 15% | sector 10%.
Known profiles (liberation_day_2025) apply score floors so critical channels are not dropped on brief shock text.
Retrieval budget: PRIMARY 6 bullets, SECONDARY 3, WATCHLIST 1.</p>""")
    sections.append("<h3>All 13 Channels (ranked)</h3><table><tr><th>Tier</th><th>Channel</th><th>Score</th><th>Reason</th></tr>")
    for tier, name, score, reason in channels:
        cls = "tag-primary" if tier == "PRIMARY" else ("tag-secondary" if tier == "SECONDARY" else "tag-watch")
        sections.append(
            f'<tr><td><span class="tag {cls}">{tier}</span></td><td>{html.escape(name)}</td>'
            f"<td>{score:.1f}</td><td>{html.escape(reason)}</td></tr>"
        )
    sections.append("</table></div>")

    sections.append('<div class="card"><h2>Round 1 — Domain Analysis Summary</h2>')
    sections.append("""<p>After Layer 0, five agents produced domain analyses. Parsed artifact quality varied:
Environmental and Devil's Advocate produced structured JSON; Social partial; Political minimal in saved artifacts;
Economic agent hallucinated Ukraine/GPT-4o context and failed JSON parse. Terminal screenshots capture richer UI output.</p>""")

    agent_notes = [
        ("Political (phi4-mini)", "Terminal showed full geopolitical JSON (escalation, alliances, GPR, safe-haven flows). Saved artifact: minimal {eventType, impact}.", political_ui_excerpt()),
        ("Economic (nemotron-mini:4b)", "Terminal showed channel-scored risk-off assessment. Saved artifact: invalid JSON referencing GPT-4o and Ukraine invasion — schema drift.", economic_ui_excerpt()),
        ("Environmental (granite3.3:8b)", "Correctly tariff-focused: Supply Chain (High), Energy (Medium), Cyber (Low). Sectors XLK, ITA, XLE.", format_json_block(round1.get("environmental_technology", {}), indent=2)),
        ("Social (llama3.1:8b)", "Terminal showed weighted scores and SPX -26.2% 5-day prediction. Saved artifact: partial behavioural channels.", social_ui_excerpt()),
        ("Devil's Advocate (qwen2.5:7b)", "Contrarian: market underestimates long-term tariff impact; GPR magnitude -3.2%; relief rally under-weighted.", format_json_block(round1.get("devils_advocate", {}), indent=2)),
    ]
    for title, note, block in agent_notes:
        sections.append(f"<h3>{html.escape(title)}</h3><p>{html.escape(note)}</p><pre>{html.escape(block)}</pre>")

    sections.append('<h3>Round 1 Quality Observations</h3><ul>')
    sections.append("<li><strong>Scenario bleed:</strong> Several agents mixed Ukraine 2022 evidence into Liberation Day tariff scenario (Layer 0 corpus includes cross-channel analogues).</li>")
    sections.append("<li><strong>JSON compliance:</strong> Economic agent output failed parse — impacts downstream DCS SP500 forecast extraction.</li>")
    sections.append("<li><strong>Display vs artifact:</strong> Political and Social terminal displays were richer than persisted round1_all.json entries.</li>")
    sections.append("<li><strong>Devil's Advocate UI:</strong> Terminal showed simplified one-liner; full JSON preserved in devils_advocate_round1.json.</li>")
    sections.append("</ul></div>")

    sections.append(render_round_debate_html(
        "Round 2",
        ROUND2_AGENT_SUMMARIES,
        [
            "Cross-agent disagreement: Whether geopolitical/tariff shocks are fully priced in.",
            "Safe-haven flows: USD rally vs gold/Treasuries under GPR elevation.",
            "Inflation pass-through: Energy/commodity channel → CPI → consumer spending.",
            "Key data points cited: 10Y Treasury 1.93%, pump price $4.50/gal, real wage growth negative.",
            "Temporal dynamics: Immediate market reaction vs longer-horizon macro impacts.",
        ],
    ))
    sections.append("""<div class="note"><strong>Artifact note:</strong> Round 2+ live-debate text in your terminal is captured in screenshots.
Persisted <code>*_roundN.json</code> files may be overwritten with later-round content.
Screenshots are the authoritative live-debate record.</div>""")
    sections.append(render_dcs_html(DCS_ROUND2_TERMINAL, dcs_for_round(dcs_scores, 2), "Round 2"))

    sections.append(render_round_debate_html(
        "Round 3",
        ROUND3_AGENT_SUMMARIES,
        [
            "Convergence toward consumer-level impacts: agents shift from investor-centric to household purchasing power.",
            "Price pass-through consensus: Energy/inflation channels now widely accepted across Political, Economic, Environmental.",
            "Social challenges safe-haven narrative: household debt and disposable income limit consumer adjustment.",
            "View revision: Multiple agents explicitly state Round 1 stances evolved after Rounds 2–3 peer feedback.",
            "Devil's Advocate anchors debate on real-world consumer struggles vs abstract investor flows.",
            "DCS trend: Info gain drops from 1.000 (R2) to 0.912 (R3) — debate vocabulary stabilizing but still novel.",
        ],
    ))
    sections.append(render_dcs_html(DCS_ROUND3_TERMINAL, dcs_for_round(dcs_scores, 3), "Round 3"))

    sections.append(render_round_debate_html(
        "Round 4",
        ROUND4_AGENT_SUMMARIES,
        [
            "Dual-thread framework emerges: Immediate Economic Shock (consumer/household) + Investor Sentiment (GPR/safe-haven).",
            "Political agent produces longest synthesis — explicitly maps responses to each peer agent by name.",
            "Devil's Advocate re-introduces GPR as sustained risk-off driver vs Round 3's consumer-only convergence.",
            "Environmental agent acts as round synthesizer — proposes integrated forecasting framework.",
            "Master Context channels cited: Consumer Financial Health, Household Debt Dynamics, Immediate Economic Shock.",
            "DCS info gain rebounds to 1.000 (from 0.912 in R3) — 52% novel vocabulary despite debate maturing.",
        ],
    ))
    sections.append(render_dcs_html(DCS_ROUND4_TERMINAL, dcs_for_round(dcs_scores, 4), "Round 4"))

    sections.append(render_round_debate_html(
        "Round 5",
        ROUND5_AGENT_SUMMARIES,
        [
            "Final convergence: dual-thread framework (Immediate Shock + GPR) accepted by all agents.",
            "Political balances immediate consumption stress vs long-term GRP — rejects either/or prioritization.",
            "Social explicitly rejects artificial dichotomy between geopolitical and immediate shock factors.",
            "Devil's Advocate anchors final round on GPR Channel with Kuwait 1990 historical analogue.",
            "DCS action switches from EXPLORE to EXPLOIT — max round cap (5) reached, not low disagreement.",
            "Pipeline transition: Live Debate + DCS complete → Moderator consensus/dissent → Plausibility Gate.",
        ],
    ))
    sections.append(render_dcs_html(DCS_ROUND5_TERMINAL, dcs_for_round(dcs_scores, 5), "Round 5"))

    sections.append("""<div class="card"><h2>DCS Progression Across Rounds 2–5</h2>
<table><tr><th>Round</th><th>DCS (terminal)</th><th>Action</th><th>Info Gain</th><th>Key note</th></tr>
<tr><td>2</td><td>0.793</td><td>EXPLORE</td><td>1.000</td><td>78% novel vocabulary — debate opening</td></tr>
<tr><td>3</td><td>0.746</td><td>EXPLORE</td><td>0.912</td><td>Consumer-level convergence begins</td></tr>
<tr><td>4</td><td>0.769</td><td>EXPLORE</td><td>1.000</td><td>GPR thread re-introduced by Devil's Advocate</td></tr>
<tr><td>5</td><td>0.761</td><td>EXPLOIT</td><td>0.984</td><td>Max round cap — stop debating</td></tr>
</table>
<p>Disagreement held at 0.450 throughout (default — fewer than two valid SP500 forecasts from Round 1 JSON).</p></div>""")

    sections.append(render_model_evaluation_html())

    sections.append(render_final_pipeline_html(gate, layer3, portfolio))

    sections.append('<div class="card"><h2>Chronological Terminal Walkthrough (Screenshots)</h2>')
    sections.append('<p>Scroll through the session as it appeared in the Quorum terminal. Each step matches the live run order. Images are embedded in this document.</p>')
    for i, (fname, title, caption) in enumerate(SCREENSHOTS, 1):
        src = images.get(fname, "")
        if not src:
            sections.append(f"""<figure class="shot timeline">
<span class="step">Step {i} of {len(SCREENSHOTS)}</span>
<h3>{html.escape(title)}</h3>
<p class="note">Screenshot missing: {html.escape(fname)}</p>
<figcaption>{html.escape(caption)}</figcaption>
</figure>""")
            continue
        sections.append(f"""<figure class="shot timeline">
<span class="step">Step {i} of {len(SCREENSHOTS)}</span>
<h3>{html.escape(title)}</h3>
<img src="{src}" alt="{html.escape(title)}" loading="lazy"/>
<figcaption>{html.escape(caption)}</figcaption>
</figure>""")
    sections.append("</div>")

    sections.append(f"""<div class="card">
<h2>Artifacts Referenced</h2>
<ul>
<li><code>{html.escape(str(run_dir / 'layer0.json'))}</code></li>
<li><code>{html.escape(str(run_dir / 'layer0_summary.txt'))}</code></li>
<li><code>{html.escape(str(run_dir / 'model_benchmark_report.json'))}</code></li>
<li><code>{html.escape(str(run_dir / 'round1_all.json'))}</code></li>
<li><code>{html.escape(str(run_dir / 'round1_displays.json'))}</code></li>
<li><code>{html.escape(str(run_dir / 'dcs_scores.json'))}</code></li>
<li><code>{html.escape(str(run_dir / 'live_debate_transcript.txt'))}</code></li>
<li><code>{html.escape(str(run_dir / 'plausibility_gate.json'))}</code></li>
<li><code>{html.escape(str(run_dir / 'layer3_quant.json'))}</code></li>
<li><code>{html.escape(str(run_dir / 'portfolio_recommendation.json'))}</code></li>
<li>Terminal artifacts also saved: <code>{html.escape(PIPELINE_SUMMARY_TERMINAL['artifacts_path'])}</code></li>
</ul>
<p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} local time</p>
</div>
""")

    sections.append("</main><footer>SPAR Complete Proof of Work — SP Jain Group 3 — Quorum CLI</footer></body></html>")
    return "".join(sections)


class ReportPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)

    def header_block(self, title: str, subtitle: str = "") -> None:
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 210, 28, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 14)
        self.set_xy(10, 8)
        self.cell(0, 8, clean(title), ln=True)
        if subtitle:
            self.set_font("Helvetica", "", 9)
            self.set_x(10)
            self.cell(0, 5, clean(subtitle), ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(6)

    def section(self, title: str) -> None:
        self.ln(2)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*NAVY)
        self.cell(0, 8, clean(title), ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def content_w(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def body(self, text: str) -> None:
        self.set_font("Helvetica", "", 9)
        self.multi_cell(self.content_w(), 4.5, clean(text))
        self.ln(1)

    def bullet(self, text: str) -> None:
        self.set_font("Helvetica", "", 9)
        self.multi_cell(self.content_w(), 4.5, clean(f"  - {text}"))

    def table_simple(self, headers: list[str], rows: list[list[str]], col_w: list[int] | None = None) -> None:
        if not rows:
            return
        n = len(headers)
        if col_w is None:
            total = 190
            col_w = [total // n] * n
        self.set_font("Helvetica", "B", 8)
        for i, h in enumerate(headers):
            self.cell(col_w[i], 6, clean(h), border=1)
        self.ln()
        self.set_font("Helvetica", "", 7)
        for row in rows:
            if self.get_y() > 270:
                self.add_page()
            heights = []
            lines_per_cell = []
            for i, cell in enumerate(row):
                lines = textwrap.wrap(clean(str(cell)), width=max(12, int(col_w[i] / 1.8))) or [""]
                lines_per_cell.append(lines)
                heights.append(len(lines))
            h = 4 * max(heights)
            y0 = self.get_y()
            x0 = self.l_margin
            for i, lines in enumerate(lines_per_cell):
                x = x0 + sum(col_w[:i])
                self.rect(x, y0, col_w[i], h)
                self.set_xy(x + 1, y0 + 1)
                for line in lines:
                    self.cell(col_w[i] - 2, 4, line)
                    self.set_x(x + 1)
                    self.set_y(self.get_y() + 4)
                self.set_xy(x + col_w[i], y0)
            self.set_y(y0 + h)

    def add_screenshot(self, path: Path, caption: str, max_h: float = 100) -> None:
        if not path.exists():
            return
        if self.get_y() > 200:
            self.add_page()
        self.set_font("Helvetica", "I", 8)
        self.multi_cell(self.content_w(), 4, clean(caption))
        self.ln(1)
        w = 190
        self.image(str(path), x=10, w=w, h=max_h)
        self.ln(4)


def build_pdf(
    run_dir: Path,
    shot_dir: Path,
    layer0: dict,
    round1: dict,
    bench: dict,
    dcs_scores: list,
    out_path: Path,
    gate: dict | None = None,
    layer3: dict | None = None,
    portfolio: dict | None = None,
) -> None:
    pdf = ReportPDF()
    run_ts = parse_run_timestamp(run_dir)
    ts_str = run_ts.strftime("%Y-%m-%d %H:%M:%S") if run_ts else "2026-07-08 00:33:05"

    pdf.add_page()
    pdf.header_block(
        "SPAR Complete Proof of Work",
        f"Liberation Day Tariffs | Run {run_dir.name} | {ts_str}",
    )
    pdf.section("Executive Summary")
    pdf.body(
        "Complete SPAR session: Layer 0 channel prioritization, Round 1 domain analysis, "
        "Rounds 2-5 live debate with DCS, Gemma3 4b moderator synthesis, plausibility gate CLEARED, "
        "Layer 3 quantification, and hedge-fund portfolio recommendation with GLD/TLT overlay."
    )

    pdf.section("Runtime Model Assignment")
    pdf.table_simple(
        ["Role", "Model ID", "Display Name"],
        [[r, m, d] for r, m, d in RUNTIME_MODEL_MAP],
        [45, 55, 90],
    )

    pdf.section("Benchmark Stack Ranking (demo-diverse preset)")
    pdf.table_simple(
        ["Role", "Model", "Overall", "Role-Fit"],
        [[r, m, f"{o:.1f}", f"{f:.1f}"] for r, m, _, o, f in BENCHMARK_PRESET_ROLES],
        [40, 50, 30, 30],
    )

    pdf.section("Frontier Reference Models")
    pdf.table_simple(
        ["Model", "Provider", "Overall"],
        [[m, p, f"{s:.1f}"] for m, p, s in FRONTIER_REFS],
        [70, 50, 30],
    )

    swaps = bench.get("swap_recommendations", [])
    if swaps:
        pdf.section("Role Swap Recommendations")
        pdf.table_simple(
            ["Role", "Current", "Rec", "Best", "Delta"],
            [
                [
                    s.get("role", ""),
                    s.get("current_model", ""),
                    s.get("recommendation", ""),
                    s.get("best_model", ""),
                    f"{s.get('delta', 0):+.1f}",
                ]
                for s in swaps
            ],
            [35, 40, 25, 40, 20],
        )

    pdf.add_page()
    pdf.section("Layer 0 — Scenario & Regime")
    shock = layer0.get("shock_parsed", {})
    pdf.body(
        f"Scenario: {shock.get('scenario_id')} | Event: {', '.join(shock.get('event_type', []))} | "
        f"Horizon: {shock.get('time_horizon')} | Tiers: 7 PRIMARY / 4 SECONDARY / 2 WATCHLIST"
    )
    for k, v in layer0.get("regime", {}).items():
        pdf.bullet(f"{k.title()}: {v}")

    pdf.section("Layer 0 — Channel Scores")
    pdf.table_simple(
        ["Tier", "Channel", "Score"],
        [[t, n, f"{s:.1f}"] for t, n, s, _ in build_channel_table(layer0)],
        [25, 115, 20],
    )

    pdf.add_page()
    pdf.section("Round 1 Agent Outputs (artifact + UI notes)")
    summaries = [
        ("Political (phi4-mini)", "Terminal: full geopolitical JSON. Artifact: minimal parse."),
        ("Economic (nemotron-mini)", "Terminal: channel scores. Artifact: JSON parse error, Ukraine bleed."),
        ("Environmental (granite3.3)", "Tariff-focused supply chain / energy / cyber channels."),
        ("Social (llama3.1)", "Behavioural amplification; terminal predicted SPX -26.2% (5d)."),
        ("Devil's Advocate (qwen2.5)", "GPR -3.2%; relief rally under-weighted vs consensus."),
    ]
    for title, note in summaries:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, clean(title), ln=True)
        pdf.body(note)

    pdf.section("Round 2 — Live Cross-Examination")
    pdf.body("Agents respond to peers' Round 1 views. Screenshots are the authoritative record.")
    for agent_title, bullets in ROUND2_AGENT_SUMMARIES:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, clean(agent_title), ln=True)
        for b in bullets:
            pdf.bullet(b)
        pdf.ln(1)

    pdf.section("DCS After Round 2 (terminal)")
    pdf.body(
        f"DCS = {DCS_ROUND2_TERMINAL['dcs_score']:.3f} | tau = {DCS_ROUND2_TERMINAL['threshold']} | "
        f"Decision: {DCS_ROUND2_TERMINAL['action']}"
    )
    for key, label in [("disagreement", "Disagreement"), ("info_gain", "Info gain"), ("rag_exhaustion", "RAG exhaustion")]:
        c = DCS_ROUND2_TERMINAL["components"][key]
        pdf.bullet(f"{label} ({c['weight']}): {c['value']:.3f} — {c['detail']}")
    dcs_r2 = dcs_for_round(dcs_scores, 2)
    if dcs_r2:
        pdf.body(f"Artifact (dcs_scores.json): DCS = {dcs_r2.get('dcs_score', 0):.4f}")

    pdf.add_page()
    pdf.section("Round 3 — Live Cross-Examination")
    pdf.body(
        "Round 3 shows convergence on consumer-level transmission channels. Agents revise Round 1 stances "
        "after peer feedback on price pass-through, household debt, and disposable income."
    )
    for agent_title, bullets in ROUND3_AGENT_SUMMARIES:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, clean(agent_title), ln=True)
        for b in bullets:
            pdf.bullet(b)
        pdf.ln(1)

    pdf.section("DCS After Round 3 (terminal)")
    pdf.body(
        f"DCS = {DCS_ROUND3_TERMINAL['dcs_score']:.3f} | tau = {DCS_ROUND3_TERMINAL['threshold']} | "
        f"Decision: {DCS_ROUND3_TERMINAL['action']} | {DCS_ROUND3_TERMINAL['reason']}"
    )
    for key, label in [("disagreement", "Disagreement"), ("info_gain", "Info gain"), ("rag_exhaustion", "RAG exhaustion")]:
        c = DCS_ROUND3_TERMINAL["components"][key]
        pdf.bullet(f"{label} ({c['weight']}): {c['value']:.3f} — {c['detail']}")
    dcs_r3 = dcs_for_round(dcs_scores, 3)
    if dcs_r3:
        pdf.body(f"Artifact (dcs_scores.json): DCS = {dcs_r3.get('dcs_score', 0):.4f}")

    pdf.add_page()
    pdf.section("Round 4 — Live Cross-Examination")
    pdf.body(
        "Round 4 crystallizes a dual-thread framework: Immediate Economic Shock (household finances) "
        "woven with Investor Sentiment (GPR, safe-haven flows). Political agent delivers comprehensive synthesis."
    )
    for agent_title, bullets in ROUND4_AGENT_SUMMARIES:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, clean(agent_title), ln=True)
        for b in bullets:
            pdf.bullet(b)
        pdf.ln(1)

    pdf.section("DCS After Round 4 (terminal)")
    pdf.body(
        f"DCS = {DCS_ROUND4_TERMINAL['dcs_score']:.3f} | tau = {DCS_ROUND4_TERMINAL['threshold']} | "
        f"Decision: {DCS_ROUND4_TERMINAL['action']} | {DCS_ROUND4_TERMINAL['reason']}"
    )
    for key, label in [("disagreement", "Disagreement"), ("info_gain", "Info gain"), ("rag_exhaustion", "RAG exhaustion")]:
        c = DCS_ROUND4_TERMINAL["components"][key]
        pdf.bullet(f"{label} ({c['weight']}): {c['value']:.3f} — {c['detail']}")
    dcs_r4 = dcs_for_round(dcs_scores, 4)
    if dcs_r4:
        pdf.body(f"Artifact (dcs_scores.json): DCS = {dcs_r4.get('dcs_score', 0):.4f}")

    pdf.add_page()
    pdf.section("Round 5 — Final Live Cross-Examination")
    pdf.body(
        "Round 5 achieves full convergence on dual-thread framework. DCS hits EXPLOIT at max round cap. "
        "Pipeline: Live Debate + DCS complete -> Moderator + Plausibility Gate."
    )
    for agent_title, bullets in ROUND5_AGENT_SUMMARIES:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, clean(agent_title), ln=True)
        for b in bullets:
            pdf.bullet(b)
        pdf.ln(1)

    pdf.section("DCS After Round 5 (terminal) — EXPLOIT")
    pdf.body(
        f"DCS = {DCS_ROUND5_TERMINAL['dcs_score']:.3f} | tau = {DCS_ROUND5_TERMINAL['threshold']} | "
        f"Decision: {DCS_ROUND5_TERMINAL['action']} | {DCS_ROUND5_TERMINAL['reason']}"
    )
    for key, label in [("disagreement", "Disagreement"), ("info_gain", "Info gain"), ("rag_exhaustion", "RAG exhaustion")]:
        c = DCS_ROUND5_TERMINAL["components"][key]
        pdf.bullet(f"{label} ({c['weight']}): {c['value']:.3f} — {c['detail']}")
    pdf.body(DCS_ROUND5_TERMINAL["next_step"])
    dcs_r5 = dcs_for_round(dcs_scores, 5)
    if dcs_r5:
        pdf.body(f"Artifact (dcs_scores.json): DCS = {dcs_r5.get('dcs_score', 0):.4f}, action = {dcs_r5.get('action', '')}")

    pdf.section("DCS Progression (Rounds 2–5)")
    pdf.table_simple(
        ["Round", "DCS", "Action", "Info Gain"],
        [["2", "0.793", "EXPLORE", "1.000"], ["3", "0.746", "EXPLORE", "0.912"],
         ["4", "0.769", "EXPLORE", "1.000"], ["5", "0.761", "EXPLOIT", "0.984"]],
        [20, 25, 30, 25],
    )

    pdf.add_page()
    pdf.section("Cross-Model Performance Evaluation")
    pdf.body(
        "Rubric-weighted scores (0-100) across Rounds 1-5. Derived from debate transcript, "
        "artifacts, and terminal screenshots."
    )
    pdf.table_simple(
        ["Rank", "Model", "Role", "Composite", "R1", "R5", "Delta"],
        [
            [
                str(i),
                m["display"],
                m["runtime_role"],
                f"{m['composite']:.1f}",
                str(m["round_totals"][1]),
                str(m["round_totals"][5]),
                f"{m['round_totals'][5] - m['round_totals'][1]:+d}",
            ]
            for i, m in enumerate(
                sorted([x for x in MODEL_EVALUATIONS if x["round_totals"].get(1)], key=lambda x: x["composite"], reverse=True),
                1,
            )
        ],
        [12, 40, 28, 18, 12, 12, 14],
    )
    pdf.body("Top performer: Granite3.3 8b (82.4). Weakest: Nemotron Mini 4b (60.2, R1 JSON failure).")
    pdf.body("Best improver: Phi4 Mini (+24 R1 to R4). Steadiest: Llama3.1 (+14 R1 to R5).")
    pdf.body("Moderator Gemma3 4b synthesis score: 90/100 (not in live debate).")

    pdf.add_page()
    pdf.section("Moderator Synthesis (Layer 2) — Gemma3 4b")
    c = MODERATOR_TERMINAL["consensus"]
    d = MODERATOR_TERMINAL["dissent"]
    pdf.body(f"Consensus: {c['direction']}, confidence {c['confidence']}, plausibility {c['plausibility_score']}/100")
    pdf.body(f"Channels: {', '.join(c['channels'])}")
    pdf.table_simple(
        ["ETF", "Consensus %", "Dissent %"],
        [[e, f"{c['magnitude_pct'][e]:+.1f}", f"{d['magnitude_pct'][e]:+.1f}"] for e in c["magnitude_pct"]],
        [30, 35, 35],
    )
    pdf.body(f"Dissent agents: {', '.join(d['agents'])} | plausibility {d['plausibility_score']}/100")

    pdf.section("Plausibility Gate — CLEARED")
    pg = PLAUSIBILITY_TERMINAL
    pdf.body(
        f"{pg['decision']} | Composite {pg['composite_score']}/100 (detail {pg['composite_detail']}) | "
        f"tau={pg['threshold']} | Mod {pg['moderator_score']} | FSR {pg['fsr_score']}"
    )
    if gate:
        pdf.body(f"Artifact: composite {gate.get('composite_score', 0):.2f}, passed={gate.get('passed')}")

    pdf.section("Layer 3 — Portfolio Quantification")
    l3 = LAYER3_TERMINAL
    pdf.body(
        f"Consensus P&L {l3['consensus_portfolio_pnl_pct']:+.2f}% | Dissent tail {l3['dissent_portfolio_pnl_pct']:+.2f}% | "
        f"VaR {l3['var_95_pct']:.2f}% | ES {l3['expected_shortfall_pct']:.2f}%"
    )
    pdf.body(
        f"Factors: Mkt {l3['factor_shocks_pct']['market']:+.2f}%, "
        f"SMB {l3['factor_shocks_pct']['smb']:+.2f}%, HML {l3['factor_shocks_pct']['hml']:+.2f}%"
    )

    pdf.section("Portfolio Recommendation")
    pr = PORTFOLIO_TERMINAL
    pdf.body(
        f"VaR {pr['var_before_pct']:.2f}% -> {pr['var_after_pct']:.2f}% | "
        f"Hedge overlay {pr['hedge_overlay_pct']:.0f}% | Cash {pr['cash_weight_pct']:.1f}%"
    )
    pdf.table_simple(
        ["Action", "Asset", "Delta pp"],
        [[t[0], t[1], f"{t[4]:+.1f}"] for t in pr["trades"]],
        [35, 30, 25],
    )
    pdf.body(f"Artifacts: {pr['artifacts_path']}")

    pdf.add_page()
    pdf.section("Terminal Screenshots (chronological)")
    for fname, title, caption in SCREENSHOTS:
        path = shot_dir / fname
        pdf.add_screenshot(path, f"{title}: {caption}", max_h=95)

    pdf.section("Artifacts")
    for name in [
        "layer0.json", "model_benchmark_report.json", "round1_all.json", "dcs_scores.json",
        "plausibility_gate.json", "layer3_quant.json", "portfolio_recommendation.json",
    ]:
        pdf.bullet(str(run_dir / name))
    pdf.ln(3)
    pdf.body(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    pdf.output(str(out_path))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate complete SPAR proof-of-work HTML + PDF")
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    run_dir: Path = args.run_dir

    shot_dir = ensure_screenshots(run_dir)
    embedded_images = embed_screenshots(shot_dir)
    layer0 = load_json(run_dir / "layer0.json")
    round1 = load_json(run_dir / "round1_all.json")
    bench = load_json(run_dir / "model_benchmark_report.json")
    dcs_path = run_dir / "dcs_scores.json"
    dcs_scores = load_json(dcs_path) if dcs_path.exists() else []

    gate_path = run_dir / "plausibility_gate.json"
    layer3_path = run_dir / "layer3_quant.json"
    portfolio_path = run_dir / "portfolio_recommendation.json"
    gate = load_json(gate_path) if gate_path.exists() else None
    layer3 = load_json(layer3_path) if layer3_path.exists() else None
    portfolio = load_json(portfolio_path) if portfolio_path.exists() else None

    html_path = run_dir / "SPAR_Complete_Proof_of_Work.html"
    pdf_path = run_dir / "SPAR_Complete_Proof_of_Work.pdf"

    html_path.write_text(
        build_html(
            run_dir, shot_dir, layer0, round1, bench, dcs_scores,
            gate, layer3, portfolio, embedded_images=embedded_images,
        ),
        encoding="utf-8",
    )
    build_pdf(run_dir, shot_dir, layer0, round1, bench, dcs_scores, pdf_path, gate, layer3, portfolio)

    print(f"HTML: {html_path}")
    print(f"PDF:  {pdf_path}")
    print(f"Screenshots: {shot_dir}")
    size_mb = html_path.stat().st_size / (1024 * 1024)
    embedded_count = sum(1 for v in embedded_images.values() if v)
    print(f"HTML size: {size_mb:.2f} MB (self-contained, {embedded_count}/{len(SCREENSHOTS)} screenshots embedded)")


if __name__ == "__main__":
    main()
