#!/usr/bin/env python3
"""Print SPAR offline model comparative benchmark analysis.

Usage:
    uv run python examples/spar_model_benchmark_report.py
    uv run python examples/spar_model_benchmark_report.py --preset demo-diverse --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from quorum.methods.spar_model_benchmarks import build_analysis_report, format_benchmark_report


def main() -> None:
    parser = argparse.ArgumentParser(description="SPAR model benchmark comparative analysis")
    parser.add_argument("--preset", default="demo-diverse")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown summary")
    args = parser.parse_args()

    if args.json:
        print(json.dumps(build_analysis_report(args.preset), indent=2))
    else:
        print(format_benchmark_report(args.preset))


if __name__ == "__main__":
    main()
