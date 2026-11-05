#!/usr/bin/env python3
"""Import a Human–GPT–Cursor annotation batch from staging into DEV (non-Gold).

WP3.2 integrity rules:
- `import_ready=true` alone cannot bypass semantic certification.
- Self-declared `graph_approval_status` cannot legitimize UNKNOWN/placeholder graphs.
- WP3 dual windows must map to early-A and late-B evidence with times/frames/SHA/QA links.
- Certification requires an independent review record, not a bare boolean.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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
)

UNCERTIFIED_SEMANTICS = {
    "UNRESOLVED",
    "HYPOTHESIS_ONLY",
    "CHATGPT_FRAME_VISUAL_PRELIMINARY",
    "ORDERED_MULTIFRAME_SUGGESTS",
    "STATIC_VISIBLE",
    "UNKNOWN",
    None,
    "",
}

PLACEHOLDER_GRAPH_STATUS = {
    "DRAFT_PLACEHOLDER_NOT_EXECUTABLE",
    "DRAFT_NOT_EXECUTABLE_NOT_GOLD",
    "ABSENT_REJECTED_PAIR",
}

CERTIFIED_SEMANTICS = {
    "HUMAN_VIDEO_VERIFIED",
    "HUMAN_APPROVED",
    "CONTINUOUS_VIDEO_VERIFIED",
    "FACT_VERIFIED",
}


class ImportRejected(Exception):
    pass


def _reject(msg: str) -> None:
    raise ImportRejected(msg)


def _node_op(n: dict[str, Any]) -> str:
    return str(n.get("op") or n.get("raw_operator") or "")


def _is_unknown_op(op: str) -> bool:
    return (not op) or op.startswith("UNKNOWN") or op == "UNKNOWN_PENDING_SEMANTIC_REVIEW"


def _normalize_windows(raw: dict[str, Any]) -> dict[str, list] | None:
    """Accept windows_seconds [[a0,a1],[b0,b1]] or windows {A:[..], B:[..]}."""
    if isinstance(raw.get("windows"), dict):
        w = raw["windows"]
        if w.get("A") and w.get("B"):
            return {"A": list(w["A"]), "B": list(w["B"])}
        if w.get("A") and not w.get("B"):
            return {"A": list(w["A"]), "B": None}  # type: ignore[dict-item]
    ws = raw.get("windows_seconds")
    if isinstance(ws, list) and len(ws) >= 2 and ws[0] and ws[1]:
        return {"A": list(ws[0]), "B": list(ws[1])}
    if isinstance(ws, dict) and ws.get("A") and ws.get("B"):
        return {"A": list(ws["A"]), "B": list(ws["B"])}
    return None


def _independent_review_ok(raw: dict[str, Any]) -> tuple[bool, str | None]:
    """Require a structured independent review record for certification claims."""
    rev = raw.get("independent_review") or raw.get("human_adjudication_record")
    if not isinstance(rev, dict):
        # bare boolean / status flags are insufficient
        if raw.get("human_approved") is True or raw.get("certified") is True:
            return False, "BOOLEAN_FLAG_NOT_INDEPENDENT_REVIEW_RECORD"
        return False, "MISSING_INDEPENDENT_REVIEW_RECORD"
    required = ["reviewer_role", "review_status", "scope", "source_type"]
    missing = [k for k in required if not rev.get(k)]
    if missing:
        return False, f"INDEPENDENT_REVIEW_MISSING_FIELDS:{','.join(missing)}"
    if rev.get("reviewer_role") not in {
        "HUMAN_SCIENTIFIC_OWNER",
        "HUMAN_REVIEWER",
        "INDEPENDENT_ADJUDICATOR",
    }:
        return False, "INDEPENDENT_REVIEW_ROLE_INVALID"
    if rev.get("review_status") not in {
        "HUMAN_APPROVED",
        "HUMAN_VIDEO_VERIFIED",
        "FACT_VERIFIED",
    }:
        return False, "INDEPENDENT_REVIEW_STATUS_NOT_CERTIFIED"
    if rev.get("forged") is True or rev.get("self_attested_without_reviewer") is True:
        return False, "FORGED_OR_SELF_ATTESTED_REVIEW"
    return True, None


def _graph_structurally_valid(nodes: list[dict], edges: list[dict]) -> tuple[bool, str | None]:
    if not nodes:
        return False, "EMPTY_NODES"
    if any(_is_unknown_op(_node_op(n)) for n in nodes):
        return False, "UNKNOWN_OR_PLACEHOLDER_OPERATOR"
    nids = {n.get("node_id") for n in nodes}
    if None in nids or "" in nids:
        return False, "MISSING_NODE_ID"
    if len(nids) != len(nodes):
        return False, "DUPLICATE_NODE_ID"
    for e in edges:
        if e.get("source") not in nids or e.get("target") not in nids:
            return False, "GRAPH_EDGE_INCOMPLETE"
    # Require at least one data-flow edge for multi-node graphs
    if len(nodes) >= 2 and not edges:
        return False, "MISSING_DATAFLOW_EDGES"
    return True, None


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

        if raw.get("import_ready") is False:
            errors.append(
                {
                    "code": "IMPORT_NOT_READY",
                    "source_item_id": sid,
                    "import_block_reason": raw.get("import_block_reason"),
                }
            )
            continue

        # Structural graph legality first — self-declared approvals never override.
        pg_check = raw.get("program_graph") or {}
        pg_status = pg_check.get("status") or ""
        nodes = pg_check.get("nodes") or []
        edges = pg_check.get("edges") or []
        g_ok, g_err = _graph_structurally_valid(nodes, edges)
        if pg_status in PLACEHOLDER_GRAPH_STATUS or not g_ok:
            errors.append(
                {
                    "code": "ILLEGAL_OR_MISSING_PROGRAM_GRAPH",
                    "source_item_id": sid,
                    "program_graph_status": pg_status or "EMPTY",
                    "detail": g_err or "PLACEHOLDER_STATUS",
                    "graph_approval_status_ignored": raw.get("graph_approval_status"),
                }
            )
            continue

        # Semantic certification: NEVER bypassable by import_ready alone.
        sem = raw.get("semantic_certification") or raw.get("relation_evidence_tier")
        if sem in UNCERTIFIED_SEMANTICS or sem not in CERTIFIED_SEMANTICS:
            # Allow legacy non-WP3 example staging without semantic field only if
            # not a WP3 pair and no certification claim is made.
            is_wp3 = str(sid).startswith(("wp3", "WP3")) or "_PAIR" in str(sid)
            claims_cert = bool(
                raw.get("semantic_certification")
                or raw.get("relation_evidence_tier")
                or raw.get("human_approved")
                or raw.get("certified")
                or raw.get("graph_approval_status")
                in {"HUMAN_APPROVED", "CHAT_APPROVED_EXECUTABLE"}
            )
            if is_wp3 or claims_cert or raw.get("import_ready") is True:
                ok_rev, rev_err = _independent_review_ok(raw)
                if not ok_rev or sem not in CERTIFIED_SEMANTICS:
                    errors.append(
                        {
                            "code": "SEMANTICS_NOT_CERTIFIED_FOR_IMPORT",
                            "source_item_id": sid,
                            "semantic_certification": sem,
                            "import_ready": raw.get("import_ready"),
                            "detail": rev_err
                            or "UNCERTIFIED_SEMANTIC_STATUS_CANNOT_BE_BYPASSED_BY_IMPORT_READY",
                        }
                    )
                    continue

        # WP3 dual-window integrity
        is_wp3 = str(sid).startswith(("wp3", "WP3")) or "_PAIR" in str(sid)
        windows = _normalize_windows(raw)
        if is_wp3:
            if raw.get("import_ready") is not True:
                errors.append(
                    {
                        "code": "WP3_STUB_REQUIRES_EXPLICIT_IMPORT_READY",
                        "source_item_id": sid,
                    }
                )
                continue
            if not windows or windows.get("B") is None:
                errors.append(
                    {
                        "code": "WP3_MISSING_B_WINDOW",
                        "source_item_id": sid,
                        "detail": "windows_seconds must provide early A and late B",
                    }
                )
                continue
            # Evidence frame provenance required for WP3 imports
            ev_pack = raw.get("evidence_pack") or {}
            for role in ("A", "B"):
                role_pack = ev_pack.get(role) or {}
                if not role_pack.get("source_frame_refs") or not role_pack.get("source_hashes"):
                    errors.append(
                        {
                            "code": "WP3_EVIDENCE_PROVENANCE_INCOMPLETE",
                            "source_item_id": sid,
                            "window": role,
                        }
                    )
                    break
            else:
                pass
            if any(
                e.get("source_item_id") == sid
                and e.get("code") == "WP3_EVIDENCE_PROVENANCE_INCOMPLETE"
                for e in errors
            ):
                continue
            ok_rev, rev_err = _independent_review_ok(raw)
            if not ok_rev:
                errors.append(
                    {
                        "code": "MISSING_REVIEWER_PROVENANCE",
                        "source_item_id": sid,
                        "detail": rev_err,
                    }
                )
                continue

        if raw.get("split_assignment") in ("SEEN", "UNSEEN") and raw.get(
            "split_promotion_approved"
        ) is not True:
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

        # Re-validate edges (defense in depth; already checked structurally)
        nids = {n.get("node_id") for n in nodes}
        edge_bad = False
        for e in edges:
            if e.get("source") not in nids or e.get("target") not in nids:
                errors.append({"code": "GRAPH_EDGE_INCOMPLETE", "source_item_id": sid})
                edge_bad = True
                break
        if edge_bad:
            continue

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

        evidence_ids: list[str] = []
        ev_pack = raw.get("evidence_pack") or {}
        if windows and windows.get("A") and windows.get("B"):
            for role, label in (("A", "EARLY_A"), ("B", "LATE_B")):
                w = windows[role]
                role_pack = ev_pack.get(role) or {}
                eid = evidence_id(sid, label)
                evidence_ids.append(eid)
                new_ev.append(
                    {
                        "evidence_id": eid,
                        "qa_id": qid,
                        "source_item_id": sid,
                        "video_id": vid,
                        "window_role": role,
                        "window_start": w[0],
                        "window_end": w[1],
                        "modality": role_pack.get("modality") or "visual",
                        "source_frame_refs": role_pack.get("source_frame_refs"),
                        "source_hashes": role_pack.get("source_hashes")
                        or {"status": "UNKNOWN"},
                        "claim": role_pack.get("claim"),
                        "certification_status": role_pack.get("certification_status")
                        or "SOURCE_WINDOW_ONLY",
                        "reviewer_provenance": (
                            raw.get("independent_review")
                            or {"batch_id": batch_id, "status": "PENDING"}
                        ),
                    }
                )
        else:
            # Legacy single/partial window path (non-WP3 example batches)
            ev = {
                "evidence_id": evidence_id(sid, "STAGING"),
                "qa_id": qid,
                "source_item_id": sid,
                "video_id": vid,
                "window_start": None,
                "window_end": None,
                "modality": "UNKNOWN",
                "source_frame_refs": None,
                "source_hashes": {"status": "UNKNOWN"},
                "claim": None,
                "certification_status": "UNKNOWN",
                "reviewer_provenance": {"batch_id": batch_id},
            }
            if isinstance(raw.get("windows"), dict) and raw["windows"].get("A"):
                a = raw["windows"]["A"]
                ev["window_start"] = a[0]
                ev["window_end"] = a[1]
                ev["window_role"] = "A"
                ev["certification_status"] = "SOURCE_WINDOW_ONLY"
            evidence_ids = [ev["evidence_id"]]
            new_ev.append(ev)

        qa_row = {
            "qa_id": qid,
            "source_qa_id": raw.get("source_qa_id") or sid,
            "source_item_id": sid,
            "video_id": vid,
            "question": raw.get("question"),
            "answer": raw.get("answer"),
            "answer_status": raw.get("answer_status") or "UNKNOWN_MISSING_SOURCE",
            "program_graph_id": pid,
            "evidence_ids": evidence_ids,
            "windows_seconds": [windows["A"], windows["B"]] if windows and windows.get("B") else raw.get("windows_seconds"),
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
                "single_window_shortcut": (raw.get("necessity") or {}).get(
                    "single_frame_shortcut"
                ),
                "answer_certification": qa_row["answer_status"],
                "cross_window_bind": None,
                "human_adjudication": raw.get("independent_review")
                or raw.get("human_adjudication"),
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
        write_json(DS_ROOT / "staging" / f"{batch_id}.import_report.json", result)
        return result

    result["status"] = "VALIDATED_READY"
    if apply:
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
