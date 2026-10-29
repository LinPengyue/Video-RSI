#!/usr/bin/env python3
"""Dry-run config checks for Track A. No model calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "research_audit/lvbench_compositional/track_a/configs/dry_run_arms.json"
RESULT = ROOT / "research_audit/lvbench_compositional/track_a/config_check_result.json"


def main() -> int:
    if not CFG.is_file():
        print(json.dumps({"ok": False, "error": f"missing {CFG}"}))
        return 2
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    counts = cfg.get("current_counts", {})
    checks = {
        "dry_run": bool(cfg.get("dry_run")),
        "forbid_paid_api": bool(cfg.get("forbid_paid_api")),
        "forbid_hs1_as_final_judge": bool(cfg.get("forbid_hs1_as_final_judge")),
        "arms_complete": set(cfg.get("arms_required", []))
        >= {"no_harness", "fixed_strong_planner", "vanilla_rsi", "new_rsi"},
        "supported_unseen_items_ge_min": counts.get("supported_composition_questions", 0)
        >= cfg.get("min_supported_unseen_items_to_start", 6),
        "supported_unseen_videos_ge_min": counts.get("supported_composition_videos", 0)
        >= cfg.get("min_supported_unseen_videos", 3),
        "valid_seen_query_action_ge_min": counts.get("valid_query_action_train_audited", 0)
        >= cfg.get("min_valid_seen_query_action_items", 4),
    }
    ok = all(
        [
            checks["dry_run"],
            checks["forbid_paid_api"],
            checks["forbid_hs1_as_final_judge"],
            checks["arms_complete"],
        ]
    )
    ready = ok and checks["supported_unseen_items_ge_min"] and checks["supported_unseen_videos_ge_min"] and checks["valid_seen_query_action_ge_min"]
    out = {
        "config_ok": ok,
        "ok_for_expensive_rsi": ready,
        "checks": checks,
        "current_counts": counts,
    }
    RESULT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
