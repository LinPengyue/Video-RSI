#!/usr/bin/env python3
"""Regenerate desensitized summaries from local run_dir (no API)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ab_infoflow_runner import ResultStore, decide_go_stop, safe_summary, summarize_ab
from infoflow_lib import PREFLIGHT, load_json, load_train_items, load_oracle, TRAIN_ORACLE, write_json


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, default=PREFLIGHT / "runs" / "infoflow_v1")
    args = ap.parse_args()
    items = load_train_items()
    golds = load_oracle(TRAIN_ORACLE)
    store = ResultStore(args.run_dir)
    ab = summarize_ab(store, items, golds)
    conn = load_json(args.run_dir / "connectivity_result.json") if (args.run_dir / "connectivity_result.json").is_file() else None
    diag = load_json(args.run_dir / "diagnose_result.json") if (args.run_dir / "diagnose_result.json").is_file() else None
    decision = decide_go_stop(ab, diag)
    safe = safe_summary(ab, conn, diag)
    safe["go_stop"] = decision
    write_json(args.run_dir / "ab_summary.json", ab)
    write_json(PREFLIGHT / "out" / "ab_summary.safe.json", safe)
    write_json(args.run_dir / "go_stop.json", decision)
    print(json.dumps({"n": ab["n"], "A": ab["A_correct"], "B": ab["B_correct"], "decision": decision["decision"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
