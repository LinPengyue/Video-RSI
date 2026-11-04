#!/usr/bin/env python3
"""Bootstrap LongVideoCompBench v0.1.0-dev from WP1 + Stage2 graphs + pilot inventory.

Does not invent answers, hashes, licenses, or promote SOURCE_WINDOW_ONLY → FRAME_CERTIFIED.
Does not modify the immutable WP1 5+2 export. A/B without original QA are PARTIAL/GRAPH_ONLY.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    ALGO,
    DATASET_VERSION,
    DS_ROOT,
    FROZEN_5_2,
    FROZEN_5_2_SEEN,
    FROZEN_5_2_UNSEEN,
    NORM,
    PILOT,
    PROPOSED_7_4_SEEN,
    PROPOSED_7_4_UNSEEN,
    REPO_ROOT,
    SEED_11,
    WP1,
    evidence_id,
    pg_id,
    qa_id,
    review_id,
    utc_now,
    write_json,
    write_jsonl,
)


def load_inventory() -> dict[str, dict]:
    inv = json.loads((PILOT / "PILOT_INVENTORY.json").read_text())
    return {it["item_id"]: it for it in inv["items"]}


def load_wp1() -> dict:
    report = json.loads((WP1 / "VALIDATION_REPORT.json").read_text())
    if report.get("status") != "PASS":
        raise SystemExit(
            f"WP1 VALIDATION_REPORT status={report.get('status')}; "
            "bootstrap will only emit schemas/tools if forced, refusing data forge."
        )
    return {
        "report": report,
        "qa": json.loads((WP1 / "qa_items.json").read_text()),
        "graphs": json.loads((WP1 / "program_graphs.json").read_text()),
        "videos": json.loads((WP1 / "video_manifest.json").read_text()),
        "split": json.loads((WP1 / "split_manifest.json").read_text()),
    }


def load_norm_graph(item_id: str) -> dict:
    return json.loads((NORM / "graphs" / f"{item_id}.json").read_text())


def missing_fields(obj: dict, required: list[str]) -> list[str]:
    miss = []
    for k in required:
        v = obj.get(k)
        if v is None or v == "" or v == "UNKNOWN" or v == []:
            # empty evidence_ids may be legitimate; still report if required non-empty conceptually
            if k == "evidence_ids" and v == []:
                miss.append(k)
            elif k != "evidence_ids":
                miss.append(k)
    return miss


def build_videos(wp1: dict, inv: dict[str, dict]) -> tuple[list[dict], dict]:
    by_vid: dict[str, dict] = {}
    # WP1 engineering fingerprints (not scientific authority)
    for v in wp1["videos"]["videos"]:
        local = v.get("local_engineering_fingerprint") or {}
        by_vid[v["video_id"]] = {
            "video_id": v["video_id"],
            "source_dataset": v.get("source_dataset") or "LVBench",
            "source_video_id": v["video_id"],
            "source_uri": v.get("accessible_uri_or_path"),
            "duration_seconds": None,  # not forged
            "media_sha256": v.get("video_sha256_scientific") or "UNKNOWN",
            "engineering_sha256": local.get("sha256"),
            "access_status": v.get("access_status") or "UNKNOWN",
            "license_status": "UNKNOWN_NOT_DECLARED_OPEN",
            "pool": "DEV",
            "provenance": {
                "wp1_video_manifest": True,
                "scientific_hash_status": v.get("video_sha256_scientific"),
                "limitations": v.get("limitations"),
            },
        }
    # Inventory videos for F1/F2 (and any seed not in WP1)
    for item_id in SEED_11:
        it = inv.get(item_id) or {}
        vid = it.get("video_id")
        if not vid:
            continue
        if vid not in by_vid:
            by_vid[vid] = {
                "video_id": vid,
                "source_dataset": "LVBench",
                "source_video_id": vid,
                "source_uri": None,
                "duration_seconds": None,
                "media_sha256": "UNKNOWN",
                "engineering_sha256": None,
                "access_status": "PATH_UNKNOWN",
                "license_status": "UNKNOWN_NOT_DECLARED_OPEN",
                "pool": "DEV",
                "provenance": {
                    "from": "PILOT_INVENTORY",
                    "item_ids": [item_id],
                },
            }
        else:
            by_vid[vid].setdefault("provenance", {}).setdefault("item_ids", [])
            if item_id not in by_vid[vid]["provenance"]["item_ids"]:
                by_vid[vid]["provenance"]["item_ids"].append(item_id)

    # Placeholder video slot for seeds with unknown video (A/B)
    if "UNKNOWN_VIDEO_FOR_GRAPH_ONLY_SEEDS" not in by_vid:
        pass  # do not invent a fake video row; QA will have video_id null

    field_missing = {
        vid: missing_fields(
            row,
            [
                "duration_seconds",
                "source_uri",
            ],
        )
        + (
            ["media_sha256_scientific"]
            if row.get("media_sha256") in (None, "UNKNOWN")
            else []
        )
        for vid, row in by_vid.items()
    }
    return sorted(by_vid.values(), key=lambda x: x["video_id"]), field_missing


def convert_graph(item_id: str, g: dict) -> dict:
    nodes = []
    for n in g.get("nodes") or []:
        nodes.append(
            {
                "node_id": n.get("node_id"),
                "raw_operator": n.get("raw_operator"),
                "layer1": n.get("layer1"),
                "layer2": n.get("layer2"),
                "raw_inputs": n.get("raw_inputs") or [],
                "raw_outputs": n.get("raw_outputs") or [],
                "normalized_inputs": n.get("normalized_inputs") or [],
                "normalized_outputs": n.get("normalized_outputs") or [],
                "clip_role": n.get("normalized_clip_role") or n.get("raw_clip_role"),
                "time_conditions": n.get("raw_time_conditions"),
                "evidence_ref": n.get("raw_evidence"),
                "uncertainty_status": n.get("evidence_certification")
                or "UNKNOWN",
                "evidence_certification": n.get("evidence_certification"),
            }
        )
    edges = []
    for e in g.get("edges") or []:
        edges.append(
            {
                "edge_id": e.get("edge_id"),
                "source": e.get("from_node") or e.get("source"),
                "target": e.get("to_node") or e.get("target"),
                "dependency_kind": e.get("normalized_dependency_kind")
                or e.get("dependency_kind"),
                "raw_dependency_kind": e.get("raw_dependency_kind"),
                "provenance": e.get("provenance"),
            }
        )
    return {
        "program_graph_id": pg_id(item_id),
        "qa_id": qa_id(item_id),
        "source_item_id": item_id,
        "n_nodes": g.get("n_nodes", len(nodes)),
        "n_edges": g.get("n_edges", len(edges)),
        "nodes": nodes,
        "edges": edges,
        "graph_approval_status": g.get("normalization_status")
        or "INGESTED_NOT_FORMAL_GOLD",
        "split_role_fixed_source": g.get("split_role_fixed"),
        "source_provenance": {
            "normalized_graph_path": str(
                (NORM / "graphs" / f"{item_id}.json").relative_to(REPO_ROOT)
            ),
            "source": g.get("source"),
            "algo_version": g.get("algo_version"),
        },
    }


def build_evidence_for_item(item_id: str, inv_it: dict | None, wp1_item: dict | None) -> list[dict]:
    rows = []
    windows = None
    video_id = None
    if wp1_item:
        video_id = wp1_item.get("video_id")
        w = wp1_item.get("windows") or {}
        if w.get("status") == "RECORDED_SOURCE_SECONDS" and w.get("A") and w.get("B"):
            windows = {
                "A": (w["A"]["t_start_s"], w["A"]["t_end_s"]),
                "B": (w["B"]["t_start_s"], w["B"]["t_end_s"]),
            }
    if windows is None and inv_it and inv_it.get("windows_seconds"):
        ws = inv_it["windows_seconds"]
        windows = {"A": tuple(ws["A"]), "B": tuple(ws["B"])}
        video_id = video_id or inv_it.get("video_id")

    if windows:
        for role, (start, end) in windows.items():
            rows.append(
                {
                    "evidence_id": evidence_id(item_id, role),
                    "video_id": video_id,
                    "window_start": start,
                    "window_end": end,
                    "modality": "video_window",
                    "source_frame_refs": None,
                    "source_hashes": {"status": "UNKNOWN"},
                    "claim": f"Source window {role} as recorded in scientific review",
                    "certification_status": "SOURCE_WINDOW_ONLY",
                    "reviewer_provenance": {
                        "source": "WP1_or_PILOT_INVENTORY_windows_seconds",
                        "note": "Not auto-upgraded to FRAME_CERTIFIED",
                    },
                }
            )
    else:
        rows.append(
            {
                "evidence_id": evidence_id(item_id, "UNKNOWN"),
                "video_id": (inv_it or {}).get("video_id") or (wp1_item or {}).get("video_id"),
                "window_start": None,
                "window_end": None,
                "modality": "UNKNOWN",
                "source_frame_refs": None,
                "source_hashes": {"status": "UNKNOWN"},
                "claim": None,
                "certification_status": "UNKNOWN",
                "reviewer_provenance": {
                    "source": "missing_approved_source_seconds",
                    "note": "Do not invent windows from program graphs",
                },
            }
        )
    return rows


def build_review(item_id: str, inv_it: dict | None, wp1_item: dict | None, record: dict | None) -> dict:
    auth = None
    if wp1_item and wp1_item.get("necessity"):
        auth = wp1_item["necessity"].get("necessity_authoritative")
    hj = None
    if record and isinstance(record.get("human_judgments_preserved"), dict):
        hj = record["human_judgments_preserved"]
    inv_nec = (inv_it or {}).get("single_window_necessity") or {}

    a_only = b_only = a_plus_b = None
    basis = None
    if auth:
        a_only = auth.get("a_only_sufficient")
        b_only = auth.get("b_only_sufficient")
        a_plus_b = auth.get("a_plus_b")
        basis = auth.get("authority")
    elif hj:
        a_only = hj.get("a_only_sufficient")
        b_only = hj.get("b_only_sufficient")
        a_plus_b = hj.get("a_plus_b_supports_user_answer")
        basis = "human_judgments_preserved"
    elif inv_nec:
        a_only = inv_nec.get("a_only_sufficient", inv_nec.get("a_only_sufficient_full_question"))
        b_only = inv_nec.get("b_only_sufficient", inv_nec.get("b_only_sufficient_full_question"))
        a_plus_b = inv_nec.get("a_plus_b") or inv_nec.get("a_plus_b_necessary")
        basis = "PILOT_INVENTORY.single_window_necessity"

    return {
        "review_id": review_id(item_id, "necessity"),
        "qa_id": qa_id(item_id),
        "review_kind": "necessity_and_adjudication",
        "a_only": a_only,
        "b_only": b_only,
        "a_plus_b": a_plus_b,
        "single_window_shortcut": None,
        "answer_certification": "HUMAN_REFERENCE_OR_HISTORICAL_NOT_FORMAL_GOLD"
        if (wp1_item or inv_it)
        else "UNKNOWN_MISSING_SOURCE",
        "cross_window_bind": {
            "status": "RECORDED_IN_PROGRAM_GRAPH_NOT_AUTO_PASSED"
        },
        "human_adjudication": hj,
        "decision_basis": basis,
        "decision_version": DATASET_VERSION,
        "necessity_test_passed": "NOT_AUTO_INFERRED_FROM_GRAPH",
        "provenance": {
            "inventory_necessity": inv_nec or None,
            "wp1_necessity_present": bool(auth),
        },
    }


def proposed_split_assignment(item_id: str) -> tuple[str, str]:
    if item_id in FROZEN_5_2_SEEN:
        return "SEEN", "frozen_5_2+proposed_7_4_dev"
    if item_id in FROZEN_5_2_UNSEEN:
        return "UNSEEN", "frozen_5_2+proposed_7_4_dev"
    if item_id in ("A", "P7_R4_F1"):
        return "SEEN_PROPOSED", "proposed_7_4_dev_PROPOSED"
    if item_id in ("B", "P7_R4_F2"):
        return "UNSEEN_PROPOSED", "proposed_7_4_dev_PROPOSED"
    return "PENDING", "unknown"


def bootstrap() -> dict:
    wp1 = load_wp1()
    inv = load_inventory()
    wp1_qa = {x["item_id"]: x for x in wp1["qa"]["items"]}

    videos, video_missing = build_videos(wp1, inv)
    graphs = []
    qas = []
    evidence = []
    reviews = []
    necessity_tests = []
    adjudication = []
    per_item_missing: dict[str, dict] = {}

    for item_id in SEED_11:
        g_raw = load_norm_graph(item_id)
        g = convert_graph(item_id, g_raw)
        graphs.append(g)

        inv_it = inv.get(item_id)
        wp1_it = wp1_qa.get(item_id)
        rec_path = PILOT / "provenance_snapshots" / f"{item_id}.json"
        record = json.loads(rec_path.read_text()) if rec_path.is_file() else None
        bp_path = PILOT / "provenance_snapshots" / f"{item_id}_blind_packet.json"
        blind = json.loads(bp_path.read_text()) if bp_path.is_file() else None

        question = None
        answer = None
        video_id = None
        source_qa = item_id

        if wp1_it:
            question = wp1_it.get("question_text")
            answer = (wp1_it.get("answer") or {}).get("answer_text")
            video_id = wp1_it.get("video_id")
            source_qa = wp1_it.get("qa_uid") or item_id
        elif inv_it:
            question = inv_it.get("question_open")
            answer = inv_it.get("answer_reference")
            video_id = inv_it.get("video_id")
            source_qa = inv_it.get("qa_uid") or item_id
            if not question and blind:
                question = blind.get("frozen_question")
        elif blind:
            question = blind.get("frozen_question")
            video_id = blind.get("video_id")

        # Never invent answer from graph outputs
        if answer is None and item_id in ("A", "B"):
            completeness = "GRAPH_ONLY"
            answer_status = "UNKNOWN_MISSING_SOURCE"
        elif question and answer is not None:
            completeness = "COMPLETE"
            answer_status = "HUMAN_REFERENCE_OR_HISTORICAL_NOT_FORMAL_GOLD"
        elif question and answer is None:
            completeness = "PARTIAL"
            answer_status = "UNKNOWN_MISSING_SOURCE"
        else:
            completeness = "GRAPH_ONLY"
            answer_status = "UNKNOWN_MISSING_SOURCE"

        ev_rows = build_evidence_for_item(item_id, inv_it, wp1_it)
        evidence.extend(ev_rows)
        rev = build_review(item_id, inv_it, wp1_it, record)
        reviews.append(rev)
        necessity_tests.append(
            {
                "necessity_test_id": review_id(item_id, "necessity_test"),
                "qa_id": qa_id(item_id),
                "a_only": rev["a_only"],
                "b_only": rev["b_only"],
                "a_plus_b": rev["a_plus_b"],
                "passed": "NOT_AUTO_INFERRED_FROM_GRAPH",
                "source": rev["decision_basis"],
            }
        )
        adjudication.append(
            {
                "log_id": review_id(item_id, "adjudication_log"),
                "qa_id": qa_id(item_id),
                "source_item_id": item_id,
                "event": "BOOTSTRAP_IMPORT",
                "utc": utc_now(),
                "notes": (
                    "Imported from WP1/pilot/normalized graphs; no new scientific adjudication."
                ),
                "formal_gold": False,
            }
        )

        split_asg, split_ver = proposed_split_assignment(item_id)
        qa_row = {
            "qa_id": qa_id(item_id),
            "source_qa_id": str(source_qa),
            "source_item_id": item_id,
            "video_id": video_id,
            "question": question,
            "answer": answer,
            "answer_status": answer_status,
            "program_graph_id": pg_id(item_id),
            "evidence_ids": [e["evidence_id"] for e in ev_rows],
            "necessity_test_id": review_id(item_id, "necessity_test"),
            "review_status": "IMPORTED_PENDING_DATASET_REVIEW",
            "split_assignment": split_asg,
            "split_version": split_ver,
            "composition_attributes": {
                "capability_families_upper": (inv_it or {}).get(
                    "capability_families_upper"
                ),
                "pilot_role_inventory": (inv_it or {}).get("pilot_role"),
                "graph_split_role_fixed": g_raw.get("split_role_fixed"),
            },
            "provenance": {
                "wp1_item": item_id in wp1_qa,
                "inventory_item": item_id in inv,
                "normalized_graph": True,
                "record_snapshot": str(rec_path.relative_to(REPO_ROOT))
                if rec_path.is_file()
                else None,
            },
            "record_completeness": completeness,
            "formal_gold": False,
        }
        qas.append(qa_row)

        miss = []
        if not question:
            miss.append("question")
        if answer is None:
            miss.append("answer")
        if not video_id:
            miss.append("video_id")
        if completeness != "COMPLETE":
            miss.append(f"record_completeness={completeness}")
        # window unknowns
        if all(e.get("window_start") is None for e in ev_rows):
            miss.append("windows_seconds")
        per_item_missing[item_id] = {
            "qa_id": qa_id(item_id),
            "missing_fields": miss,
            "record_completeness": completeness,
        }

    splits = {
        "schema": "longvideocompbenc_splits_v0_1",
        "dataset_version": DATASET_VERSION,
        "built_utc": utc_now(),
        "frozen_5_2": {
            "status": "FROZEN_FOR_TRACK_A_MINIMAL_VALIDATION",
            "seen": FROZEN_5_2_SEEN,
            "unseen": FROZEN_5_2_UNSEEN,
            "immutable": True,
            "wp1_export_path": str(WP1.relative_to(REPO_ROOT)),
            "wp1_validation_status": wp1["report"].get("status"),
            "note": "Do not mutate; Track A minimal validation continues to use WP1 pack.",
        },
        "proposed_7_4_dev": {
            "status": "PROPOSED",
            "seen": PROPOSED_7_4_SEEN,
            "unseen": PROPOSED_7_4_UNSEEN,
            "approval_record": None,
            "candidate_items": {
                "A": {
                    "proposed_pool": "SEEN",
                    "approval_status": "PROPOSED",
                    "prior_label": "CANDIDATE_ONLY",
                },
                "B": {
                    "proposed_pool": "UNSEEN",
                    "approval_status": "PROPOSED",
                    "prior_label": "CANDIDATE_ONLY",
                },
                "P7_R4_F1": {
                    "proposed_pool": "SEEN",
                    "approval_status": "PROPOSED",
                    "prior_label": "CANDIDATE_SENSITIVITY_OR_HOLD",
                },
                "P7_R4_F2": {
                    "proposed_pool": "UNSEEN",
                    "approval_status": "PROPOSED",
                    "prior_label": "CANDIDATE_SENSITIVITY_OR_HOLD",
                },
            },
            "note": (
                "Human final pool approval for A/B/F1/F2 is not recorded as frozen; "
                "status remains PROPOSED."
            ),
        },
        "policy": {
            "no_auto_gold": True,
            "no_inplace_release_mutation": True,
            "sealed_separate": True,
            "scorer_private_not_in_track_a_inference": True,
        },
    }

    # Write data
    write_jsonl(DS_ROOT / "data" / "videos.jsonl", videos)
    write_jsonl(DS_ROOT / "data" / "qa_items.jsonl", qas)
    write_jsonl(DS_ROOT / "data" / "program_graphs.jsonl", graphs)
    write_jsonl(DS_ROOT / "data" / "evidence.jsonl", evidence)
    write_json(DS_ROOT / "data" / "splits.json", splits)
    write_jsonl(DS_ROOT / "annotations" / "human_reviews.jsonl", reviews)
    write_jsonl(DS_ROOT / "annotations" / "necessity_tests.jsonl", necessity_tests)
    write_jsonl(DS_ROOT / "annotations" / "adjudication_log.jsonl", adjudication)

    complete = sum(1 for q in qas if q["record_completeness"] == "COMPLETE")
    partial = sum(1 for q in qas if q["record_completeness"] == "PARTIAL")
    graph_only = sum(1 for q in qas if q["record_completeness"] == "GRAPH_ONLY")

    report = {
        "schema": "longvideocompbenc_bootstrap_report_v0_1",
        "algo_version": ALGO,
        "dataset_version": DATASET_VERSION,
        "built_utc": utc_now(),
        "wp1_status": wp1["report"].get("status"),
        "wp1_algo": wp1["report"].get("algo_version"),
        "seeds_requested": SEED_11,
        "n_program_graphs_imported": len(graphs),
        "n_qa_records": len(qas),
        "n_qa_complete": complete,
        "n_qa_partial": partial,
        "n_qa_graph_only": graph_only,
        "n_videos_unique": len(videos),
        "n_evidence_rows": len(evidence),
        "n_reviews": len(reviews),
        "proposed_7_4_status": "PROPOSED",
        "frozen_5_2_immutable": True,
        "per_item_missing_fields": per_item_missing,
        "video_field_missing": video_missing,
        "status": "PARTIAL" if graph_only or partial else "COMPLETE",
        "status_note": (
            "PARTIAL because some seeds lack original question/answer and/or windows; "
            "no fields were forged."
            if (graph_only or partial)
            else "All 11 seeds have complete QA records."
        ),
        "not_done": [
            "No new video annotation",
            "No Gold promotion",
            "No Track A / expensive RSI",
            "No public license claim",
            "Videos not copied into git",
        ],
    }
    write_json(DS_ROOT / "reports" / "bootstrap_report.json", report)
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.parse_args()
    report = bootstrap()
    print(json.dumps({
        "status": report["status"],
        "n_graphs": report["n_program_graphs_imported"],
        "n_qa_complete": report["n_qa_complete"],
        "n_qa_graph_only": report["n_qa_graph_only"],
        "n_videos": report["n_videos_unique"],
        "proposed_7_4": report["proposed_7_4_status"],
    }, indent=2))


if __name__ == "__main__":
    main()
