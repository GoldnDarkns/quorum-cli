"""SPAR Debate Continuation Score (DCS) — explore / exploit controller.

After each live debate round (Round 2+), computes whether agents should debate
again or pass to the Moderator (Layer 2).

Paper formula (SPAR.html / spar-prompts.html):
    DCS = w1·Disagreement + w2·InfoGain + w3·(1 − RAG_exhaustion)
    If DCS > τ and round < max_rounds → EXPLORE (another live round)
    Else → EXPLOIT (Moderator synthesis)
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

MAG_TICKERS = ("SP500", "XLE", "XLF", "XLK", "ITA", "XLY")

DEFAULT_THRESHOLD = 0.35
DEFAULT_MAX_ROUNDS = 5
WEIGHTS = (0.34, 0.33, 0.33)  # disagreement, info_gain, (1 - rag_exhaustion)


@dataclass(frozen=True)
class DcsComponents:
    disagreement: float
    info_gain: float
    rag_exhaustion: float
    disagreement_detail: str
    info_gain_detail: str
    rag_exhaustion_detail: str

    @property
    def continuation_value(self) -> float:
        w1, w2, w3 = WEIGHTS
        return w1 * self.disagreement + w2 * self.info_gain + w3 * (1.0 - self.rag_exhaustion)


@dataclass(frozen=True)
class DcsDecision:
    round_number: int
    score: float
    threshold: float
    max_rounds: int
    action: str  # "explore" | "exploit"
    components: DcsComponents
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_number": self.round_number,
            "dcs_score": round(self.score, 4),
            "threshold": self.threshold,
            "max_rounds": self.max_rounds,
            "action": self.action,
            "reason": self.reason,
            "components": {
                "disagreement": round(self.components.disagreement, 4),
                "info_gain": round(self.components.info_gain, 4),
                "rag_exhaustion": round(self.components.rag_exhaustion, 4),
                "disagreement_detail": self.components.disagreement_detail,
                "info_gain_detail": self.components.info_gain_detail,
                "rag_exhaustion_detail": self.components.rag_exhaustion_detail,
            },
        }


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_magnitude_pct(parsed: dict[str, Any]) -> dict[str, float]:
    mag = parsed.get("magnitude_pct")
    if not isinstance(mag, dict):
        return {}
    out: dict[str, float] = {}
    for ticker in MAG_TICKERS:
        val = _safe_float(mag.get(ticker))
        if val is not None:
            out[ticker] = val
    return out


def score_disagreement(round1_results: dict[str, Any]) -> tuple[float, str]:
    """Variance of Round 1 SP500 forecasts + direction diversity."""
    sp500_vals: list[float] = []
    directions: list[str] = []
    for data in round1_results.values():
        if not isinstance(data, dict) or "parse_error" in data:
            continue
        mag = extract_magnitude_pct(data)
        if "SP500" in mag:
            sp500_vals.append(mag["SP500"])
        direction = data.get("direction")
        if isinstance(direction, str) and direction.strip():
            directions.append(direction.strip().lower())

    if len(sp500_vals) < 2:
        return 0.45, "Fewer than two valid SP500 forecasts — default moderate disagreement."

    mean = sum(sp500_vals) / len(sp500_vals)
    variance = sum((v - mean) ** 2 for v in sp500_vals) / len(sp500_vals)
    spread_pp = variance**0.5
    magnitude_score = min(1.0, spread_pp / 8.0)

    unique_dirs = len(set(directions))
    if unique_dirs <= 1:
        direction_score = 0.2
    elif unique_dirs == 2:
        direction_score = 0.65
    else:
        direction_score = 1.0

    score = 0.65 * magnitude_score + 0.35 * direction_score
    detail = (
        f"SP500 spread σ≈{spread_pp:.1f}pp across {len(sp500_vals)} agents; "
        f"{unique_dirs} distinct direction(s) ({', '.join(sorted(set(directions))) or 'n/a'})."
    )
    return score, detail


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{3,}", text.lower())


def score_information_gain(
    prior_round_speeches: dict[str, str] | None,
    current_round_speeches: dict[str, str],
) -> tuple[float, str]:
    """How much new content appeared vs the previous live debate round."""
    if not prior_round_speeches:
        return 0.85, "First live debate round — high information gain by definition."

    prior_tokens = set(_tokenize(" ".join(prior_round_speeches.values())))
    current_tokens = set(_tokenize(" ".join(current_round_speeches.values())))
    if not current_tokens:
        return 0.0, "Empty current round — no new information."

    new_tokens = current_tokens - prior_tokens
    novelty_ratio = len(new_tokens) / max(1, len(current_tokens))
    score = min(1.0, novelty_ratio * 2.2)
    detail = (
        f"{len(new_tokens)} new token groups vs prior round "
        f"({novelty_ratio:.0%} of current-round vocabulary is novel)."
    )
    return score, detail


def score_rag_exhaustion(debate_transcript: str) -> tuple[float, str]:
    """Repetition in the growing transcript — high means agents are rehashing."""
    words = _tokenize(debate_transcript)
    if len(words) < 80:
        return 0.15, "Short transcript — low repetition risk."

    trigrams = [tuple(words[i : i + 3]) for i in range(len(words) - 2)]
    if not trigrams:
        return 0.15, "Insufficient text for repetition scan."

    counts = Counter(trigrams)
    repeated = sum(1 for c in counts.values() if c >= 3)
    repetition_ratio = repeated / max(1, len(counts))
    score = min(1.0, repetition_ratio * 4.0)
    detail = (
        f"{repeated} repeated 3-gram patterns in transcript "
        f"({repetition_ratio:.0%} of unique phrases recur)."
    )
    return score, detail


def compute_dcs(
    round_number: int,
    round1_results: dict[str, Any],
    prior_live_speeches: dict[str, str] | None,
    current_live_speeches: dict[str, str],
    debate_transcript: str,
    threshold: float = DEFAULT_THRESHOLD,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    round1_displays: dict[str, str] | None = None,
) -> DcsDecision:
    """Compute DCS after completing live debate ``round_number``."""
    d_score, d_detail = score_disagreement(round1_results)

    if prior_live_speeches:
        prior_for_gain = prior_live_speeches
    elif round_number == 2 and round1_displays:
        prior_for_gain = round1_displays
    else:
        prior_for_gain = None

    i_score, i_detail = score_information_gain(prior_for_gain, current_live_speeches)
    r_score, r_detail = score_rag_exhaustion(debate_transcript)

    components = DcsComponents(
        disagreement=d_score,
        info_gain=i_score,
        rag_exhaustion=r_score,
        disagreement_detail=d_detail,
        info_gain_detail=i_detail,
        rag_exhaustion_detail=r_detail,
    )
    score = components.continuation_value

    if round_number >= max_rounds:
        action = "exploit"
        reason = f"Round {round_number} reached max cap ({max_rounds}) — stop debating."
    elif score > threshold:
        action = "explore"
        reason = (
            f"DCS {score:.3f} > τ {threshold:.2f} — agents still disagree or produce new information."
        )
    else:
        action = "exploit"
        reason = (
            f"DCS {score:.3f} ≤ τ {threshold:.2f} — debate converged or exhausted — synthesise."
        )

    return DcsDecision(
        round_number=round_number,
        score=score,
        threshold=threshold,
        max_rounds=max_rounds,
        action=action,
        components=components,
        reason=reason,
    )


def format_dcs_summary(decision: DcsDecision) -> str:
    """Human-readable DCS block for Quorum terminal UI."""
    c = decision.components
    w1, w2, w3 = WEIGHTS
    lines = [
        "**Debate Continuation Score (DCS)**",
        "",
        f"After Round **{decision.round_number}**: **DCS = {decision.score:.3f}** (threshold τ = {decision.threshold:.2f})",
        f"**Decision: {decision.action.upper()}** — {decision.reason}",
        "",
        "**Components:**",
        f"- Disagreement ({w1:.0%} weight): **{c.disagreement:.3f}** — {c.disagreement_detail}",
        f"- Information gain ({w2:.0%} weight): **{c.info_gain:.3f}** — {c.info_gain_detail}",
        f"- RAG exhaustion ({w3:.0%} weight, inverted): **{c.rag_exhaustion:.3f}** — {c.rag_exhaustion_detail}",
        "",
        "_Formula: DCS = w₁·Disagreement + w₂·InfoGain + w₃·(1 − RAG_exhaustion)_",
    ]
    if decision.action == "explore":
        lines.append(f"\n→ **Another live round will run** (max round {decision.max_rounds}).")
    else:
        lines.append("\n→ **Passing to Moderator** for consensus + dissent synthesis.")
    return "\n".join(lines)
