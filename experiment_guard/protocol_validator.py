"""Protocol checks: frozen IDs, leakage, resume contamination, cache reuse, matched frames.

Formal experiments must explicitly declare required fields. Missing declarations yield
INCOMPLETE — never a silent PASS.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from experiment_guard.fingerprint_snapshot import frame_bundle_hash


# Checks that a formal architecture comparison must explicitly satisfy (PASS),
# not leave as NOT_APPLICABLE due to omitted kwargs.
FORMAL_REQUIRED_CHECKS = (
    "frozen_eval_ids_declared",
    "train_eval_isolation",
    "gate_eval_isolation",
    "arm_config_fingerprints",
    "arm_harness_fingerprints",
    "resume_cache_protocol",
)


def validate_protocol(
    *,
    formal: bool = False,
    eval_ids: Iterable[str] | None = None,
    train_ids: Iterable[str] | None = None,
    gate_ids: Iterable[str] | None = None,
    editor_subset_ids: Iterable[str] | None = None,
    arm_ids: dict[str, Iterable[str]] | None = None,
    arm_config_fingerprints: dict[str, str] | None = None,
    arm_harness_fingerprints: dict[str, str] | None = None,
    resume_results_path: Path | None = None,
    expected_config_fingerprint: str | None = None,
    observed_config_fingerprint: str | None = None,
    cache_reuse_allowed: bool | None = None,
    cache_source: str | None = None,
    cache_compatible: bool | None = None,
    harness_sha_expected: str | None = None,
    harness_sha_observed: str | None = None,
    claimed_matched_frames: bool = False,
    frame_bundles_by_arm: dict[str, dict[str, dict]] | None = None,
) -> dict[str, Any]:
    """Validate experiment protocol.

    Returns status: PASS | FAIL | INCOMPLETE
    INCOMPLETE = required formal fields were not supplied (cannot claim full protocol pass).
    """
    reason_codes: list[str] = []
    checks: list[dict] = []

    eval_set = set(eval_ids) if eval_ids is not None else None
    train_set = set(train_ids) if train_ids is not None else None
    gate_set = set(gate_ids) if gate_ids is not None else None
    editor_set = set(editor_subset_ids) if editor_subset_ids is not None else None

    # --- frozen eval IDs declared ---
    if eval_set is not None:
        checks.append(
            {
                "name": "frozen_eval_ids_declared",
                "status": "PASS" if len(eval_set) > 0 else "FAIL",
                "n": len(eval_set),
            }
        )
        if not eval_set:
            reason_codes.append("empty_eval_ids")
    else:
        checks.append({"name": "frozen_eval_ids_declared", "status": "NOT_APPLICABLE", "missing": "eval_ids"})

    # --- isolation ---
    if eval_set is not None and train_set is not None:
        leak = sorted(eval_set & train_set)
        checks.append({"name": "train_eval_isolation", "status": "FAIL" if leak else "PASS", "n_leak": len(leak)})
        if leak:
            reason_codes.append("train_eval_leak")
    else:
        checks.append(
            {
                "name": "train_eval_isolation",
                "status": "NOT_APPLICABLE",
                "missing": [k for k, v in (("eval_ids", eval_set), ("train_ids", train_set)) if v is None],
            }
        )

    if eval_set is not None and gate_set is not None:
        leak = sorted(eval_set & gate_set)
        checks.append({"name": "gate_eval_isolation", "status": "FAIL" if leak else "PASS", "n_leak": len(leak)})
        if leak:
            reason_codes.append("gate_eval_leak")
    else:
        checks.append(
            {
                "name": "gate_eval_isolation",
                "status": "NOT_APPLICABLE",
                "missing": [k for k, v in (("eval_ids", eval_set), ("gate_ids", gate_set)) if v is None],
            }
        )

    if eval_set is not None and editor_set is not None:
        leak = sorted(eval_set & editor_set)
        checks.append({"name": "editor_eval_isolation", "status": "FAIL" if leak else "PASS", "n_leak": len(leak)})
        if leak:
            reason_codes.append("editor_eval_leak")
    else:
        checks.append({"name": "editor_eval_isolation", "status": "NOT_APPLICABLE"})

    if arm_ids:
        sets = {k: set(v) for k, v in arm_ids.items()}
        ref_name, ref = next(iter(sets.items()))
        mismatch = False
        for name, s in sets.items():
            if s != ref:
                mismatch = True
                reason_codes.append("arm_id_mismatch:%s_vs_%s" % (name, ref_name))
        checks.append({"name": "arm_same_eval_ids", "status": "FAIL" if mismatch else "PASS"})
    else:
        checks.append({"name": "arm_same_eval_ids", "status": "NOT_APPLICABLE", "missing": "arm_ids"})

    # --- arm fingerprints (must be explicit for formal) ---
    if arm_config_fingerprints:
        vals = list(arm_config_fingerprints.values())
        ok = all(vals) and len(set(vals)) >= 1
        # Different arms MAY share config; empty values fail
        if any(not v for v in vals):
            reason_codes.append("arm_config_fingerprint_empty")
            checks.append({"name": "arm_config_fingerprints", "status": "FAIL", "fingerprints": arm_config_fingerprints})
        else:
            checks.append({"name": "arm_config_fingerprints", "status": "PASS", "fingerprints": arm_config_fingerprints})
    else:
        checks.append({"name": "arm_config_fingerprints", "status": "NOT_APPLICABLE", "missing": "arm_config_fingerprints"})

    if arm_harness_fingerprints:
        if any(not v for v in arm_harness_fingerprints.values()):
            reason_codes.append("arm_harness_fingerprint_empty")
            checks.append({"name": "arm_harness_fingerprints", "status": "FAIL", "fingerprints": arm_harness_fingerprints})
        else:
            checks.append({"name": "arm_harness_fingerprints", "status": "PASS", "fingerprints": arm_harness_fingerprints})
    else:
        checks.append({"name": "arm_harness_fingerprints", "status": "NOT_APPLICABLE", "missing": "arm_harness_fingerprints"})

    # --- resume / cache protocol must be declared for formal ---
    if cache_reuse_allowed is None and resume_results_path is None and expected_config_fingerprint is None:
        checks.append(
            {
                "name": "resume_cache_protocol",
                "status": "NOT_APPLICABLE",
                "missing": "cache_reuse_allowed|resume_results_path|expected_config_fingerprint",
            }
        )
    else:
        resume_ok = True
        if resume_results_path is not None and Path(resume_results_path).is_file():
            if not expected_config_fingerprint or not observed_config_fingerprint:
                resume_ok = False
                reason_codes.append("resume_without_complete_fingerprints")
            elif expected_config_fingerprint != observed_config_fingerprint:
                resume_ok = False
                reason_codes.append("resume_config_fingerprint_mismatch")
        if cache_reuse_allowed is True:
            if cache_compatible is False:
                resume_ok = False
                reason_codes.append("incompatible_cache_reuse")
            elif cache_compatible is None:
                resume_ok = False
                reason_codes.append("cache_reuse_unverified")
        elif cache_reuse_allowed is False and cache_source:
            resume_ok = False
            reason_codes.append("cache_reuse_not_allowed_but_source_present")
        checks.append(
            {
                "name": "resume_cache_protocol",
                "status": "PASS" if resume_ok else "FAIL",
                "cache_reuse_allowed": cache_reuse_allowed,
                "cache_source": cache_source,
                "cache_compatible": cache_compatible,
            }
        )

    # legacy single harness pair (optional extra)
    if harness_sha_expected and harness_sha_observed:
        if harness_sha_expected != harness_sha_observed:
            reason_codes.append("harness_sha_mismatch")
            checks.append({"name": "harness_version", "status": "FAIL"})
        else:
            checks.append({"name": "harness_version", "status": "PASS"})
    else:
        checks.append({"name": "harness_version", "status": "NOT_APPLICABLE"})

    # --- matched-frame: per-item timestamps + bundle hash ---
    if claimed_matched_frames:
        if not frame_bundles_by_arm or len(frame_bundles_by_arm) < 2:
            reason_codes.append("matched_frames_claim_without_bundles")
            checks.append({"name": "matched_frames", "status": "FAIL"})
        else:
            arm_names = list(frame_bundles_by_arm.keys())
            ref = frame_bundles_by_arm[arm_names[0]]
            mismatches = []
            for aname in arm_names[1:]:
                other = frame_bundles_by_arm[aname]
                for sid, bundle in ref.items():
                    ob = other.get(sid)
                    if ob is None:
                        mismatches.append({"sample_id": sid, "reason": "missing_in_%s" % aname})
                        continue
                    ts_a = [float(x) for x in bundle.get("timestamps") or []]
                    ts_b = [float(x) for x in ob.get("timestamps") or []]
                    if ts_a != ts_b:
                        mismatches.append({"sample_id": sid, "reason": "timestamp_mismatch", "arms": [arm_names[0], aname]})
                        continue
                    ha = bundle.get("bundle_hash") or frame_bundle_hash(ts_a)
                    hb = ob.get("bundle_hash") or frame_bundle_hash(ts_b)
                    if ha != hb:
                        mismatches.append({"sample_id": sid, "reason": "bundle_hash_mismatch", "arms": [arm_names[0], aname]})
            checks.append(
                {
                    "name": "matched_frames",
                    "status": "FAIL" if mismatches else "PASS",
                    "n_mismatches": len(mismatches),
                    "mismatches_head": mismatches[:10],
                }
            )
            if mismatches:
                reason_codes.append("matched_frames_per_item_mismatch")
    else:
        checks.append({"name": "matched_frames", "status": "NOT_APPLICABLE", "note": "no matched-frame claim"})

    by_name = {c["name"]: c for c in checks}
    incomplete = False
    if formal:
        for req in FORMAL_REQUIRED_CHECKS:
            c = by_name.get(req)
            if c is None or c["status"] == "NOT_APPLICABLE":
                incomplete = True
                reason_codes.append("protocol_incomplete:%s" % req)
            elif c["status"] == "FAIL":
                reason_codes.append("protocol_fail:%s" % req)

    if any(c["status"] == "FAIL" for c in checks) or any(
        r.startswith("protocol_fail") or r in (
            "train_eval_leak",
            "gate_eval_leak",
            "editor_eval_leak",
            "resume_config_fingerprint_mismatch",
            "incompatible_cache_reuse",
            "matched_frames_per_item_mismatch",
            "matched_frames_claim_without_bundles",
        )
        for r in reason_codes
    ):
        # strip incomplete-only if we already FAIL for substance — still keep codes
        status = "FAIL"
    elif incomplete or (formal and any(r.startswith("protocol_incomplete") for r in reason_codes)):
        status = "INCOMPLETE"
    else:
        status = "PASS"

    # de-dupe reason codes
    seen = set()
    uniq = []
    for r in reason_codes:
        if r not in seen:
            seen.add(r)
            uniq.append(r)

    return {
        "status": status,
        "formal": formal,
        "reason_codes": uniq,
        "checks": checks,
        "usable_for_architecture_ranking": status == "PASS",
        "note": (
            "INCOMPLETE means required formal protocol fields were not declared — "
            "this is not a silent PASS."
            if status == "INCOMPLETE"
            else None
        ),
    }


def load_id_list(path: Path, key: str = "sample_ids") -> list[str]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return list(data)
    return list(data[key])
