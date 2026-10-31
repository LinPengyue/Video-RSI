"""B5 — cheap auto triage with calibrated honest labels (V2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _proxy_blind_answer(qa: dict[str, Any], side: str) -> dict[str, Any]:
    """Rule heuristic only — NOT a video model blind answer."""
    mech = qa.get("mechanism")
    ans = qa.get("provisional_answer_zh") or qa.get("normalized_answer")
    note = "RULE_PROXY_NOT_VIDEO_TESTED"
    if side == "B":
        if mech == "reverse_name_to_early_garment":
            return {"answer": None, "confidence": 0.2, "note": note}
        if mech == "ordered_state_transitions":
            return {"answer": "may_read_final_and_infer_prior", "confidence": 0.55, "note": note}
        if mech == "heat_boundary_name_contrast":
            return {"answer": "late_name_only", "confidence": 0.7, "note": note}
        return {"answer": None, "confidence": 0.3, "note": note}
    if side == "A":
        if mech == "reverse_name_to_early_garment":
            return {"answer": ans, "confidence": 0.4, "note": note}
        if mech == "ordered_state_transitions":
            return {"answer": "first_transition_only", "confidence": 0.6, "note": note}
        if mech == "heat_boundary_name_contrast":
            return {"answer": "early_name_only", "confidence": 0.7, "note": note}
        return {"answer": None, "confidence": 0.3, "note": note}
    return {"answer": ans, "confidence": 0.65, "note": note}


def screen_one(qa: dict[str, Any], events_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    risks: list[str] = []

    for fid in qa.get("fact_ids") or []:
        ev = events_by_id.get(fid)
        if not ev:
            errors.append(f"missing_fact:{fid}")
            continue
        if ev["time_end_s"] < ev["time_start_s"]:
            errors.append(f"illegal_time:{fid}")
        for p in ev.get("evidence_paths") or []:
            if p and not Path(p).exists() and not Path("/home/descfly/lpy/Video-RSI/" + p).exists():
                risks.append(f"evidence_path_missing:{p}")

    if qa.get("duplicate_of_family"):
        risks.append("duplicate_evidence_family")
    if qa.get("generation_error"):
        errors.append("generation_error:" + ",".join((qa.get("fact_binding") or {}).get("errors") or ["unspecified"]))
    if qa.get("leakage_error"):
        errors.append("question_side_semantic_leakage")
    binding = qa.get("fact_binding") or {}
    if binding.get("binding_status") == "QUARANTINE_BINDING_ERROR":
        errors.append("fact_binding_quarantine")

    a_proxy = _proxy_blind_answer(qa, "A")
    b_proxy = _proxy_blind_answer(qa, "B")
    ab_proxy = _proxy_blind_answer(qa, "AB")

    if qa.get("mechanism") == "ordered_state_transitions":
        risks.append("possible_B_only_order_leak")
    if qa.get("mechanism") == "heat_boundary_name_contrast":
        risks.append("text_overlay_low_complexity_control")
    if "audio_required" in (qa.get("uncertainty") or []):
        risks.append("audio_required_unresolved")
    if qa.get("answer_status") == "ANSWER_PENDING" and not qa.get("provisional_answer_zh"):
        risks.append("no_provisional_answer")
    if qa.get("from_new_observation"):
        risks.append("from_new_frame_observation_unverified_video")

    score = 0.4
    if not errors:
        score += 0.15
    if qa.get("retained_as_independent_sample"):
        score += 0.1
    if qa.get("mechanism") in {"reverse_name_to_early_garment", "cross_scene_attribute_contrast"}:
        score += 0.15
    if qa.get("from_new_observation"):
        score += 0.05
    if qa.get("development_control"):
        score -= 0.05
    if "audio_required" in (qa.get("uncertainty") or []):
        score -= 0.2
    if qa.get("mechanism") == "cross_shot_narrative":
        score -= 0.15
    score = max(0.0, min(1.0, score - 0.05 * len(errors)))

    # Calibrated labels — never AUTO_HIGH as objective correctness
    if errors:
        grade = "REJECT_HARD"
    elif qa.get("development_control") or "text_overlay_low_complexity_control" in risks:
        grade = "SHORTCUT_CONTROL"
    elif score >= 0.7:
        grade = "HEURISTIC_HIGH_NOT_VIDEO_TESTED"
    elif score >= 0.5:
        grade = "HEURISTIC_MEDIUM_NOT_VIDEO_TESTED"
    elif score >= 0.35:
        grade = "HEURISTIC_LOW_NOT_VIDEO_TESTED"
    else:
        grade = "UNCERTAIN"

    return {
        "qa_id": qa["qa_id"],
        "video_id": qa["video_id"],
        "grade": grade,
        "score": round(score, 3),
        "evidence_tested": False,
        "masked_qa_executed": False,
        "hard_errors": errors,
        "risks": risks,
        "proxy_A_only": a_proxy,
        "proxy_B_only": b_proxy,
        "proxy_A_plus_B": ab_proxy,
        "necessity_proxy": {
            "a_solves": bool(a_proxy.get("answer")) and a_proxy.get("confidence", 0) > 0.55,
            "b_solves": bool(b_proxy.get("answer")) and b_proxy.get("confidence", 0) > 0.55,
            "note": "RULE_PROXY_NOT_VIDEO_TESTED — not formal necessity",
        },
        "evidence_family": qa.get("evidence_family"),
        "mechanism": qa.get("mechanism"),
        "funnel_level": "AUTO_TRIAGED",
        "data_partition_status": "UNASSIGNED",
        "formal_supported": False,
        "from_new_observation": bool(qa.get("from_new_observation")),
    }


def screen_batch(drafts: list[dict[str, Any]], events_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [screen_one(d, events_by_id) for d in drafts]


def prioritize_for_human(screened: list[dict[str, Any]], drafts_by_id: dict[str, dict[str, Any]], k: int = 12) -> list[dict[str, Any]]:
    """Prefer distinct families; do not pad with duplicates/UNKNOWN/quarantine."""
    import random

    rng = random.Random(20261030)
    by_fam: dict[str, dict[str, Any]] = {}
    for s in screened:
        qa = drafts_by_id.get(s["qa_id"], {})
        if s["grade"] == "REJECT_HARD":
            continue
        if qa.get("generation_error") or qa.get("duplicate_of_family"):
            continue
        if not qa.get("retained_as_independent_sample", True):
            continue
        fam = s.get("evidence_family") or s["qa_id"]
        if fam not in by_fam or s["score"] > by_fam[fam]["score"]:
            by_fam[fam] = s
    pool = list(by_fam.values())

    high = [s for s in pool if "HIGH" in s["grade"]]
    medium = [s for s in pool if "MEDIUM" in s["grade"]]
    controls = [s for s in pool if s["grade"] == "SHORTCUT_CONTROL"]
    uncertain = [s for s in pool if s["grade"] in {"HEURISTIC_LOW_NOT_VIDEO_TESTED", "UNCERTAIN"}]
    # Prefer new-observation items
    new_obs = [s for s in pool if s.get("from_new_observation")]

    picked: list[dict[str, Any]] = []
    picked_ids: set[str] = set()

    def _add(s: dict[str, Any]) -> None:
        if s["qa_id"] in picked_ids or len(picked) >= k:
            return
        picked.append(s)
        picked_ids.add(s["qa_id"])

    for s in new_obs:
        _add(s)
    seen_mech: set[str] = set()
    for bucket in (high, medium, controls, uncertain):
        for s in bucket:
            mech = s.get("mechanism") or ""
            if mech in seen_mech and len(picked) >= max(3, k // 2):
                continue
            _add(s)
            seen_mech.add(mech)
    for s in sorted(pool, key=lambda x: x["score"], reverse=True):
        _add(s)
    for s in rng.sample(high, k=min(1, len(high))) if high else []:
        _add(s)

    out = []
    for i, s in enumerate(picked[:k]):
        qa = drafts_by_id[s["qa_id"]]
        out.append(
            {
                "priority": i + 1,
                "qa_id": s["qa_id"],
                "video_id": s["video_id"],
                "grade": s["grade"],
                "score": s["score"],
                "mechanism": s.get("mechanism"),
                "reason": _reason(s),
                "question_zh": qa.get("question_zh"),
                "from_new_observation": s.get("from_new_observation"),
                "answer_hidden_in_blind": True,
            }
        )
    return out


def _reason(s: dict[str, Any]) -> str:
    if s.get("from_new_observation"):
        return "new_frame_observation_candidate"
    if "HIGH" in s["grade"]:
        return "heuristic_high_calibration_not_video_tested"
    if s["grade"] == "SHORTCUT_CONTROL":
        return "development_control_or_shortcut"
    if s["risks"]:
        return "risk_sample:" + ",".join(s["risks"][:2])
    return "coverage_or_uncertain"
