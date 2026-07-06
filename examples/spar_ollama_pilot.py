#!/usr/bin/env python3
"""
SPAR offline pilot — run domain agents via Ollama (no cloud API keys).

Uses the same Layer 0 pipeline and live Round 2 debate as Quorum's SPAR method.
For UI-identical streaming output, use examples/spar_live_demo.py instead.

Usage:
    uv run python examples/spar_ollama_pilot.py --round all
    uv run python examples/spar_ollama_pilot.py --round 1
    uv run python examples/spar_ollama_pilot.py --round 2 --run-id 20260701_211531
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from quorum.methods.spar import ROUND2_LIVE_DEBATE_INSTRUCTION, _format_agent_response, _parse_json_response
from quorum.methods.spar_layer0 import build_agent_system_prompt, run_layer0_pipeline

PROMPTS = ROOT / "Proejct Info" / "prompts"
OUTPUT = ROOT / "Proejct Info" / "spar_outputs"

DEFAULT_TASK = (
    "Russia has launched a full-scale military invasion of Ukraine across multiple fronts. "
    "Ground forces entered from Belarus, Donbas, and Crimea. Missile strikes hit Kyiv. "
    "Knowledge cutoff: February 23, 2022 market close."
)

AGENTS = [
    ("Political", "political_geopolitical", "agent1_political_geopolitical.txt", "POLITICAL"),
    ("Economic", "economic_fiscal_market", "agent2_economic_fiscal_market.txt", "ECONOMIC"),
    ("Environmental", "environmental_technology", "agent3_environmental_technology.txt", "ENVIRONMENTAL"),
    ("Social", "social_behavioural", "agent4_social_behavioural.txt", "SOCIAL"),
    ("DevilsAdvocate", "devils_advocate", "agent5_devils_advocate.txt", "DEVILS_ADVOCATE"),
]


def load_prompt(name: str) -> str:
    path = PROMPTS / name
    if not path.exists():
        raise FileNotFoundError(f"Missing prompt file: {path}. Run: python scripts/extract_spar_prompts.py")
    return path.read_text(encoding="utf-8")


def ollama_chat(model: str, system: str, user: str, base_url: str = "http://localhost:11434") -> str:
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
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


def run_round1(model: str, base_url: str, run_dir: Path, layer0: object, task: str) -> dict[str, dict]:
    results: dict[str, dict] = {}
    displays: dict[str, str] = {}

    for role_key, agent_id, prompt_file, ipc_role in AGENTS:
        label = ipc_role.replace("_", " ").title()
        print(f"\n{'='*60}\n[{label}] Round 1 — generating...\n{'='*60}")
        master = load_prompt("master_context.txt")
        agent_prompt = load_prompt(prompt_file)
        system = build_agent_system_prompt(master, layer0, role_key, agent_prompt)
        user = f"{task.strip()}\n\nProduce your Round 1 JSON output now. JSON only."
        raw = ollama_chat(model, system, user, base_url)
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


def run_round2_live(
    model: str, base_url: str, run_dir: Path, layer0: object, displays: dict[str, str]
) -> dict[str, dict]:
    results: dict[str, dict] = {}
    debate: list[str] = [_build_round1_transcript(displays), "\n=== ROUND 2 — Live cross-examination ===\n"]

    for role_key, agent_id, prompt_file, ipc_role in AGENTS:
        label = ipc_role.replace("_", " ").title()
        print(f"\n{'='*60}\n[{label}] Round 2 — live debate...\n{'='*60}")
        master = load_prompt("master_context.txt")
        agent_prompt = load_prompt(prompt_file)
        system = build_agent_system_prompt(master, layer0, role_key, agent_prompt)
        transcript = "\n".join(debate)
        user = ROUND2_LIVE_DEBATE_INSTRUCTION.format(role_label=label, transcript=transcript)
        raw = ollama_chat(model, system, user, base_url)
        (run_dir / f"{agent_id}_round2_raw.txt").write_text(raw, encoding="utf-8")
        results[agent_id] = {"round": 2, "live_response": raw}
        (run_dir / f"{agent_id}_round2.json").write_text(json.dumps(results[agent_id], indent=2), encoding="utf-8")
        debate.append(f"--- {ipc_role} (speaking now) ---\n{raw}\n")
        print(f"  OK — {len(raw)} chars")

    (run_dir / "live_debate_transcript.txt").write_text("\n".join(debate), encoding="utf-8")
    return results


def run_moderator(model: str, base_url: str, run_dir: Path, layer0: object, transcript: dict) -> str:
    print(f"\n{'='*60}\n[Moderator] Synthesizing...\n{'='*60}")
    master = load_prompt("master_context.txt")
    mod = load_prompt("moderator.txt")
    system = build_agent_system_prompt(master, layer0, "Moderator", mod)
    user = f"Full debate transcript:\n{json.dumps(transcript, indent=2)}"
    raw = ollama_chat(model, system, user, base_url)
    (run_dir / "moderator_raw.txt").write_text(raw, encoding="utf-8")
    print("  Done — saved moderator_raw.txt")
    return raw


def load_layer0(task: str, run_dir: Path) -> object:
    """Run Layer 0 pipeline; persist summary on first run."""
    layer0_path = run_dir / "layer0.json"
    if not layer0_path.exists():
        return run_layer0(task, run_dir)
    return run_layer0_pipeline(task)


def main() -> None:
    parser = argparse.ArgumentParser(description="SPAR Ollama offline pilot (Layer 0 + live debate)")
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model name")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--task", default=DEFAULT_TASK, help="Shock scenario text")
    parser.add_argument("--round", choices=["layer0", "1", "2", "moderator", "all"], default="all")
    parser.add_argument("--run-id", default=None, help="Reuse existing run folder")
    args = parser.parse_args()

    if not PROMPTS.exists() or not (PROMPTS / "master_context.txt").exists():
        print("Extracting prompts from spar-prompts.html...")
        import subprocess

        subprocess.run([sys.executable, str(ROOT / "scripts" / "extract_spar_prompts.py")], check=True)

    ts = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT / f"run_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {run_dir}")
    print(f"Model: {args.model}")

    layer0_path = run_dir / "layer0.json"

    if args.round == "layer0":
        run_layer0(args.task, run_dir)
        print(f"\nDone. Layer 0 saved in: {run_dir}")
        return

    layer0 = load_layer0(args.task, run_dir)

    if args.round in ("1", "all"):
        r1 = run_round1(args.model, args.base_url, run_dir, layer0, args.task)
        (run_dir / "round1_all.json").write_text(json.dumps(r1, indent=2), encoding="utf-8")

    if args.round in ("2", "all"):
        r1_path = run_dir / "round1_all.json"
        disp_path = run_dir / "round1_displays.json"
        if not r1_path.exists() or not disp_path.exists():
            raise SystemExit(f"Round 1 results not found in {run_dir}. Run --round 1 first.")
        displays = json.loads(disp_path.read_text(encoding="utf-8"))
        r2 = run_round2_live(args.model, args.base_url, run_dir, layer0, displays)
        (run_dir / "round2_all.json").write_text(json.dumps(r2, indent=2), encoding="utf-8")

    if args.round in ("moderator", "all"):
        for name in ("round1_all.json", "round2_all.json"):
            if not (run_dir / name).exists():
                raise SystemExit(f"Missing {name} in {run_dir}. Run prior rounds first.")
        transcript = {
            "layer0": json.loads(layer0_path.read_text(encoding="utf-8")) if layer0_path.exists() else layer0.to_dict(),
            "round1": json.loads((run_dir / "round1_all.json").read_text(encoding="utf-8")),
            "round2": json.loads((run_dir / "round2_all.json").read_text(encoding="utf-8")),
        }
        live_path = run_dir / "live_debate_transcript.txt"
        if live_path.exists():
            transcript["live_debate_transcript"] = live_path.read_text(encoding="utf-8")
        run_moderator(args.model, args.base_url, run_dir, layer0, transcript)

    print(f"\nDone. Results in: {run_dir}")
    if args.round == "1":
        print(f"\nNext:\n  uv run python examples/spar_ollama_pilot.py --round 2 --run-id {ts}")
    if args.round == "2":
        print(f"\nNext:\n  uv run python examples/spar_ollama_pilot.py --round moderator --run-id {ts}")


if __name__ == "__main__":
    main()
