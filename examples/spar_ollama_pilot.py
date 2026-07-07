#!/usr/bin/env python3
"""
SPAR offline pilot — run domain agents via Ollama (no cloud API keys).

Uses the same Layer 0 pipeline and live Round 2 debate as Quorum's SPAR method.
Supports per-agent model mapping via config/spar_offline_models.json presets.

Usage:
    # Recommended first thesis test (3 models, Liberation Day):
    uv run python examples/spar_ollama_pilot.py --preset fast-thesis --scenario liberation-day

    # Full five-family variety:
    uv run python examples/spar_ollama_pilot.py --preset thesis --scenario liberation-day

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
    ROUND2_LIVE_DEBATE_INSTRUCTION,
    _format_agent_response,
    _parse_json_response,
    build_moderator_user_message,
)
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


def run_layer0(task: str, run_dir: Path) -> object:
    print(f"\n{'='*60}\n[Layer 0] Transmission-channel prioritization...\n{'='*60}")
    layer0 = run_layer0_pipeline(task)
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
        system = build_agent_system_prompt(master, layer0, role_key, agent_prompt)
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


def run_round2_live(
    models: OfflineModelMap,
    base_url: str,
    run_dir: Path,
    layer0: object,
    displays: dict[str, str],
    task: str,
    resume: bool = False,
) -> dict[str, dict]:
    results: dict[str, dict] = {}
    debate: list[str] = [_build_round1_transcript(displays), "\n=== ROUND 2 — Live cross-examination ===\n"]
    existing_path = run_dir / "round2_all.json"
    if resume and existing_path.exists():
        results = json.loads(existing_path.read_text(encoding="utf-8"))

    for role_key, agent_id, prompt_file, ipc_role in AGENTS:
        if resume and _round2_complete(run_dir, agent_id):
            label = ipc_role.replace("_", " ").title()
            prior = json.loads((run_dir / f"{agent_id}_round2.json").read_text(encoding="utf-8"))
            results[agent_id] = prior
            debate.append(f"--- {ipc_role} (speaking now) ---\n{prior.get('live_response', '')}\n")
            print(f"\n[{label}] Round 2 — skipped (already complete)")
            continue

        model = models.for_role(role_key)
        label = ipc_role.replace("_", " ").title()
        print(f"\n{'='*60}\n[{label}] Round 2 — {model}\n{'='*60}")
        master = resolve_master_context(task, PROMPTS)
        agent_prompt = load_prompt(prompt_file)
        system = build_agent_system_prompt(master, layer0, role_key, agent_prompt)
        transcript = _cap_transcript("\n".join(debate))
        user = ROUND2_LIVE_DEBATE_INSTRUCTION.format(role_label=label, transcript=transcript)
        raw = ollama_chat(model, system, user, base_url, models.debate_options)
        (run_dir / f"{agent_id}_round2_raw.txt").write_text(raw, encoding="utf-8")
        results[agent_id] = {"round": 2, "live_response": raw, "model": model}
        (run_dir / f"{agent_id}_round2.json").write_text(json.dumps(results[agent_id], indent=2), encoding="utf-8")
        debate.append(f"--- {ipc_role} (speaking now) ---\n{raw}\n")
        print(f"  OK — {len(raw)} chars")

    (run_dir / "live_debate_transcript.txt").write_text("\n".join(debate), encoding="utf-8")
    return results


def run_moderator(
    models: OfflineModelMap,
    base_url: str,
    run_dir: Path,
    layer0: object,
    task: str,
    round1_displays: dict[str, str],
    round2_results: dict,
) -> str:
    model = models.for_role("Moderator")
    print(f"\n{'='*60}\n[Moderator] Synthesizing — {model}\n{'='*60}")
    master = resolve_master_context(task, PROMPTS)
    mod = load_prompt("moderator.txt")
    system = build_agent_system_prompt(master, layer0, "Moderator", mod)
    user = build_moderator_user_message(task, layer0, round1_displays, round2_results)
    raw = ollama_chat(model, system, user, base_url, models.debate_options)
    (run_dir / "moderator_raw.txt").write_text(raw, encoding="utf-8")
    print("  Done — saved moderator_raw.txt")
    return raw


def load_layer0(task: str, run_dir: Path) -> object:
    """Run Layer 0 pipeline and persist summary (always scenario-aware)."""
    layer0 = run_layer0_pipeline(task)
    (run_dir / "layer0_summary.txt").write_text(layer0.summary_text, encoding="utf-8")
    (run_dir / "layer0.json").write_text(json.dumps(layer0.to_dict(), indent=2), encoding="utf-8")
    return layer0


def main() -> None:
    parser = argparse.ArgumentParser(description="SPAR Ollama offline pilot (Layer 0 + live debate)")
    parser.add_argument(
        "--preset",
        choices=["uniform", "fast-thesis", "thesis"],
        default="thesis",
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
    (run_dir / "model_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Output directory: {run_dir}")
    print(f"Preset: {models.preset} — {models.description}")
    print(f"Scenario: {args.scenario}")
    print("Model map:")
    for role_key, *_ in AGENTS:
        print(f"  {role_key:16} -> {models.for_role(role_key)}")
    print(f"  {'Moderator':16} -> {models.for_role('Moderator')}")

    layer0_path = run_dir / "layer0.json"

    if args.round == "layer0":
        run_layer0(task, run_dir)
        print(f"\nDone. Layer 0 saved in: {run_dir}")
        return

    layer0 = load_layer0(task, run_dir)

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
        r2 = run_round2_live(models, args.base_url, run_dir, layer0, displays, task, resume=args.resume)
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
        run_moderator(models, args.base_url, run_dir, layer0, task, displays, r2)

    print(f"\nDone. Results in: {run_dir}")
    if args.round == "1":
        print(f"\nNext:\n  uv run python examples/spar_ollama_pilot.py --round 2 --run-id {ts} --preset {args.preset}")
    if args.round == "2":
        print(
            f"\nNext:\n  uv run python examples/spar_ollama_pilot.py --round moderator --run-id {ts} --preset {args.preset}"
        )


if __name__ == "__main__":
    main()
