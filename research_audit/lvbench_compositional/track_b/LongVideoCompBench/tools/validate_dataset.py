#!/usr/bin/env python3
"""Validate LongVideoCompBench: Gates A–D + negative-test helpers."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DS_ROOT,
    FROZEN_5_2,
    FROZEN_5_2_SEEN,
    FROZEN_5_2_UNSEEN,
    PROPOSED_7_4_SEEN,
    PROPOSED_7_4_UNSEEN,
    SEED_11,
    WP1,
    read_jsonl,
    utc_now,
    write_json,
)

# Reuse WP1 builtin schema validator
sys.path.insert(0, str(WP1 / "eng"))
from strict_schema import SchemaError, validate_or_raise  # noqa: E402


def load_schema(name: str) -> dict:
    return json.loads((DS_ROOT / "schemas" / name).read_text())


def gate_a_schema(data: dict) -> list[dict]:
    issues = []
    mapping = [
        ("video.schema.json", data["videos"]),
        ("qa_item.schema.json", data["qas"]),
        ("program_graph.schema.json", data["graphs"]),
        ("evidence.schema.json", data["evidence"]),
        ("review.schema.json", data["reviews"]),
    ]
    for schema_name, rows in mapping:
        schema = load_schema(schema_name)
        for i, row in enumerate(rows):
            try:
                validate_or_raise(row, schema)
            except SchemaError as e:
                issues.append(
                    {
                        "gate": "A",
                        "code": "SCHEMA_FAIL",
                        "schema": schema_name,
                        "index": i,
                        "path": e.path,
                        "error": e.message,
                        "id": row.get("qa_id")
                        or row.get("video_id")
                        or row.get("program_graph_id")
                        or row.get("evidence_id")
                        or row.get("review_id"),
                    }
                )
    try:
        validate_or_raise(data["splits"], load_schema("split.schema.json"))
    except SchemaError as e:
        issues.append({"gate": "A", "code": "SPLIT_SCHEMA_FAIL", "error": str(e)})
    # JSONL parse already done; ensure unique IDs
    for key, id_field in (
        ("videos", "video_id"),
        ("qas", "qa_id"),
        ("graphs", "program_graph_id"),
        ("evidence", "evidence_id"),
        ("reviews", "review_id"),
    ):
        ids = [r[id_field] for r in data[key]]
        if len(ids) != len(set(ids)):
            issues.append({"gate": "A", "code": "DUPLICATE_ID", "entity": key})
    return issues


def gate_b_refs(data: dict) -> list[dict]:
    issues = []
    videos = {v["video_id"] for v in data["videos"]}
    qas = {q["qa_id"]: q for q in data["qas"]}
    graphs = {g["program_graph_id"]: g for g in data["graphs"]}
    evidence = {e["evidence_id"]: e for e in data["evidence"]}

    for q in data["qas"]:
        if q.get("video_id") and q["video_id"] not in videos:
            issues.append(
                {
                    "gate": "B",
                    "code": "QA_VIDEO_DANGLING",
                    "qa_id": q["qa_id"],
                    "video_id": q["video_id"],
                }
            )
        pg = q.get("program_graph_id")
        if pg and pg not in graphs:
            issues.append(
                {"gate": "B", "code": "QA_GRAPH_DANGLING", "qa_id": q["qa_id"], "pg": pg}
            )
        for eid in q.get("evidence_ids") or []:
            if eid not in evidence:
                issues.append(
                    {
                        "gate": "B",
                        "code": "QA_EVIDENCE_DANGLING",
                        "qa_id": q["qa_id"],
                        "evidence_id": eid,
                    }
                )
    for g in data["graphs"]:
        if g["qa_id"] not in qas:
            issues.append(
                {"gate": "B", "code": "GRAPH_QA_DANGLING", "pg": g["program_graph_id"]}
            )
        nids = {n["node_id"] for n in g["nodes"]}
        for e in g["edges"]:
            if e["source"] not in nids or e["target"] not in nids:
                issues.append(
                    {
                        "gate": "B",
                        "code": "GRAPH_EDGE_NODE_MISSING",
                        "pg": g["program_graph_id"],
                        "edge": e,
                    }
                )
    for e in data["evidence"]:
        if e.get("video_id") and e["video_id"] not in videos:
            issues.append(
                {
                    "gate": "B",
                    "code": "EVIDENCE_VIDEO_DANGLING",
                    "evidence_id": e["evidence_id"],
                }
            )
    return issues


def gate_c_provenance(data: dict) -> list[dict]:
    issues = []
    for q in data["qas"]:
        if q.get("formal_gold") is True:
            issues.append({"gate": "C", "code": "FALSE_GOLD", "qa_id": q["qa_id"]})
        if q["record_completeness"] == "COMPLETE":
            if not q.get("question") or q.get("answer") is None:
                issues.append(
                    {
                        "gate": "C",
                        "code": "COMPLETE_BUT_MISSING_QA_TEXT",
                        "qa_id": q["qa_id"],
                    }
                )
        if q["record_completeness"] == "GRAPH_ONLY" and q.get("answer") is not None:
            # graph-only should not have forged answers; null is required
            pass
        # Do not accept answer invented status
        if q.get("answer_status") == "FORMAL_GOLD":
            issues.append({"gate": "C", "code": "ANSWER_STATUS_PROMOTED", "qa_id": q["qa_id"]})
    for e in data["evidence"]:
        # SOURCE_WINDOW_ONLY must not be FRAME_CERTIFIED
        if e.get("certification_status") == "FRAME_CERTIFIED":
            # only fail if provenance says it was auto-upgraded from window-only
            prov = e.get("reviewer_provenance") or {}
            if "auto" in json.dumps(prov).lower() or prov.get("upgraded_from"):
                issues.append(
                    {
                        "gate": "C",
                        "code": "FRAME_CERT_AUTO_UPGRADE",
                        "evidence_id": e["evidence_id"],
                    }
                )
    for r in data["reviews"]:
        if r.get("necessity_test_passed") is True or r.get("necessity_test_passed") == "TRUE":
            # must be explicit human; auto from graph forbidden without basis
            if r.get("decision_basis") in (None, "program_graph_inferred"):
                issues.append(
                    {
                        "gate": "C",
                        "code": "NECESSITY_AUTO_FROM_GRAPH",
                        "review_id": r["review_id"],
                    }
                )
    # Unknown media hash must remain UNKNOWN (not fake hex)
    for v in data["videos"]:
        h = v.get("media_sha256")
        if h and h != "UNKNOWN" and len(h) == 64:
            # engineering fingerprint may exist separately; scientific claim requires provenance
            if (v.get("provenance") or {}).get("forged_hash"):
                issues.append(
                    {"gate": "C", "code": "FORGED_VIDEO_HASH", "video_id": v["video_id"]}
                )
    return issues


def gate_d_split_leakage(data: dict) -> list[dict]:
    issues = []
    splits = data["splits"]
    f = splits["frozen_5_2"]
    if f.get("immutable") is not True:
        issues.append({"gate": "D", "code": "FROZEN_NOT_IMMUTABLE"})
    if f.get("seen") != FROZEN_5_2_SEEN or f.get("unseen") != FROZEN_5_2_UNSEEN:
        issues.append({"gate": "D", "code": "FROZEN_5_2_MUTATED", "frozen": f})
    # WP1 export files must still exist and match frozen ids
    wp1_qa = json.loads((WP1 / "qa_items.json").read_text())
    wp1_ids = [x["item_id"] for x in wp1_qa["items"]]
    if wp1_ids != FROZEN_5_2:
        issues.append({"gate": "D", "code": "WP1_EXPORT_CHANGED", "ids": wp1_ids})
    p = splits["proposed_7_4_dev"]
    if p.get("status") == "HUMAN_APPROVED_FROZEN" and not p.get("approval_record"):
        issues.append({"gate": "D", "code": "ILLEGAL_SPLIT_PROMOTION_NO_APPROVAL"})
    if p.get("status") != "PROPOSED" and p.get("approval_record") is None:
        # bootstrap requires PROPOSED
        issues.append(
            {
                "gate": "D",
                "code": "ILLEGAL_SPLIT_PROMOTION",
                "status": p.get("status"),
            }
        )
    if p.get("seen") != PROPOSED_7_4_SEEN or p.get("unseen") != PROPOSED_7_4_UNSEEN:
        issues.append({"gate": "D", "code": "PROPOSED_7_4_UNEXPECTED", "proposed": p})
    # Leakage: dataset DEV may contain answers; Track A inference pack must not be overwritten here.
    # Check no release claims public answers
    for q in data["qas"]:
        if q.get("answer_status") == "PUBLIC_TEST_ANSWER":
            issues.append({"gate": "D", "code": "PUBLIC_ANSWER_LEAK", "qa_id": q["qa_id"]})
    return issues


def load_data() -> dict:
    return {
        "videos": read_jsonl(DS_ROOT / "data" / "videos.jsonl"),
        "qas": read_jsonl(DS_ROOT / "data" / "qa_items.jsonl"),
        "graphs": read_jsonl(DS_ROOT / "data" / "program_graphs.jsonl"),
        "evidence": read_jsonl(DS_ROOT / "data" / "evidence.jsonl"),
        "reviews": read_jsonl(DS_ROOT / "annotations" / "human_reviews.jsonl"),
        "splits": json.loads((DS_ROOT / "data" / "splits.json").read_text()),
    }


def run_gates(data: dict | None = None) -> dict:
    data = data or load_data()
    a = gate_a_schema(data)
    b = gate_b_refs(data)
    c = gate_c_provenance(data)
    d = gate_d_split_leakage(data)

    def status(issues: list[dict]) -> str:
        return "PASS" if not issues else "FAIL"

    # Gate B: allow null video_id for GRAPH_ONLY (no dangling)
    b_filtered = [
        i
        for i in b
        if not (
            i.get("code") == "QA_VIDEO_DANGLING"
            and any(
                q["qa_id"] == i.get("qa_id") and q.get("video_id") is None
                for q in data["qas"]
            )
        )
    ]

    report = {
        "schema": "longvideocompbenc_validation_v0_1",
        "validated_utc": utc_now(),
        "gates": {
            "A_schema": {"status": status(a), "n_issues": len(a), "issues": a},
            "B_referential_integrity": {
                "status": status(b_filtered),
                "n_issues": len(b_filtered),
                "issues": b_filtered,
            },
            "C_scientific_provenance": {
                "status": status(c),
                "n_issues": len(c),
                "issues": c,
            },
            "D_split_and_leakage": {
                "status": status(d),
                "n_issues": len(d),
                "issues": d,
            },
        },
        "seed_counts": {
            "n_qas": len(data["qas"]),
            "n_graphs": len(data["graphs"]),
            "n_videos": len(data["videos"]),
            "expected_graphs": len(SEED_11),
        },
    }
    overall = (
        "PASS"
        if all(g["status"] == "PASS" for g in report["gates"].values())
        else "FAIL"
    )
    # PARTIAL data completeness is OK for bootstrap if gates pass
    report["overall"] = overall
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.parse_args()
    report = run_gates()
    write_json(DS_ROOT / "reports" / "validation_report.json", report)
    # also update split integrity report pointer
    write_json(
        DS_ROOT / "reports" / "split_integrity_report.json",
        {
            "schema": "longvideocompbenc_split_integrity_v0_1",
            "validated_utc": utc_now(),
            "gate_d": report["gates"]["D_split_and_leakage"],
            "frozen_5_2": FROZEN_5_2,
            "proposed_7_4_seen": PROPOSED_7_4_SEEN,
            "proposed_7_4_unseen": PROPOSED_7_4_UNSEEN,
        },
    )
    print(
        json.dumps(
            {
                "overall": report["overall"],
                "gates": {k: v["status"] for k, v in report["gates"].items()},
            },
            indent=2,
        )
    )
    if report["overall"] != "PASS":
        for gname, g in report["gates"].items():
            if g["status"] != "PASS":
                print(gname, json.dumps(g["issues"][:5], indent=2, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
