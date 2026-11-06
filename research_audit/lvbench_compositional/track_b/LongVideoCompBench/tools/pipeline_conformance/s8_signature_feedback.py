#!/usr/bin/env python3
"""S8: composition structure feedback via normalized_programs_v1.

Reuses Layer1/Layer2 mapping and directed 2/3-node subgraph signatures.
Does not invent video facts to fill missing signatures.
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


def load_seen_graphs() -> dict[str, dict]:
    graphs = {}
    gdir = NP / "graphs"
    for gid in SEEN:
        p = gdir / f"{gid}.json"
        if p.exists():
            graphs[gid] = json.loads(p.read_text())
    return graphs


def draft_graph_to_normalized(program_graph: dict[str, Any]) -> dict[str, Any]:
    """Convert S3–S5 draft graph into normalized_programs-like shape for subgraph enum."""
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
            }
        )
    return {
        "graph_id": program_graph.get("program_id") or "draft",
        "nodes": nodes,
        "edges": edges,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
    }


def audit_draft_against_seen(program_graph: dict[str, Any]) -> dict[str, Any]:
    seen = load_seen_graphs()
    draft = draft_graph_to_normalized(program_graph)
    seen_l1 = {n["layer1"] for g in seen.values() for n in g["nodes"]}
    seen_l2 = {n["layer2"] for g in seen.values() for n in g["nodes"]}

    draft_l1 = {n["layer1"] for n in draft["nodes"]}
    draft_l2 = {n["layer2"] for n in draft["nodes"]}
    atomic_covered_l1 = draft_l1 <= seen_l1
    # Layer2 may use provisional names not in Seen vocab — treat as covered if L1 covered
    # and ops are bind/locate/query family known in Seen via L1
    unseen_l2 = sorted(draft_l2 - seen_l2)

    sigs = {}
    for size in (2, 3):
        for layer, mode in (("layer1", "ops"), ("layer2", "ops")):
            key = f"{size}node_{layer}_{mode}"
            items = enumerate_subgraphs(draft, size, layer, mode)
            seen_u, _, _ = pool_signatures(seen, list(seen.keys()), size, layer, mode)
            novel = [it for it in items if it["signature"] not in seen_u]
            sigs[key] = {
                "n_subgraphs": len(items),
                "n_novel_vs_seen": len(novel),
                "novel_signatures": [it["signature"] for it in novel[:20]],
                "all_signatures": [it["signature"] for it in items],
            }

    # Classification
    if not atomic_covered_l1:
        bucket = "ATOMIC_NOVELTY_OR_UNKNOWN_CONTROL"
        atomic_covered_ood = False
    elif any(sigs[k]["n_novel_vs_seen"] > 0 for k in sigs if "layer1" in k):
        bucket = "ATOMIC_COVERED_COMPOSITION_OOD_CANDIDATE"
        atomic_covered_ood = True
    else:
        bucket = "NEW_INSTANCE_OLD_SIGNATURE_FAMILY"
        atomic_covered_ood = False

    missing_priority = []
    for k, v in sigs.items():
        if v["n_novel_vs_seen"] == 0 and v["n_subgraphs"] > 0:
            continue
        if v["n_novel_vs_seen"] > 0:
            missing_priority.append({"cell": k, "novel": v["novel_signatures"][:5]})

    return {
        "schema": "s8_signature_feedback_v1",
        "program_id": draft["graph_id"],
        "seen_atomic_layer1": sorted(seen_l1),
        "draft_layer1": sorted(draft_l1),
        "draft_layer2": sorted(draft_l2),
        "unseen_layer2_labels": unseen_l2,
        "atomic_covered_in_seen_layer1": atomic_covered_l1,
        "bucket": bucket,
        "atomic_covered_ood_candidate": atomic_covered_ood,
        "freeze_unseen": False,
        "subgraph_audit": sigs,
        "missing_structure_priority_hint": missing_priority,
        "note": "Priority hints must not cause fabrication of video facts",
    }
