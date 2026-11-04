#!/usr/bin/env python3
"""WP1: export Track-A-facing minimal validation benchmark (read-only aggregation).

Does not start Track A, mint formal Gold, invent video facts, or claim frame certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
PILOT = (
    ROOT
    / "research_audit/lvbench_compositional/track_b/family_level_minimal_validation_pilot_v0.1"
)
NORM = (
    ROOT
    / "research_audit/lvbench_compositional/track_b/normalized_programs_v1"
)
OUT = Path(__file__).resolve().parents[1]
VIDEO_ROOTS = [
    Path("/home/descfly/lpy/dataset/LVBench/videos"),
    ROOT / "data" / "lvbench" / "videos",
]

SEEN = ["SP001", "SP002", "SP005", "SP201", "SP202"]
UNSEEN = ["P7_VTCD_C2", "P7_TJR_R3"]
EXPORT_IDS = SEEN + UNSEEN
ALGO = "minimal_validation_export_v1.0.0"


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


def load_inventory() -> dict[str, dict]:
    inv = json.loads((PILOT / "PILOT_INVENTORY.json").read_text())
    return {it["item_id"]: it for it in inv["items"]}


def find_video(video_id: str) -> Path | None:
    for root in VIDEO_ROOTS:
        p = root / f"{video_id}.mp4"
        if p.is_file():
            return p
    return None


def necessity_block(item_id: str, inv_it: dict, record: dict | None) -> dict:
    """Prefer scientific preserved judgments; keep inventory fields as secondary."""
    out = {
        "status": "RECORDED_FROM_SCIENTIFIC_SOURCES",
        "not_model_ablation": True,
        "sources": [],
    }
    # Seen pilot records
    if record and record.get("composition_necessity"):
        out["composition_necessity_label"] = record["composition_necessity"]
        out["sources"].append("provenance_record.composition_necessity")
    inv_nec = inv_it.get("single_window_necessity") or {}
    out["inventory_single_window_necessity"] = inv_nec
    out["sources"].append("PILOT_INVENTORY.single_window_necessity")

    hj = None
    if record and isinstance(record.get("human_judgments_preserved"), dict):
        hj = record["human_judgments_preserved"]
    if hj:
        out["human_judgments_preserved"] = {
            "a_only_sufficient": yn_to_bool(hj.get("a_only_sufficient")),
            "b_only_sufficient": yn_to_bool(hj.get("b_only_sufficient")),
            "a_plus_b_supports_user_answer": yn_to_bool(
                hj.get("a_plus_b_supports_user_answer")
            ),
            "truly_needs_cross_clip_composition": yn_to_bool(
                hj.get("truly_needs_cross_clip_composition")
            ),
            "raw": hj,
        }
        out["sources"].append("graph_or_record.human_judgments_preserved")
        # primary conclusion from preserved human judgment when present
        out["primary"] = {
            "a_only_sufficient": out["human_judgments_preserved"]["a_only_sufficient"],
            "b_only_sufficient": out["human_judgments_preserved"]["b_only_sufficient"],
            "cross_clip_necessary": out["human_judgments_preserved"][
                "truly_needs_cross_clip_composition"
            ],
            "authority": "human_judgments_preserved",
        }
        # conflict vs inventory booleans if both present
        inv_a = inv_nec.get("a_only_sufficient")
        inv_b = inv_nec.get("b_only_sufficient")
        if inv_a is not None and out["primary"]["a_only_sufficient"] is not None:
            if bool(inv_a) != bool(out["primary"]["a_only_sufficient"]) or (
                inv_b is not None
                and out["primary"]["b_only_sufficient"] is not None
                and bool(inv_b) != bool(out["primary"]["b_only_sufficient"])
            ):
                out["inventory_vs_preserved_conflict"] = True
                out["conflict_note"] = (
                    "Inventory single_window_necessity booleans disagree with "
                    "human_judgments_preserved; Track A must use preserved human judgment."
                )
            else:
                out["inventory_vs_preserved_conflict"] = False
    else:
        # Seen inventory necessity
        out["primary"] = {
            "a_only_sufficient": inv_nec.get("a_only_sufficient"),
            "b_only_sufficient": inv_nec.get("b_only_sufficient"),
            "a_plus_b": inv_nec.get("a_plus_b")
            or inv_nec.get("a_plus_b_necessary"),
            "authority": "PILOT_INVENTORY.single_window_necessity",
        }
    return out


def windows_block(item_id: str, inv_it: dict, record: dict | None) -> dict:
    wins = None
    if record and record.get("windows_seconds"):
        wins = record["windows_seconds"]
    if wins is None:
        wins = inv_it.get("windows_seconds")
    if wins:
        return {
            "status": "RECORDED_SOURCE_SECONDS",
            "A": {"t_start_s": wins["A"][0], "t_end_s": wins["A"][1]},
            "B": {"t_start_s": wins["B"][0], "t_end_s": wins["B"][1]},
            "time_base": "source_video_seconds",
            "precision": "AS_RECORDED_IN_SCIENTIFIC_REVIEW_NOT_REVERIFIED_HERE",
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
    }


def answer_block(inv_it: dict, record: dict | None) -> dict:
    ans = inv_it.get("answer_reference")
    hist = None
    if record and record.get("historical_answer") is not None:
        hist = record["historical_answer"]
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
        # P7 frozen question from blind packet if needed
        if not q and item_id.startswith("P7_"):
            bp = PILOT / "provenance_snapshots" / f"{item_id}_blind_packet.json"
            if bp.is_file():
                q = json.loads(bp.read_text()).get("frozen_question")
        items.append(
            {
                "item_id": item_id,
                "qa_uid": inv_it.get("qa_uid"),
                "video_id": inv_it.get("video_id")
                or (record or {}).get("video_id"),
                "split_role_pilot": inv_it.get("pilot_role"),
                "question_text": q,
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
    videos = {}
    for qa in qa_items:
        vid = qa["video_id"]
        videos.setdefault(vid, []).append(qa["item_id"])
    rows = []
    for video_id, item_ids in sorted(videos.items()):
        path = find_video(video_id)
        # scientific hash: only if previously recorded somewhere — default UNKNOWN
        scientific_hash = "UNKNOWN"
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
                "video_sha256_scientific": scientific_hash,
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
        "fixed_seen": SEEN,
        "fixed_unseen": UNSEEN,
        "candidate_excluded_from_this_export": ["A", "B", "P7_R4_F1", "P7_R4_F2", "SP205"],
        "items": rows,
    }


def validate_export(qa, graphs, videos, split) -> dict:
    issues = []
    qa_ids = [x["item_id"] for x in qa]
    g_ids = [x["item_id"] for x in graphs]
    s_ids = [x["item_id"] for x in split["items"]]
    if qa_ids != EXPORT_IDS or g_ids != EXPORT_IDS or s_ids != EXPORT_IDS:
        issues.append({"code": "ID_ORDER_OR_SET_MISMATCH", "qa": qa_ids, "graphs": g_ids})
    # join keys
    for q in qa:
        if not q.get("video_id"):
            issues.append({"code": "MISSING_VIDEO_ID", "item_id": q["item_id"]})
        if not q.get("question_text"):
            issues.append({"code": "MISSING_QUESTION", "item_id": q["item_id"]})
        if q["answer"].get("formal_gold") is True:
            issues.append({"code": "FALSE_GOLD", "item_id": q["item_id"]})
        if q["answer"]["answer_certification_status"] == "FORMAL_GOLD":
            issues.append({"code": "FALSE_GOLD_STATUS", "item_id": q["item_id"]})
    vid_set = {v["video_id"] for v in videos}
    for q in qa:
        if q["video_id"] not in vid_set:
            issues.append(
                {"code": "QA_VIDEO_JOIN_FAIL", "item_id": q["item_id"], "video_id": q["video_id"]}
            )
    for g in graphs:
        node_ids = {n["node_id"] for n in g["nodes"]}
        for e in g["edges"]:
            if e["from_node"] not in node_ids or e["to_node"] not in node_ids:
                issues.append({"code": "GRAPH_EDGE_JOIN_FAIL", "item_id": g["item_id"], "edge": e})
        if g["n_nodes"] != len(g["nodes"]) or g["n_edges"] != len(g["edges"]):
            issues.append({"code": "GRAPH_COUNT_MISMATCH", "item_id": g["item_id"]})
        # no frame-certified claim on chat sidecars
        if g["normalization_status"] == "CHAT_APPROVED_SIDECAR_INGESTED":
            for n in g["nodes"]:
                if n.get("evidence_certification") == "FRAME_CERTIFIED":
                    issues.append(
                        {"code": "FALSE_FRAME_CERT", "item_id": g["item_id"], "node": n["node_id"]}
                    )
    # schema-ish required fields
    for q in qa:
        for k in ("item_id", "qa_uid", "video_id", "question_text", "answer", "windows", "necessity"):
            if k not in q:
                issues.append({"code": "QA_SCHEMA", "missing": k, "item_id": q.get("item_id")})
    status = "PASS" if not issues else "FAIL"
    return {
        "schema": "minimal_validation_export_validation_v1",
        "status": status,
        "n_issues": len(issues),
        "issues": issues,
        "checks": {
            "join_qa_video": "PASS"
            if not any(i["code"] == "QA_VIDEO_JOIN_FAIL" for i in issues)
            else "FAIL",
            "join_graph_edges": "PASS"
            if not any(i["code"] == "GRAPH_EDGE_JOIN_FAIL" for i in issues)
            else "FAIL",
            "no_false_gold": "PASS"
            if not any(str(i["code"]).startswith("FALSE_GOLD") for i in issues)
            else "FAIL",
            "id_set_7": "PASS" if qa_ids == EXPORT_IDS else "FAIL",
        },
        "validated_utc": utc_now(),
        "algo_version": ALGO,
    }


def write_readme() -> str:
    return f"""# Track B → Track A minimal validation export v1

Read-only packaging of the fixed **5 Seen + 2 Unseen** pilot for Track A *loading/plumbing* checks.

**Not** a formal Gold set. **Not** a launch of Track A experiments.

## Files

| File | Contents |
|------|----------|
| `qa_items.json` | QA text, answer + certification status, item/video IDs, A/B windows, necessity |
| `program_graphs.json` | 7 normalized directed graphs (nodes/edges/L1/L2/I/O/time/evidence status) |
| `video_manifest.json` | Video IDs, local path if resolved, time base, hashes |
| `split_manifest.json` | Fixed 5/2 roles, structure labels, training-exposure limits |
| `schemas/*.json` | Lightweight JSON Schemas |
| `VALIDATION_REPORT.json` | Schema/join-key validation result |

## Join keys

- `item_id` joins `qa_items` ↔ `program_graphs` ↔ `split_manifest.items`
- `video_id` joins `qa_items` ↔ `video_manifest`

## Loading example

```python
import json
from pathlib import Path
root = Path('research_audit/lvbench_compositional/track_b/minimal_validation_export_v1')
qa = {{x['item_id']: x for x in json.loads((root/'qa_items.json').read_text())['items']}}
graphs = {{x['item_id']: x for x in json.loads((root/'program_graphs.json').read_text())['graphs']}}
videos = {{x['video_id']: x for x in json.loads((root/'video_manifest.json').read_text())['videos']}}
assert set(qa) == set(graphs)
for item_id, row in qa.items():
    assert row['video_id'] in videos
```

## Limits (mandatory)

- Answers are `HUMAN_REFERENCE_OR_HISTORICAL_NOT_FORMAL_GOLD` — **not** formal Gold.
- Chat-approved program sidecars are **not** frame-level video certification.
- P7 windows may be `UNKNOWN_PENDING_SOURCE_SECOND_MAPPING` — do not invent seconds from graphs.
- Pilot Seen/Unseen ≠ formal Seen/Unseen/train exposure.
- Local video SHA (if present) is an engineering fingerprint only.

## Sources

- Pilot inventory/records: `family_level_minimal_validation_pilot_v0.1/`
- Normalized graphs: `normalized_programs_v1/graphs/{{item_id}}.json`
- Built by `{ALGO}` at export time.

## Validate

```bash
python3 eng/build_minimal_validation_export_v1.py
python3 tests/test_minimal_validation_export_v1.py -v
```
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "schemas").mkdir(exist_ok=True)
    inv = load_inventory()
    qa = build_qa_items(inv)
    graphs = build_program_graphs()
    videos = build_video_manifest(qa)
    split = build_split_manifest(inv, graphs)

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

    report = validate_export(qa, graphs, videos, split)

    # lightweight schemas
    schemas = {
        "qa_items.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["schema", "items"],
            "properties": {
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
                            "answer",
                            "windows",
                            "necessity",
                        ],
                    },
                }
            },
        },
        "program_graphs.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["schema", "graphs"],
            "properties": {
                "graphs": {
                    "type": "array",
                    "minItems": 7,
                    "maxItems": 7,
                    "items": {
                        "type": "object",
                        "required": ["item_id", "nodes", "edges", "n_nodes", "n_edges"],
                    },
                }
            },
        },
        "video_manifest.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["schema", "videos"],
            "properties": {"videos": {"type": "array", "minItems": 1}},
        },
        "split_manifest.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["schema", "fixed_seen", "fixed_unseen", "items"],
        },
    }
    for name, sch in schemas.items():
        (OUT / "schemas" / name).write_text(json.dumps(sch, indent=2) + "\n")

    # optional jsonschema if installed
    try:
        import jsonschema  # type: ignore

        jsonschema.validate(qa_doc, schemas["qa_items.schema.json"])
        jsonschema.validate(graphs_doc, schemas["program_graphs.schema.json"])
        jsonschema.validate(video_doc, schemas["video_manifest.schema.json"])
        jsonschema.validate(split, schemas["split_manifest.schema.json"])
        report["jsonschema"] = "PASS"
    except ImportError:
        report["jsonschema"] = "SKIPPED_LIBRARY_NOT_INSTALLED_USED_STRUCTURAL_CHECKS"
    except Exception as e:
        report["jsonschema"] = f"FAIL:{e}"
        report["status"] = "FAIL"
        report["issues"].append({"code": "JSONSCHEMA", "error": str(e)})

    (OUT / "qa_items.json").write_text(json.dumps(qa_doc, indent=2, ensure_ascii=False) + "\n")
    (OUT / "program_graphs.json").write_text(
        json.dumps(graphs_doc, indent=2, ensure_ascii=False) + "\n"
    )
    (OUT / "video_manifest.json").write_text(
        json.dumps(video_doc, indent=2, ensure_ascii=False) + "\n"
    )
    (OUT / "split_manifest.json").write_text(
        json.dumps(split, indent=2, ensure_ascii=False) + "\n"
    )
    (OUT / "VALIDATION_REPORT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    (OUT / "README.md").write_text(write_readme())
    print(json.dumps({"status": report["status"], "checks": report["checks"]}, indent=2))


if __name__ == "__main__":
    main()
