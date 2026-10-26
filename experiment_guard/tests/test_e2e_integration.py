#!/usr/bin/env python3
"""End-to-end Guard tests through runner-equivalent paths (0 paid API)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
VIDEORSI = "/home/descfly/miniconda3/envs/videorsi/bin/python"
SYSTEM = "/usr/bin/python3"
if not Path(SYSTEM).is_file():
    SYSTEM = "/home/descfly/miniconda3/bin/python3"

from experiment_guard import GuardedExperiment, PreflightCapabilities, classify_item_run
from experiment_guard.concurrent_batch import run_guarded_batch
from experiment_guard.fingerprint_snapshot import capture_snapshot, reread_fingerprint
from experiment_guard.preflight import load_config, default_config_path
from experiment_guard.runtime_guard import RuntimeGuard, BatchAbortPolicy
from experiment_guard.protocol_validator import validate_protocol
from experiment_guard.fingerprints import config_fingerprint, harness_fingerprint


SEED = ROOT / "evolution" / "run-seed42" / "versions" / "initial_harness"
PILOT = ROOT / "research_audit" / "arch_self_evolution_pilot"


def _phase_d(sid):
    return {
        "sample_id": sid,
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


def test_eval_independent_dry_run_no_provider():
    r = subprocess.run(
        [SYSTEM, str(PILOT / "eval_independent.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "n" in data
    assert "guard" in data
    print("PASS test_eval_independent_dry_run_no_provider")


def test_editor_arms_prepare_only_no_provider():
    r = subprocess.run(
        [SYSTEM, str(PILOT / "run_editor_arms.py"), "--prepare-only", "--arm", "baseline"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert r.returncode == 0, r.stderr + r.stdout
    data = json.loads(r.stdout)
    assert data["guard"]["note"].startswith("dry-run") or "preflight not required" in data["guard"]["note"]
    print("PASS test_editor_arms_prepare_only_no_provider")


def test_execute_wrong_python_blocked_via_require_preflight():
    """Simulate --execute preflight under system python (Phase D host)."""
    r = subprocess.run(
        [
            SYSTEM,
            "-c",
            "from experiment_guard import require_preflight, PreflightCapabilities;"
            "require_preflight(capabilities=PreflightCapabilities(), reexec=False, require_provider_env=False)",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert r.returncode != 0
    assert "EXPERIMENT_GUARD_PREFLIGHT_FAIL" in (r.stderr + r.stdout) or r.returncode == 2
    print("PASS test_execute_wrong_python_blocked_via_require_preflight")


def test_concurrent_abort_stops_submitting_remaining():
    guard = RuntimeGuard(policy=BatchAbortPolicy())
    ids = ["s%02d" % i for i in range(24)]
    calls = {"n": 0}

    def worker(sid):
        calls["n"] += 1
        time.sleep(0.01)
        return _phase_d(sid)

    report = run_guarded_batch(ids, worker, guard, max_workers=2)
    assert report.aborted
    assert report.never_submitted > 0 or report.cancelled_before_start > 0, report.to_dict()
    # Must not run all 24
    assert report.submitted < 24, report.to_dict()
    assert report.completed < 24
    print(
        "PASS test_concurrent_abort_stops_submitting_remaining",
        "submitted=%d never=%d cancelled=%d completed=%d"
        % (report.submitted, report.never_submitted, report.cancelled_before_start, report.completed),
    )


def test_fingerprint_reread_detects_config_change():
    with tempfile.TemporaryDirectory() as td:
        cfg_path = Path(td) / "cfg.json"
        base = load_config()
        cfg_path.write_text(json.dumps(base, indent=2))
        snap1 = capture_snapshot(config_path=cfg_path, harness_dir=SEED)
        # mutate on disk
        base2 = json.loads(cfg_path.read_text())
        base2.setdefault("solver", {})["max_steps"] = int(base2.get("solver", {}).get("max_steps", 11)) + 1
        cfg_path.write_text(json.dumps(base2, indent=2))
        fp2, _ = reread_fingerprint(config_path=cfg_path, harness_dir=SEED)
        assert fp2 != snap1.config_fp

        ge = GuardedExperiment(
            experiment_id="fp_drift",
            out_dir=Path(td) / "guard",
            config_path=cfg_path,
            harness_dir=SEED,
            capabilities=PreflightCapabilities(
                visual_sample_frames=False,
                host_must_match_config_python=False,
                provider_config=False,
            ),
            formal_protocol=False,
        )
        # start_soft with original content restored first
        cfg_path.write_text(json.dumps(base, indent=2))
        ge.start_soft(reexec=False)
        start_fp = ge.cfg_fp
        # drift
        base2 = json.loads(cfg_path.read_text())
        base2.setdefault("solver", {})["max_steps"] = int(base2.get("solver", {}).get("max_steps", 11)) + 7
        cfg_path.write_text(json.dumps(base2, indent=2))
        # healthy result but fingerprint change should abort
        ok = {
            "sample_id": "x",
            "status": "answered",
            "answer": "A",
            "usage": {"qwen_frames": 4, "frames_extracted": 4},
            "memory": [{"tool": "overview", "observation": {"text": "ok", "frames": ["f"]}}],
            "service_trace": [{"service": "qwen"}],
            "diagnostics": {},
        }
        aborted = ge.observe(ok)
        assert aborted is True
        assert ge.runtime.abort_reason == "config_or_harness_fingerprint_changed"
        assert ge.live_fingerprint()[0] != start_fp
        print("PASS test_fingerprint_reread_detects_config_change")


def test_multi_arm_config_mismatch_protocol():
    v = validate_protocol(
        formal=True,
        eval_ids=["a"],
        train_ids=["t"],
        gate_ids=["g"],
        arm_ids={"initial": ["a"], "direct": ["a"]},
        arm_config_fingerprints={"initial": "cfgA", "direct": "cfgB"},  # different OK for architectures
        arm_harness_fingerprints={"initial": "h1", "direct": "h1"},
        cache_reuse_allowed=False,
    )
    # different configs across arms are allowed; status should still PASS if all declared
    assert v["status"] == "PASS", v
    # But empty / missing formal fields fail incomplete
    v2 = validate_protocol(formal=True, eval_ids=["a"], train_ids=["t"], gate_ids=["g"])
    assert v2["status"] == "INCOMPLETE"
    print("PASS test_multi_arm_config_mismatch_protocol")


def test_resume_old_results_blocked():
    p = ROOT / "experiment_guard" / "out" / "_resume_old.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("[]\n")
    v = validate_protocol(
        formal=True,
        eval_ids=["a"],
        train_ids=["t"],
        gate_ids=["g"],
        arm_ids={"initial": ["a"]},
        arm_config_fingerprints={"initial": "new"},
        arm_harness_fingerprints={"initial": "h"},
        resume_results_path=p,
        expected_config_fingerprint="new",
        observed_config_fingerprint="old",
        cache_reuse_allowed=False,
    )
    assert v["status"] == "FAIL"
    assert "resume_config_fingerprint_mismatch" in v["reason_codes"]
    print("PASS test_resume_old_results_blocked")


def test_intentional_no_vision_not_aborted():
    g = RuntimeGuard(policy=BatchAbortPolicy())
    g.observe_result(
        {
            "sample_id": "z",
            "status": "answered",
            "answer": "C",
            "usage": {"qwen_frames": 0, "frames_extracted": 0, "deepseek_calls": 1},
            "memory": [],
            "service_trace": [],
            "diagnostics": {},
        }
    )
    assert g.aborted is False
    assert classify_item_run(
        {
            "sample_id": "z",
            "status": "answered",
            "answer": "C",
            "usage": {"qwen_frames": 0, "frames_extracted": 0},
            "memory": [],
            "service_trace": [],
            "diagnostics": {},
        }
    )["intentional_no_vision"]
    print("PASS test_intentional_no_vision_not_aborted")


def test_mock_acceptance_runner():
    r = subprocess.run(
        [VIDEORSI, str(ROOT / "experiment_guard" / "mock_acceptance_runner.py"), "--mode", "both"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "VALID_PATH" in r.stdout
    assert "INVALID_PATH" in r.stdout
    ranking_inv = json.loads((ROOT / "experiment_guard" / "out" / "mock_acceptance" / "invalid" / "architecture_ranking.json").read_text())
    assert ranking_inv["usable"] is False
    print("PASS test_mock_acceptance_runner")


def test_eval_execute_cannot_skip_guard_symbol():
    """Source-level: --execute path references require/GuardedExperiment.start."""
    src = (PILOT / "eval_independent.py").read_text()
    assert "GuardedExperiment" in src
    assert "guard.start" in src
    assert "require_provider_env=True" in src
    src2 = (PILOT / "run_editor_arms.py").read_text()
    assert "GuardedExperiment" in src2
    assert "guard.start" in src2
    print("PASS test_eval_execute_cannot_skip_guard_symbol")


def main() -> int:
    tests = [
        test_eval_independent_dry_run_no_provider,
        test_editor_arms_prepare_only_no_provider,
        test_execute_wrong_python_blocked_via_require_preflight,
        test_concurrent_abort_stops_submitting_remaining,
        test_fingerprint_reread_detects_config_change,
        test_multi_arm_config_mismatch_protocol,
        test_resume_old_results_blocked,
        test_intentional_no_vision_not_aborted,
        test_mock_acceptance_runner,
        test_eval_execute_cannot_skip_guard_symbol,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
        except Exception as exc:
            failed += 1
            print("FAIL", fn.__name__, exc)
    print("e2e failed=%d total=%d" % (failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
