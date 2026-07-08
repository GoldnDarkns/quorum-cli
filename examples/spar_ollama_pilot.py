#!/usr/bin/env python3
"""
SPAR offline pilot — run domain agents via Ollama (no cloud API keys).

Uses the same Layer 0 pipeline and live Round 2 debate as Quorum's SPAR method.
Supports per-agent model mapping via config/spar_offline_models.json presets.

Usage:
    # Recommended Liberation Day demo (6 model families):
    uv run python examples/spar_ollama_pilot.py --preset demo-diverse --scenario liberation-day

    # Quick thesis test (3 models):
    uv run python examples/spar_ollama_pilot.py --preset fast-thesis --scenario liberation-day

    # Single-model baseline (replicate Ukraine pilot):
    uv run python examples/spar_ollama_pilot.py --preset uniform --round 1
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from quorum.methods.spar import (
    LIVE_DEBATE_ROUND_INSTRUCTION,
    ROUND2_LIVE_DEBATE_INSTRUCTION,
    _format_agent_response,
    _parse_json_response,
    build_moderator_user_message,
)
from quorum.methods.spar_plausibility_gate import (
    evaluate_plausibility_gate,
    format_plausibility_gate_summary,
)
from quorum.methods.spar_model_benchmarks import build_analysis_report, format_benchmark_report
from quorum.methods.spar_layer3 import (
    format_layer3_summary,
    format_portfolio_recommendation,
    run_layer3_quantification,
    save_layer3_artifacts,
)
from quorum.config import get_settings
from quorum.methods.spar_layer0 import (
    build_agent_system_prompt,
    resolve_master_context,
    run_layer0_pipeline,
)

PROMPTS = ROOT / "Proejct Info" / "prompts"
OUTPUT = ROOT / "Proejct Info" / "spar_outputs"
MODEL_CONFIG = ROOT / "config" / "spar_offline_models.json"

UKRAINE_TASK = (
    "Russia has launched a full-scale military invasion of Ukraine across multiple fronts. "
    "Ground forces entered from Belarus, Donbas, and Crimea. Missile strikes hit Kyiv. "
    "Knowledge cutoff: February 23, 2022 market close."
)

LIBERATION_DAY_TASK = (
    "On April 2, 2025, the United States announced broad reciprocal tariffs under the "
    "'Liberation Day' trade policy package, with sector-specific rates on imports from "
    "major trading partners and immediate implementation timelines. Equity futures fell "
    "sharply overnight; the VIX rose; USD strengthened; bond yields moved lower on "
    "growth concerns. Knowledge cutoff: April 2, 2025, 09:00 ET (before cash equity open)."
)

SCENARIOS = {
    "ukraine": UKRAINE_TASK,
    "liberation-day": LIBERATION_DAY_TASK,
}

AGENTS = [
    ("Political", "political_geopolitical", "agent1_political_geopolitical.txt", "POLITICAL"),
    ("Economic", "economic_fiscal_market", "agent2_economic_fiscal_market.txt", "ECONOMIC"),
    ("Environmental", "environmental_technology", "agent3_environmental_technology.txt", "ENVIRONMENTAL"),
    ("Social", "social_behavioural", "agent4_social_behavioural.txt", "SOCIAL"),
    ("DevilsAdvocate", "devils_advocate", "agent5_devils_advocate.txt", "DEVILS_ADVOCATE"),
]


@dataclass(frozen=True)
class OfflineModelMap:
    """Per-role Ollama model names plus shared chat options."""

    default: str
    roles: dict[str, str]
    ollama_options: dict[str, Any]
    ollama_options_long: dict[str, Any]
    preset: str
    description: str
    compact_layer0: bool = True

    def for_role(self, role_key: str) -> str:
        return self.roles.get(role_key, self.default)

    def unique_models(self) -> list[str]:
        names = {self.default, *self.roles.values()}
        return sorted(names)

    @property
    def debate_options(self) -> dict[str, Any]:
        return self.ollama_options_long or self.ollama_options

    def to_manifest(self) -> dict[str, Any]:
        agent_models = {role_key: self.for_role(role_key) for role_key, *_ in AGENTS}
        return {
            "preset": self.preset,
            "description": self.description,
            "default": self.default,
            "agents": agent_models,
            "moderator": self.for_role("Moderator"),
            "unique_models": self.unique_models(),
            "ollama_options": self.ollama_options,
            "ollama_options_long": self.ollama_options_long,
        }


def load_model_map(
    preset: str,
    config_path: Path = MODEL_CONFIG,
    override_model: str | None = None,
) -> OfflineModelMap:
    if override_model:
        return OfflineModelMap(
            default=override_model,
            roles={},
            ollama_options={"temperature": 0, "num_ctx": 8192},
            ollama_options_long={"temperature": 0, "num_ctx": 12288},
            preset="uniform",
            description=f"Single model override: {override_model}",
            compact_layer0=True,
        )

    if not config_path.exists():
        raise FileNotFoundError(f"Missing model config: {config_path}")

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    presets = raw.get("presets", {})
    if preset not in presets:
        known = ", ".join(sorted(presets))
        raise ValueError(f"Unknown preset '{preset}'. Choose from: {known}")

    entry = presets[preset]
    return OfflineModelMap(
        default=entry.get("default", "qwen2.5:7b"),
        roles=entry.get("roles", {}),
        ollama_options=raw.get("ollama_options", {"temperature": 0, "num_ctx": 8192}),
        ollama_options_long=raw.get("ollama_options_long", {"temperature": 0, "num_ctx": 12288}),
        preset=preset,
        description=entry.get("description", ""),
        compact_layer0=bool(raw.get("offline_compact_layer0", True)),
    )


def load_prompt(name: str) -> str:
    path = PROMPTS / name
    if not path.exists():
        raise FileNotFoundError(f"Missing prompt file: {path}. Run: python scripts/extract_spar_prompts.py")
    return path.read_text(encoding="utf-8")


def rebuild_round1_displays(run_dir: Path) -> dict[str, str]:
    """Rebuild readable Round 1 transcript from saved JSON/raw files."""
    displays: dict[str, str] = {}
    all_path = run_dir / "round1_all.json"
    if not all_path.exists():
        return displays
    round1_all = json.loads(all_path.read_text(encoding="utf-8"))
    for _role_key, agent_id, _prompt_file, _ipc_role in AGENTS:
        parsed = round1_all.get(agent_id)
        if not isinstance(parsed, dict) or "parse_error" in parsed:
            continue
        raw_path = run_dir / f"{agent_id}_round1_raw.txt"
        raw = raw_path.read_text(encoding="utf-8") if raw_path.exists() else json.dumps(parsed)
        displays[agent_id] = _format_agent_response(raw, parsed)
    return displays


def _cap_transcript(text: str, limit: int = 10000) -> str:
    if len(text) <= limit:
        return text
    return f"...[transcript truncated — showing last {limit} chars]...\n{text[-limit:]}"


def ollama_chat(
    model: str,
    system: str,
    user: str,
    base_url: str = "http://localhost:11434",
    options: dict[str, Any] | None = None,
    timeout: int = 1200,
) -> str:
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": options or {"temperature": 0, "num_ctx": 8192},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Ollama request failed: {exc}\n"
            "Is Ollama running? Try: ollama serve  OR open the Ollama app."
        ) from exc
    return data.get("message", {}).get("content", "")


def run_layer0(task: str, run_dir: Path, compact: bool = True) -> object:
    print(f"\n{'='*60}\n[Layer 0] Transmission-channel prioritization...\n{'='*60}")
    layer0 = run_layer0_pipeline(task, compact=compact)
    (run_dir / "layer0_summary.txt").write_text(layer0.summary_text, encoding="utf-8")
    (run_dir / "layer0.json").write_text(json.dumps(layer0.to_dict(), indent=2), encoding="utf-8")
    print(layer0.summary_text[:800])
    if len(layer0.summary_text) > 800:
        print("... [truncated]")
    return layer0


def _round1_complete(run_dir: Path, agent_id: str) -> bool:
    path = run_dir / f"{agent_id}_round1.json"
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return "parse_error" not in data


def run_round1(
    models: OfflineModelMap,
    base_url: str,
    run_dir: Path,
    layer0: object,
    task: str,
    resume: bool = False,
) -> dict[str, dict]:
    results: dict[str, dict] = {}
    displays: dict[str, str] = {}
    existing_path = run_dir / "round1_displays.json"
    if resume and existing_path.exists():
        displays = json.loads(existing_path.read_text(encoding="utf-8"))
    existing_all = run_dir / "round1_all.json"
    if resume and existing_all.exists():
        results = json.loads(existing_all.read_text(encoding="utf-8"))

    for role_key, agent_id, prompt_file, ipc_role in AGENTS:
        if resume and _round1_complete(run_dir, agent_id):
            label = ipc_role.replace("_", " ").title()
            print(f"\n[{label}] Round 1 — skipped (already complete)")
            continue
        model = models.for_role(role_key)
        label = ipc_role.replace("_", " ").title()
        print(f"\n{'='*60}\n[{label}] Round 1 — {model}\n{'='*60}")
        master = resolve_master_context(task, PROMPTS)
        agent_prompt = load_prompt(prompt_file)
        system = build_agent_system_prompt(
            master, layer0, role_key, agent_prompt, compact=models.compact_layer0
        )
        user = f"{task.strip()}\n\nProduce your Round 1 JSON output now. JSON only."
        raw = ollama_chat(model, system, user, base_url, models.ollama_options)
        (run_dir / f"{agent_id}_round1_raw.txt").write_text(raw, encoding="utf-8")
        try:
            parsed = _parse_json_response(raw)
            results[agent_id] = parsed
            displays[agent_id] = _format_agent_response(raw, parsed)
            (run_dir / f"{agent_id}_round1.json").write_text(json.dumps(parsed, indent=2), encoding="utf-8")
            print(f"  OK — direction={parsed.get('direction')}, confidence={parsed.get('confidence')}")
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"  WARN — JSON parse failed: {exc}")
            results[agent_id] = {"parse_error": str(exc), "raw_preview": raw[:500]}
            displays[agent_id] = raw[:500]
    (run_dir / "round1_displays.json").write_text(json.dumps(displays, indent=2), encoding="utf-8")
    return results


def _build_round1_transcript(displays: dict[str, str]) -> str:
    sections = ["=== ROUND 1 — Independent analyses ===\n"]
    for _role_key, agent_id, _prompt_file, ipc_role in AGENTS:
        sections.append(f"--- {ipc_role} ---\n{displays.get(agent_id, '(no output)')}\n")
    return "\n".join(sections)


def _round2_complete(run_dir: Path, agent_id: str) -> bool:
    return (run_dir / f"{agent_id}_round2.json").exists()


def run_debate_with_dcs(
    models: OfflineModelMap,
    base_url: str,
    run_dir: Path,
    layer0: object,
    displays: dict[str, str],
    round1_results: dict[str, dict],
    task: str,
    resume: bool = False,
) -> tuple[dict[str, dict], dict[int, dict[str, dict]], list[dict]]:
    """Run live debate rounds 2..N with DCS explore/exploit between rounds."""
    settings = get_settings()
    dcs_enabled = settings.spar_dcs_enabled
    threshold = settings.spar_dcs_threshold
    max_rounds = settings.spar_max_debate_rounds

    debate_rounds: dict[int, dict[str, dict]] = {}
    debate_raw_by_round: dict[int, dict[str, str]] = {}
    dcs_history: list[dict] = []
    debate: list[str] = [_build_round1_transcript(displays)]
    prior_speeches: dict[str, str] | None = None
    final_results: dict[str, dict] = {}

    for debate_round in range(2, max_rounds + 1):
        debate.append(f"\n=== ROUND {debate_round} — Live cross-examination ===\n")
        round_results: dict[str, dict] = {}
        round_raw: dict[str, str] = {}
        round_speeches: dict[str, str] = {}

        for role_key, agent_id, prompt_file, ipc_role in AGENTS:
            if resume and debate_round == 2 and _round2_complete(run_dir, agent_id):
                label = ipc_role.replace("_", " ").title()
                prior = json.loads((run_dir / f"{agent_id}_round2.json").read_text(encoding="utf-8"))
                round_results[agent_id] = prior
                round_speeches[agent_id] = prior.get("live_response", "")
                debate.append(f"--- {ipc_role} (speaking now) ---\n{prior.get('live_response', '')}\n")
                print(f"\n[{label}] Round {debate_round} — skipped (already complete)")
                continue

            model = models.for_role(role_key)
            label = ipc_role.replace("_", " ").title()
            print(f"\n{'='*60}\n[{label}] Round {debate_round} — {model}\n{'='*60}")
            master = resolve_master_context(task, PROMPTS)
            agent_prompt = load_prompt(prompt_file)
            system = build_agent_system_prompt(
                master, layer0, role_key, agent_prompt, compact=models.compact_layer0
            )
            transcript = _cap_transcript("\n".join(debate))
            user = LIVE_DEBATE_ROUND_INSTRUCTION.format(
                round_num=debate_round,
                role_label=label,
                transcript=transcript,
            )
            raw = ollama_chat(model, system, user, base_url, models.debate_options)
            round_raw[agent_id] = raw
            round_results[agent_id] = {"round": debate_round, "live_response": raw, "model": model}
            round_speeches[agent_id] = raw
            if debate_round == 2:
                (run_dir / f"{agent_id}_round2_raw.txt").write_text(raw, encoding="utf-8")
                (run_dir / f"{agent_id}_round2.json").write_text(
                    json.dumps(round_results[agent_id], indent=2), encoding="utf-8"
                )
            else:
                (run_dir / f"{agent_id}_round{debate_round}_raw.txt").write_text(raw, encoding="utf-8")
                (run_dir / f"{agent_id}_round{debate_round}.json").write_text(
                    json.dumps(round_results[agent_id], indent=2), encoding="utf-8"
                )
            debate.append(f"--- {ipc_role} (speaking now) ---\n{raw}\n")
            print(f"  OK — {len(raw)} chars")

        debate_rounds[debate_round] = round_results
        debate_raw_by_round[debate_round] = round_raw
        final_results = round_results
        (run_dir / "live_debate_transcript.txt").write_text("\n".join(debate), encoding="utf-8")

        if not dcs_enabled:
            break

        decision = compute_dcs(
            round_number=debate_round,
            round1_results=round1_results,
            prior_live_speeches=prior_speeches,
            current_live_speeches=round_speeches,
            debate_transcript="\n".join(debate),
            threshold=threshold,
            max_rounds=max_rounds,
            round1_displays=displays if debate_round == 2 else None,
        )
        dcs_history.append(decision.to_dict())
        (run_dir / "dcs_scores.json").write_text(json.dumps(dcs_history, indent=2), encoding="utf-8")
        print(f"\n{format_dcs_summary(decision)}")

        if decision.action == "exploit":
            break
        prior_speeches = round_speeches

    serializable = {str(rnd): data for rnd, data in sorted(debate_rounds.items())}
    (run_dir / "debate_rounds_all.json").write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    return final_results, debate_rounds, dcs_history


def run_round2_live(
    models: OfflineModelMap,
    base_url: str,
    run_dir: Path,
    layer0: object,
    displays: dict[str, str],
    task: str,
    resume: bool = False,
    round1_results: dict[str, dict] | None = None,
) -> dict[str, dict]:
    """Backward-compatible wrapper — runs DCS-aware debate and returns final round."""
    r1 = round1_results
    if r1 is None:
        r1_path = run_dir / "round1_all.json"
        r1 = json.loads(r1_path.read_text(encoding="utf-8")) if r1_path.exists() else {}
    final, _rounds, _dcs = run_debate_with_dcs(
        models, base_url, run_dir, layer0, displays, r1, task, resume=resume
    )
    (run_dir / "round2_all.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
    return final


def run_plausibility_gate(run_dir: Path, moderator_raw: str, scenario_id: str = "generic") -> dict:
    """Evaluate Layer 2 plausibility gate and optionally pause for human review."""
    settings = get_settings()
    decision, fsr_result = evaluate_plausibility_gate(
        moderator_raw,
        threshold=settings.spar_plausibility_threshold,
        enabled=settings.spar_plausibility_gate_enabled,
        scenario_id=scenario_id,
        fsr_enabled=settings.spar_fsr_benchmark_enabled,
        moderator_weight=settings.spar_fsr_moderator_weight,
        fsr_weight=settings.spar_fsr_weight,
    )
    payload = decision.to_dict()
    (run_dir / "plausibility_gate.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n{format_plausibility_gate_summary(decision, fsr_result)}")

    if (
        settings.spar_plausibility_gate_enabled
        and not decision.passed
        and settings.spar_human_review_block
    ):
        try:
            input("\n[HUMAN REVIEW] Press Enter to acknowledge low plausibility and end run...")
        except EOFError:
            print("\n[HUMAN REVIEW] Non-interactive mode — flagged in plausibility_gate.json")
    return payload


def run_moderator(
    models: OfflineModelMap,
    base_url: str,
    run_dir: Path,
    layer0: object,
    task: str,
    round1_displays: dict[str, str],
    round2_results: dict,
    debate_rounds: dict[int, dict] | None = None,
) -> str:
    model = models.for_role("Moderator")
    print(f"\n{'='*60}\n[Moderator] Synthesizing — {model}\n{'='*60}")
    master = resolve_master_context(task, PROMPTS)
    mod = load_prompt("moderator.txt")
    system = build_agent_system_prompt(
        master, layer0, "Moderator", mod, compact=models.compact_layer0
    )
    user = build_moderator_user_message(
        task,
        layer0,
        round1_displays,
        round2_results=round2_results,
        debate_rounds=debate_rounds,
    )
    raw = ollama_chat(model, system, user, base_url, models.debate_options)
    (run_dir / "moderator_raw.txt").write_text(raw, encoding="utf-8")
    print("  Done — saved moderator_raw.txt")
    return raw


def load_layer0(task: str, run_dir: Path, compact: bool = True) -> object:
    """Run Layer 0 pipeline and persist summary (always scenario-aware)."""
    layer0 = run_layer0_pipeline(task, compact=compact)
    (run_dir / "layer0_summary.txt").write_text(layer0.summary_text, encoding="utf-8")
    (run_dir / "layer0.json").write_text(json.dumps(layer0.to_dict(), indent=2), encoding="utf-8")
    return layer0


def main() -> None:
    parser = argparse.ArgumentParser(description="SPAR Ollama offline pilot (Layer 0 + live debate)")
    parser.add_argument(
        "--preset",
        choices=["uniform", "fast-thesis", "thesis", "demo-diverse"],
        default="demo-diverse",
        help="Model mapping preset from config/spar_offline_models.json",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override: use one Ollama model for every role (ignores --preset)",
    )
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        default="liberation-day",
        help="Pre-registered shock scenario",
    )
    parser.add_argument("--task", default=None, help="Custom scenario text (overrides --scenario)")
    parser.add_argument("--round", choices=["layer0", "1", "2", "moderator", "all"], default="all")
    parser.add_argument("--run-id", default=None, help="Reuse existing run folder")
    parser.add_argument("--resume", action="store_true", help="Skip agents that already completed the current round")
    args = parser.parse_args()

    if not PROMPTS.exists() or not (PROMPTS / "master_context.txt").exists():
        print("Extracting prompts from spar-prompts.html...")
        import subprocess

        subprocess.run([sys.executable, str(ROOT / "scripts" / "extract_spar_prompts.py")], check=True)

    task = args.task or SCENARIOS[args.scenario]
    models = load_model_map(args.preset, override_model=args.model)

    ts = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT / f"run_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = models.to_manifest()
    manifest["scenario"] = args.scenario
    manifest["task_preview"] = task[:200]
    bench_report = build_analysis_report(args.preset)
    manifest["model_benchmark_report"] = bench_report
    (run_dir / "model_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "model_benchmark_report.json").write_text(
        json.dumps(bench_report, indent=2), encoding="utf-8"
    )
    print(format_benchmark_report(args.preset))

    print(f"Output directory: {run_dir}")
    print(f"Preset: {models.preset} — {models.description}")
    print(f"Scenario: {args.scenario}")
    print("Model map:")
    for role_key, *_ in AGENTS:
        print(f"  {role_key:16} -> {models.for_role(role_key)}")
    print(f"  {'Moderator':16} -> {models.for_role('Moderator')}")

    layer0_path = run_dir / "layer0.json"

    if args.round == "layer0":
        run_layer0(task, run_dir, compact=models.compact_layer0)
        print(f"\nDone. Layer 0 saved in: {run_dir}")
        return

    layer0 = load_layer0(task, run_dir, compact=models.compact_layer0)

    if args.round in ("1", "all"):
        r1 = run_round1(models, args.base_url, run_dir, layer0, task, resume=args.resume)
        (run_dir / "round1_all.json").write_text(json.dumps(r1, indent=2), encoding="utf-8")

    if args.round in ("2", "all"):
        r1_path = run_dir / "round1_all.json"
        disp_path = run_dir / "round1_displays.json"
        if not r1_path.exists() or not disp_path.exists():
            raise SystemExit(f"Round 1 results not found in {run_dir}. Run --round 1 first.")
        displays = rebuild_round1_displays(run_dir)
        (run_dir / "round1_displays.json").write_text(json.dumps(displays, indent=2), encoding="utf-8")
        r1 = json.loads((run_dir / "round1_all.json").read_text(encoding="utf-8"))
        r2, debate_rounds, _dcs = run_debate_with_dcs(
            models, args.base_url, run_dir, layer0, displays, r1, task, resume=args.resume
        )
        (run_dir / "round2_all.json").write_text(json.dumps(r2, indent=2), encoding="utf-8")

    if args.round in ("moderator", "all"):
        for name in ("round1_all.json", "round2_all.json"):
            if not (run_dir / name).exists():
                raise SystemExit(f"Missing {name} in {run_dir}. Run prior rounds first.")
        disp_path = run_dir / "round1_displays.json"
        displays = json.loads(disp_path.read_text(encoding="utf-8")) if disp_path.exists() else {}
        round1_all = json.loads((run_dir / "round1_all.json").read_text(encoding="utf-8"))
        for _role_key, agent_id, _prompt_file, _ipc_role in AGENTS:
            entry = displays.get(agent_id, "")
            if entry and entry != "(no output)":
                continue
            parsed = round1_all.get(agent_id)
            if not isinstance(parsed, dict) or "parse_error" in parsed:
                continue
            raw_path = run_dir / f"{agent_id}_round1_raw.txt"
            raw = raw_path.read_text(encoding="utf-8") if raw_path.exists() else json.dumps(parsed)
            displays[agent_id] = _format_agent_response(raw, parsed)
        r2 = json.loads((run_dir / "round2_all.json").read_text(encoding="utf-8"))
        debate_rounds_path = run_dir / "debate_rounds_all.json"
        debate_rounds = None
        if debate_rounds_path.exists():
            raw_rounds = json.loads(debate_rounds_path.read_text(encoding="utf-8"))
            debate_rounds = {int(k): v for k, v in raw_rounds.items()}
        run_moderator(
            models, args.base_url, run_dir, layer0, task, displays, r2, debate_rounds=debate_rounds
        )
        moderator_raw = (run_dir / "moderator_raw.txt").read_text(encoding="utf-8")
        scenario_id = layer0.shock_parsed.get("scenario_id", "generic")
        gate_payload = run_plausibility_gate(run_dir, moderator_raw, scenario_id=scenario_id)
        settings = get_settings()
        if settings.spar_layer3_enabled and (
            not settings.spar_plausibility_gate_enabled or gate_payload.get("passed")
        ):
            round1_path = run_dir / "round1_all.json"
            round1_results = (
                json.loads(round1_path.read_text(encoding="utf-8"))
                if round1_path.exists()
                else {}
            )
            l3 = run_layer3_quantification(
                moderator_raw,
                round1_results=round1_results,
                moderator_plausibility=gate_payload.get("consensus_score"),
            )
            (run_dir / "layer3_quant.json").write_text(json.dumps(l3.to_dict(), indent=2), encoding="utf-8")
            (run_dir / "portfolio_recommendation.json").write_text(
                json.dumps(l3.portfolio_recommendation.to_dict(), indent=2), encoding="utf-8"
            )
            save_layer3_artifacts(run_dir, l3)
            print(f"\n{format_layer3_summary(l3)}")
            print(f"\n{format_portfolio_recommendation(l3.portfolio_recommendation)}")

    print(f"\nDone. Results in: {run_dir}")
    if args.round == "1":
        print(f"\nNext:\n  uv run python examples/spar_ollama_pilot.py --round 2 --run-id {ts} --preset {args.preset}")
    if args.round == "2":
        print(
            f"\nNext:\n  uv run python examples/spar_ollama_pilot.py --round moderator --run-id {ts} --preset {args.preset}"
        )


if __name__ == "__main__":
    main()
