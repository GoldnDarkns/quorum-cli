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
    "phase.spar.1.msg",
    "phase.spar.2.msg",
    "phase.spar.3.msg",
    "role.political",
    "role.economic",
    "role.environmental",
    "role.social",
    "role.devilsAdvocate",
    "role.moderator",
    "round.round1",
    "round.round2",
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


def main() -> None:
    _, en_entries = parse_ts(TRANSLATIONS / "en.ts")
    for lang in ("de", "es", "fr", "it", "sv"):
        path = TRANSLATIONS / f"{lang}.ts"
        text, entries = parse_ts(path)
        missing = [key for key in SPAR_KEYS if key not in entries]
        if not missing:
            print(f"{lang}: ok")
            continue
        block = "\n".join(f'  "{key}": "{en_entries[key]}",' for key in missing)
        anchor = '  "discussion.tradeoff":'
        if anchor not in text:
            raise SystemExit(f"Anchor not found in {path}")
        text = text.replace(anchor, block + "\n" + anchor, 1)
        path.write_text(text, encoding="utf-8")
        print(f"{lang}: added {len(missing)} keys")


if __name__ == "__main__":
    main()
