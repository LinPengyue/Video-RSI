#!/usr/bin/env python3
"""Engineering-only builder for the scientific certification workbench.
Does NOT fill Seen/Unseen, necessity PASS/FAIL, or directed-program conclusions.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = Path(__file__).resolve().parent
MEDIA = WB / "media"
AUDIT = ROOT.parent  # research_audit/lvbench_compositional


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def link_media(src: Path, name: str) -> dict:
    MEDIA.mkdir(parents=True, exist_ok=True)
    dst = MEDIA / name
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    os.symlink(os.path.relpath(src, MEDIA), dst)
    exists = src.exists()
    return {
        "served_as": f"media/{name}",
        "source_path": str(src.relative_to(ROOT)) if str(src).startswith(str(ROOT)) else str(src),
        "bytes": src.stat().st_size if exists else None,
        "exists": exists,
        "sha256": sha256_file(src) if exists else None,
        "is_mp4_ftyp": (src.read_bytes()[4:8] == b"ftyp") if exists and src.stat().st_size > 12 else False,
    }


def empty_judgments() -> dict:
    return {
        "a_only_sufficient": "",
        "b_only_sufficient": "",
        "a_plus_b_supports_user_answer": "",
        "truly_needs_cross_clip_composition": "",
        "directed_program_structure": "",
        "bucket_seen_unseen_control_or_hold": "",
        "rationale_and_open_issues": "",
        "filled_by": "",
        "filled_utc": "",
    }


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def intervals_overlap(a, b) -> bool:
    return max(a[0], b[0]) < min(a[1], b[1])


def probe_playable(path: Path) -> dict:
    out = {"path": str(path), "exists": path.exists(), "ffprobe_ok": None, "codec": None, "duration_s": None}
    if not path.exists():
        return out
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name,duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            streams = data.get("streams") or []
            if streams:
                out["ffprobe_ok"] = True
                out["codec"] = streams[0].get("codec_name")
                try:
                    out["duration_s"] = float(streams[0].get("duration") or 0) or None
                except (TypeError, ValueError):
                    out["duration_s"] = None
            else:
                out["ffprobe_ok"] = False
                out["error"] = "no video stream"
        else:
            out["ffprobe_ok"] = False
            out["error"] = (r.stderr or r.stdout or "ffprobe_failed")[:300]
    except FileNotFoundError:
        out["ffprobe_ok"] = None
        out["error"] = "ffprobe_not_available"
    except Exception as e:
        out["ffprobe_ok"] = False
        out["error"] = str(e)[:300]
    return out


def main() -> None:
    vtcd_review = load_json("round_002/user_reviews/VTCD_USER_REVIEW_2026-11-01.json")
    vtcd_qa = load_json("round_002/qa_candidates/VTCD_COMPOSITIONAL_QA_CANDIDATES.json")
    tjr = load_json("round_003/TJR_USER_QA_REVISION_2026-11-01.json")
    r4_raw = load_json("round_004/user_reviews/ROUND4_USER_REVIEW_2026-11-02_RAW.json")
    r4_conf = load_json("round_004/user_reviews/ROUND4_USER_CONFIRMED_QA_REVISION_2026-11-02.json")
    r4_man = load_json("round_004/media_manifest.json")
    vtcd_man = load_json("round_002/vtcd_review/media_manifest.json")
    blind_c2 = load_json("round_004/certification/independent_review_packets/P7_VTCD_C2_blind_packet.json")
    blind_c4 = load_json("round_004/certification/independent_review_packets/P7_VTCD_C4_blind_packet.json")
    ans_keys = load_json("round_004/certification/ANSWER_KEYS_DO_NOT_SERVE_TO_REVIEWER.json")["keys"]

    sierra = {}
    with (AUDIT / "pilot_v2_2/test_video_review.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["id"] in ("LVCOMP-V2-002", "LVCOMP-V2-003"):
                sierra[row["id"]] = row

    media_pairs = [
        ("vtcd_A_context_158_191.mp4", ROOT / "round_002/vtcd_review/media/A_context_158_191.mp4"),
        ("vtcd_B_context_260_285.mp4", ROOT / "round_002/vtcd_review/media/B_context_260_285.mp4"),
        ("vtcd_A_core_browser_163_186.mp4", ROOT / "round_002/vtcd_review/media/A_core_browser_163_186.mp4"),
        ("vtcd_B_core_browser_265_280.mp4", ROOT / "round_002/vtcd_review/media/B_core_browser_265_280.mp4"),
        ("tjr_A_1100_1125.mp4", ROOT / "round_002/tjr_relocate/media/early_candidate_dragon_ride_1100_1125.mp4"),
        ("tjr_B_1200_1220.mp4", ROOT / "round_002/tjr_relocate/media/late_dual_performers_1200_1220.mp4"),
        ("F1A_restaurant_259_295.mp4", ROOT / "round_004/media/F1A_restaurant_259_295.mp4"),
        ("F1B_snow_2995_3015.mp4", ROOT / "round_004/media/F1B_snow_2995_3015.mp4"),
        ("F2A_dog_wood_20_45.mp4", ROOT / "round_004/media/F2A_dog_wood_20_45.mp4"),
        ("F2B_later_play_123_165.mp4", ROOT / "round_004/media/F2B_later_play_123_165.mp4"),
        ("F3A_race_intro_125_190.mp4", ROOT / "round_004/media/F3A_race_intro_125_190.mp4"),
        ("F3B_result_board_290_340.mp4", ROOT / "round_004/media/F3B_result_board_290_340.mp4"),
        ("F4A_bioprint_1055_1065.mp4", ROOT / "round_004/media/F4A_bioprint_1055_1065.mp4"),
        ("F4A_bioprint_1055_1070.mp4", ROOT / "round_004/media/F4A_bioprint_1055_1070.mp4"),  # historical superseded
        ("F4B_plated_insert_1065_1075.mp4", ROOT / "round_004/media/F4B_plated_insert_1065_1075.mp4"),
        ("S1_sierra_id_35_45.mp4", ROOT / "round_004/media/S1_sierra_id_35_45.mp4"),
        ("S2_remove_shoe_125_135.mp4", ROOT / "round_004/media/S2_remove_shoe_125_135.mp4"),
        ("S3_score_00_1785_1805.mp4", ROOT / "round_004/media/S3_score_00_1785_1805.mp4"),
        ("S4_fan_text_A_178_190.mp4", ROOT / "round_004/media/S4_fan_text_A_178_190.mp4"),
        ("sierra_calib_id_35_45.mp4", ROOT / "local_media/JTa_Ue2MSwc/sierra_id_35_45.mp4"),
        ("sierra_calib_remove_shoe_125_135.mp4", ROOT / "local_media/JTa_Ue2MSwc/remove_shoe_125_135.mp4"),
        ("sierra_calib_slap_lunge_335_350.mp4", ROOT / "local_media/JTa_Ue2MSwc/slap_lunge_335_350.mp4"),
    ]
    media_index = {name: link_media(src, name) for name, src in media_pairs}

    conf_by_id = {x["id"]: x for x in r4_conf["user_confirmed_revisions"]}
    raw_by_id = {x["id"]: x for x in r4_raw["structure_candidates"]}
    seen_raw = {x["id"]: x for x in r4_raw["seen_primitives"]}
    c2_en = next(c for c in vtcd_qa["candidates"] if c["candidate_id"].startswith("VTCD_C2"))
    c4_en = next(c for c in vtcd_qa["candidates"] if c["candidate_id"].startswith("VTCD_C4"))

    items = []

    items.append(
        {
            "workbench_id": "P7_VTCD_C2",
            "section": "p7_composition_candidates",
            "qa_uid": "P7_VTCD_C2",
            "video_id": "VTCDQYYKA9o",
            "intervals": {
                "A_source_s": [158.0, 191.0],
                "B_source_s": [260.0, 285.0],
                "A_core_s": [163.0, 186.0],
                "B_core_s": [265.0, 280.0],
                "user_approx_events": {
                    "remove_jacket_source_s_approx": [168.0, 170.0],
                    "fan_text_A_source_s_approx": 184.0,
                    "fan_text_B_source_s_approx": 269.0,
                },
                "timestamp_precision": "APPROXIMATE_FROM_USER_PLAYBACK_OFFSETS_NOT_FRAME_ACCURATE",
            },
            "clips": {
                "A": "media/vtcd_A_context_158_191.mp4",
                "B": "media/vtcd_B_context_260_285.mp4",
            },
            "user_final_qa": {
                "question_zh": blind_c2["frozen_question"],
                "answer_zh": ans_keys["P7_VTCD_C2"],
                "question_en_candidate_source": c2_en["question_en"],
                "answer_en_candidate_source": c2_en["expected_answer"],
                "status": "USER_ACCEPTED_QA_CANDIDATE",
                "composition_necessity_status": "NOT_TESTED",
            },
            "identity_and_events": {
                "event_A": "REMOVE_JACKET / 脱下外套",
                "identity": "SAME_PERSON",
                "basis": "Fan Zhendong text in A and B (user)",
            },
            "history_refs": [
                "round_002/user_reviews/VTCD_USER_REVIEW_2026-11-01.json",
                "round_002/qa_candidates/VTCD_COMPOSITIONAL_QA_CANDIDATES.json",
            ],
            "history_payload": {"vtcd_user_review": vtcd_review, "candidate_en": c2_en},
            "scientific_judgment_fields": empty_judgments(),
            "note": "Expert evidence-dependency workbench — NOT independent blind review.",
        }
    )

    items.append(
        {
            "workbench_id": "P7_VTCD_C4",
            "section": "p7_composition_candidates",
            "qa_uid": "P7_VTCD_C4",
            "video_id": "VTCDQYYKA9o",
            "intervals": {
                "A_source_s": [158.0, 191.0],
                "B_source_s": [260.0, 285.0],
                "user_approx_events": {
                    "remove_jacket_source_s_approx": [168.0, 170.0],
                    "previous_results_fan_B_source_s_approx": 269.0,
                },
                "timestamp_precision": "APPROXIMATE_FROM_USER_PLAYBACK_OFFSETS_NOT_FRAME_ACCURATE",
            },
            "clips": {
                "A": "media/vtcd_A_context_158_191.mp4",
                "B": "media/vtcd_B_context_260_285.mp4",
            },
            "user_final_qa": {
                "question_zh": blind_c4["frozen_question"],
                "answer_zh": ans_keys["P7_VTCD_C4"],
                "question_en_candidate_source": c4_en["question_en"],
                "answer_en_candidate_source": c4_en["expected_answer"],
                "status": "USER_ACCEPTED_QA_CANDIDATE",
                "composition_necessity_status": "NOT_TESTED",
                "wording_hazard": c4_en.get("wording_hazard"),
            },
            "identity_and_events": {"event_A": "REMOVE_JACKET", "identity": "SAME_PERSON"},
            "history_refs": [
                "round_002/user_reviews/VTCD_USER_REVIEW_2026-11-01.json",
                "round_002/qa_candidates/VTCD_COMPOSITIONAL_QA_CANDIDATES.json",
            ],
            "history_payload": {"vtcd_user_review": vtcd_review, "candidate_en": c4_en},
            "scientific_judgment_fields": empty_judgments(),
            "note": "Expert evidence-dependency workbench — NOT independent blind review.",
        }
    )

    rev = tjr["latest_user_explicit_revision"]
    items.append(
        {
            "workbench_id": "P7_TJR_R3",
            "section": "p7_composition_candidates",
            "qa_uid": "P7_TJR_R3",
            "video_id": "TJR1oYDDTwg",
            "intervals": {
                "A_source_s": tjr["source_intervals_s"]["A"],
                "B_source_s": tjr["source_intervals_s"]["B"],
            },
            "clips": {"A": "media/tjr_A_1100_1125.mp4", "B": "media/tjr_B_1200_1220.mp4"},
            "user_final_qa": {
                "question_zh": rev["revised_question_zh"],
                "answer_zh": rev["revised_answer_zh"],
                "status": rev["draft_status"],
                "composition_necessity_status": "NOT_TESTED",
                "prior_accepted_question_zh": tjr["user_review_sources"][1].get("question_candidate"),
                "prior_answer_field_zh": tjr["user_review_sources"][1].get("question_reason_or_answer"),
                "prior_qa_decision": tjr["user_review_sources"][1].get("question_review"),
            },
            "identity_and_events": {
                "identity": "SAME_PERSON",
                "A_obs": tjr["user_review_sources"][1]["user_event_observation_A"],
                "B_obs": tjr["user_review_sources"][1]["user_event_observation_B"],
                "same_person_reason": tjr["user_review_sources"][1]["same_person_reason"],
            },
            "history_refs": ["round_003/TJR_USER_QA_REVISION_2026-11-01.json"],
            "history_payload": tjr,
            "scientific_judgment_fields": empty_judgments(),
            "note": "Expert evidence-dependency workbench — NOT independent blind review.",
        }
    )

    clip_map = {
        "R4_F1": ("media/F1A_restaurant_259_295.mp4", "media/F1B_snow_2995_3015.mp4", [259, 295], [2995, 3015]),
        "R4_F2": ("media/F2A_dog_wood_20_45.mp4", "media/F2B_later_play_123_165.mp4", [20, 45], [123, 165]),
        "R4_F3": ("media/F3A_race_intro_125_190.mp4", "media/F3B_result_board_290_340.mp4", [125, 190], [290, 340]),
    }
    for fid in ["R4_F1", "R4_F2", "R4_F3"]:
        c = conf_by_id[fid]
        raw = raw_by_id[fid]
        a, b, ia, ib = clip_map[fid]
        items.append(
            {
                "workbench_id": f"P7_{fid}",
                "section": "p7_composition_candidates",
                "qa_uid": f"P7_{fid}",
                "video_id": c["video_id"],
                "intervals": {"A_source_s": ia, "B_source_s": ib},
                "clips": {"A": a, "B": b},
                "user_final_qa": {
                    "question_zh": c["user_confirmed_question"],
                    "answer_zh": c["user_confirmed_answer"],
                    "status": c["status"],
                    "source_qa_decision": c["source_qa_decision"],
                    "source_original_question": c["source_original_question"],
                    "source_original_answer_or_revision_field": c.get(
                        "source_original_answer", c.get("source_answer_field_was_revision_not_answer")
                    ),
                    "user_literal_wording_preserved": c.get("user_literal_wording_preserved"),
                    "wording_caveat": c.get("wording_caveat"),
                    "evidence_caveat": c.get("evidence_caveat"),
                    "composition_necessity_status": "NOT_TESTED",
                },
                "identity_and_events": {
                    "obs_A": raw["obs_A"],
                    "obs_B": raw["obs_B"],
                    "identity": raw.get("identity"),
                    "identity_reason": raw.get("identity_reason"),
                    "raw_qa_decision": raw["qa_decision"],
                    "raw_question": raw["question"],
                    "raw_answer_field": raw["answer"],
                },
                "history_refs": [
                    "round_004/user_reviews/ROUND4_USER_REVIEW_2026-11-02_RAW.json",
                    "round_004/user_reviews/ROUND4_USER_CONFIRMED_QA_REVISION_2026-11-02.json",
                ],
                "history_payload": {"confirmed": c, "raw": raw},
                "scientific_judgment_fields": empty_judgments(),
                "note": "F3 literal wording preserved without polish." if fid == "R4_F3" else "Expert evidence-dependency workbench — NOT independent blind review.",
            }
        )

    f4u = r4_conf["f4_unchanged"]
    f4r = raw_by_id["R4_F4"]
    items.append(
        {
            "workbench_id": "P7_R4_F4",
            "section": "p7_composition_candidates",
            "qa_uid": "P7_R4_F4",
            "video_id": f4u["video_id"],
            "intervals": {
                "A_source_s": [1055, 1065],
                "B_source_s": [1065, 1075],
                "overlap_note": "Overlap removed by user-approved A crop; intervals abut at 1065s",
                "A_previous_source_s": [1055, 1070],
                "previous_overlap_seconds": 5,
            },
            "clips": {
                "A": "media/F4A_bioprint_1055_1065.mp4",
                "B": "media/F4B_plated_insert_1065_1075.mp4",
                "A_historical_superseded": "media/F4A_bioprint_1055_1070.mp4",
            },
            "user_final_qa": {
                "question_zh": f4u["original_question"],
                "answer_zh": f4u["original_answer"],
                "status": "USER_ACCEPT_HELD",
                "raw_relation": f4u["raw_relation"],
                "user_instruction": f4u["user_instruction"],
                "interpretation_note": f4u["interpretation_note"],
                "composition_necessity_status": "NOT_TESTED",
            },
            "identity_and_events": {
                "obs_A": f4r["obs_A"],
                "obs_B": f4r["obs_B"],
                "relation": f4r["relation"],
                "relation_reason": f4r["relation_reason"],
            },
            "history_refs": [
                "round_004/user_reviews/ROUND4_USER_REVIEW_2026-11-02_RAW.json",
                "round_004/user_reviews/ROUND4_USER_CONFIRMED_QA_REVISION_2026-11-02.json",
            ],
            "history_payload": {"confirmed_policy": f4u, "raw": f4r},
            "scientific_judgment_fields": empty_judgments(),
            "note": "Preserve BOTH user reference interpretation AND raw EDIT_JUXTAPOSITION. No Gold upgrade.",
        }
    )

    items.append(
        {
            "workbench_id": "TA_LVCOMP-V2-002",
            "section": "track_a_sierra_calibration",
            "qa_uid": "LVCOMP-V2-002",
            "video_id": "JTa_Ue2MSwc",
            "role_note": "HISTORICAL_CALIBRATION_ONLY — not a new P7 family",
            "intervals": {
                "time_references": sierra["LVCOMP-V2-002"]["time_references"],
                "evidence_timestamp": sierra["LVCOMP-V2-002"]["evidence_timestamp"],
                "clips_approximate_source_s": {"id_graphic": [35, 45], "remove_shoe": [125, 135]},
            },
            "clips": {
                "A": "media/sierra_calib_id_35_45.mp4",
                "B": "media/sierra_calib_remove_shoe_125_135.mp4",
            },
            "user_final_qa": {
                "question_en": sierra["LVCOMP-V2-002"]["question"],
                "answer_en": sierra["LVCOMP-V2-002"]["answer"],
                "status": "TRACK_A_HISTORICALLY_SUPPORTED",
                "source_fact_status": sierra["LVCOMP-V2-002"]["source_fact_status"],
                "composition_status": sierra["LVCOMP-V2-002"]["composition_status"],
            },
            "history_refs": ["pilot_v2_2/test_video_review.csv", "pilot_v2_2/judgments.json"],
            "history_payload": {"csv_row": sierra["LVCOMP-V2-002"]},
            "scientific_judgment_fields": empty_judgments(),
        }
    )
    items.append(
        {
            "workbench_id": "TA_LVCOMP-V2-003",
            "section": "track_a_sierra_calibration",
            "qa_uid": "LVCOMP-V2-003",
            "video_id": "JTa_Ue2MSwc",
            "role_note": "HISTORICAL_CALIBRATION_ONLY",
            "intervals": {
                "time_references": sierra["LVCOMP-V2-003"]["time_references"],
                "evidence_timestamp": sierra["LVCOMP-V2-003"]["evidence_timestamp"],
                "clips_approximate_source_s": {"id_graphic": [35, 45], "slap_lunge": [335, 350]},
            },
            "clips": {
                "A": "media/sierra_calib_id_35_45.mp4",
                "B": "media/sierra_calib_slap_lunge_335_350.mp4",
            },
            "user_final_qa": {
                "question_en": sierra["LVCOMP-V2-003"]["question"],
                "answer_en": sierra["LVCOMP-V2-003"]["answer"],
                "status": "TRACK_A_HISTORICALLY_SUPPORTED",
                "source_fact_status": sierra["LVCOMP-V2-003"]["source_fact_status"],
                "composition_status": sierra["LVCOMP-V2-003"]["composition_status"],
            },
            "history_refs": ["pilot_v2_2/test_video_review.csv", "pilot_v2_2/judgments.json"],
            "history_payload": {"csv_row": sierra["LVCOMP-V2-003"]},
            "scientific_judgment_fields": empty_judgments(),
        }
    )

    seen_clips = {
        "R4_S1": ("media/S1_sierra_id_35_45.mp4", "JTa_Ue2MSwc", [35, 45]),
        "R4_S2": ("media/S2_remove_shoe_125_135.mp4", "JTa_Ue2MSwc", [125, 135]),
        "R4_S3": ("media/S3_score_00_1785_1805.mp4", "T1yhBv1ytzw", [1785, 1805]),
        "R4_S4": ("media/S4_fan_text_A_178_190.mp4", "VTCDQYYKA9o", [178, 190]),
    }
    for sid, (clip, vid, win) in seen_clips.items():
        items.append(
            {
                "workbench_id": f"P7_{sid}",
                "section": "round4_seen_primitive_observations",
                "qa_uid": f"P7_{sid}",
                "video_id": vid,
                "intervals": {"source_s": win},
                "clips": {"single": clip},
                "user_final_qa": {
                    "observation_accepted": seen_raw[sid]["obs"],
                    "decision": seen_raw[sid]["decision"],
                    "status": "USER_ACCEPTED_SEEN_PRIMITIVE_OBSERVATION",
                    "note": "Observation accept ≠ formal train Seen entry",
                },
                "history_refs": ["round_004/user_reviews/ROUND4_USER_REVIEW_2026-11-02_RAW.json"],
                "history_payload": {"raw_entry": seen_raw[sid]},
                "scientific_judgment_fields": empty_judgments(),
            }
        )

    catalog = {
        "workbench_id": "P7_SCIENTIFIC_CERTIFICATION_WORKBENCH_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "skill_ref": "USER_GPT_SCIENTIFIC_REVIEW_SKILL_v2.md",
        "skill_git_sha_at_build": "cf74c0a30ec9e9aaef73ec193ac0b537fe5dc9ee",
        "purpose": "Engineering workbench for USER+GPT scientific certification. Cursor does not adjudicate.",
        "disclaimer": "Known-answer expert evidence-dependency review. NOT independent blind adjudication.",
        "cursor_boundary": {
            "no_scientific_pass_fail": True,
            "no_autofill_seen_unseen": True,
            "structure_leaveout_v1": "HISTORICAL_DRAFT_ONLY_NOT_USER_APPROVED",
            "no_gold_upgrade": True,
        },
        "counts": {
            "p7_user_accepted_or_confirmed_qa_candidates": 7,
            "track_a_sierra_calibration_qa": 2,
            "round4_seen_primitive_observations": 4,
            "formal_qualified_families": 0,
            "formal_gold": 0,
        },
        "media_index": media_index,
        "items": items,
    }
    (WB / "WORKBENCH_CATALOG.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    (WB / "SCIENTIFIC_JUDGMENTS_BLANK.json").write_text(
        json.dumps(
            {
                "schema_note": "Fill ONLY by USER/GPT. Cursor must not auto-complete.",
                "items": {it["workbench_id"]: empty_judgments() for it in items},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # --- engineering checks ---
    checks = {
        "check_id": "P7_WORKBENCH_ENGINEERING_CHECKS_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Deterministic engineering facts only — not scientific conclusions",
        "media_existence_and_manifest": [],
        "playability_probe": [],
        "interval_overlaps_within_item": [],
        "qa_uid_duplicates": [],
        "video_id_inventory": {},
        "hypothetical_split_leakage": {
            "status": "N_A_NO_USER_APPROVED_TRAIN_TEST_SPLIT",
            "note": "No user/GPT-approved formal split provided. Engineering checker ready; no cross train/test claim made.",
            "same_video_appearing_in_multiple_workbench_roles": {},
        },
        "summary": {},
    }

    # Round4 manifest consistency
    for clip in r4_man["clips"]:
        src = ROOT / "round_004/media" / clip["file"]
        entry = {
            "manifest": "round_004/media_manifest.json",
            "file": clip["file"],
            "video_id": clip["video_id"],
            "t_start_s": clip["t_start_s"],
            "t_end_s": clip["t_end_s"],
            "manifest_bytes": clip["bytes"],
            "manifest_sha256": clip["sha256"],
            "exists": src.exists(),
            "actual_bytes": src.stat().st_size if src.exists() else None,
            "actual_sha256": sha256_file(src) if src.exists() else None,
        }
        entry["bytes_match"] = entry["exists"] and entry["actual_bytes"] == entry["manifest_bytes"]
        entry["sha256_match"] = entry["exists"] and entry["actual_sha256"] == entry["manifest_sha256"]
        checks["media_existence_and_manifest"].append(entry)

    # VTCD manifest subset used by workbench
    for clip in vtcd_man["clips"]:
        if clip["clip_id"] not in ("A_context_158_191", "B_context_260_285", "A_core_browser_163_186", "B_core_browser_265_280"):
            continue
        src = Path(clip["absolute_path"])
        entry = {
            "manifest": "round_002/vtcd_review/media_manifest.json",
            "file": clip["relative_path"],
            "video_id": clip["video_id"],
            "t_start_s": clip["source_t_start_s"],
            "t_end_s": clip["source_t_end_s"],
            "manifest_bytes": clip["bytes"],
            "manifest_sha256": clip["sha256"],
            "exists": src.exists(),
            "actual_bytes": src.stat().st_size if src.exists() else None,
            "actual_sha256": sha256_file(src) if src.exists() else None,
        }
        entry["bytes_match"] = entry["exists"] and entry["actual_bytes"] == entry["manifest_bytes"]
        entry["sha256_match"] = entry["exists"] and entry["actual_sha256"] == entry["manifest_sha256"]
        checks["media_existence_and_manifest"].append(entry)

    # TJR files (no dedicated sha manifest historically)
    for label, rel, t0, t1, vid in [
        ("tjr_A", "round_002/tjr_relocate/media/early_candidate_dragon_ride_1100_1125.mp4", 1100, 1125, "TJR1oYDDTwg"),
        ("tjr_B", "round_002/tjr_relocate/media/late_dual_performers_1200_1220.mp4", 1200, 1220, "TJR1oYDDTwg"),
        ("sierra_id", "local_media/JTa_Ue2MSwc/sierra_id_35_45.mp4", 35, 45, "JTa_Ue2MSwc"),
        ("sierra_shoe", "local_media/JTa_Ue2MSwc/remove_shoe_125_135.mp4", 125, 135, "JTa_Ue2MSwc"),
        ("sierra_slap", "local_media/JTa_Ue2MSwc/slap_lunge_335_350.mp4", 335, 350, "JTa_Ue2MSwc"),
    ]:
        src = ROOT / rel
        checks["media_existence_and_manifest"].append(
            {
                "manifest": "none_sha_recorded_prior",
                "file": rel,
                "label": label,
                "video_id": vid,
                "t_start_s": t0,
                "t_end_s": t1,
                "exists": src.exists(),
                "actual_bytes": src.stat().st_size if src.exists() else None,
                "actual_sha256": sha256_file(src) if src.exists() else None,
                "bytes_match": None,
                "sha256_match": None,
            }
        )

    # playability for each served media
    for name, meta in media_index.items():
        p = MEDIA / name
        probe = probe_playable(p.resolve() if p.exists() else p)
        probe["served_as"] = meta["served_as"]
        probe["is_mp4_ftyp"] = meta["is_mp4_ftyp"]
        checks["playability_probe"].append(probe)

    # overlaps + uid/video inventory
    uid_seen = {}
    for it in items:
        uid = it["qa_uid"]
        uid_seen.setdefault(uid, []).append(it["workbench_id"])
        checks["video_id_inventory"].setdefault(it["video_id"], []).append(it["workbench_id"])
        iv = it.get("intervals") or {}
        a = iv.get("A_source_s")
        b = iv.get("B_source_s")
        if a and b:
            ov = intervals_overlap(a, b)
            checks["interval_overlaps_within_item"].append(
                {
                    "workbench_id": it["workbench_id"],
                    "video_id": it["video_id"],
                    "A_source_s": a,
                    "B_source_s": b,
                    "overlap": ov,
                    "overlap_seconds": (min(a[1], b[1]) - max(a[0], b[0])) if ov else 0,
                }
            )

    checks["qa_uid_duplicates"] = [{k: v} for k, v in uid_seen.items() if len(v) > 1]
    checks["hypothetical_split_leakage"]["same_video_appearing_in_multiple_workbench_roles"] = {
        vid: ids for vid, ids in checks["video_id_inventory"].items() if len(ids) > 1
    }

    man_ok = all(
        (e.get("bytes_match") in (True, None)) and (e.get("sha256_match") in (True, None)) and e.get("exists")
        for e in checks["media_existence_and_manifest"]
    )
    play_ok = all(p.get("exists") and p.get("is_mp4_ftyp") for p in checks["playability_probe"])
    ffprobe_any = any(p.get("ffprobe_ok") is True for p in checks["playability_probe"])
    ffprobe_fail = [p for p in checks["playability_probe"] if p.get("ffprobe_ok") is False]
    checks["summary"] = {
        "all_media_exist": all(e.get("exists") for e in checks["media_existence_and_manifest"]),
        "round_manifest_sha_bytes_ok_where_applicable": man_ok,
        "all_served_media_mp4_ftyp": play_ok,
        "ffprobe_available_and_any_ok": ffprobe_any,
        "ffprobe_failures": len(ffprobe_fail),
        "items_with_ab_overlap": sum(1 for x in checks["interval_overlaps_within_item"] if x["overlap"]),
        "duplicate_qa_uids": len(checks["qa_uid_duplicates"]),
        "unique_video_ids": len(checks["video_id_inventory"]),
        "missing_media": [e["file"] for e in checks["media_existence_and_manifest"] if not e.get("exists")],
    }
    (WB / "ENGINEERING_CHECKS.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"items": len(items), "media": len(media_index), "summary": checks["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
