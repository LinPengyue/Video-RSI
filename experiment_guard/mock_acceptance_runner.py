#!/usr/bin/env python3
"""Minimal Preflight → Runner → Runtime → Validation → Health (0 paid API).

Uses Mock Provider + local video smoke for 2 synthetic harness-like results.
Mirrors the GuardedExperiment lifecycle wired into eval_independent.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiment_guard import GuardedExperiment, PreflightCapabilities
from experiment_guard.fingerprints import config_fingerprint, harness_fingerprint
from experiment_guard.preflight import load_config, default_config_path


SEED = ROOT / "evolution" / "run-seed42" / "versions" / "initial_harness"
OUT = ROOT / "experiment_guard" / "out" / "mock_acceptance"


def healthy_result(sid: str, *, use_vision: bool = True) -> dict:
    if use_vision:
        return {
            "sample_id": sid,
            "status": "answered",
            "answer": "A",
            "usage": {"qwen_frames": 4, "frames_extracted": 4, "deepseek_calls": 2},
            "memory": [{"tool": "overview", "observation": {"text": "scene", "frames": ["f1", "f2"]}}],
            "service_trace": [{"service": "qwen"}, {"service": "sample_frames"}],
            "diagnostics": {},
        }
    return {
        "sample_id": sid,
        "status": "answered",
        "answer": "B",
        "usage": {"qwen_frames": 0, "frames_extracted": 0, "deepseek_calls": 1},
        "memory": [],
        "service_trace": [{"service": "deepseek"}],
        "diagnostics": {},
    }


def broken_result(sid: str) -> dict:
    return {
        "sample_id": sid,
        "status": "answered",
        "answer": "A",
        "usage": {"qwen_frames": 0, "frames_extracted": 0, "deepseek_calls": 5},
        "memory": [
            {
                "tool": "overview",
                "observation": {
                    "error": "RuntimeError",
                    "message": "ModuleNotFoundError: No module named 'imageio_ffmpeg'",
                },
            }
        ],
        "service_trace": [
            {"service": "sample_frames", "error": "ModuleNotFoundError: No module named 'imageio_ffmpeg'"}
        ],
        "diagnostics": {"tool_execution_errors": 1},
    }


def run_valid_path() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    cfg_path = default_config_path()
    guard = GuardedExperiment(
        experiment_id="mock_acceptance_valid",
        out_dir=OUT / "valid",
        config_path=cfg_path,
        harness_dir=SEED,
        capabilities=PreflightCapabilities(visual_sample_frames=True, provider_config=False),
        require_provider_env=False,
        formal_protocol=True,
    )
    pf = guard.start_soft(reexec=False, config=cfg)
    assert pf["status"] == "PASS", pf.get("reason_codes")

    ids = ["mock_s1", "mock_s2"]
    gold = {"mock_s1": "A", "mock_s2": "B"}

    def worker(sid: str) -> dict:
        return healthy_result(sid, use_vision=(sid == "mock_s1"))

    batch = guard.run_batch(ids, worker, max_workers=2)
    assert not batch.aborted
    health = guard.finalize(
        batch.results,
        gold=gold,
        expected_ids=ids,
        protocol_kwargs={
            "formal": True,
            "eval_ids": ids,
            "train_ids": ["train_only"],
            "gate_ids": ["gate_only"],
            "editor_subset_ids": ["ed_only"],
            "arm_ids": {"initial": ids},
            "arm_config_fingerprints": {"initial": config_fingerprint(cfg)},
            "arm_harness_fingerprints": {"initial": harness_fingerprint(SEED).get("sha16")},
            "cache_reuse_allowed": False,
        },
    )
    # Copy example
    examples = ROOT / "experiment_guard" / "examples"
    examples.mkdir(exist_ok=True)
    for stem in ("experiment_health.json", "experiment_health.md"):
        src = OUT / "valid" / stem
        if src.is_file():
            (examples / ("mock_acceptance_VALID_" + stem.replace("experiment_", ""))).write_text(src.read_text())
    return health


def run_invalid_path() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    cfg_path = default_config_path()
    guard = GuardedExperiment(
        experiment_id="mock_acceptance_invalid",
        out_dir=OUT / "invalid",
        config_path=cfg_path,
        harness_dir=SEED,
        capabilities=PreflightCapabilities(
            visual_sample_frames=False,  # skip smoke; inject Phase-D results
            host_must_match_config_python=False,
            provider_config=False,
        ),
        require_provider_env=False,
        formal_protocol=True,
    )
    guard.start_soft(reexec=False, config=cfg)
    ids = ["bad_%d" % i for i in range(8)]

    def worker(sid: str) -> dict:
        return broken_result(sid)

    batch = guard.run_batch(ids, worker, max_workers=2)
    assert batch.aborted, "must abort on first infra failure"
    assert batch.never_submitted > 0 or batch.cancelled_before_start > 0, batch.to_dict()
    health = guard.finalize(
        batch.results,
        gold={sid: "A" for sid in ids},
        expected_ids=ids,
        protocol_kwargs={
            "formal": True,
            "eval_ids": ids,
            "train_ids": ["train_only"],
            "gate_ids": ["gate_only"],
            "editor_subset_ids": [],
            "arm_ids": {"initial": ids},
            "arm_config_fingerprints": {"initial": config_fingerprint(cfg)},
            "arm_harness_fingerprints": {"initial": harness_fingerprint(SEED).get("sha16")},
            "cache_reuse_allowed": False,
        },
    )
    assert health["usable_for_architecture_ranking"] is False
    examples = ROOT / "experiment_guard" / "examples"
    for stem in ("experiment_health.json", "experiment_health.md"):
        src = OUT / "invalid" / stem
        if src.is_file():
            (examples / ("mock_acceptance_INVALID_" + stem.replace("experiment_", ""))).write_text(src.read_text())
    return {"health": health, "batch": batch.to_dict()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["valid", "invalid", "both"], default="both")
    args = ap.parse_args()
    out = {}
    if args.mode in ("valid", "both"):
        h = run_valid_path()
        out["valid"] = {
            "overall_validity": h.get("overall_validity"),
            "usable": h.get("usable_for_architecture_ranking"),
            "reason_codes": h.get("reason_codes"),
        }
        print("VALID_PATH", json.dumps(out["valid"], indent=2))
    if args.mode in ("invalid", "both"):
        inv = run_invalid_path()
        out["invalid"] = {
            "overall_validity": inv["health"].get("overall_validity"),
            "usable": inv["health"].get("usable_for_architecture_ranking"),
            "batch": {k: inv["batch"][k] for k in ("aborted", "abort_reason", "submitted", "never_submitted", "cancelled_before_start", "completed_after_abort")},
        }
        print("INVALID_PATH", json.dumps(out["invalid"], indent=2))
    (OUT / "acceptance_summary.json").write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
