#!/usr/bin/env python3
"""Offline tests for Direct VQA Guard coverage + historical data protection (0 API)."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research_audit" / "arch_evolution_min_preflight"))
sys.path.insert(0, str(ROOT / "research_audit" / "arch_self_evolution_pilot"))

from experiment_guard import GuardedExperiment, PreflightCapabilities, classify_item_run, validate_multi_arm
from experiment_guard.direct_vqa_audit import (
    assess_direct_vqa_reuse,
    expected_direct_meta,
    normalize_direct_vqa_record,
)
from experiment_guard.fingerprints import config_fingerprint, harness_fingerprint
from experiment_guard.preflight import load_config

PILOT = ROOT / "research_audit" / "arch_self_evolution_pilot"
SEED = ROOT / "evolution" / "run-seed42" / "versions" / "initial_harness"
FROZEN_SAFE = PILOT / "out" / "phase_d_eval.safe.json"
FROZEN_RUN = PILOT / "runs" / "phase_d_eval_v1"


def _healthy_initial(sid, ans="A"):
    return {
        "sample_id": sid,
        "status": "answered",
        "answer": ans,
        "usage": {"qwen_frames": 8, "frames_extracted": 8, "deepseek_calls": 2},
        "memory": [{"tool": "overview", "observation": {"text": "ok", "frames": ["f1"]}}],
        "service_trace": [{"service": "qwen"}],
        "diagnostics": {},
    }


def _broken_initial(sid):
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


def _ok_direct_rec(sid, n=32, ans="A"):
    return {
        "sample_id": sid,
        "path": "DirectVQA",
        "stage": "answer",
        "status": "ok",
        "answer": ans,
        "n_frames": n,
        "timestamps": [float(i) for i in range(n)],
        "frame_bundle_sha": "bundle_%s" % sid,
        "frame_path_hashes": ["h%d" % i for i in range(n)],
        "prompt_sha": "sha_%s" % sid,
        "prompt_version": "infoflow_vqa_letter_json_v1",
        "request_model": "mock-qwen",
        "config_fingerprint": "cfg",
        "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        "error": "",
    }


def test_normalize_preserves_real_evidence_not_fake_frames():
    bad = {"sample_id": "x", "status": "ok", "answer": "A", "n_frames": 0, "error": ""}
    g = normalize_direct_vqa_record(bad)
    assert g["usage"]["qwen_frames"] == 0
    assert classify_item_run(g)["validity"] == "INVALID_RUN"
    ok = normalize_direct_vqa_record(_ok_direct_rec("y", n=4))
    assert ok["usage"]["qwen_frames"] == 4
    assert classify_item_run(ok)["validity"] == "VALID_RUN"
    print("PASS test_normalize_preserves_real_evidence_not_fake_frames")


def test_ranking_blocked_when_direct_invalid_initial_valid():
    ids = ["s1", "s2"]
    initial = [_healthy_initial(s) for s in ids]
    direct = [
        normalize_direct_vqa_record(
            {
                "sample_id": s,
                "status": "provider_error",
                "answer": None,
                "n_frames": 0,
                "error": "timeout",
                "timestamps": [],
            }
        )
        for s in ids
    ]
    m = validate_multi_arm(
        {"initial": initial, "direct_vqa": direct},
        gold={s: "A" for s in ids},
        expected_ids=ids,
        vision_required_arms=["initial", "direct_vqa"],
    )
    assert m["overall_validity"] == "INVALID"
    assert m["usable_for_architecture_ranking"] is False
    print("PASS test_ranking_blocked_when_direct_invalid_initial_valid")


def test_ranking_blocked_when_initial_invalid_direct_valid():
    ids = ["s1", "s2"]
    initial = [_broken_initial(s) for s in ids]
    direct = [normalize_direct_vqa_record(_ok_direct_rec(s, n=8)) for s in ids]
    m = validate_multi_arm(
        {"initial": initial, "direct_vqa": direct},
        gold={s: "A" for s in ids},
        expected_ids=ids,
        vision_required_arms=["initial", "direct_vqa"],
    )
    assert m["overall_validity"] == "INVALID"
    assert m["usable_for_architecture_ranking"] is False
    print("PASS test_ranking_blocked_when_initial_invalid_direct_valid")


def test_ranking_ok_when_both_valid():
    ids = ["s1", "s2"]
    initial = [_healthy_initial(s) for s in ids]
    direct = [normalize_direct_vqa_record(_ok_direct_rec(s, n=8, ans="A")) for s in ids]
    m = validate_multi_arm(
        {"initial": initial, "direct_vqa": direct},
        gold={s: "A" for s in ids},
        expected_ids=ids,
        vision_required_arms=["initial", "direct_vqa"],
        require_same_ids=True,
    )
    assert m["overall_validity"] == "VALID", m
    assert m["usable_for_architecture_ranking"] is True
    print("PASS test_ranking_ok_when_both_valid")


def test_direct_provider_failure_stops_remaining():
    import eval_independent as ei

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        run_dir = td / "run"
        cfg = load_config()
        ids = ["a", "b", "c", "d"]
        items = {
            s: {
                "sample_id": s,
                "question": "q",
                "options": {"A": "a", "B": "b"},
                "duration": 10.0,
                "video_path": str(td / "missing.mp4"),
            }
            for s in ids
        }
        gold = {s: "A" for s in ids}
        cache = {}

        class FailProvider:
            def chat(self, role, messages, frames=0, request_model=""):
                from infoflow_lib import ProviderResponse

                return ProviderResponse(
                    status="error",
                    text="",
                    usage={},
                    frames=frames,
                    role=role,
                    request_model=request_model or "mock",
                    error="injected_provider_failure",
                    latency_seconds=0.01,
                )

        def fake_extract(video, timestamps, out_dir, config):
            out_dir = Path(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            paths = []
            for i, _ts in enumerate(timestamps):
                p = out_dir / ("f%d.jpg" % i)
                p.write_bytes(b"\xff\xd8\xff\xd9")
                paths.append(p)
            return paths

        guard = GuardedExperiment(
            experiment_id="direct_fail",
            out_dir=run_dir / "guard",
            capabilities=PreflightCapabilities(
                visual_sample_frames=False,
                host_must_match_config_python=False,
                provider_config=False,
            ),
            formal_protocol=False,
        )
        guard.start_soft(reexec=False, config=cfg)

        orig = ei.extract_frames
        ei.extract_frames = fake_extract
        try:
            summary, results, stats = ei.run_direct_vqa(
                ids,
                items,
                gold,
                cache,
                cfg,
                FailProvider(),
                run_dir,
                guard=guard,
                cfg_fp="cfg",
                harness_sha="h",
            )
        finally:
            ei.extract_frames = orig

        assert stats["aborted"] is True
        assert len(results) < len(ids), "must stop before finishing all ids: %d" % len(results)
        print("PASS test_direct_provider_failure_stops_remaining n=%d" % len(results))


def test_direct_provider_exception_preserves_diagnosis_and_stops():
    import eval_independent as ei

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        run_dir = td / "run"
        cfg = load_config()
        ids = ["a", "b", "c"]
        items = {
            s: {
                "sample_id": s,
                "question": "q",
                "options": {"A": "a", "B": "b"},
                "duration": 10.0,
                "video_path": str(td / "x.mp4"),
            }
            for s in ids
        }
        gold = {s: "A" for s in ids}

        class BoomProvider:
            def chat(self, *a, **k):
                raise RuntimeError("network_boom")

        def fake_extract(video, timestamps, out_dir, config):
            out_dir = Path(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            paths = []
            for i, _ts in enumerate(timestamps):
                p = out_dir / ("f%d.jpg" % i)
                p.write_bytes(b"\xff\xd8\xff\xd9")
                paths.append(p)
            return paths

        guard = GuardedExperiment(
            experiment_id="direct_exc",
            out_dir=run_dir / "guard",
            capabilities=PreflightCapabilities(
                visual_sample_frames=False,
                host_must_match_config_python=False,
                provider_config=False,
            ),
            formal_protocol=False,
        )
        guard.start_soft(reexec=False, config=cfg)
        orig = ei.extract_frames
        ei.extract_frames = fake_extract
        try:
            _s, results, stats = ei.run_direct_vqa(
                ids, items, gold, {}, cfg, BoomProvider(), run_dir, guard=guard, cfg_fp="cfg", harness_sha="h"
            )
        finally:
            ei.extract_frames = orig
        assert stats["aborted"] is True
        assert len(results) == 1
        assert "ProviderException" in (results[0].get("direct_vqa_record") or {}).get("error", "")
        assert results[0]["status"] == "provider_error"
        print("PASS test_direct_provider_exception_preserves_diagnosis_and_stops")


def test_resume_rejects_incompatible():
    expected = expected_direct_meta(
        sample_id="s1",
        prompt_sha="new_sha",
        prompt_version="infoflow_vqa_letter_json_v1",
        request_model="mock-qwen",
        timestamps=[1.0, 2.0],
        config_fingerprint="cfg_new",
    )
    old = {
        "status": "ok",
        "n_frames": 2,
        "prompt_sha": "old_sha",
        "prompt_version": "infoflow_vqa_letter_json_v1",
        "request_model": "mock-qwen",
        "timestamps": [1.0, 2.0],
    }
    v = assess_direct_vqa_reuse(old, expected)
    assert v["compatible"] is False
    assert "prompt_sha_mismatch" in v["reasons"]
    # status=ok alone insufficient
    v2 = assess_direct_vqa_reuse({"status": "ok", "n_frames": 2}, expected)
    assert v2["compatible"] is False
    print("PASS test_resume_rejects_incompatible")


def test_resume_rejects_missing_timestamps_no_inference():
    expected = expected_direct_meta(
        sample_id="s1",
        prompt_sha="sha",
        prompt_version="infoflow_vqa_letter_json_v1",
        request_model="Qwen3.6-Plus",
        timestamps=[1.0] * 32,
        config_fingerprint="cfg",
    )
    # Legacy Phase D shape: no timestamps — must NOT infer from prompt_sha + n_frames
    legacy = {
        "status": "ok",
        "n_frames": 32,
        "prompt_sha": "sha",
        "prompt_version": "infoflow_vqa_letter_json_v1",
        "request_model": "Qwen3.6-Plus",
    }
    v = assess_direct_vqa_reuse(legacy, expected)
    assert v["compatible"] is False
    assert "timestamps_missing_cannot_infer" in v["reasons"]
    # Full meta with matching timestamps still OK
    full = dict(legacy)
    full["timestamps"] = [1.0] * 32
    v2 = assess_direct_vqa_reuse(full, expected)
    assert v2["compatible"] is True
    print("PASS test_resume_rejects_missing_timestamps_no_inference")


def test_frozen_phase_d_files_untouched_and_run_dir_blocked():
    import eval_independent as ei

    before = FROZEN_SAFE.read_bytes() if FROZEN_SAFE.is_file() else None
    mtime = FROZEN_SAFE.stat().st_mtime_ns if FROZEN_SAFE.is_file() else None

    try:
        ei.assert_run_dir_safe(FROZEN_RUN)
        raise AssertionError("should have refused frozen run dir")
    except SystemExit as exc:
        assert "REFUSING" in str(exc)

    # Simulate writing safe only under new dir
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td) / "phase_d_eval_guarded_test"
        run_dir.mkdir()
        safe = {"n": 0, "note": "test"}
        from solver_full_workspace.engine.common import write_json

        write_json(run_dir / "phase_d_eval.safe.json", safe)
        assert (run_dir / "phase_d_eval.safe.json").is_file()

    if before is not None:
        assert FROZEN_SAFE.read_bytes() == before
        assert FROZEN_SAFE.stat().st_mtime_ns == mtime
    print("PASS test_frozen_phase_d_files_untouched_and_run_dir_blocked")


def test_both_arms_enter_guard_finalize_limit4_shape():
    """Simulate --arms initial,direct_vqa --limit 4 both in multi_arms."""
    ids = ["lvbench_%d" % i for i in range(4)]
    initial = [_healthy_initial(s) for s in ids]
    direct = [normalize_direct_vqa_record(_ok_direct_rec(s, n=8)) for s in ids]
    cfg = load_config()
    with tempfile.TemporaryDirectory() as td:
        guard = GuardedExperiment(
            experiment_id="limit4",
            out_dir=Path(td) / "guard",
            capabilities=PreflightCapabilities(
                visual_sample_frames=False,
                host_must_match_config_python=False,
                provider_config=False,
            ),
            formal_protocol=True,
        )
        guard.start_soft(reexec=False, config=cfg)
        for r in initial:
            guard.observe(r)
        health = guard.finalize(
            initial,
            gold={s: "A" for s in ids},
            expected_ids=ids,
            multi_arms={"initial": initial, "direct_vqa": direct},
            protocol_kwargs={
                "formal": True,
                "eval_ids": ids,
                "train_ids": ["t"],
                "gate_ids": ["g"],
                "editor_subset_ids": [],
                "arm_ids": {"initial": ids, "direct_vqa": ids},
                "arm_config_fingerprints": {
                    "initial": config_fingerprint(cfg),
                    "direct_vqa": config_fingerprint(cfg),
                },
                "arm_harness_fingerprints": {
                    "initial": harness_fingerprint(SEED).get("sha16"),
                    "direct_vqa": "direct_vqa_fixed32_or_overview_bundle",
                },
                "cache_reuse_allowed": False,
            },
        )
        multi = json.loads((Path(td) / "guard" / "multi_arm_validation.json").read_text())
        assert set(multi["arms"].keys()) == {"initial", "direct_vqa"}
        assert multi["arms"]["direct_vqa"]["n"] == 4
        assert multi["arms"]["initial"]["n"] == 4
        assert health.get("usable_for_architecture_ranking") is True
        print("PASS test_both_arms_enter_guard_finalize_limit4_shape")


def test_dry_run_mentions_new_default_run_dir():
    import subprocess

    r = subprocess.run(
        [sys.executable, str(PILOT / "eval_independent.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "phase_d_eval_guarded_v1" in data.get("default_run_dir", "")
    assert "phase_d_eval_v1" in data.get("frozen_run_dir_blocked", "")
    print("PASS test_dry_run_mentions_new_default_run_dir")


def main() -> int:
    tests = [
        test_normalize_preserves_real_evidence_not_fake_frames,
        test_ranking_blocked_when_direct_invalid_initial_valid,
        test_ranking_blocked_when_initial_invalid_direct_valid,
        test_ranking_ok_when_both_valid,
        test_direct_provider_failure_stops_remaining,
        test_direct_provider_exception_preserves_diagnosis_and_stops,
        test_resume_rejects_incompatible,
        test_resume_rejects_missing_timestamps_no_inference,
        test_frozen_phase_d_files_untouched_and_run_dir_blocked,
        test_both_arms_enter_guard_finalize_limit4_shape,
        test_dry_run_mentions_new_default_run_dir,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
        except Exception as exc:
            failed += 1
            print("FAIL", fn.__name__, exc)
    print("direct_vqa_patch failed=%d total=%d" % (failed, len(tests)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
