"""Tiered provenance labels for factory events (V2)."""

from __future__ import annotations

from typing import Any

# Canonical tiers — curated fixtures ≠ newly discovered
PROVENANCE_TIERS = (
    "CURATED_FROM_PRIOR_HUMAN_OR_CHATGPT_AUDIT",
    "CURSOR_FRAME_VISUAL_OBSERVATION",  # agent-inspected stills this round
    "CHATGPT_FRAME_OBSERVATION",
    "CHATGPT_MULTIFRAME_OBSERVATION",  # ordered still-sheet review (not continuous-certified)
    "AUTOMATIC_COARSE_FRAME",
    "AUTOMATIC_SEMANTIC_MODEL_OBSERVATION",
    "HUMAN_VIDEO_VERIFIED",
)

# Legacy provenance strings → tier
_LEGACY_MAP = {
    "FRAME_VISUAL_OBSERVATION": "AUTOMATIC_COARSE_FRAME",
    "VIDEO_MODEL_OBSERVATION": "AUTOMATIC_SEMANTIC_MODEL_OBSERVATION",
    "ASR_OR_SUBTITLE": "AUTOMATIC_SEMANTIC_MODEL_OBSERVATION",
    "OFFICIAL_QA_HINT": "CURATED_FROM_PRIOR_HUMAN_OR_CHATGPT_AUDIT",
    "HUMAN_VIDEO_REVIEW": "HUMAN_VIDEO_VERIFIED",
}


def normalize_provenance(ev: dict[str, Any]) -> str:
    # Curated fixtures always win (even if an older default tier was baked in)
    if ev.get("from_curated_dict") or ev.get("is_curated_fixture"):
        return "CURATED_FROM_PRIOR_HUMAN_OR_CHATGPT_AUDIT"
    if ev.get("provenance_tier") in PROVENANCE_TIERS:
        return ev["provenance_tier"]
    src = ev.get("provenance") or ev.get("source") or ""
    if src in PROVENANCE_TIERS:
        return src
    if src in _LEGACY_MAP:
        return _LEGACY_MAP[src]
    verb = ev.get("verb") or ""
    if verb in {"visual_sample", "seed_frame_present"}:
        return "AUTOMATIC_COARSE_FRAME"
    return "AUTOMATIC_COARSE_FRAME"


def annotate_event(ev: dict[str, Any]) -> dict[str, Any]:
    out = dict(ev)
    tier = normalize_provenance(out)
    out["provenance_tier"] = tier
    out["is_newly_discovered_semantic"] = tier in {
        "CURSOR_FRAME_VISUAL_OBSERVATION",
        "CHATGPT_FRAME_OBSERVATION",
        "CHATGPT_MULTIFRAME_OBSERVATION",
        "AUTOMATIC_SEMANTIC_MODEL_OBSERVATION",
        "HUMAN_VIDEO_VERIFIED",
    } and (out.get("verb") not in {"visual_sample", "seed_frame_present"})
    out["is_curated_fixture"] = tier == "CURATED_FROM_PRIOR_HUMAN_OR_CHATGPT_AUDIT"
    return out


def count_by_provenance(events: list[dict[str, Any]]) -> dict[str, Any]:
    tiers: dict[str, int] = {t: 0 for t in PROVENANCE_TIERS}
    for e in events:
        tiers[normalize_provenance(e)] = tiers.get(normalize_provenance(e), 0) + 1
    coarse = sum(1 for e in events if e.get("verb") in {"visual_sample", "seed_frame_present"})
    curated_sem = sum(
        1
        for e in events
        if normalize_provenance(e) == "CURATED_FROM_PRIOR_HUMAN_OR_CHATGPT_AUDIT"
        and e.get("verb") not in {"visual_sample", "seed_frame_present"}
    )
    new_sem = sum(1 for e in events if e.get("is_newly_discovered_semantic"))
    return {
        "by_tier": tiers,
        "n_total_coarse_frames": coarse,
        "n_curated_semantic_events": curated_sem,
        "n_new_machine_or_agent_semantic_events": new_sem,
    }
