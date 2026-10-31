"""Validate + normalize ChatGPT still-frame observations into factory events."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import EXTRACTOR_VERSION
from .provenance import annotate_event

REQUIRED = (
    "event_id",
    "video_id",
    "time_span",
    "action_or_state",
    "evidence_paths",
    "observed_vs_inferred",
    "uncertainty",
    "provenance",
)


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_raw_chatgpt_events(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        # skip status placeholders
        if row.get("status") == "PENDING_CHATGPT_FRAME_PRODUCTION" or "schema_hint" in row:
            continue
        if not row.get("event_id"):
            continue
        rows.append(row)
    return rows


def validate_chatgpt_events(
    raw: list[dict[str, Any]],
    *,
    manifest_frames: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Schema / path / sha / dedup checks. Does not invent semantics."""
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_frame_ids: set[str] = set()
    frame_by_path = {}
    if manifest_frames:
        for f in manifest_frames:
            frame_by_path[f.get("evidence_path")] = f
            frame_by_path[str(Path(f.get("evidence_path") or ""))] = f

    for row in raw:
        reasons: list[str] = []
        for k in REQUIRED:
            if k not in row:
                reasons.append(f"missing:{k}")
        if row.get("provenance") != "CHATGPT_FRAME_OBSERVATION":
            reasons.append("bad_provenance")
        ts = row.get("time_span") or {}
        if not isinstance(ts, dict) or "start_s" not in ts or "end_s" not in ts:
            reasons.append("bad_time_span")
        else:
            # Instantaneous still point is allowed (start==end)
            if float(ts["start_s"]) > float(ts["end_s"]):
                reasons.append("time_span_inverted")
        paths = row.get("evidence_paths") or []
        if not paths:
            reasons.append("no_evidence_paths")
        eid = row.get("event_id")
        if eid in seen_ids:
            reasons.append("duplicate_event_id")
        fid = row.get("evidence_frame_id")
        if fid and fid in seen_frame_ids:
            reasons.append("duplicate_evidence_frame_id")

        # Evidence path existence + optional sha check
        for p in paths:
            pp = Path(p)
            if not pp.is_file():
                reasons.append(f"missing_file:{p}")
                continue
            declared = row.get("source_frame_sha256")
            if declared:
                got = _sha256_file(pp)
                if got and got != declared:
                    reasons.append(f"sha256_mismatch:{p}")
            # Manifest cross-check when available
            mf = frame_by_path.get(p)
            if mf is not None:
                if mf.get("video_id") and mf["video_id"] != row.get("video_id"):
                    reasons.append("manifest_video_id_mismatch")
                # allow ~2s clock skew between manifest time_s and event time_span
                mt = mf.get("time_s")
                if mt is not None and abs(float(mt) - float(ts.get("start_s", mt))) > 2.5:
                    reasons.append("manifest_time_mismatch")

        if row.get("video_motion_verified") is True:
            reasons.append("claimed_motion_verified_on_still_batch")
        if row.get("cross_shot_identity_verified") is True:
            reasons.append("claimed_cross_shot_identity_on_still_batch")

        if reasons:
            rejected.append({"event_id": eid, "reasons": reasons, "raw": row})
            continue
        seen_ids.add(eid)
        if fid:
            seen_frame_ids.add(fid)
        accepted.append(row)

    return {
        "n_raw": len(raw),
        "n_accepted": len(accepted),
        "n_rejected": len(rejected),
        "accepted": accepted,
        "rejected": rejected,
        "duplicate_event_ids_caught": sum(1 for r in rejected if "duplicate_event_id" in (r.get("reasons") or [])),
    }


def normalize_chatgpt_event(row: dict[str, Any]) -> dict[str, Any]:
    """Map ChatGPT still schema → factory event graph node (still-point, not continuous)."""
    ts = row["time_span"]
    t0 = float(ts["start_s"])
    t1 = float(ts["end_s"])
    # Keep instantaneous stills as a point interval (t1==t0); do not invent duration.
    actor = row.get("actor")
    if actor is None or (isinstance(actor, str) and not actor.strip()):
        actor_local = f"unspecified_still_{row['event_id'][-3:]}"
    else:
        actor_local = str(actor)[:120]
    action = str(row.get("action_or_state") or "")
    # Verb is a short machine tag; full text stays in notes/summary
    verb = "still_scene_observation"
    location = ""
    # Light location hint from text without claiming geo
    low = action.lower()
    if "street" in low or "shop" in low or "road" in low:
        location = "outdoor_street_or_commercial"
    elif "indoor" in low or "sofa" in low or "plate" in low or "children" in low:
        location = "indoor_setting"
    elif "aerial" in low or "parkroyal" in low or "tower" in low:
        location = "aerial_urban"
    elif "schematic" in low or "animated" in low or "diagram" in low:
        location = "computer_graphic"
    elif "vending" in low:
        location = "vending_machine_closeup"
    elif "card" in low and "display" in low:
        location = "collectible_card_display"

    unresolved = [
        "evidence_modality_single_static_frame",
        "video_motion_unverified",
        "cross_shot_identity_unverified",
        "not_continuous_video_event",
    ]
    if row.get("uncertainty"):
        unresolved.append("chatgpt_uncertainty_recorded")

    ev = {
        "event_id": row["event_id"],
        "video_id": row["video_id"],
        "time_start_s": round(t0, 3),
        "time_end_s": round(t1, 3),
        "time_point_still_s": round(t0, 3),
        "actor_local_track": actor_local,
        "verb": verb,
        "object": str(row.get("object") or "")[:240],
        "location": location,
        "state_before": None,
        "state_after": None,
        "modality": "visual_still",
        "evidence_paths": list(row.get("evidence_paths") or []),
        "confidence": 0.55,
        "observed_vs_inferred": row.get("observed_vs_inferred") or "observed",
        "unresolved_flags": unresolved,
        "extractor_version": EXTRACTOR_VERSION,
        "provenance": "CHATGPT_FRAME_OBSERVATION",
        "provenance_tier": "CHATGPT_FRAME_OBSERVATION",
        "from_curated_dict": False,
        "notes": action[:500],
        "summary_zh": action[:240],
        "identity_link": {"status": "LOCAL_ONLY", "match_confidence": None, "distractors": []},
        "evidence_modality": row.get("evidence_modality") or "single_static_frame",
        "evidence_frame_id": row.get("evidence_frame_id"),
        "source_frame_sha256": row.get("source_frame_sha256"),
        "video_motion_verified": False,
        "cross_shot_identity_verified": False,
        "is_continuous_video_event": False,
        "is_still_frame_observation": True,
        "relation_or_qa_certification": row.get("relation_or_qa_certification") or "NOT_ASSESSED",
        "data_partition_status": row.get("partition") or "UNASSIGNED",
        "formal_supported": False,
    }
    return annotate_event(ev)


def ingest_chatgpt_events_file(
    path: Path,
    *,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    raw = load_raw_chatgpt_events(path)
    manifest_frames = None
    if manifest_path and manifest_path.exists():
        man = json.loads(manifest_path.read_text())
        manifest_frames = man.get("frames") or []
    report = validate_chatgpt_events(raw, manifest_frames=manifest_frames)
    normalized = [normalize_chatgpt_event(r) for r in report["accepted"]]
    by_video: dict[str, list[dict[str, Any]]] = {}
    for ev in normalized:
        by_video.setdefault(ev["video_id"], []).append(ev)
    evidence: list[dict[str, Any]] = []
    for ev in normalized:
        for p in ev.get("evidence_paths") or []:
            evidence.append(
                {
                    "evidence_id": f"{ev['event_id']}_ev",
                    "video_id": ev["video_id"],
                    "time_s": ev["time_start_s"],
                    "path": p,
                    "kind": "chatgpt_frame_observation",
                    "time_unit": "seconds_file_clock",
                    "provenance_tier": "CHATGPT_FRAME_OBSERVATION",
                    "evidence_modality": "single_static_frame",
                }
            )
    report["normalized_events"] = normalized
    report["events_by_video"] = by_video
    report["evidence"] = evidence
    return report
