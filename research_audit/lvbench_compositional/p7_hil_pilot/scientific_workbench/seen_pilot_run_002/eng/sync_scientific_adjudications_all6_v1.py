#!/usr/bin/env python3
"""Sync run_002 six-pack scientific adjudications from user handoff (all6 v1).

Non-destructive: archives prior RECORDS before writing current pointers.
Does NOT mint formal Seen/Unseen/Gold, freeze pool, expose train, or unlock Track A RSI.
USER_ASSIGNED_UNSEEN ≠ formal_unseen freeze.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

PILOT = Path(__file__).resolve().parents[1]
WB = PILOT.parent
REV = PILOT / "scientific_reviews"
HANDOFF = REV / "handoff" / "run_002_scientific_adjudications_all6_v1.json"
HIST = REV / "HISTORY"
GATES = {
    "formal_seen_train": False,
    "formal_unseen": False,
    "formal_gold": False,
    "train_exposed": False,
    "seen_pool_frozen": False,
    "approve_expensive_track_a_rsi": False,
}
BASELINE = "9afc5e95156041833421ff3e034d76deb8aac7c3"


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


def archive_current_records(stamp: str) -> None:
    HIST.mkdir(parents=True, exist_ok=True)
    for p in (REV / "RECORDS_BY_PACK").glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        ver = d.get("graph_version") or "no_graph"
        dest = HIST / f"{p.stem}_{ver}_pre_all6_{stamp}.json"
        if not dest.exists():
            shutil.copy2(p, dest)
        if p.stem == "SP205" and d.get("graph_version") == "v0.4":
            alias = HIST / "SP205_v0.4_conditional.json"
            if not alias.exists():
                shutil.copy2(p, alias)


def record_from_handoff(src: dict, ingested_utc: str) -> dict:
    """Map handoff record → workbench scientific record (current pointer)."""
    pack_id = src["pack_id"]
    out = {
        "schema": "seen_pilot_run_002_scientific_record_v1",
        "run_id": "seen_pilot_run_002",
        "pack_id": pack_id,
        "video_id": src["video_id"],
        "qa_uid": src["qa_uid"],
        "windows_seconds": src["evidence_windows_seconds"],
        "user_decision": src["user_decision"],
        "graph_version": src.get("graph_version"),
        "user_split_assignment": src.get("user_split_assignment", "UNASSIGNED"),
        "user_split_decision": src.get("user_split_decision", "NOT_YET_ASSIGNED"),
        **{k: bool(src.get(k, False)) if k in GATES else GATES[k] for k in GATES},
        # Force gates false regardless of handoff typos
        **GATES,
        "engineering_must_not_auto_approve": True,
        "ingested_utc": ingested_utc,
        "handoff_schema": "cvpr2027_trackb_run002_scientific_adjudications_complete_v1",
        "baseline_commit": BASELINE,
        "branch_note": "Artifacts on research/lvbench-comp-p7-hil-pilot; USER_ASSIGNED_UNSEEN ≠ formal Unseen freeze.",
        "question_original_en": src.get("question_original_en"),
        "answer_candidate": src.get("answer_candidate"),
        "human_observations": src.get("human_observations") or [],
        "scientific_inferences": src.get("scientific_inferences") or [],
        "directed_program_graph": src.get("directed_program_graph") or {},
        "evidence_limitations": src.get("evidence_limitations") or [],
        "single_window_necessity_audit": src.get("single_window_necessity_audit") or {},
        "engineering_status": src.get("engineering_status"),
        "promotion_gate": src.get("promotion_gate"),
        "video_group_id": src.get("video_group_id"),
        "shared_video_with": src.get("shared_video_with") or [],
        "source_record_url": src.get("source_record_url"),
    }
    for optional in (
        "shared_B_window_with",
        "original_source_graph_version",
        "rejection_reason",
        "relocalization",
        "question_zh",
        "question_en",
        "answer_zh",
        "previous_graph_version",
        "evidence",
        "engineering_repair_ref",
        "prior_v04_history",
        "media_sha256",
        "user_approved_split_not_equivalent_to_formal_freeze",
        "split_group_isolation_note",
    ):
        if optional in src:
            out[optional] = src[optional]
    # Normalize rejection_reason to keep membership tests stable
    if "rejection_reason" in out and isinstance(out["rejection_reason"], list):
        out["rejection_reason_codes"] = list(out["rejection_reason"])
        out["rejection_reason"] = " + ".join(out["rejection_reason"])
    # SP205 v0.5: do not re-apply v0.4 successor gap as current blocker
    if pack_id == "SP205":
        out["v04_history_ref"] = "scientific_reviews/HISTORY/SP205_v0.4_conditional.json"
        out["v04_engineering_repair_ref"] = "scientific_reviews/engineering_checks/SP205_A_media_repair.json"
        out["sp205_v05_notes"] = {
            "TemporalSuccessor_removed": True,
            "CompareTemporalOrder_required": True,
            "middle_interval_required_for_v05": False,
            "old_blocker_MODEL_ACCESSIBLE_TEMPORAL_GAP_superseded": True,
            "user_split": "USER_ASSIGNED_UNSEEN",
            "formal_unseen_still_false": True,
        }
    return out


def write_approved_graph(rec: dict) -> None:
    pid = rec["pack_id"]
    ver = rec.get("graph_version")
    if rec["user_decision"] != "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH" or not ver:
        return
    path = REV / "APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS" / f"{pid}_{ver}.json"
    payload = {
        "graph_id": f"seen_pilot_run_002::{pid}::{ver}",
        "user_confirmation_status": "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH",
        "program": rec["directed_program_graph"],
        "graph_version": ver,
        "user_split_assignment": rec.get("user_split_assignment"),
        "user_split_decision": rec.get("user_split_decision"),
        **GATES,
        "note": "Compositional candidate only; USER_ASSIGNED_UNSEEN ≠ formal Unseen freeze; not formal Seen/Gold.",
    }
    if pid == "SP205":
        payload["operator_semantics"] = rec["directed_program_graph"].get("operator_semantics")
        payload["removed_required_operator"] = "TemporalSuccessor"
        payload["new_required_operator"] = "CompareTemporalOrder"
        payload["video_group_isolation"] = {
            "video_id": rec["video_id"],
            "forbid_derived_samples_in_seen_train": True,
            "shared_with": rec.get("shared_video_with") or [],
        }
    dump(path, payload)


def update_catalog(records: list[dict], ingested_utc: str, summary: dict) -> None:
    cat = json.loads((PILOT / "CATALOG.json").read_text(encoding="utf-8"))
    by = {r["pack_id"]: r for r in records}
    for it in cat["items"]:
        pid = it["pack_id"]
        rec = by[pid]
        it["scientific_review"] = {
            "ingested": True,
            "user_decision": rec["user_decision"],
            "record_path": f"scientific_reviews/RECORDS_BY_PACK/{pid}.json",
            "compositional_candidate_graph_approved": rec["user_decision"]
            == "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH",
            "graph_version": rec.get("graph_version"),
            "user_split_assignment": rec.get("user_split_assignment"),
            "user_split_decision": rec.get("user_split_decision"),
        }
        it["user_confirmation_status"] = "SCIENTIFIC_REVIEW_INGESTED"
        for k, v in GATES.items():
            it[k] = v
        if pid == "SP205":
            it["clips"]["A"] = "seen_pilot_run_002/media/SP205/A_wgBlACG927Y_202_370.mp4"
            it["media_status"] = "OK"
            it["intervals"]["A"]["start_s"] = 202.0
            it["intervals"]["A"]["end_s"] = 370.0
            it["intervals"]["A"]["basis"] = {
                "source_time_reference": "03:22-06:10",
                "truncated_for_review_cost": False,
                "restored_full_A": True,
                "note": "Restored A retained for SP205 v0.5; TemporalSuccessor gap not a v0.5 blocker.",
            }
            it["scientific_review"]["user_assigned_unseen"] = True
            it["scientific_review"].pop("conditional_promotion", None)
            # Update QA clue text to v0.5 after-semantics (still unverified historical clue status for answer)
            if "qa_clue_unverified" in it:
                it["qa_clue_unverified"]["question_en_v05"] = rec.get("question_en")
                it["qa_clue_unverified"]["question_zh_v05"] = rec.get("question_zh")
                it["qa_clue_unverified"]["operator_semantics"] = "TEMPORAL_ORDER_NOT_IMMEDIATE_SUCCESSOR"
    for d in cat.get("diagnostic_negatives") or []:
        if d["pack_id"] == "DN201":
            rec = by["DN201"]
            d["user_decision"] = rec["user_decision"]
            d["record_path"] = "scientific_reviews/RECORDS_BY_PACK/DN201.json"
            d["split_group_isolation_note"] = rec.get("split_group_isolation_note")
            d["shared_video_with"] = rec.get("shared_video_with")
            for k, v in GATES.items():
                d[k] = v
    cat["scientific_adjudication_ingest"] = {
        "ingested_utc": ingested_utc,
        "handoff": "scientific_reviews/handoff/run_002_scientific_adjudications_all6_v1.json",
        "approved_compositional_candidates": summary["scientifically_approved_compositional_candidates"],
        "user_assigned_unseen": summary["user_assigned_unseen"],
        "approved_but_split_unassigned": summary["approved_but_split_unassigned"],
        "rejected": summary["rejected"],
        "deferred_relocalization": summary["deferred"],
        "auto_promoted_to_formal_seen": 0,
        "auto_promoted_to_formal_unseen": 0,
        "video_group_isolation": {
            "wgBlACG927Y": {
                "reason": "SP205 USER_ASSIGNED_UNSEEN",
                "forbid_derived_in_seen_train": ["SP205", "DN201"],
            }
        },
        **GATES,
    }
    cat["does_not_overwrite_run_001"] = True
    dump(PILOT / "CATALOG.json", cat)


def update_review_packs(records: list[dict]) -> None:
    by = {r["pack_id"]: r for r in records}
    mapping = [
        ("SP201", "review_packs/SP201_Hf-n1yfd8II.json"),
        ("SP202", "review_packs/SP202_Hf-n1yfd8II.json"),
        ("SP203", "review_packs/SP203_Hf-n1yfd8II.json"),
        ("SP204", "review_packs/SP204_9-gOCOu_KGU.json"),
        ("SP205", "review_packs/SP205_wgBlACG927Y.json"),
        ("DN201", "diagnostic_negatives/DN201_wgBlACG927Y.json"),
    ]
    for pid, rel in mapping:
        pp = PILOT / rel
        pack = json.loads(pp.read_text(encoding="utf-8"))
        rec = by[pid]
        pack["scientific_review_pointer"] = {
            "user_decision": rec["user_decision"],
            "graph_version": rec.get("graph_version"),
            "user_split_assignment": rec.get("user_split_assignment"),
            "user_split_decision": rec.get("user_split_decision"),
            "record_path": f"scientific_reviews/RECORDS_BY_PACK/{pid}.json",
            "handoff": "scientific_reviews/handoff/run_002_scientific_adjudications_all6_v1.json",
        }
        pack["user_confirmation_status"] = "SCIENTIFIC_REVIEW_INGESTED"
        for k, v in GATES.items():
            pack[k] = v
        if pid == "SP205":
            pack["graph_version"] = "v0.5"
            pack["user_split_assignment"] = "UNSEEN"
            pack["user_split_decision"] = "USER_ASSIGNED_UNSEEN"
            pack["directed_program_graph"] = rec["directed_program_graph"]
            pack["question_en_v05"] = rec.get("question_en")
            pack["question_zh_v05"] = rec.get("question_zh")
            pack["media"]["A"]["relpath"] = "seen_pilot_run_002/media/SP205/A_wgBlACG927Y_202_370.mp4"
            pack["media"]["A"]["sha256"] = (rec.get("media_sha256") or {}).get(
                "A", pack["media"]["A"].get("sha256")
            )
            pack["media"]["A"]["t_start_s"] = 202.0
            pack["media"]["A"]["t_end_s"] = 370.0
            pack["intervals"]["A"]["start_s"] = 202.0
            pack["intervals"]["A"]["end_s"] = 370.0
            pack["v04_history_ref"] = "scientific_reviews/HISTORY/SP205_v0.4_conditional.json"
            pack["scientific_review_pointer"]["compositional_candidate_graph_approved"] = True
            pack["scientific_review_pointer"]["formal_unseen"] = False
            pack["video_group_isolation"] = {
                "video_id": "wgBlACG927Y",
                "forbid_derived_samples_in_seen_train": True,
            }
        if pid == "DN201":
            pack["split_group_isolation_note"] = rec.get("split_group_isolation_note")
            pack["shared_video_with"] = rec.get("shared_video_with")
        dump(pp, pack)


def refresh_manifest() -> None:
    files = []
    for root in (PILOT / "media", PILOT / "relocalization"):
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.mp4")):
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
        "sp205_A_restored": {
            "relpath": "seen_pilot_run_002/media/SP205/A_wgBlACG927Y_202_370.mp4",
            "sha256": sha256_file(PILOT / "media/SP205/A_wgBlACG927Y_202_370.mp4"),
            "coverage_clock": "03:22-06:10",
        },
        "note": "SP205 v0.5 approved; v0.4 repair audit retained under engineering_checks/HISTORY.",
    }
    dump(PILOT / "MANIFEST.json", man)


def update_isolation(summary: dict) -> None:
    iso_path = PILOT / "ISOLATION_CHECK.json"
    iso = json.loads(iso_path.read_text(encoding="utf-8"))
    iso["updated_utc"] = utc_now()
    iso["user_assigned_unseen_video_groups"] = {
        "wgBlACG927Y": {
            "packs": ["SP205", "DN201"],
            "forbid_in_seen_train": True,
            "reason": "SP205 USER_ASSIGNED_UNSEEN holds out entire source video group",
            "formal_unseen": False,
        }
    }
    iso["all6_sync"] = {
        "approved": summary["scientifically_approved_compositional_candidates"],
        "user_assigned_unseen": summary["user_assigned_unseen"],
        **GATES,
    }
    dump(iso_path, iso)


def main() -> None:
    assert HANDOFF.exists(), f"missing handoff: {HANDOFF}"
    handoff = json.loads(HANDOFF.read_text(encoding="utf-8"))
    assert handoff["target_run"] == "seen_pilot_run_002"
    assert len(handoff["records"]) == 6
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_current_records(stamp)
    ingested_utc = utc_now()
    records = []
    for src in handoff["records"]:
        # Preserve gate falsity from handoff validation
        for g in GATES:
            assert src.get(g) is False, f"{src['pack_id']} gate {g} must be false"
        rec = record_from_handoff(src, ingested_utc)
        dump(REV / "RECORDS_BY_PACK" / f"{rec['pack_id']}.json", rec)
        write_approved_graph(rec)
        records.append(rec)

    # Verify SP205 media SHA still matches restored file
    a_path = PILOT / "media/SP205/A_wgBlACG927Y_202_370.mp4"
    b_path = PILOT / "media/SP205/B_wgBlACG927Y_838_852.mp4"
    r205 = next(r for r in records if r["pack_id"] == "SP205")
    assert r205["graph_version"] == "v0.5"
    assert r205["user_decision"] == "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH"
    assert r205["user_split_decision"] == "USER_ASSIGNED_UNSEEN"
    assert r205["formal_unseen"] is False
    assert "CompareTemporalOrder" in json.dumps(r205["directed_program_graph"])
    assert "TemporalSuccessor" == r205["directed_program_graph"].get("removed_required_operator")
    assert sha256_file(a_path) == r205["media_sha256"]["A"]
    assert sha256_file(b_path) == r205["media_sha256"]["B"]
    # Keep v0.4 repair audit file (do not delete / overwrite into approval)
    repair_path = REV / "engineering_checks/SP205_A_media_repair.json"
    assert repair_path.exists()
    repair = json.loads(repair_path.read_text(encoding="utf-8"))
    repair["historical_status"] = "V04_AUDIT_RETAINED"
    repair["applicability_to_v05"] = "SUPERSEDED_NOT_REQUIRED_FOR_COMPARE_TEMPORAL_ORDER"
    repair["current_scientific_pointer"] = "scientific_reviews/RECORDS_BY_PACK/SP205.json"
    repair["current_graph_version"] = "v0.5"
    dump(repair_path, repair)

    summary = handoff["summary"]
    update_catalog(records, ingested_utc, summary)
    update_review_packs(records)
    refresh_manifest()
    update_isolation(summary)

    decisions = {r["pack_id"]: r["user_decision"] for r in records}
    index = {
        "run_id": "seen_pilot_run_002",
        "ingested_utc": ingested_utc,
        "baseline_engineering_commit": BASELINE,
        "handoff": "scientific_reviews/handoff/run_002_scientific_adjudications_all6_v1.json",
        "headline": (
            "3 USER_APPROVED compositional candidates (SP201/SP202/SP205 v0.5); "
            "SP205 USER_ASSIGNED_UNSEEN (formal_unseen=false); "
            "1 REJECTED (SP204); 2 DEFER (SP203/DN201); "
            "0 formal Seen/Gold; Track A RSI gated; wgBlACG927Y held out of Seen train."
        ),
        "decisions": decisions,
        "approved_compositional_candidates": summary["scientifically_approved_compositional_candidates"],
        "user_assigned_unseen": summary["user_assigned_unseen"],
        "approved_but_split_unassigned": summary["approved_but_split_unassigned"],
        "deferred": summary["deferred"],
        "rejected": summary["rejected"],
        "sp205_graph_version": "v0.5",
        "sp205_promoted_scientific": True,
        "sp205_formal_unseen": False,
        "sp205_v04_blocker_superseded": True,
        "video_group_isolation": {
            "wgBlACG927Y": ["SP205", "DN201"],
            "forbid_derived_in_seen_train": True,
        },
        "records": [f"scientific_reviews/RECORDS_BY_PACK/{r['pack_id']}.json" for r in records],
        "history_dir": "scientific_reviews/HISTORY/",
        **GATES,
        "run_001_untouched": True,
    }
    dump(REV / "INDEX.json", index)

    report = {
        "title": "run_002 all6 scientific adjudication sync",
        "ingested_utc": ingested_utc,
        "baseline": BASELINE,
        "handoff_sha256": sha256_file(HANDOFF),
        "decisions": decisions,
        "approved": summary["scientifically_approved_compositional_candidates"],
        "user_assigned_unseen": summary["user_assigned_unseen"],
        "remaining_evidence_issues": [
            "SP205 first_transport_scope_provenance still PENDING_EXPLICIT_EARLIER_TIMELINE_EVIDENCE_POINTER",
            "SP205 model_time_order_accessibility PENDING_INPUT_PROTOCOL_CHECK",
            "SP203 / DN201 still DEFER pending human re-review of relocalization packs",
            "USER_ASSIGNED_UNSEEN does not freeze formal Unseen test set",
        ],
        **GATES,
    }
    dump(REV / "ALL6_SYNC_REPORT.json", report)
    print(json.dumps({"ok": True, **{k: report[k] for k in ("decisions", "approved", "user_assigned_unseen")}}, indent=2))


if __name__ == "__main__":
    main()
