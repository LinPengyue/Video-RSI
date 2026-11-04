#!/usr/bin/env python3
"""WP1.1: Track-A-facing minimal validation export (engineering patch).

Does not start Track A, mint formal Gold, invent video seconds, or rewrite science.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ENG = Path(__file__).resolve().parent
sys.path.insert(0, str(ENG))
from inference_access import (  # noqa: E402
    WHITELIST_FILENAME,
    build_whitelist_document,
)
from strict_schema import SchemaError, validate_or_raise  # noqa: E402

ROOT = Path(__file__).resolve().parents[5]
PILOT = (
    ROOT
    / "research_audit/lvbench_compositional/track_b/family_level_minimal_validation_pilot_v0.1"
)
NORM = ROOT / "research_audit/lvbench_compositional/track_b/normalized_programs_v1"
OUT = Path(__file__).resolve().parents[1]
VIDEO_ROOTS = [
    Path("/home/descfly/lpy/dataset/LVBench/videos"),
    ROOT / "data" / "lvbench" / "videos",
]

SEEN = ["SP001", "SP002", "SP005", "SP201", "SP202"]
UNSEEN = ["P7_VTCD_C2", "P7_TJR_R3"]
EXPORT_IDS = SEEN + UNSEEN
ALGO = "minimal_validation_export_v1.2.0"

ANSWER_OUTPUT_MARKERS = re.compile(
    r"(^answer$|^answer[_-]|_answer$|final_answer|user_answer)", re.IGNORECASE
)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def yn_to_bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("是", "yes", "true", "y"):
        return True
    if s in ("否", "no", "false", "n"):
        return False
    return None


def detect_language(text: str | None) -> str:
    if not text:
        return "UNKNOWN"
    return "zh" if CJK_RE.search(text) else "en"


def load_inventory() -> dict[str, dict]:
    inv = json.loads((PILOT / "PILOT_INVENTORY.json").read_text())
    return {it["item_id"]: it for it in inv["items"]}


def find_video(video_id: str) -> Path | None:
    for root in VIDEO_ROOTS:
        p = root / f"{video_id}.mp4"
        if p.is_file():
            return p
    return None


def _map_sufficient_fields(src: dict) -> tuple[dict, list[dict]]:
    """Map recorded necessity keys into Track-A authoritative booleans without dropping full_question."""
    mappings: list[dict] = []
    out: dict = {}

    def take(canon: str, *aliases: str):
        if canon in src and src[canon] is not None:
            out[canon] = src[canon]
            return
        for a in aliases:
            if a in src and src[a] is not None:
                out[canon] = src[a]
                mappings.append(
                    {
                        "canonical_field": canon,
                        "mapped_from": a,
                        "value": src[a],
                    }
                )
                return
        out[canon] = None

    take("a_only_sufficient", "a_only_sufficient_full_question")
    take("b_only_sufficient", "b_only_sufficient_full_question")
    # a_plus_b / necessary labels
    if "a_plus_b_necessary" in src and src["a_plus_b_necessary"] is not None:
        out["a_plus_b"] = src["a_plus_b_necessary"]
        mappings.append(
            {
                "canonical_field": "a_plus_b",
                "mapped_from": "a_plus_b_necessary",
                "value": src["a_plus_b_necessary"],
            }
        )
    elif "a_plus_b" in src:
        out["a_plus_b"] = src["a_plus_b"]
    else:
        out["a_plus_b"] = None
    return out, mappings


def necessity_block(item_id: str, inv_it: dict, record: dict | None) -> dict:
    """Provenance retained; Track A must use necessity_authoritative only."""
    provenance: dict = {
        "inventory_single_window_necessity": inv_it.get("single_window_necessity") or {},
    }
    sources = ["PILOT_INVENTORY.single_window_necessity"]
    field_mappings: list[dict] = []

    if record and record.get("composition_necessity"):
        provenance["composition_necessity_label"] = record["composition_necessity"]
        sources.append("provenance_record.composition_necessity")
    if record and record.get("single_window_necessity_audit"):
        provenance["single_window_necessity_audit"] = record[
            "single_window_necessity_audit"
        ]
        sources.append("provenance_record.single_window_necessity_audit")

    hj_raw = None
    if record and isinstance(record.get("human_judgments_preserved"), dict):
        hj_raw = record["human_judgments_preserved"]
    if hj_raw:
        provenance["human_judgments_preserved"] = {
            "a_only_sufficient": yn_to_bool(hj_raw.get("a_only_sufficient")),
            "b_only_sufficient": yn_to_bool(hj_raw.get("b_only_sufficient")),
            "a_plus_b_supports_user_answer": yn_to_bool(
                hj_raw.get("a_plus_b_supports_user_answer")
            ),
            "truly_needs_cross_clip_composition": yn_to_bool(
                hj_raw.get("truly_needs_cross_clip_composition")
            ),
            "raw": hj_raw,
        }
        sources.append("graph_or_record.human_judgments_preserved")

    # Authority priority: original human judgment preserved > record audit > inventory
    conflict = None
    if hj_raw:
        auth = {
            "a_only_sufficient": yn_to_bool(hj_raw.get("a_only_sufficient")),
            "b_only_sufficient": yn_to_bool(hj_raw.get("b_only_sufficient")),
            "a_plus_b": yn_to_bool(hj_raw.get("a_plus_b_supports_user_answer")),
            "cross_clip_necessary": yn_to_bool(
                hj_raw.get("truly_needs_cross_clip_composition")
            ),
            "authority": "human_judgments_preserved",
            "authority_note": (
                "Original human scientific judgment is the sole Track A necessity authority "
                "when present; inventory booleans are provenance only."
            ),
        }
        inv = provenance["inventory_single_window_necessity"]
        inv_mapped, inv_maps = _map_sufficient_fields(inv)
        field_mappings.extend(
            {"source": "inventory", **m} for m in inv_maps
        )
        if inv_mapped.get("a_only_sufficient") is not None and auth[
            "a_only_sufficient"
        ] is not None:
            if bool(inv_mapped["a_only_sufficient"]) != bool(auth["a_only_sufficient"]) or (
                inv_mapped.get("b_only_sufficient") is not None
                and auth["b_only_sufficient"] is not None
                and bool(inv_mapped["b_only_sufficient"]) != bool(auth["b_only_sufficient"])
            ):
                conflict = {
                    "inventory_vs_preserved_conflict": True,
                    "inventory_mapped": inv_mapped,
                    "preserved": {
                        "a_only_sufficient": auth["a_only_sufficient"],
                        "b_only_sufficient": auth["b_only_sufficient"],
                    },
                    "resolution": "USE_human_judgments_preserved_AS_AUTHORITATIVE",
                }
    else:
        # Prefer record audit (SP201/SP202), else inventory
        src = None
        authority = None
        if record and record.get("single_window_necessity_audit"):
            src = record["single_window_necessity_audit"]
            authority = "provenance_record.single_window_necessity_audit"
        else:
            src = provenance["inventory_single_window_necessity"]
            authority = "PILOT_INVENTORY.single_window_necessity"
        mapped, maps = _map_sufficient_fields(src)
        field_mappings.extend({"source": authority, **m} for m in maps)
        # Also record inventory mapping when audit used
        if authority != "PILOT_INVENTORY.single_window_necessity":
            _, inv_maps = _map_sufficient_fields(
                provenance["inventory_single_window_necessity"]
            )
            field_mappings.extend(
                {"source": "PILOT_INVENTORY.single_window_necessity", **m}
                for m in inv_maps
            )
        def coerce_sufficient(v):
            if isinstance(v, bool):
                return v
            b = yn_to_bool(v)
            if b is not None:
                return b
            if isinstance(v, str) and "INSUFFICIENT" in v.upper():
                return False
            return None

        a_bool = coerce_sufficient(mapped.get("a_only_sufficient"))
        b_bool = coerce_sufficient(mapped.get("b_only_sufficient"))
        auth = {
            "a_only_sufficient": a_bool,
            "b_only_sufficient": b_bool,
            "a_plus_b": mapped.get("a_plus_b"),
            "cross_clip_necessary": None
            if mapped.get("a_plus_b") is None
            else True,  # compositional pilot items record A+B support
            "authority": authority,
            "authority_note": (
                "Mapped a_only_sufficient_full_question / b_only_sufficient_full_question "
                "onto Track A canonical fields when those were the recorded keys."
            ),
            "source_field_mappings": maps,
        }

    return {
        "status": "RECORDED_FROM_SCIENTIFIC_SOURCES",
        "not_model_ablation": True,
        "necessity_authoritative": auth,
        # backward-compatible alias used by prior consumers — identical to authoritative
        "primary": {
            "a_only_sufficient": auth["a_only_sufficient"],
            "b_only_sufficient": auth["b_only_sufficient"],
            "a_plus_b": auth.get("a_plus_b"),
            "cross_clip_necessary": auth.get("cross_clip_necessary"),
            "authority": auth["authority"],
        },
        "provenance_records": provenance,
        "field_mappings": field_mappings,
        "conflict": conflict,
        "sources": sources,
    }


def windows_block(item_id: str, inv_it: dict, record: dict | None) -> dict:
    wins = None
    source = None
    if record and record.get("windows_seconds"):
        wins = record["windows_seconds"]
        source = "provenance_record.windows_seconds"
    if wins is None and inv_it.get("windows_seconds"):
        wins = inv_it["windows_seconds"]
        source = "PILOT_INVENTORY.windows_seconds"

    # Approved-source search notes (do not promote unapproved offsets)
    approved_search = {
        "checked_sources": [
            "provenance_record.windows_seconds",
            "PILOT_INVENTORY.windows_seconds",
            "p4_scientific_review_pack/REVIEW_PACK.json",
            "precise_timing_status on approved graph",
        ],
        "non_authoritative_candidates_not_promoted": [],
    }
    # Blind-packet clip filenames encode engineering extract ranges — not approved source seconds
    bp = PILOT / "provenance_snapshots" / f"{item_id}_blind_packet.json"
    if bp.is_file():
        approved_search["non_authoritative_candidates_not_promoted"].append(
            {
                "source": str(bp.relative_to(ROOT)),
                "reason": (
                    "Review-media clip filenames may embed numeric ranges; these are not "
                    "scientifically approved source-second A/B windows."
                ),
            }
        )
    if record and record.get("precise_timing_status"):
        approved_search["precise_timing_status"] = record["precise_timing_status"]

    review_pack = (
        PILOT / "p4_scientific_review_pack" / "REVIEW_PACK.json"
    )
    if review_pack.is_file():
        rp = json.loads(review_pack.read_text())
        for row in (
            rp.get("pilot_items_for_review")
            or rp.get("items")
            or rp.get("review_items")
            or []
        ):
            if row.get("item_id") == item_id:
                approved_search["review_pack_windows_seconds"] = row.get(
                    "windows_seconds"
                )
                break

    if wins:
        return {
            "status": "RECORDED_SOURCE_SECONDS",
            "A": {"t_start_s": wins["A"][0], "t_end_s": wins["A"][1]},
            "B": {"t_start_s": wins["B"][0], "t_end_s": wins["B"][1]},
            "time_base": "source_video_seconds",
            "precision": "AS_RECORDED_IN_SCIENTIFIC_REVIEW_NOT_REVERIFIED_HERE",
            "source": source,
            "evaluation_gates": {
                "fixed_ab_window_eval": "AVAILABLE_FROM_RECORDED_SECONDS",
                "block_reason": None,
            },
            "approved_source_search": approved_search,
        }

    return {
        "status": "UNKNOWN_PENDING_SOURCE_SECOND_MAPPING",
        "A": None,
        "B": None,
        "window_roles": inv_it.get("window_roles"),
        "windows_note": inv_it.get("windows_note")
        or "Precise source-second mapping not available in authoritative export sources",
        "time_base": "UNKNOWN",
        "do_not_infer_from_program_graph": True,
        "evaluation_gates": {
            "fixed_ab_window_eval": "BLOCKED",
            "block_reason": (
                "No scientifically approved source-second A/B mapping; fixed A/B window "
                "evaluation must not run for this item."
            ),
        },
        "approved_source_search": approved_search,
    }


def answer_block(inv_it: dict, record: dict | None) -> dict:
    ans = inv_it.get("answer_reference")
    hist = None
    if record and record.get("historical_answer") is not None:
        hist = record["historical_answer"]
    if hist is None and record and record.get("answer_candidate") is not None:
        hist = record["answer_candidate"]
    text = hist if hist is not None else ans
    return {
        "answer_text": text,
        "answer_certification_status": "HUMAN_REFERENCE_OR_HISTORICAL_NOT_FORMAL_GOLD",
        "formal_gold": False,
        "formal_gold_note": "Export must not treat this as certified Gold.",
        "sources": [
            s
            for s in [
                "provenance_record.historical_answer" if hist is not None else None,
                "PILOT_INVENTORY.answer_reference",
            ]
            if s
        ],
    }


def build_qa_items(inv: dict[str, dict]) -> list[dict]:
    items = []
    for item_id in EXPORT_IDS:
        inv_it = inv[item_id]
        rec_path = PILOT / "provenance_snapshots" / f"{item_id}.json"
        record = json.loads(rec_path.read_text()) if rec_path.is_file() else None
        q = inv_it.get("question_open")
        if record and record.get("original_question"):
            q = record["original_question"]
        if record and record.get("question_original_en") and not q:
            q = record["question_original_en"]
        if not q and item_id.startswith("P7_"):
            bp = PILOT / "provenance_snapshots" / f"{item_id}_blind_packet.json"
            if bp.is_file():
                q = json.loads(bp.read_text()).get("frozen_question")
        lang = detect_language(q)
        items.append(
            {
                "item_id": item_id,
                "qa_uid": inv_it.get("qa_uid"),
                "video_id": inv_it.get("video_id")
                or (record or {}).get("video_id"),
                "split_role_pilot": inv_it.get("pilot_role"),
                "question_text": q,
                "question_language": lang,
                "qa_format": inv_it.get("qa_format") or "OPEN_ENDED",
                "answer": answer_block(inv_it, record),
                "windows": windows_block(item_id, inv_it, record),
                "necessity": necessity_block(item_id, inv_it, record),
                "provenance": {
                    "inventory_path": str(
                        (PILOT / "PILOT_INVENTORY.json").relative_to(ROOT)
                    ),
                    "record_path": str(rec_path.relative_to(ROOT))
                    if rec_path.is_file()
                    else None,
                    "graph_version": inv_it.get("graph_version"),
                    "scientific_approval_source": inv_it.get(
                        "scientific_approval_source"
                    ),
                },
                "gates": {
                    "formal_seen_train": bool(inv_it.get("formal_seen_train")),
                    "formal_unseen": bool(inv_it.get("formal_unseen")),
                    "formal_gold": bool(inv_it.get("formal_gold")),
                    "train_exposed": bool(inv_it.get("train_exposed")),
                    "approve_expensive_track_a_rsi": bool(
                        inv_it.get("approve_expensive_track_a_rsi")
                    ),
                },
            }
        )
    return items


def build_program_graphs() -> list[dict]:
    out = []
    for item_id in EXPORT_IDS:
        g = json.loads((NORM / "graphs" / f"{item_id}.json").read_text())
        nodes = []
        for n in g["nodes"]:
            nodes.append(
                {
                    "node_id": n["node_id"],
                    "raw_operator": n.get("raw_operator"),
                    "layer1": n.get("layer1"),
                    "layer2": n.get("layer2"),
                    "raw_inputs": n.get("raw_inputs"),
                    "raw_outputs": n.get("raw_outputs"),
                    "normalized_inputs": n.get("normalized_inputs"),
                    "normalized_outputs": n.get("normalized_outputs"),
                    "raw_clip_role": n.get("raw_clip_role"),
                    "normalized_clip_role": n.get("normalized_clip_role"),
                    "raw_time_conditions": n.get("raw_time_conditions"),
                    "raw_evidence": n.get("raw_evidence"),
                    "evidence_certification": n.get("evidence_certification"),
                    "provenance": n.get("provenance"),
                }
            )
        edges = [
            {
                "edge_id": e.get("edge_id"),
                "from_node": e["from_node"],
                "to_node": e["to_node"],
                "raw_dependency_kind": e.get("raw_dependency_kind"),
                "normalized_dependency_kind": e.get("normalized_dependency_kind"),
                "provenance": e.get("provenance"),
            }
            for e in g["edges"]
        ]
        out.append(
            {
                "item_id": item_id,
                "graph_id": g.get("graph_id", item_id),
                "normalization_status": g.get("normalization_status"),
                "split_role_fixed": g.get("split_role_fixed"),
                "n_nodes": g["n_nodes"],
                "n_edges": g["n_edges"],
                "nodes": nodes,
                "edges": edges,
                "source": g.get("source"),
                "evidence_disclaimer": (
                    "Chat-approved sidecars / structured P7 graphs are NOT frame-level "
                    "video certification. evidence_certification fields must be respected."
                ),
                "normalized_graph_path": str(
                    (NORM / "graphs" / f"{item_id}.json").relative_to(ROOT)
                ),
            }
        )
    return out


def build_video_manifest(qa_items: list[dict]) -> list[dict]:
    videos: dict[str, list[str]] = {}
    for qa in qa_items:
        videos.setdefault(qa["video_id"], []).append(qa["item_id"])
    rows = []
    for video_id, item_ids in sorted(videos.items()):
        path = find_video(video_id)
        local_fp = None
        if path is not None:
            local_fp = {
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "status": "ENGINEERING_LOCAL_FINGERPRINT_NOT_DATASET_AUTHORITY",
            }
        rows.append(
            {
                "video_id": video_id,
                "source_dataset": "LVBench",
                "source_note": "Original LVBench video assets used by Track B pilot",
                "accessible_uri_or_path": str(path) if path else None,
                "access_status": "LOCAL_PATH_RESOLVED" if path else "PATH_UNKNOWN",
                "time_base": "source_video_seconds",
                "video_sha256_scientific": "UNKNOWN",
                "evidence_sha256_scientific": "UNKNOWN",
                "local_engineering_fingerprint": local_fp,
                "used_by_item_ids": item_ids,
                "limitations": [
                    "Scientific content hash not present in Track B provenance → UNKNOWN",
                    "Local fingerprint (if any) is engineering-only, not a Gold/media authority claim",
                ],
            }
        )
    return rows


def build_split_manifest(inv: dict[str, dict], graphs: list[dict]) -> dict:
    g_by = {g["item_id"]: g for g in graphs}
    rows = []
    for item_id in EXPORT_IDS:
        inv_it = inv[item_id]
        g = g_by[item_id]
        layer1 = sorted({n["layer1"] for n in g["nodes"] if n.get("layer1")})
        layer2 = sorted({n["layer2"] for n in g["nodes"] if n.get("layer2")})
        rows.append(
            {
                "item_id": item_id,
                "pilot_role": "SEEN" if item_id in SEEN else "UNSEEN",
                "formal_seen_train": False,
                "formal_unseen": False,
                "formal_gold": False,
                "train_exposed": bool(inv_it.get("train_exposed")),
                "approve_expensive_track_a_rsi": bool(
                    inv_it.get("approve_expensive_track_a_rsi")
                ),
                "structure_labels": {
                    "capability_families_upper_inventory": inv_it.get(
                        "capability_families_upper"
                    ),
                    "layer1_families_normalized": layer1,
                    "layer2_atoms_normalized": layer2,
                    "n_nodes": g["n_nodes"],
                    "n_edges": g["n_edges"],
                },
                "training_exposure_limits": {
                    "may_use_as_formal_train": False,
                    "may_claim_formal_unseen": False,
                    "may_claim_formal_gold": False,
                    "track_a_use": "MINIMAL_VALIDATION_ONLY",
                    "note": (
                        "Pilot Seen/Unseen roles are fixed for this export; they are not "
                        "formal Seen/Unseen promotions."
                    ),
                },
            }
        )
    return {
        "schema": "minimal_validation_split_manifest_v1",
        "algo_version": ALGO,
        "fixed_seen": SEEN,
        "fixed_unseen": UNSEEN,
        "candidate_excluded_from_this_export": [
            "A",
            "B",
            "P7_R4_F1",
            "P7_R4_F2",
            "SP205",
        ],
        "items": rows,
    }


def _is_answer_bearing_output(token: str | None) -> bool:
    if not token or not isinstance(token, str):
        return False
    return bool(ANSWER_OUTPUT_MARKERS.search(token.strip()))


def redact_graph_for_inference(graph: dict) -> dict:
    """Strip answer-bearing I/O and human gold-like evidence payloads."""
    nodes = []
    for n in graph["nodes"]:
        raw_out = n.get("raw_outputs") or []
        norm_out = n.get("normalized_outputs") or []
        answer_bearing = any(_is_answer_bearing_output(x) for x in list(raw_out) + list(norm_out))
        node = {
            "node_id": n["node_id"],
            "raw_operator": n.get("raw_operator"),
            "layer1": n.get("layer1"),
            "layer2": n.get("layer2"),
            "raw_inputs": n.get("raw_inputs"),
            "normalized_inputs": n.get("normalized_inputs"),
            "raw_clip_role": n.get("raw_clip_role"),
            "normalized_clip_role": n.get("normalized_clip_role"),
            "raw_time_conditions": n.get("raw_time_conditions"),
            "evidence_certification": n.get("evidence_certification"),
            "provenance": n.get("provenance"),
            "outputs_redacted": True if answer_bearing else False,
        }
        if answer_bearing:
            node["raw_outputs"] = ["__REDACTED_ANSWER_BEARING__"]
            node["normalized_outputs"] = ["__REDACTED_ANSWER_BEARING__"]
            node["raw_evidence"] = {"status": "REDACTED_ANSWER_OR_GOLD_LIKE"}
        else:
            # Still strip rich evidence payloads that can encode gold-like facts
            node["raw_outputs"] = n.get("raw_outputs")
            node["normalized_outputs"] = n.get("normalized_outputs")
            ev = n.get("raw_evidence")
            if isinstance(ev, dict) and any(
                k in ev for k in ("on_screen_text", "answer", "label", "human_note")
            ):
                node["raw_evidence"] = {
                    "status": "REDACTED_HUMAN_EVIDENCE_PAYLOAD",
                    "keys_present": sorted(ev.keys()),
                }
            else:
                node["raw_evidence"] = None
        nodes.append(node)
    return {
        "item_id": graph["item_id"],
        "graph_id": graph["graph_id"],
        "normalization_status": graph["normalization_status"],
        "split_role_fixed": graph["split_role_fixed"],
        "n_nodes": graph["n_nodes"],
        "n_edges": graph["n_edges"],
        "nodes": nodes,
        "edges": graph["edges"],
        "inference_safe_note": (
            "Answer-bearing outputs and human evidence payloads redacted. "
            "Unseen original graphs are omitted entirely from this projection."
        ),
    }


def redact_split_for_inference(split: dict) -> dict:
    """Keep Seen structure labels; strip Unseen operator sets / node-edge counts."""
    items = []
    for row in split["items"]:
        out = {
            "item_id": row["item_id"],
            "pilot_role": row["pilot_role"],
            "formal_seen_train": row["formal_seen_train"],
            "formal_unseen": row["formal_unseen"],
            "formal_gold": row["formal_gold"],
            "train_exposed": row["train_exposed"],
            "approve_expensive_track_a_rsi": row.get("approve_expensive_track_a_rsi"),
            "training_exposure_limits": row["training_exposure_limits"],
        }
        if row["item_id"] in UNSEEN or row.get("pilot_role") == "UNSEEN":
            out["structure_labels"] = {
                "status": "WITHHELD_FROM_INFERENCE",
                "reason": (
                    "Unseen Layer1/Layer2 operator sets, node counts, and edge counts "
                    "are scorer/scientific-audit only; not visible to ordinary inference."
                ),
            }
        else:
            out["structure_labels"] = row.get("structure_labels")
        items.append(out)
    return {
        "schema": "minimal_validation_inference_safe_split_manifest_v1",
        "algo_version": ALGO,
        "fixed_seen": list(split["fixed_seen"]),
        "fixed_unseen": list(split["fixed_unseen"]),
        "candidate_excluded_from_this_export": list(
            split.get("candidate_excluded_from_this_export") or []
        ),
        "items": items,
        "structure_policy": {
            "seen_structure_labels": "VISIBLE",
            "unseen_structure_labels": "WITHHELD",
        },
    }


def build_projections(qa, graphs, videos, split) -> dict:
    """Full scientific pack stays at package root; projections are isolated."""
    answers = []
    eval_private = []
    inf_qa = []
    for q in qa:
        answers.append(
            {
                "item_id": q["item_id"],
                "qa_uid": q["qa_uid"],
                "video_id": q["video_id"],
                "answer_text": q["answer"]["answer_text"],
                "answer_certification_status": q["answer"][
                    "answer_certification_status"
                ],
                "formal_gold": False,
                "windows": q["windows"],
                "necessity_authoritative": q["necessity"]["necessity_authoritative"],
                "access": "SCORER_PRIVATE_ONLY",
            }
        )
        eval_private.append(
            {
                "item_id": q["item_id"],
                "qa_uid": q["qa_uid"],
                "necessity_authoritative": q["necessity"]["necessity_authoritative"],
                "necessity_provenance_conflict": q["necessity"].get("conflict"),
                "windows_evaluation_gates": q["windows"].get("evaluation_gates"),
                "access": "SCORER_PRIVATE_EVAL_METADATA_ONLY",
            }
        )
        inf_qa.append(
            {
                "item_id": q["item_id"],
                "qa_uid": q["qa_uid"],
                "video_id": q["video_id"],
                "split_role_pilot": q["split_role_pilot"],
                "question_text": q["question_text"],
                "question_language": q["question_language"],
                "qa_format": q["qa_format"],
                "windows": {
                    "status": q["windows"]["status"],
                    "A": q["windows"].get("A"),
                    "B": q["windows"].get("B"),
                    "time_base": q["windows"].get("time_base"),
                    "evaluation_gates": q["windows"].get("evaluation_gates"),
                    "do_not_infer_from_program_graph": q["windows"].get(
                        "do_not_infer_from_program_graph"
                    ),
                },
                # Human A-only/B-only necessity is scorer-private (WP1.2).
                "necessity": {
                    "status": "WITHHELD_SCORER_PRIVATE",
                    "note": "necessity_authoritative lives in projections/scorer_private/",
                },
                "gates": q["gates"],
                "answer": {
                    "status": "WITHHELD_INFERENCE_SAFE",
                    "formal_gold": False,
                },
            }
        )

    # Seen graphs only, redacted; Unseen graphs omitted
    seen_graphs = [
        redact_graph_for_inference(g) for g in graphs if g["item_id"] in SEEN
    ]
    inf_split = redact_split_for_inference(split)
    whitelist = build_whitelist_document(ALGO)
    return {
        "inference_safe": {
            "qa_items": {
                "schema": "minimal_validation_inference_safe_qa_v1",
                "algo_version": ALGO,
                "access": "TRACK_A_INFERENCE_ALLOWED",
                "items": inf_qa,
                "forbidden": [
                    "reference_answers",
                    "answer_bearing_graph_outputs",
                    "human_gold_like_evidence_payloads",
                    "unseen_original_program_graphs",
                    "unseen_structure_labels_operator_sets",
                    "necessity_authoritative_human_labels",
                ],
            },
            "program_graphs_seen_redacted": {
                "schema": "minimal_validation_inference_safe_graphs_v1",
                "algo_version": ALGO,
                "access": "TRACK_A_INFERENCE_ALLOWED_SEEN_ONLY",
                "unseen_graphs_policy": "OMITTED_NOT_FOR_INFERENCE",
                "omitted_unseen_item_ids": UNSEEN,
                "n_graphs": len(seen_graphs),
                "graphs": seen_graphs,
            },
            "video_manifest": {
                "schema": "minimal_validation_video_manifest_v1",
                "algo_version": ALGO,
                "videos": videos,
            },
            "split_manifest": inf_split,
            "whitelist": whitelist,
            "ACCESS.md": (
                "# Inference-safe projection\n\n"
                "Ordinary Track A inference may read **only** paths listed in "
                f"`{WHITELIST_FILENAME}`, opened via `eng/inference_access.py`.\n\n"
                "Must NOT contain: reference answers, answer-bearing graph outputs, "
                "human Gold-like evidence payloads, Unseen original program graphs, "
                "Unseen structure/operator/size labels, or human necessity_authoritative.\n"
                "Do not rely on this markdown alone — enforce the whitelist.\n"
                "Oracle-program experiment scope is NOT decided by this export.\n"
            ),
        },
        "scorer_private": {
            "answers": {
                "schema": "minimal_validation_scorer_private_answers_v1",
                "algo_version": ALGO,
                "access": "SCORER_PRIVATE_ONLY_NOT_FOR_INFERENCE",
                "formal_gold": False,
                "items": answers,
            },
            "eval_private_metadata": {
                "schema": "minimal_validation_scorer_private_eval_metadata_v1",
                "algo_version": ALGO,
                "access": "SCORER_PRIVATE_ONLY_NOT_FOR_INFERENCE",
                "items": eval_private,
                "note": (
                    "Human necessity_authoritative (A-only/B-only/cross-clip) is "
                    "evaluation-private; ordinary inference must not preload it."
                ),
            },
            "ACCESS.md": (
                "# Scorer-private projection\n\n"
                "Reference answers, necessity_authoritative, and eval metadata. "
                "Must not be mounted into ordinary Track A inference.\n"
                "Answers remain HUMAN_REFERENCE_OR_HISTORICAL_NOT_FORMAL_GOLD.\n"
            ),
        },
    }


def build_schemas() -> dict[str, dict]:
    window_schema = {
        "type": "object",
        "required": ["status", "evaluation_gates"],
        "properties": {
            "status": {
                "type": "string",
                "enum": [
                    "RECORDED_SOURCE_SECONDS",
                    "UNKNOWN_PENDING_SOURCE_SECOND_MAPPING",
                ],
            },
            "A": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "required": ["t_start_s", "t_end_s"],
                        "properties": {
                            "t_start_s": {"type": "number"},
                            "t_end_s": {"type": "number"},
                        },
                    },
                ]
            },
            "B": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "required": ["t_start_s", "t_end_s"],
                        "properties": {
                            "t_start_s": {"type": "number"},
                            "t_end_s": {"type": "number"},
                        },
                    },
                ]
            },
            "evaluation_gates": {
                "type": "object",
                "required": ["fixed_ab_window_eval"],
                "properties": {
                    "fixed_ab_window_eval": {"type": "string"},
                    "block_reason": {"type": ["string", "null"]},
                },
            },
        },
    }
    necessity_schema = {
        "type": "object",
        "required": ["necessity_authoritative", "provenance_records"],
        "properties": {
            "necessity_authoritative": {
                "type": "object",
                "required": [
                    "a_only_sufficient",
                    "b_only_sufficient",
                    "authority",
                ],
                "properties": {
                    "a_only_sufficient": {"type": ["boolean", "null"]},
                    "b_only_sufficient": {"type": ["boolean", "null"]},
                    "authority": {"type": "string", "minLength": 1},
                },
            },
            "provenance_records": {"type": "object"},
        },
    }
    return {
        "qa_items.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["schema", "algo_version", "items", "n_items"],
            "properties": {
                "schema": {"const": "minimal_validation_qa_items_v1"},
                "algo_version": {"type": "string"},
                "n_items": {"type": "integer", "const": 7},
                "items": {
                    "type": "array",
                    "minItems": 7,
                    "maxItems": 7,
                    "items": {
                        "type": "object",
                        "required": [
                            "item_id",
                            "qa_uid",
                            "video_id",
                            "question_text",
                            "question_language",
                            "answer",
                            "windows",
                            "necessity",
                            "gates",
                        ],
                        "properties": {
                            "item_id": {"type": "string", "minLength": 1},
                            "qa_uid": {"type": "string", "minLength": 1},
                            "video_id": {"type": "string", "minLength": 1},
                            "question_text": {"type": "string", "minLength": 1},
                            "question_language": {
                                "type": "string",
                                "enum": ["en", "zh", "UNKNOWN"],
                            },
                            "answer": {
                                "type": "object",
                                "required": [
                                    "answer_text",
                                    "answer_certification_status",
                                    "formal_gold",
                                ],
                                "properties": {
                                    "formal_gold": {"const": False},
                                    "answer_certification_status": {
                                        "const": "HUMAN_REFERENCE_OR_HISTORICAL_NOT_FORMAL_GOLD"
                                    },
                                },
                            },
                            "windows": window_schema,
                            "necessity": necessity_schema,
                            "gates": {
                                "type": "object",
                                "required": [
                                    "formal_seen_train",
                                    "formal_unseen",
                                    "formal_gold",
                                    "train_exposed",
                                ],
                                "properties": {
                                    "formal_gold": {"const": False},
                                    "formal_seen_train": {"type": "boolean"},
                                    "formal_unseen": {"type": "boolean"},
                                    "train_exposed": {"type": "boolean"},
                                },
                            },
                        },
                    },
                },
            },
        },
        "program_graphs.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["schema", "graphs", "n_graphs"],
            "properties": {
                "schema": {"const": "minimal_validation_program_graphs_v1"},
                "n_graphs": {"type": "integer", "const": 7},
                "graphs": {
                    "type": "array",
                    "minItems": 7,
                    "maxItems": 7,
                    "items": {
                        "type": "object",
                        "required": [
                            "item_id",
                            "graph_id",
                            "nodes",
                            "edges",
                            "n_nodes",
                            "n_edges",
                        ],
                        "properties": {
                            "item_id": {"type": "string"},
                            "graph_id": {"type": "string"},
                            "n_nodes": {"type": "integer", "minimum": 1},
                            "n_edges": {"type": "integer", "minimum": 0},
                            "nodes": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "object",
                                    "required": ["node_id"],
                                    "properties": {
                                        "node_id": {"type": "string", "minLength": 1}
                                    },
                                },
                            },
                            "edges": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["from_node", "to_node"],
                                    "properties": {
                                        "from_node": {"type": "string"},
                                        "to_node": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "video_manifest.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["schema", "videos"],
            "properties": {
                "schema": {"const": "minimal_validation_video_manifest_v1"},
                "videos": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": [
                            "video_id",
                            "source_dataset",
                            "time_base",
                            "video_sha256_scientific",
                            "used_by_item_ids",
                        ],
                        "properties": {
                            "video_id": {"type": "string", "minLength": 1},
                            "video_sha256_scientific": {"type": "string"},
                            "used_by_item_ids": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "split_manifest.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["schema", "fixed_seen", "fixed_unseen", "items"],
            "properties": {
                "schema": {"const": "minimal_validation_split_manifest_v1"},
                "fixed_seen": {
                    "type": "array",
                    "minItems": 5,
                    "maxItems": 5,
                    "items": {"type": "string"},
                },
                "fixed_unseen": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 2,
                    "items": {"type": "string"},
                },
                "items": {
                    "type": "array",
                    "minItems": 7,
                    "maxItems": 7,
                    "items": {
                        "type": "object",
                        "required": [
                            "item_id",
                            "pilot_role",
                            "formal_seen_train",
                            "formal_unseen",
                            "formal_gold",
                            "train_exposed",
                            "training_exposure_limits",
                        ],
                        "properties": {
                            "formal_gold": {"const": False},
                            "formal_seen_train": {"const": False},
                            "formal_unseen": {"const": False},
                            "training_exposure_limits": {
                                "type": "object",
                                "required": [
                                    "may_use_as_formal_train",
                                    "may_claim_formal_unseen",
                                    "may_claim_formal_gold",
                                ],
                                "properties": {
                                    "may_use_as_formal_train": {"const": False},
                                    "may_claim_formal_unseen": {"const": False},
                                    "may_claim_formal_gold": {"const": False},
                                },
                            },
                        },
                    },
                },
            },
        },
    }


def run_schema_validation(docs: dict[str, dict], schemas: dict[str, dict]) -> dict:
    """Strict schema validation. SKIPPED ⇒ overall cannot be PASS."""
    engine = None
    lib_errors: list[dict] = []
    try:
        import jsonschema  # type: ignore

        engine = f"jsonschema_library:{getattr(jsonschema, '__version__', 'unknown')}"
        for name, doc in docs.items():
            try:
                jsonschema.validate(doc, schemas[name])
            except Exception as e:  # noqa: BLE001
                lib_errors.append({"schema": name, "error": str(e)})
        if not lib_errors:
            return {"status": "PASS", "engine": engine, "errors": []}
        # fall through to builtin for detail, but keep FAIL
    except ImportError:
        engine = None

    builtin_errors: list[dict] = []
    for name, doc in docs.items():
        try:
            validate_or_raise(doc, schemas[name])
        except SchemaError as e:
            builtin_errors.append(
                {"schema": name, "path": e.path, "error": e.message}
            )
    if engine is None:
        engine = "builtin_draft2020_12_subset"
    if lib_errors:
        return {
            "status": "FAIL",
            "engine": engine,
            "errors": lib_errors + builtin_errors,
            "note": "jsonschema library reported failures",
        }
    if builtin_errors:
        return {"status": "FAIL", "engine": engine, "errors": builtin_errors}
    return {"status": "PASS", "engine": engine, "errors": []}


def uniqueness_and_join_checks(qa, graphs, videos, split) -> list[dict]:
    issues: list[dict] = []
    qa_ids = [x["item_id"] for x in qa]
    g_ids = [x["item_id"] for x in graphs]
    s_ids = [x["item_id"] for x in split["items"]]
    if qa_ids != EXPORT_IDS or g_ids != EXPORT_IDS or s_ids != EXPORT_IDS:
        issues.append(
            {"code": "ID_ORDER_OR_SET_MISMATCH", "qa": qa_ids, "graphs": g_ids, "split": s_ids}
        )
    if len(set(qa_ids)) != len(qa_ids):
        issues.append({"code": "DUPLICATE_ITEM_ID_QA"})
    if len(set(g_ids)) != len(g_ids):
        issues.append({"code": "DUPLICATE_ITEM_ID_GRAPHS"})
    qa_uids = [x["qa_uid"] for x in qa]
    if len(set(qa_uids)) != len(qa_uids):
        issues.append({"code": "DUPLICATE_QA_UID", "qa_uids": qa_uids})
    vid_ids = [v["video_id"] for v in videos]
    if len(set(vid_ids)) != len(vid_ids):
        issues.append({"code": "DUPLICATE_VIDEO_ID"})

    vid_set = {v["video_id"] for v in videos}
    for q in qa:
        if not q.get("video_id") or q["video_id"] not in vid_set:
            issues.append(
                {
                    "code": "QA_VIDEO_JOIN_FAIL",
                    "item_id": q["item_id"],
                    "video_id": q.get("video_id"),
                }
            )
        if not q.get("question_text"):
            issues.append({"code": "MISSING_QUESTION", "item_id": q["item_id"]})
        if q["answer"].get("formal_gold") is True:
            issues.append({"code": "FALSE_GOLD", "item_id": q["item_id"]})
        if q["answer"]["answer_certification_status"] == "FORMAL_GOLD":
            issues.append({"code": "FALSE_GOLD_STATUS", "item_id": q["item_id"]})
        auth = q["necessity"]["necessity_authoritative"]
        if q["item_id"] in ("SP201", "SP202"):
            if auth.get("a_only_sufficient") is None or auth.get("b_only_sufficient") is None:
                issues.append(
                    {
                        "code": "SP201_SP202_NECESSITY_NULL",
                        "item_id": q["item_id"],
                        "auth": auth,
                    }
                )
        if q["item_id"] in UNSEEN:
            if auth.get("authority") != "human_judgments_preserved":
                issues.append(
                    {
                        "code": "P7_AUTHORITY_NOT_HUMAN_JUDGMENT",
                        "item_id": q["item_id"],
                        "authority": auth.get("authority"),
                    }
                )
            if q["windows"]["evaluation_gates"]["fixed_ab_window_eval"] != "BLOCKED":
                issues.append(
                    {
                        "code": "P7_WINDOW_EVAL_NOT_BLOCKED",
                        "item_id": q["item_id"],
                    }
                )

    for g in graphs:
        node_ids = [n["node_id"] for n in g["nodes"]]
        if len(set(node_ids)) != len(node_ids):
            issues.append({"code": "DUPLICATE_NODE_ID", "item_id": g["item_id"]})
        nset = set(node_ids)
        for e in g["edges"]:
            if e["from_node"] not in nset or e["to_node"] not in nset:
                issues.append(
                    {"code": "GRAPH_EDGE_JOIN_FAIL", "item_id": g["item_id"], "edge": e}
                )
        if g["n_nodes"] != len(g["nodes"]) or g["n_edges"] != len(g["edges"]):
            issues.append({"code": "GRAPH_COUNT_MISMATCH", "item_id": g["item_id"]})
        if g["normalization_status"] == "CHAT_APPROVED_SIDECAR_INGESTED":
            for n in g["nodes"]:
                if n.get("evidence_certification") == "FRAME_CERTIFIED":
                    issues.append(
                        {
                            "code": "FALSE_FRAME_CERT",
                            "item_id": g["item_id"],
                            "node": n["node_id"],
                        }
                    )
    return issues


def leak_scan_inference_safe(proj_root: Path, answers: list[dict]) -> list[dict]:
    issues: list[dict] = []
    answer_texts = {
        str(a["answer_text"]).strip()
        for a in answers
        if a.get("answer_text") is not None and str(a["answer_text"]).strip()
    }
    # Scan all files under inference_safe
    for path in proj_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".json", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(proj_root))
        for ans in answer_texts:
            # numeric-only answers are weak leak signals; still flag exact JSON string form
            if len(ans) <= 1:
                needle = json.dumps(ans, ensure_ascii=False)
                if needle in text and '"answer_text"' in text:
                    issues.append(
                        {
                            "code": "ANSWER_LEAK",
                            "file": rel,
                            "answer": ans,
                        }
                    )
            elif ans in text:
                issues.append({"code": "ANSWER_LEAK", "file": rel, "answer": ans})
        for uid in UNSEEN:
            if f'"item_id": "{uid}"' in text and "program_graphs" in rel:
                # Unseen may appear in qa_items / split; not in graphs file
                if "graphs" in text and '"nodes"' in text:
                    issues.append(
                        {"code": "UNSEEN_GRAPH_LEAK", "file": rel, "item_id": uid}
                    )
        if path.suffix == ".json":
            if '"necessity_authoritative"' in text or '"a_only_sufficient"' in text:
                issues.append(
                    {
                        "code": "NECESSITY_LABEL_LEAK",
                        "file": rel,
                        "note": "Human necessity labels must stay scorer-private",
                    }
                )
            if '"b_only_sufficient"' in text:
                issues.append({"code": "NECESSITY_LABEL_LEAK", "file": rel})
        if "__REDACTED" not in text:
            if re.search(r'"raw_outputs"\s*:\s*\[[^\]]*"answer"', text):
                issues.append({"code": "ANSWER_OUTPUT_LEAK", "file": rel})
            if '"on_screen_text"' in text:
                issues.append({"code": "GOLD_LIKE_EVIDENCE_LEAK", "file": rel})
    # Explicit: unseen graphs file must omit
    gpath = proj_root / "program_graphs_seen_redacted.json"
    if gpath.is_file():
        gdoc = json.loads(gpath.read_text())
        present = {g["item_id"] for g in gdoc.get("graphs", [])}
        for uid in UNSEEN:
            if uid in present:
                issues.append({"code": "UNSEEN_GRAPH_PRESENT", "item_id": uid})
        for gid in SEEN:
            if gid not in present:
                issues.append(
                    {"code": "SEEN_GRAPH_MISSING_IN_INFERENCE_SAFE", "item_id": gid}
                )
    # Unseen structure labels must be withheld in inference split
    spath = proj_root / "split_manifest.json"
    if spath.is_file():
        sdoc = json.loads(spath.read_text())
        for row in sdoc.get("items") or []:
            if row.get("item_id") not in UNSEEN and row.get("pilot_role") != "UNSEEN":
                continue
            labels = row.get("structure_labels") or {}
            if labels.get("status") != "WITHHELD_FROM_INFERENCE":
                issues.append(
                    {
                        "code": "UNSEEN_STRUCTURE_LABEL_LEAK",
                        "item_id": row.get("item_id"),
                        "structure_labels": labels,
                    }
                )
            leak_keys = (
                "layer1_families_normalized",
                "layer2_atoms_normalized",
                "n_nodes",
                "n_edges",
                "capability_families_upper_inventory",
            )
            if any(k in labels for k in leak_keys):
                issues.append(
                    {
                        "code": "UNSEEN_STRUCTURE_OPERATOR_OR_SIZE_LEAK",
                        "item_id": row.get("item_id"),
                        "keys": [k for k in leak_keys if k in labels],
                    }
                )
    # Whitelist must exist and deny parent escapes conceptually
    wpath = proj_root / WHITELIST_FILENAME
    if not wpath.is_file():
        issues.append({"code": "MISSING_INFERENCE_WHITELIST"})
    else:
        wl = json.loads(wpath.read_text())
        allowed = set(wl.get("allowed_relative_paths") or [])
        for denied in (
            "../scorer_private/answers.json",
            "../../qa_items.json",
            "../../program_graphs.json",
        ):
            if denied in allowed:
                issues.append(
                    {"code": "WHITELIST_ALLOWS_DENIED_PATH", "path": denied}
                )
    return issues


def build_necessity_diff(qa: list[dict]) -> dict:
    rows = []
    for q in qa:
        nec = q["necessity"]
        auth = nec["necessity_authoritative"]
        inv = nec["provenance_records"].get("inventory_single_window_necessity") or {}
        inv_mapped, _ = _map_sufficient_fields(inv)
        rows.append(
            {
                "item_id": q["item_id"],
                "authoritative": auth,
                "inventory_raw": inv,
                "inventory_mapped_canonical": inv_mapped,
                "field_mappings": nec.get("field_mappings"),
                "conflict": nec.get("conflict"),
                "human_judgments_preserved": nec["provenance_records"].get(
                    "human_judgments_preserved"
                ),
                "single_window_necessity_audit": nec["provenance_records"].get(
                    "single_window_necessity_audit"
                ),
            }
        )
    return {
        "schema": "necessity_diff_report_v1",
        "algo_version": ALGO,
        "policy": (
            "Track A must consume necessity_authoritative only. Inventory and other "
            "records are provenance. Conflicts resolve to human_judgments_preserved."
        ),
        "items": rows,
    }


def build_window_report(qa: list[dict]) -> dict:
    rows = []
    for q in qa:
        w = q["windows"]
        rows.append(
            {
                "item_id": q["item_id"],
                "status": w["status"],
                "fixed_ab_window_eval": w["evaluation_gates"]["fixed_ab_window_eval"],
                "block_reason": w["evaluation_gates"].get("block_reason"),
                "A": w.get("A"),
                "B": w.get("B"),
                "approved_source_search": w.get("approved_source_search"),
            }
        )
    blocked = [
        r["item_id"]
        for r in rows
        if r["fixed_ab_window_eval"] == "BLOCKED"
    ]
    return {
        "schema": "window_availability_report_v1",
        "algo_version": ALGO,
        "blocked_fixed_ab_window_eval": blocked,
        "items": rows,
        "policy": "Do not guess source seconds; unapproved offsets stay UNKNOWN.",
    }


def build_language_structure_report(qa: list[dict], graphs: list[dict]) -> dict:
    lang = {}
    for q in qa:
        lang[q["item_id"]] = {
            "question_language": q["question_language"],
            "split_role_pilot": q["split_role_pilot"],
            "question_preview": (q["question_text"] or "")[:80],
        }
    # C2 abbreviation constraint — report only, do not rewrite labels
    c2 = next(g for g in graphs if g["item_id"] == "P7_VTCD_C2")
    c2_nodes = []
    for n in c2["nodes"]:
        if n.get("raw_operator") in (
            "ReadNameAbbreviationGraphic",
            "ReadNameGraphic",
        ) or (n.get("raw_evidence") or {}).get("on_screen_text"):
            c2_nodes.append(
                {
                    "node_id": n["node_id"],
                    "raw_operator": n.get("raw_operator"),
                    "layer1": n.get("layer1"),
                    "layer2": n.get("layer2"),
                    "on_screen_text": (n.get("raw_evidence") or {}).get(
                        "on_screen_text"
                    ),
                    "issue": None,
                }
            )
    for row in c2_nodes:
        if row["raw_operator"] == "ReadNameAbbreviationGraphic":
            if row["layer2"] == "ReadPersonNameFromGraphic":
                row["issue"] = (
                    "STRUCTURE_LIMIT: raw operator is name-abbreviation matching "
                    "(ReadNameAbbreviationGraphic / e.g. 'Fan Z.D.'), but Layer2 collapses "
                    "to generic ReadPersonNameFromGraphic. Track A must not treat the "
                    "generic Layer2 label as the full scientific constraint."
                )
            else:
                row["issue"] = (
                    "Raw abbreviation-matching operator present; preserve strict semantics."
                )

    seen_langs = {lang[i]["question_language"] for i in SEEN}
    unseen_langs = {lang[i]["question_language"] for i in UNSEEN}
    return {
        "schema": "language_and_structure_limits_report_v1",
        "algo_version": ALGO,
        "language_distribution": {
            "seen_item_languages": {i: lang[i]["question_language"] for i in SEEN},
            "unseen_item_languages": {i: lang[i]["question_language"] for i in UNSEEN},
            "summary": (
                f"Seen items languages={sorted(seen_langs)}; "
                f"Unseen items languages={sorted(unseen_langs)}. "
                "5 Seen English / 2 Unseen Chinese distribution difference is reported "
                "as a validation limitation, not rewritten."
            ),
            "limitation": (
                "Language mismatch between Seen (en) and Unseen (zh) may confound "
                "Track A minimal validation; no scientific relabeling performed."
            ),
        },
        "per_item": lang,
        "c2_name_abbreviation_constraint": {
            "item_id": "P7_VTCD_C2",
            "policy": "Report only; do not rewrite scientific annotations.",
            "nodes": c2_nodes,
        },
    }


def validate_export(qa, graphs, videos, split, schema_result, leak_issues) -> dict:
    issues = uniqueness_and_join_checks(qa, graphs, videos, split)
    schema_status = schema_result["status"]
    if schema_status != "PASS":
        issues.append(
            {
                "code": "SCHEMA_VALIDATION_NOT_PASS",
                "schema_result": schema_result,
            }
        )
    for li in leak_issues:
        issues.append(li)

    def ok(code_prefix: str) -> str:
        return (
            "PASS"
            if not any(str(i.get("code", "")).startswith(code_prefix) for i in issues)
            else "FAIL"
        )

    checks = {
        "schema_validation": schema_status,
        "schema_engine": schema_result.get("engine"),
        "join_qa_video": ok("QA_VIDEO_JOIN"),
        "join_graph_edges": ok("GRAPH_EDGE_JOIN"),
        "uniqueness": (
            "PASS"
            if not any(str(i.get("code", "")).startswith("DUPLICATE") for i in issues)
            else "FAIL"
        ),
        "no_false_gold": (
            "PASS"
            if not any(str(i.get("code", "")).startswith("FALSE_GOLD") for i in issues)
            else "FAIL"
        ),
        "id_set_7": "PASS" if [x["item_id"] for x in qa] == EXPORT_IDS else "FAIL",
        "necessity_authoritative": (
            "PASS"
            if not any(
                i.get("code") in ("SP201_SP202_NECESSITY_NULL", "P7_AUTHORITY_NOT_HUMAN_JUDGMENT")
                for i in issues
            )
            else "FAIL"
        ),
        "p7_window_eval_blocked": (
            "PASS"
            if not any(i.get("code") == "P7_WINDOW_EVAL_NOT_BLOCKED" for i in issues)
            else "FAIL"
        ),
        "inference_safe_leak_scan": "PASS" if not leak_issues else "FAIL",
    }
    # Full PASS only if every check passes AND schema actually ran PASS
    status = (
        "PASS"
        if schema_status == "PASS" and all(
            v == "PASS" for k, v in checks.items() if k != "schema_engine"
        )
        else "FAIL"
    )
    return {
        "schema": "minimal_validation_export_validation_v1_1",
        "status": status,
        "n_issues": len(issues),
        "issues": issues,
        "checks": checks,
        "schema_validation_detail": schema_result,
        "validated_utc": utc_now(),
        "algo_version": ALGO,
        "policy_notes": [
            "Schema validation SKIPPED/FAIL ⇒ overall status cannot be PASS.",
            "Answers are not formal Gold.",
            "Sidecars are not frame-level video certification.",
            "Training exposure protection fields unchanged (all formal_* false).",
        ],
    }


def write_readme() -> str:
    return f"""# Track B → Track A minimal validation export v1.1

Read-only packaging of the fixed **5 Seen + 2 Unseen** pilot for Track A *loading/plumbing* checks.

**Not** a formal Gold set. **Not** a launch of Track A experiments.

## Layout

| Path | Role |
|------|------|
| `qa_items.json` / `program_graphs.json` / `video_manifest.json` / `split_manifest.json` | Full scientific audit pack |
| `projections/inference_safe/` | Ordinary Track A inference projection |
| `projections/scorer_private/` | Scorer-only answers (not for inference) |
| `NECESSITY_DIFF_REPORT.json` | Inventory vs authoritative necessity |
| `WINDOW_AVAILABILITY_REPORT.json` | Fixed A/B window eval availability |
| `LANGUAGE_AND_STRUCTURE_LIMITS_REPORT.json` | en/zh split + C2 abbreviation constraint |
| `CHANGE_LIST_WP1_2.md` | Isolation patch change list |
| `projections/inference_safe/INFERENCE_ACCESS_WHITELIST.json` | Machine-enforced inference file whitelist |
| `schemas/*.json` | Strict JSON Schemas |
| `VALIDATION_REPORT.json` | Schema + join + uniqueness + leak scan |

## Join keys

- `item_id` joins QA ↔ graphs ↔ split
- `video_id` joins QA ↔ video_manifest

## Necessity authority

Scientific audit / scorer-private: use `necessity.necessity_authoritative`.  
Ordinary inference projection: necessity labels are **withheld** (`WITHHELD_SCORER_PRIVATE`).

## Inference access

```python
from eng.inference_access import resolve_allowed_path, open_text
root = Path('.../projections/inference_safe')
text = open_text(root, 'qa_items.json')  # parent escapes raise InferenceAccessError
```

## Limits

- Answers: `HUMAN_REFERENCE_OR_HISTORICAL_NOT_FORMAL_GOLD`
- Unseen graphs omitted; Unseen structure labels withheld from inference split
- Human A-only/B-only necessity is scorer-private only
- P7 windows UNKNOWN ⇒ `fixed_ab_window_eval=BLOCKED`
- C2 abbreviation-matching constraint reported; annotations not rewritten
- Local video SHA is engineering-only

## Validate

```bash
python3 eng/build_minimal_validation_export_v1.py
python3 tests/test_minimal_validation_export_v1.py -v
```

Built by `{ALGO}`.
"""


def write_change_list() -> str:
    return """# WP1.2 Change List (inference-side isolation)

Engineering-only patch on top of `b1e57d6`. No scientific re-adjudication. No Track A launch.

1. **Unseen structure withheld** — `projections/inference_safe/split_manifest.json` keeps Seen structure labels; Unseen Layer1/Layer2/operator sets and n_nodes/n_edges are `WITHHELD_FROM_INFERENCE`. Full split remains in the scientific audit pack at package root.
2. **Necessity private** — `necessity_authoritative` removed from inference QA projection; moved to `projections/scorer_private/eval_private_metadata.json` (+ still on scorer answers).
3. **File access whitelist** — `INFERENCE_ACCESS_WHITELIST.json` + `eng/inference_access.py::resolve_allowed_path` reject parent escapes to answers / Unseen graphs. Not ACCESS.md-only.
4. **Negative leak tests** — Injecting Unseen operators/structure or reference answers into the inference projection must fail validation.
5. **Preserved** — Root scientific audit, schema/join/necessity/window/language/evidence checks; formal_* and train_exposed unchanged.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "schemas").mkdir(exist_ok=True)
    proj_inf = OUT / "projections" / "inference_safe"
    proj_scorer = OUT / "projections" / "scorer_private"
    proj_inf.mkdir(parents=True, exist_ok=True)
    proj_scorer.mkdir(parents=True, exist_ok=True)

    inv = load_inventory()
    qa = build_qa_items(inv)
    graphs = build_program_graphs()
    videos = build_video_manifest(qa)
    split = build_split_manifest(inv, graphs)
    projections = build_projections(qa, graphs, videos, split)

    qa_doc = {
        "schema": "minimal_validation_qa_items_v1",
        "algo_version": ALGO,
        "built_utc": utc_now(),
        "n_items": len(qa),
        "items": qa,
        "disclaimer": "Answers are not formal Gold. Export is for Track A minimal validation only.",
    }
    graphs_doc = {
        "schema": "minimal_validation_program_graphs_v1",
        "algo_version": ALGO,
        "built_utc": utc_now(),
        "n_graphs": len(graphs),
        "graphs": graphs,
        "disclaimer": "Sidecar/structured graphs ≠ frame-certified video semantics.",
    }
    video_doc = {
        "schema": "minimal_validation_video_manifest_v1",
        "algo_version": ALGO,
        "built_utc": utc_now(),
        "videos": videos,
    }

    schemas = build_schemas()
    for name, sch in schemas.items():
        (OUT / "schemas" / name).write_text(json.dumps(sch, indent=2) + "\n")

    # Write projections before leak scan
    (proj_inf / "qa_items.json").write_text(
        json.dumps(projections["inference_safe"]["qa_items"], indent=2, ensure_ascii=False)
        + "\n"
    )
    (proj_inf / "program_graphs_seen_redacted.json").write_text(
        json.dumps(
            projections["inference_safe"]["program_graphs_seen_redacted"],
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    (proj_inf / "video_manifest.json").write_text(
        json.dumps(
            projections["inference_safe"]["video_manifest"], indent=2, ensure_ascii=False
        )
        + "\n"
    )
    (proj_inf / "split_manifest.json").write_text(
        json.dumps(
            projections["inference_safe"]["split_manifest"], indent=2, ensure_ascii=False
        )
        + "\n"
    )
    (proj_inf / WHITELIST_FILENAME).write_text(
        json.dumps(projections["inference_safe"]["whitelist"], indent=2, ensure_ascii=False)
        + "\n"
    )
    (proj_inf / "ACCESS.md").write_text(projections["inference_safe"]["ACCESS.md"])
    (proj_scorer / "answers.json").write_text(
        json.dumps(projections["scorer_private"]["answers"], indent=2, ensure_ascii=False)
        + "\n"
    )
    (proj_scorer / "eval_private_metadata.json").write_text(
        json.dumps(
            projections["scorer_private"]["eval_private_metadata"],
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    (proj_scorer / "ACCESS.md").write_text(projections["scorer_private"]["ACCESS.md"])

    leak_issues = leak_scan_inference_safe(
        proj_inf, projections["scorer_private"]["answers"]["items"]
    )
    schema_result = run_schema_validation(
        {
            "qa_items.schema.json": qa_doc,
            "program_graphs.schema.json": graphs_doc,
            "video_manifest.schema.json": video_doc,
            "split_manifest.schema.json": split,
        },
        schemas,
    )
    report = validate_export(qa, graphs, videos, split, schema_result, leak_issues)

    (OUT / "qa_items.json").write_text(
        json.dumps(qa_doc, indent=2, ensure_ascii=False) + "\n"
    )
    (OUT / "program_graphs.json").write_text(
        json.dumps(graphs_doc, indent=2, ensure_ascii=False) + "\n"
    )
    (OUT / "video_manifest.json").write_text(
        json.dumps(video_doc, indent=2, ensure_ascii=False) + "\n"
    )
    (OUT / "split_manifest.json").write_text(
        json.dumps(split, indent=2, ensure_ascii=False) + "\n"
    )
    (OUT / "NECESSITY_DIFF_REPORT.json").write_text(
        json.dumps(build_necessity_diff(qa), indent=2, ensure_ascii=False) + "\n"
    )
    (OUT / "WINDOW_AVAILABILITY_REPORT.json").write_text(
        json.dumps(build_window_report(qa), indent=2, ensure_ascii=False) + "\n"
    )
    (OUT / "LANGUAGE_AND_STRUCTURE_LIMITS_REPORT.json").write_text(
        json.dumps(
            build_language_structure_report(qa, graphs), indent=2, ensure_ascii=False
        )
        + "\n"
    )
    (OUT / "VALIDATION_REPORT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    (OUT / "CHANGE_LIST_WP1_2.md").write_text(write_change_list())
    (OUT / "README.md").write_text(write_readme())

    print(
        json.dumps(
            {
                "status": report["status"],
                "checks": report["checks"],
                "n_issues": report["n_issues"],
            },
            indent=2,
        )
    )
    if report["status"] != "PASS":
        print(json.dumps(report["issues"][:20], indent=2, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
