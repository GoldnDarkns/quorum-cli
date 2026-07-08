"""Federal Reserve FSR benchmark for SPAR plausibility validation (paper prong 3).

Compares the Moderator consensus scenario against curated expert stress-language
excerpts from U.S. Federal Reserve Financial Stability Reports.

Paper framing (spar-presentation.html):
    three-pronged plausibility → historical analogue match,
    internal economic consistency, and benchmark comparison against
    Federal Reserve stress scenario language.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "spar_fsr_benchmark.json"

FINANCIAL_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "could", "would",
    "may", "than", "into", "over", "under", "have", "has", "been", "were",
    "are", "was", "will", "also", "more", "such", "their", "they", "them",
}


@dataclass(frozen=True)
class FsrPassageMatch:
    passage_id: str
    score: float
    themes: tuple[str, ...]
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "passage_id": self.passage_id,
            "score": round(self.score, 4),
            "themes": list(self.themes),
            "excerpt": self.excerpt[:240],
        }


@dataclass(frozen=True)
class FsrBenchmarkResult:
    alignment_score: float
    scenario_id: str
    fsr_editions: tuple[str, ...]
    matched_passages: tuple[FsrPassageMatch, ...]
    scenario_text_preview: str
    source: str
    citation: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "alignment_score": round(self.alignment_score, 2),
            "scenario_id": self.scenario_id,
            "fsr_editions": list(self.fsr_editions),
            "matched_passages": [m.to_dict() for m in self.matched_passages],
            "scenario_text_preview": self.scenario_text_preview[:500],
            "source": self.source,
            "citation": self.citation,
            "detail": self.detail,
        }


def _tokenize(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]{3,}", text.lower()))
    return {t for t in tokens if t not in FINANCIAL_STOPWORDS}


def _resolve_config_path(config_path: Path | None = None) -> Path:
    path = config_path or _DEFAULT_CONFIG
    if path.exists():
        return path
    alt = Path.cwd() / "config" / "spar_fsr_benchmark.json"
    if alt.exists():
        return alt
    return path


@lru_cache(maxsize=4)
def _load_corpus_cached(path_str: str) -> dict[str, Any]:
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def load_fsr_corpus(config_path: Path | None = None) -> dict[str, Any]:
    """Load curated FSR benchmark passages from JSON config."""
    path = _resolve_config_path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"FSR benchmark config not found: {path}")
    return _load_corpus_cached(str(path.resolve()))


def resolve_fsr_passages(
    scenario_id: str,
    corpus: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], tuple[str, ...], str]:
    """Return passages, FSR edition labels, and corpus source string."""
    data = corpus or load_fsr_corpus()
    scenarios = data.get("scenarios", {})
    entry = scenarios.get(scenario_id) or scenarios.get("generic", {})
    passages = list(entry.get("passages", []))
    generic_passages = list(scenarios.get("generic", {}).get("passages", []))

    seen_ids: set[str] = set()
    merged: list[dict[str, Any]] = []
    for item in passages + generic_passages:
        pid = str(item.get("id", ""))
        if pid and pid in seen_ids:
            continue
        if pid:
            seen_ids.add(pid)
        merged.append(item)

    editions = tuple(str(e) for e in entry.get("fsr_editions", []))
    source = str(data.get("source", "Federal Reserve FSR"))
    return merged, editions, source


def build_consensus_text(consensus: dict[str, Any] | None) -> str:
    """Flatten consensus JSON into text for benchmark comparison."""
    if not consensus:
        return ""

    parts: list[str] = []
    for key in ("consensus_summary", "direction", "dissent_direction"):
        val = consensus.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())

    channels = consensus.get("primary_transmission_channels")
    if isinstance(channels, list):
        parts.extend(str(c) for c in channels if c)

    magnitude = consensus.get("magnitude_pct")
    if isinstance(magnitude, dict):
        for ticker, pct in magnitude.items():
            try:
                parts.append(f"{ticker} {float(pct):+.1f}%")
            except (TypeError, ValueError):
                parts.append(f"{ticker} {pct}")

    return " ".join(parts)


def _passage_overlap_score(scenario_tokens: set[str], passage_text: str, themes: list[str]) -> float:
    passage_tokens = _tokenize(passage_text)
    if not passage_tokens or not scenario_tokens:
        return 0.0

    overlap = len(scenario_tokens & passage_tokens)
    base = overlap / max(1, min(len(scenario_tokens), len(passage_tokens)))
    theme_bonus = 0.0
    scenario_lower = " ".join(scenario_tokens)
    for theme in themes:
        theme_term = theme.replace("_", " ")
        if theme_term in scenario_lower or theme.replace("_", "") in scenario_lower:
            theme_bonus += 0.08
    return min(1.0, base * 1.6 + theme_bonus)


def score_fsr_alignment(
    consensus: dict[str, Any] | None,
    scenario_id: str,
    *,
    corpus: dict[str, Any] | None = None,
    top_k: int = 3,
) -> FsrBenchmarkResult:
    """Score how well the consensus scenario aligns with Fed FSR stress language."""
    data = corpus or load_fsr_corpus()
    passages, editions, source = resolve_fsr_passages(scenario_id, data)
    citation = str(data.get("citation", "https://www.federalreserve.gov/publications/financial-stability-report.htm"))
    scenario_text = build_consensus_text(consensus)
    scenario_tokens = _tokenize(scenario_text)

    if not scenario_text.strip():
        return FsrBenchmarkResult(
            alignment_score=0.0,
            scenario_id=scenario_id,
            fsr_editions=editions,
            matched_passages=(),
            scenario_text_preview="",
            source=source,
            citation=citation,
            detail="No consensus text available for FSR benchmark comparison.",
        )

    scored: list[FsrPassageMatch] = []
    for entry in passages:
        text = str(entry.get("text", ""))
        themes = tuple(str(t) for t in entry.get("themes", []))
        pid = str(entry.get("id", "unknown"))
        raw = _passage_overlap_score(scenario_tokens, text, list(themes))
        scored.append(
            FsrPassageMatch(
                passage_id=pid,
                score=raw,
                themes=themes,
                excerpt=text,
            )
        )

    scored.sort(key=lambda m: m.score, reverse=True)
    top = scored[:top_k]
    if not top:
        alignment = 0.0
        detail = "No FSR passages matched."
    else:
        weights = [0.5, 0.3, 0.2][: len(top)]
        weight_sum = sum(weights)
        alignment = sum(m.score * w for m, w in zip(top, weights)) / weight_sum
        alignment = min(100.0, alignment * 100.0)
        top_id = top[0].passage_id
        detail = (
            f"Top FSR match: {top_id} ({top[0].score:.0%} token/theme overlap). "
            f"Weighted alignment across {len(top)} passage(s): {alignment:.1f}/100."
        )

    return FsrBenchmarkResult(
        alignment_score=alignment,
        scenario_id=scenario_id,
        fsr_editions=editions,
        matched_passages=tuple(top),
        scenario_text_preview=scenario_text[:500],
        source=source,
        citation=citation,
        detail=detail,
    )


def format_fsr_benchmark_summary(result: FsrBenchmarkResult) -> str:
    """Human-readable FSR benchmark block for Quorum UI."""
    lines = [
        "**Federal Reserve FSR Benchmark (Layer 2 — prong 3)**",
        "",
        f"**FSR alignment score: {result.alignment_score:.1f} / 100**",
        f"Scenario bucket: **{result.scenario_id}**",
        f"FSR editions referenced: {', '.join(result.fsr_editions) or 'n/a'}",
        "",
        result.detail,
        "",
        "**Top matched FSR passages:**",
    ]
    if not result.matched_passages:
        lines.append("- (none)")
    else:
        for match in result.matched_passages:
            lines.append(
                f"- `{match.passage_id}` ({match.score:.0%}) — {match.excerpt[:180]}..."
            )
    lines.append(f"\n_Source: {result.source}_")
    lines.append(f"_Citation: {result.citation}_")
    return "\n".join(lines)
