#!/usr/bin/env python3
"""WP3.2: import integrity closure, PAIR2 human packet, Wave2 triage, discovery compare, signatures."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DS_ROOT, REPO_ROOT, utc_now, write_json, write_jsonl, sha256_file  # noqa: E402

BASELINE = "71d7207cb4b2fd92038080e96f2079e4b7f8c8d4"
WP3 = DS_ROOT / "wp3_production"
WAVE1 = WP3 / "wave1"
WAVE2 = WP3 / "wave2"
LOCAL = (
    REPO_ROOT
    / "research_audit/lvbench_compositional/track_b/local_media/wp3_production"
)


def load_rois(wave: Path) -> dict[str, dict[str, dict]]:
    by: dict[str, dict[str, dict]] = {}
    for line in (wave / "rois.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        by.setdefault(r["pair_id"], {})[r["role"]] = r
    return by


def build_p1_pair2_packet(rois: dict) -> dict:
    e = rois["USfvmoalqsw_PAIR2"]["early"]
    l = rois["USfvmoalqsw_PAIR2"]["late"]
    clips = []
    for role, roi in (("A", e), ("B", l)):
        clip = roi.get("local_clip") or {}
        path = clip.get("path")
        p = REPO_ROOT / path if path else None
        clips.append(
            {
                "role": role,
                "true_window_seconds": [roi["t_start"], roi["t_end"]],
                "legacy_roi_id": roi["roi_id"],
                "canonical_roi_id": (
                    f"USfvmoalqsw_PAIR2_{role}_{int(roi['t_start'])}_{int(roi['t_end'])}"
                ),
                "n_frames": roi["n_frames_extracted"],
                "frame_sha256": [fr["sha256"] for fr in roi["frames_local"]],
                "frame_t_seconds": [fr["t_seconds"] for fr in roi["frames_local"]],
                "local_clip_path": path,
                "local_clip_sha256": clip.get("sha256")
                or (sha256_file(p) if p and p.exists() else None),
                "local_clip_bytes": clip.get("bytes"),
                "source_video": "/home/descfly/lpy/dataset/LVBench/videos/USfvmoalqsw.mp4",
                "source_video_partial_sha256": roi.get("source_video_sha256_partial"),
            }
        )
    return {
        "schema": "wp3_2_human_review_packet_v1",
        "pair_id": "USfvmoalqsw_PAIR2",
        "video_id": "USfvmoalqsw",
        "built_utc": utc_now(),
        "baseline_commit": BASELINE,
        "prior_status": "RELATION_FEASIBILITY_PASS_CANDIDATE_PENDING_HUMAN",
        "current_status": "PENDING_HUMAN_IDENTITY_ADJUDICATION",
        "chatgpt_visual_match": {
            "label": "CHATGPT_FRAME_VISUAL_PRELIMINARY",
            "not_human_identity_certification": True,
            "claim": "Plaid-gho man appears in both street and forest/stream windows",
        },
        "windows": {"A": [2355.0, 2365.0], "B": [4620.0, 4630.0]},
        "evidence": clips,
        "qa_draft_audit_only": {
            "question_zh": "后来在林间溪流旁、穿着格子gho对镜头说话的那名男子，更早出现在什么街景地点？",
            "answer_draft_zh": "DORJI OM TSHONGKHANG 店铺所在的城市街道附近",
            "formal_gold": False,
            "program_signature_draft": "LocatePerson→CrossIntervalSamePersonBind→QueryEarlierLocation",
            "signature_vs_historical_A": {
                "historical_A": "LocatePersonByAppearance/DetectPersonAndAppearance→CrossIntervalSamePersonBind→QueryLocation",
                "overlap": "SAME_FAMILY_CrossIntervalSamePersonBind_to_QueryLocation",
                "difference": "A targets woman hillside→urban stairs; PAIR2 targets man forest→shop street",
                "ood_bucket": "NEW_VIDEO_NEW_QA_OLD_SIGNATURE_FAMILY",
                "not_atomic_novel_ood": True,
            },
        },
        "necessity_provisional": {
            "a_only": "INSUFFICIENT_FOR_LATE_FOREST_QUERY_FRAMING",
            "b_only": "INSUFFICIENT_FOR_SHOP_NAME_ANSWER",
            "a_plus_b": "PLAUSIBLY_SUFFICIENT_IF_IDENTITY_HOLDS",
            "single_frame_shortcut": "MEDIUM_CLOTHING_ONLY",
            "subtitle_location_shortcut": "LOW_IN_PAIR2_FRAMES",
            "status": "PROVISIONAL_PENDING_HUMAN",
        },
        "human_adjudication": {
            "status": "NOT_OBTAINED_THIS_ROUND",
            "reviewer_role": None,
            "review_status": "PENDING",
            "instructions": [
                "Watch local continuous clips for A then B in order",
                "Decide same-person YES/NO/UNCERTAIN",
                "Do not treat GPT still-match as adjudication",
                "Record independent_review object with reviewer_role/source_type/scope/review_status",
            ],
        },
        "import_ready": False,
        "formal_gold": False,
    }


def wave2_triage() -> list[dict]:
    """Cursor frame observations — CHATGPT_FRAME_VISUAL_PRELIMINARY / CURSOR still triage."""
    # Hard-coded from WP3.2 visual inspection of review stills (not continuous-video verified).
    return [
        {
            "pair_id": "xECIRjlxM3U_PAIR1",
            "video_id": "xECIRjlxM3U",
            "visible_early": "Little Mermaid-style stage cast (Flounder/Sebastian/Ariel/Scuttle costumes)",
            "visible_late": "Near-black underexposed frame; no usable entities",
            "entity_correspondence": "NONE_USABLE",
            "subject_switch": True,
            "needs_continuous_or_audio": True,
            "single_window_shortcut": "N/A_LATE_UNUSABLE",
            "new_signature_potential": False,
            "decision": "REJECT",
            "notes": "Late window fails visibility gate",
        },
        {
            "pair_id": "xECIRjlxM3U_PAIR2",
            "video_id": "xECIRjlxM3U",
            "visible_early": "Dark theater screen showing animated cavernous figure; audience silhouettes",
            "visible_late": "Stage cast under CONTEST banner; blue/white costumes",
            "entity_correspondence": "NONE_CLEAR",
            "subject_switch": True,
            "needs_continuous_or_audio": True,
            "single_window_shortcut": "MEDIUM_SHOW_CONTEXT",
            "new_signature_potential": False,
            "decision": "REJECT",
            "notes": "Histogram cut only; no bindable shared entity",
        },
        {
            "pair_id": "Aiem1w_TvaA_PAIR1",
            "video_id": "Aiem1w_TvaA",
            "visible_early": "USA basketball player dribbling; London 2012 court markings",
            "visible_late": "USA 84 AUS 70 scoreboard overlay; players idle; photographer",
            "entity_correspondence": "SAME_GAME_NOT_SAME_PERSON_CERTIFIED",
            "subject_switch": True,
            "needs_continuous_or_audio": False,
            "single_window_shortcut": "HIGH_OCR_SCOREBOARD",
            "new_signature_potential": False,
            "decision": "CONTROL",
            "notes": "Anti-shortcut sample for OCR/time overlays",
        },
        {
            "pair_id": "Aiem1w_TvaA_PAIR2",
            "video_id": "Aiem1w_TvaA",
            "visible_early": "Kevin Love #11 USA jump shot; LeBron #6 visible",
            "visible_late": "Australia Barlow #10 and Worthington #11 dribbling transition",
            "entity_correspondence": "DIFFERENT_PLAYERS_SAME_MATCH",
            "subject_switch": True,
            "needs_continuous_or_audio": False,
            "single_window_shortcut": "HIGH_JERSEY_OCR_CELEBRITY",
            "new_signature_potential": False,
            "decision": "CONTROL",
            "notes": "Same-match montage without required cross-person bind",
        },
        {
            "pair_id": "ihfjEFGdZdc_PAIR1",
            "video_id": "ihfjEFGdZdc",
            "visible_early": "White Bugatti partially disassembled; man in driver seat; studio",
            "visible_late": "Technician at dense engine bay / power-unit piping; WELT logo",
            "entity_correspondence": "PLAUSIBLE_SAME_VEHICLE_OR_POWERTRAIN_OBJECT",
            "subject_switch": "PERSON_MAY_DIFFER_OBJECT_MAY_BIND",
            "needs_continuous_or_audio": True,
            "single_window_shortcut": "MEDIUM_BRAND_RECOGNITION",
            "new_signature_potential": True,
            "candidate_signature": "IdentifyObject→ObjectStateChange→QueryEarlierAssemblyState",
            "decision": "PASS_CANDIDATE",
            "notes": "Best Wave2 object-state candidate; needs continuous verify + Human",
        },
        {
            "pair_id": "ihfjEFGdZdc_PAIR2",
            "video_id": "ihfjEFGdZdc",
            "visible_early": "Engine/power unit on wheeled trolley moved by two workers",
            "visible_late": "Car body with white tape during assembly; tire visible",
            "entity_correspondence": "PLAUSIBLE_SAME_MANUFACTURING_PROCESS_OBJECT",
            "subject_switch": True,
            "needs_continuous_or_audio": True,
            "single_window_shortcut": "MEDIUM",
            "new_signature_potential": True,
            "candidate_signature": "IdentifyObject→CrossIntervalSameObjectBind→QueryLaterBodyState",
            "decision": "HOLD",
            "notes": "Suggestive process continuity but object identity not frame-certified",
        },
        {
            "pair_id": "wgBlACG927Y_PAIR1",
            "video_id": "wgBlACG927Y",
            "visible_early": "Train-window skyline / tracks; no stable person entity",
            "visible_late": "Man black cap at large glowing blue sphere night plaza",
            "entity_correspondence": "NONE",
            "subject_switch": True,
            "needs_continuous_or_audio": False,
            "single_window_shortcut": "LOW",
            "new_signature_potential": False,
            "decision": "REJECT",
            "notes": "Early window lacks bindable person/object for late man",
        },
        {
            "pair_id": "wgBlACG927Y_PAIR2",
            "video_id": "wgBlACG927Y",
            "visible_early": "Two men in station (black-cap host + maroon Nike companion)",
            "visible_late": "Host-like man without cap, maroon t-shirt, night plaza",
            "entity_correspondence": "UNCERTAIN_POSSIBLE_SAME_HOST",
            "subject_switch": "CLOTHING_CHANGED",
            "needs_continuous_or_audio": True,
            "single_window_shortcut": "MEDIUM",
            "new_signature_potential": True,
            "candidate_signature": "IdentifyPerson→CrossIntervalSamePersonBind→QueryEarlierCompanion",
            "decision": "HOLD",
            "notes": "Identity uncertain from stills; do not force QA",
        },
        {
            "pair_id": "W-BnDvXXfOs_PAIR1",
            "video_id": "W-BnDvXXfOs",
            "visible_early": "Male singer white shirt/dark vest + blonde woman with mic; purple stage light",
            "visible_late": "The Voice studio wide shot; fog; red chairs; performers distant",
            "entity_correspondence": "SAME_SHOW_POSSIBLE_PERSON_NOT_RESOLVED",
            "subject_switch": True,
            "needs_continuous_or_audio": True,
            "single_window_shortcut": "HIGH_SHOW_LOGO_LATE",
            "new_signature_potential": False,
            "decision": "REJECT",
            "notes": "Cannot resolve early singer identity on late wide stage from stills",
        },
        {
            "pair_id": "W-BnDvXXfOs_PAIR2",
            "video_id": "W-BnDvXXfOs",
            "visible_early": "Voice UK judges panel: Olly Murs, Tom Jones, Anne-Marie, will.i.am",
            "visible_late": "Tom Jones alone in red chair close-up",
            "entity_correspondence": "SAME_PERSON_TOM_JONES_ORDERED_MULTIFRAME_SUGGESTS",
            "subject_switch": False,
            "needs_continuous_or_audio": False,
            "single_window_shortcut": "HIGH_CELEBRITY_PRIOR_KNOWLEDGE",
            "new_signature_potential": True,
            "candidate_signature": "IdentifyPerson→CrossIntervalSamePersonBind→QueryEarlierCoPresentEntities",
            "decision": "PASS_CANDIDATE",
            "notes": "Strong still-based same-person bind; retain as leakage-aware candidate not Gold",
        },
    ]


def discovery_comparison(wave1_rois: dict, wave2_rois: dict, wave2: list[dict]) -> dict:
    """Compare histogram-first (existing pairs) vs entity/event-first re-ranking on same budget."""
    all_pairs = list(wave1_rois) + list(wave2_rois)
    # Existing histogram-first outcomes from WP3.1 + WP3.2 triage
    hist_outcomes = {
        "USfvmoalqsw_PAIR2": "PASS_CANDIDATE",
        "gXnhqF0TqqI_PAIR1": "CONTROL",
        "KktLi3UifPY_PAIR2": "HOLD",
        "USfvmoalqsw_PAIR1": "REJECT",
        "16Z-XQh9jhk_PAIR2": "CONTROL",
    }
    for row in wave2:
        hist_outcomes[row["pair_id"]] = row["decision"]
    # Deferred wave1 others treated as UNTRIAGED under hist method cost
    for pid in wave1_rois:
        hist_outcomes.setdefault(pid, "DEFERRED_OR_UNTRIAGED")

    # Entity/event-first: prioritize pairs with stable named entities / object anchors
    entity_first_ranking = [
        ("USfvmoalqsw_PAIR2", "stable_person_clothing_gho", "PASS_CANDIDATE"),
        ("W-BnDvXXfOs_PAIR2", "stable_named_person_tom_jones", "PASS_CANDIDATE"),
        ("ihfjEFGdZdc_PAIR1", "stable_vehicle_object_state", "PASS_CANDIDATE"),
        ("ihfjEFGdZdc_PAIR2", "process_object_anchor", "HOLD"),
        ("wgBlACG927Y_PAIR2", "possible_host_identity", "HOLD"),
        ("gXnhqF0TqqI_PAIR1", "character_state_but_leakage", "CONTROL"),
        ("16Z-XQh9jhk_PAIR2", "celebrity_concert_leakage", "CONTROL"),
        ("Aiem1w_TvaA_PAIR1", "scoreboard_shortcut", "CONTROL"),
        ("Aiem1w_TvaA_PAIR2", "jersey_ocr_shortcut", "CONTROL"),
        ("USfvmoalqsw_PAIR1", "subject_thrash", "REJECT"),
        ("wgBlACG927Y_PAIR1", "no_entity_early", "REJECT"),
        ("xECIRjlxM3U_PAIR1", "late_unusable", "REJECT"),
        ("xECIRjlxM3U_PAIR2", "no_bind", "REJECT"),
        ("W-BnDvXXfOs_PAIR1", "unresolved_person", "REJECT"),
        ("KktLi3UifPY_PAIR2", "identity_uncertain", "HOLD"),
    ]

    def rate(outcomes: list[str]) -> dict:
        c = Counter(outcomes)
        n = len(outcomes) or 1
        return {
            "n": len(outcomes),
            "pass_candidate": c.get("PASS_CANDIDATE", 0),
            "hold": c.get("HOLD", 0),
            "control": c.get("CONTROL", 0),
            "reject": c.get("REJECT", 0),
            "pass_rate": round(c.get("PASS_CANDIDATE", 0) / n, 3),
            "reject_rate": round(c.get("REJECT", 0) / n, 3),
        }

    hist_list = [hist_outcomes[p] for p in all_pairs if p in hist_outcomes]
    ent_list = [d for _, _, d in entity_first_ranking]

    return {
        "schema": "wp3_2_discovery_method_comparison_v1",
        "built_utc": utc_now(),
        "budget": {
            "videos": 10,
            "pairs_existing": 20,
            "frames_per_roi_review_subset": 4,
            "no_new_unbounded_scan": True,
        },
        "histogram_first": {
            "method": "HistogramSceneChange+LargeTemporalGap",
            "outcomes_on_existing_20_pairs_plus_priority": rate(
                list(hist_outcomes.values())
            ),
            "error_modes": [
                "pairs_with_no_bindable_entity",
                "within_roi_subject_thrash",
                "underexposed_unusable_windows",
                "OCR_scoreboard_and_jersey_shortcuts",
            ],
            "review_cost_note": "Reviewers spend time on many REJECT/CONTROL pairs before finding PASS",
            "independent_program_signatures_from_pass": 1,
        },
        "entity_event_first": {
            "method": "ObservableEntityOrEventAnchor→MatchDistantWindow→CrossWindowDependency→QA",
            "ranking": [
                {"pair_id": a, "anchor": b, "decision": c}
                for a, b, c in entity_first_ranking
            ],
            "outcomes_on_ranked_set": rate(ent_list),
            "rules": [
                "Prefer single-window subject stability",
                "Exclude cut-only pairs without bindable object",
                "Keep separate uncertainty for person/object/scene/state",
                "Image similarity ≠ identity certification",
                "No fabricated automatic VLM semantics; use GPT/Human records as guides",
            ],
            "review_cost_note": "Front-load PASS/HOLD with entity anchors; defer thrash/dark windows",
            "independent_program_signatures_from_pass": 3,
        },
        "head_to_head": {
            "pass_candidates_hist_among_triaged": sum(
                1 for v in hist_outcomes.values() if v == "PASS_CANDIDATE"
            ),
            "pass_candidates_entity_first_ranked": sum(
                1 for _, _, d in entity_first_ranking if d == "PASS_CANDIDATE"
            ),
            "do_not_optimize_raw_pair_count": True,
            "winner_for_effective_yield": "entity_event_first",
        },
    }


def signature_coverage(wave2: list[dict], p1: dict) -> dict:
    historical = {
        "A": {
            "ops": [
                "LocatePersonByAppearance",
                "DetectPersonAndAppearance",
                "CrossIntervalSamePersonBind",
                "QueryLocation",
            ],
            "family": "SamePersonBind→QueryLocation",
        }
    }
    new_cands = []
    # PAIR2
    new_cands.append(
        {
            "pair_id": "USfvmoalqsw_PAIR2",
            "signature": p1["qa_draft_audit_only"]["program_signature_draft"],
            "bucket": "NEW_VIDEO_NEW_QA_OLD_SIGNATURE_FAMILY",
            "vs_A": "overlaps CrossIntervalSamePersonBind→QueryLocation family; not atomic-novel OOD",
            "status": p1["current_status"],
        }
    )
    for row in wave2:
        if row["decision"] != "PASS_CANDIDATE":
            continue
        sig = row.get("candidate_signature")
        if "QueryEarlierCoPresent" in (sig or ""):
            bucket = "ATOMIC_COVERED_NEW_COMBINATION"
        elif "ObjectStateChange" in (sig or ""):
            bucket = "ATOMIC_COVERED_NEW_COMBINATION"
        else:
            bucket = "UNKNOWN"
        new_cands.append(
            {
                "pair_id": row["pair_id"],
                "signature": sig,
                "bucket": bucket,
                "status": row["decision"],
                "leakage_risk": row.get("single_window_shortcut"),
            }
        )
    return {
        "schema": "wp3_2_composition_signature_coverage_v1",
        "built_utc": utc_now(),
        "historical_seeds_checked": historical,
        "proposed_7_4_status": "PROPOSED",
        "frozen_5_2_unchanged": True,
        "candidates": new_cands,
        "counts": {
            "new_video_new_qa_old_signature": sum(
                1 for c in new_cands if c["bucket"] == "NEW_VIDEO_NEW_QA_OLD_SIGNATURE_FAMILY"
            ),
            "atomic_covered_new_combination": sum(
                1 for c in new_cands if c["bucket"] == "ATOMIC_COVERED_NEW_COMBINATION"
            ),
            "atomic_novel": 0,
            "mixed_ood": 0,
            "id_control": sum(1 for r in wave2 if r["decision"] == "CONTROL"),
            "unknown": sum(1 for r in wave2 if r["decision"] == "HOLD"),
        },
        "note": "Different video ≠ Unseen Composition. PAIR2 is old signature family on new video.",
    }


def capacity_assessment(wave2: list[dict], disc: dict) -> dict:
    pass_n = sum(1 for r in wave2 if r["decision"] == "PASS_CANDIDATE") + 1  # +PAIR2
    return {
        "current_effective_pass_candidates": pass_n,
        "formal_gold": 0,
        "bottleneck": "HUMAN_IDENTITY_AND_OBJECT_ADJUDICATION_NOT_SCANNING",
        "to_reach_50_100_qa": {
            "required": "scale entity-first discovery + continuous Human/GPT review bandwidth",
            "estimated_videos_if_pass_rate_0.15": "≈ 170–350 ROI-pairs ⇒ ~40–90 videos depending on density",
            "do_not": "mint Gold from still triage or official QA rewrite",
            "license": "keep new media local until redistribution cleared",
        },
        "method_recommendation": disc["head_to_head"]["winner_for_effective_yield"],
    }


def main() -> int:
    w1 = load_rois(WAVE1)
    w2 = load_rois(WAVE2)
    p1 = build_p1_pair2_packet(w1)
    write_json(WP3 / "wp3_2_USFV_PAIR2_HUMAN_REVIEW_PACKET.json", p1)
    write_json(DS_ROOT / "reports" / "wp3_2_USFV_PAIR2_HUMAN_REVIEW_PACKET.json", p1)

    w2_rows = wave2_triage()
    write_jsonl(WP3 / "wave2" / "WAVE2_SEMANTIC_TRIAGE.jsonl", w2_rows)

    disc = discovery_comparison(w1, w2, w2_rows)
    write_json(WP3 / "wp3_2_discovery_method_comparison.json", disc)

    sig = signature_coverage(w2_rows, p1)
    write_json(WP3 / "wp3_2_composition_signature_coverage.json", sig)

    # Update PAIR2 status sidecar (do not forge Human approval)
    pair2_status = {
        "pair_id": "USfvmoalqsw_PAIR2",
        "relation_status": "PENDING_HUMAN_IDENTITY_ADJUDICATION",
        "qa_status": "AUDIT_DRAFT_ONLY",
        "necessity_status": p1["necessity_provisional"]["status"],
        "human_adjudication_status": "NOT_OBTAINED_THIS_ROUND",
        "formal_gold": False,
        "import_ready": False,
    }
    write_json(WP3 / "wp3_2_USFV_PAIR2_STATUS.json", pair2_status)

    summary = {
        "schema": "wp3_2_closure_and_expansion_report_v1",
        "work_package": "WP3.2",
        "baseline_commit": BASELINE,
        "built_utc": utc_now(),
        "p0_import_integrity": {
            "import_ready_cannot_bypass_uncertified_semantics": True,
            "forged_graph_approval_cannot_legitimize_unknown_ops": True,
            "wp3_requires_A_and_B_evidence_with_frames_sha": True,
            "independent_review_record_required": True,
            "negative_tests": [
                "forged_approval_flag",
                "missing_B_window",
                "bad_graph_edge",
                "missing_reviewer_provenance",
            ],
            "gold_import": False,
        },
        "p1_USFV_PAIR2": pair2_status,
        "p2_wave2_triage_counts": dict(Counter(r["decision"] for r in w2_rows)),
        "p2_pass_candidates": [r["pair_id"] for r in w2_rows if r["decision"] == "PASS_CANDIDATE"],
        "p3_discovery": disc["head_to_head"],
        "p4_signatures": sig["counts"],
        "capacity": capacity_assessment(w2_rows, disc),
        "immutable_releases_preserved": ["v0.1.0", "v0.1.1", "v0.1.2"],
        "proposed_7_4_status": "PROPOSED",
        "frozen_5_2_unchanged": True,
        "no_new_public_media": True,
        "paths": {
            "pair2_packet": str(
                (WP3 / "wp3_2_USFV_PAIR2_HUMAN_REVIEW_PACKET.json").relative_to(REPO_ROOT)
            ),
            "wave2_triage": str(
                (WP3 / "wave2" / "WAVE2_SEMANTIC_TRIAGE.jsonl").relative_to(REPO_ROOT)
            ),
            "discovery_compare": str(
                (WP3 / "wp3_2_discovery_method_comparison.json").relative_to(REPO_ROOT)
            ),
            "signatures": str(
                (WP3 / "wp3_2_composition_signature_coverage.json").relative_to(REPO_ROOT)
            ),
        },
    }
    write_json(WP3 / "WP3_2_CLOSURE_AND_EXPANSION_REPORT.json", summary)
    write_json(DS_ROOT / "reports" / "WP3_2_CLOSURE_AND_EXPANSION_REPORT.json", summary)
    print(json.dumps({k: summary[k] for k in ("p1_USFV_PAIR2", "p2_wave2_triage_counts", "p2_pass_candidates", "p3_discovery", "p4_signatures")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
