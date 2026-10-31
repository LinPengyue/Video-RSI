"""B1/B2 — coarse scan + event graph construction (no expensive models)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from . import EXTRACTOR_VERSION

FFMPEG = os.environ.get(
    "LVBENCH_FFMPEG",
    "/home/descfly/.cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffmpeg",
)


def _extract_frame(video: Path, t: float, out: Path) -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 500:
        return True
    r = subprocess.run(
        [FFMPEG, "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-q:v", "4", str(out)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return r.returncode == 0 and out.exists()


def _coarse_sample_times(duration: float | None, max_samples: int = 12) -> list[float]:
    if not duration or duration <= 0:
        return [5.0, 30.0, 60.0]
    # Avoid full 1fps: sample at deciles + a few midpoints
    fracs = [0.05, 0.12, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.88, 0.95]
    times = [max(1.0, min(duration - 1.0, duration * f)) for f in fracs]
    return times[:max_samples]


def _event(
    *,
    event_id: str,
    video_id: str,
    t0: float,
    t1: float,
    actor: str,
    verb: str,
    obj: str = "",
    location: str = "",
    state_before: str | None = None,
    state_after: str | None = None,
    modality: str = "visual",
    evidence_paths: list[str] | None = None,
    confidence: float = 0.5,
    observed_vs_inferred: str = "observed",
    unresolved_flags: list[str] | None = None,
    source: str = "FRAME_VISUAL_OBSERVATION",
    provenance_tier: str | None = None,
    from_curated_dict: bool = False,
    notes: str = "",
    summary_zh: str = "",
) -> dict[str, Any]:
    tier = provenance_tier
    if tier is None:
        if from_curated_dict:
            tier = "CURATED_FROM_PRIOR_HUMAN_OR_CHATGPT_AUDIT"
        elif verb in {"visual_sample", "seed_frame_present"}:
            tier = "AUTOMATIC_COARSE_FRAME"
        else:
            tier = "AUTOMATIC_COARSE_FRAME"
    return {
        "event_id": event_id,
        "video_id": video_id,
        "time_start_s": round(t0, 3),
        "time_end_s": round(t1, 3),
        "actor_local_track": actor,
        "verb": verb,
        "object": obj,
        "location": location,
        "state_before": state_before,
        "state_after": state_after,
        "modality": modality,
        "evidence_paths": evidence_paths or [],
        "confidence": confidence,
        "observed_vs_inferred": observed_vs_inferred,
        "unresolved_flags": unresolved_flags or [],
        "extractor_version": EXTRACTOR_VERSION,
        "provenance": source,
        "provenance_tier": tier,
        "from_curated_dict": from_curated_dict,
        "notes": notes,
        "summary_zh": summary_zh,
        "identity_link": {"status": "LOCAL_ONLY", "match_confidence": None, "distractors": []},
        "is_newly_discovered_semantic": tier
        in {
            "CURSOR_FRAME_VISUAL_OBSERVATION",
            "CHATGPT_FRAME_OBSERVATION",
            "AUTOMATIC_SEMANTIC_MODEL_OBSERVATION",
            "HUMAN_VIDEO_VERIFIED",
        }
        and verb not in {"visual_sample", "seed_frame_present"},
        "is_curated_fixture": tier == "CURATED_FROM_PRIOR_HUMAN_OR_CHATGPT_AUDIT",
    }


# Frame observations from previously unlabeled seed videos (agent still inspection, 2026-10-31).
# Not CURATED fixtures; not SUPPORTED; still UNASSIGNED drafts.
NEW_FRAME_OBSERVATIONS: dict[str, list[dict[str, Any]]] = {
    "S8vPx-u9p_A": [
        _event(
            event_id="S8v_E_snow_children",
            video_id="S8vPx-u9p_A",
            t0=848,
            t1=849,
            actor="child_pair_local",
            verb="walk_in_snow",
            obj="boy_dark_coat_hat; girl_red_skirt_blue_hood",
            location="snowy_building_exterior",
            confidence=0.7,
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/S8vPx-u9p_A/seed_frame_1_t848.jpg"
            ],
            provenance_tier="CURSOR_FRAME_VISUAL_OBSERVATION",
            source="CURSOR_FRAME_VISUAL_OBSERVATION",
            summary_zh="动画：雪地中两名儿童（深色大衣男孩与红裙蓝帽女孩）在建筑前行走",
            notes="Traditional animation still; identity across later scenes unverified",
            unresolved_flags=["animation_style", "identity_across_cuts_unknown"],
        ),
        _event(
            event_id="S8v_E_crystal_stairs",
            video_id="S8vPx-u9p_A",
            t0=2121,
            t1=2122,
            actor="camera_interior",
            verb="show_ascending_stairs",
            obj="teal_stairs_between_crystal_pillars",
            location="dark_crystalline_corridor",
            confidence=0.65,
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/S8vPx-u9p_A/seed_frame_2_t2121.jpg"
            ],
            provenance_tier="CURSOR_FRAME_VISUAL_OBSERVATION",
            source="CURSOR_FRAME_VISUAL_OBSERVATION",
            summary_zh="动画：深色晶柱夹道中向上的阶梯",
            unresolved_flags=["place_in_narrative_unknown"],
        ),
        _event(
            event_id="S8v_E_water_spray",
            video_id="S8vPx-u9p_A",
            t0=3182,
            t1=3183,
            actor="watercraft_or_figure_local",
            verb="high_speed_water_maneuver",
            obj="white_wake_spray; reddish_rect_object",
            location="dark_water",
            confidence=0.45,
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/S8vPx-u9p_A/seed_frame_3_t3182.jpg"
            ],
            provenance_tier="CURSOR_FRAME_VISUAL_OBSERVATION",
            source="CURSOR_FRAME_VISUAL_OBSERVATION",
            summary_zh="高速水面转向/溅起白浪；主体因运动模糊未完全辨认",
            unresolved_flags=["severe_motion_blur", "actor_identity_uncertain"],
        ),
    ],
    "iA_69g87Ilw": [
        _event(
            event_id="iA_E_fruit_platter_point",
            video_id="iA_69g87Ilw",
            t0=361,
            t1=362,
            actor="hand_local_fpv",
            verb="point_touch_grapes",
            obj="pineapple_center_fruit_bowl; red_grapes",
            location="indoor_luxury_table",
            confidence=0.8,
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/iA_69g87Ilw/seed_frame_1_t361.jpg"
            ],
            provenance_tier="CURSOR_FRAME_VISUAL_OBSERVATION",
            source="CURSOR_FRAME_VISUAL_OBSERVATION",
            summary_zh="室内水果盘（中央菠萝）旁一只手指向/触碰红葡萄；右上角字幕 Walk With Me",
            notes="Overlay text Walk With Me visible",
            unresolved_flags=["speaker_face_not_in_frame"],
        ),
        _event(
            event_id="iA_E_host_armchair_selfie",
            video_id="iA_69g87Ilw",
            t0=904,
            t1=905,
            actor="host_short_brown_hair_local",
            verb="sit_hold_selfie_stick",
            obj="black_selfie_stick; dark_polo; white_shorts",
            location="indoor_armchair_blue_gold_room",
            confidence=0.85,
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/iA_69g87Ilw/seed_frame_2_t904.jpg"
            ],
            provenance_tier="CURSOR_FRAME_VISUAL_OBSERVATION",
            source="CURSOR_FRAME_VISUAL_OBSERVATION",
            summary_zh="短发男子坐彩色格纹扶手椅，右手持黑色自拍杆；Walk With Me 角标",
            unresolved_flags=["same_show_as_fruit_scene_hypothesis"],
        ),
        _event(
            event_id="iA_E_infinity_pool_night",
            video_id="iA_69g87Ilw",
            t0=1356,
            t1=1357,
            actor="camera_poolside",
            verb="show_illuminated_pool",
            obj="turquoise_infinity_pool_underwater_lights",
            location="night_outdoor_pool",
            confidence=0.85,
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/iA_69g87Ilw/seed_frame_3_t1356.jpg"
            ],
            provenance_tier="CURSOR_FRAME_VISUAL_OBSERVATION",
            source="CURSOR_FRAME_VISUAL_OBSERVATION",
            summary_zh="夜间发光无边泳池；Walk With Me 角标仍在",
            unresolved_flags=["host_absent_in_frame"],
        ),
    ],
    "hROKtPqktO8": [
        _event(
            event_id="hRO_E_sidewalk_67",
            video_id="hROKtPqktO8",
            t0=503,
            t1=504,
            actor="pedestrian_teal_sweater_local",
            verb="walk_away_on_sidewalk",
            obj="building_number_67; white_subcompact_car",
            location="urban_sidewalk_autumn",
            confidence=0.8,
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/hROKtPqktO8/seed_frame_1_t503.jpg"
            ],
            provenance_tier="CURSOR_FRAME_VISUAL_OBSERVATION",
            source="CURSOR_FRAME_VISUAL_OBSERVATION",
            summary_zh="城市人行道：门牌 67、红建筑、青绿色毛衣行人背影、秋叶",
            unresolved_flags=["city_identity_unknown"],
        ),
        _event(
            event_id="hRO_E_lava_hills",
            video_id="hROKtPqktO8",
            t0=1259,
            t1=1260,
            actor="camera_landscape",
            verb="show_volcanic_terrain",
            obj="dark_lava_rock; tan_ash_hills",
            location="high_altitude_volcanic",
            confidence=0.85,
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/hROKtPqktO8/seed_frame_2_t1259.jpg"
            ],
            provenance_tier="CURSOR_FRAME_VISUAL_OBSERVATION",
            source="CURSOR_FRAME_VISUAL_OBSERVATION",
            summary_zh="火山熔岩与灰褐山丘空旷景观（无行人）",
            unresolved_flags=["place_name_unknown", "link_to_urban_scene_unverified"],
        ),
        _event(
            event_id="hRO_E_night_snow_parka",
            video_id="hROKtPqktO8",
            t0=1889,
            t1=1890,
            actor="person_black_beanie_local",
            verb="face_camera_in_snowfall",
            obj="olive_parka_hood; black_beanie",
            location="outdoor_night_snow",
            confidence=0.7,
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/hROKtPqktO8/seed_frame_3_t1889.jpg"
            ],
            provenance_tier="CURSOR_FRAME_VISUAL_OBSERVATION",
            source="CURSOR_FRAME_VISUAL_OBSERVATION",
            summary_zh="夜间降雪中戴黑帽与橄榄色连帽外套者面对镜头",
            unresolved_flags=["identity_vs_teal_pedestrian_unknown", "motion_noise"],
        ),
    ],
}


# Curated high-value events from prior visual audits (DEV only; not SUPPORTED).
CURATED: dict[str, list[dict[str, Any]]] = {
    "T1yhBv1ytzw": [
        _event(
            event_id="T1yh_E_score_00",
            video_id="T1yhBv1ytzw",
            t0=1785,
            t1=1790,
            actor="broadcast_overlay",
            verb="display_score",
            obj="BRI 0-0 LIV",
            state_after="0-0",
            confidence=0.9,
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/T1yhBv1ytzw/score_state_keyframes/t_29_45.jpg"
            ],
            notes="Scoreboard overlay; descriptive fact",
        ),
        _event(
            event_id="T1yh_E_liv_lead",
            video_id="T1yhBv1ytzw",
            t0=1870,
            t1=1895,
            actor="team_LIV_red",
            verb="score_change_observed",
            obj="BRI 0-1 LIV",
            state_before="0-0",
            state_after="0-1",
            confidence=0.85,
            unresolved_flags=["scorer_unknown", "kick_origin_unknown", "live_vs_replay_separated"],
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/chatgpt_review_assets/T1yhBv1ytzw/liv_live_pre_2950_3014.jpg",
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/T1yhBv1ytzw/score_state_keyframes/t_31_30.jpg",
            ],
        ),
        _event(
            event_id="T1yh_E_bri_equalize",
            video_id="T1yhBv1ytzw",
            t0=2328,
            t1=2380,
            actor="team_BRI_stripes",
            verb="score_change_observed",
            obj="BRI 1-1 LIV",
            state_before="0-1",
            state_after="1-1",
            confidence=0.85,
            unresolved_flags=["scorer_unknown", "set_piece_candidate_unconfirmed"],
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/chatgpt_review_assets/T1yhBv1ytzw/bha_live_3845_3919.jpg",
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/T1yhBv1ytzw/score_state_keyframes/t_39_40.jpg",
            ],
        ),
    ],
    "VTCDQYYKA9o": [
        _event(
            event_id="VTCD_E_red_jacket_towel",
            video_id="VTCDQYYKA9o",
            t0=166,
            t1=175,
            actor="athlete_short_hair_local_A",
            verb="wipe_face_wear_jacket",
            obj="white_towel + red_jacket",
            confidence=0.75,
            unresolved_flags=["identity_not_formally_bound"],
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/chatgpt_review_assets/VTCDQYYKA9o/garment_0240_0320_1fps.jpg"
            ],
        ),
        _event(
            event_id="VTCD_E_remove_red_jacket",
            video_id="VTCDQYYKA9o",
            t0=170,
            t1=185,
            actor="athlete_short_hair_local_A",
            verb="remove_outer_garment",
            obj="red_jacket",
            state_before="red_jacket",
            state_after="blue_yellow_jersey",
            confidence=0.8,
            unresolved_flags=["identity_continuity_pending_video"],
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/chatgpt_review_assets/VTCDQYYKA9o/tt_qa_adjudication/contact_A.jpg"
            ],
        ),
        _event(
            event_id="VTCD_E_previous_results_fan",
            video_id="VTCDQYYKA9o",
            t0=270,
            t1=275,
            actor="athlete_blue_yellow_local_B",
            verb="display_previous_results_overlay",
            obj="PREVIOUS RESULTS CHN FAN ZHENDONG",
            confidence=0.9,
            notes="Overlay is PREVIOUS RESULTS not live score",
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/chatgpt_review_assets/VTCDQYYKA9o/event_stills/later_t_4_30.jpg"
            ],
            unresolved_flags=["same_person_as_local_A_hypothesis"],
        ),
    ],
    "Z86xysw5Ncc": [
        _event(
            event_id="Z86_E_intro_gay",
            video_id="Z86xysw5Ncc",
            t0=165,
            t1=190,
            actor="runner_intro_local_A",
            verb="broadcast_intro_caption",
            obj="USA Gay",
            confidence=0.85,
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/chatgpt_review_assets/Z86xysw5Ncc/z86_0205_0410.jpg"
            ],
        ),
        _event(
            event_id="Z86_E_intro_ndure",
            video_id="Z86xysw5Ncc",
            t0=125,
            t1=145,
            actor="runner_intro_local_B",
            verb="broadcast_intro_caption",
            obj="NOR Jaysuma Saidy Ndure",
            confidence=0.85,
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/chatgpt_review_assets/Z86xysw5Ncc/z86_0205_0410.jpg"
            ],
        ),
        _event(
            event_id="Z86_E_start_list_heat2",
            video_id="Z86xysw5Ncc",
            t0=325,
            t1=332,
            actor="overlay_start_list",
            verb="display_start_list",
            obj="MEN'S 100M START LIST ROUND 1 HEAT 2 incl. USA Justin Gatlin",
            confidence=0.95,
            notes="START LIST not results — CORR-Z86-STARTLIST-001",
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/chatgpt_review_assets/Z86xysw5Ncc/board_stills/t_5_27_crop.jpg"
            ],
            unresolved_flags=["not_finish_results"],
        ),
    ],
    "JPPMz8fEml0": [
        _event(
            event_id="JPP_E_indoor_talk",
            video_id="JPPMz8fEml0",
            t0=60,
            t1=65,
            actor="bearded_man_local",
            verb="gesture_speak",
            location="indoor",
            confidence=0.55,
            unresolved_flags=["narrative_link_unknown"],
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/JPPMz8fEml0/uid_2963_context_frame_01.jpg"
            ],
        ),
        _event(
            event_id="JPP_E_city_aerial",
            video_id="JPPMz8fEml0",
            t0=78,
            t1=82,
            actor="camera_aerial",
            verb="show_cityscape",
            location="outdoor_city",
            confidence=0.6,
            unresolved_flags=["place_identity_unknown"],
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/JPPMz8fEml0/uid_2963_strict_frame_01.jpg"
            ],
        ),
    ],
    "QWXlvx1GoTY": [
        _event(
            event_id="QWX_E_slide_questions",
            video_id="QWXlvx1GoTY",
            t0=2515,
            t1=2520,
            actor="presenter_local",
            verb="present_slide",
            obj="Cisco Live infrastructure/security questions",
            confidence=0.7,
            unresolved_flags=["spoken_answer_unknown_need_audio"],
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/QWXlvx1GoTY/uid_2463_context_frame_01.jpg"
            ],
        ),
        _event(
            event_id="QWX_E_presenter_closeup",
            video_id="QWXlvx1GoTY",
            t0=2533,
            t1=2538,
            actor="presenter_local",
            verb="speak_closeup",
            confidence=0.55,
            unresolved_flags=["audio_not_audited"],
            evidence_paths=[
                "research_audit/lvbench_compositional/track_b/construction_discovery_assets/QWXlvx1GoTY/uid_2463_strict_frame_01.jpg"
            ],
        ),
    ],
}

# Ensure curated fixtures are never counted as newly discovered
for _evs in CURATED.values():
    for _e in _evs:
        _e["from_curated_dict"] = True
        _e["is_curated_fixture"] = True
        _e["provenance_tier"] = "CURATED_FROM_PRIOR_HUMAN_OR_CHATGPT_AUDIT"
        _e["is_newly_discovered_semantic"] = False


def extract_for_video(inv: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Return event graph + evidence index entries for one video. Never raises out."""
    vid = inv["video_id"]
    media_status = inv.get("media_status", "OK")
    events: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    flags: list[str] = []

    if media_status != "OK" or not inv.get("media_path"):
        return {
            "video_id": vid,
            "status": "MEDIA_UNAVAILABLE",
            "events": [],
            "evidence": [],
            "flags": ["MEDIA_UNAVAILABLE"],
        }

    video = Path(inv["media_path"])
    frame_dir = run_dir / "frames" / vid
    # Coarse scan frames
    times = _coarse_sample_times(inv.get("duration_s"))
    for i, t in enumerate(times):
        out = frame_dir / f"coarse_t{int(t):05d}.jpg"
        ok = _extract_frame(video, t, out)
        if not ok:
            flags.append(f"EXTRACTION_FAILED_t{t}")
            continue
        rel = str(out.relative_to(run_dir.parent.parent.parent.parent)) if False else str(out)
        # store repo-relative if under workspace
        try:
            rel_path = str(out.resolve()).split("/Video-RSI/")[-1] if "/Video-RSI/" in str(out.resolve()) else str(out)
        except Exception:
            rel_path = str(out)
        evidence.append(
            {
                "evidence_id": f"{vid}_coarse_{i}",
                "video_id": vid,
                "time_s": t,
                "path": rel_path,
                "kind": "coarse_scan_frame",
                "time_unit": "seconds_file_clock",
            }
        )
        events.append(
            _event(
                event_id=f"{vid}_coarse_vis_{i}",
                video_id=vid,
                t0=t,
                t1=t + 1,
                actor=f"scene_local_{i}",
                verb="visual_sample",
                confidence=0.35,
                evidence_paths=[rel_path],
                observed_vs_inferred="observed",
                source="FRAME_VISUAL_OBSERVATION",
                unresolved_flags=["coarse_unlabeled"],
                notes="Coarse scan only; not a semantic gold event",
            )
        )

    # Merge curated events (fixtures — not newly discovered)
    for ev in CURATED.get(vid, []):
        ev = dict(ev)
        ev["from_curated_dict"] = True
        ev["provenance_tier"] = "CURATED_FROM_PRIOR_HUMAN_OR_CHATGPT_AUDIT"
        ev["is_curated_fixture"] = True
        ev["is_newly_discovered_semantic"] = False
        events.append(ev)
        for p in ev.get("evidence_paths") or []:
            evidence.append(
                {
                    "evidence_id": f"{ev['event_id']}_ev",
                    "video_id": vid,
                    "time_s": ev["time_start_s"],
                    "path": p,
                    "kind": "curated_review_asset",
                    "time_unit": "seconds_file_clock",
                    "provenance_tier": "CURATED_FROM_PRIOR_HUMAN_OR_CHATGPT_AUDIT",
                }
            )

    # New frame visual observations (this round; not curated recycle)
    for ev in NEW_FRAME_OBSERVATIONS.get(vid, []):
        events.append(ev)
        for p in ev.get("evidence_paths") or []:
            evidence.append(
                {
                    "evidence_id": f"{ev['event_id']}_ev",
                    "video_id": vid,
                    "time_s": ev["time_start_s"],
                    "path": p,
                    "kind": "new_frame_observation",
                    "time_unit": "seconds_file_clock",
                    "provenance_tier": ev.get("provenance_tier"),
                }
            )

    # Seed frames from construction assets if present (coarse placeholders only)
    seed_dir = Path("research_audit/lvbench_compositional/track_b/construction_discovery_assets") / vid
    if seed_dir.is_dir():
        for j, p in enumerate(sorted(seed_dir.glob("seed_frame_*.jpg"))[:3]):
            # Parse tNNNN from filename when present
            t_s = 0.0
            import re as _re

            m = _re.search(r"_t(\d+)", p.stem)
            if m:
                t_s = float(m.group(1))
            # Skip duplicate seed placeholder if NEW_FRAME_OBSERVATION already covers this time
            if any(
                abs(e["time_start_s"] - t_s) < 1.0 and e.get("provenance_tier") == "CURSOR_FRAME_VISUAL_OBSERVATION"
                for e in events
            ):
                continue
            events.append(
                _event(
                    event_id=f"{vid}_seed_{j}",
                    video_id=vid,
                    t0=t_s,
                    t1=t_s + 1,
                    actor=f"seed_local_{j}",
                    verb="seed_frame_present",
                    confidence=0.4,
                    evidence_paths=[str(p)],
                    unresolved_flags=["time_from_filename_only", "semantics_unlabeled"],
                    notes=p.name,
                    provenance_tier="AUTOMATIC_COARSE_FRAME",
                )
            )

    n_new = sum(1 for e in events if e.get("is_newly_discovered_semantic"))
    n_cur = sum(1 for e in events if e.get("is_curated_fixture"))
    return {
        "video_id": vid,
        "status": "OK" if not any(f.startswith("EXTRACTION_FAILED") and len(evidence) == 0 for f in flags) else "PARTIAL",
        "events": events,
        "evidence": evidence,
        "flags": flags,
        "n_events": len(events),
        "n_curated": n_cur,
        "n_new_semantic": n_new,
        "n_coarse": sum(1 for e in events if e["verb"] == "visual_sample"),
        "semantic_extractor_status": (
            "CURSOR_FRAME_OBSERVATIONS_PRESENT"
            if n_new
            else ("CURATED_ONLY" if n_cur else "BLOCKED_NO_SEMANTIC_EXTRACTOR")
        ),
    }
