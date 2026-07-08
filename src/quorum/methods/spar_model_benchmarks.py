"""Comparative public-benchmark analysis for SPAR offline model stacks.

Maps each model in a preset (e.g. demo-diverse) against six SPAR-relevant
benchmarks and ranks role fit to guide model swaps after debate trials.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "spar_model_benchmarks.json"

SPAR_ROLES = [
    "Political",
    "Economic",
    "Environmental",
    "Social",
    "DevilsAdvocate",
    "Moderator",
]


@dataclass(frozen=True)
class ModelBenchmarkProfile:
    model_id: str
    provider: str
    spar_role: str | None
    overall_score: float
    role_fit_score: float
    benchmark_scores: dict[str, float]
    frontier_reference: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "spar_role": self.spar_role,
            "overall_score": round(self.overall_score, 2),
            "role_fit_score": round(self.role_fit_score, 2),
            "benchmark_scores": {k: round(v, 2) for k, v in self.benchmark_scores.items()},
            "frontier_reference": self.frontier_reference,
        }


@lru_cache(maxsize=2)
def _load_config_cached(path_str: str) -> dict[str, Any]:
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def load_benchmark_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or _DEFAULT_CONFIG
    if not path.exists():
        alt = Path.cwd() / "config" / "spar_model_benchmarks.json"
        path = alt if alt.exists() else path
    if not path.exists():
        raise FileNotFoundError(f"Model benchmark config not found: {path}")
    return _load_config_cached(str(path.resolve()))


def _overall_score(scores: dict[str, float], benchmark_keys: list[str]) -> float:
    vals = [scores[k] for k in benchmark_keys if k in scores]
    return sum(vals) / len(vals) if vals else 0.0


def _role_fit_score(scores: dict[str, float], role: str, role_weights: dict[str, Any]) -> float:
    weights = role_weights.get(role, {})
    total_w = 0.0
    acc = 0.0
    for bench, weight in weights.items():
        if bench in scores:
            acc += float(weight) * scores[bench]
            total_w += float(weight)
    return acc / total_w if total_w else _overall_score(scores, list(scores))


def build_model_profile(
    model_id: str,
    entry: dict[str, Any],
    role_weights: dict[str, Any],
    benchmark_keys: list[str],
) -> ModelBenchmarkProfile:
    scores = {k: float(v) for k, v in entry.get("scores", {}).items()}
    role = entry.get("spar_role")
    role_fit = _role_fit_score(scores, role, role_weights) if role else _overall_score(scores, benchmark_keys)
    return ModelBenchmarkProfile(
        model_id=model_id,
        provider=str(entry.get("provider", "unknown")),
        spar_role=role,
        overall_score=_overall_score(scores, benchmark_keys),
        role_fit_score=role_fit,
        benchmark_scores=scores,
        frontier_reference=bool(entry.get("frontier_reference", False)),
    )


def models_for_preset(
    preset: str,
    config: dict[str, Any] | None = None,
    *,
    include_frontier: bool = True,
) -> list[ModelBenchmarkProfile]:
    """Return benchmark profiles for models in a SPAR preset plus frontier refs."""
    data = config or load_benchmark_config()
    benchmark_keys = list(data.get("benchmarks", {}).keys())
    role_weights = data.get("role_weights", {})
    profiles: list[ModelBenchmarkProfile] = []

    for model_id, entry in data.get("models", {}).items():
        if entry.get("frontier_reference"):
            if include_frontier:
                profiles.append(build_model_profile(model_id, entry, role_weights, benchmark_keys))
            continue
        if entry.get("in_spar_preset") == preset:
            profiles.append(build_model_profile(model_id, entry, role_weights, benchmark_keys))
    return profiles


def rank_by_role(profiles: list[ModelBenchmarkProfile], role: str) -> list[ModelBenchmarkProfile]:
    """Rank all stack models by fitness for a given SPAR role."""
    data = load_benchmark_config()
    role_weights = data.get("role_weights", {})
    benchmark_keys = list(data.get("benchmarks", {}).keys())

    ranked: list[ModelBenchmarkProfile] = []
    for profile in profiles:
        if profile.frontier_reference:
            continue
        fit = _role_fit_score(profile.benchmark_scores, role, role_weights)
        ranked.append(
            ModelBenchmarkProfile(
                model_id=profile.model_id,
                provider=profile.provider,
                spar_role=profile.spar_role,
                overall_score=profile.overall_score,
                role_fit_score=fit,
                benchmark_scores=profile.benchmark_scores,
                frontier_reference=False,
            )
        )
    ranked.sort(key=lambda p: p.role_fit_score, reverse=True)
    return ranked


def recommend_role_swaps(
    preset: str,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Suggest better models per role based on public benchmarks (offline stack only)."""
    data = config or load_benchmark_config()
    profiles = models_for_preset(preset, data, include_frontier=False)
    suggestions: list[dict[str, Any]] = []

    for role in SPAR_ROLES:
        current = next((p for p in profiles if p.spar_role == role), None)
        ranked = rank_by_role(profiles, role)
        if not ranked:
            continue
        best = ranked[0]
        if current is None:
            continue
        if best.model_id == current.model_id:
            suggestions.append(
                {
                    "role": role,
                    "current_model": current.model_id,
                    "recommendation": "keep",
                    "best_model": best.model_id,
                    "current_fit": round(current.role_fit_score, 1),
                    "best_fit": round(best.role_fit_score, 1),
                    "reason": "Current assignment matches top benchmark fit for this role.",
                }
            )
        else:
            delta = best.role_fit_score - current.role_fit_score
            suggestions.append(
                {
                    "role": role,
                    "current_model": current.model_id,
                    "recommendation": "consider_swap" if delta >= 3.0 else "keep",
                    "best_model": best.model_id,
                    "current_fit": round(current.role_fit_score, 1),
                    "best_fit": round(best.role_fit_score, 1),
                    "delta": round(delta, 1),
                    "reason": (
                        f"{best.model_id} scores +{delta:.1f} pts higher on role-weighted benchmarks."
                        if delta >= 3.0
                        else "Marginal benchmark gain — keep unless debate quality disagrees."
                    ),
                }
            )
    return suggestions


def build_analysis_report(preset: str = "demo-diverse") -> dict[str, Any]:
    """Full comparative analysis payload for manifest / JSON export."""
    config = load_benchmark_config()
    stack = models_for_preset(preset, config, include_frontier=True)
    stack_only = [p for p in stack if not p.frontier_reference]
    frontier = [p for p in stack if p.frontier_reference]

    stack_sorted = sorted(stack_only, key=lambda p: p.overall_score, reverse=True)
    frontier_sorted = sorted(frontier, key=lambda p: p.overall_score, reverse=True)

    gap_to_frontier: dict[str, float] = {}
    if frontier_sorted:
        best_frontier = frontier_sorted[0].overall_score
        for p in stack_only:
            gap_to_frontier[p.model_id] = round(best_frontier - p.overall_score, 1)

    return {
        "preset": preset,
        "benchmarks": list(config.get("benchmarks", {}).keys()),
        "benchmark_meta": config.get("benchmarks", {}),
        "stack_ranking": [p.to_dict() for p in stack_sorted],
        "frontier_reference": [p.to_dict() for p in frontier_sorted],
        "gap_to_best_frontier": gap_to_frontier,
        "role_rankings": {
            role: [p.to_dict() for p in rank_by_role(stack_only, role)[:4]]
            for role in SPAR_ROLES
        },
        "swap_recommendations": recommend_role_swaps(preset, config),
        "spar_relevance": config.get("spar_relevance", ""),
    }


def format_benchmark_report(preset: str = "demo-diverse") -> str:
    """Human-readable comparative analysis for terminal / Quorum UI."""
    report = build_analysis_report(preset)
    lines = [
        "**SPAR Model Benchmark Analysis**",
        "",
        f"Preset: **{preset}** — six public benchmarks vs frontier references",
        "",
        "**Stack ranking (overall SPAR benchmark average):**",
    ]
    for idx, entry in enumerate(report["stack_ranking"], start=1):
        lines.append(
            f"{idx}. **{entry['model_id']}** ({entry['provider']}) — "
            f"overall {entry['overall_score']:.1f}, role-fit {entry['role_fit_score']:.1f} "
            f"[{entry['spar_role']}]"
        )

    if report["frontier_reference"]:
        lines.append("\n**Frontier reference (cloud — not in offline stack):**")
        for entry in report["frontier_reference"]:
            lines.append(
                f"- {entry['model_id']}: overall {entry['overall_score']:.1f} "
                f"(gap vs stack leader informs upgrade path)"
            )

    lines.append("\n**Per-benchmark leaders (offline stack):**")
    bench_keys = report["benchmarks"]
    stack = report["stack_ranking"]
    for bench in bench_keys:
        leader = max(stack, key=lambda e: e["benchmark_scores"].get(bench, 0))
        score = leader["benchmark_scores"].get(bench, 0)
        meta = report["benchmark_meta"].get(bench, {})
        lines.append(f"- {meta.get('name', bench)}: **{leader['model_id']}** ({score:.1f})")

    lines.append("\n**Role swap recommendations (benchmark-driven):**")
    for rec in report["swap_recommendations"]:
        flag = "✓ KEEP" if rec["recommendation"] == "keep" else "↔ SWAP?"
        lines.append(
            f"- {rec['role']:16} {flag} — {rec['current_model']} "
            f"(fit {rec['current_fit']}) → best: {rec['best_model']} ({rec['best_fit']})"
        )
        lines.append(f"  _{rec['reason']}_")

    lines.append(
        "\n_Note: Public leaderboard scores inform model selection; final verdict should "
        "combine debate quality from your SPAR trial runs._"
    )
    return "\n".join(lines)
