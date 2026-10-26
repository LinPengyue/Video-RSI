#!/usr/bin/env python3
"""Minimal Path A/B info-flow A/B runner (design + dry-run).

Path A (reuse): DeepSeek answers from cached overview perception text.
Path B: Qwen direct VQA on ffmpeg-reextracted frames at the same timestamps.

Default: --dry-run (no provider calls).
Paid execution requires BOTH --execute and env ARCH_AB_ALLOW_PAID=1.

Does not import Editor. Does not touch Gate cohort. Does not modify evolution/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = Path(__file__).resolve().parent / "exploratory_samples_n20.json"
TRAIN_CACHE = ROOT / "evolution" / "run-seed42" / "training_cache" / "initial_harness"
TRAIN_ITEMS = ROOT / "data" / "lvbench-split" / "train_items.jsonl"
GATE_ORACLE = ROOT / "data" / "lvbench-split" / "gate_oracle.jsonl"


def load_gate_ids() -> set[str]:
    ids = set()
    for line in GATE_ORACLE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ids.add(json.loads(line)["sample_id"])
    return ids


def load_train_items() -> dict:
    out = {}
    for line in TRAIN_ITEMS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["sample_id"]] = row
    return out


def cache_by_sample_id() -> dict:
    out = {}
    for path in TRAIN_CACHE.glob("item_*.json"):
        row = json.loads(path.read_text(encoding="utf-8"))
        out[row["sample_id"]] = row
    return out


def overview_bundle(traj: dict) -> dict:
    for step in traj.get("memory") or []:
        if step.get("tool") != "overview":
            continue
        obs = step.get("observation") or {}
        frames = obs.get("frames") or []
        text = ((obs.get("perception") or {}).get("text") or "").strip()
        timestamps = [float(f["timestamp"]) for f in frames]
        return {
            "timestamps": timestamps,
            "n_frames": len(timestamps),
            "perception_text": text,
            "frame_ids": [f.get("id") for f in frames],
        }
    raise ValueError("no overview step")


def extract_frames(video_path: Path, timestamps: list[float], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, ts in enumerate(timestamps):
        dest = out_dir / ("frame_%06d.jpg" % i)
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-ss", str(ts), "-i", str(video_path),
                "-frames:v", "1", "-vf", "scale=768:-2", "-threads", "1", "-y", str(dest),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        paths.append(dest)
    return paths


def bundle_sha(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def dry_plan(sample_ids: list[str]) -> dict:
    gate = load_gate_ids()
    items = load_train_items()
    cache = cache_by_sample_id()
    rows = []
    for sid in sample_ids:
        if sid in gate:
            raise SystemExit("ABORT: Gate ID leaked into exploratory set: %s" % sid)
        item = items[sid]
        traj = cache[sid]
        ov = overview_bundle(traj)
        rows.append(
            {
                "sample_id": sid,
                "video_path_exists": Path(item["video_path"]).is_file(),
                "question_type": item.get("question_type"),
                "n_overview_frames": ov["n_frames"],
                "perception_chars": len(ov["perception_text"]),
                "planned_path_B": "qwen_direct_vqa",
                "planned_path_A": "deepseek_on_cached_overview_text",
                "qwen_calls": 1,
                "deepseek_calls": 1,
                "editor_calls": 0,
            }
        )
    return {
        "mode": "dry-run",
        "n": len(rows),
        "total_qwen": sum(r["qwen_calls"] for r in rows),
        "total_deepseek": sum(r["deepseek_calls"] for r in rows),
        "total_editor": 0,
        "items": rows,
        "consistency_checks": [
            "overview timestamps from train_cache",
            "ffmpeg extract once → shared frame_bundle_sha for A and B",
            "Gate ID exclusion",
            "budget ≤24/24/0",
        ],
        "execute_blocked_unless": "ARCH_AB_ALLOW_PAID=1 and --execute",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--execute", action="store_true", help="paid calls; also needs ARCH_AB_ALLOW_PAID=1")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    frozen = json.loads(SAMPLES.read_text(encoding="utf-8"))
    ids = list(frozen["sample_ids"])
    if args.limit is not None:
        ids = ids[: args.limit]

    if args.execute:
        if os.environ.get("ARCH_AB_ALLOW_PAID") != "1":
            print("Refusing --execute without ARCH_AB_ALLOW_PAID=1", file=sys.stderr)
            return 2
        print(
            "EXECUTE path not implemented in preflight; wire provider.chat after approval.",
            file=sys.stderr,
        )
        return 3

    plan = dry_plan(ids)
    out = Path(__file__).resolve().parent / "out" / "ab_dry_run_plan.safe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(out), "n": plan["n"], "qwen": plan["total_qwen"], "deepseek": plan["total_deepseek"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
