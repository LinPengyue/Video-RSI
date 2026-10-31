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
    require_manifest_membership: bool | None = None,
    require_source_sha: bool | None = None,
    allowed_provenances: tuple[str, ...] = ("CHATGPT_FRAME_OBSERVATION",),
) -> dict[str, Any]:
    """Schema / path / sha / dedup checks. Does not invent semantics.

    When ``manifest_frames`` is provided, trusted-production mode defaults ON:
    every evidence path must appear in the manifest and ``source_frame_sha256``
    must be present and match the file. Pass
    ``require_manifest_membership=False`` / ``require_source_sha=False`` to keep
    the legacy lenient path (no-manifest callers unchanged).
    """
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_frame_ids: set[str] = set()
    frame_by_path: dict[str, dict[str, Any]] = {}
    if manifest_frames:
        for f in manifest_frames:
            frame_by_path[f.get("evidence_path")] = f
            frame_by_path[str(Path(f.get("evidence_path") or ""))] = f
    # Trusted production when a manifest is explicitly supplied
    if require_manifest_membership is None:
        require_manifest_membership = bool(manifest_frames)
    if require_source_sha is None:
        require_source_sha = bool(manifest_frames)

    for row in raw:
        reasons: list[str] = []
        for k in REQUIRED:
            if k not in row:
                reasons.append(f"missing:{k}")
        if row.get("provenance") not in allowed_provenances:
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

        declared = row.get("source_frame_sha256")
        sha_list = row.get("evidence_sha256")
        if sha_list is not None and not isinstance(sha_list, list):
            reasons.append("bad_evidence_sha256_type")
            sha_list = None
        if (
            require_source_sha
            and not declared
            and not (isinstance(sha_list, list) and len(sha_list) == len(paths) and all(sha_list))
        ):
            reasons.append("missing_source_frame_sha256")
        if isinstance(sha_list, list) and paths and len(sha_list) != len(paths):
            reasons.append("evidence_sha256_length_mismatch")

        # Evidence path existence + sha / manifest checks
        for i, p in enumerate(paths):
            pp = Path(p)
            if not pp.is_file():
                reasons.append(f"missing_file:{p}")
                continue
            path_declared = None
            if isinstance(sha_list, list) and i < len(sha_list):
                path_declared = sha_list[i]
            elif declared and len(paths) == 1:
                path_declared = declared
            if path_declared:
                got = _sha256_file(pp)
                if got and got != path_declared:
                    reasons.append(f"sha256_mismatch:{p}")
            mf = frame_by_path.get(p) or frame_by_path.get(str(pp))
            if mf is None:
                if require_manifest_membership:
                    reasons.append(f"not_in_manifest:{p}")
            else:
                if mf.get("video_id") and mf["video_id"] != row.get("video_id"):
                    reasons.append("manifest_video_id_mismatch")
                # Path must fall within the event's time_span (multiframe) or near start (single)
                mt = mf.get("time_s")
                if mt is not None and isinstance(ts, dict) and "start_s" in ts and "end_s" in ts:
                    t0, t1 = float(ts["start_s"]), float(ts["end_s"])
                    if not (t0 - 2.5 <= float(mt) <= t1 + 2.5):
                        reasons.append(f"manifest_time_outside_span:{p}")
                msha = mf.get("sha256") or mf.get("source_frame_sha256")
                if path_declared and msha and path_declared != msha:
                    reasons.append("manifest_sha256_mismatch")
                # ROI consistency when both sides declare roi_id
                if row.get("roi_id") and mf.get("roi_id") and row["roi_id"] != mf["roi_id"]:
                    reasons.append("manifest_roi_mismatch")

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
    """Map ChatGPT still / multiframe schema → factory event node (not continuous-certified)."""
    ts = row["time_span"]
    t0 = float(ts["start_s"])
    t1 = float(ts["end_s"])
    actor = row.get("actor")
    if actor is None or (isinstance(actor, str) and not actor.strip()):
        actor_local = f"unspecified_still_{row['event_id'][-3:]}"
    else:
        actor_local = str(actor)[:120]
    action = str(row.get("action_or_state") or "")
    prov = row.get("provenance") or "CHATGPT_FRAME_OBSERVATION"
    is_mf = prov == "CHATGPT_MULTIFRAME_OBSERVATION" or bool(row.get("roi_id"))
    verb = "multiframe_still_observation" if is_mf else "still_scene_observation"
    location = ""
    low = action.lower()
    if "street" in low or "shop" in low or "road" in low:
        location = "outdoor_street_or_commercial"
    elif "indoor" in low or "sofa" in low or "plate" in low or "children" in low:
        location = "indoor_setting"
    elif "aerial" in low or "parkroyal" in low or "tower" in low:
        location = "aerial_urban"
    elif "schematic" in low or "animated" in low or "diagram" in low:
        location = "computer_graphic"
    elif "vending" in low or "售货" in action:
        location = "vending_machine_closeup"
    elif "card" in low or "卡" in action:
        location = "collectible_card_display"
    elif "nozzle" in low or "lattice" in low or "打印" in action or "网格" in action:
        location = "printer_build_plate"

    unresolved = [
        "video_motion_unverified",
        "cross_shot_identity_unverified",
        "not_continuous_video_event",
    ]
    if is_mf:
        unresolved.append("evidence_modality_ordered_still_sheet")
        unresolved.append("still_sequence_only")
    else:
        unresolved.append("evidence_modality_single_static_frame")
    if row.get("uncertainty"):
        unresolved.append("chatgpt_uncertainty_recorded")
    if row.get("modality_label") == "UNRESOLVED":
        unresolved.append("modality_label_unresolved")

    ev = {
        "event_id": row["event_id"],
        "video_id": row["video_id"],
        "roi_id": row.get("roi_id"),
        "time_start_s": round(t0, 3),
        "time_end_s": round(t1, 3),
        "time_point_still_s": round(t0, 3) if abs(t1 - t0) < 1e-6 else None,
        "actor_local_track": actor_local,
        "verb": verb,
        "object": str(row.get("object") or "")[:240],
        "location": location,
        "state_before": row.get("state_before"),
        "state_after": row.get("state_after"),
        "modality": "visual_multiframe_still" if is_mf else "visual_still",
        "modality_label": row.get("modality_label"),
        "evidence_paths": list(row.get("evidence_paths") or []),
        "evidence_frame_ids": list(row.get("evidence_frame_ids") or []),
        "evidence_sha256": list(row.get("evidence_sha256") or []),
        "confidence": 0.55 if row.get("observed_vs_inferred") == "observed" else 0.45,
        "observed_vs_inferred": row.get("observed_vs_inferred") or "observed",
        "unresolved_flags": unresolved,
        "extractor_version": EXTRACTOR_VERSION,
        "provenance": prov,
        "provenance_tier": prov if prov in {
            "CHATGPT_FRAME_OBSERVATION",
            "CHATGPT_MULTIFRAME_OBSERVATION",
        } else "CHATGPT_FRAME_OBSERVATION",
        "from_curated_dict": False,
        "notes": action[:500],
        "summary_zh": action[:240],
        "identity_link": {"status": "LOCAL_ONLY", "match_confidence": None, "distractors": []},
        "evidence_modality": (
            row.get("evidence_modality")
            or ("multiframe_still_sheet" if is_mf else "single_static_frame")
        ),
        "evidence_frame_id": row.get("evidence_frame_id"),
        "source_frame_sha256": row.get("source_frame_sha256"),
        "candidate_kind": row.get("candidate_kind"),
        "composition_certification": row.get("composition_certification") or "NOT_CERTIFIED",
        "video_motion_verified": False,
        "cross_shot_identity_verified": False,
        "is_continuous_video_event": False,
        "is_still_frame_observation": True,
        "is_multiframe_still_observation": is_mf,
        "relation_or_qa_certification": row.get("relation_or_qa_certification") or "NOT_ASSESSED",
        "data_partition_status": row.get("data_partition_status") or row.get("partition") or "UNASSIGNED",
        "formal_supported": False,
    }
    return annotate_event(ev)


def ingest_chatgpt_events_file(
    path: Path,
    *,
    manifest_path: Path | None = None,
    require_manifest_membership: bool | None = None,
    require_source_sha: bool | None = None,
    allowed_provenances: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    raw = load_raw_chatgpt_events(path)
    # Auto-detect multiframe provenance from file contents
    provs = {r.get("provenance") for r in raw if r.get("provenance")}
    if allowed_provenances is None:
        if "CHATGPT_MULTIFRAME_OBSERVATION" in provs:
            allowed_provenances = (
                "CHATGPT_FRAME_OBSERVATION",
                "CHATGPT_MULTIFRAME_OBSERVATION",
            )
        else:
            allowed_provenances = ("CHATGPT_FRAME_OBSERVATION",)
    manifest_frames = None
    if manifest_path and manifest_path.exists():
        man = json.loads(manifest_path.read_text())
        # Support both flat `frames` and nested ROI `frames_flat`
        manifest_frames = man.get("frames") or man.get("frames_flat") or []
        if not manifest_frames and "meta" in man:
            manifest_frames = man.get("frames") or []
    report = validate_chatgpt_events(
        raw,
        manifest_frames=manifest_frames,
        require_manifest_membership=require_manifest_membership,
        require_source_sha=require_source_sha,
        allowed_provenances=allowed_provenances,
    )
    normalized = [normalize_chatgpt_event(r) for r in report["accepted"]]
    by_video: dict[str, list[dict[str, Any]]] = {}
    for ev in normalized:
        by_video.setdefault(ev["video_id"], []).append(ev)
    evidence: list[dict[str, Any]] = []
    for ev in normalized:
        for i, p in enumerate(ev.get("evidence_paths") or []):
            evidence.append(
                {
                    "evidence_id": f"{ev['event_id']}_ev{i}",
                    "video_id": ev["video_id"],
                    "roi_id": ev.get("roi_id"),
                    "time_s": ev["time_start_s"],
                    "path": p,
                    "kind": (
                        "chatgpt_multiframe_observation"
                        if ev.get("is_multiframe_still_observation")
                        else "chatgpt_frame_observation"
                    ),
                    "time_unit": "seconds_file_clock",
                    "provenance_tier": ev.get("provenance_tier"),
                    "evidence_modality": ev.get("evidence_modality"),
                    "sha256": (ev.get("evidence_sha256") or [None])[i]
                    if i < len(ev.get("evidence_sha256") or [])
                    else None,
                }
            )
    report["normalized_events"] = normalized
    report["events_by_video"] = by_video
    report["evidence"] = evidence
    return report
