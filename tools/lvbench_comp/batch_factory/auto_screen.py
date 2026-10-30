"""B5 — cheap auto triage: evidence checks, shortcut proxies, scoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _proxy_blind_answer(qa: dict[str, Any], side: str) -> dict[str, Any]:
    """Heuristic proxy — NOT proof of necessity."""
    mech = qa.get("mechanism")
    ans = qa.get("provisional_answer_zh") or qa.get("normalized_answer")
    if side == "B":
        if mech == "reverse_name_to_early_garment":
            return {"answer": None, "confidence": 0.2, "note": "B has name/jersey; jacket color typically absent"}
        if mech == "ordered_state_transitions":
            return {"answer": "may_read_final_and_infer_prior", "confidence": 0.55, "note": "B overlay may show 0-1→1-1 leaking order"}
        if mech == "heat_boundary_name_contrast":
            return {"answer": "Gatlin_only", "confidence": 0.7, "note": "B-only can read start list USA name"}
        return {"answer": None, "confidence": 0.3, "note": "proxy"}
    if side == "A":
        if mech == "reverse_name_to_early_garment":
            return {"answer": ans, "confidence": 0.4, "note": "A may see red jacket but not who is named later"}
        if mech == "ordered_state_transitions":
            return {"answer": "first_transition_only", "confidence": 0.6, "note": "A sees first score change"}
        if mech == "heat_boundary_name_contrast":
            return {"answer": "Gay_only", "confidence": 0.7, "note": "A-only intro caption"}
        return {"answer": None, "confidence": 0.3, "note": "proxy"}
    # A+B
    return {"answer": ans, "confidence": 0.65, "note": "proxy_combined"}


def screen_one(qa: dict[str, Any], events_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    risks: list[str] = []

    # Evidence existence
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

    a_proxy = _proxy_blind_answer(qa, "A")
    b_proxy = _proxy_blind_answer(qa, "B")
    ab_proxy = _proxy_blind_answer(qa, "AB")

    # Shortcut heuristics
    if b_proxy.get("answer") and qa.get("mechanism") == "ordered_state_transitions":
        risks.append("possible_B_only_order_leak")
    if qa.get("mechanism") == "heat_boundary_name_contrast":
        risks.append("text_overlay_low_complexity_control")
    if "audio_required" in (qa.get("uncertainty") or []):
        risks.append("audio_required_unresolved")
    if qa.get("answer_status") == "ANSWER_PENDING" and not qa.get("provisional_answer_zh"):
        risks.append("no_provisional_answer")

    # Score
    score = 0.4
    if not errors:
        score += 0.15
    if qa.get("retained_as_independent_sample"):
        score += 0.1
    if qa.get("mechanism") in {"reverse_name_to_early_garment", "ordered_state_transitions"}:
        score += 0.15
    if qa.get("development_control"):
        score -= 0.05
    if "audio_required" in (qa.get("uncertainty") or []):
        score -= 0.2
    if qa.get("mechanism") == "cross_shot_narrative":
        score -= 0.15
    score = max(0.0, min(1.0, score - 0.05 * len(errors)))

    if errors:
        grade = "REJECT_HARD"
    elif score >= 0.7 and not qa.get("development_control"):
        grade = "AUTO_HIGH"
    elif score >= 0.5:
        grade = "AUTO_MEDIUM"
    elif "text_overlay_low_complexity_control" in risks or qa.get("development_control"):
        grade = "SHORTCUT_CONTROL"
    elif score >= 0.35:
        grade = "AUTO_LOW"
    else:
        grade = "UNCERTAIN"

    return {
        "qa_id": qa["qa_id"],
        "video_id": qa["video_id"],
        "grade": grade,
        "score": round(score, 3),
        "hard_errors": errors,
        "risks": risks,
        "proxy_A_only": a_proxy,
        "proxy_B_only": b_proxy,
        "proxy_A_plus_B": ab_proxy,
        "necessity_proxy": {
            "a_solves": bool(a_proxy.get("answer")) and a_proxy.get("confidence", 0) > 0.55,
            "b_solves": bool(b_proxy.get("answer")) and b_proxy.get("confidence", 0) > 0.55,
            "note": "Proxy only — not formal necessity",
        },
        "evidence_family": qa.get("evidence_family"),
        "mechanism": qa.get("mechanism"),
        "funnel_level": "AUTO_TRIAGED",
        "data_partition_status": "UNASSIGNED",
        "formal_supported": False,
    }


def screen_batch(drafts: list[dict[str, Any]], events_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [screen_one(d, events_by_id) for d in drafts]


def prioritize_for_human(screened: list[dict[str, Any]], drafts_by_id: dict[str, dict[str, Any]], k: int = 12) -> list[dict[str, Any]]:
    """Active sampling: new signatures, conflicts/risks, ≥20% high random, low false-kill candidates."""
    import random

    rng = random.Random(20261030)
    by_fam: dict[str, dict[str, Any]] = {}
    for s in screened:
        if s["grade"] == "REJECT_HARD":
            continue
        fam = s.get("evidence_family") or s["qa_id"]
        if fam not in by_fam or s["score"] > by_fam[fam]["score"]:
            by_fam[fam] = s
    pool = list(by_fam.values())

    high = [s for s in pool if s["grade"] == "AUTO_HIGH"]
    medium = [s for s in pool if s["grade"] == "AUTO_MEDIUM"]
    controls = [s for s in pool if s["grade"] == "SHORTCUT_CONTROL"]
    uncertain = [s for s in pool if s["grade"] in {"AUTO_LOW", "UNCERTAIN"}]

    picked: list[dict[str, Any]] = []
    picked_ids: set[str] = set()

    def _add(s: dict[str, Any]) -> None:
        if s["qa_id"] in picked_ids or len(picked) >= k:
            return
        picked.append(s)
        picked_ids.add(s["qa_id"])

    # Pass 1: diverse mechanisms (prefer high→medium→control→uncertain)
    seen_mech: set[str] = set()
    for bucket in (high, medium, controls, uncertain):
        for s in bucket:
            mech = s.get("mechanism") or ""
            if mech in seen_mech:
                continue
            _add(s)
            seen_mech.add(mech)

    # Pass 2: fill to k with remaining by score (same mechanism OK if different family)
    rest = sorted(pool, key=lambda s: s["score"], reverse=True)
    for s in rest:
        _add(s)

    # Ensure ≥20% high among picked when high exists
    if high:
        n_high_target = max(1, int(0.2 * max(1, len(picked))))
        have = sum(1 for s in picked if s["grade"] == "AUTO_HIGH")
        for s in high:
            if have >= n_high_target:
                break
            if s["qa_id"] not in picked_ids and len(picked) < k:
                picked.append(s)
                picked_ids.add(s["qa_id"])
                have += 1

    # Random high calibration extras (may replace lowest if already full — append if room)
    for s in rng.sample(high, k=min(2, len(high))) if high else []:
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
                "provisional_answer_zh": qa.get("provisional_answer_zh"),
                "answer_hidden_in_blind": True,
            }
        )
    return out


def _reason(s: dict[str, Any]) -> str:
    if s["grade"] == "AUTO_HIGH":
        return "high_auto_or_calibration"
    if s["grade"] == "SHORTCUT_CONTROL":
        return "development_control_or_shortcut"
    if s["risks"]:
        return "risk_sample:" + ",".join(s["risks"][:2])
    return "coverage_or_uncertain"
