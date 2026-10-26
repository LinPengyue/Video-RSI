#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiment_guard.result_validator import validate_arm, validate_multi_arm


def _ok(sid, ans="A", frames=8):
    return {
        "sample_id": sid,
        "status": "answered",
        "answer": ans,
        "usage": {"qwen_frames": frames, "frames_extracted": frames, "deepseek_calls": 2},
        "memory": [{"tool": "overview", "observation": {"text": "ok", "frames": ["f1"]}}],
        "service_trace": [{"service": "qwen"}],
        "diagnostics": {},
    }


def _broken(sid, ans="A"):
    return {
        "sample_id": sid,
        "status": "answered",
        "answer": ans,
        "usage": {"qwen_frames": 0, "frames_extracted": 0, "deepseek_calls": 5},
        "memory": [
            {
                "tool": "overview",
                "observation": {"error": "RuntimeError", "message": "ModuleNotFoundError: No module named 'imageio_ffmpeg'"},
            }
        ],
        "service_trace": [{"service": "sample_frames", "error": "ModuleNotFoundError: No module named 'imageio_ffmpeg'"}],
        "diagnostics": {"tool_execution_errors": 1},
    }


def test_healthy_arm_valid():
    gold = {"s1": "A", "s2": "B"}
    rows = [_ok("s1", "A"), _ok("s2", "B")]
    v = validate_arm(rows, gold=gold, expected_ids=["s1", "s2"], arm_name="initial")
    assert v["overall_validity"] == "VALID"
    assert v["usable_for_architecture_ranking"] is True
    assert v["architecture_comparable"]["accuracy"] == 1.0
    print("PASS test_healthy_arm_valid")


def test_phase_d_arm_invalid_blocks_ranking():
    gold = {"s1": "A", "s2": "A"}
    rows = [_broken("s1", "A"), _broken("s2", "A")]
    v = validate_arm(rows, gold=gold, arm_name="initial")
    assert v["overall_validity"] == "INVALID"
    assert v["usable_for_architecture_ranking"] is False
    assert v["naive_including_invalid"]["accuracy"] == 1.0  # would have looked good
    assert "systematic_vision_infra_failure" in v["reason_codes"] or "has_invalid_runs" in v["reason_codes"]
    print("PASS test_phase_d_arm_invalid_blocks_ranking")


def test_multi_arm_sample_mismatch():
    m = validate_multi_arm(
        {"initial": [_ok("s1")], "direct": [_ok("s2")]},
        require_same_ids=True,
    )
    assert m["overall_validity"] != "VALID" or any("mismatch" in c for c in m["reason_codes"])
    assert any("mismatch" in c for c in m["reason_codes"])
    print("PASS test_multi_arm_sample_mismatch")


def test_multi_arm_vision_lost():
    m = validate_multi_arm(
        {
            "initial": [_broken("s1"), _broken("s2")],
            "direct": [_ok("s1", frames=32), _ok("s2", frames=32)],
        },
        expected_ids=["s1", "s2"],
        vision_required_arms=["initial", "direct"],
    )
    assert m["overall_validity"] == "INVALID"
    assert m["usable_for_architecture_ranking"] is False
    print("PASS test_multi_arm_vision_lost")


def main() -> int:
    failed = 0
    for fn in (
        test_healthy_arm_valid,
        test_phase_d_arm_invalid_blocks_ranking,
        test_multi_arm_sample_mismatch,
        test_multi_arm_vision_lost,
    ):
        try:
            fn()
        except Exception as exc:
            failed += 1
            print("FAIL", fn.__name__, exc)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
