#!/usr/bin/env python3
"""Preflight Guard offline tests."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIDEORSI = Path("/home/descfly/miniconda3/envs/videorsi/bin/python")
# Explicit broken host (Phase D): must NOT equal videorsi; lacks imageio_ffmpeg.
SYSTEM = Path("/usr/bin/python3")
if not SYSTEM.is_file():
    SYSTEM = Path("/home/descfly/miniconda3/bin/python3")


def test_preflight_pass_under_videorsi():
    r = subprocess.run(
        [
            str(VIDEORSI),
            "-m",
            "experiment_guard.guarded_runner",
            "--soft",
            "--no-reexec",
            "--out",
            str(ROOT / "experiment_guard" / "out" / "test_preflight_pass.json"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
    )
    assert r.returncode == 0, r.stderr + r.stdout
    report = json.loads((ROOT / "experiment_guard" / "out" / "test_preflight_pass.json").read_text())
    assert report["status"] == "PASS"
    smoke = next(c for c in report["checks"] if c["name"] == "sample_frames_smoke")
    assert smoke["status"] == "PASS"
    assert smoke["detail"]["n_frames"] == 4
    assert smoke["detail"]["meter_summary"]["qwen_frames"] >= 4
    print("PASS test_preflight_pass_under_videorsi")


def test_phase_d_regression_system_python_blocked():
    """Known Phase D failure: host python without imageio_ffmpeg must FAIL before batch."""
    r = subprocess.run(
        [
            str(SYSTEM),
            "-m",
            "experiment_guard.guarded_runner",
            "--soft",
            "--no-reexec",
            "--out",
            str(ROOT / "experiment_guard" / "out" / "test_preflight_phase_d_fail.json"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
    )
    assert r.returncode != 0, "system python must fail preflight"
    report = json.loads((ROOT / "experiment_guard" / "out" / "test_preflight_phase_d_fail.json").read_text())
    assert report["status"] == "FAIL"
    codes = report.get("reason_codes") or []
    assert any(
        c in codes
        for c in (
            "host_python_mismatch",
            "imageio_ffmpeg_missing",
            "sample_frames_failed",
        )
    ) or any(
        c["status"] == "FAIL" and c.get("reason_code") in (
            "host_python_mismatch",
            "imageio_ffmpeg_missing",
            "sample_frames_failed",
        )
        for c in report["checks"]
    )
    print("PASS test_phase_d_regression_system_python_blocked")


def test_require_preflight_exits():
    r = subprocess.run(
        [
            str(SYSTEM),
            "-c",
            "from experiment_guard import require_preflight; require_preflight(reexec=False)",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
    )
    assert r.returncode != 0
    assert "EXPERIMENT_GUARD_PREFLIGHT_FAIL" in (r.stderr + r.stdout) or r.returncode == 2
    print("PASS test_require_preflight_exits")


def test_editor_and_probe_mock_under_videorsi():
    r = subprocess.run(
        [
            str(VIDEORSI),
            "-m",
            "experiment_guard",
            "--soft",
            "--no-reexec",
            "--editor",
            "--probe",
            "--out",
            str(ROOT / "experiment_guard" / "out" / "test_preflight_editor_probe.json"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
    )
    assert r.returncode == 0, r.stderr + r.stdout
    report = json.loads((ROOT / "experiment_guard" / "out" / "test_preflight_editor_probe.json").read_text())
    assert report["status"] == "PASS"
    by = {c["name"]: c for c in report["checks"]}
    assert by["editor_observe_mock"]["status"] == "PASS"
    assert by["infoflow_probe_mock"]["status"] == "PASS"
    print("PASS test_editor_and_probe_mock_under_videorsi")


def main() -> int:
    (ROOT / "experiment_guard" / "out").mkdir(parents=True, exist_ok=True)
    failed = 0
    for fn in (
        test_phase_d_regression_system_python_blocked,
        test_preflight_pass_under_videorsi,
        test_require_preflight_exits,
        test_editor_and_probe_mock_under_videorsi,
    ):
        try:
            fn()
        except Exception as exc:
            failed += 1
            print("FAIL", fn.__name__, exc)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
