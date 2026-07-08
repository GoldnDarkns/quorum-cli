#!/usr/bin/env python3
"""Copy SPAR translation keys from en.ts into other language files."""

import re
from pathlib import Path

TRANSLATIONS = Path(__file__).resolve().parents[1] / "frontend" / "src" / "i18n" / "translations"

SPAR_KEYS = [
    "method.spar.name",
    "method.spar.desc",
    "method.spar.useCase",
    "method.spar.requirement",
    "phase.spar.1",
    "phase.spar.2",
    "phase.spar.3",
    "phase.spar.4",
    "phase.spar.1.msg",
    "phase.spar.2.msg",
    "phase.spar.3.msg",
    "phase.spar.4.msg",
    "role.layer0",
    "role.political",
    "role.economic",
    "role.environmental",
    "role.social",
    "role.devilsAdvocate",
    "role.moderator",
    "role.dcs",
    "role.plausibilityGate",
    "role.benchmarks",
    "role.layer3",
    "role.artifacts",
    "role.portfolio",
    "round.layer0",
    "round.round1",
    "round.round2",
    "round.dcs",
    "round.plausibilityGate",
    "round.modelBenchmarks",
    "round.layer3",
    "round.moderator",
    "round.portfolioRecommendation",
    "msg.humanReviewPrompt",
    "consensus.cleared",
    "consensus.humanReview",
    "terminology.result.spar",
    "terminology.synthesis.spar",
    "terminology.differences.spar",
    "terminology.by.spar",
    "terminology.consensus.spar",
    "discussion.spar",
]


def parse_ts(path: Path) -> tuple[str, dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    entries: dict[str, str] = {}
    for match in re.finditer(r'"([^"]+)":\s*"((?:[^"\\]|\\.)*)"', text):
        entries[match.group(1)] = match.group(2)
    return text, entries


def upsert_keys(text: str, entries: dict[str, str], en_entries: dict[str, str], keys: list[str]) -> str:
    """Replace existing SPAR keys or append missing ones."""
    updated = text
    missing: list[str] = []
    for key in keys:
        if key not in en_entries:
            continue
        pattern = rf'  "{re.escape(key)}": "[^"]*",\n'
        replacement = f'  "{key}": "{en_entries[key]}",\n'
        if re.search(pattern, updated):
            updated = re.sub(pattern, replacement, updated, count=1)
        elif key not in entries:
            missing.append(key)
    if missing:
        block = "\n".join(f'  "{key}": "{en_entries[key]}",' for key in missing)
        anchor = '  "discussion.tradeoff":'
        if anchor not in updated:
            raise SystemExit("Anchor not found for missing keys")
        updated = updated.replace(anchor, block + "\n" + anchor, 1)
    return updated, missing


def main() -> None:
    _, en_entries = parse_ts(TRANSLATIONS / "en.ts")
    for lang in ("de", "es", "fr", "it", "sv"):
        path = TRANSLATIONS / f"{lang}.ts"
        text, entries = parse_ts(path)
        updated, missing = upsert_keys(text, entries, en_entries, SPAR_KEYS)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            print(f"{lang}: synced {len(SPAR_KEYS)} keys ({len(missing)} added)")
        else:
            print(f"{lang}: ok")


if __name__ == "__main__":
    main()
