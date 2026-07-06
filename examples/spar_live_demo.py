#!/usr/bin/env python3
"""Run SPAR with live terminal output (same backend as Quorum UI)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from quorum.agents import get_role_assignments
from quorum.methods.base import PhaseMarker, SynthesisResult, TeamTextMessage, ThinkingIndicator
from quorum.methods.spar import SparMethod
from quorum.providers import format_display_name

MODEL = "ollama:qwen2.5:7b"
TASK = (
    "Russia has launched a full-scale military invasion of Ukraine across multiple fronts. "
    "Ground forces entered from Belarus, Donbas, and Crimea. Missile strikes hit Kyiv. "
    "Knowledge cutoff: February 23, 2022 market close."
)


def banner(text: str, char: str = "=") -> None:
    width = 72
    print(f"\n{char * width}\n{text}\n{char * width}", flush=True)


async def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    roles = get_role_assignments("spar", [MODEL])
    banner(f"SPAR LIVE — {format_display_name(MODEL)}")
    print(f"Roles: {', '.join(roles.keys()) if roles else 'default'}", flush=True)

    method = SparMethod(model_ids=[MODEL], role_assignments=roles)

    async for msg in method.run_stream(TASK):
        if isinstance(msg, PhaseMarker):
            banner(f"PHASE {msg.phase}/{msg.total_phases}: {msg.message_key}", "-")
        elif isinstance(msg, ThinkingIndicator):
            print(f"\n  ... {format_display_name(msg.model)} thinking ...", flush=True)
        elif isinstance(msg, TeamTextMessage):
            role = f"[{msg.role}] " if msg.role else ""
            rnd = f" ({msg.round_type})" if msg.round_type else ""
            print(f"\n>>> {role}{format_display_name(msg.source)}{rnd}\n", flush=True)
            # Print first ~1200 chars so terminal stays readable
            body = msg.content
            if len(body) > 1200:
                print(body[:1200] + "\n... [truncated for display]", flush=True)
            else:
                print(body, flush=True)
        elif isinstance(msg, SynthesisResult):
            banner("MODERATOR SYNTHESIS")
            print(msg.synthesis[:2000], flush=True)
            if len(msg.synthesis) > 2000:
                print("\n... [truncated]", flush=True)

    banner("SPAR COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())
