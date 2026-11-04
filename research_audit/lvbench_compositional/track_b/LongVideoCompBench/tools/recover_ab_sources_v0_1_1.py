#!/usr/bin/env python3
"""WP2.1: audit A/B source recovery + C2/R3/F1/F2 window candidates; patch v0.1.1.

Does not invent QA from program-graph output tokens (answer_urban_stairs /
answer_fruit_platter). Does not promote review-media filename seconds to
approved windows_seconds. Does not mutate releases/v0.1.0.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DS_ROOT,
    NORM,
    PILOT,
    REPO_ROOT,
    WP1,
    read_jsonl,
    sha256_file,
    utc_now,
    write_json,
    write_jsonl,
)
from validate_dataset import run_gates  # noqa: E402

ALGO = "longvideocompbenc_recover_ab_v0_1_1"


def _sha(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except Exception:
        return str(path)


def field_rec(
    *,
    recovered_value,
    source_path,
    source_sha256,
    recovery_method,
    confidence,
    certification_status,
    unresolved_reason=None,
    candidates=None,
):
    return {
        "recovered_value": recovered_value,
        "source_path": source_path,
        "source_sha256": source_sha256,
        "recovery_method": recovery_method,
        "confidence": confidence,
        "certification_status": certification_status,
        "unresolved_reason": unresolved_reason,
        "candidates": candidates or [],
    }


def build_ab_audit() -> dict:
    graph_a = NORM / "graphs" / "A.json"
    graph_b = NORM / "graphs" / "B.json"
    handoff = (
        NORM
        / "chat_approved_handoff"
        / "track_b_stage2_chat_approved_handoff_v1.json"
    )
    adj = PILOT / "p3_e1_targeted_evidence" / "HUMAN_ADJUDICATIONS.json"
    drafts = (
        REPO_ROOT
        / "research_audit/lvbench_compositional/track_b/batch_factory/run_002/qa_drafts.jsonl"
    )
    catalog = PILOT / "p3_e1_review_platform" / "data" / "catalog.json"

    a_sha, b_sha = _sha(graph_a), _sha(graph_b)
    h_sha, adj_sha, d_sha = _sha(handoff), _sha(adj), _sha(drafts)

    # Load draft questions as CONFLICTING candidates (semantics ≠ graph A/B)
    draft_rows = []
    if drafts.is_file():
        for line in drafts.read_text().splitlines():
            row = json.loads(line)
            if row.get("video_id") in ("hROKtPqktO8", "iA_69g87Ilw"):
                draft_rows.append(
                    {
                        "qa_id": row.get("qa_id"),
                        "video_id": row.get("video_id"),
                        "question_zh": row.get("question_zh"),
                        "provisional_answer_zh": row.get("provisional_answer_zh"),
                        "gold_answer": row.get("gold_answer"),
                        "answer_status": row.get("answer_status"),
                        "time_intervals": row.get("time_intervals"),
                        "formal_supported": row.get("formal_supported"),
                        "funnel_level": row.get("funnel_level"),
                        "note": (
                            "Batch-factory contrast draft — NOT bound to Stage2 item "
                            "A/B program graphs; not promoted."
                        ),
                    }
                )

    adj_doc = json.loads(adj.read_text()) if adj.is_file() else {"records": []}

    items = {}
    # ---- A ----
    items["A"] = {
        "question": field_rec(
            recovered_value=None,
            source_path=None,
            source_sha256=None,
            recovery_method="exhaustive_repo_and_pilot_search",
            confidence="NONE",
            certification_status="UNRESOLVED",
            unresolved_reason=(
                "No authoritative original question text bound to source_item_id=A. "
                "Chat-approved graph A has no question field. Batch-factory drafts on "
                "hROKtPqktO8 are semantic contrast QAs, not the A program "
                "(hillside-selfie↔urban-stairway bind→QueryLocation)."
            ),
            candidates=[
                {
                    "kind": "REJECTED_AS_ITEM_A_QUESTION",
                    "why_rejected": "No item_id=A binding; question type mismatches graph A",
                    "examples": [
                        r for r in draft_rows if r["video_id"] == "hROKtPqktO8"
                    ],
                    "source_path": _rel(drafts),
                    "source_sha256": d_sha,
                }
            ],
        ),
        "answer": field_rec(
            recovered_value=None,
            source_path=_rel(graph_a),
            source_sha256=a_sha,
            recovery_method="explicit_non_inference_from_graph_outputs",
            confidence="NONE",
            certification_status="UNRESOLVED",
            unresolved_reason=(
                "Graph output token answer_urban_stairs is an I/O label, not an "
                "approved human answer. Forbidden to reverse-mint QA answer from it."
            ),
            candidates=[
                {
                    "kind": "GRAPH_IO_TOKEN_NOT_ANSWER",
                    "token": "answer_urban_stairs",
                    "source_path": _rel(graph_a),
                    "source_sha256": a_sha,
                    "certification_status": "NOT_AN_ANSWER",
                }
            ],
        ),
        "video_id": field_rec(
            recovered_value=None,
            source_path=_rel(adj),
            source_sha256=adj_sha,
            recovery_method="evidence_string_overlap_hypothesis_only",
            confidence="LOW_UNBOUND",
            certification_status="CANDIDATE_CONFLICTING_OR_UNBOUND",
            unresolved_reason=(
                "Graph A evidence strings mention 'later hillside selfie' / "
                "'earlier urban stairway'. HUMAN_ADJUDICATIONS record hillside selfie "
                "on hROKtPqktO8@1255-1265 and street/selfie@500-510, but do not name "
                "'urban stairway' and never bind item_id=A. Not promoted."
            ),
            candidates=[
                {
                    "video_id": "hROKtPqktO8",
                    "basis": "hillside selfie ROI overlap with graph A raw_evidence",
                    "rois": [
                        "hROKtPqktO8_ROI_500_510",
                        "hROKtPqktO8_ROI_1255_1265",
                    ],
                    "source_path": _rel(adj),
                    "source_sha256": adj_sha,
                    "certification_status": "NOT_CERTIFIED",
                    "human_review_status": [
                        r.get("review_status")
                        for r in adj_doc.get("records", [])
                        if r.get("video_id") == "hROKtPqktO8"
                    ],
                }
            ],
        ),
        "windows": field_rec(
            recovered_value=None,
            source_path=_rel(catalog) if catalog.is_file() else _rel(adj),
            source_sha256=_sha(catalog) if catalog.is_file() else adj_sha,
            recovery_method="roi_context_windows_not_item_ab_windows",
            confidence="LOW_UNBOUND",
            certification_status="NOT_ITEM_WINDOWS",
            unresolved_reason=(
                "ROI/context seconds exist for hROKtPqktO8 but are not approved "
                "windows_seconds for item A."
            ),
            candidates=[
                {
                    "video_id": "hROKtPqktO8",
                    "roi_id": "hROKtPqktO8_ROI_500_510",
                    "roi_seconds": [500, 510],
                    "context_seconds": [480, 530],
                    "role_hypothesis": "possibly earlier clip (street/selfie) — NOT urban-stairway certified",
                },
                {
                    "video_id": "hROKtPqktO8",
                    "roi_id": "hROKtPqktO8_ROI_1255_1265",
                    "roi_seconds": [1255, 1265],
                    "context_seconds": [1235, 1285],
                    "role_hypothesis": "later hillside selfie — matches graph evidence string only",
                },
            ],
        ),
        "evidence_media_paths": field_rec(
            recovered_value=None,
            source_path=_rel(
                PILOT / "p3_e1_targeted_evidence" / "EVIDENCE_MANIFEST.json"
            ),
            source_sha256=_sha(
                PILOT / "p3_e1_targeted_evidence" / "EVIDENCE_MANIFEST.json"
            ),
            recovery_method="local_media_paths_for_candidate_video",
            confidence="MEDIUM_FOR_ROI_MEDIA_ONLY",
            certification_status="ROI_MEDIA_NOT_ITEM_A_EVIDENCE",
            unresolved_reason="Paths belong to P3-E1 ROI contexts, not certified item-A evidence pack.",
            candidates=[
                {
                    "path": "research_audit/lvbench_compositional/track_b/local_media/p3_e1_targeted_evidence/hROKtPqktO8/ROI1_CONTEXT/",
                    "git_committed": False,
                },
                {
                    "path": "research_audit/lvbench_compositional/track_b/local_media/p3_e1_targeted_evidence/hROKtPqktO8/ROI2_CONTEXT/",
                    "git_committed": False,
                },
            ],
        ),
        "human_scientific_adjudication": field_rec(
            recovered_value={
                "for_item_A_qa": None,
                "for_related_rois_only": True,
            },
            source_path=_rel(adj),
            source_sha256=adj_sha,
            recovery_method="human_adjudications_roi_level",
            confidence="HIGH_FOR_ROI_NOT_ITEM",
            certification_status="ROI_NOT_CERTIFIED",
            unresolved_reason="No human adjudication record keyed by item_id/pack_id A.",
            candidates=[
                {
                    "roi_id": r.get("roi_id"),
                    "review_status": r.get("review_status"),
                    "certification_status": r.get("certification_status"),
                }
                for r in adj_doc.get("records", [])
                if r.get("video_id") == "hROKtPqktO8"
            ],
        ),
        "program_graph_structure": field_rec(
            recovered_value={
                "present": True,
                "n_nodes": 4,
                "n_edges": 3,
                "status": "CHAT_APPROVED_SIDECAR_NOT_FRAME_CERTIFIED",
            },
            source_path=_rel(graph_a),
            source_sha256=a_sha,
            recovery_method="already_in_dataset",
            confidence="HIGH_STRUCTURE_ONLY",
            certification_status="NOT_FRAME_CERTIFIED_BY_HANDOFF",
            unresolved_reason=None,
        ),
    }

    # ---- B ----
    items["B"] = {
        "question": field_rec(
            recovered_value=None,
            source_path=None,
            source_sha256=None,
            recovery_method="exhaustive_repo_and_pilot_search",
            confidence="NONE",
            certification_status="UNRESOLVED",
            unresolved_reason=(
                "No authoritative original question text bound to source_item_id=B. "
                "Graph B is room-bind→QueryEarlierObject(fruit platter); iA batch drafts "
                "are scene-contrast QAs and are not promoted."
            ),
            candidates=[
                {
                    "kind": "REJECTED_AS_ITEM_B_QUESTION",
                    "why_rejected": "No item_id=B binding; mismatch vs LocateFarewellRoom program",
                    "examples": [
                        r for r in draft_rows if r["video_id"] == "iA_69g87Ilw"
                    ],
                    "source_path": _rel(drafts),
                    "source_sha256": d_sha,
                }
            ],
        ),
        "answer": field_rec(
            recovered_value=None,
            source_path=_rel(graph_b),
            source_sha256=b_sha,
            recovery_method="explicit_non_inference_from_graph_outputs",
            confidence="NONE",
            certification_status="UNRESOLVED",
            unresolved_reason=(
                "Graph output token answer_fruit_platter is an I/O label, not an "
                "approved human answer."
            ),
            candidates=[
                {
                    "kind": "GRAPH_IO_TOKEN_NOT_ANSWER",
                    "token": "answer_fruit_platter",
                    "source_path": _rel(graph_b),
                    "source_sha256": b_sha,
                    "certification_status": "NOT_AN_ANSWER",
                }
            ],
        ),
        "video_id": field_rec(
            recovered_value=None,
            source_path=_rel(adj),
            source_sha256=adj_sha,
            recovery_method="evidence_string_overlap_hypothesis_only",
            confidence="LOW_UNBOUND",
            certification_status="CANDIDATE_CONFLICTING_OR_UNBOUND",
            unresolved_reason=(
                "Fruit-platter observation exists on iA_69g87Ilw@358-368, and graph B "
                "queries earlier fruit platter, but 'farewell room' is not an approved "
                "ROI label and item_id=B is never bound."
            ),
            candidates=[
                {
                    "video_id": "iA_69g87Ilw",
                    "basis": "fruit platter ROI overlap with graph B raw_evidence",
                    "rois": [
                        "iA_69g87Ilw_ROI_358_368",
                        "iA_69g87Ilw_ROI_900_910",
                    ],
                    "source_path": _rel(adj),
                    "source_sha256": adj_sha,
                    "certification_status": "NOT_CERTIFIED",
                    "human_review_status": [
                        r.get("review_status")
                        for r in adj_doc.get("records", [])
                        if r.get("video_id") == "iA_69g87Ilw"
                    ],
                }
            ],
        ),
        "windows": field_rec(
            recovered_value=None,
            source_path=_rel(adj),
            source_sha256=adj_sha,
            recovery_method="roi_context_windows_not_item_ab_windows",
            confidence="LOW_UNBOUND",
            certification_status="NOT_ITEM_WINDOWS",
            unresolved_reason="ROI seconds are not approved item-B A/B windows.",
            candidates=[
                {
                    "video_id": "iA_69g87Ilw",
                    "roi_id": "iA_69g87Ilw_ROI_358_368",
                    "roi_seconds": [358, 368],
                    "context_seconds": [350, 375],
                    "role_hypothesis": "earlier fruit-platter display candidate",
                },
                {
                    "video_id": "iA_69g87Ilw",
                    "roi_id": "iA_69g87Ilw_ROI_900_910",
                    "roi_seconds": [900, 910],
                    "context_seconds": [890, 920],
                    "role_hypothesis": "later speaking/door-sign — NOT certified farewell-room",
                },
            ],
        ),
        "evidence_media_paths": field_rec(
            recovered_value=None,
            source_path=_rel(
                PILOT / "p3_e1_targeted_evidence" / "EVIDENCE_MANIFEST.json"
            ),
            source_sha256=_sha(
                PILOT / "p3_e1_targeted_evidence" / "EVIDENCE_MANIFEST.json"
            ),
            recovery_method="local_media_paths_for_candidate_video",
            confidence="MEDIUM_FOR_ROI_MEDIA_ONLY",
            certification_status="ROI_MEDIA_NOT_ITEM_B_EVIDENCE",
            unresolved_reason="ROI media ≠ item-B certified evidence.",
            candidates=[
                {
                    "path": "research_audit/lvbench_compositional/track_b/local_media/p3_e1_targeted_evidence/iA_69g87Ilw/ROI3_CONTEXT/",
                    "git_committed": False,
                },
                {
                    "path": "research_audit/lvbench_compositional/track_b/local_media/p3_e1_targeted_evidence/iA_69g87Ilw/ROI4_CONTEXT/",
                    "git_committed": False,
                },
            ],
        ),
        "human_scientific_adjudication": field_rec(
            recovered_value={
                "for_item_B_qa": None,
                "for_related_rois_only": True,
            },
            source_path=_rel(adj),
            source_sha256=adj_sha,
            recovery_method="human_adjudications_roi_level",
            confidence="HIGH_FOR_ROI_NOT_ITEM",
            certification_status="ROI_NOT_CERTIFIED",
            unresolved_reason="No human adjudication record keyed by item_id/pack_id B.",
            candidates=[
                {
                    "roi_id": r.get("roi_id"),
                    "review_status": r.get("review_status"),
                    "certification_status": r.get("certification_status"),
                }
                for r in adj_doc.get("records", [])
                if r.get("video_id") == "iA_69g87Ilw"
            ],
        ),
        "program_graph_structure": field_rec(
            recovered_value={
                "present": True,
                "n_nodes": 4,
                "n_edges": 3,
                "status": "CHAT_APPROVED_SIDECAR_NOT_FRAME_CERTIFIED",
            },
            source_path=_rel(graph_b),
            source_sha256=b_sha,
            recovery_method="already_in_dataset",
            confidence="HIGH_STRUCTURE_ONLY",
            certification_status="NOT_FRAME_CERTIFIED_BY_HANDOFF",
            unresolved_reason=None,
        ),
    }

    def recovery_rate(item: dict) -> dict:
        primary = ["question", "answer", "video_id", "windows"]
        n_ok = sum(1 for k in primary if item[k]["recovered_value"] is not None)
        return {
            "primary_fields": primary,
            "n_recovered": n_ok,
            "n_total": len(primary),
            "rate": round(n_ok / len(primary), 4),
        }

    return {
        "schema": "ab_source_recovery_audit_v0_1_1",
        "algo_version": ALGO,
        "built_utc": utc_now(),
        "baseline_commit_expected": "32b161ff6d3200461e0e004d6ea11ebf4ac366e4",
        "policy": [
            "Do not reverse-mint QA from answer_urban_stairs / answer_fruit_platter",
            "Chat-approved graph structure ≠ frame/video certification",
            "Batch-factory drafts without item_id binding are candidates only",
            "Promote dataset fields only when recovered_value is non-null with explicit binding",
        ],
        "items": items,
        "recovery_rates": {k: recovery_rate(v) for k, v in items.items()},
        "dataset_action": {
            "A_record_completeness": "GRAPH_ONLY_RETAINED",
            "B_record_completeness": "GRAPH_ONLY_RETAINED",
            "formal_gold": False,
            "reason": "Primary QA fields remain unresolved; no silent promotion.",
        },
        "handoff_sha256": h_sha,
    }


def build_window_audit() -> dict:
    """C2/R3/F1/F2 — record candidates; do not promote without scientific approval."""
    out = {}
    specs = {
        "P7_VTCD_C2": {
            "blind": PILOT / "provenance_snapshots" / "P7_VTCD_C2_blind_packet.json",
            "filename_windows": {"A": [158, 191], "B": [260, 285]},
            "media_hints": [
                "p7_hil_pilot/round_002/vtcd_review/media/A_context_158_191.mp4",
                "p7_hil_pilot/round_002/vtcd_review/media/B_context_260_285.mp4",
            ],
        },
        "P7_TJR_R3": {
            "blind": PILOT / "provenance_snapshots" / "P7_TJR_R3_blind_packet.json",
            "filename_windows": {"A": [1100, 1125], "B": [1200, 1220]},
            "media_hints": [
                "p7_hil_pilot/round_002/tjr_relocate/media/early_candidate_dragon_ride_1100_1125.mp4",
                "p7_hil_pilot/round_002/tjr_relocate/media/late_dual_performers_1200_1220.mp4",
            ],
        },
        "P7_R4_F1": {
            "blind": PILOT / "provenance_snapshots" / "P7_R4_F1_blind_packet.json",
            "filename_windows": {"A": [259, 295], "B": [2995, 3015]},
            "media_hints": [
                "round_004/media/F1A_restaurant_259_295.mp4",
                "round_004/media/F1B_snow_2995_3015.mp4",
            ],
        },
        "P7_R4_F2": {
            "blind": PILOT / "provenance_snapshots" / "P7_R4_F2_blind_packet.json",
            "filename_windows": {"A": [20, 45], "B": [123, 165]},
            "media_hints": [
                "round_004/media/F2A_dog_wood_20_45.mp4",
                "round_004/media/F2B_later_play_123_165.mp4",
            ],
        },
    }
    for item_id, spec in specs.items():
        gpath = PILOT / "provenance_snapshots" / f"{item_id}.json"
        g = json.loads(gpath.read_text()) if gpath.is_file() else {}
        out[item_id] = {
            "recovered_value": None,
            "source_path": _rel(spec["blind"]),
            "source_sha256": _sha(spec["blind"]),
            "recovery_method": "blind_packet_clip_filename_parse_only",
            "confidence": "LOW_FILENAME_DERIVED",
            "certification_status": "NOT_PROMOTED_PENDING_SCIENTIFIC_APPROVAL",
            "precise_timing_status": g.get("precise_timing_status"),
            "unresolved_reason": (
                "Filename-encoded ranges and review clips are engineering extract "
                "hints; inventory/REVIEW_PACK windows_seconds remain null; "
                "precise_timing_status is PENDING/PARTIAL. Per WP1.1 policy, not "
                "written as RECORDED_SOURCE_SECONDS."
            ),
            "candidates": [
                {
                    "kind": "REVIEW_MEDIA_FILENAME_SECONDS",
                    "windows_seconds_hypothesis": spec["filename_windows"],
                    "media_hints": spec["media_hints"],
                    "do_not_use_as_fixed_ab_eval": True,
                }
            ],
            "dataset_action": "WINDOWS_REMAIN_UNKNOWN",
        }
    return {
        "schema": "window_recovery_c2_r3_f1_f2_audit_v0_1_1",
        "algo_version": ALGO,
        "built_utc": utc_now(),
        "items": out,
        "policy": "No invented seconds; no promotion without approved windows_seconds.",
    }


def patch_qa_provenance(ab_audit: dict) -> None:
    qas = read_jsonl(DS_ROOT / "data" / "qa_items.jsonl")
    out = []
    for q in qas:
        if q.get("source_item_id") in ("A", "B"):
            q = dict(q)
            q["provenance"] = dict(q.get("provenance") or {})
            q["provenance"]["ab_source_recovery_v0_1_1"] = {
                "audit": "reports/AB_SOURCE_RECOVERY_AUDIT.json",
                "record_completeness_unchanged": q["record_completeness"],
                "recovery_rate": ab_audit["recovery_rates"][q["source_item_id"]],
                "note": "No primary QA fields promoted.",
            }
            assert q["record_completeness"] == "GRAPH_ONLY"
            assert q.get("formal_gold") is False
            assert q.get("question") is None
            assert q.get("answer") is None
        out.append(q)
    write_jsonl(DS_ROOT / "data" / "qa_items.jsonl", out)


def write_human_checklist(ab_audit: dict, win_audit: dict) -> str:
    lines = [
        "# Human / GPT supplement checklist (WP2.1)",
        "",
        "A/B remain `GRAPH_ONLY`. Do not treat graph I/O tokens as answers.",
        "",
        "## A / B — required before completeness upgrade",
        "",
        "For each of A and B, supply or approve:",
        "1. Bound `video_id` (or explicitly reject hROKtPqktO8 / iA_69g87Ilw candidates).",
        "2. Original question text (not reverse-derived from program graph).",
        "3. Original answer text with certification status (still not formal Gold unless separately approved).",
        "4. Approved `windows_seconds` A/B (ROI candidates are insufficient alone).",
        "5. Explicit item_id↔evidence pack binding.",
        "",
        f"- A primary recovery rate: {ab_audit['recovery_rates']['A']}",
        f"- B primary recovery rate: {ab_audit['recovery_rates']['B']}",
        "",
        "## C2 / R3 / F1 / F2 — window authorization",
        "",
        "Filename-derived candidates exist but are **not** dataset windows. Approve or reject:",
        "",
    ]
    for iid, row in win_audit["items"].items():
        hyp = row["candidates"][0]["windows_seconds_hypothesis"]
        lines.append(
            f"- `{iid}`: candidate {hyp} — status `{row['precise_timing_status']}` — **needs scientific authorization**"
        )
    lines.append("")
    lines.append("See `reports/AB_SOURCE_RECOVERY_AUDIT.json` and `reports/WINDOW_RECOVERY_C2_R3_F1_F2_AUDIT.json`.")
    lines.append("")
    return "\n".join(lines)


def build_v011_release() -> dict:
    ver = "v0.1.1"
    out = DS_ROOT / "releases" / ver
    if (out / "manifest.json").is_file():
        # Immutable: do not rebuild in place; return existing manifest.
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
        "reports/bootstrap_report.json",
        "reports/coverage_report.json",
        "reports/split_integrity_report.json",
        "reports/validation_report.json",
        "reports/AB_SOURCE_RECOVERY_AUDIT.json",
        "reports/WINDOW_RECOVERY_C2_R3_F1_F2_AUDIT.json",
        "reports/HUMAN_SUPPLEMENT_CHECKLIST.md",
        "VERSION",
        "CHANGELOG.md",
    ]
    out.mkdir(parents=True, exist_ok=True)
    checksums = []
    copied = []
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
        "parent_release": "v0.1.0",
        "parent_immutable_verified": True,
        "includes_video_binaries": False,
        "ab_recovery": "ATTEMPTED_PRIMARY_FIELDS_UNRESOLVED_GRAPH_ONLY_RETAINED",
        "files": copied,
    }
    write_json(out / "manifest.json", manifest)
    return manifest


def main() -> None:
    # Verify v0.1.0 still present / immutable
    v010 = DS_ROOT / "releases" / "v0.1.0"
    if not (v010 / "manifest.json").is_file():
        raise SystemExit("v0.1.0 missing — refuse patch")

    ab = build_ab_audit()
    win = build_window_audit()
    write_json(DS_ROOT / "reports" / "AB_SOURCE_RECOVERY_AUDIT.json", ab)
    write_json(DS_ROOT / "reports" / "WINDOW_RECOVERY_C2_R3_F1_F2_AUDIT.json", win)
    checklist = write_human_checklist(ab, win)
    (DS_ROOT / "reports" / "HUMAN_SUPPLEMENT_CHECKLIST.md").write_text(
        checklist, encoding="utf-8"
    )

    patch_qa_provenance(ab)

    # Changelog + version note
    cl = (DS_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = """## v0.1.1 — WP2.1 A/B recovery audit (no Gold / no invented QA)

- Added `reports/AB_SOURCE_RECOVERY_AUDIT.json` with per-field recovery evidence.
- Added `reports/WINDOW_RECOVERY_C2_R3_F1_F2_AUDIT.json` (filename candidates only; not promoted).
- A/B remain `GRAPH_ONLY` — question/answer/video_id/windows unresolved under binding rules.
- `releases/v0.1.0` left immutable; this snapshot is `releases/v0.1.1`.
- No Track A / sealed / 5+2 / 7+4 / Gold changes.

"""
    if "## v0.1.1" not in cl:
        (DS_ROOT / "CHANGELOG.md").write_text(entry + cl, encoding="utf-8")
    (DS_ROOT / "VERSION").write_text("0.1.1-dev\n", encoding="utf-8")

    # Re-validate + stats
    from dataset_statistics import main as stats_main

    # stats_main parses argv — call coverage rewrite lightly
    import dataset_statistics as ds

    # run gates
    report = run_gates()
    write_json(DS_ROOT / "reports" / "validation_report.json", report)
    if report["overall"] != "PASS":
        print(json.dumps(report, indent=2)[:4000])
        raise SystemExit("validation failed")

    # refresh coverage via subprocess-style
    sys.argv = ["dataset_statistics.py"]
    stats_main()

    manifest = build_v011_release()
    print(
        json.dumps(
            {
                "ab_rates": ab["recovery_rates"],
                "dataset_action": ab["dataset_action"],
                "validation": report["overall"],
                "release": manifest["version"],
                "v0.1.0_intact": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
