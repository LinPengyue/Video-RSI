#!/usr/bin/env python3
"""S8: composition structure feedback via normalized_programs_v1.

Layer 1 coverage and Layer 2 coverage are computed separately.
Layer 2 operator names are normalized only via auditable equivalence;
unproven aliases return UNKNOWN and must not be force-merged.
Atomic-covered composition-OOD requires: all L2 atoms Seen-covered,
target directed composition absent from Seen, and role/dependency/
training-exposure checks all pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[6]
NP = ROOT / "research_audit/lvbench_compositional/track_b/normalized_programs_v1"
ENG = NP / "eng"
SEEN = ["SP001", "SP002", "SP005", "SP201", "SP202"]

sys.path.insert(0, str(ENG))
from stage4_m3_isomorphism import enumerate_subgraphs, pool_signatures  # noqa: E402


# Auditable Layer-2 equivalence only. Identity is always exact.
# Do NOT add speculative aliases (e.g. CrossIntervalSamePersonBind ≈ BindSamePerson)
# without an independent operator-equivalence proof artifact.
LAYER2_AUDITABLE_ALIASES: dict[str, dict[str, str]] = {
    # empty by design until an audited equivalence table exists
}


def load_seen_graphs() -> dict[str, dict]:
    graphs = {}
    gdir = NP / "graphs"
    for gid in SEEN:
        p = gdir / f"{gid}.json"
        if p.exists():
            graphs[gid] = json.loads(p.read_text())
    return graphs


def seen_layer_vocab(seen: dict[str, dict]) -> tuple[set[str], set[str]]:
    seen_l1 = {n["layer1"] for g in seen.values() for n in g["nodes"]}
    seen_l2 = {n["layer2"] for g in seen.values() for n in g["nodes"]}
    return seen_l1, seen_l2


def normalize_layer2_operator(raw: str, seen_l2: set[str]) -> dict[str, Any]:
    """Normalize a Layer-2 operator name with an auditable trail.

    Returns status EXACT | ALIAS | UNKNOWN. UNKNOWN must not be treated as covered.
    """
    if not raw:
        return {
            "raw": raw,
            "normalized": None,
            "status": "UNKNOWN",
            "reason": "empty_operator_name",
        }
    if raw in seen_l2:
        return {
            "raw": raw,
            "normalized": raw,
            "status": "EXACT",
            "reason": "exact_seen_layer2_label",
        }
    alias = LAYER2_AUDITABLE_ALIASES.get(raw)
    if alias and alias.get("normalized") in seen_l2:
        return {
            "raw": raw,
            "normalized": alias["normalized"],
            "status": "ALIAS",
            "reason": alias.get("proof") or "auditable_alias_table",
            "proof_ref": alias.get("proof_ref"),
        }
    if alias and alias.get("normalized") not in seen_l2:
        return {
            "raw": raw,
            "normalized": None,
            "status": "UNKNOWN",
            "reason": "alias_target_not_in_seen_layer2",
        }
    return {
        "raw": raw,
        "normalized": None,
        "status": "UNKNOWN",
        "reason": "no_auditable_equivalence_to_seen_layer2",
    }


def draft_graph_to_normalized(program_graph: dict[str, Any]) -> dict[str, Any]:
    """Convert S5 draft graph into normalized_programs-like shape for subgraph enum."""
    nodes = []
    for n in program_graph.get("nodes") or []:
        nodes.append(
            {
                "node_id": n["node_id"],
                "raw_operator": n.get("op") or n.get("raw_operator"),
                "layer1": n.get("layer1") or "UNKNOWN_LAYER1",
                "layer2": n.get("layer2") or n.get("op") or "UNKNOWN_LAYER2",
                "normalized_clip_role": n.get("normalized_clip_role") or n.get("window"),
                "raw_clip_role": n.get("raw_clip_role") or n.get("window"),
            }
        )
    edges = []
    for e in program_graph.get("edges") or []:
        frm = e.get("from_node") or e.get("from") or e.get("source")
        to = e.get("to_node") or e.get("to") or e.get("target")
        edges.append(
            {
                "from_node": frm,
                "to_node": to,
                "from": frm,
                "to": to,
                "type": e.get("type") or "dataflow",
                "port": e.get("port") or e.get("from_port"),
            }
        )
    return {
        "graph_id": program_graph.get("program_id") or "draft",
        "nodes": nodes,
        "edges": edges,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
    }


def _role_dependency_training_checks(
    draft: dict[str, Any],
    program_graph: dict[str, Any],
) -> dict[str, Any]:
    """Independent gates required for Atomic-covered composition-OOD."""
    roles = {n.get("normalized_clip_role") for n in draft["nodes"] if n.get("normalized_clip_role")}
    has_a = "A" in roles
    has_b = "B" in roles
    # Expected dataflow: both locates → bind → query (not a mere node list)
    edge_pairs = {
        (e.get("from_node") or e.get("from"), e.get("to_node") or e.get("to"))
        for e in draft["edges"]
    }
    ops = {n["node_id"]: n.get("raw_operator") or n.get("layer2") for n in draft["nodes"]}
    bind_nodes = [nid for nid, op in ops.items() if op and "Bind" in str(op)]
    locate_nodes = [nid for nid, op in ops.items() if op and "Locate" in str(op)]
    query_nodes = [nid for nid, op in ops.items() if op and "Query" in str(op)]
    locates_feed_bind = False
    bind_feeds_query = False
    if bind_nodes and locate_nodes:
        locates_feed_bind = all(
            any((ln, bn) in edge_pairs for bn in bind_nodes) for ln in locate_nodes
        )
    if bind_nodes and query_nodes:
        bind_feeds_query = any((bn, qn) in edge_pairs for bn in bind_nodes for qn in query_nodes)

    # Training exposure: draft must not reuse a Seen graph_id / seed program bytes
    training_ok = draft["graph_id"] not in SEEN and not str(draft["graph_id"]).startswith("SP")

    role_ok = has_a and has_b
    dep_ok = locates_feed_bind and bind_feeds_query
    return {
        "role_check": {
            "pass": role_ok,
            "roles_present": sorted(roles),
            "requires": ["A", "B"],
        },
        "dependency_check": {
            "pass": dep_ok,
            "locates_feed_bind": locates_feed_bind,
            "bind_feeds_query": bind_feeds_query,
            "edge_pairs": sorted((a, b) for a, b in edge_pairs if a and b),
        },
        "training_exposure_check": {
            "pass": training_ok,
            "draft_graph_id": draft["graph_id"],
            "seen_seed_ids": list(SEEN),
            "note": "Does not claim video-level contamination audit; only seed-graph id collision",
        },
        "all_pass": role_ok and dep_ok and training_ok,
        "semantic_io_validated": bool(
            (program_graph.get("semantic_validation") or {}).get("status") == "OK"
        ),
    }


def audit_draft_against_seen(program_graph: dict[str, Any]) -> dict[str, Any]:
    seen = load_seen_graphs()
    draft = draft_graph_to_normalized(program_graph)
    seen_l1, seen_l2 = seen_layer_vocab(seen)

    draft_l1 = {n["layer1"] for n in draft["nodes"]}
    draft_l2_raw = {n["layer2"] for n in draft["nodes"]}

    l2_norm = [normalize_layer2_operator(lab, seen_l2) for lab in sorted(draft_l2_raw)]
    normalized_l2 = {r["normalized"] for r in l2_norm if r["normalized"]}
    unknown_l2 = [r for r in l2_norm if r["status"] == "UNKNOWN"]

    atomic_covered_l1 = draft_l1 <= seen_l1 and len(draft_l1) > 0
    # L2 coverage requires successful normalization for EVERY draft L2 label AND
    # normalized set ⊆ seen_l2. UNKNOWN blocks coverage (no force-merge).
    atomic_covered_l2 = (not unknown_l2) and normalized_l2 <= seen_l2 and len(normalized_l2) > 0

    # Subgraph signatures: L1 uses layer1; L2 uses normalized labels when known,
    # else keep raw for novelty reporting but mark unverified.
    draft_for_l2_sig = json.loads(json.dumps(draft))
    for n in draft_for_l2_sig["nodes"]:
        nr = normalize_layer2_operator(n["layer2"], seen_l2)
        if nr["normalized"]:
            n["layer2"] = nr["normalized"]

    sigs: dict[str, Any] = {}
    for size in (2, 3):
        for layer, mode in (("layer1", "ops"), ("layer2", "ops")):
            key = f"{size}node_{layer}_{mode}"
            g = draft if layer == "layer1" else draft_for_l2_sig
            items = enumerate_subgraphs(g, size, layer, mode)
            seen_u, _, _ = pool_signatures(seen, list(seen.keys()), size, layer, mode)
            novel = [it for it in items if it["signature"] not in seen_u]
            sigs[key] = {
                "n_subgraphs": len(items),
                "n_novel_vs_seen": len(novel),
                "novel_signatures": [it["signature"] for it in novel[:20]],
                "all_signatures": [it["signature"] for it in items],
            }

    gates = _role_dependency_training_checks(draft, program_graph)
    composition_novel_l1 = any(
        sigs[k]["n_novel_vs_seen"] > 0 for k in sigs if "layer1" in k
    )
    composition_novel_l2 = any(
        sigs[k]["n_novel_vs_seen"] > 0 for k in sigs if "layer2" in k
    )

    # Always begin as unverified structural novelty, then promote only if criteria met.
    provisional = "STRUCTURAL_NOVELTY_CANDIDATE_UNVERIFIED"
    atomic_covered_ood = False
    if not atomic_covered_l1:
        bucket = "ATOMIC_NOVELTY_OR_UNKNOWN_CONTROL"
    elif not atomic_covered_l2:
        bucket = "L1_COVERED_L2_UNCOVERED_OR_UNKNOWN"
    elif (
        atomic_covered_l1
        and atomic_covered_l2
        and (composition_novel_l1 or composition_novel_l2)
        and gates["all_pass"]
        and gates["semantic_io_validated"]
    ):
        bucket = "ATOMIC_COVERED_COMPOSITION_OOD_CANDIDATE"
        atomic_covered_ood = True
    elif atomic_covered_l1 and atomic_covered_l2 and not (composition_novel_l1 or composition_novel_l2):
        bucket = "NEW_INSTANCE_OLD_SIGNATURE_FAMILY"
    else:
        bucket = provisional

    missing_priority = []
    for k, v in sigs.items():
        if v["n_novel_vs_seen"] > 0:
            missing_priority.append({"cell": k, "novel": v["novel_signatures"][:5]})
    if unknown_l2:
        missing_priority.append(
            {
                "cell": "layer2_normalization",
                "novel": [r["raw"] for r in unknown_l2],
                "note": "Cannot invent facts to force L2 coverage",
            }
        )

    return {
        "schema": "s8_signature_feedback_v2",
        "program_id": draft["graph_id"],
        "provisional_label_before_recompute": provisional,
        "seen_atomic_layer1": sorted(seen_l1),
        "seen_atomic_layer2": sorted(seen_l2),
        "draft_layer1": sorted(draft_l1),
        "draft_layer2_raw": sorted(draft_l2_raw),
        "layer2_normalization": l2_norm,
        "normalized_layer2": sorted(x for x in normalized_l2 if x),
        "unseen_or_unknown_layer2": [r["raw"] for r in unknown_l2],
        "atomic_covered_in_seen_layer1": atomic_covered_l1,
        "atomic_covered_in_seen_layer2": atomic_covered_l2,
        "layer1_coverage_does_not_imply_layer2": True,
        "composition_novel_layer1": composition_novel_l1,
        "composition_novel_layer2": composition_novel_l2,
        "gates": gates,
        "bucket": bucket,
        "atomic_covered_ood_candidate": atomic_covered_ood,
        "freeze_unseen": False,
        "subgraph_audit": sigs,
        "missing_structure_priority_hint": missing_priority,
        "note": "Priority hints must not cause fabrication of video facts",
    }
