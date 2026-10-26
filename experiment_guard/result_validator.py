"""Layer 3: Result Validation — scientific validity before reporting accuracy."""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from experiment_guard.runtime_guard import classify_item_run


def _ids(results: list[dict]) -> list[str]:
    return [r.get("sample_id") for r in results]


def validate_arm(
    results: list[dict],
    *,
    gold: dict[str, str] | None = None,
    expected_ids: Iterable[str] | None = None,
    arm_name: str = "arm",
    allow_degraded: bool = False,
    expected_config_fingerprint: str | None = None,
    observed_config_fingerprint: str | None = None,
) -> dict[str, Any]:
    assessments = [classify_item_run(r) for r in results]
    valid = [a for a in assessments if a["validity"] == "VALID_RUN"]
    degraded = [a for a in assessments if a["validity"] == "DEGRADED_RUN"]
    invalid = [a for a in assessments if a["validity"] == "INVALID_RUN"]

    reason_codes: list[str] = []
    ids = _ids(results)
    dup = [sid for sid, n in Counter(ids).items() if n > 1]
    if dup:
        reason_codes.append("duplicate_sample_ids")
    if expected_ids is not None:
        exp = list(expected_ids)
        missing = sorted(set(exp) - set(ids))
        extra = sorted(set(ids) - set(exp))
        if missing:
            reason_codes.append("missing_samples")
        if extra:
            reason_codes.append("unexpected_samples")
    else:
        missing, extra = [], []

    if expected_config_fingerprint and observed_config_fingerprint:
        if expected_config_fingerprint != observed_config_fingerprint:
            reason_codes.append("config_fingerprint_mismatch_resume")

    qwen_frames = [int(a["qwen_frames"] or 0) for a in assessments]
    visual_req = sum(a["visual_requests"] for a in assessments)
    visual_ok = sum(a["visual_ok"] for a in assessments)
    visual_success_rate = (visual_ok / visual_req) if visual_req else None

    # Accuracy — architecture-comparable uses VALID only (+ optional DEGRADED)
    comparable = valid + (degraded if allow_degraded else [])
    correct = 0
    if gold is not None:
        for r, a in zip(results, assessments):
            if a["validity"] == "INVALID_RUN":
                continue
            if a["validity"] == "DEGRADED_RUN" and not allow_degraded:
                continue
            if r.get("status") in ("answered", "ok") and r.get("answer") == gold.get(r["sample_id"]):
                correct += 1

    if invalid:
        reason_codes.append("has_invalid_runs")
    if degraded and not allow_degraded:
        reason_codes.append("has_degraded_runs_excluded")

    # Overall for this arm
    if any(c in reason_codes for c in ("config_fingerprint_mismatch_resume",)) or (
        invalid and visual_req > 0 and visual_ok == 0
    ):
        overall = "INVALID"
    elif invalid or (degraded and not allow_degraded) or missing or dup:
        overall = "PARTIALLY_VALID" if valid else "INVALID"
    else:
        overall = "VALID"

    # Phase D style: all vision infra broken → INVALID for architecture claims
    if invalid and len(invalid) == len(assessments) and any(
        "imageio_ffmpeg_missing" in (a.get("reasons") or []) or "visual_tooling_failed" in (a.get("reasons") or [])
        for a in invalid
    ):
        overall = "INVALID"
        if "systematic_vision_infra_failure" not in reason_codes:
            reason_codes.append("systematic_vision_infra_failure")

    naive_correct = 0
    if gold is not None:
        naive_correct = sum(
            1
            for r in results
            if r.get("status") in ("answered", "ok") and r.get("answer") == gold.get(r["sample_id"])
        )

    return {
        "arm": arm_name,
        "overall_validity": overall,
        "reason_codes": reason_codes,
        "n": len(assessments),
        "n_valid_run": len(valid),
        "n_degraded_run": len(degraded),
        "n_invalid_run": len(invalid),
        "n_intentional_no_vision_among_valid": sum(1 for a in valid if a["intentional_no_vision"]),
        "duplicates": dup,
        "missing_samples": missing,
        "unexpected_samples": extra,
        "visual_success_rate": visual_success_rate,
        "qwen_frames": {
            "mean": (sum(qwen_frames) / len(qwen_frames)) if qwen_frames else None,
            "min": min(qwen_frames) if qwen_frames else None,
            "max": max(qwen_frames) if qwen_frames else None,
            "total": sum(qwen_frames),
        },
        "architecture_comparable": {
            "n": len(comparable),
            "correct": correct if gold is not None else None,
            "accuracy": (correct / len(comparable)) if (gold is not None and comparable) else None,
            "excluded_invalid": len(invalid),
            "excluded_degraded": 0 if allow_degraded else len(degraded),
        },
        "naive_including_invalid": {
            "n": len(results),
            "correct": naive_correct if gold is not None else None,
            "accuracy": (naive_correct / len(results)) if (gold is not None and results) else None,
            "warning": "Do not use for architecture claims if overall_validity != VALID",
        },
        "assessments": assessments,
        "usable_for_architecture_ranking": overall == "VALID",
    }


def validate_multi_arm(
    arms: dict[str, list[dict]],
    *,
    gold: dict[str, str] | None = None,
    expected_ids: Iterable[str] | None = None,
    require_same_ids: bool = True,
    allow_degraded: bool = False,
    claimed_matched_frames: bool = False,
    arm_fingerprints: dict[str, str] | None = None,
    vision_required_arms: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Cross-arm protocol + validity for architecture comparisons."""
    per_arm = {
        name: validate_arm(
            rows,
            gold=gold,
            expected_ids=expected_ids,
            arm_name=name,
            allow_degraded=allow_degraded,
            observed_config_fingerprint=(arm_fingerprints or {}).get(name),
            expected_config_fingerprint=(arm_fingerprints or {}).get("__expected__"),
        )
        for name, rows in arms.items()
    }
    reason_codes: list[str] = []

    id_sets = {name: set(_ids(rows)) for name, rows in arms.items()}
    if require_same_ids and len(id_sets) >= 2:
        ref = next(iter(id_sets.values()))
        for name, s in id_sets.items():
            if s != ref:
                reason_codes.append("arm_sample_set_mismatch:%s" % name)

    vision_required = set(vision_required_arms or [])
    for name in vision_required:
        arm = per_arm.get(name)
        if not arm:
            reason_codes.append("missing_vision_required_arm:%s" % name)
            continue
        # Lost vision due to infra
        if arm["n_invalid_run"] and arm["qwen_frames"]["total"] == 0 and arm["n_valid_run"] == 0:
            reason_codes.append("arm_lost_vision:%s" % name)
        if arm["overall_validity"] == "INVALID":
            reason_codes.append("arm_invalid:%s" % name)

    # Matched-frame claim (only if experiment asserts it)
    if claimed_matched_frames:
        means = {
            name: (arm["qwen_frames"]["mean"] or 0)
            for name, arm in per_arm.items()
        }
        vals = list(means.values())
        if vals and (max(vals) - min(vals)) > 1e-6:
            # Different budgets OK for architecture compare unless claimed matched
            reason_codes.append("claimed_matched_frames_but_means_differ")

    arm_overalls = [a["overall_validity"] for a in per_arm.values()]
    if any(o == "INVALID" for o in arm_overalls) or any(c.startswith("arm_lost_vision") for c in reason_codes):
        overall = "INVALID"
    elif any(o == "PARTIALLY_VALID" for o in arm_overalls) or reason_codes:
        overall = "PARTIALLY_VALID"
    else:
        overall = "VALID"

    # Aggregate reason codes from arms
    for a in per_arm.values():
        for rc in a["reason_codes"]:
            tagged = "%s:%s" % (a["arm"], rc)
            if tagged not in reason_codes:
                reason_codes.append(tagged)

    return {
        "overall_validity": overall,
        "reason_codes": reason_codes,
        "arms": per_arm,
        "usable_for_architecture_ranking": overall == "VALID",
        "note": (
            "Different arms may use different visual budgets; only matched-frame claims "
            "require identical frame sets. All arms must run in a healthy environment."
        ),
    }
