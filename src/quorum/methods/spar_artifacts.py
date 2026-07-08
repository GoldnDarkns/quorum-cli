"""Persist SPAR run artifacts (parity with examples/spar_ollama_pilot.py)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]

SPAR_ROLE_ORDER = [
    "Political",
    "Economic",
    "Environmental",
    "Social",
    "DevilsAdvocate",
    "Moderator",
]

SPAR_AGENT_IDS = [
    "political_geopolitical",
    "economic_fiscal_market",
    "environmental_technology",
    "social_behavioural",
    "devils_advocate",
]


def resolve_spar_output_root() -> Path:
    """Resolve directory for SPAR run folders.

    Priority:
    1. QUORUM_REPORT_DIR when set to something other than default ~/reports
    2. Repo ``Proejct Info/spar_outputs`` when prompts exist (dev / quorum.bat from repo)
    3. Settings report dir (default ~/reports)
    """
    settings = get_settings()
    default_reports = Path("~/reports").expanduser()
    configured = Path(settings.report_dir).expanduser()
    if configured != default_reports:
        return settings.get_report_dir()

    repo_outputs = _REPO_ROOT / "Proejct Info" / "spar_outputs"
    if (_REPO_ROOT / "Proejct Info" / "prompts" / "master_context.txt").exists():
        return repo_outputs

    return settings.get_report_dir()


def new_run_directory(output_root: Path | None = None, run_id: str | None = None) -> Path:
    """Create ``run_<timestamp>/`` under the SPAR output root."""
    root = output_root or resolve_spar_output_root()
    ts = run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = root / f"run_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


@dataclass
class SparRunSnapshot:
    """Complete SPAR run state for disk persistence."""

    task: str
    layer0: Layer0State
    round1_results: dict[str, Any]
    round1_raw: dict[str, str]
    round1_displays: dict[str, str]
    round2_results: dict[str, Any]
    round2_raw: dict[str, str]
    debate_transcript: str
    moderator_raw: str
    model_map: dict[str, str]
    source: str = "quorum-ui"
    run_id: str | None = None
    debate_rounds: dict[int, dict[str, Any]] = field(default_factory=dict)
    debate_raw_by_round: dict[int, dict[str, str]] = field(default_factory=dict)
    dcs_history: list[dict[str, Any]] = field(default_factory=list)
    plausibility_gate: dict[str, Any] | None = None
    layer3_quant: dict[str, Any] | None = None
    model_benchmark_report: dict[str, Any] | None = None


def build_model_map(
    model_ids: list[str],
    role_assignments: dict[str, list[str]] | None,
) -> dict[str, str]:
    """Map SPAR roles to model IDs for manifest.json."""
    role_names = SPAR_ROLE_ORDER
    mapping: dict[str, str] = {}
    for role in role_names:
        if role_assignments and role in role_assignments and role_assignments[role]:
            mapping[role] = role_assignments[role][0]
        elif role in role_names:
            idx = role_names.index(role)
            mapping[role] = model_ids[idx % len(model_ids)]
        else:
            mapping[role] = model_ids[0]
    return mapping


def persist_spar_run(
    snapshot: SparRunSnapshot,
    output_root: Path | None = None,
) -> Path:
    """Write all SPAR research artifacts to disk. Returns the run directory."""
    run_dir = new_run_directory(output_root, snapshot.run_id)

    manifest = {
        "source": snapshot.source,
        "task_preview": snapshot.task.strip()[:200],
        "scenario_id": snapshot.layer0.shock_parsed.get("scenario_id", "generic"),
        "agents": {
            role: snapshot.model_map.get(role, "")
            for role in SPAR_ROLE_ORDER
            if role != "Moderator"
        },
        "moderator": snapshot.model_map.get("Moderator", ""),
        "model_map": snapshot.model_map,
        "unique_models": sorted(set(snapshot.model_map.values())),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "model_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    (run_dir / "layer0.json").write_text(
        json.dumps(snapshot.layer0.to_dict(), indent=2), encoding="utf-8"
    )
    (run_dir / "layer0_summary.txt").write_text(snapshot.layer0.summary_text, encoding="utf-8")
    (run_dir / "task.txt").write_text(snapshot.task.strip(), encoding="utf-8")

    for agent_id in SPAR_AGENT_IDS:
        raw = snapshot.round1_raw.get(agent_id, "")
        if raw:
            (run_dir / f"{agent_id}_round1_raw.txt").write_text(raw, encoding="utf-8")
        parsed = snapshot.round1_results.get(agent_id)
        if parsed is not None:
            (run_dir / f"{agent_id}_round1.json").write_text(
                json.dumps(parsed, indent=2), encoding="utf-8"
            )

    (run_dir / "round1_all.json").write_text(
        json.dumps(snapshot.round1_results, indent=2), encoding="utf-8"
    )
    (run_dir / "round1_displays.json").write_text(
        json.dumps(snapshot.round1_displays, indent=2), encoding="utf-8"
    )

    for agent_id in SPAR_AGENT_IDS:
        raw = snapshot.round2_raw.get(agent_id, "")
        if raw:
            (run_dir / f"{agent_id}_round2_raw.txt").write_text(raw, encoding="utf-8")
        entry = snapshot.round2_results.get(agent_id)
        if entry is not None:
            (run_dir / f"{agent_id}_round2.json").write_text(
                json.dumps(entry, indent=2), encoding="utf-8"
            )

    (run_dir / "round2_all.json").write_text(
        json.dumps(snapshot.round2_results, indent=2), encoding="utf-8"
    )

    if snapshot.debate_rounds:
        serializable_rounds = {
            str(rnd): data for rnd, data in sorted(snapshot.debate_rounds.items())
        }
        (run_dir / "debate_rounds_all.json").write_text(
            json.dumps(serializable_rounds, indent=2), encoding="utf-8"
        )
        for rnd, round_data in snapshot.debate_rounds.items():
            if rnd == 2:
                continue
            for agent_id in SPAR_AGENT_IDS:
                raw_by_round = snapshot.debate_raw_by_round.get(rnd, {})
                raw = raw_by_round.get(agent_id, "")
                if raw:
                    (run_dir / f"{agent_id}_round{rnd}_raw.txt").write_text(
                        raw, encoding="utf-8"
                    )
                entry = round_data.get(agent_id)
                if entry is not None:
                    (run_dir / f"{agent_id}_round{rnd}.json").write_text(
                        json.dumps(entry, indent=2), encoding="utf-8"
                    )

    if snapshot.dcs_history:
        (run_dir / "dcs_scores.json").write_text(
            json.dumps(snapshot.dcs_history, indent=2), encoding="utf-8"
        )

    if snapshot.plausibility_gate:
        (run_dir / "plausibility_gate.json").write_text(
            json.dumps(snapshot.plausibility_gate, indent=2), encoding="utf-8"
        )
        fsr_payload = snapshot.plausibility_gate.get("fsr_benchmark")
        if fsr_payload:
            (run_dir / "fsr_benchmark.json").write_text(
                json.dumps(fsr_payload, indent=2), encoding="utf-8"
            )

    if snapshot.layer3_quant:
        (run_dir / "layer3_quant.json").write_text(
            json.dumps(snapshot.layer3_quant, indent=2), encoding="utf-8"
        )
        rec = snapshot.layer3_quant.get("portfolio_recommendation")
        if rec:
            (run_dir / "portfolio_recommendation.json").write_text(
                json.dumps(rec, indent=2), encoding="utf-8"
            )

    if snapshot.model_benchmark_report:
        (run_dir / "model_benchmark_report.json").write_text(
            json.dumps(snapshot.model_benchmark_report, indent=2), encoding="utf-8"
        )

    (run_dir / "live_debate_transcript.txt").write_text(
        snapshot.debate_transcript, encoding="utf-8"
    )
    (run_dir / "moderator_raw.txt").write_text(snapshot.moderator_raw, encoding="utf-8")

    logger.info("SPAR artifacts saved to %s", run_dir)
    return run_dir


def maybe_persist_spar_run(snapshot: SparRunSnapshot, output_root: Path | None = None) -> Path | None:
    """Persist when SPAR_SAVE_ARTIFACTS is enabled (default on)."""
    settings = get_settings()
    if not getattr(settings, "spar_save_artifacts", True):
        return None
    return persist_spar_run(snapshot, output_root=output_root)
