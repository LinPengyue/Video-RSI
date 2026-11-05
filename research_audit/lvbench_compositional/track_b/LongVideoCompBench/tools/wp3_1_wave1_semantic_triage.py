#!/usr/bin/env python3
"""WP3.1: Wave1 GPT/Cursor frame semantic triage + relation feasibility audit.

Does NOT mark CONTINUOUS_VIDEO_VERIFIED from stills.
Does NOT auto-upgrade Formal Gold / Human Approved.
Does NOT delete low-priority Wave1 history.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DS_ROOT, REPO_ROOT, utc_now, write_json, write_jsonl  # noqa: E402

BASELINE = "1fbe837790fc94de2fd76c616c0578b9c4dec524"
WAVE1 = DS_ROOT / "wp3_production" / "wave1"
OUT = DS_ROOT / "wp3_production" / "WP3_WAVE1_GPT_SEMANTIC_TRIAGE_AND_RELATION_AUDIT.json"
OUT_COPY = DS_ROOT / "reports" / "WP3_WAVE1_GPT_SEMANTIC_TRIAGE_AND_RELATION_AUDIT.json"

PRIORITY_ORDER = [
    "USfvmoalqsw_PAIR2",
    "gXnhqF0TqqI_PAIR1",
    "KktLi3UifPY_PAIR2",
    "USfvmoalqsw_PAIR1",
    "16Z-XQh9jhk_PAIR2",
]


def load_rois() -> dict[str, dict[str, dict]]:
    by: dict[str, dict[str, dict]] = {}
    for line in (WAVE1 / "rois.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        by.setdefault(r["pair_id"], {})[r["role"]] = r
    return by


def frame_refs(roi: dict) -> list[dict]:
    refs = []
    for fr in roi.get("frames_local") or []:
        refs.append(
            {
                "t_seconds": fr["t_seconds"],
                "path": fr["path"],
                "sha256": fr["sha256"],
                "bytes": fr["bytes"],
                "storage": "gitignored_local_media",
            }
        )
    return refs


def review_refs(roi: dict) -> list[dict]:
    return [
        {
            "t_seconds": fr["t_seconds"],
            "path": fr["path"],
            "sha256": fr["sha256"],
            "bytes": fr["bytes"],
            "storage": "github_review_subset",
        }
        for fr in (roi.get("review_frames") or [])
    ]


def naming_fix(roi: dict) -> dict:
    parts = roi["roi_id"].split("_")
    named_start, named_end = int(parts[-2]), int(parts[-1])
    return {
        "legacy_roi_id": roi["roi_id"],
        "named_window_seconds": [named_start, named_end],
        "true_window_seconds": [roi["t_start"], roi["t_end"]],
        "true_center_s": roi["center_s"],
        "naming_bug": "ROI directory used center_s as start and center+10 as end (+5s vs true t_start)",
        "offset_seconds": {
            "named_start_minus_true_start": named_start - roi["t_start"],
            "named_end_minus_true_end": named_end - roi["t_end"],
        },
        "canonical_roi_id": (
            f"{roi['pair_id']}_{roi['role'].upper()}_"
            f"{int(roi['t_start'])}_{int(roi['t_end'])}"
        ),
        "fix_policy": "SIDECAR_ONLY_NO_REWRITE_OF_COMMITTED_PATHS_OR_IMMUTABLE_RELEASES",
    }


def build_priority_audits(by: dict) -> list[dict]:
    audits = []

    # 1) USfvmoalqsw_PAIR2 — strongest same-person bind candidate
    p = "USfvmoalqsw_PAIR2"
    e, l = by[p]["early"], by[p]["late"]
    audits.append(
        {
            "pair_id": p,
            "priority_rank": 1,
            "video_id": "USfvmoalqsw",
            "genre_label": {
                "auto_guess": "vlog",
                "cursor_frame_observation": "travel_vlog_bhutan",
                "human_confirmed": None,
                "label_status": "AUTO_HEURISTIC_PLUS_FRAME_OBSERVATION",
            },
            "windows_seconds_true": {
                "early": [e["t_start"], e["t_end"]],
                "late": [l["t_start"], l["t_end"]],
                "gap_s": l["t_start"] - e["t_end"],
            },
            "roi_naming_fix": {
                "early": naming_fix(e),
                "late": naming_fix(l),
            },
            "source_frame_refs": {
                "early_full_12": frame_refs(e),
                "late_full_12": frame_refs(l),
                "early_review_subset": review_refs(e),
                "late_review_subset": review_refs(l),
                "early_clip": e.get("local_clip"),
                "late_clip": l.get("local_clip"),
            },
            "visible_facts": {
                "early": {
                    "entities": [
                        "young_man_short_brown_hair_plaid_gho_selfie_foreground",
                        "secondary_person_dark_clothing_near_shoe_crates",
                    ],
                    "objects": [
                        "shop_sign_DORJI_OM_TSHONGKHANG",
                        "white_suzuki_celerio_taxi",
                        "crates_of_footwear",
                        "street_umbrellas",
                    ],
                    "scene": "outdoor_urban_bhutanese_street_overcast",
                    "actions_static_supported": [
                        "man_facing_camera_speaking_or_posing",
                        "pedestrian_near_shopfront",
                    ],
                    "requires_motion_or_audio": [
                        "speech_content",
                        "whether_man_walks_or_only_turns_head",
                    ],
                },
                "late": {
                    "entities": ["same_appearance_class_young_man_plaid_gho"],
                    "objects": ["stone_embankment", "stream_over_rocks", "wooden_plank_bridge"],
                    "scene": "lush_forest_stream_rural_outdoor",
                    "actions_static_supported": [
                        "man_speaking_to_camera",
                        "hand_gesture_toward_foliage",
                    ],
                    "requires_motion_or_audio": ["speech_content", "gesture_trajectory"],
                },
            },
            "candidate_cross_window_relation": {
                "operator": "CrossIntervalSamePersonBind",
                "claim": (
                    "The plaid-gho man in the late forest/stream window is the same "
                    "individual seen earlier on the Dorji Om Tshongkhang street."
                ),
                "follow_on_query_family": "IdentifyPerson→QueryEarlierLocation",
            },
            "relation_evidence_tier": "ORDERED_MULTIFRAME_SUGGESTS",
            "observation_provenance": "CHATGPT_FRAME_VISUAL_PRELIMINARY",
            "not_continuous_video_verified": True,
            "alternative_explanations": [
                "Different man wearing similar plaid gho / lookalike",
                "Costume continuity without identity continuity",
                "Edited multi-person travel montage",
            ],
            "shortcut_risk": {
                "single_frame": "MEDIUM — distinctive gho may answer clothing-only questions",
                "subtitle_overlay": "LOW_IN_REVIEWED_FRAMES — Instagram handle appears in PAIR1 late, not this pair",
                "official_qa_leak": "UNKNOWN_DEV_META_EXISTS_BUT_NOT_USED_AS_ANSWER",
                "same_video_id_assumption": "FORBIDDEN — identity not assumed from video_id alone",
            },
            "qa_candidate": {
                "status": "DRAFT_PENDING_HUMAN_IDENTITY_CONFIRMATION",
                "question_zh": "后来站在林间溪流旁、穿着格子gho对镜头说话的那名男子，更早出现在什么街景地点？",
                "answer_draft_zh": "DORJI OM TSHONGKHANG 店铺所在的城市街道附近",
                "windows_seconds": [[e["t_start"], e["t_end"]], [l["t_start"], l["t_end"]]],
                "program_graph_draft": {
                    "nodes": [
                        {"node_id": "n0", "op": "LocatePerson", "window": "late", "attrs": {"cue": "plaid_gho_man_by_stream"}},
                        {"node_id": "n1", "op": "CrossIntervalSamePersonBind", "inputs": ["n0"]},
                        {"node_id": "n2", "op": "QueryEarlierLocation", "inputs": ["n1"], "window": "early"},
                    ],
                    "edges": [
                        {"source": "n0", "target": "n1"},
                        {"source": "n1", "target": "n2"},
                    ],
                    "status": "DRAFT_NOT_EXECUTABLE_NOT_GOLD",
                },
                "formal_gold": False,
            },
            "necessity_status": {
                "a_only_early": "INSUFFICIENT_FOR_LATE_QUERY_FRAMING",
                "b_only_late": "INSUFFICIENT_FOR_SHOP_LOCATION_ANSWER",
                "a_plus_b": "PLAUSIBLY_SUFFICIENT_IF_IDENTITY_HOLDS",
                "single_frame_shortcut": "PARTIAL_RISK_IF_QUESTION_ONLY_ASKS_CLOTHING",
                "status": "PROVISIONAL_PASS_PENDING_HUMAN",
                "note": "Necessity provisional; identity bind not Human Approved.",
            },
            "human_review_required": True,
            "decision": "RELATION_FEASIBILITY_PASS_CANDIDATE_PENDING_HUMAN",
        }
    )

    # 2) gXnhqF0TqqI_PAIR1 — character identity + state change, high prior-knowledge risk
    p = "gXnhqF0TqqI_PAIR1"
    e, l = by[p]["early"], by[p]["late"]
    audits.append(
        {
            "pair_id": p,
            "priority_rank": 2,
            "video_id": "gXnhqF0TqqI",
            "genre_label": {
                "auto_guess": "animation",
                "cursor_frame_observation": "2d_hand_drawn_animation_toad_character",
                "human_confirmed": None,
                "label_status": "AUTO_HEURISTIC_PLUS_FRAME_OBSERVATION",
            },
            "windows_seconds_true": {
                "early": [e["t_start"], e["t_end"]],
                "late": [l["t_start"], l["t_end"]],
                "gap_s": l["t_start"] - e["t_end"],
            },
            "roi_naming_fix": {"early": naming_fix(e), "late": naming_fix(l)},
            "source_frame_refs": {
                "early_full_12": frame_refs(e),
                "late_full_12": frame_refs(l),
                "early_review_subset": review_refs(e),
                "late_review_subset": review_refs(l),
                "early_clip": e.get("local_clip"),
                "late_clip": l.get("local_clip"),
            },
            "visible_facts": {
                "early": {
                    "entities": ["green_anthropomorphic_toad_yellow_check_jacket_red_cravat"],
                    "objects": ["wrist_chains", "ball_and_chain", "stone_dungeon_walls", "rats_or_mice"],
                    "scene": "dungeon_prison_cell",
                    "actions_static_supported": ["toad_shackled_sitting_distressed"],
                    "requires_motion_or_audio": ["crying_vs_static_pose", "dialogue"],
                },
                "late": {
                    "entities": ["green_anthropomorphic_toad_tan_jacket"],
                    "objects": ["wooden_desk", "red_lampshade", "red_swivel_chair", "paper_or_stick"],
                    "scene": "wood_paneled_study_cluttered",
                    "actions_static_supported": ["toad_at_desk_writing_or_gesturing"],
                    "requires_motion_or_audio": ["writing_motion", "speech"],
                },
            },
            "candidate_cross_window_relation": {
                "operator": "CrossIntervalSameCharacterBind+ObjectStateChange",
                "claim": "Same toad character: early imprisoned → later free in study.",
                "follow_on_query_family": "IdentifyCharacter→QueryEarlierState",
            },
            "relation_evidence_tier": "ORDERED_MULTIFRAME_SUGGESTS",
            "observation_provenance": "CHATGPT_FRAME_VISUAL_PRELIMINARY",
            "not_continuous_video_verified": True,
            "alternative_explanations": [
                "Different toad characters with similar design",
                "Non-narrative montage without intended identity continuity",
            ],
            "shortcut_risk": {
                "single_frame": "HIGH — iconic costume/state readable in one still",
                "prior_knowledge_leak": "HIGH — famous Wind-in-the-Willows / Disney Toad narrative",
                "official_qa_leak": "UNKNOWN",
                "same_video_id_assumption": "FORBIDDEN",
            },
            "qa_candidate": {
                "status": "DRAFT_CONTROL_LEAKAGE_FLAGGED",
                "question_zh": "后来在书房桌前活动的那只穿夹克的绿蟾蜍，更早处于什么状态？",
                "answer_draft_zh": "被锁链拴在地牢中（含脚镣铁球）",
                "windows_seconds": [[e["t_start"], e["t_end"]], [l["t_start"], l["t_end"]]],
                "program_graph_draft": {
                    "nodes": [
                        {"node_id": "n0", "op": "LocateCharacter", "window": "late"},
                        {"node_id": "n1", "op": "CrossIntervalSameCharacterBind", "inputs": ["n0"]},
                        {"node_id": "n2", "op": "QueryEarlierState", "inputs": ["n1"], "window": "early"},
                    ],
                    "edges": [
                        {"source": "n0", "target": "n1"},
                        {"source": "n1", "target": "n2"},
                    ],
                    "status": "DRAFT_NOT_EXECUTABLE_NOT_GOLD",
                },
                "formal_gold": False,
            },
            "necessity_status": {
                "a_only_early": "MAY_ANSWER_IMPRISONED_WITHOUT_LATE_CUE",
                "b_only_late": "MAY_ANSWER_STUDY_WITHOUT_EARLY_STATE",
                "a_plus_b": "NEEDED_FOR_TRUE_CROSS_WINDOW_QUERY",
                "single_frame_shortcut": "HIGH",
                "prior_knowledge_shortcut": "HIGH",
                "status": "FAIL_OR_CONTROL_DUE_TO_LEAKAGE",
            },
            "human_review_required": True,
            "decision": "RETAIN_AS_CONTROL_HIGH_PRIOR_KNOWLEDGE_LEAKAGE",
        }
    )

    # 3) KktLi3UifPY_PAIR2 — possible same man, clothing change, weak bind
    p = "KktLi3UifPY_PAIR2"
    e, l = by[p]["early"], by[p]["late"]
    audits.append(
        {
            "pair_id": p,
            "priority_rank": 3,
            "video_id": "KktLi3UifPY",
            "genre_label": {
                "auto_guess": "interview",
                "cursor_frame_observation": "food_vlog_then_outdoor_coastal_segment",
                "human_confirmed": None,
                "label_status": "AUTO_HEURISTIC_CONFLICTS_WITH_FRAMES",
            },
            "windows_seconds_true": {
                "early": [e["t_start"], e["t_end"]],
                "late": [l["t_start"], l["t_end"]],
                "gap_s": l["t_start"] - e["t_end"],
            },
            "roi_naming_fix": {"early": naming_fix(e), "late": naming_fix(l)},
            "source_frame_refs": {
                "early_full_12": frame_refs(e),
                "late_full_12": frame_refs(l),
                "early_review_subset": review_refs(e),
                "late_review_subset": review_refs(l),
                "early_clip": e.get("local_clip"),
                "late_clip": l.get("local_clip"),
            },
            "visible_facts": {
                "early": {
                    "entities": [
                        "man_reddish_blonde_sushi_hachimaki_blue_dot_shirt",
                        "woman_long_brown_hair_mustard_shirt",
                    ],
                    "objects": ["red_lacquer_bowls", "sake_glasses", "green_bottle", "shoji_screen"],
                    "scene": "indoor_japanese_style_dining",
                    "actions_static_supported": ["eating_drinking_with_chopsticks"],
                    "requires_motion_or_audio": ["conversation_content"],
                },
                "late": {
                    "entities": ["man_black_UA_shirt_black_bandana_optional_same_person"],
                    "objects": ["curved_wooden_boards_with_ropes_on_rocky_shore"],
                    "scene": "outdoor_tidal_mudflat_coast",
                    "actions_static_supported": ["boards_static", "man_standing_outdoors"],
                    "requires_motion_or_audio": ["whether_man_uses_boards", "identity_confirmation"],
                    "within_roi_heterogeneity": "late_window includes board-only then man-closeup",
                },
            },
            "candidate_cross_window_relation": {
                "operator": "CrossIntervalSamePersonBind",
                "claim": "Possibly same male host indoor dining → outdoor coast; clothing fully changed.",
                "follow_on_query_family": "IdentifyPerson→QueryEarlierActivity",
            },
            "relation_evidence_tier": "UNRESOLVED",
            "observation_provenance": "CHATGPT_FRAME_VISUAL_PRELIMINARY",
            "not_continuous_video_verified": True,
            "alternative_explanations": [
                "Different man with similar hair",
                "No intended entity bind between dining and coast segments",
                "Late boards are scene-cut without person continuity",
            ],
            "shortcut_risk": {
                "single_frame": "MEDIUM",
                "identity_uncertainty": "HIGH",
                "same_video_id_assumption": "FORBIDDEN",
            },
            "qa_candidate": None,
            "necessity_status": {"status": "NOT_APPLICABLE_NO_CERTIFIED_RELATION"},
            "human_review_required": True,
            "decision": "HOLD_NO_QA_IDENTITY_NOT_FRAME_CERTIFIED",
        }
    )

    # 4) USfvmoalqsw_PAIR1 — mismatched subjects
    p = "USfvmoalqsw_PAIR1"
    e, l = by[p]["early"], by[p]["late"]
    audits.append(
        {
            "pair_id": p,
            "priority_rank": 4,
            "video_id": "USfvmoalqsw",
            "genre_label": {
                "auto_guess": "vlog",
                "cursor_frame_observation": "travel_vlog_bhutan_mixed_subjects",
                "human_confirmed": None,
                "label_status": "AUTO_HEURISTIC_PLUS_FRAME_OBSERVATION",
            },
            "windows_seconds_true": {
                "early": [e["t_start"], e["t_end"]],
                "late": [l["t_start"], l["t_end"]],
                "gap_s": l["t_start"] - e["t_end"],
            },
            "roi_naming_fix": {"early": naming_fix(e), "late": naming_fix(l)},
            "source_frame_refs": {
                "early_full_12": frame_refs(e),
                "late_full_12": frame_refs(l),
                "early_review_subset": review_refs(e),
                "late_review_subset": review_refs(l),
                "early_clip": e.get("local_clip"),
                "late_clip": l.get("local_clip"),
            },
            "visible_facts": {
                "early": {
                    "entities": [
                        "woman_name_tag_CHOKI_LHAM_glasses",
                        "young_man_and_woman_inside_vehicle_later_in_same_roi",
                    ],
                    "objects": ["silver_SUV", "white_bus", "YouTube_SUBSCRIBED_overlay"],
                    "scene": "parking_area_then_vehicle_interior_within_10s",
                    "within_roi_instability": True,
                },
                "late": {
                    "entities": [
                        "man_plaid_gho_touching_woven_bag",
                        "woman_pink_jacket_holding_basket_in_shop",
                    ],
                    "objects": ["striped_woven_bag", "Instagram_overlay_@JACK_TORR", "corrugated_roof_shop"],
                    "scene": "outdoor_rural_then_indoor_craft_shop_within_10s",
                    "within_roi_instability": True,
                },
            },
            "candidate_cross_window_relation": None,
            "relation_evidence_tier": "UNRESOLVED",
            "observation_provenance": "CHATGPT_FRAME_VISUAL_PRELIMINARY",
            "not_continuous_video_verified": True,
            "alternative_explanations": [
                "Histogram pair only; no shared primary entity across early/late",
            ],
            "shortcut_risk": {"overlay_leak": "MEDIUM — YouTube/Instagram UI overlays present"},
            "qa_candidate": None,
            "necessity_status": {"status": "NOT_APPLICABLE"},
            "human_review_required": False,
            "decision": "REJECT_NO_CLEAR_CROSS_WINDOW_BIND",
        }
    )

    # 5) 16Z-XQh9jhk_PAIR2 — anti-shortcut control; genre mislabel
    p = "16Z-XQh9jhk_PAIR2"
    e, l = by[p]["early"], by[p]["late"]
    audits.append(
        {
            "pair_id": p,
            "priority_rank": 5,
            "video_id": "16Z-XQh9jhk",
            "genre_label": {
                "auto_guess": "sports",
                "cursor_frame_observation": "live_concert_performance_not_sports",
                "human_confirmed": None,
                "label_status": "AUTO_HEURISTIC_INCORRECT_VS_FRAMES",
            },
            "windows_seconds_true": {
                "early": [e["t_start"], e["t_end"]],
                "late": [l["t_start"], l["t_end"]],
                "gap_s": l["t_start"] - e["t_end"],
            },
            "roi_naming_fix": {"early": naming_fix(e), "late": naming_fix(l)},
            "source_frame_refs": {
                "early_full_12": frame_refs(e),
                "late_full_12": frame_refs(l),
                "early_review_subset": review_refs(e),
                "late_review_subset": review_refs(l),
                "early_clip": e.get("local_clip"),
                "late_clip": l.get("local_clip"),
            },
            "visible_facts": {
                "early": {
                    "entities": [
                        "blonde_female_singer_neon_green_zebra_dress_pink_mic",
                        "backup_performer_pink_bodysuit_yellow_sphere_headpiece",
                    ],
                    "scene": "dark_concert_stage_closeup",
                    "actions_static_supported": ["singing_pose_with_microphone"],
                },
                "late": {
                    "entities": ["distant_stage_performer_on_LED", "blonde_performer_green_black_jumpsuit"],
                    "objects": ["stadium_screens_rainbow_graphic", "crowd_silhouettes"],
                    "scene": "stadium_wide_then_stage_medium",
                    "within_roi_heterogeneity": True,
                },
            },
            "candidate_cross_window_relation": {
                "operator": "CrossIntervalSamePersonBind",
                "claim": "Possibly same lead performer across concert segments.",
                "follow_on_query_family": "IdentifyPerformer→QueryEarlierCostume",
            },
            "relation_evidence_tier": "ORDERED_MULTIFRAME_SUGGESTS",
            "observation_provenance": "CHATGPT_FRAME_VISUAL_PRELIMINARY",
            "not_continuous_video_verified": True,
            "alternative_explanations": [
                "Different songs/outfits without requiring cross-window bind",
                "Celebrity prior knowledge answers without video evidence",
            ],
            "shortcut_risk": {
                "single_frame": "HIGH — distinctive costume/celebrity face",
                "prior_knowledge_leak": "HIGH — celebrity concert recognition",
                "anti_shortcut_role": "PRIMARY_NEGATIVE_CONTROL_SAMPLE",
            },
            "qa_candidate": None,
            "necessity_status": {
                "status": "FAIL_HIGH_SHORTCUT",
                "note": "Retained as anti-shortcut control; not counted as valid compositional QA.",
            },
            "human_review_required": True,
            "decision": "RETAIN_AS_SHORTCUT_CONTROL_NOT_VALID_COMP_QA",
        }
    )
    return audits


def build_deferred(by: dict, priority: set[str]) -> list[dict]:
    out = []
    for pid in sorted(by):
        if pid in priority:
            continue
        e, l = by[pid]["early"], by[pid]["late"]
        out.append(
            {
                "pair_id": pid,
                "priority_rank": None,
                "video_id": e["video_id"],
                "windows_seconds_true": {
                    "early": [e["t_start"], e["t_end"]],
                    "late": [l["t_start"], l["t_end"]],
                },
                "roi_naming_fix": {"early": naming_fix(e), "late": naming_fix(l)},
                "source_frame_refs_summary": {
                    "n_early_frames": len(e.get("frames_local") or []),
                    "n_late_frames": len(l.get("frames_local") or []),
                    "early_review_dir": e.get("review_frames_dir"),
                    "late_review_dir": l.get("review_frames_dir"),
                },
                "relation_evidence_tier": "UNRESOLVED",
                "observation_provenance": "NOT_TRIAGED_THIS_ROUND",
                "qa_candidate": None,
                "necessity_status": {"status": "UNKNOWN"},
                "human_review_required": True,
                "decision": "DEFERRED_LOW_PRIORITY_HISTORY_PRESERVED",
            }
        )
    return out


def write_roi_naming_sidecar(by: dict) -> Path:
    rows = []
    for pid, roles in by.items():
        for role, roi in roles.items():
            rows.append(
                {
                    **naming_fix(roi),
                    "pair_id": pid,
                    "role": role,
                    "video_id": roi["video_id"],
                    "true_sample_timestamps": [fr["t_seconds"] for fr in roi.get("frames_local") or []],
                    "true_sample_sha256": [fr["sha256"] for fr in roi.get("frames_local") or []],
                }
            )
    path = WAVE1 / "ROI_NAMING_CORRECTION_SIDECAR.jsonl"
    write_jsonl(path, rows)
    return path


def write_genre_audit() -> Path:
    rows = [
        {
            "video_id": "USfvmoalqsw",
            "auto_guess": "vlog",
            "frame_observation": "travel_vlog_bhutan",
            "human_confirmed": None,
            "status": "AUTO_PLUS_FRAME",
        },
        {
            "video_id": "16Z-XQh9jhk",
            "auto_guess": "sports",
            "frame_observation": "concert_performance",
            "human_confirmed": None,
            "status": "AUTO_INCORRECT_VS_FRAMES",
            "correction_proposed": "concert_live_performance",
        },
        {
            "video_id": "CgvJqGxzRfE",
            "auto_guess": "documentary",
            "frame_observation": None,
            "human_confirmed": None,
            "status": "AUTO_ONLY_UNVERIFIED",
        },
        {
            "video_id": "KktLi3UifPY",
            "auto_guess": "interview",
            "frame_observation": "food_vlog_and_outdoor_segments",
            "human_confirmed": None,
            "status": "AUTO_LIKELY_MISMATCH",
        },
        {
            "video_id": "gXnhqF0TqqI",
            "auto_guess": "animation",
            "frame_observation": "2d_animation_confirmed_in_frames",
            "human_confirmed": None,
            "status": "AUTO_CONSISTENT_WITH_FRAMES",
        },
    ]
    path = WAVE1 / "GENRE_LABEL_AUDIT.jsonl"
    write_jsonl(path, rows)
    return path


def update_run004_gate(n_feasible: int, pair_ids: list[str]) -> Path:
    gate = {
        "run_004_status": "PARTIAL_UNLOCK_RELATION_FEASIBILITY_ONLY"
        if n_feasible
        else "NOT_STARTED",
        "status": (
            "RELATION_FEASIBILITY_PASS_FOR_LISTED_PAIRS"
            if n_feasible
            else "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE"
        ),
        "n_qualifying_pairs": n_feasible,
        "qualifying_pair_ids": pair_ids,
        "still_blocked_for": [
            "FORMAL_GOLD",
            "CONTINUOUS_VIDEO_VERIFIED_AUTO_FROM_STILLS",
            "HUMAN_APPROVED_IDENTITY",
            "FULL_BATCH_QA_MINTING",
        ],
        "note": (
            "WP3.1 still-frame triage found provisional relation-feasible candidates. "
            "run_004 may draft QA only for listed pairs; no Gold; no continuous-video upgrade from stills."
        ),
        "updated_utc": utc_now(),
        "baseline_commit": BASELINE,
    }
    path = DS_ROOT / "wp3_production" / "RUN_004_GATE_WP3_1.json"
    write_json(path, gate)
    # also mirror near pilot gate for visibility without rewriting old pilot gate semantics
    write_json(DS_ROOT / "reports" / "RUN_004_GATE_WP3_1.json", gate)
    return path


def write_refined_staging(audits: list[dict]) -> Path:
    items = []
    for a in audits:
        qa = a.get("qa_candidate")
        if not qa or qa.get("status", "").startswith("DRAFT") is False:
            # still record rejects with import_ready false
            pass
        import_ready = False
        semantic_ok = a["decision"] == "RELATION_FEASIBILITY_PASS_CANDIDATE_PENDING_HUMAN"
        items.append(
            {
                "source_item_id": a["pair_id"],
                "video_id": a["video_id"],
                "question": (qa or {}).get("question_zh"),
                "answer": (qa or {}).get("answer_draft_zh"),
                "answer_status": "CHAT_DRAFT_PENDING_HUMAN"
                if qa and semantic_ok
                else "NO_QA_THIS_ROUND",
                "windows_seconds": (qa or {}).get("windows_seconds")
                or a.get("windows_seconds_true"),
                "program_graph": (qa or {}).get("program_graph_draft")
                or {
                    "nodes": [],
                    "edges": [],
                    "status": "ABSENT_REJECTED_PAIR",
                },
                "operator_signature": (a.get("candidate_cross_window_relation") or {}).get(
                    "operator"
                ),
                "necessity": a.get("necessity_status"),
                "review_status": "DRAFT",
                "relation_evidence_tier": a.get("relation_evidence_tier"),
                "observation_provenance": a.get("observation_provenance"),
                "semantic_certification": "UNRESOLVED"
                if a.get("human_review_required")
                else a.get("decision"),
                "import_ready": import_ready,
                "formal_gold": False,
                "split_assignment": "PENDING",
                "decision": a["decision"],
                "import_block_reason": (
                    "SEMANTICS_PENDING_HUMAN"
                    if semantic_ok
                    else f"DECISION_{a['decision']}"
                ),
            }
        )
    path = DS_ROOT / "staging" / "wp3_1_wave1_triage_refined_batch.json"
    write_json(
        path,
        {
            "batch_id": "wp3_1_wave1_triage_refined_2026-11-05",
            "status": "STAGING_ONLY_NOT_IMPORTED",
            "formal_gold": False,
            "import_ready": False,
            "items": items,
            "note": "Refined after WP3.1 triage. Must remain rejected by import until human certification.",
        },
    )
    return path


def media_redistribution_note() -> dict:
    return {
        "status": "LICENSE_UNCONFIRMED_STOP_NEW_PUBLIC_MEDIA",
        "policy": (
            "Do not add new third-party review frames/clips to public GitHub until "
            "redistribution rights are confirmed. Existing committed review stills retained "
            "for audit continuity; no force-push / history rewrite."
        ),
        "local_reextraction": {
            "tool": "research_audit/lvbench_compositional/track_b/LongVideoCompBench/tools/wp3_wave_production.py",
            "video_root": "/home/descfly/lpy/dataset/LVBench/videos",
            "gitignored_full_packs": str(
                (
                    REPO_ROOT
                    / "research_audit/lvbench_compositional/track_b/local_media/wp3_production"
                ).relative_to(REPO_ROOT)
            ),
        },
        "this_round_added_new_public_media_files": False,
    }


def main() -> int:
    by = load_rois()
    priority_audits = build_priority_audits(by)
    deferred = build_deferred(by, set(PRIORITY_ORDER))
    naming_path = write_roi_naming_sidecar(by)
    genre_path = write_genre_audit()
    staging_path = write_refined_staging(priority_audits)

    feasible = [
        a["pair_id"]
        for a in priority_audits
        if a["decision"] == "RELATION_FEASIBILITY_PASS_CANDIDATE_PENDING_HUMAN"
    ]
    gate_path = update_run004_gate(len(feasible), feasible)

    report = {
        "schema": "wp3_wave1_gpt_semantic_triage_and_relation_audit_v1",
        "work_package": "WP3.1",
        "baseline_commit": BASELINE,
        "built_utc": utc_now(),
        "scope": "Wave1 priority pairs only; no new videos",
        "observation_rule": {
            "stills_may_be": [
                "STATIC_VISIBLE",
                "ORDERED_MULTIFRAME_SUGGESTS",
                "UNRESOLVED",
            ],
            "stills_must_not_become": ["CONTINUOUS_VIDEO_VERIFIED"],
            "chatgpt_triage_label": "CHATGPT_FRAME_VISUAL_PRELIMINARY",
            "not_human_approved": True,
            "not_formal_gold": True,
        },
        "priority_order_source": "GPT_VISUAL_PRELIMINARY_TRIAGE_NOT_HUMAN_APPROVED",
        "pairs": priority_audits + deferred,
        "summary": {
            "n_priority_reviewed": len(priority_audits),
            "n_deferred_low_priority": len(deferred),
            "relation_feasibility_pass_pending_human": feasible,
            "reject": [
                a["pair_id"]
                for a in priority_audits
                if a["decision"].startswith("REJECT")
            ],
            "hold": [
                a["pair_id"]
                for a in priority_audits
                if a["decision"].startswith("HOLD")
            ],
            "control": [
                a["pair_id"]
                for a in priority_audits
                if "CONTROL" in a["decision"]
            ],
            "n_formal_gold": 0,
            "n_human_approved": 0,
            "n_continuous_video_verified": 0,
        },
        "engineering_fixes": {
            "roi_naming_sidecar": str(naming_path.relative_to(REPO_ROOT)),
            "genre_label_audit": str(genre_path.relative_to(REPO_ROOT)),
            "import_guard": "import_annotation_batch rejects import_ready=false / uncertified WP3 stubs",
            "media_redistribution": media_redistribution_note(),
            "immutable_releases_preserved": ["v0.1.0", "v0.1.1", "v0.1.2"],
            "frozen_5_2_unchanged": True,
            "proposed_7_4_status": "PROPOSED",
        },
        "run_004_gate": str(gate_path.relative_to(REPO_ROOT)),
        "staging_refined": str(staging_path.relative_to(REPO_ROOT)),
        "next_production_advice": [
            "Human Scientific Owner confirms identity on USfvmoalqsw_PAIR2 using local clips before any Gold path",
            "Do not mint more Wave2 QA until Wave1 feasible relations are human-adjudicated",
            "Keep gXnhqF0TqqI_PAIR1 and 16Z-XQh9jhk_PAIR2 as leakage/shortcut controls",
            "Stop committing new public review media until license clearance",
            "For next discovery wave, prefer entity-stable windows (avoid within-ROI subject thrash)",
        ],
    }
    write_json(OUT, report)
    write_json(OUT_COPY, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print("report=", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
