"""SPAR Layer 3 — portfolio quantification & hedge-fund recommendation.

Maps validated moderator scenarios to sector shocks via Fama-French loadings,
computes portfolio VaR/ES, optimises a min-variance GLD/TLT hedge sleeve, and
outputs actionable rebalance trades for the paper deliverable.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from .spar_plausibility_gate import parse_moderator_output

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_FACTORS = _REPO_ROOT / "config" / "spar_layer3_factors.json"

MAG_TICKERS = ("SP500", "XLE", "XLF", "XLK", "ITA", "XLY")


@dataclass(frozen=True)
class PortfolioTrade:
    asset: str
    action: str  # REDUCE | INCREASE | ADD_HEDGE | HOLD
    current_weight_pct: float
    target_weight_pct: float
    delta_weight_pct: float
    reason: str


@dataclass
class PortfolioRecommendation:
    baseline_equity_weights: dict[str, float]
    recommended_equity_weights: dict[str, float]
    hedge_weights: dict[str, float]
    cash_weight_pct: float
    trades: list[PortfolioTrade] = field(default_factory=list)
    var_before_pct: float = 0.0
    var_after_hedge_pct: float = 0.0
    expected_hedge_pnl_pct: float = 0.0
    narrative: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_equity_weights": self.baseline_equity_weights,
            "recommended_equity_weights": self.recommended_equity_weights,
            "hedge_weights": self.hedge_weights,
            "cash_weight_pct": round(self.cash_weight_pct, 3),
            "trades": [
                {
                    "asset": t.asset,
                    "action": t.action,
                    "current_weight_pct": round(t.current_weight_pct, 2),
                    "target_weight_pct": round(t.target_weight_pct, 2),
                    "delta_weight_pct": round(t.delta_weight_pct, 2),
                    "reason": t.reason,
                }
                for t in self.trades
            ],
            "var_before_pct": round(self.var_before_pct, 3),
            "var_after_hedge_pct": round(self.var_after_hedge_pct, 3),
            "expected_hedge_pnl_pct": round(self.expected_hedge_pnl_pct, 3),
            "narrative": self.narrative,
        }


@dataclass(frozen=True)
class ConfidenceBands:
    agent_mean_confidence: float
    agent_calibration_score: float
    sector_bands: dict[str, dict[str, float]]
    portfolio_pnl_low_pct: float
    portfolio_pnl_mid_pct: float
    portfolio_pnl_high_pct: float
    var_95_low_pct: float
    var_95_high_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_mean_confidence": round(self.agent_mean_confidence, 3),
            "agent_calibration_score": round(self.agent_calibration_score, 1),
            "sector_bands_pct": self.sector_bands,
            "portfolio_pnl_low_pct": round(self.portfolio_pnl_low_pct, 3),
            "portfolio_pnl_mid_pct": round(self.portfolio_pnl_mid_pct, 3),
            "portfolio_pnl_high_pct": round(self.portfolio_pnl_high_pct, 3),
            "var_95_low_pct": round(self.var_95_low_pct, 3),
            "var_95_high_pct": round(self.var_95_high_pct, 3),
        }


@dataclass(frozen=True)
class Layer3QuantResult:
    consensus_returns: dict[str, float]
    dissent_returns: dict[str, float]
    factor_implied_returns: dict[str, float]
    factor_shocks: dict[str, float]
    portfolio_weights: dict[str, float]
    consensus_portfolio_pnl_pct: float
    dissent_portfolio_pnl_pct: float
    var_95_pct: float
    expected_shortfall_pct: float
    hedge_weights: dict[str, float]
    portfolio_recommendation: PortfolioRecommendation
    confidence_bands: ConfidenceBands | None
    sector_heatmap_text: str
    narrative: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "consensus_returns_pct": self.consensus_returns,
            "dissent_returns_pct": self.dissent_returns,
            "factor_implied_returns_pct": self.factor_implied_returns,
            "factor_shocks_pct": self.factor_shocks,
            "portfolio_weights": self.portfolio_weights,
            "consensus_portfolio_pnl_pct": round(self.consensus_portfolio_pnl_pct, 3),
            "dissent_portfolio_pnl_pct": round(self.dissent_portfolio_pnl_pct, 3),
            "var_95_pct": round(self.var_95_pct, 3),
            "expected_shortfall_pct": round(self.expected_shortfall_pct, 3),
            "hedge_weights": self.hedge_weights,
            "portfolio_recommendation": self.portfolio_recommendation.to_dict(),
            "confidence_bands": self.confidence_bands.to_dict() if self.confidence_bands else None,
            "sector_heatmap_text": self.sector_heatmap_text,
            "narrative": self.narrative,
        }


@lru_cache(maxsize=2)
def _load_factors_cached(path_str: str) -> dict[str, Any]:
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def load_layer3_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or _DEFAULT_FACTORS
    if not path.exists():
        alt = Path.cwd() / "config" / "spar_layer3_factors.json"
        path = alt if alt.exists() else path
    if not path.exists():
        raise FileNotFoundError(f"Layer 3 factor config not found: {path}")
    return _load_factors_cached(str(path.resolve()))


def _extract_returns(scenario: dict[str, Any] | None) -> dict[str, float]:
    if not scenario:
        return {}
    mag = scenario.get("magnitude_pct")
    if not isinstance(mag, dict):
        return {}
    out: dict[str, float] = {}
    for ticker in MAG_TICKERS:
        try:
            out[ticker] = float(mag[ticker])
        except (TypeError, ValueError):
            continue
    return out


def _portfolio_pnl(weights: dict[str, float], returns: dict[str, float]) -> float:
    return sum(weights.get(t, 0.0) * returns.get(t, 0.0) for t in MAG_TICKERS)


def _portfolio_vol(weights: dict[str, float], daily_vol: dict[str, float]) -> float:
    var = 0.0
    for ticker in MAG_TICKERS:
        w = weights.get(ticker, 0.0)
        vol = daily_vol.get(ticker, 1.5)
        var += (w * vol) ** 2
    return math.sqrt(var)


def _compute_var_es(mu: float, sigma: float, z: float = 1.645) -> tuple[float, float]:
    var_95 = -(mu - z * sigma)
    phi_z = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    es = -(mu - sigma * phi_z / 0.05)
    return var_95, es


def _normalise_direction(value: Any) -> str:
    if not isinstance(value, str):
        return "neutral"
    text = value.strip().lower()
    if "neg" in text:
        return "negative"
    if "pos" in text:
        return "positive"
    return "neutral"


def _channel_blob(channels: list[str] | None) -> str:
    return " ".join(channels or []).lower()


def _infer_factor_shocks(
    consensus: dict[str, Any] | None,
    channels: list[str] | None,
    config: dict[str, Any],
) -> dict[str, float]:
    """Map scenario direction + transmission channels to Fama-French factor moves."""
    direction = _normalise_direction(consensus.get("direction") if consensus else None)
    base = dict(
        config.get("scenario_factor_shocks_by_direction", {}).get(
            direction,
            {"market": -0.008, "smb": 0.0, "hml": 0.0},
        )
    )
    blob = _channel_blob(channels)
    adjustments = config.get("channel_factor_adjustments", {})
    for key, adj in adjustments.items():
        if key in blob:
            for factor, delta in adj.items():
                base[factor] = base.get(factor, 0.0) + float(delta)

    # Anchor market factor to consensus SP500 shock when available
    if consensus:
        mag = consensus.get("magnitude_pct")
        if isinstance(mag, dict) and "SP500" in mag:
            try:
                sp = float(mag["SP500"]) / 100.0
                base["market"] = 0.55 * base.get("market", 0.0) + 0.45 * sp
            except (TypeError, ValueError):
                pass
    return {k: round(v * 100, 3) for k, v in base.items()}  # store as %


def _fama_french_sector_returns(
    factor_shocks_pct: dict[str, float],
    config: dict[str, Any],
) -> dict[str, float]:
    """R_i = beta_m * dM + s * dSMB + h * dHML (factor shocks in %)."""
    loadings = config.get("sector_factor_loadings", {})
    out: dict[str, float] = {}
    dm = factor_shocks_pct.get("market", 0.0)
    ds = factor_shocks_pct.get("smb", 0.0)
    dh = factor_shocks_pct.get("hml", 0.0)
    for ticker in MAG_TICKERS:
        ld = loadings.get(ticker, {})
        beta = float(ld.get("market", 1.0))
        smb = float(ld.get("smb", 0.0))
        hml = float(ld.get("hml", 0.0))
        out[ticker] = round(beta * dm + smb * ds + hml * dh, 2)
    return out


def _blend_returns(
    moderator: dict[str, float],
    factor_implied: dict[str, float],
    weight_moderator: float = 0.65,
) -> dict[str, float]:
    """Blend moderator sector shocks with FF-implied returns for robustness."""
    blended: dict[str, float] = {}
    for ticker in MAG_TICKERS:
        m = moderator.get(ticker)
        f = factor_implied.get(ticker)
        if m is not None and f is not None:
            blended[ticker] = round(weight_moderator * m + (1 - weight_moderator) * f, 2)
        elif m is not None:
            blended[ticker] = m
        elif f is not None:
            blended[ticker] = f
    return blended


def _invert_2x2(m: list[list[float]]) -> list[list[float]] | None:
    a, b = m[0]
    c, d = m[1]
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    inv_det = 1.0 / det
    return [
        [d * inv_det, -b * inv_det],
        [-c * inv_det, a * inv_det],
    ]


def _mat_vec(m: list[list[float]], v: list[float]) -> list[float]:
    return [sum(m[i][j] * v[j] for j in range(len(v))) for i in range(len(m))]


def _min_variance_hedge_weights(
    equity_weights: dict[str, float],
    hedge_assets: list[str],
    config: dict[str, Any],
) -> dict[str, float]:
    """Min-variance hedge overlay: h* = -Sigma_h^{-1} * cov(portfolio, hedges)."""
    policy = config.get("portfolio_policy", {})
    max_sleeve = float(policy.get("max_hedge_sleeve_pct", 0.35))
    hedge_cov = config.get("hedge_covariance_daily_pct2", {})
    sector_hedge_cov = config.get("sector_hedge_cov_daily_pct2", {})
    hedge_meta = config.get("hedge_universe", {})

    if len(hedge_assets) == 0:
        return {}

    # Build Sigma_h
    sigma_h: list[list[float]] = []
    for h1 in hedge_assets:
        row = []
        for h2 in hedge_assets:
            row.append(float(hedge_cov.get(h1, {}).get(h2, 0.0)))
        sigma_h.append(row)

    # cov(portfolio, hedge_j) = sum_i w_i * cov(sector_i, hedge_j)
    cov_ph: list[float] = []
    for hedge in hedge_assets:
        c = 0.0
        for ticker in MAG_TICKERS:
            w = equity_weights.get(ticker, 0.0)
            c += w * float(sector_hedge_cov.get(ticker, {}).get(hedge, 0.0))
        cov_ph.append(c)

    inv = _invert_2x2(sigma_h) if len(hedge_assets) == 2 else None
    if inv is None:
        # Fallback: channel-heuristic split
        return _heuristic_hedge_weights(equity_weights, config, hedge_assets)

    h_raw = _mat_vec(inv, [-x for x in cov_ph])
    h_nonneg = [max(0.0, x) for x in h_raw]
    total = sum(h_nonneg)
    if total <= 0:
        return {a: 0.0 for a in hedge_assets}

    # Scale to max hedge sleeve (weights are portfolio fractions)
    scale = min(1.0, max_sleeve / total) if total > max_sleeve else 1.0
    return {hedge_assets[i]: round(h_nonneg[i] * scale, 4) for i in range(len(hedge_assets))}


def _heuristic_hedge_weights(
    equity_weights: dict[str, float],
    config: dict[str, Any],
    hedge_assets: list[str],
    portfolio_pnl: float = -1.0,
    channels: list[str] | None = None,
) -> dict[str, float]:
    """Fallback hedge split when covariance matrix is singular."""
    if portfolio_pnl >= 0:
        return {a: 0.0 for a in hedge_assets}

    policy = config.get("portfolio_policy", {})
    max_sleeve = float(policy.get("max_hedge_sleeve_pct", 0.35))
    severity = min(1.0, abs(portfolio_pnl) / 8.0)
    total_hedge = round(0.12 + 0.23 * severity, 3)
    total_hedge = min(total_hedge, max_sleeve)

    blob = _channel_blob(channels)
    gld_share, tlt_share = 0.35, 0.65
    if "energy" in blob or "commodity" in blob or "inflation" in blob:
        gld_share, tlt_share = 0.55, 0.45
    if "growth" in blob or "trade" in blob or "credit" in blob:
        gld_share, tlt_share = 0.30, 0.70

    out: dict[str, float] = {a: 0.0 for a in hedge_assets}
    if "GLD" in out:
        out["GLD"] = round(total_hedge * gld_share, 4)
    if "TLT" in out:
        out["TLT"] = round(total_hedge * tlt_share, 4)
    return out


def _portfolio_var_with_hedge(
    equity_weights: dict[str, float],
    hedge_weights: dict[str, float],
    daily_vol: dict[str, float],
    config: dict[str, Any],
    scenario_mu: float,
) -> tuple[float, float]:
    """Return (var_before, var_after) using parametric 1-day model."""
    sigma_equity = _portfolio_vol(equity_weights, daily_vol)
    var_before, _ = _compute_var_es(scenario_mu, sigma_equity)

    hedge_assets = list(hedge_weights.keys())
    hedge_cov = config.get("hedge_covariance_daily_pct2", {})
    sector_hedge_cov = config.get("sector_hedge_cov_daily_pct2", {})

    var_h = 0.0
    for h1, w1 in hedge_weights.items():
        for h2, w2 in hedge_weights.items():
            var_h += w1 * w2 * float(hedge_cov.get(h1, {}).get(h2, 0.0))

    cov_cross = 0.0
    for h, wh in hedge_weights.items():
        for ticker in MAG_TICKERS:
            we = equity_weights.get(ticker, 0.0)
            cov_cross += 2 * wh * we * float(sector_hedge_cov.get(ticker, {}).get(h, 0.0))

    sigma_total = math.sqrt(max(0.0, sigma_equity**2 + var_h + cov_cross))
    hedge_meta = config.get("hedge_universe", {})
    hedge_mu = sum(
        hedge_weights.get(h, 0.0) * float(hedge_meta.get(h, {}).get("stress_return_pct", 0.0))
        for h in hedge_weights
    )
    mu_total = scenario_mu + hedge_mu
    var_after, _ = _compute_var_es(mu_total, sigma_total)
    return var_before, var_after


def _build_portfolio_recommendation(
    baseline_weights: dict[str, float],
    consensus_returns: dict[str, float],
    hedge_weights: dict[str, float],
    config: dict[str, Any],
    channels: list[str] | None,
    consensus_pnl: float,
) -> PortfolioRecommendation:
    """Generate hedge-fund style rebalance: trim losers, add hedges, park cash."""
    policy = config.get("portfolio_policy", {})
    min_cash = float(policy.get("min_cash_pct", 0.05))
    max_cut = float(policy.get("max_single_sector_cut_pct", 0.08))
    trim_threshold = float(policy.get("sector_trim_threshold_pct", -2.0))
    boost_threshold = float(policy.get("sector_boost_threshold_pct", 2.0))

    hedge_total = sum(hedge_weights.values())
    cash = min_cash
    if consensus_pnl < -3.0:
        cash = min(0.15, min_cash + abs(consensus_pnl) * 0.01)

    equity_budget = max(0.0, 1.0 - cash - hedge_total)
    recommended = dict(baseline_weights)
    trades: list[PortfolioTrade] = []
    freed = 0.0

    # Trim sectors with negative scenario shocks
    for ticker in MAG_TICKERS:
        ret = consensus_returns.get(ticker, 0.0)
        current = baseline_weights.get(ticker, 0.0)
        if ret <= trim_threshold and current > 0:
            cut = min(max_cut, current * 0.35, abs(ret) / 100 * 0.5)
            new_w = max(0.0, current - cut)
            recommended[ticker] = new_w
            freed += current - new_w
            trades.append(
                PortfolioTrade(
                    asset=ticker,
                    action="REDUCE",
                    current_weight_pct=round(current * 100, 2),
                    target_weight_pct=round(new_w * 100, 2),
                    delta_weight_pct=round((new_w - current) * 100, 2),
                    reason=f"Scenario shock {ret:+.1f}% under {_channel_blob(channels) or 'consensus'} channels",
                )
            )

    # Boost relative winners modestly (rotate within equity sleeve)
    boost_pool = freed * 0.25
    winners = [
        (t, consensus_returns.get(t, 0.0))
        for t in MAG_TICKERS
        if consensus_returns.get(t, 0.0) >= boost_threshold
    ]
    winners.sort(key=lambda x: x[1], reverse=True)
    for ticker, ret in winners[:2]:
        if boost_pool <= 0:
            break
        add = min(boost_pool, max_cut * 0.5)
        current = recommended.get(ticker, 0.0)
        recommended[ticker] = current + add
        boost_pool -= add
        trades.append(
            PortfolioTrade(
                asset=ticker,
                action="INCREASE",
                current_weight_pct=round((current - add) * 100, 2),
                target_weight_pct=round(recommended[ticker] * 100, 2),
                delta_weight_pct=round(add * 100, 2),
                reason=f"Relative outperformer in scenario ({ret:+.1f}%)",
            )
        )

    # Normalise equity sleeve to budget
    eq_sum = sum(recommended.get(t, 0.0) for t in MAG_TICKERS)
    if eq_sum > 0 and equity_budget > 0:
        scale = equity_budget / eq_sum
        for ticker in MAG_TICKERS:
            recommended[ticker] = round(recommended.get(ticker, 0.0) * scale, 4)

    hedge_meta = config.get("hedge_universe", {})
    for asset, weight in hedge_weights.items():
        if weight <= 0:
            continue
        label = hedge_meta.get(asset, {}).get("label", asset)
        trades.append(
            PortfolioTrade(
                asset=asset,
                action="ADD_HEDGE",
                current_weight_pct=0.0,
                target_weight_pct=round(weight * 100, 2),
                delta_weight_pct=round(weight * 100, 2),
                reason=f"Min-variance hedge sleeve — {label}",
            )
        )

    if cash > min_cash:
        trades.append(
            PortfolioTrade(
                asset="CASH",
                action="INCREASE",
                current_weight_pct=round(min_cash * 100, 2),
                target_weight_pct=round(cash * 100, 2),
                delta_weight_pct=round((cash - min_cash) * 100, 2),
                reason="Liquidity buffer for tail scenario / implementation lag",
            )
        )

    var_before, var_after = _portfolio_var_with_hedge(
        baseline_weights, hedge_weights, config.get("daily_volatility_pct", {}), config, consensus_pnl
    )
    hedge_mu = sum(
        hedge_weights.get(h, 0.0) * float(hedge_meta.get(h, {}).get("stress_return_pct", 0.0))
        for h in hedge_weights
    )

    narrative = (
        f"Rebalance equity sleeve toward defensives, deploy {hedge_total*100:.1f}% hedge overlay "
        f"(GLD/TLT min-variance), hold {cash*100:.1f}% cash. "
        f"Est. VaR improves {var_before:.2f}% -> {var_after:.2f}% (parametric 1-day)."
    )

    return PortfolioRecommendation(
        baseline_equity_weights={k: baseline_weights.get(k, 0.0) for k in MAG_TICKERS},
        recommended_equity_weights={k: recommended.get(k, 0.0) for k in MAG_TICKERS},
        hedge_weights=dict(hedge_weights),
        cash_weight_pct=cash,
        trades=trades,
        var_before_pct=var_before,
        var_after_hedge_pct=var_after,
        expected_hedge_pnl_pct=hedge_mu,
        narrative=narrative,
    )


def _collect_agent_forecasts(
    round1_results: dict[str, Any] | None,
) -> tuple[list[float], dict[str, list[float]]]:
    """Agent confidence scores and per-sector magnitude forecasts from Round 1."""
    confidences: list[float] = []
    sector_lists: dict[str, list[float]] = {t: [] for t in MAG_TICKERS}
    if not round1_results:
        return confidences, sector_lists

    for data in round1_results.values():
        if not isinstance(data, dict) or "parse_error" in data:
            continue
        conf = data.get("confidence")
        if conf is not None:
            try:
                val = float(conf)
                if val > 1.0:
                    val = val / 100.0
                confidences.append(min(1.0, max(0.0, val)))
            except (TypeError, ValueError):
                pass
        mag = _extract_returns(data)
        for ticker, pct in mag.items():
            sector_lists[ticker].append(pct)
    return confidences, sector_lists


def _compute_confidence_bands(
    round1_results: dict[str, Any] | None,
    consensus_returns: dict[str, float],
    weights: dict[str, float],
    daily_vol: dict[str, float],
    z: float,
    moderator_plausibility: float | None = None,
) -> ConfidenceBands | None:
    confidences, sector_lists = _collect_agent_forecasts(round1_results)
    if not confidences and not any(sector_lists.values()):
        return None

    agent_mean = sum(confidences) / len(confidences) if confidences else 0.65
    calibration = agent_mean * 100.0
    if moderator_plausibility is not None:
        calibration = 0.6 * calibration + 0.4 * moderator_plausibility

    sector_bands: dict[str, dict[str, float]] = {}
    low_returns: dict[str, float] = {}
    high_returns: dict[str, float] = {}

    for ticker in MAG_TICKERS:
        vals = sector_lists.get(ticker, [])
        mid = consensus_returns.get(ticker, 0.0)
        if len(vals) >= 2:
            low = min(vals)
            high = max(vals)
        elif len(vals) == 1:
            spread = max(1.5, abs(vals[0]) * 0.25)
            low = vals[0] - spread
            high = vals[0] + spread
        else:
            spread = max(1.0, abs(mid) * 0.2)
            low = mid - spread
            high = mid + spread
        sector_bands[ticker] = {"low": round(low, 2), "mid": round(mid, 2), "high": round(high, 2)}
        low_returns[ticker] = low
        high_returns[ticker] = high

    pnl_low = _portfolio_pnl(weights, low_returns)
    pnl_mid = _portfolio_pnl(weights, consensus_returns)
    pnl_high = _portfolio_pnl(weights, high_returns)
    sigma = _portfolio_vol(weights, daily_vol)
    var_low, _ = _compute_var_es(pnl_high, sigma, z)  # high returns -> lower VaR
    var_high, _ = _compute_var_es(pnl_low, sigma, z)

    return ConfidenceBands(
        agent_mean_confidence=agent_mean,
        agent_calibration_score=calibration,
        sector_bands=sector_bands,
        portfolio_pnl_low_pct=pnl_low,
        portfolio_pnl_mid_pct=pnl_mid,
        portfolio_pnl_high_pct=pnl_high,
        var_95_low_pct=var_low,
        var_95_high_pct=var_high,
    )


def _heatmap_cell(value: float) -> str:
    if value <= -6:
        return "####"
    if value <= -3:
        return "### "
    if value < 0:
        return "##  "
    if value == 0:
        return "    "
    if value < 3:
        return " ++ "
    if value < 6:
        return "+++ "
    return "++++"


def format_sector_pnl_heatmap(
    consensus_returns: dict[str, float],
    dissent_returns: dict[str, float],
    factor_implied: dict[str, float],
    weights: dict[str, float],
    confidence_bands: ConfidenceBands | None = None,
) -> str:
    """ASCII sector P&L heatmap for terminal display and artifact export."""
    header = " ".join(f"{t:>6}" for t in MAG_TICKERS)
    lines = [
        "**Sector P&L heatmap (5-day scenario shocks, %)**",
        "",
        f"         {header}",
    ]

    def row(label: str, data: dict[str, float]) -> str:
        cells = " ".join(f"{data.get(t, 0.0):+6.1f}" for t in MAG_TICKERS)
        return f"{label:8} {cells}"

    def row_vis(label: str, data: dict[str, float]) -> str:
        cells = " ".join(f"{_heatmap_cell(data.get(t, 0.0)):>6}" for t in MAG_TICKERS)
        return f"{label:8} {cells}"

    lines.append(row("Consens", consensus_returns))
    lines.append(row("Dissent", dissent_returns))
    lines.append(row("FF-implied", factor_implied))
    weighted = {t: weights.get(t, 0.0) * consensus_returns.get(t, 0.0) for t in MAG_TICKERS}
    lines.append(row("Wt*PnL", weighted))
    lines.append("")
    lines.append("Intensity (loss -> gain):")
    lines.append(row_vis("Consens", consensus_returns))

    if confidence_bands:
        lines.append("")
        lines.append("**Agent-derived confidence bands (Round 1 dispersion):**")
        for ticker in MAG_TICKERS:
            band = confidence_bands.sector_bands.get(ticker, {})
            if band:
                lines.append(
                    f"- {ticker}: {band.get('low', 0):+.1f}% to {band.get('high', 0):+.1f}% "
                    f"(mid {band.get('mid', 0):+.1f}%)"
                )
        lines.append(
            f"- Portfolio P&L band: **{confidence_bands.portfolio_pnl_low_pct:+.2f}%** to "
            f"**{confidence_bands.portfolio_pnl_high_pct:+.2f}%** "
            f"(mid {confidence_bands.portfolio_pnl_mid_pct:+.2f}%)"
        )
        lines.append(
            f"- VaR95 band: {confidence_bands.var_95_low_pct:.2f}% to "
            f"{confidence_bands.var_95_high_pct:.2f}% "
            f"(agent calibration {confidence_bands.agent_calibration_score:.0f}/100)"
        )

    return "\n".join(lines)


def save_layer3_artifacts(run_dir: Path, result: Layer3QuantResult) -> None:
    """Persist heatmap text and optional PNG chart when matplotlib is available."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "sector_pnl_heatmap.txt").write_text(result.sector_heatmap_text, encoding="utf-8")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        tickers = list(MAG_TICKERS)
        consensus = [result.consensus_returns.get(t, 0.0) for t in tickers]
        dissent = [result.dissent_returns.get(t, 0.0) for t in tickers]
        x = range(len(tickers))
        width = 0.35
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.bar([i - width / 2 for i in x], consensus, width, label="Consensus", color="#c0392b")
        ax.bar([i + width / 2 for i in x], dissent, width, label="Dissent", color="#8e44ad", alpha=0.85)
        ax.axhline(0, color="#333", linewidth=0.8)
        ax.set_xticks(list(x))
        ax.set_xticklabels(tickers)
        ax.set_ylabel("Scenario shock (%)")
        ax.set_title("SPAR Layer 3 — Sector scenario shocks")
        ax.legend()
        fig.tight_layout()
        fig.savefig(run_dir / "sector_pnl_heatmap.png", dpi=120)
        plt.close(fig)
    except ImportError:
        pass


def run_layer3_quantification(
    moderator_raw: str,
    *,
    config: dict[str, Any] | None = None,
    round1_results: dict[str, Any] | None = None,
    moderator_plausibility: float | None = None,
) -> Layer3QuantResult:
    """Quantify consensus + dissent scenarios into VaR, hedge, and portfolio action."""
    cfg = config or load_layer3_config()
    consensus, dissent = parse_moderator_output(moderator_raw)
    consensus_ret_raw = _extract_returns(consensus)
    dissent_ret = _extract_returns(dissent) or consensus_ret_raw

    channels: list[str] = []
    if isinstance(consensus, dict):
        ch = consensus.get("primary_transmission_channels")
        if isinstance(ch, list):
            channels = [str(c) for c in ch]

    factor_shocks = _infer_factor_shocks(consensus, channels, cfg)
    factor_implied = _fama_french_sector_returns(factor_shocks, cfg)
    consensus_ret = _blend_returns(consensus_ret_raw, factor_implied)

    weights = dict(cfg.get("default_portfolio_weights", {}))
    daily_vol = cfg.get("daily_volatility_pct", {})
    z = float(cfg.get("z_score_95", 1.645))
    policy = cfg.get("portfolio_policy", {})
    hedge_assets = list(policy.get("hedge_assets_active", ["GLD", "TLT"]))

    consensus_pnl = _portfolio_pnl(weights, consensus_ret)
    dissent_pnl = _portfolio_pnl(weights, dissent_ret)
    sigma = _portfolio_vol(weights, daily_vol)
    tail_mu = 0.6 * consensus_pnl + 0.4 * dissent_pnl
    var_95, es = _compute_var_es(tail_mu, sigma, z)

    if policy.get("use_min_variance_hedge", True) and consensus_pnl < 0:
        hedge = _min_variance_hedge_weights(weights, hedge_assets, cfg)
    else:
        hedge = _heuristic_hedge_weights(weights, cfg, hedge_assets, consensus_pnl, channels)

    if consensus_pnl >= 0 and sum(hedge.values()) == 0:
        hedge = {a: 0.0 for a in hedge_assets}

    recommendation = _build_portfolio_recommendation(
        weights, consensus_ret, hedge, cfg, channels, consensus_pnl
    )

    confidence_bands = _compute_confidence_bands(
        round1_results,
        consensus_ret,
        weights,
        daily_vol,
        z,
        moderator_plausibility=moderator_plausibility,
    )
    heatmap = format_sector_pnl_heatmap(
        consensus_ret, dissent_ret, factor_implied, weights, confidence_bands
    )

    narrative = (
        f"Under the consensus scenario the model portfolio shocks {consensus_pnl:+.2f}% "
        f"(moderator + Fama-French blend). Dissent tail {dissent_pnl:+.2f}%. "
        f"Parametric VaR95 ~ {var_95:.2f}% with ES ~ {es:.2f}%. "
        f"{recommendation.narrative}"
    )

    return Layer3QuantResult(
        consensus_returns=consensus_ret,
        dissent_returns=dissent_ret,
        factor_implied_returns=factor_implied,
        factor_shocks=factor_shocks,
        portfolio_weights=weights,
        consensus_portfolio_pnl_pct=consensus_pnl,
        dissent_portfolio_pnl_pct=dissent_pnl,
        var_95_pct=var_95,
        expected_shortfall_pct=es,
        hedge_weights=hedge,
        portfolio_recommendation=recommendation,
        confidence_bands=confidence_bands,
        sector_heatmap_text=heatmap,
        narrative=narrative,
    )


def format_portfolio_recommendation(rec: PortfolioRecommendation) -> str:
    """Hedge-fund deliverable: trades, target weights, VaR impact."""
    lines = [
        "**Hedge Fund Portfolio Recommendation (post-Layer 3)**",
        "",
        rec.narrative,
        "",
        f"**VaR (95%, 1-day):** {rec.var_before_pct:.2f}% before hedge -> "
        f"**{rec.var_after_hedge_pct:.2f}%** after hedge overlay",
        f"**Expected hedge sleeve P&L (stress):** {rec.expected_hedge_pnl_pct:+.2f}%",
        f"**Target cash:** {rec.cash_weight_pct * 100:.1f}%",
        "",
        "**Recommended trades:**",
    ]
    for trade in rec.trades:
        sign = "+" if trade.delta_weight_pct >= 0 else ""
        lines.append(
            f"- **{trade.action}** {trade.asset}: "
            f"{trade.current_weight_pct:.1f}% -> {trade.target_weight_pct:.1f}% "
            f"({sign}{trade.delta_weight_pct:.1f} pp) — {trade.reason}"
        )

    lines.append("\n**Target equity weights (after rebalance):**")
    for ticker in MAG_TICKERS:
        w = rec.recommended_equity_weights.get(ticker, 0.0)
        if w > 0:
            lines.append(f"- {ticker}: **{w * 100:.1f}%**")

    if rec.hedge_weights:
        lines.append("\n**Hedge overlay (add to portfolio):**")
        for asset, weight in rec.hedge_weights.items():
            if weight > 0:
                lines.append(f"- {asset}: **{weight * 100:.1f}%**")

    return "\n".join(lines)


def format_layer3_summary(result: Layer3QuantResult) -> str:
    """Human-readable Layer 3 block for Quorum UI."""
    lines = [
        "**Layer 3 — Portfolio Quantification**",
        "",
        f"**Consensus portfolio P&L:** {result.consensus_portfolio_pnl_pct:+.2f}%",
        f"**Dissent tail P&L:** {result.dissent_portfolio_pnl_pct:+.2f}%",
        f"**VaR (95%, 1-day parametric):** {result.var_95_pct:.2f}%",
        f"**Expected Shortfall:** {result.expected_shortfall_pct:.2f}%",
        "",
        "**Factor shocks (Fama-French, %):**",
        f"- Market: {result.factor_shocks.get('market', 0):+.2f}% | "
        f"SMB: {result.factor_shocks.get('smb', 0):+.2f}% | "
        f"HML: {result.factor_shocks.get('hml', 0):+.2f}%",
        "",
        "**Sector shocks (consensus % — moderator + FF blend):**",
    ]
    for ticker in MAG_TICKERS:
        val = result.consensus_returns.get(ticker)
        ff = result.factor_implied_returns.get(ticker)
        if val is not None:
            ff_note = f" (FF-implied {ff:+.1f}%)" if ff is not None else ""
            lines.append(f"- {ticker}: {val:+.1f}%{ff_note}")

    lines.append("\n**Min-variance hedge weights:**")
    for asset, weight in result.hedge_weights.items():
        if weight > 0:
            lines.append(f"- {asset}: **{weight * 100:.1f}%**")

    lines.append(f"\n{result.narrative}")
    lines.append("")
    lines.append(result.sector_heatmap_text)
    lines.append("")
    lines.append(format_portfolio_recommendation(result.portfolio_recommendation))
    return "\n".join(lines)
