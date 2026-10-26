#!/usr/bin/env python3
"""Fault injection suite — must catch Phase D and related silent failures."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiment_guard.health_report import build_health_report, write_health_report
from experiment_guard.preflight import CheckResult, PreflightCapabilities, load_config, run_preflight, run_sample_frames_smoke
from experiment_guard.result_validator import validate_arm, validate_multi_arm
from experiment_guard.runtime_guard import BatchAbortPolicy, RuntimeGuard, classify_item_run
from experiment_guard.protocol_validator import validate_protocol
from experiment_guard.guarded_runner import GuardedExperiment


OUT = ROOT / "experiment_guard" / "out" / "fault_injection"


def _cfg():
    return load_config()


def fault_missing_imageio_ffmpeg_classified():
    r = {
        "sample_id": "f1",
        "status": "answered",
        "answer": "A",
        "usage": {"qwen_frames": 0, "frames_extracted": 0, "deepseek_calls": 4},
        "memory": [
            {
                "tool": "overview",
                "observation": {"error": "RuntimeError", "message": "ModuleNotFoundError: No module named 'imageio_ffmpeg'"},
            }
        ],
        "service_trace": [{"service": "sample_frames", "error": "ModuleNotFoundError: No module named 'imageio_ffmpeg'"}],
        "diagnostics": {"tool_execution_errors": 1},
    }
    a = classify_item_run(r)
    assert a["validity"] == "INVALID_RUN"
    assert "imageio_ffmpeg_missing" in a["reasons"] or "visual_tooling_failed" in a["reasons"]
    print("PASS fault_missing_imageio_ffmpeg_classified")


def fault_invalid_ffmpeg_path_smoke():
    cfg = _cfg()
    # Inject sample_frames that raises ffmpeg path error
    def boom(services, timestamps):
        raise RuntimeError("ffmpeg executable not found: /bad/ffmpeg")

    cr = run_sample_frames_smoke(cfg, sample_frames_hook=boom)
    assert cr.status == "FAIL"
    assert cr.reason_code in ("sample_frames_failed", "imageio_ffmpeg_missing")
    print("PASS fault_invalid_ffmpeg_path_smoke")


def fault_missing_video():
    cfg = _cfg()
    cr = run_sample_frames_smoke(cfg, video_path=Path("/nonexistent/video_guard_test.mp4"))
    assert cr.status == "FAIL"
    assert cr.reason_code == "smoke_video_unavailable"
    print("PASS fault_missing_video")


def fault_corrupt_video_decode():
    cfg = _cfg()
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "corrupt.mp4"
        bad.write_bytes(b"not-a-video")
        cr = run_sample_frames_smoke(cfg, video_path=bad)
        assert cr.status == "FAIL"
        assert cr.reason_code in (
            "sample_frames_failed",
            "frame_decode_failed",
            "frame_count_mismatch",
            "frame_file_missing",
        ), cr.reason_code
        print("PASS fault_corrupt_video_decode")


def fault_sample_frames_exception():
    cfg = _cfg()

    def boom(services, timestamps):
        raise RuntimeError("injected sample_frames failure")

    cr = run_sample_frames_smoke(cfg, sample_frames_hook=boom)
    assert cr.status == "FAIL"
    assert "injected sample_frames" in str(cr.detail.get("error", ""))
    print("PASS fault_sample_frames_exception")


def fault_qwen_request_failure_meter():
    # Simulate answered with qwen events but 0 frames
    r = {
        "sample_id": "f_qwen",
        "status": "answered",
        "answer": "B",
        "usage": {"qwen_frames": 0, "frames_extracted": 4, "deepseek_calls": 1},
        "memory": [{"tool": "overview", "observation": {"text": "x", "frames": ["f1"]}}],
        "service_trace": [{"service": "qwen"}, {"service": "sample_frames"}],
        "diagnostics": {},
    }
    a = classify_item_run(r)
    assert a["validity"] == "INVALID_RUN"
    assert "meter_inconsistent_with_trace" in a["reasons"]
    print("PASS fault_qwen_request_failure_meter")


def fault_answered_after_all_vision_failed():
    r = {
        "sample_id": "f_ans",
        "status": "answered",
        "answer": "C",
        "usage": {"qwen_frames": 0, "frames_extracted": 0, "deepseek_calls": 6},
        "memory": [
            {"tool": "overview", "observation": {"error": "x", "message": "fail"}},
            {"tool": "scan_interval", "observation": {"error": "x", "message": "fail"}},
        ],
        "service_trace": [{"service": "sample_frames", "error": "fail"}],
        "diagnostics": {"tool_execution_errors": 2},
    }
    a = classify_item_run(r)
    assert a["validity"] == "INVALID_RUN"
    v = validate_arm([r], gold={"f_ans": "C"})
    assert v["usable_for_architecture_ranking"] is False
    assert v["naive_including_invalid"]["correct"] == 1
    print("PASS fault_answered_after_all_vision_failed")


def fault_intentional_no_vision_ok():
    r = {
        "sample_id": "f_int",
        "status": "answered",
        "answer": "D",
        "usage": {"qwen_frames": 0, "frames_extracted": 0, "deepseek_calls": 1},
        "memory": [],
        "service_trace": [{"service": "deepseek"}],
        "diagnostics": {},
    }
    a = classify_item_run(r)
    assert a["validity"] == "VALID_RUN"
    assert a["intentional_no_vision"]
    print("PASS fault_intentional_no_vision_ok")


def fault_arm_sample_mismatch():
    m = validate_multi_arm({"A": [{"sample_id": "1", "status": "answered", "answer": "A", "usage": {}, "memory": [], "service_trace": [], "diagnostics": {}}],
                            "B": [{"sample_id": "2", "status": "answered", "answer": "A", "usage": {}, "memory": [], "service_trace": [], "diagnostics": {}}]})
    assert any("mismatch" in c for c in m["reason_codes"])
    print("PASS fault_arm_sample_mismatch")


def fault_resume_old_config():
    p = OUT / "old_results.json"
    OUT.mkdir(parents=True, exist_ok=True)
    p.write_text("[]\n")
    v = validate_protocol(
        resume_results_path=p,
        expected_config_fingerprint="new_fp",
        observed_config_fingerprint="old_fp",
    )
    assert "resume_config_fingerprint_mismatch" in v["reason_codes"]
    print("PASS fault_resume_old_config")


def fault_editor_investigation_failure_still_flagged():
    # Editor finishes but investigation tools failed → INVALID_RUN on investigation result shape
    r = {
        "sample_id": "ed1",
        "status": "completed",
        "answer": None,
        "usage": {"qwen_frames": 0, "frames_extracted": 0},
        "memory": [
            {"tool": "overview", "observation": {"error": "RuntimeError", "message": "ModuleNotFoundError: No module named 'imageio_ffmpeg'"}}
        ],
        "service_trace": [{"service": "sample_frames", "error": "ModuleNotFoundError: No module named 'imageio_ffmpeg'"}],
        "diagnostics": {"tool_execution_errors": 1},
    }
    a = classify_item_run(r)
    assert a["validity"] == "INVALID_RUN"
    print("PASS fault_editor_investigation_failure_still_flagged")


def fault_injection_emits_health_report():
    """Generate example health report under fault injection (Phase D-like batch)."""
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for i in range(3):
        results.append(
            {
                "sample_id": "lvbench_fault_%d" % i,
                "status": "answered",
                "answer": "A",
                "usage": {"qwen_frames": 0, "frames_extracted": 0, "deepseek_calls": 4},
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
        )
    gold = {r["sample_id"]: "A" for r in results}
    guard = GuardedExperiment(
        experiment_id="fault_injection_phase_d_sim",
        out_dir=OUT / "sim_run",
        capabilities=PreflightCapabilities(
            visual_sample_frames=False,  # skip real smoke; simulate post-hoc
            host_must_match_config_python=False,
            provider_config=False,
        ),
    )
    # Soft start without visual to allow generating post-hoc invalid report
    pf = guard.start_soft(reexec=False)
    # Force mark preflight as FAIL for the demo report realism
    pf["status"] = "FAIL"
    pf["reason_codes"] = ["imageio_ffmpeg_missing"]
    guard.preflight_report = pf
    rt = RuntimeGuard(policy=BatchAbortPolicy())
    for r in results:
        rt.observe_result(r)
        if rt.aborted:
            break
    guard.runtime = rt
    health = guard.finalize(results, gold=gold, expected_ids=[r["sample_id"] for r in results])
    assert health["overall_validity"] == "INVALID"
    assert health["usable_for_architecture_ranking"] is False
    assert (OUT / "sim_run" / "experiment_health.md").is_file()
    # Copy canonical example
    example_dir = ROOT / "experiment_guard" / "examples"
    example_dir.mkdir(parents=True, exist_ok=True)
    md = (OUT / "sim_run" / "experiment_health.md").read_text()
    js = (OUT / "sim_run" / "experiment_health.json").read_text()
    (example_dir / "fault_injection_health.md").write_text(md)
    (example_dir / "fault_injection_health.json").write_text(js)
    print("PASS fault_injection_emits_health_report")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tests = [
        fault_missing_imageio_ffmpeg_classified,
        fault_invalid_ffmpeg_path_smoke,
        fault_missing_video,
        fault_corrupt_video_decode,
        fault_sample_frames_exception,
        fault_qwen_request_failure_meter,
        fault_answered_after_all_vision_failed,
        fault_intentional_no_vision_ok,
        fault_arm_sample_mismatch,
        fault_resume_old_config,
        fault_editor_investigation_failure_still_flagged,
        fault_injection_emits_health_report,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
        except Exception as exc:
            failed += 1
            print("FAIL", fn.__name__, exc)
    print("fault_injection failed=%d total=%d" % (failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
