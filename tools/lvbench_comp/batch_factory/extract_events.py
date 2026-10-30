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
    notes: str = "",
) -> dict[str, Any]:
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
        "notes": notes,
        "identity_link": {"status": "LOCAL_ONLY", "match_confidence": None, "distractors": []},
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

    # Merge curated events (higher priority)
    for ev in CURATED.get(vid, []):
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
                }
            )

    # Seed frames from construction assets if present
    seed_dir = Path("research_audit/lvbench_compositional/track_b/construction_discovery_assets") / vid
    if seed_dir.is_dir():
        for j, p in enumerate(sorted(seed_dir.glob("seed_frame_*.jpg"))[:3]):
            events.append(
                _event(
                    event_id=f"{vid}_seed_{j}",
                    video_id=vid,
                    t0=0,
                    t1=1,
                    actor=f"seed_local_{j}",
                    verb="seed_frame_present",
                    confidence=0.4,
                    evidence_paths=[str(p)],
                    unresolved_flags=["time_from_filename_only", "semantics_unlabeled"],
                    notes=p.name,
                )
            )

    return {
        "video_id": vid,
        "status": "OK" if not any(f.startswith("EXTRACTION_FAILED") and len(evidence) == 0 for f in flags) else "PARTIAL",
        "events": events,
        "evidence": evidence,
        "flags": flags,
        "n_events": len(events),
        "n_curated": len(CURATED.get(vid, [])),
        "n_coarse": sum(1 for e in events if e["verb"] == "visual_sample"),
    }
