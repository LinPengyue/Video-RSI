#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiment_guard.protocol_validator import validate_protocol


def test_leak_detection():
    v = validate_protocol(formal=False, eval_ids=["a", "b"], train_ids=["b", "c"], gate_ids=["d"])
    assert v["status"] == "FAIL"
    assert "train_eval_leak" in v["reason_codes"]
    print("PASS test_leak_detection")


def test_arm_id_mismatch():
    v = validate_protocol(formal=False, arm_ids={"initial": ["a", "b"], "direct": ["a", "c"]})
    assert v["status"] == "FAIL"
    assert any("arm_id_mismatch" in c for c in v["reason_codes"])
    print("PASS test_arm_id_mismatch")


def test_resume_fingerprint_mismatch():
    p = ROOT / "experiment_guard" / "out" / "_fake_resume.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}\n")
    v = validate_protocol(
        formal=False,
        resume_results_path=p,
        expected_config_fingerprint="aaa",
        observed_config_fingerprint="bbb",
        cache_reuse_allowed=False,
    )
    assert v["status"] == "FAIL"
    assert "resume_config_fingerprint_mismatch" in v["reason_codes"]
    print("PASS test_resume_fingerprint_mismatch")


def test_incompatible_cache_reuse():
    v = validate_protocol(formal=False, cache_reuse_allowed=True, cache_source="phase_d", cache_compatible=False)
    assert v["status"] == "FAIL"
    assert "incompatible_cache_reuse" in v["reason_codes"]
    print("PASS test_incompatible_cache_reuse")


def test_formal_incomplete_not_pass():
    """Missing formal declarations must be INCOMPLETE, never silent PASS."""
    v = validate_protocol(formal=True)
    assert v["status"] == "INCOMPLETE"
    assert v["usable_for_architecture_ranking"] is False
    assert any(c.startswith("protocol_incomplete") for c in v["reason_codes"])
    print("PASS test_formal_incomplete_not_pass")


def test_clean_formal_protocol():
    v = validate_protocol(
        formal=True,
        eval_ids=["a", "b"],
        train_ids=["c"],
        gate_ids=["d"],
        editor_subset_ids=["e"],
        arm_ids={"initial": ["a", "b"], "direct": ["a", "b"]},
        arm_config_fingerprints={"initial": "cfg1", "direct": "cfg1"},
        arm_harness_fingerprints={"initial": "h1", "direct": "h1"},
        cache_reuse_allowed=True,
        cache_source="direct_vqa",
        cache_compatible=True,
        harness_sha_expected="x",
        harness_sha_observed="x",
    )
    assert v["status"] == "PASS", v
    assert v["usable_for_architecture_ranking"] is True
    print("PASS test_clean_formal_protocol")


def test_matched_frames_per_item():
    bundles = {
        "initial": {"s1": {"timestamps": [1.0, 2.0], "bundle_hash": "aaa"}},
        "direct": {"s1": {"timestamps": [1.0, 3.0], "bundle_hash": "aaa"}},
    }
    v = validate_protocol(
        formal=False,
        claimed_matched_frames=True,
        frame_bundles_by_arm=bundles,
        cache_reuse_allowed=False,
    )
    assert v["status"] == "FAIL"
    assert "matched_frames_per_item_mismatch" in v["reason_codes"]
    print("PASS test_matched_frames_per_item")


def main() -> int:
    failed = 0
    for fn in (
        test_leak_detection,
        test_arm_id_mismatch,
        test_resume_fingerprint_mismatch,
        test_incompatible_cache_reuse,
        test_formal_incomplete_not_pass,
        test_clean_formal_protocol,
        test_matched_frames_per_item,
    ):
        try:
            fn()
        except Exception as e:
            failed += 1
            print("FAIL", fn.__name__, e)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
