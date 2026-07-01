#!/usr/bin/env python3
"""
SPAR offline pilot — run domain agents via Ollama (no cloud API keys).

Usage:
    uv run python examples/spar_ollama_pilot.py --round 1
    uv run python examples/spar_ollama_pilot.py --round 2
    uv run python examples/spar_ollama_pilot.py --round all
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "Proejct Info" / "prompts"
OUTPUT = ROOT / "Proejct Info" / "spar_outputs"

AGENTS = [
    ("political_geopolitical", "agent1_political_geopolitical.txt", "Political & Geopolitical"),
    ("economic_fiscal_market", "agent2_economic_fiscal_market.txt", "Economic, Fiscal & Market"),
    ("environmental_technology", "agent3_environmental_technology.txt", "Environmental & Technology"),
    ("social_behavioural", "agent4_social_behavioural.txt", "Social & Behavioural"),
    ("devils_advocate", "agent5_devils_advocate.txt", "Devil's Advocate"),
]

ROUND2_INSTRUCTION = """Round 2 — Cross-Examination.

Here are the Round 1 outputs from all agents:
{round1_json}

You must:
1) Identify one point of genuine agreement with at least one other agent, citing their specific claim.
2) Identify one factual or logical disagreement with at least one other agent, citing evidence from the Master Context.
3) If your direction or magnitude estimate changes from Round 1, your supporting_evidence must include a new data point that justifies the change — not just exposure to another agent's opinion.

Return updated JSON with round: 2 and a response_to field added. JSON only, no markdown fences."""


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


def parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start : end + 1])


def run_round1(model: str, base_url: str, run_dir: Path) -> dict[str, dict]:
    master = load_prompt("master_context.txt")
    results: dict[str, dict] = {}

    for agent_id, prompt_file, label in AGENTS:
        print(f"\n{'='*60}\n[{label}] Round 1 — generating...\n{'='*60}")
        agent_prompt = load_prompt(prompt_file)
        system = f"{master}\n\n{agent_prompt}"
        user = "Produce your Round 1 JSON output now. JSON only."
        raw = ollama_chat(model, system, user, base_url)
        (run_dir / f"{agent_id}_round1_raw.txt").write_text(raw, encoding="utf-8")
        try:
            parsed = parse_json_response(raw)
            results[agent_id] = parsed
            (run_dir / f"{agent_id}_round1.json").write_text(
                json.dumps(parsed, indent=2), encoding="utf-8"
            )
            print(f"  OK — direction={parsed.get('direction')}, confidence={parsed.get('confidence')}")
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"  WARN — JSON parse failed: {exc}")
            results[agent_id] = {"parse_error": str(exc), "raw_preview": raw[:500]}
    return results


def run_round2(model: str, base_url: str, run_dir: Path, round1: dict[str, dict]) -> dict[str, dict]:
    master = load_prompt("master_context.txt")
    round1_blob = json.dumps(round1, indent=2)
    results: dict[str, dict] = {}

    for agent_id, prompt_file, label in AGENTS:
        print(f"\n{'='*60}\n[{label}] Round 2 — cross-examination...\n{'='*60}")
        agent_prompt = load_prompt(prompt_file)
        system = f"{master}\n\n{agent_prompt}"
        user = ROUND2_INSTRUCTION.format(round1_json=round1_blob)
        raw = ollama_chat(model, system, user, base_url)
        (run_dir / f"{agent_id}_round2_raw.txt").write_text(raw, encoding="utf-8")
        try:
            parsed = parse_json_response(raw)
            results[agent_id] = parsed
            (run_dir / f"{agent_id}_round2.json").write_text(
                json.dumps(parsed, indent=2), encoding="utf-8"
            )
            print(f"  OK — direction={parsed.get('direction')}")
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"  WARN — JSON parse failed: {exc}")
            results[agent_id] = {"parse_error": str(exc), "raw_preview": raw[:500]}
    return results


def run_moderator(model: str, base_url: str, run_dir: Path, transcript: dict) -> str:
    print(f"\n{'='*60}\n[Moderator] Synthesizing...\n{'='*60}")
    master = load_prompt("master_context.txt")
    mod = load_prompt("moderator.txt")
    system = f"{master}\n\n{mod}"
    user = f"Full debate transcript:\n{json.dumps(transcript, indent=2)}"
    raw = ollama_chat(model, system, user, base_url)
    (run_dir / "moderator_raw.txt").write_text(raw, encoding="utf-8")
    print("  Done — saved moderator_raw.txt")
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description="SPAR Ollama offline pilot")
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model name")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--round", choices=["1", "2", "moderator", "all"], default="1")
    parser.add_argument("--run-id", default=None, help="Reuse existing run folder for round 2")
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

    if args.round in ("1", "all"):
        r1 = run_round1(args.model, args.base_url, run_dir)
        (run_dir / "round1_all.json").write_text(json.dumps(r1, indent=2), encoding="utf-8")

    if args.round in ("2", "all"):
        r1_path = run_dir / "round1_all.json"
        if not r1_path.exists():
            raise SystemExit(f"Round 1 results not found in {run_dir}. Run --round 1 first.")
        r1 = json.loads(r1_path.read_text(encoding="utf-8"))
        r2 = run_round2(args.model, args.base_url, run_dir, r1)
        (run_dir / "round2_all.json").write_text(json.dumps(r2, indent=2), encoding="utf-8")

    if args.round in ("moderator", "all"):
        for name in ("round1_all.json", "round2_all.json"):
            if not (run_dir / name).exists():
                raise SystemExit(f"Missing {name} in {run_dir}. Run rounds 1 and 2 first.")
        transcript = {
            "round1": json.loads((run_dir / "round1_all.json").read_text(encoding="utf-8")),
            "round2": json.loads((run_dir / "round2_all.json").read_text(encoding="utf-8")),
        }
        run_moderator(args.model, args.base_url, run_dir, transcript)

    print(f"\nDone. Results in: {run_dir}")
    if args.round == "1":
        print(f"\nNext step:\n  uv run python examples/spar_ollama_pilot.py --round 2 --run-id {ts}")
    if args.round == "2":
        print(f"\nNext step:\n  uv run python examples/spar_ollama_pilot.py --round moderator --run-id {ts}")


if __name__ == "__main__":
    main()
