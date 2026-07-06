#!/usr/bin/env python3
"""Short live SPAR test: Layer 0 + 2 agents R1/R2 + moderator (5 LLM calls)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from quorum.agents import get_role_assignments
from quorum.methods.base import PhaseMarker, SynthesisResult, TeamTextMessage, ThinkingIndicator
from quorum.methods.spar import ROUND2_LIVE_DEBATE_INSTRUCTION, SPAR_AGENT_SPECS, SparMethod, _build_round1_transcript, _format_agent_response, _parse_json_response, _role_label
from quorum.methods.spar_layer0 import run_layer0_pipeline
from quorum.providers import format_display_name

MODEL = "ollama:llama3.2:3b"
SHOCK = "Russia has launched a full-scale military invasion of Ukraine."
MINI_AGENTS = SPAR_AGENT_SPECS[:2]  # Political + Economic only


async def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    roles = get_role_assignments("spar", [MODEL])
    method = SparMethod(model_ids=[MODEL], role_assignments=roles)
    layer0 = run_layer0_pipeline(SHOCK)

    print("=== LAYER 0 ===")
    print(layer0.summary_text[:600], "...\n")

    round1_displays: dict[str, str] = {}
    round1_results: dict = {}
    debate: list[str] = [_build_round1_transcript({}), "\n=== ROUND 2 ===\n"]

    for role_key, agent_id, prompt_file, ipc_role in MINI_AGENTS:
        print(f"\n--- Round 1: {ipc_role} ---")
        system = method._system_for_agent(layer0, role_key, prompt_file)
        raw = await method._get_model_response(
            MODEL, system, f"{SHOCK}\n\nProduce Round 1 JSON only."
        )
        try:
            parsed = _parse_json_response(raw)
            round1_results[agent_id] = parsed
            display = _format_agent_response(raw, parsed)
        except Exception:
            display = raw[:400]
        round1_displays[agent_id] = display
        print(display[:500])

    debate[0] = _build_round1_transcript(round1_displays)
    for role_key, agent_id, prompt_file, ipc_role in MINI_AGENTS:
        print(f"\n--- Round 2 live: {ipc_role} ---")
        system = method._system_for_agent(layer0, role_key, prompt_file)
        user = ROUND2_LIVE_DEBATE_INSTRUCTION.format(
            role_label=_role_label(ipc_role),
            transcript="\n".join(debate),
        )
        raw = await method._get_model_response(MODEL, system, user)
        debate.append(f"--- {ipc_role} ---\n{raw}\n")
        print(raw[:400], "...")

    print("\n--- Moderator ---")
    from quorum.methods.spar import _load_prompt
    from quorum.methods.spar_layer0 import build_agent_system_prompt

    mod_system = build_agent_system_prompt(
        _load_prompt("master_context.txt"), layer0, "Moderator", _load_prompt("moderator.txt")
    )
    import json

    payload = {
        "layer0": layer0.to_dict(),
        "round1": round1_results,
        "live_debate_transcript": "\n".join(debate),
    }
    mod = await method._get_model_response(
        MODEL, mod_system, f"Full debate:\n{json.dumps(payload, indent=2)[:4000]}"
    )
    print(mod[:800])
    print("\n=== MINI LIVE TEST COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
