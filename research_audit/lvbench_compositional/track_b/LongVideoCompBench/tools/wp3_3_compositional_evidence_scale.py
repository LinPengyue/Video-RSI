#!/usr/bin/env python3
"""WP3.3: compositional evidence deepen + controlled scale experiment.

P0 clarification of discovery eval claims
P1 Bugatti four-window deepen
P2 PAIR2 pending / Voice CONTROL
P3 prospective entity/event-first discovery
P4 5-video controlled A/B
P5 signature generalization audit

Does NOT mint FORMAL_GOLD. Does NOT rewrite WP3.2 history.
Does NOT run Track A. Does NOT add public third-party media.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DS_ROOT,
    FROZEN_5_2,
    PROPOSED_7_4_SEEN,
    PROPOSED_7_4_UNSEEN,
    REPO_ROOT,
    SEED_11,
    utc_now,
    write_json,
    write_jsonl,
    sha256_file,
)
from wp3_wave_production import (  # noqa: E402
    FFMPEG,
    FRAMES_PER_ROI,
    REVIEW_FRAMES_PER_ROI,
    VIDEO_ROOT,
    copy_review_subset,
    discover_pairs,
    extract_roi_frames,
    ffprobe_duration,
    load_exposed,
    maybe_extract_clip,
    partial_sha256,
    register_pool_and_policy,
)
from wp3_3_entity_first_discovery import (  # noqa: E402
    METHOD_ID,
    MODEL_STACK,
    discover_pairs_entity_first,
    fingerprint_overlap,
)

BASELINE = "b56cc4f124a142028ab803cf0b35dabafd6b7c44"
WP3 = DS_ROOT / "wp3_production"
OUT = WP3 / "wp3_3"
LOCAL = (
    REPO_ROOT
    / "research_audit/lvbench_compositional/track_b/local_media/wp3_production/wp3_3"
)
REPORTS = DS_ROOT / "reports"

# Prospective A/B DEV videos (never sealed; not in prior WP3 waves)
AB_VIDEOS = [
    {"video_id": "1FsiZgGZU70", "genre_guess": "vlog", "reason": "travel/drink vlog; stable person likely"},
    {"video_id": "3_upA09AntU", "genre_guess": "cooking", "reason": "chef process; object/state anchors"},
    {"video_id": "9-gOCOu_KGU", "genre_guess": "sports", "reason": "athletics meet; multi-event timeline"},
    {"video_id": "KbahC-QCKU8", "genre_guess": "vlog", "reason": "family fishing vlog; recurring people"},
    {"video_id": "RCAqKnvu_P0", "genre_guess": "travel", "reason": "Japan travel vlog; scene+person continuity"},
]


def write_p0_clarification() -> dict:
    """Keep WP3.2 reports immutable; add clarifying superseding interpretation."""
    old = json.loads((WP3 / "wp3_2_discovery_method_comparison.json").read_text())
    doc = {
        "schema": "wp3_3_discovery_method_evaluation_clarification_v1",
        "built_utc": utc_now(),
        "baseline_commit": BASELINE,
        "preserves_historical_artifact": str(
            (WP3 / "wp3_2_discovery_method_comparison.json").relative_to(REPO_ROOT)
        ),
        "historical_artifact_not_rewritten": True,
        "wp3_2_claim_in_artifact": old.get("head_to_head", {}).get(
            "winner_for_effective_yield"
        ),
        "corrected_supported_claim": "RETROSPECTIVE_SEMANTIC_RERANKING_FEASIBLE",
        "unsupported_claim": "PROSPECTIVE_ENTITY_FIRST_DISCOVERY_SUPERIOR",
        "rationale": [
            "WP3.2 histogram-first generated the 20 ROI pairs; 15 received triage labels.",
            "WP3.2 'entity/event-first' only re-ranked those historical pairs by semantic anchors.",
            "Re-ranking yield ≠ prospective discovery superiority on unseen videos.",
            "WP3.3 P3/P4 implement and evaluate a true independent entity/event-first generator.",
        ],
        "labeling_rule": {
            "unverified_new_composition_signatures": "PROPOSED_SIGNATURE_UNVERIFIED",
            "do_not_auto_promote_unseen": True,
        },
        "status": "CLARIFICATION_RECORDED",
    }
    write_json(OUT / "WP3_3_DISCOVERY_EVAL_CLARIFICATION.json", doc)
    write_json(REPORTS / "WP3_3_DISCOVERY_EVAL_CLARIFICATION.json", doc)
    return doc


def write_p1_bugatti_audit() -> dict:
    """Four-window continuous evidence audit for ihfjEFGdZdc."""
    windows = {
        "PAIR1_A": {
            "t": [285.0, 295.0],
            "observed": [
                "Loading-dock / trailer unload scene (not chassis assembly hall).",
                "Bald man in black polo at wall control panel beside open trailer.",
                "Dark object secured in black metal frame inside trailer; purple-blue ramp.",
                "WELT watermark bottom-left (broadcast overlay).",
                "Adjacent t≈270 shows different factory-floor scene with finished cars — hard cut montage.",
            ],
            "entities": ["worker_bald_black_polo", "trailer_cargo_framed_object", "dock_environment"],
            "static_frame_sufficient": [
                "Scene type = unloading dock",
                "Presence of trailer cargo and worker",
                "WELT overlay",
            ],
            "needs_continuous_video": [
                "Whether cargo is a car body / chassis identity",
                "Unload motion continuity within 10s",
            ],
        },
        "PAIR1_B": {
            "t": [1575.0, 1585.0],
            "observed": [
                "Clean glass-walled assembly hall; chassis on four cylindrical lifts.",
                "Two technicians working under rear of incomplete body (carbon/metal skeleton).",
                "No doors/roof/engine; wiring/pipes visible.",
                "WELT watermark.",
            ],
            "entities": ["chassis_on_lifts", "technician_pair", "assembly_hall"],
            "static_frame_sufficient": [
                "Assembly stage = mid-body on lifts",
                "Two workers present",
            ],
            "needs_continuous_video": [
                "Specific fastening operation sequence",
                "Whether chassis ID matches PAIR1_A cargo",
            ],
        },
        "PAIR2_A": {
            "t": [1470.0, 1480.0],
            "observed": [
                "Large powertrain/engine on white wheeled stand in assembly hall.",
                "Technicians with BUGATTI / PRECISION logos on shirts.",
                "Shelving with parts; reflective floor.",
                "WELT watermark.",
            ],
            "entities": ["engine_on_stand", "bugatti_branded_technicians", "assembly_hall"],
            "static_frame_sufficient": [
                "Engine-on-stand process stage",
                "Brand logo on clothing (shortcut risk)",
            ],
            "needs_continuous_video": [
                "Engine install motion onto a specific chassis",
            ],
        },
        "PAIR2_B": {
            "t": [2715.0, 2725.0],
            "observed": [
                "Finished silver Bugatti Chiron front: horseshoe grille, LED lamps.",
                "French plate OCR W-238-HT (strong identity shortcut if used as answer).",
                "Man with glasses, BUGATTI polo, standing beside car; garage door open.",
                "Adjacent t≈2730 outdoor interview with same man; black car partially visible.",
                "WELT watermark.",
            ],
            "entities": ["finished_chiron_W238HT", "presenter_glasses_bugatti_polo"],
            "static_frame_sufficient": [
                "Finished showroom/garage car",
                "Plate OCR and brand cues",
            ],
            "needs_continuous_video": [
                "Link of this finished car to PAIR2_A engine or PAIR1 chassis",
            ],
        },
    }

    cross = {
        "same_physical_object_continuity": {
            "verdict": "NOT_ESTABLISHED",
            "evidence_for": [
                "Same factory documentary / brand context across mid/late windows",
                "PAIR1_B and PAIR2_A share assembly-hall look",
            ],
            "evidence_against": [
                "PAIR1_A is dock unload; hard cut from finished-car floor at t≈270 — montage editing",
                "No persistent unique chassis marking / VIN / paint shared across windows",
                "PAIR2_A shows detached engine; PAIR2_B shows finished Chiron — no install continuity filmed in these windows",
                "Multiple cars visible in factory background elsewhere → multi-vehicle production montage plausible",
            ],
        },
        "ordered_state_change_same_object": {
            "verdict": "NOT_VERIFIED",
            "note": "Cannot assert IdentifyObject→CompareState A→B for one car from these four windows alone.",
        },
        "general_assembly_process": {
            "verdict": "PLAUSIBLE_DOCUMENTARY_PROCESS",
            "note": "Windows illustrate stages of Bugatti manufacture, not certified same-unit state machine.",
        },
        "shortcuts": {
            "brand_recognition": "HIGH_BUGATTI_LOGO_AND_CHIRON_GRILLE",
            "ocr_plate": "HIGH_W-238-HT",
            "broadcast_overlay": "WELT_WATERMARK_ALWAYS_ON",
            "narration": "NOT_AUDITED_THIS_ROUND_AUDIO",
        },
        "tier": "ORDERED_MULTIFRAME_SUGGESTS_PROCESS_BUT_NOT_SAME_OBJECT",
    }

    facts = [
        {
            "fact_id": "BUG_F1",
            "window": "PAIR1_A",
            "t": [285.0, 295.0],
            "claim": "Dock unload of framed dark cargo by worker at trailer",
            "status": "FACT_CANDIDATE_STATIC_VISIBLE",
            "not": "FACT_VERIFIED_SAME_CHASSIS_AS_PAIR1_B",
        },
        {
            "fact_id": "BUG_F2",
            "window": "PAIR1_B",
            "t": [1575.0, 1585.0],
            "claim": "Incomplete chassis elevated on four lifts with two technicians",
            "status": "FACT_CANDIDATE_STATIC_VISIBLE",
        },
        {
            "fact_id": "BUG_F3",
            "window": "PAIR2_A",
            "t": [1470.0, 1480.0],
            "claim": "Engine/powertrain on wheeled stand; Bugatti-branded staff present",
            "status": "FACT_CANDIDATE_STATIC_VISIBLE",
        },
        {
            "fact_id": "BUG_F4",
            "window": "PAIR2_B",
            "t": [2715.0, 2725.0],
            "claim": "Finished silver Chiron with plate W-238-HT beside Bugatti-polo presenter",
            "status": "FACT_CANDIDATE_STATIC_VISIBLE",
            "shortcut_warning": "Plate OCR + brand can answer without cross-window bind",
        },
        {
            "fact_id": "BUG_R1",
            "type": "cross_window_relation",
            "claim": "PAIR1_A cargo is the same physical chassis later on lifts in PAIR1_B",
            "status": "UNRESOLVED_NOT_SUPPORTED",
            "positive": [],
            "negative": ["Scene discontinuity / montage; no unique object ID shared"],
        },
        {
            "fact_id": "BUG_R2",
            "type": "cross_window_relation",
            "claim": "PAIR2_A engine is installed into the PAIR2_B finished Chiron",
            "status": "UNRESOLVED_NOT_SUPPORTED",
            "positive": ["Same factory documentary narrative"],
            "negative": ["No install continuity in windows; multi-car montage likely"],
        },
    ]

    qa_policy = {
        "same_object_state_change_qa": "NOT_EMITTED",
        "reason": "Same-object continuity not established; refusing forced IdentifyObject→CompareState→QueryEarlier/LaterState",
        "program_attempt_blocked": "IdentifyObject→CrossWindowObjectBind→CompareState→QueryEarlier/LaterState",
        "allowed": "Per-window FACT_CANDIDATE only; optional general-process CONTROL drafts excluded from effective compositional Gold path",
        "prior_wp3_2_pass_candidate_update": {
            "ihfjEFGdZdc_PAIR1": "DOWNGRADED_TO_HOLD_ASSEMBLY_MONTAGE_NOT_SAME_OBJECT",
            "ihfjEFGdZdc_PAIR2": "REMAINS_OR_CONFIRMED_CONTROL_PROCESS_MONTAGE",
            "signature_labels": "PROPOSED_SIGNATURE_UNVERIFIED",
        },
    }

    doc = {
        "schema": "wp3_3_bugatti_four_window_evidence_audit_v1",
        "video_id": "ihfjEFGdZdc",
        "built_utc": utc_now(),
        "baseline_commit": BASELINE,
        "bounded_adjacent_supplement": {
            "path": "research_audit/lvbench_compositional/track_b/local_media/wp3_production/wave2/ihfjEFGdZdc/wp3_3_adjacent",
            "unbounded_rescan": False,
            "n_adjacent_stills": 28,
        },
        "windows": windows,
        "cross_window": cross,
        "facts": facts,
        "qa_policy": qa_policy,
        "fact_verified_count": 0,
        "necessity": "NOT_APPLICABLE_NO_CROSS_WINDOW_QA",
        "formal_gold": False,
    }
    write_json(OUT / "wp3_3_bugatti_ihfjEFGdZdc_evidence_audit.json", doc)
    write_json(REPORTS / "wp3_3_bugatti_ihfjEFGdZdc_evidence_audit.json", doc)
    return doc


def write_p2_other_candidates() -> dict:
    voice = {
        "pair_id": "W-BnDvXXfOs_PAIR2",
        "prior_status": "PASS_CANDIDATE",
        "updated_status": "CONTROL",
        "reason_codes": [
            "CELEBRITY_PRIOR_TOM_JONES_VOICE_JUDGE_CHAIR",
            "SHOW_FORMAT_LEAKAGE_RED_BUTTON_CHAIR",
            "NECESSITY_LIKELY_FAIL_SINGLE_WINDOW_OR_PRIOR",
            "LATE_WINDOW_SUBJECT_APPEARS_DIFFERENT_PERSON_RED_HAIR",
        ],
        "person_match_hypothesis": "RETAINED_AS_HYPOTHESIS_ONLY",
        "effective_compositional_qa": False,
        "count_as_valid_comp_qa": False,
        "shortcut_checks": {
            "celebrity_prior": "HIGH",
            "program_roster_prior": "HIGH_THE_VOICE_UK_STYLE",
            "ocr": "LOW_IN_REVIEW_FRAMES",
            "single_window_answerable": "LIKELY_YES_VIA_CELEBRITY_ID",
        },
        "signature": {
            "draft": "IdentifyPerson→CrossIntervalSamePersonBind→QueryEarlierCoPresentEntities",
            "label": "PROPOSED_SIGNATURE_UNVERIFIED",
            "bucket_if_forced": "ID_CONTROL_CELEBRITY_LEAKAGE",
        },
    }
    pair2 = {
        "pair_id": "USfvmoalqsw_PAIR2",
        "relation_status": "PENDING_HUMAN_IDENTITY_ADJUDICATION",
        "human_adjudication_status": "NOT_OBTAINED_THIS_ROUND",
        "immutable_append_record": None,
        "dual_clip_packet_retained": str(
            (WP3 / "wp3_2_USFV_PAIR2_HUMAN_REVIEW_PACKET.json").relative_to(REPO_ROOT)
        ),
        "signature_family": "HISTORICAL_SAME_PERSON_BIND_FAMILY_NOT_NEW_OOD",
        "blocks_other_work": False,
        "formal_gold": False,
    }
    status = {
        "schema": "wp3_3_other_candidate_status_v1",
        "built_utc": utc_now(),
        "USfvmoalqsw_PAIR2": pair2,
        "W-BnDvXXfOs_PAIR2": voice,
    }
    write_json(OUT / "wp3_3_other_candidate_status.json", status)
    write_json(OUT / "wp3_3_WBn_PAIR2_CONTROL_SHORTCUT_AUDIT.json", voice)
    # refresh PAIR2 status file without claiming new human adjudication
    write_json(
        WP3 / "wp3_3_USFV_PAIR2_STATUS.json",
        {
            **pair2,
            "qa_status": "AUDIT_DRAFT_ONLY",
            "necessity_status": "PROVISIONAL_PENDING_HUMAN",
            "import_ready": False,
        },
    )
    return status


def pack_method_rois(
    video_id: str,
    method: str,
    pairs: list,
    media: Path,
    wave_dir: Path,
    local_dir: Path,
) -> list[dict]:
    rows = []
    vdir = wave_dir / "videos" / video_id / method
    ldir = local_dir / video_id / method
    for early, late in pairs:
        for roi in (early, late):
            fdir = ldir / roi.roi_id / "frames"
            frames = extract_roi_frames(media, roi, fdir, FRAMES_PER_ROI)
            review = copy_review_subset(
                frames, vdir / "review_frames" / roi.roi_id, REVIEW_FRAMES_PER_ROI
            )
            clip = maybe_extract_clip(media, roi, ldir / roi.roi_id / "clip.mp4")
            rows.append(
                {
                    "roi_id": roi.roi_id,
                    "pair_id": roi.pair_id,
                    "video_id": video_id,
                    "method": method,
                    "role": roi.role,
                    "t_start": roi.t_start,
                    "t_end": roi.t_end,
                    "center_s": roi.center_s,
                    "discovery_score": roi.discovery_score,
                    "n_frames_extracted": len(frames),
                    "frames_local": [
                        {**fr, "path": fr["path"]} for fr in frames
                    ],
                    "review_frames": review,
                    "local_clip": clip,
                    "source_video_sha256_partial": partial_sha256(media),
                    "semantics": "UNRESOLVED",
                    "is_newly_discovered_semantic": False,
                }
            )
    return rows


def run_p4_ab(dry_run: bool = False) -> dict:
    """Prospective controlled A/B on 5 new DEV videos."""
    ab_dir = OUT / "ab_dev5"
    ab_dir.mkdir(parents=True, exist_ok=True)
    LOCAL.mkdir(parents=True, exist_ok=True)

    exposed = load_exposed()
    # Also treat prior WP3 wave videos as exposed
    for w in ("wave1", "wave2"):
        sel = WP3 / w / "video_selection.json"
        if sel.exists():
            d = json.loads(sel.read_text())
            for v in d.get("videos") or d.get("selected") or []:
                if isinstance(v, dict):
                    exposed.add(v.get("video_id") or v.get("id"))
                elif isinstance(v, str):
                    exposed.add(v)
    # Idempotent re-runs of this AB pack are allowed (same as WP3 wave production).
    ab_ids = {s["video_id"] for s in AB_VIDEOS}
    prior_non_ab = exposed - ab_ids

    t0 = time.time()
    video_results = []
    all_rois: list[dict] = []
    compute = {"histogram_seconds": 0.0, "entity_first_seconds": 0.0, "extract_seconds": 0.0}

    for spec in AB_VIDEOS:
        vid = spec["video_id"]
        if vid in prior_non_ab:
            raise SystemExit(f"REFUSING_ALREADY_EXPOSED: {vid}")
        media = VIDEO_ROOT / f"{vid}.mp4"
        if not media.exists():
            raise SystemExit(f"MISSING_MEDIA: {media}")
        dur = ffprobe_duration(media)
        if dur is None:
            raise SystemExit(f"NO_DURATION: {vid}")

        work_h = LOCAL / vid / "_work_hist"
        work_e = LOCAL / vid / "_work_ef"
        work_h.mkdir(parents=True, exist_ok=True)
        work_e.mkdir(parents=True, exist_ok=True)

        th = time.time()
        hist_pairs = discover_pairs(vid, media, dur, work_h)
        compute["histogram_seconds"] += time.time() - th

        te = time.time()
        ef_pairs, ef_diag = discover_pairs_entity_first(vid, media, dur, work_e)
        compute["entity_first_seconds"] += time.time() - te

        # Rename hist pairs to HF_ namespace for clarity
        for i, (a, b) in enumerate(hist_pairs):
            pid = f"{vid}_HF_PAIR{i+1}"
            for roi, role in ((a, "early"), (b, "late")):
                roi.pair_id = pid
                roi.role = role
                roi.roi_id = f"{pid}_{role.upper()}_{int(roi.t_start)}_{int(roi.t_end)}"

        hist_centers = [(a.center_s, b.center_s) for a, b in hist_pairs]
        ef_centers = [(a.center_s, b.center_s) for a, b in ef_pairs]
        dups = fingerprint_overlap(hist_centers, ef_centers)

        if not dry_run:
            tx = time.time()
            all_rois.extend(
                pack_method_rois(vid, "histogram_first", hist_pairs, media, ab_dir, LOCAL)
            )
            all_rois.extend(
                pack_method_rois(vid, "entity_first", ef_pairs, media, ab_dir, LOCAL)
            )
            compute["extract_seconds"] += time.time() - tx

        video_results.append(
            {
                "video_id": vid,
                "genre_guess": spec["genre_guess"],
                "duration_s": dur,
                "checksum_partial_sha256": partial_sha256(media),
                "histogram_first": {
                    "n_pairs": len(hist_pairs),
                    "pairs": [
                        {
                            "pair_id": a.pair_id,
                            "early": [a.t_start, a.t_end],
                            "late": [b.t_start, b.t_end],
                            "score": a.discovery_score,
                        }
                        for a, b in hist_pairs
                    ],
                },
                "entity_first": {
                    "n_pairs": len(ef_pairs),
                    "diagnostics": ef_diag,
                    "pairs": [
                        {
                            "pair_id": a.pair_id,
                            "early": [a.t_start, a.t_end],
                            "late": [b.t_start, b.t_end],
                            "score": a.discovery_score,
                        }
                        for a, b in ef_pairs
                    ],
                },
                "cross_method_duplicates": dups,
                "budget": {
                    "max_pairs_per_method": 2,
                    "frames_per_roi": FRAMES_PER_ROI,
                    "review_frames_per_roi": REVIEW_FRAMES_PER_ROI,
                    "official_qa_answers_used_as_discovery_target": False,
                },
            }
        )

    write_jsonl(ab_dir / "rois.jsonl", all_rois)
    write_json(ab_dir / "video_results.json", {"videos": video_results, "compute": compute})

    # Blind method-hidden triage stubs filled by GPT-assisted review after frame inspect
    triage = blind_triage_ab(ab_dir, video_results)
    write_json(ab_dir / "blind_triage.json", triage)

    # Register DEV exposure (not sealed)
    selected = [
        {
            **s,
            "wave": "wp3_3_ab_dev5",
            "duration_s": next(v["duration_s"] for v in video_results if v["video_id"] == s["video_id"]),
            "checksum_partial_sha256": next(
                v["checksum_partial_sha256"] for v in video_results if v["video_id"] == s["video_id"]
            ),
            "github_visible_assets": [],
        }
        for s in AB_VIDEOS
    ]
    # register_pool_and_policy expects list with video_id; reuse carefully
    try:
        reg = register_pool_and_policy(selected)
    except Exception as e:
        reg = {"status": "MANUAL_OR_PARTIAL", "error": str(e), "videos": [s["video_id"] for s in selected]}

    summary = {
        "schema": "wp3_3_ab_prospective_discovery_v1",
        "built_utc": utc_now(),
        "baseline_commit": BASELINE,
        "videos": [s["video_id"] for s in AB_VIDEOS],
        "split": "DEV_ONLY_NOT_SEALED",
        "methods": {
            "A": "histogram_first=BOUNDED_HISTOGRAM_SCENECHANGE",
            "B": METHOD_ID,
            "B_model_stack": MODEL_STACK,
        },
        "fairness": {
            "comparable_frame_budget": True,
            "max_pairs_per_method_per_video": 2,
            "independent_generators": True,
            "not_retrospective_rerank": True,
            "official_answers_as_targets": False,
            "review_method_blinding_attempted": True,
        },
        "compute_cost_seconds": compute,
        "wall_seconds": round(time.time() - t0, 2),
        "registration": reg,
        "triage_summary": triage["summary"],
        "limitations": triage.get("limitations", []),
    }
    write_json(OUT / "wp3_3_ab_prospective_discovery.json", summary)
    write_json(REPORTS / "wp3_3_ab_prospective_discovery.json", summary)
    return {"summary": summary, "triage": triage, "video_results": video_results}


def blind_triage_ab(ab_dir: Path, video_results: list[dict]) -> dict:
    """GPT-assisted blind triage of A/B pairs.

    Labels are ADJUDICATION_DRAFT with reviewer_role=cursor_gpt_visual — NOT Human Scientific Owner Gold.
    Method ids are recorded separately after labeling to simulate blinding during judgment.
    """
    pairs_out = []
    # Pre-authored judgments from visual review of discovery outputs + sampled frames.
    # Keys are pair_ids; judgments made on content, then method attached.
    # Default conservative: most histogram pairs REJECT/HOLD; entity-first only PASS if
    # frames show bindable recurring entity without single-window shortcut.

    # We inspect available review frames after extraction; for dry structure we
    # apply conservative rules + per-video notes filled in after run.
    judgments_path = OUT / "wp3_3_ab_triage_judgments.json"
    if judgments_path.exists():
        judgments = json.loads(judgments_path.read_text())
    else:
        judgments = {"by_pair_id": {}, "notes": "filled_after_frame_review"}

    for vr in video_results:
        for method_key, method_name in (
            ("histogram_first", "histogram_first"),
            ("entity_first", "entity_first"),
        ):
            for p in vr[method_key]["pairs"]:
                pid = p["pair_id"]
                j = judgments.get("by_pair_id", {}).get(pid)
                if j is None:
                    j = {
                        "decision": "HOLD",
                        "fact_verified": False,
                        "cross_window_bind_feasible": "UNKNOWN",
                        "necessity": "UNKNOWN",
                        "qa_family": None,
                        "program_signature": None,
                        "signature_label": "PROPOSED_SIGNATURE_UNVERIFIED",
                        "failure_reason": "PENDING_FRAME_REVIEW_OR_NO_CLEAR_BIND",
                        "reviewer_role": "cursor_gpt_visual_not_human_scientific_owner",
                        "formal_gold": False,
                    }
                pairs_out.append(
                    {
                        "pair_id": pid,
                        "video_id": vr["video_id"],
                        "method_revealed_after_label": method_name,
                        "windows": {"early": p["early"], "late": p["late"]},
                        **j,
                    }
                )

    # Dedup: if HF and EF propose near-identical windows, count once for gold yield
    dedup_notes = []
    for vr in video_results:
        for d in vr.get("cross_method_duplicates") or []:
            dedup_notes.append({"video_id": vr["video_id"], **d})

    def count(method: str, pred) -> int:
        return sum(1 for p in pairs_out if p["method_revealed_after_label"] == method and pred(p))

    summary = {
        "n_pairs_total": len(pairs_out),
        "n_pairs_histogram": count("histogram_first", lambda p: True),
        "n_pairs_entity_first": count("entity_first", lambda p: True),
        "candidate_yield": {
            "histogram_first_PASS_CANDIDATE": count(
                "histogram_first", lambda p: p["decision"] == "PASS_CANDIDATE"
            ),
            "entity_first_PASS_CANDIDATE": count(
                "entity_first", lambda p: p["decision"] == "PASS_CANDIDATE"
            ),
        },
        "gold_yield": {
            "formal_gold": 0,
            "fact_verified": sum(1 for p in pairs_out if p.get("fact_verified")),
            "note": "Gold cannot be auto-promoted by GPT/Cursor",
        },
        "necessity": dict(Counter(p.get("necessity") for p in pairs_out)),
        "cross_window_bind_feasible": dict(
            Counter(p.get("cross_window_bind_feasible") for p in pairs_out)
        ),
        "dedup_cross_method": dedup_notes,
        "review_hours_estimate": round(len(pairs_out) * 0.12, 2),
    }
    return {
        "schema": "wp3_3_ab_blind_triage_v1",
        "built_utc": utc_now(),
        "pairs": pairs_out,
        "summary": summary,
        "limitations": [
            "No local semantic vision model; entity-first uses stability/fingerprint proxy + GPT visual assist",
            "Blinding is post-hoc method reveal in records; single reviewer (Cursor GPT) — not independent dual human",
            "FACT_VERIFIED requires Human Scientific Owner for Gold path; GPT labels remain draft",
            "If fairness incomplete, do not declare method winner",
        ],
    }


def write_p5_signatures(bugatti: dict, other: dict, ab: dict) -> dict:
    historical = {
        "A": {
            "ops": [
                "LocatePersonByAppearance",
                "DetectPersonAndAppearance",
                "CrossIntervalSamePersonBind",
                "QueryLocation",
            ],
            "family": "SamePersonBind→QueryLocation",
        },
        "seed_ids_checked": SEED_11,
        "frozen_5_2": FROZEN_5_2,
        "proposed_7_4": {"seen": PROPOSED_7_4_SEEN, "unseen": PROPOSED_7_4_UNSEEN, "status": "PROPOSED"},
    }
    candidates = [
        {
            "pair_id": "USfvmoalqsw_PAIR2",
            "signature": "LocatePerson→CrossIntervalSamePersonBind→QueryEarlierLocation",
            "label": "PROPOSED_SIGNATURE_UNVERIFIED",
            "bucket": "NEW_VIDEO_NEW_QA_OLD_SIGNATURE_FAMILY",
            "atomic_covered_in_seen": True,
            "novel_edge": False,
            "dataflow_novel": False,
            "video_independent": True,
            "object_swap_only": True,
            "single_window_answerable": "UNKNOWN_PENDING_HUMAN",
            "atomic_covered_ood_candidate": False,
            "freeze_unseen": False,
        },
        {
            "pair_id": "ihfjEFGdZdc_PAIR1",
            "signature": "IdentifyObject→CrossWindowObjectBind→CompareState→QueryEarlierState",
            "label": "PROPOSED_SIGNATURE_UNVERIFIED",
            "bucket": "REJECTED_FOR_OOD_CLAIM_SAME_OBJECT_NOT_ESTABLISHED",
            "atomic_covered_in_seen": True,
            "novel_edge": "CompareState_edge_unverified",
            "evidence": bugatti["cross_window"]["same_physical_object_continuity"]["verdict"],
            "atomic_covered_ood_candidate": False,
            "freeze_unseen": False,
        },
        {
            "pair_id": "W-BnDvXXfOs_PAIR2",
            "signature": "IdentifyPerson→CrossIntervalSamePersonBind→QueryEarlierCoPresentEntities",
            "label": "PROPOSED_SIGNATURE_UNVERIFIED",
            "bucket": "ID_CONTROL_CELEBRITY_LEAKAGE",
            "atomic_covered_ood_candidate": False,
            "freeze_unseen": False,
        },
    ]
    # Add AB pass signatures if any
    for p in ab["triage"]["pairs"]:
        if p.get("program_signature") and p["decision"] == "PASS_CANDIDATE":
            candidates.append(
                {
                    "pair_id": p["pair_id"],
                    "signature": p["program_signature"],
                    "label": p.get("signature_label") or "PROPOSED_SIGNATURE_UNVERIFIED",
                    "bucket": "AB_DEV_DRAFT",
                    "method": p["method_revealed_after_label"],
                    "atomic_covered_ood_candidate": False,
                    "freeze_unseen": False,
                }
            )

    doc = {
        "schema": "wp3_3_composition_signature_audit_v1",
        "built_utc": utc_now(),
        "historical": historical,
        "candidates": candidates,
        "counts": {
            "proposed_signature_unverified": sum(
                1 for c in candidates if c.get("label") == "PROPOSED_SIGNATURE_UNVERIFIED"
            ),
            "atomic_covered_ood_candidate": sum(
                1 for c in candidates if c.get("atomic_covered_ood_candidate")
            ),
            "frozen_unseen_promotions": 0,
        },
        "independent_signature_growth": {
            "new_verified_independent_signatures": 0,
            "note": "No evidence+signature dual pass this round for OOD freeze",
        },
        "frozen_5_2_unchanged": True,
        "proposed_7_4_status": "PROPOSED",
    }
    write_json(OUT / "wp3_3_composition_signature_audit.json", doc)
    write_json(REPORTS / "wp3_3_composition_signature_audit.json", doc)
    return doc


def write_final_report(p0, p1, p2, ab, p5) -> dict:
    triage = ab["triage"]["summary"]
    review_h = triage.get("review_hours_estimate") or 1.0
    pass_cand = (
        triage["candidate_yield"]["histogram_first_PASS_CANDIDATE"]
        + triage["candidate_yield"]["entity_first_PASS_CANDIDATE"]
    )
    # Effective after voice CONTROL + bugatti downgrade from prior waves
    effective = {
        "prior_wave_pass_still_effective": 0,
        "usfv_pair2_pending": 1,
        "bugatti_same_object": 0,
        "voice_control": 1,
        "ab_pass_candidates": pass_cand,
        "formal_gold": 0,
        "fact_verified": triage["gold_yield"]["fact_verified"],
    }
    scale = {
        "recommend_expand_to_50_100_qa": False,
        "basis": [
            "Prospective A/B did not yet demonstrate reliable repeatable Gold-grade compositional discovery",
            "Entity-first lacks local semantic model; GPT-assisted proxy ≠ automated discovery win",
            "Human identity adjudication still bottleneck (PAIR2 pending)",
            "Bugatti high-potential downgraded: montage ≠ same-object state change",
            "Cost per effective Gold remains dominated by Human certification, not scan volume",
        ],
        "when_to_reconsider": [
            "Human confirms ≥1 new bindable cross-window relation on AB DEV with Necessity PASS",
            "Entity-first prospective yield > histogram under matched budget on ≥5 videos with FACT_VERIFIED",
            "Independent dual-human review bandwidth available",
        ],
    }
    report = {
        "schema": "wp3_3_compositional_evidence_scale_report_v1",
        "work_package": "WP3.3",
        "baseline_commit": BASELINE,
        "built_utc": utc_now(),
        "deliverables": {
            "p0_clarification": p0["corrected_supported_claim"],
            "p1_bugatti": p1["cross_window"]["same_physical_object_continuity"]["verdict"],
            "p2_other": {
                "USfvmoalqsw_PAIR2": p2["USfvmoalqsw_PAIR2"]["relation_status"],
                "W-BnDvXXfOs_PAIR2": p2["W-BnDvXXfOs_PAIR2"]["updated_status"],
            },
            "p3_entity_first_method": METHOD_ID,
            "p3_not_fully_automated": True,
            "p4_ab_videos": ab["summary"]["videos"],
            "p5_signature_growth": p5["independent_signature_growth"],
        },
        "counts": {
            "FACT_VERIFIED": effective["fact_verified"],
            "Necessity_PASS": triage["necessity"].get("PASS", 0),
            "Necessity_FAIL": triage["necessity"].get("FAIL", 0),
            "Necessity_UNKNOWN": triage["necessity"].get("UNKNOWN", 0),
            "formal_gold": 0,
            "candidate_yield_ab": triage["candidate_yield"],
            "gold_yield_ab": triage["gold_yield"],
        },
        "effective_inventory": effective,
        "yield_per_review_hour": {
            "candidate_pass_per_hour": round(pass_cand / max(review_h, 0.01), 3),
            "gold_per_hour": 0.0,
            "review_hours_estimate": review_h,
        },
        "scale_recommendation": scale,
        "protections": {
            "immutable_releases": ["v0.1.0", "v0.1.1", "v0.1.2"],
            "frozen_5_2_unchanged": True,
            "proposed_7_4": "PROPOSED",
            "track_a_experiments_run": False,
            "no_public_third_party_media_added": True,
            "no_gpt_auto_gold": True,
        },
        "artifacts": {
            "clarification": str((OUT / "WP3_3_DISCOVERY_EVAL_CLARIFICATION.json").relative_to(REPO_ROOT)),
            "bugatti": str((OUT / "wp3_3_bugatti_ihfjEFGdZdc_evidence_audit.json").relative_to(REPO_ROOT)),
            "other": str((OUT / "wp3_3_other_candidate_status.json").relative_to(REPO_ROOT)),
            "ab": str((OUT / "wp3_3_ab_prospective_discovery.json").relative_to(REPO_ROOT)),
            "signatures": str((OUT / "wp3_3_composition_signature_audit.json").relative_to(REPO_ROOT)),
            "entity_first_module": "research_audit/lvbench_compositional/track_b/LongVideoCompBench/tools/wp3_3_entity_first_discovery.py",
        },
    }
    write_json(OUT / "WP3_3_COMPOSITIONAL_EVIDENCE_SCALE_REPORT.json", report)
    write_json(REPORTS / "WP3_3_COMPOSITIONAL_EVIDENCE_SCALE_REPORT.json", report)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-ab", action="store_true")
    ap.add_argument("--ab-only", action="store_true")
    ap.add_argument("--dry-run-ab", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if not args.ab_only:
        p0 = write_p0_clarification()
        p1 = write_p1_bugatti_audit()
        p2 = write_p2_other_candidates()
    else:
        p0 = json.loads((OUT / "WP3_3_DISCOVERY_EVAL_CLARIFICATION.json").read_text())
        p1 = json.loads((OUT / "wp3_3_bugatti_ihfjEFGdZdc_evidence_audit.json").read_text())
        p2 = json.loads((OUT / "wp3_3_other_candidate_status.json").read_text())

    if args.skip_ab:
        ab = {
            "summary": json.loads((OUT / "wp3_3_ab_prospective_discovery.json").read_text()),
            "triage": json.loads((OUT / "ab_dev5" / "blind_triage.json").read_text()),
            "video_results": [],
        }
    else:
        ab = run_p4_ab(dry_run=args.dry_run_ab)

    p5 = write_p5_signatures(p1, p2, ab)
    report = write_final_report(p0, p1, p2, ab, p5)
    print(json.dumps({
        "p0": p0["corrected_supported_claim"],
        "bugatti_same_object": p1["cross_window"]["same_physical_object_continuity"]["verdict"],
        "voice": p2["W-BnDvXXfOs_PAIR2"]["updated_status"],
        "ab_videos": ab["summary"]["videos"],
        "counts": report["counts"],
        "scale": report["scale_recommendation"]["recommend_expand_to_50_100_qa"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
