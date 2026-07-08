"""SPAR Layer 2 Plausibility Gate — route low-scoring scenarios to human review.

After the Moderator produces consensus + dissent JSON, the gate checks whether
the composite plausibility score meets the configured threshold.

Three-pronged plausibility (spar-presentation.html):
    1) historical analogue match (moderator / Layer 0)
    2) internal economic consistency (moderator self-score)
    3) Federal Reserve FSR stress-language benchmark (objective alignment score)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .spar_fsr_benchmark import FsrBenchmarkResult, format_fsr_benchmark_summary, score_fsr_alignment

DEFAULT_THRESHOLD = 60.0
DEFAULT_MODERATOR_WEIGHT = 0.55
DEFAULT_FSR_WEIGHT = 0.45


@dataclass(frozen=True)
class PlausibilityGateDecision:
    passed: bool
    threshold: float
    consensus_score: float | None
    dissent_score: float | None
    composite_score: float | None
    fsr_alignment_score: float | None
    moderator_weight: float
    fsr_weight: float
    consensus_scenario: dict[str, Any] | None
    minority_dissent: dict[str, Any] | None
    fsr_benchmark: dict[str, Any] | None
    action: str  # "proceed" | "human_review"
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "threshold": self.threshold,
            "consensus_score": self.consensus_score,
            "dissent_score": self.dissent_score,
            "composite_score": self.composite_score,
            "fsr_alignment_score": self.fsr_alignment_score,
            "moderator_weight": self.moderator_weight,
            "fsr_weight": self.fsr_weight,
            "action": self.action,
            "reason": self.reason,
            "consensus_scenario": self.consensus_scenario,
            "minority_dissent": self.minority_dissent,
            "fsr_benchmark": self.fsr_benchmark,
        }


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_json_objects(raw: str) -> list[dict[str, Any]]:
    """Extract one or two JSON objects from moderator output."""
    text = raw.strip()
    objects: list[dict[str, Any]] = []

    fence_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    for block in fence_blocks:
        try:
            objects.append(json.loads(block))
        except json.JSONDecodeError:
            continue
    if objects:
        return objects

    segments = re.split(r"\n\s*\n", _strip_fences(text))
    for segment in segments:
        start = segment.find("{")
        end = segment.rfind("}")
        if start == -1 or end == -1:
            continue
        try:
            objects.append(json.loads(segment[start : end + 1]))
        except json.JSONDecodeError:
            continue
    return objects


def parse_moderator_output(raw: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (consensus_scenario, minority_dissent) parsed from moderator text."""
    objects = _extract_json_objects(raw)
    consensus: dict[str, Any] | None = None
    dissent: dict[str, Any] | None = None

    for obj in objects:
        obj_type = str(obj.get("type", "")).lower()
        if obj_type == "consensus_scenario":
            consensus = obj
        elif obj_type == "minority_dissent":
            dissent = obj

    if consensus is None and objects:
        consensus = objects[0]
    if dissent is None and len(objects) > 1:
        dissent = objects[1]
    return consensus, dissent


def _safe_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < 0:
        return 0.0
    if score > 100:
        return 100.0
    return score


def _composite_score(
    moderator_score: float,
    fsr_score: float | None,
    *,
    moderator_weight: float,
    fsr_weight: float,
    fsr_enabled: bool,
) -> float:
    if not fsr_enabled or fsr_score is None:
        return moderator_score
    total = moderator_weight + fsr_weight
    if total <= 0:
        return moderator_score
    return (moderator_weight * moderator_score + fsr_weight * fsr_score) / total


def evaluate_plausibility_gate(
    moderator_raw: str,
    threshold: float = DEFAULT_THRESHOLD,
    *,
    enabled: bool = True,
    scenario_id: str = "generic",
    fsr_enabled: bool = True,
    moderator_weight: float = DEFAULT_MODERATOR_WEIGHT,
    fsr_weight: float = DEFAULT_FSR_WEIGHT,
) -> tuple[PlausibilityGateDecision, FsrBenchmarkResult | None]:
    """Evaluate whether the moderator scenario passes the plausibility gate."""
    if not enabled:
        return PlausibilityGateDecision(
            passed=True,
            threshold=threshold,
            consensus_score=None,
            dissent_score=None,
            composite_score=None,
            fsr_alignment_score=None,
            moderator_weight=moderator_weight,
            fsr_weight=fsr_weight,
            consensus_scenario=None,
            minority_dissent=None,
            fsr_benchmark=None,
            action="proceed",
            reason="Plausibility gate disabled — auto-proceed.",
        ), None

    consensus, dissent = parse_moderator_output(moderator_raw)
    consensus_score = _safe_score(consensus.get("plausibility_score")) if consensus else None
    dissent_score = _safe_score(dissent.get("plausibility_score")) if dissent else None

    fsr_result: FsrBenchmarkResult | None = None
    fsr_alignment: float | None = None
    if fsr_enabled and consensus is not None:
        fsr_result = score_fsr_alignment(consensus, scenario_id)
        fsr_alignment = fsr_result.alignment_score

    if consensus_score is None:
        return PlausibilityGateDecision(
            passed=False,
            threshold=threshold,
            consensus_score=None,
            dissent_score=dissent_score,
            composite_score=None,
            fsr_alignment_score=fsr_alignment,
            moderator_weight=moderator_weight,
            fsr_weight=fsr_weight,
            consensus_scenario=consensus,
            minority_dissent=dissent,
            fsr_benchmark=fsr_result.to_dict() if fsr_result else None,
            action="human_review",
            reason="Could not parse consensus plausibility_score — route to human review.",
        ), fsr_result

    composite = _composite_score(
        consensus_score,
        fsr_alignment,
        moderator_weight=moderator_weight,
        fsr_weight=fsr_weight,
        fsr_enabled=fsr_enabled and fsr_alignment is not None,
    )

    if composite >= threshold:
        fsr_note = f"; FSR alignment {fsr_alignment:.0f}/100" if fsr_alignment is not None else ""
        return PlausibilityGateDecision(
            passed=True,
            threshold=threshold,
            consensus_score=consensus_score,
            dissent_score=dissent_score,
            composite_score=composite,
            fsr_alignment_score=fsr_alignment,
            moderator_weight=moderator_weight,
            fsr_weight=fsr_weight,
            consensus_scenario=consensus,
            minority_dissent=dissent,
            fsr_benchmark=fsr_result.to_dict() if fsr_result else None,
            action="proceed",
            reason=(
                f"Composite plausibility {composite:.0f} ≥ τ {threshold:.0f} "
                f"(moderator {consensus_score:.0f}{fsr_note}) — cleared for Layer 3."
            ),
        ), fsr_result

    fsr_note = (
        f", FSR {fsr_alignment:.0f}/100 → composite {composite:.0f}"
        if fsr_alignment is not None
        else ""
    )
    return PlausibilityGateDecision(
        passed=False,
        threshold=threshold,
        consensus_score=consensus_score,
        dissent_score=dissent_score,
        composite_score=composite,
        fsr_alignment_score=fsr_alignment,
        moderator_weight=moderator_weight,
        fsr_weight=fsr_weight,
        consensus_scenario=consensus,
        minority_dissent=dissent,
        fsr_benchmark=fsr_result.to_dict() if fsr_result else None,
        action="human_review",
        reason=(
            f"Composite plausibility {composite:.0f} < τ {threshold:.0f} "
            f"(moderator {consensus_score:.0f}{fsr_note}) — flagged for human review."
        ),
    ), fsr_result


def format_plausibility_gate_summary(
    decision: PlausibilityGateDecision,
    fsr_result: FsrBenchmarkResult | None = None,
) -> str:
    """Human-readable Plausibility Gate block for Quorum terminal UI."""
    lines = [
        "**Plausibility Gate (Layer 2)**",
        "",
        f"**Decision: {decision.action.upper().replace('_', ' ')}** — {decision.reason}",
        "",
        "**Scores:**",
        f"- Moderator consensus plausibility: **{decision.consensus_score if decision.consensus_score is not None else 'n/a'}** / 100",
        f"- Minority dissent plausibility: **{decision.dissent_score if decision.dissent_score is not None else 'n/a'}** / 100",
    ]
    if decision.fsr_alignment_score is not None:
        lines.append(
            f"- Federal Reserve FSR alignment: **{decision.fsr_alignment_score:.1f}** / 100"
        )
    if decision.composite_score is not None and decision.fsr_alignment_score is not None:
        lines.append(
            f"- Composite gate score ({decision.moderator_weight:.0%} mod + "
            f"{decision.fsr_weight:.0%} FSR): **{decision.composite_score:.1f}** / 100"
        )
    lines.append(f"- Gate threshold τ: **{decision.threshold:.0f}**")

    if decision.passed:
        lines.append("\n→ **Cleared** — ready for Layer 3 (VaR / hedge) when implemented.")
    else:
        lines.append(
            "\n→ **Human review required** — acknowledge the flag before ending the run. "
            "Layer 3 will not run until a reviewer approves."
        )

    if fsr_result is not None:
        lines.append("")
        lines.append(format_fsr_benchmark_summary(fsr_result))

    return "\n".join(lines)
