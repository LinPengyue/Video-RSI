#!/usr/bin/env python3
"""Runtime Guard Case A/B/C + abort policy."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiment_guard.runtime_guard import BatchAbortPolicy, RuntimeGuard, classify_item_run


def _phase_d_like():
    return {
        "sample_id": "lvbench_x",
        "status": "answered",
        "answer": "A",
        "usage": {"qwen_frames": 0, "qwen_calls": 0, "frames_extracted": 0, "deepseek_calls": 5},
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


def test_case_a_intentional_no_vision():
    fake = {
        "sample_id": "y",
        "status": "answered",
        "answer": "B",
        "usage": {"qwen_frames": 0, "qwen_calls": 0, "frames_extracted": 0, "deepseek_calls": 2},
        "memory": [{"tool": "read_transcript", "observation": {"status": "unavailable"}}],
        "service_trace": [{"service": "deepseek"}],
        "diagnostics": {"tool_execution_errors": 0},
    }
    a = classify_item_run(fake)
    assert a["validity"] == "VALID_RUN"
    assert a["intentional_no_vision"] is True
    assert a["case"] == "A"
    print("PASS test_case_a_intentional_no_vision")


def test_case_b_vision_infra_failure():
    a = classify_item_run(_phase_d_like())
    assert a["validity"] == "INVALID_RUN"
    assert a["case"] == "B"
    assert "visual_tooling_failed" in a["reasons"] or "imageio_ffmpeg_missing" in a["reasons"]
    assert a["error_kind"] == "ENGINEERING_ERROR"
    print("PASS test_case_b_vision_infra_failure")


def test_case_c_partial():
    fake = {
        "sample_id": "z",
        "status": "answered",
        "answer": "C",
        "usage": {"qwen_frames": 4, "frames_extracted": 8, "deepseek_calls": 3},
        "memory": [
            {"tool": "overview", "observation": {"text": "ok scene", "frames": ["f1"]}},
            {"tool": "scan_interval", "observation": {"error": "timeout", "message": "provider timeout"}},
        ],
        "service_trace": [{"service": "qwen"}],
        "diagnostics": {"tool_execution_errors": 1},
    }
    a = classify_item_run(fake)
    assert a["validity"] == "DEGRADED_RUN"
    assert a["case"] == "C"
    print("PASS test_case_c_partial")


def test_batch_abort_on_phase_d():
    g = RuntimeGuard(policy=BatchAbortPolicy())
    a = g.observe_result(_phase_d_like())
    assert a["validity"] == "INVALID_RUN"
    assert g.aborted is True
    assert g.abort_reason in (
        "systematic_sample_frames_infra_error",
        "meter_inconsistent_with_trace",
        "repeated_infrastructure_failure",
    )
    print("PASS test_batch_abort_on_phase_d")


def test_no_false_positive_on_intentional():
    g = RuntimeGuard(policy=BatchAbortPolicy())
    g.observe_result(
        {
            "sample_id": "a",
            "status": "answered",
            "answer": "A",
            "usage": {"qwen_frames": 0, "frames_extracted": 0, "deepseek_calls": 1},
            "memory": [],
            "service_trace": [],
            "diagnostics": {},
        }
    )
    assert g.aborted is False
    print("PASS test_no_false_positive_on_intentional")


def main() -> int:
    failed = 0
    for fn in (
        test_case_a_intentional_no_vision,
        test_case_b_vision_infra_failure,
        test_case_c_partial,
        test_batch_abort_on_phase_d,
        test_no_false_positive_on_intentional,
    ):
        try:
            fn()
        except Exception as exc:
            failed += 1
            print("FAIL", fn.__name__, exc)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
