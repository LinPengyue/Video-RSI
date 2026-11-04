#!/usr/bin/env python3
"""CLI: Stage 2 normalize → validate; Stage 3 only if Stage 2 PASS."""
from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent


def main() -> int:
    ap = argparse.ArgumentParser(description="Track B Stage2/3 normalized programs + overlap")
    ap.add_argument("--stage", choices=["2", "3", "all"], default="all")
    args = ap.parse_args()

    if args.stage in ("2", "all"):
        # Isolate argv so nested argparse does not see --stage
        old_argv = sys.argv
        try:
            sys.argv = [str(HERE / "build_normalized_programs_v1.py")]
            runpy.run_path(str(HERE / "build_normalized_programs_v1.py"), run_name="__main__")
        finally:
            sys.argv = old_argv

    report = json.loads((OUT / "validation_report.json").read_text())
    print(f"Stage2={report['status']} totals={report['observed_totals']}")

    if args.stage in ("3", "all"):
        if report["status"] != "PASS":
            print(
                "Stage3=BLOCKED: Stage 2 did not PASS; overlap metrics intentionally null.",
                file=sys.stderr,
            )
            return 2
        print("Stage3 would run here (not reached while Stage2 BLOCKED)")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
