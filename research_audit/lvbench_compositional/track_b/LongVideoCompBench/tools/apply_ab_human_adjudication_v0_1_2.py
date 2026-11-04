#!/usr/bin/env python3
"""WP2.2: ingest Human Scientific Owner A/B adjudications → LongVideoCompBench v0.1.2.

Preserves v0.1.0 / v0.1.1. Does not mint formal Gold. Does not auto-complete
QA windows_seconds from ROI alone. Does not mutate frozen 5+2 or PROPOSED 7+4.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DS_ROOT,
    FROZEN_5_2,
    PROPOSED_7_4_SEEN,
    PROPOSED_7_4_UNSEEN,
    evidence_id,
    qa_id,
    read_jsonl,
    review_id,
    sha256_file,
    utc_now,
    write_json,
    write_jsonl,
)
from validate_dataset import run_gates  # noqa: E402

ALGO = "longvideocompbenc_ab_human_adj_v0_1_2"
BASELINE = "1bb34ce53482eee78d1bba62cfee4bba2073b65b"

# Human Scientific Owner confirmations (this chat)
ADJUDICATIONS = {
    "A": {
        "video_id": "hROKtPqktO8",
        "rois": {
            "A": {"start": 500, "end": 510, "label": "early_roi_street_selfie_context"},
            "B": {"start": 1255, "end": 1265, "label": "late_roi_hillside_selfie"},
        },
        "relation": {
            "operator": "CrossIntervalSamePersonBind",
            "human_claim": "Women in the two ROIs are the same person.",
            "status": "HUMAN_APPROVED",
        },
        "qa_draft": {
            "question": "后来在山坡自拍的那名女性，之前出现在哪里？",
            "answer_semantic": "城市台阶附近",
            "status": "CHAT_RECONSTRUCTED_QA_DRAFT",
            "note": (
                "Reconstructed in chat from program semantics; not verbatim original QA. "
                "城市台阶 / answer still require video-observation reconciliation."
            ),
        },
        "split_assignment": "SEEN_PROPOSED",
    },
    "B": {
        "video_id": "iA_69g87Ilw",
        "rois": {
            "A": {"start": 358, "end": 368, "label": "early_roi_fruit_platter"},
            "B": {"start": 900, "end": 910, "label": "late_roi_speaking_door_context"},
        },
        "relation": {
            "operator": "CrossViewSameRoomBind",
            "human_claim": "The two ROIs belong to the same room.",
            "status": "HUMAN_APPROVED",
        },
        "qa_draft": {
            "question": "后来出现的告别房间，在更早的画面中有什么物品？",
            "answer_semantic": "水果拼盘",
            "status": "CHAT_RECONSTRUCTED_QA_DRAFT",
            "note": (
                "Reconstructed in chat from program semantics; not verbatim original QA. "
                "告别房间 / fruit-platter wording still require video-observation reconciliation."
            ),
        },
        "split_assignment": "UNSEEN_PROPOSED",
    },
}


def ensure_answer_status_schema() -> None:
    path = DS_ROOT / "schemas" / "qa_item.schema.json"
    sch = json.loads(path.read_text())
    enum = sch["properties"]["answer_status"]["enum"]
    if "CHAT_RECONSTRUCTED_QA_DRAFT" not in enum:
        enum.append("CHAT_RECONSTRUCTED_QA_DRAFT")
        path.write_text(json.dumps(sch, indent=2) + "\n")


def upsert_videos(videos: list[dict]) -> list[dict]:
    by = {v["video_id"]: v for v in videos}
    for sid, adj in ADJUDICATIONS.items():
        vid = adj["video_id"]
        if vid not in by:
            by[vid] = {
                "video_id": vid,
                "source_dataset": "LVBench",
                "source_video_id": vid,
                "source_uri": f"/home/descfly/lpy/dataset/LVBench/videos/{vid}.mp4",
                "duration_seconds": None,
                "media_sha256": "UNKNOWN",
                "engineering_sha256": None,
                "access_status": "PATH_CANDIDATE_LOCAL_LVBENCH",
                "license_status": "UNKNOWN_NOT_DECLARED_OPEN",
                "pool": "DEV",
                "provenance": {
                    "bound_via": "WP2.2_HUMAN_SCIENTIFIC_OWNER_ADJUDICATION",
                    "items": [sid],
                    "baseline_commit": BASELINE,
                },
            }
        else:
            by[vid].setdefault("provenance", {}).setdefault("items", [])
            if sid not in by[vid]["provenance"]["items"]:
                by[vid]["provenance"]["items"].append(sid)
            by[vid]["provenance"]["bound_via"] = "WP2.2_HUMAN_SCIENTIFIC_OWNER_ADJUDICATION"
    return sorted(by.values(), key=lambda x: x["video_id"])


def build_roi_evidence(sid: str, adj: dict) -> list[dict]:
    rows = []
    for role, roi in adj["rois"].items():
        rows.append(
            {
                "evidence_id": evidence_id(sid, f"ROI_{role}"),
                "video_id": adj["video_id"],
                "window_start": roi["start"],
                "window_end": roi["end"],
                "modality": "video_window_roi",
                "source_frame_refs": None,
                "source_hashes": {"status": "UNKNOWN"},
                "claim": (
                    f"Human-confirmed related ROI ({roi['label']}) for item {sid}; "
                    "not automatically a complete formal QA windows_seconds covering all "
                    "evidence needed to answer the question."
                ),
                "certification_status": "SOURCE_WINDOW_ONLY",
                "reviewer_provenance": {
                    "reviewer_role": "HUMAN_SCIENTIFIC_OWNER",
                    "source_type": "DIRECT_USER_CONFIRMATION_IN_CHAT",
                    "review_status": "HUMAN_APPROVED",
                    "scope": "RELATED_ROI_FRAGMENT",
                    "roi_label": roi["label"],
                    "formal_qa_windows_complete": False,
                    "algo_version": ALGO,
                    "baseline_commit": BASELINE,
                },
            }
        )
    # Retain historical UNKNOWN evidence row as archived pointer (new id)
    rows.append(
        {
            "evidence_id": evidence_id(sid, "UNKNOWN_ARCHIVED_PRE_WP2_2"),
            "video_id": adj["video_id"],
            "window_start": None,
            "window_end": None,
            "modality": "UNKNOWN",
            "source_frame_refs": None,
            "source_hashes": {"status": "UNKNOWN"},
            "claim": "Pre-WP2.2 placeholder evidence retained for audit continuity.",
            "certification_status": "UNKNOWN",
            "reviewer_provenance": {
                "archived_from": evidence_id(sid, "UNKNOWN"),
                "note": "Superseded for active use by ROI_* rows; kept for history.",
            },
        }
    )
    return rows


def build_human_adj_record(sid: str, adj: dict, prior_audit_snippet: dict | None) -> dict:
    return {
        "adjudication_id": f"lvcb:hadj:{sid}:wp2_2_video_bind_cross_window",
        "qa_id": qa_id(sid),
        "source_item_id": sid,
        "reviewer_role": "HUMAN_SCIENTIFIC_OWNER",
        "source_type": "DIRECT_USER_CONFIRMATION_IN_CHAT",
        "review_status": "HUMAN_APPROVED",
        "scope": "VIDEO_BINDING_AND_CROSS_WINDOW_RELATION",
        "video_id": adj["video_id"],
        "rois": adj["rois"],
        "cross_window_relation": adj["relation"],
        "prior_unauthenticated_state": {
            "from_ab_source_recovery_v0_1_1": prior_audit_snippet,
            "note": (
                "Prior audit kept candidates unbound / NOT_CERTIFIED; this record "
                "promotes video binding + relation only."
            ),
        },
        "state_transition": {
            "video_id": {"from": None, "to": adj["video_id"], "status": "HUMAN_BOUND"},
            "cross_window_relation": {
                "from": "CANDIDATE_OR_GRAPH_STRUCTURE_ONLY",
                "to": "HUMAN_APPROVED",
                "operator": adj["relation"]["operator"],
            },
            "formal_qa_windows_seconds": {
                "from": "UNKNOWN",
                "to": "ROI_RELATED_NOT_FULL_QA_WINDOWS",
                "status": "NOT_AUTO_COMPLETED_FROM_ROI",
            },
            "formal_gold": {"from": False, "to": False},
        },
        "qa_draft_attached": adj["qa_draft"],
        "recorded_utc": utc_now(),
        "algo_version": ALGO,
        "baseline_commit": BASELINE,
        "formal_gold": False,
    }


def patch_qa(q: dict, adj: dict, evidence_ids: list[str]) -> dict:
    q = dict(q)
    draft = adj["qa_draft"]
    q["video_id"] = adj["video_id"]
    q["question"] = draft["question"]
    q["answer"] = draft["answer_semantic"]
    q["answer_status"] = "CHAT_RECONSTRUCTED_QA_DRAFT"
    q["evidence_ids"] = evidence_ids
    q["review_status"] = "HUMAN_VIDEO_BIND_APPROVED_QA_DRAFT_PENDING"
    q["record_completeness"] = "PARTIAL"
    q["formal_gold"] = False
    q["composition_attributes"] = dict(q.get("composition_attributes") or {})
    q["composition_attributes"]["status_bundle"] = {
        "program_graph_status": "CHAT_APPROVED_SIDECAR_NOT_FRAME_CERTIFIED",
        "human_relation_adjudication_status": "HUMAN_APPROVED",
        "human_relation_operator": adj["relation"]["operator"],
        "qa_completeness_status": "PARTIAL_CHAT_RECONSTRUCTED_DRAFT",
        "formal_qa_windows_status": "ROI_RELATED_NOT_FULL_QA_WINDOWS",
        "formal_gold_status": False,
    }
    q["composition_attributes"]["related_rois"] = adj["rois"]
    q["composition_attributes"]["formal_windows_seconds"] = {
        "status": "NOT_AUTHORIZED_AS_COMPLETE_QA_WINDOWS",
        "roi_fragments_recorded": True,
        "note": (
            "ROI ranges are human-confirmed related fragments; do not treat as "
            "complete windows_seconds covering all answer evidence."
        ),
    }
    q["provenance"] = dict(q.get("provenance") or {})
    q["provenance"]["wp2_2_human_adjudication"] = {
        "adjudication_id": f"lvcb:hadj:{q['source_item_id']}:wp2_2_video_bind_cross_window",
        "path": "annotations/ab_human_adjudications_wp2_2.jsonl",
        "qa_draft_status": "CHAT_RECONSTRUCTED_QA_DRAFT",
        "prior_recovery_audit_preserved": "reports/AB_SOURCE_RECOVERY_AUDIT.json",
    }
    return q


def patch_review(reviews: list[dict], sid: str, adj: dict) -> list[dict]:
    out = []
    target = review_id(sid, "necessity")
    found = False
    for r in reviews:
        if r.get("review_id") == target:
            found = True
            r = dict(r)
            r["cross_window_bind"] = {
                "status": "HUMAN_APPROVED",
                "operator": adj["relation"]["operator"],
                "human_claim": adj["relation"]["human_claim"],
                "scope": "VIDEO_BINDING_AND_CROSS_WINDOW_RELATION",
                "source_type": "DIRECT_USER_CONFIRMATION_IN_CHAT",
            }
            r["human_adjudication"] = {
                "adjudication_id": f"lvcb:hadj:{sid}:wp2_2_video_bind_cross_window",
                "review_status": "HUMAN_APPROVED",
            }
            r["answer_certification"] = "CHAT_RECONSTRUCTED_QA_DRAFT"
            r["decision_basis"] = "HUMAN_SCIENTIFIC_OWNER_DIRECT_CONFIRMATION_WP2_2"
            r["decision_version"] = "0.1.2-dev"
            r["necessity_test_passed"] = "NOT_AUTO_INFERRED_FROM_GRAPH"
            out.append(r)
        else:
            out.append(r)
    if not found:
        out.append(
            {
                "review_id": target,
                "qa_id": qa_id(sid),
                "review_kind": "necessity_and_adjudication",
                "a_only": None,
                "b_only": None,
                "a_plus_b": None,
                "single_window_shortcut": None,
                "answer_certification": "CHAT_RECONSTRUCTED_QA_DRAFT",
                "cross_window_bind": {
                    "status": "HUMAN_APPROVED",
                    "operator": adj["relation"]["operator"],
                },
                "human_adjudication": {
                    "adjudication_id": f"lvcb:hadj:{sid}:wp2_2_video_bind_cross_window"
                },
                "decision_basis": "HUMAN_SCIENTIFIC_OWNER_DIRECT_CONFIRMATION_WP2_2",
                "decision_version": "0.1.2-dev",
                "necessity_test_passed": "NOT_AUTO_INFERRED_FROM_GRAPH",
                "provenance": {"algo": ALGO},
            }
        )
    return out


def append_adjudication_log(sid: str, adj: dict) -> dict:
    return {
        "log_id": review_id(sid, "adjudication_log_wp2_2"),
        "qa_id": qa_id(sid),
        "source_item_id": sid,
        "event": "HUMAN_VIDEO_BIND_AND_CROSS_WINDOW_APPROVED",
        "utc": utc_now(),
        "notes": (
            f"video_id={adj['video_id']}; relation={adj['relation']['operator']} "
            "HUMAN_APPROVED; QA draft attached as CHAT_RECONSTRUCTED_QA_DRAFT; "
            "formal Gold unchanged false; ROI≠full QA windows."
        ),
        "formal_gold": False,
        "supersedes_nothing": True,
        "preserves_prior_audit": "reports/AB_SOURCE_RECOVERY_AUDIT.json",
    }


def upsert_adj_log(adj_log: list[dict], row: dict) -> list[dict]:
    out = [r for r in adj_log if r.get("log_id") != row["log_id"]]
    out.append(row)
    return out


def build_release_v012() -> dict:
    ver = "v0.1.2"
    out = DS_ROOT / "releases" / ver
    if (out / "manifest.json").is_file():
        return json.loads((out / "manifest.json").read_text())
    files = [
        "data/videos.jsonl",
        "data/qa_items.jsonl",
        "data/program_graphs.jsonl",
        "data/evidence.jsonl",
        "data/splits.json",
        "annotations/human_reviews.jsonl",
        "annotations/necessity_tests.jsonl",
        "annotations/adjudication_log.jsonl",
        "annotations/ab_human_adjudications_wp2_2.jsonl",
        "reports/bootstrap_report.json",
        "reports/coverage_report.json",
        "reports/split_integrity_report.json",
        "reports/validation_report.json",
        "reports/AB_SOURCE_RECOVERY_AUDIT.json",
        "reports/WP2_2_AB_HUMAN_ADJUDICATION_REPORT.json",
        "reports/HUMAN_SUPPLEMENT_CHECKLIST.md",
        "VERSION",
        "CHANGELOG.md",
        "schemas/qa_item.schema.json",
    ]
    out.mkdir(parents=True, exist_ok=True)
    checksums, copied = [], []
    for rel in files:
        src = DS_ROOT / rel
        if not src.is_file():
            continue
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        digest = sha256_file(dest)
        checksums.append(f"{digest}  {rel}")
        copied.append({"path": rel, "sha256": digest, "bytes": dest.stat().st_size})
    (out / "checksums.sha256").write_text("\n".join(checksums) + "\n")
    manifest = {
        "schema": "longvideocompbenc_release_manifest_v0_1",
        "version": ver,
        "built_utc": utc_now(),
        "immutable": True,
        "public_release": False,
        "parent_release": "v0.1.1",
        "ancestors_immutable": ["v0.1.0", "v0.1.1"],
        "includes_video_binaries": False,
        "ab_update": "VIDEO_BOUND_RELATION_HUMAN_APPROVED_QA_DRAFT_PARTIAL",
        "formal_gold": False,
        "proposed_7_4_status": "PROPOSED",
        "frozen_5_2_unchanged": True,
        "files": copied,
    }
    write_json(out / "manifest.json", manifest)
    return manifest


def main() -> None:
    ensure_answer_status_schema()
    # Prior audit must remain on disk
    prior_path = DS_ROOT / "reports" / "AB_SOURCE_RECOVERY_AUDIT.json"
    prior = json.loads(prior_path.read_text()) if prior_path.is_file() else {}

    videos = upsert_videos(read_jsonl(DS_ROOT / "data" / "videos.jsonl"))
    qas = read_jsonl(DS_ROOT / "data" / "qa_items.jsonl")
    evidence = read_jsonl(DS_ROOT / "data" / "evidence.jsonl")
    reviews = read_jsonl(DS_ROOT / "annotations" / "human_reviews.jsonl")
    adj_log = read_jsonl(DS_ROOT / "annotations" / "adjudication_log.jsonl")
    splits = json.loads((DS_ROOT / "data" / "splits.json").read_text())

    # Replace any prior A/B evidence rows (idempotent re-run)
    drop_prefixes = ("lvcb:ev:A:", "lvcb:ev:B:")
    evidence = [e for e in evidence if not e["evidence_id"].startswith(drop_prefixes)]

    hadj_rows = []
    updated_fields = {}
    for sid, adj in ADJUDICATIONS.items():
        roi_ev = build_roi_evidence(sid, adj)
        evidence.extend(roi_ev)
        eids = [e["evidence_id"] for e in roi_ev if e["evidence_id"].endswith(("ROI_A", "ROI_B")) or ":ROI_" in e["evidence_id"]]
        # only active ROI ids for QA pointer
        eids = [evidence_id(sid, "ROI_A"), evidence_id(sid, "ROI_B")]
        prior_snip = (prior.get("items") or {}).get(sid)
        hadj_rows.append(build_human_adj_record(sid, adj, prior_snip))
        reviews = patch_review(reviews, sid, adj)
        adj_log = upsert_adj_log(adj_log, append_adjudication_log(sid, adj))
        new_qas = []
        for q in qas:
            if q.get("source_item_id") == sid:
                q = patch_qa(q, adj, eids)
                updated_fields[sid] = {
                    "video_id": q["video_id"],
                    "question": q["question"],
                    "answer": q["answer"],
                    "answer_status": q["answer_status"],
                    "record_completeness": q["record_completeness"],
                    "formal_gold": q["formal_gold"],
                    "status_bundle": q["composition_attributes"]["status_bundle"],
                    "evidence_ids": q["evidence_ids"],
                    "related_rois": q["composition_attributes"]["related_rois"],
                }
            new_qas.append(q)
        qas = new_qas

    # splits unchanged policy check
    assert splits["frozen_5_2"]["seen"] + splits["frozen_5_2"]["unseen"] == FROZEN_5_2
    assert splits["proposed_7_4_dev"]["status"] == "PROPOSED"
    assert splits["proposed_7_4_dev"]["seen"] == PROPOSED_7_4_SEEN
    assert splits["proposed_7_4_dev"]["unseen"] == PROPOSED_7_4_UNSEEN

    write_jsonl(DS_ROOT / "data" / "videos.jsonl", videos)
    write_jsonl(DS_ROOT / "data" / "qa_items.jsonl", qas)
    write_jsonl(DS_ROOT / "data" / "evidence.jsonl", evidence)
    write_jsonl(DS_ROOT / "annotations" / "human_reviews.jsonl", reviews)
    write_jsonl(DS_ROOT / "annotations" / "adjudication_log.jsonl", adj_log)
    write_jsonl(
        DS_ROOT / "annotations" / "ab_human_adjudications_wp2_2.jsonl", hadj_rows
    )

    report = {
        "schema": "wp2_2_ab_human_adjudication_report_v1",
        "algo_version": ALGO,
        "built_utc": utc_now(),
        "baseline_commit": BASELINE,
        "updated_fields": updated_fields,
        "human_adjudication_path": "annotations/ab_human_adjudications_wp2_2.jsonl",
        "prior_audit_preserved": "reports/AB_SOURCE_RECOVERY_AUDIT.json",
        "remaining_gaps": [
            "QA texts are CHAT_RECONSTRUCTED_QA_DRAFT — not verbatim original QA",
            "Answer semantics (城市台阶附近 / 水果拼盘) need video-observation reconciliation",
            "ROI fragments ≠ complete formal QA windows_seconds",
            "formal_gold remains false for A/B",
            "Necessity A-only/B-only tests not newly human-passed this round",
            "7+4 remains PROPOSED",
        ],
        "not_done": [
            "No new video scan",
            "No Track A experiment",
            "No Gold promotion",
            "v0.1.0 and v0.1.1 untouched",
        ],
    }
    write_json(DS_ROOT / "reports" / "WP2_2_AB_HUMAN_ADJUDICATION_REPORT.json", report)

    # checklist update
    checklist = (
        "# Remaining gaps after WP2.2\n\n"
        + "\n".join(f"- {g}" for g in report["remaining_gaps"])
        + "\n\nPrior recovery audit preserved at `reports/AB_SOURCE_RECOVERY_AUDIT.json`.\n"
    )
    (DS_ROOT / "reports" / "HUMAN_SUPPLEMENT_CHECKLIST.md").write_text(checklist)

    cl = (DS_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = """## v0.1.2 — WP2.2 A/B human adjudication ingest

- Human Scientific Owner confirmed A↔`hROKtPqktO8` same-person bind and B↔`iA_69g87Ilw` same-room bind.
- Bound video IDs; recorded related ROI evidence; attached `CHAT_RECONSTRUCTED_QA_DRAFT` questions/answers.
- A/B → `PARTIAL` (not Gold); formal QA windows not auto-completed from ROI.
- Preserved `AB_SOURCE_RECOVERY_AUDIT.json`; left `releases/v0.1.0` and `v0.1.1` immutable.
- 5+2 frozen / 7+4 PROPOSED unchanged.

"""
    if "## v0.1.2" not in cl:
        (DS_ROOT / "CHANGELOG.md").write_text(entry + cl, encoding="utf-8")
    (DS_ROOT / "VERSION").write_text("0.1.2-dev\n", encoding="utf-8")

    val = run_gates()
    write_json(DS_ROOT / "reports" / "validation_report.json", val)
    if val["overall"] != "PASS":
        print(json.dumps(val, indent=2, ensure_ascii=False)[:5000])
        raise SystemExit(1)

    # refresh coverage
    import dataset_statistics as ds

    sys.argv = ["dataset_statistics.py"]
    ds.main()

    manifest = build_release_v012()
    print(
        json.dumps(
            {
                "validation": val["overall"],
                "release": manifest["version"],
                "updated_fields": updated_fields,
                "adjudication_path": report["human_adjudication_path"],
                "remaining_gaps": report["remaining_gaps"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
