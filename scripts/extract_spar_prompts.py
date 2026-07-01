"""Extract SPAR agent prompts from spar-prompts.html into text files."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "Proejct Info" / "spar-prompts.html"
OUT = ROOT / "Proejct Info" / "prompts"

MAPPING = {
    "master-ctx": "master_context.txt",
    "claude-pol-txt": "agent1_political_geopolitical.txt",
    "gpt-txt": "agent2_economic_fiscal_market.txt",
    "gem-txt": "agent3_environmental_technology.txt",
    "deep-txt": "agent4_social_behavioural.txt",
    "da-txt": "agent5_devils_advocate.txt",
}

MODERATOR = """You are the SPAR Moderator. You did NOT participate in the debate.

Read the full debate transcript (all rounds, all agents).

Produce TWO JSON objects in sequence, separated by a blank line:

1) CONSENSUS SCENARIO — majority positions with directional and sector magnitude estimates
2) MINORITY DISSENT — positions that were overruled but represent tail risk

Also include:
- plausibility_score: 0-100 based on historical analogue match, internal consistency, and economic logic
- primary_transmission_channels: list of agreed channels
- preserved_dissent_summary: one paragraph on what the minority warned about

Score plausibility honestly. If the debate was weak or contradictory, say so.

Output valid JSON only for each object. No markdown fences."""


def main() -> None:
    html = HTML.read_text(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)

    for elem_id, fname in MAPPING.items():
        pattern = rf'id="{re.escape(elem_id)}"[^>]*>(.*?)</div>\s*</div>\s*</div>'
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            pattern = rf'id="{re.escape(elem_id)}"[^>]*>(.*?)</div>'
            match = re.search(pattern, html, re.DOTALL)
        if not match:
            raise SystemExit(f"Could not find prompt element: {elem_id}")
        text = match.group(1).strip()
        (OUT / fname).write_text(text, encoding="utf-8")
        print(f"Wrote {fname} ({len(text)} chars)")

    (OUT / "moderator.txt").write_text(MODERATOR.strip(), encoding="utf-8")
    print("Wrote moderator.txt")


if __name__ == "__main__":
    main()
