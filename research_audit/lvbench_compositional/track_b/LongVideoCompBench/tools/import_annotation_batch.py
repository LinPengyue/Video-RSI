#!/usr/bin/env python3
"""Import a Human–GPT–Cursor annotation batch from staging into DEV (non-Gold).

Example batch JSON (staging/example_batch.json):
{
  "batch_id": "demo_batch_001",
  "items": [
    {
      "source_item_id": "DEMO001",
      "video_id": "example_video",
      "question": "Example only — not a real seed",
      "answer": null,
      "answer_status": "UNKNOWN_MISSING_SOURCE",
      "program_graph": {"nodes": [...], "edges": [...]},
      "split_assignment": "PENDING",
      "formal_gold": false
    }
  ]
}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DS_ROOT,
    evidence_id,
    pg_id,
    qa_id,
    read_jsonl,
    review_id,
    utc_now,
    write_json,
    write_jsonl,
)
class ImportRejected(Exception):
    pass


def _reject(msg: str) -> None:
    raise ImportRejected(msg)


def import_batch(batch_path: Path, *, apply: bool) -> dict:
    batch = json.loads(batch_path.read_text())
    batch_id = batch.get("batch_id") or batch_path.stem
    items = batch.get("items") or []
    if not items:
        _reject("empty batch")

    existing_qa = {q["qa_id"] for q in read_jsonl(DS_ROOT / "data" / "qa_items.jsonl")}
    existing_vid = {v["video_id"] for v in read_jsonl(DS_ROOT / "data" / "videos.jsonl")}
    existing_pg = {
        g["program_graph_id"] for g in read_jsonl(DS_ROOT / "data" / "program_graphs.jsonl")
    }

    new_qas, new_graphs, new_videos, new_ev, new_rev = [], [], [], [], []
    errors = []

    for raw in items:
        sid = raw.get("source_item_id")
        if not sid:
            errors.append({"code": "MISSING_SOURCE_ITEM_ID"})
            continue
        qid = qa_id(sid)
        pid = pg_id(sid)
        if qid in existing_qa or pid in existing_pg:
            errors.append({"code": "DUPLICATE_IMPORT", "source_item_id": sid, "qa_id": qid})
            continue
        if raw.get("formal_gold") is True:
            errors.append({"code": "UNAPPROVED_GOLD", "source_item_id": sid})
            continue
        if raw.get("split_assignment") in ("SEEN", "UNSEEN") and raw.get(
            "split_promotion_approved"
        ) is not True:
            # new batches may only enter PENDING / PROPOSED pools unless explicitly approved
            if raw.get("split_assignment") not in (
                "PENDING",
                "SEEN_PROPOSED",
                "UNSEEN_PROPOSED",
            ):
                errors.append(
                    {
                        "code": "ILLEGAL_SPLIT_PROMOTION",
                        "source_item_id": sid,
                        "split_assignment": raw.get("split_assignment"),
                    }
                )
                continue
        vid = raw.get("video_id")
        if vid and vid not in existing_vid and not raw.get("video_record"):
            # require explicit video_record for new videos
            errors.append({"code": "MISSING_VIDEO_RECORD", "video_id": vid})
            continue
        if raw.get("video_record"):
            vr = raw["video_record"]
            if vr.get("media_sha256") and vr.get("forged_hash"):
                errors.append({"code": "FORGED_VIDEO_HASH", "video_id": vid})
                continue
            if vr.get("media_sha256") is None:
                vr["media_sha256"] = "UNKNOWN"
            vr.setdefault("license_status", "UNKNOWN_NOT_DECLARED_OPEN")
            vr.setdefault("duration_seconds", None)
            vr.setdefault("pool", "DEV")
            new_videos.append(vr)
            existing_vid.add(vr["video_id"])

        pg_raw = raw.get("program_graph") or {}
        nodes = pg_raw.get("nodes") or []
        edges = pg_raw.get("edges") or []
        nids = {n.get("node_id") for n in nodes}
        for e in edges:
            if e.get("source") not in nids or e.get("target") not in nids:
                errors.append({"code": "GRAPH_EDGE_INCOMPLETE", "source_item_id": sid})
                break
        else:
            graph = {
                "program_graph_id": pid,
                "qa_id": qid,
                "source_item_id": sid,
                "n_nodes": len(nodes),
                "n_edges": len(edges),
                "nodes": nodes,
                "edges": edges,
                "graph_approval_status": raw.get("graph_approval_status")
                or "STAGING_INGESTED_NOT_GOLD",
                "source_provenance": {
                    "batch_id": batch_id,
                    "batch_path": str(batch_path),
                },
            }
            new_graphs.append(graph)

            ev = {
                "evidence_id": evidence_id(sid, "STAGING"),
                "video_id": vid,
                "window_start": (raw.get("windows") or {}).get("A", [None, None])[0]
                if isinstance(raw.get("windows"), dict)
                else None,
                "window_end": None,
                "modality": "UNKNOWN",
                "source_frame_refs": None,
                "source_hashes": {"status": "UNKNOWN"},
                "claim": None,
                "certification_status": "UNKNOWN",
                "reviewer_provenance": {"batch_id": batch_id},
            }
            # windows optional
            if isinstance(raw.get("windows"), dict) and raw["windows"].get("A"):
                a = raw["windows"]["A"]
                ev["window_start"] = a[0]
                ev["window_end"] = a[1]
                ev["certification_status"] = "SOURCE_WINDOW_ONLY"
            new_ev.append(ev)

            qa_row = {
                "qa_id": qid,
                "source_qa_id": raw.get("source_qa_id") or sid,
                "source_item_id": sid,
                "video_id": vid,
                "question": raw.get("question"),
                "answer": raw.get("answer"),
                "answer_status": raw.get("answer_status")
                or "UNKNOWN_MISSING_SOURCE",
                "program_graph_id": pid,
                "evidence_ids": [ev["evidence_id"]],
                "necessity_test_id": review_id(sid, "necessity_test"),
                "review_status": "STAGING_IMPORTED",
                "split_assignment": raw.get("split_assignment") or "PENDING",
                "split_version": f"batch:{batch_id}",
                "composition_attributes": raw.get("composition_attributes") or {},
                "provenance": {"batch_id": batch_id, "staging": True},
                "record_completeness": (
                    "COMPLETE"
                    if raw.get("question") and raw.get("answer") is not None
                    else "PARTIAL"
                ),
                "formal_gold": False,
            }
            new_qas.append(qa_row)
            new_rev.append(
                {
                    "review_id": review_id(sid, "necessity"),
                    "qa_id": qid,
                    "review_kind": "staging_import",
                    "a_only": (raw.get("necessity") or {}).get("a_only"),
                    "b_only": (raw.get("necessity") or {}).get("b_only"),
                    "a_plus_b": (raw.get("necessity") or {}).get("a_plus_b"),
                    "single_window_shortcut": None,
                    "answer_certification": qa_row["answer_status"],
                    "cross_window_bind": None,
                    "human_adjudication": raw.get("human_adjudication"),
                    "decision_basis": "staging_batch",
                    "decision_version": batch_id,
                    "necessity_test_passed": "NOT_AUTO_INFERRED_FROM_GRAPH",
                    "provenance": {"batch_id": batch_id},
                }
            )

    result = {
        "batch_id": batch_id,
        "batch_path": str(batch_path),
        "utc": utc_now(),
        "n_accepted": len(new_qas),
        "n_errors": len(errors),
        "errors": errors,
        "applied": False,
    }
    if errors:
        result["status"] = "REJECTED"
        write_json(
            DS_ROOT / "staging" / f"{batch_id}.import_report.json", result
        )
        return result

    result["status"] = "VALIDATED_READY"
    if apply:
        # append to jsonl
        def append_jsonl(path: Path, rows: list[dict]) -> None:
            with path.open("a", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

        append_jsonl(DS_ROOT / "data" / "qa_items.jsonl", new_qas)
        append_jsonl(DS_ROOT / "data" / "program_graphs.jsonl", new_graphs)
        append_jsonl(DS_ROOT / "data" / "evidence.jsonl", new_ev)
        append_jsonl(DS_ROOT / "annotations" / "human_reviews.jsonl", new_rev)
        if new_videos:
            append_jsonl(DS_ROOT / "data" / "videos.jsonl", new_videos)
        result["applied"] = True
        result["status"] = "APPLIED_DEV_NOT_GOLD"
    write_json(DS_ROOT / "staging" / f"{batch_id}.import_report.json", result)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("batch_json", type=Path)
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Append to DEV jsonl (never Gold). Default is dry-run validate only.",
    )
    args = ap.parse_args()
    try:
        result = import_batch(args.batch_json, apply=args.apply)
    except ImportRejected as e:
        print(json.dumps({"status": "REJECTED", "error": str(e)}, indent=2))
        raise SystemExit(2)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] == "REJECTED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
