#!/usr/bin/env python3
"""Quick SPAR smoke test: Layer 0 + optional single-agent Ollama call."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from quorum.methods.spar import SparMethod
from quorum.methods.spar_layer0 import run_layer0_pipeline


def test_layer0(shock: str) -> None:
    print("\n=== LAYER 0 SMOKE TEST ===\n")
    layer0 = run_layer0_pipeline(shock)
    print(layer0.summary_text)
    print("\n--- Economic agent packet (first 800 chars) ---\n")
    print(layer0.agent_packets["Economic"][:800])
    active = [a for a in layer0.activations if a.priority.value != "inactive"]
    print(f"\nActive channels: {len(active)} / {len(layer0.activations)}")


async def test_one_agent(model: str, shock: str) -> None:
    print("\n=== SINGLE AGENT ROUND 1 (live Ollama) ===\n")
    layer0 = run_layer0_pipeline(shock)
    method = SparMethod(model_ids=[model])
    system = method._system_for_agent(layer0, "Economic", "agent2_economic_fiscal_market.txt")
    user = f"{shock}\n\nProduce your Round 1 JSON output now. JSON only."
    raw = await method._get_model_response(model, system, user)
    print(raw[:1500])
    if len(raw) > 1500:
        print("\n... [truncated]")


async def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="SPAR smoke test")
    parser.add_argument(
        "--shock",
        default="Russia has launched a full-scale military invasion of Ukraine.",
    )
    parser.add_argument("--model", default="", help="If set, run one live Round 1 agent call")
    args = parser.parse_args()

    test_layer0(args.shock)
    if args.model:
        await test_one_agent(args.model, args.shock)
    else:
        print("\nTip: add --model ollama:llama3.2:3b for one live agent call")


if __name__ == "__main__":
    asyncio.run(main())
