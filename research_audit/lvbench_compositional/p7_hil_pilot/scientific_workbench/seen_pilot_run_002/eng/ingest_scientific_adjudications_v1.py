#!/usr/bin/env python3
"""LEGACY ingest for run_002 (v0.4-era SP205 conditional + media repair bookkeeping).

Superseded for scientific decisions by:
  eng/sync_scientific_adjudications_all6_v1.py
  (handoff: scientific_reviews/handoff/run_002_scientific_adjudications_all6_v1.json)

This script REFUSES to overwrite SP205 once graph_version >= v0.5 so a re-run
cannot roll USER_APPROVED v0.5 / USER_ASSIGNED_UNSEEN back to CONDITIONAL v0.4.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PILOT = Path(__file__).resolve().parents[1]
WB = PILOT.parent
REV = PILOT / "scientific_reviews"
GATES = {
    "formal_seen_train": False,
    "formal_unseen": False,
    "formal_gold": False,
    "train_exposed": False,
    "seen_pool_frozen": False,
    "approve_expensive_track_a_rsi": False,
}


def _refuse_if_v05_present() -> None:
    """Hard guard: never rewrite current SP205 pointer if all6 v0.5 already synced."""
    cur = REV / "RECORDS_BY_PACK/SP205.json"
    if not cur.exists():
        return
    d = json.loads(cur.read_text(encoding="utf-8"))
    ver = str(d.get("graph_version") or "")
    decision = d.get("user_decision") or ""
    split = d.get("user_split_decision") or ""
    if ver.startswith("v0.5") or split == "USER_ASSIGNED_UNSEEN":
        print(
            "REFUSING legacy ingest_scientific_adjudications_v1.py: "
            f"SP205 already at {ver} ({decision}; {split}). "
            "Use sync_scientific_adjudications_all6_v1.py instead. "
            "Will not roll back to CONDITIONAL v0.4.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    idx = REV / "INDEX.json"
    if idx.exists():
        ix = json.loads(idx.read_text(encoding="utf-8"))
        if ix.get("sp205_graph_version") == "v0.5" or "SP205" in (ix.get("user_assigned_unseen") or []):
            print(
                "REFUSING legacy ingest: INDEX marks SP205 v0.5 / USER_ASSIGNED_UNSEEN. "
                "Use sync_scientific_adjudications_all6_v1.py.",
                file=sys.stderr,
            )
            raise SystemExit(2)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1024 * 1024), b""):
            h.update(c)
    return h.hexdigest()


def dump(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def base_rec(pack_id: str, **kwargs) -> dict:
    return {
        "schema": "seen_pilot_run_002_scientific_record_v1",
        "run_id": "seen_pilot_run_002",
        "pack_id": pack_id,
        **GATES,
        "ingested_utc": utc_now(),
        "branch_note": "Artifacts live on research/lvbench-comp-p7-hil-pilot (run_002 baseline fa98aae); not video-grounded-evidence branch.",
        **kwargs,
    }


def main() -> None:
    _refuse_if_v05_present()
    # --- SP205 media repair ---
    a_full = PILOT / "media/SP205/A_wgBlACG927Y_202_370.mp4"
    a_trunc = PILOT / "media/SP205/A_wgBlACG927Y_202_322.mp4"
    b_clip = PILOT / "media/SP205/B_wgBlACG927Y_838_852.mp4"
    assert a_full.exists(), "restored A missing"
    sp205_repair = {
        "pack_id": "SP205",
        "before": {
            "relpath": "seen_pilot_run_002/media/SP205/A_wgBlACG927Y_202_322.mp4",
            "coverage_source_s": [202, 322],
            "coverage_clock": "03:22-05:22",
            "sha256": sha256_file(a_trunc) if a_trunc.exists() else None,
            "bytes": a_trunc.stat().st_size if a_trunc.exists() else None,
            "issue": "truncated_for_review_cost; missing human-confirmed disembark span 05:22-06:10",
        },
        "after": {
            "relpath": "seen_pilot_run_002/media/SP205/A_wgBlACG927Y_202_370.mp4",
            "coverage_source_s": [202, 370],
            "coverage_clock": "03:22-06:10",
            "sha256": sha256_file(a_full),
            "bytes": a_full.stat().st_size,
            "duration_s": 168.0,
        },
        "B_unchanged": {
            "relpath": "seen_pilot_run_002/media/SP205/B_wgBlACG927Y_838_852.mp4",
            "coverage_clock": "13:58-14:12",
            "sha256": sha256_file(b_clip),
        },
        "human_vs_model_evidence": {
            "HUMAN_REVIEWED_EVIDENCE": [
                "03:22-05:22 board HSR",
                "05:22-06:10 disembark HSR",
                "06:10-13:58 human continuity check: no other transport observed",
                "13:58-14:12 subway",
            ],
            "MODEL_ACCESSIBLE_EVIDENCE_CLIP_ONLY": [
                "A clip 03:22-06:10 (restored)",
                "B clip 13:58-14:12",
            ],
            "MODEL_NOT_ACCESSIBLE_UNDER_CLIP_ONLY": [
                "06:10-13:58 continuous segment used for no-other-transport temporal claim"
            ],
            "blocker": "MODEL_ACCESSIBLE_TEMPORAL_GAP_06:10-13:58",
            "note": "Human-reviewed middle span must not be silently treated as model-seen under clip-only protocol.",
        },
        "engineering_sparse_frame_note": {
            "sampled_relative_s_near_A_end": [150, 166],
            "observation": "Sparse stills near A end still show train interior/vestibule; does not independently confirm or refute brief disembark—full restored A is the review medium.",
            "does_not_override_human_observations": True,
        },
        "conditional_promotion": {
            "requested_status_if_all_gates_pass": "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH",
            "current_user_decision": "CONDITIONAL_USER_APPROVAL_PENDING_ENGINEERING_ACCEPTANCE",
            "gates": {
                "A_media_restored_03_22_to_06_10": True,
                "first_transport_scope_supported_in_A": True,
                "critical_temporal_relation_model_accessible": False,
                "manifest_sha_isolation_ok": True,
                "no_new_fact_conflict_forcing_retract": True,
            },
            "promoted": False,
            "reason_not_promoted": "Clip-only protocol cannot access 06:10-13:58 continuity evidence required for TemporalSuccessor/no-other-transport necessity as reviewed by human.",
        },
    }
    dump(REV / "engineering_checks/SP205_A_media_repair.json", sp205_repair)

    records = []

    # SP201
    r201 = base_rec(
        "SP201",
        video_id="Hf-n1yfd8II",
        qa_uid="LVCOMP-V2-001",
        windows_seconds={"A": [2880, 2897], "B": [5413, 5440]},
        user_decision="USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH",
        graph_version="v0.2",
        human_observations=[
            "A (48:00-48:17): blue-jersey player loses a point and shows frustration.",
            "B (90:13-90:40): blue-jersey Malaysian player ultimately wins the whole match.",
            "Deciding game 22:20; prior games 1:1; match result 2:1.",
            "Human confirms A and B are the same player.",
            "A-only cannot confirm final winner; B-only cannot confirm earlier emotion.",
        ],
        scientific_inferences=[
            "Cross-window person bind required between winner identity (B) and emotion query (A).",
        ],
        directed_program_graph={
            "program": "DetermineMatchWinner(B) → CrossWindowPersonBind → QueryEmotion(A)",
            "answer_candidate": "frustrated (lose the rally/point)",
        },
        evidence_limitations=[
            "Must not concretize 'lost the point in that rally' into 'failed to receive opponent's shuttlecock' without separate visual proof.",
        ],
        single_window_necessity_audit={
            "a_only_sufficient_full_question": "否",
            "b_only_sufficient_full_question": "否",
            "a_plus_b_necessary": "是",
        },
        engineering_status="RECORDED",
        promotion_gate="CANDIDATE_ONLY_NOT_FORMAL_SEEN",
        shared_video_with=["SP202"],
    )
    dump(REV / "RECORDS_BY_PACK/SP201.json", r201)
    records.append(r201)
    dump(
        REV / "APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS/SP201_v0.2.json",
        {
            "graph_id": "seen_pilot_run_002::SP201::v0.2",
            "user_confirmation_status": "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH",
            "program": r201["directed_program_graph"],
            **GATES,
            "note": "Candidate only; not formal Seen/Gold.",
        },
    )

    # SP202
    r202 = base_rec(
        "SP202",
        video_id="Hf-n1yfd8II",
        qa_uid="LVCOMP-V2-040",
        windows_seconds={"A": [510, 515], "B": [5413, 5440]},
        user_decision="USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH",
        graph_version="v0.3",
        human_observations=[
            "A (08:30-08:35): blue-jersey Lee Chong Wei serves first.",
            "Flag and English name support person ID; score 0:0.",
            "User checked full timeline: this is game-1 opening, not a later-game opening.",
            "B confirms Lee Chong Wei ultimately wins the match.",
            "A-only and B-only cannot establish the full relation alone.",
        ],
        scientific_inferences=[
            "Identify first server in A, bind to match-result query in B.",
        ],
        directed_program_graph={
            "program": "IdentifyFirstServer(A) → CrossWindowPersonBind → QueryMatchResult(B)",
            "answer_candidate": "final winner / wins the match",
        },
        evidence_limitations=[
            "Shares video Hf-n1yfd8II and B window with SP201 — must not count as two independent videos.",
        ],
        single_window_necessity_audit={
            "a_only_sufficient_full_question": "否",
            "b_only_sufficient_full_question": "否",
            "a_plus_b_necessary": "是",
        },
        engineering_status="RECORDED",
        promotion_gate="CANDIDATE_ONLY_NOT_FORMAL_SEEN",
        shared_video_with=["SP201"],
        shared_B_window_with=["SP201"],
    )
    dump(REV / "RECORDS_BY_PACK/SP202.json", r202)
    records.append(r202)
    dump(
        REV / "APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS/SP202_v0.3.json",
        {
            "graph_id": "seen_pilot_run_002::SP202::v0.3",
            "user_confirmation_status": "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH",
            "program": r202["directed_program_graph"],
            **GATES,
            "shared_video_with_SP201": True,
        },
    )

    # SP203
    r203 = base_rec(
        "SP203",
        video_id="Hf-n1yfd8II",
        qa_uid="LVCOMP-V2-042",
        windows_seconds={"A": [3470, 3485], "B": [5413, 5440]},
        user_decision="DEFER_NEEDS_EVIDENCE_RELOCALIZATION",
        human_observations=[
            "A (57:50-58:05) did not find the described orange-clad coughing person.",
            "Coughing behavior not confirmed.",
            "Coach-player relation not confirmed.",
            "B match result cannot repair missing A person/relation evidence.",
        ],
        scientific_inferences=[],
        directed_program_graph={"status": "NOT_APPROVED", "forbidden_nodes": ["CoachOf"]},
        evidence_limitations=[
            "Do not invent coach-player relation from historical answer.",
        ],
        single_window_necessity_audit={
            "a_only_sufficient_full_question": "未建立",
            "b_only_sufficient_full_question": "不足以弥补 A 缺失",
            "a_plus_b_necessary": "未建立（证据不足）",
        },
        engineering_status="RELOCALIZATION_PACKS_PREPARED_NO_AUTO_APPROVAL",
        promotion_gate="NO_AUTO_UPGRADE",
        relocalization={
            "search_ranges_clock": ["57:20-57:50", "57:40-58:20", "58:05-58:40"],
            "media": [
                "seen_pilot_run_002/relocalization/SP203/search_5720_5750.mp4",
                "seen_pilot_run_002/relocalization/SP203/search_5740_5820.mp4",
                "seen_pilot_run_002/relocalization/SP203/search_5805_5840.mp4",
            ],
            "engineering_sparse_observation": "Primary search window stills show match play (Rio 2016 court); orange coughing coach NOT identified by engineering. Awaiting human re-watch.",
            "candidate_event_found": False,
            "auto_approved": False,
        },
    )
    dump(REV / "RECORDS_BY_PACK/SP203.json", r203)
    records.append(r203)

    # SP204
    r204 = base_rec(
        "SP204",
        video_id="9-gOCOu_KGU",
        qa_uid="LVCOMP-V2-101",
        windows_seconds={"A": [0, 85], "B": [2134, 2153]},
        user_decision="USER_REJECTED_AS_COMPOSITIONAL_CANDIDATE",
        rejection_reason="RELATION_UNVERIFIED + COMPOSITION_NECESSITY_NOT_ESTABLISHED",
        human_observations=[
            "A: men's 10k final stadium, overhead view and event captions.",
            "B: little girl appears; hug interaction with adult athlete.",
            "Adult athlete kit shows UK flag and Farah name.",
            "B shows track and green grass.",
            "Father-daughter relation not directly verified.",
            "Irreplaceable contribution of A not established.",
        ],
        scientific_inferences=[],
        directed_program_graph={"status": "NOT_APPROVED"},
        evidence_limitations=[
            "Diagnostic case only; must not claim B-only strictly completes the full original question.",
        ],
        single_window_necessity_audit={
            "a_only_sufficient_full_question": "未建立不可替代贡献",
            "b_only_sufficient_full_question": "未严格证明可独立完成完整原题",
            "a_plus_b_necessary": "未建立",
        },
        engineering_status="RECORDED_REJECTED",
        promotion_gate="REJECTED_NOT_OVERRIDABLE_BY_AUTOSCREEN",
    )
    dump(REV / "RECORDS_BY_PACK/SP204.json", r204)
    records.append(r204)

    # SP205
    r205 = base_rec(
        "SP205",
        video_id="wgBlACG927Y",
        qa_uid="LVCOMP-V2-116",
        windows_seconds={"A": [202, 370], "B": [838, 852]},
        user_decision="CONDITIONAL_USER_APPROVAL_PENDING_ENGINEERING_ACCEPTANCE",
        graph_version="v0.4",
        human_observations=[
            "03:22-05:22: vlogger boards high-speed train.",
            "05:22-06:10: vlogger disembarks high-speed train.",
            "06:10-13:58: human check observes no other transport.",
            "13:58-14:12: vlogger rides subway; Line 3 signage, handrails, seats.",
        ],
        scientific_inferences=[
            "B-only can recognize subway but cannot alone prove it is the next transport after the first means specified by the question.",
            "Must not mark 'possible answer-string guess' as proven B-only compositional shortcut.",
            "Absence of other transport in reviewed footage ≠ proof none existed in real journey off-camera.",
        ],
        directed_program_graph={
            "program": "IdentifyFirstTransport → DetectDisembark → TemporalSuccessor → IdentifyNextTransport",
            "answer_candidate": "Subway",
            "version": "v0.4",
        },
        evidence_limitations=[
            "Precision: unobserved other transport in footage is not absolute real-world absence.",
            "MODEL_ACCESSIBLE_TEMPORAL_GAP_06:10-13:58 under clip-only protocol.",
        ],
        single_window_necessity_audit={
            "a_only_sufficient_full_question": "否（缺下一交通工具）",
            "b_only_sufficient_full_question": "否（缺第一交通工具及后继关系）",
            "a_plus_b_necessary": "用户支持，但工程侧时间连续性证据对 clip-only 模型访问未闭环",
        },
        engineering_status="A_MEDIA_RESTORED_PROMOTION_BLOCKED_MODEL_ACCESS_GAP",
        promotion_gate="CONDITIONAL_PENDING",
        engineering_repair_ref="scientific_reviews/engineering_checks/SP205_A_media_repair.json",
        conditional_promotion=sp205_repair["conditional_promotion"],
    )
    dump(REV / "RECORDS_BY_PACK/SP205.json", r205)
    records.append(r205)

    # DN201
    r_dn = base_rec(
        "DN201",
        video_id="wgBlACG927Y",
        qa_uid="LVCOMP-V2-115",
        windows_seconds={"A": [202, 322], "B": [663, 700]},
        user_decision="DEFER_TARGET_EVENT_RELOCALIZATION",
        human_observations=[
            "B (11:03-11:40) does not show leaving the platform / going upstairs.",
            "Current A+B cannot answer the original question.",
            "Must not auto-label as verified B-only shortcut negative.",
        ],
        scientific_inferences=[],
        directed_program_graph={"status": "NOT_APPROVED"},
        evidence_limitations=["Target exit/upstairs event not located in current served windows."],
        single_window_necessity_audit={
            "b_only_shortcut_confirmed": False,
            "note": "Deferred; not a certified negative shortcut exemplar yet.",
        },
        engineering_status="RELOCALIZATION_PACKS_PREPARED_NO_AUTO_APPROVAL",
        promotion_gate="NO_AUTO_UPGRADE",
        relocalization={
            "search_ranges_clock": ["06:10-07:40", "07:40-09:10", "09:10-11:03"],
            "media": [
                "seen_pilot_run_002/relocalization/DN201/search_0610_0740.mp4",
                "seen_pilot_run_002/relocalization/DN201/search_0740_0910.mp4",
                "seen_pilot_run_002/relocalization/DN201/search_0910_1103.mp4",
            ],
            "engineering_sparse_observation": "Sparse stills in 06:10-11:03 primarily show onboard HSR cabin; leave-platform/upstairs action NOT identified by engineering. Awaiting human re-watch of search clips.",
            "candidate_event_found": False,
            "auto_approved": False,
        },
    )
    dump(REV / "RECORDS_BY_PACK/DN201.json", r_dn)
    records.append(r_dn)

    # Update SP205 pack + catalog
    cat = json.loads((PILOT / "CATALOG.json").read_text(encoding="utf-8"))
    decision_by = {r["pack_id"]: r["user_decision"] for r in records}
    for it in cat["items"]:
        pid = it["pack_id"]
        rec = next(r for r in records if r["pack_id"] == pid)
        it["scientific_review"] = {
            "ingested": True,
            "user_decision": rec["user_decision"],
            "record_path": f"scientific_reviews/RECORDS_BY_PACK/{pid}.json",
            "compositional_candidate_graph_approved": rec["user_decision"]
            == "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH",
            "graph_version": rec.get("graph_version"),
        }
        it["user_confirmation_status"] = "SCIENTIFIC_REVIEW_INGESTED"
        for k, v in GATES.items():
            it[k] = v
        if pid == "SP205":
            it["clips"]["A"] = "seen_pilot_run_002/media/SP205/A_wgBlACG927Y_202_370.mp4"
            it["media_status"] = "OK"
            it["intervals"]["A"] = {
                "start_s": 202.0,
                "end_s": 370.0,
                "basis": {
                    "source_time_reference": "03:22-06:10",
                    "truncated_for_review_cost": False,
                    "restored_utc": utc_now(),
                    "note": "Restored full official A window after scientific conditional approval requirements.",
                },
            }
            it["scientific_review"]["conditional_promotion"] = sp205_repair["conditional_promotion"]
    # diagnostic DN201
    for d in cat.get("diagnostic_negatives") or []:
        if d["pack_id"] == "DN201":
            d["user_decision"] = "DEFER_TARGET_EVENT_RELOCALIZATION"
            d["record_path"] = "scientific_reviews/RECORDS_BY_PACK/DN201.json"
    cat["scientific_adjudication_ingest"] = {
        "ingested_utc": utc_now(),
        "approved_compositional_candidates": ["SP201", "SP202"],
        "conditional_pending": ["SP205"],
        "rejected": ["SP204"],
        "deferred_relocalization": ["SP203", "DN201"],
        "auto_promoted_to_formal_seen": 0,
        **GATES,
    }
    cat["does_not_overwrite_run_001"] = True
    dump(PILOT / "CATALOG.json", cat)

    # Update SP205 review pack JSON
    pack205 = json.loads((PILOT / "review_packs/SP205_wgBlACG927Y.json").read_text(encoding="utf-8"))
    pack205["intervals"]["A"] = cat["items"][4]["intervals"]["A"]  # may be wrong index
    # find by pack_id
    for it in cat["items"]:
        if it["pack_id"] == "SP205":
            pack205["intervals"]["A"] = it["intervals"]["A"]
            break
    pack205["media"]["A"] = {
        "extract_status": "OK",
        "relpath": "seen_pilot_run_002/media/SP205/A_wgBlACG927Y_202_370.mp4",
        "sha256": sp205_repair["after"]["sha256"],
        "bytes": sp205_repair["after"]["bytes"],
        "t_start_s": 202.0,
        "t_end_s": 370.0,
        "duration_s": 168.0,
        "window_basis": pack205["intervals"]["A"]["basis"],
    }
    pack205["media"]["status"] = "OK"
    pack205["user_confirmation_status"] = "SCIENTIFIC_REVIEW_INGESTED"
    pack205["scientific_review_pointer"] = next(i["scientific_review"] for i in cat["items"] if i["pack_id"] == "SP205")
    for k, v in GATES.items():
        pack205[k] = v
    dump(PILOT / "review_packs/SP205_wgBlACG927Y.json", pack205)

    # Annotate other packs lightly
    for pid, path in [
        ("SP201", "review_packs/SP201_Hf-n1yfd8II.json"),
        ("SP202", "review_packs/SP202_Hf-n1yfd8II.json"),
        ("SP203", "review_packs/SP203_Hf-n1yfd8II.json"),
        ("SP204", "review_packs/SP204_9-gOCOu_KGU.json"),
        ("DN201", "diagnostic_negatives/DN201_wgBlACG927Y.json"),
    ]:
        pp = PILOT / path
        pack = json.loads(pp.read_text(encoding="utf-8"))
        rec = next(r for r in records if r["pack_id"] == pid)
        pack["scientific_review_pointer"] = {
            "user_decision": rec["user_decision"],
            "record_path": f"scientific_reviews/RECORDS_BY_PACK/{pid}.json",
        }
        pack["user_confirmation_status"] = "SCIENTIFIC_REVIEW_INGESTED"
        for k, v in GATES.items():
            pack[k] = v
        dump(pp, pack)

    # Manifest refresh
    files = []
    for p in sorted((PILOT / "media").rglob("*.mp4")):
        rel = str(p.relative_to(WB))
        files.append({"role": rel, "relpath": rel, "sha256": sha256_file(p), "bytes": p.stat().st_size})
    for p in sorted((PILOT / "relocalization").rglob("*.mp4")):
        rel = str(p.relative_to(WB))
        files.append({"role": rel, "relpath": rel, "sha256": sha256_file(p), "bytes": p.stat().st_size})
    man = {
        "run_id": "seen_pilot_run_002",
        "updated_utc": utc_now(),
        "files": files,
        "pack_json_sha256": {
            p.name: sha256_file(p)
            for p in list((PILOT / "review_packs").glob("*.json"))
            + list((PILOT / "diagnostic_negatives").glob("*.json"))
        },
        "sp205_repair": sp205_repair["after"],
        "sp205_truncated_retained_for_diff": sp205_repair["before"],
    }
    dump(PILOT / "MANIFEST.json", man)

    # Relocalization index
    dump(
        PILOT / "relocalization/INDEX.json",
        {
            "SP203": r203["relocalization"],
            "DN201": r_dn["relocalization"],
            "human_review_entry": "Workbench Seen Pilot run_002 + relocalization/*.mp4",
            "auto_approved": False,
        },
    )

    index = {
        "run_id": "seen_pilot_run_002",
        "ingested_utc": utc_now(),
        "baseline_engineering_commit": "fa98aae25f7a5c73259e4dd33c4cb70a46cd0592",
        "headline": "2 USER_APPROVED compositional candidates (SP201/SP202); 1 CONDITIONAL pending eng (SP205); 1 REJECTED (SP204); 2 DEFER relocalization (SP203/DN201); 0 formal Seen/Gold; Track A RSI gated.",
        "decisions": decision_by,
        "approved_compositional_candidates": ["SP201", "SP202"],
        "sp205_promoted": False,
        "sp205_blocker": "MODEL_ACCESSIBLE_TEMPORAL_GAP_06:10-13:58",
        "records": [f"scientific_reviews/RECORDS_BY_PACK/{r['pack_id']}.json" for r in records],
        **GATES,
        "run_001_untouched": True,
    }
    dump(REV / "INDEX.json", index)
    print(json.dumps({"ok": True, "sp205_promoted": False, "approved": ["SP201", "SP202"]}, indent=2))


if __name__ == "__main__":
    main()
