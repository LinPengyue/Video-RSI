#!/usr/bin/env python3
"""WP3 S0–S9 end-to-end DEV smoke via Batch Factory formal entry.

Uses existing Wave/AB ROI evidence only. Does not hardcode video IDs,
questions, or Necessity labels into the production path.
Separates regression fixtures from production.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))  # repo root for tools.*
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DS_ROOT, REPO_ROOT, utc_now, write_json  # noqa: E402
from tools.lvbench_comp.batch_factory.s0_s9_production import (  # noqa: E402
    PRODUCTION_ENTRY,
    run_s0_s9_dev_smoke,
)

BASELINE = "7b133e731777d5b7ca589ef1ea4229e59fd4e7ec"
WP3 = DS_ROOT / "wp3_production"
OUT = WP3 / "wp3_s0_s9_e2e_dev_smoke"
REPORTS = DS_ROOT / "reports"
REGISTRY = WP3 / "wp3_4" / "trusted_human_review_registry" / "records.jsonl"

# Existing DEV evidence sources (paths only — selection is max_pairs, not video allowlist)
DEFAULT_ROIS = [
    WP3 / "wp3_3" / "ab_dev5" / "rois.jsonl",
    WP3 / "wave1" / "rois.jsonl",
    WP3 / "wave2" / "rois.jsonl",
]


def main() -> int:
    rois = [p for p in DEFAULT_ROIS if p.exists()]
    if not rois:
        print("ERROR: no ROI evidence jsonl found", file=sys.stderr)
        return 2
    report = run_s0_s9_dev_smoke(
        rois_jsonl_paths=rois,
        trusted_records_jsonl=REGISTRY,
        output_dir=OUT,
        max_pairs=8,
    )
    summary = {
        "schema": "wp3_s0_s9_e2e_dev_smoke_summary_v1",
        "work_package": "WP3_PRODUCTION_INTEGRATION_E2E_DEV_SMOKE",
        "baseline_commit": BASELINE,
        "built_utc": utc_now(),
        "production_entry": PRODUCTION_ENTRY,
        "n_pairs": report["n_pairs"],
        "classification_counts": report["classification_counts"],
        "exit_counts": report["exit_counts"],
        "pipeline_engineering_completion": report["pipeline_engineering_completion"],
        "scientific_rates": report["scientific_rates"],
        "failures": report["failures"],
        "protections": report["protections"],
        "claim": (
            "Engineering: unified S0–S9 path ran on real ROI evidence. "
            "Scientific rates reported separately; Formal Gold 0; "
            "no scaled Gold capacity claimed."
        ),
        "output_dir": str(OUT.relative_to(REPO_ROOT)),
    }
    write_json(OUT / "WP3_S0_S9_E2E_DEV_SMOKE_SUMMARY.json", summary)
    write_json(REPORTS / "WP3_S0_S9_E2E_DEV_SMOKE_SUMMARY.json", summary)
    write_json(REPORTS / "S0_S9_DEV_SMOKE_REPORT.json", report)
    print(json.dumps({
        "n_pairs": summary["n_pairs"],
        "classification_counts": summary["classification_counts"],
        "exit_counts": summary["exit_counts"],
        "scientific_rates": summary["scientific_rates"],
        "engineering": summary["pipeline_engineering_completion"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
