#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiment_guard.protocol_validator import validate_protocol


def test_leak_detection():
    v = validate_protocol(eval_ids=["a", "b"], train_ids=["b", "c"], gate_ids=["d"])
    assert v["status"] == "FAIL"
    assert "train_eval_leak" in v["reason_codes"]
    print("PASS test_leak_detection")


def test_arm_id_mismatch():
    v = validate_protocol(arm_ids={"initial": ["a", "b"], "direct": ["a", "c"]})
    assert v["status"] == "FAIL"
    assert any("arm_id_mismatch" in c for c in v["reason_codes"])
    print("PASS test_arm_id_mismatch")


def test_resume_fingerprint_mismatch():
    p = ROOT / "experiment_guard" / "out" / "_fake_resume.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}\n")
    v = validate_protocol(
        resume_results_path=p,
        expected_config_fingerprint="aaa",
        observed_config_fingerprint="bbb",
    )
    assert v["status"] == "FAIL"
    assert "resume_config_fingerprint_mismatch" in v["reason_codes"]
    print("PASS test_resume_fingerprint_mismatch")


def test_incompatible_cache_reuse():
    v = validate_protocol(cache_reuse_allowed=True, cache_source="phase_d", cache_compatible=False)
    assert v["status"] == "FAIL"
    assert "incompatible_cache_reuse" in v["reason_codes"]
    print("PASS test_incompatible_cache_reuse")


def test_clean_protocol():
    v = validate_protocol(
        eval_ids=["a", "b"],
        train_ids=["c"],
        gate_ids=["d"],
        editor_subset_ids=["e"],
        arm_ids={"initial": ["a", "b"], "direct": ["a", "b"]},
        cache_reuse_allowed=True,
        cache_source="direct_vqa",
        cache_compatible=True,
        harness_sha_expected="x",
        harness_sha_observed="x",
    )
    assert v["status"] == "PASS"
    print("PASS test_clean_protocol")


def main() -> int:
    failed = 0
    for fn in (
        test_leak_detection,
        test_arm_id_mismatch,
        test_resume_fingerprint_mismatch,
        test_incompatible_cache_reuse,
        test_clean_protocol,
    ):
        try:
            fn()
        except Exception as e:
            failed += 1
            print("FAIL", fn.__name__, e)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
