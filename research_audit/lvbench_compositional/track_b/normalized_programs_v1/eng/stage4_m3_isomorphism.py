#!/usr/bin/env python3
"""Stage-4 M3: directed connected induced subgraph signatures with true label-preserving isomorphism.

ID-independent canonical forms; duplicate operator labels handled by exhaustive
within-signature-class permutations (k<=3 is small).
"""
from __future__ import annotations

import itertools
from collections import Counter, defaultdict
from typing import Any, Iterable


MODES = ("ops", "ops_role", "ops_role_edge", "ops_role_edge_io")
LAYERS = ("layer1", "layer2")


def _role(n: dict) -> str:
    return str(n.get("normalized_clip_role") or n.get("raw_clip_role") or "")


def _kind(e: dict) -> str:
    return str(e.get("normalized_dependency_kind") or e.get("raw_dependency_kind") or "")


def _io_lists(n: dict) -> tuple[tuple, tuple]:
    inp = n.get("normalized_inputs")
    out = n.get("normalized_outputs")
    if inp is None:
        inp = n.get("raw_inputs") or []
    if out is None:
        out = n.get("raw_outputs") or []
    if not isinstance(inp, (list, tuple)):
        inp = [inp]
    if not isinstance(out, (list, tuple)):
        out = [out]
    return tuple(inp), tuple(out)


def node_label(n: dict, layer: str, mode: str) -> tuple:
    base = (n[layer],)
    if mode == "ops":
        return base
    # ops_role and stricter include role; dependency_kind is NEVER in node label
    return (n[layer], _role(n))


def undirected_adj(edges: list[dict]) -> dict[str, set[str]]:
    und: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        a, b = e["from_node"], e["to_node"]
        und[a].add(b)
        und[b].add(a)
    return und


def weakly_connected(subset: set[str], und: dict[str, set[str]]) -> bool:
    if not subset:
        return False
    start = next(iter(subset))
    seen = {start}
    stack = [start]
    while stack:
        u = stack.pop()
        for v in und[u]:
            if v in subset and v not in seen:
                seen.add(v)
                stack.append(v)
    return seen == subset


def induced_edges(edges: list[dict], subset: set[str]) -> list[dict]:
    return [e for e in edges if e["from_node"] in subset and e["to_node"] in subset]


def alpha_rename_io(
    ordered_nids: list[str], by_id: dict[str, dict]
) -> tuple[tuple, dict[str, str]]:
    """Rename I/O variable strings by first-appearance order under ordered nodes.

    Non-string tokens are left as canonical JSON-ish literals with a typed prefix.
    Returns ((per-node (inputs, outputs) with renamed vars), rename_map).
    """
    rename: dict[str, str] = {}
    next_i = 0

    def canon_token(tok: Any) -> str:
        nonlocal next_i
        if isinstance(tok, str):
            if tok not in rename:
                rename[tok] = f"v{next_i}"
                next_i += 1
            return rename[tok]
        return f"lit:{tok!r}"

    encoded = []
    for nid in ordered_nids:
        inp, out = _io_lists(by_id[nid])
        encoded.append((tuple(canon_token(t) for t in inp), tuple(canon_token(t) for t in out)))
    return tuple(encoded), rename


def canonical_signature(
    subset: set[str],
    by_id: dict[str, dict],
    induced: list[dict],
    layer: str,
    mode: str,
) -> tuple:
    """Lexicographically minimal encoding over label-preserving node bijections to 0..k-1."""
    nids = list(subset)
    labels = {nid: node_label(by_id[nid], layer, mode) for nid in nids}
    # Partition by label
    groups: dict[tuple, list[str]] = defaultdict(list)
    for nid in nids:
        groups[labels[nid]].append(nid)

    # Fixed order of label classes (lexicographic)
    label_order = sorted(groups.keys())
    # For each class, we permute members
    class_lists = [groups[lab] for lab in label_order]

    include_edge_kind = mode in ("ops_role_edge", "ops_role_edge_io")
    include_io = mode == "ops_role_edge_io"

    best: tuple | None = None
    for combo in itertools.product(
        *[list(itertools.permutations(lst)) for lst in class_lists]
    ):
        ordered: list[str] = []
        for perm in combo:
            ordered.extend(perm)
        local = {nid: i for i, nid in enumerate(ordered)}
        # Node label sequence in local order (redundant with partition but explicit)
        node_part = tuple(labels[nid] for nid in ordered)
        edge_part = []
        for e in induced:
            frm, to = local[e["from_node"]], local[e["to_node"]]
            if include_edge_kind:
                edge_part.append((frm, to, _kind(e)))
            else:
                edge_part.append((frm, to))
        edge_part_t = tuple(sorted(edge_part))
        if include_io:
            io_part, _ = alpha_rename_io(ordered, by_id)
            cand = (node_part, edge_part_t, io_part)
        else:
            cand = (node_part, edge_part_t)
        if best is None or cand < best:
            best = cand
    assert best is not None
    return best


def enumerate_subgraphs(
    g: dict, size: int, layer: str, mode: str
) -> list[dict]:
    """Return list of {nodes, signature, occurrence} for each induced connected subgraph."""
    nodes = g["nodes"]
    edges = g["edges"]
    by_id = {n["node_id"]: n for n in nodes}
    ids = [n["node_id"] for n in nodes]
    und = undirected_adj(edges)
    out = []
    if len(ids) < size:
        return out
    for combo in itertools.combinations(ids, size):
        subset = set(combo)
        if not weakly_connected(subset, und):
            continue
        induced = induced_edges(edges, subset)
        if size >= 2 and len(induced) == 0:
            continue
        sig = canonical_signature(subset, by_id, induced, layer, mode)
        out.append(
            {
                "nodes": tuple(sorted(subset)),
                "signature": sig,
                "n_edges": len(induced),
            }
        )
    return out


def pool_signatures(graphs: dict[str, dict], ids: list[str], size: int, layer: str, mode: str):
    """Return unique set, occurrence counter, and per-graph occurrence lists with witnesses."""
    unique = set()
    occ = Counter()
    per_graph_occ: dict[str, list[dict]] = {}
    for gid in ids:
        items = enumerate_subgraphs(graphs[gid], size, layer, mode)
        per_graph_occ[gid] = items
        for it in items:
            unique.add(it["signature"])
            occ[it["signature"]] += 1
    return unique, occ, per_graph_occ


def coverage_report(
    graphs: dict[str, dict],
    seen_ids: list[str],
    unseen_ids: list[str],
    size: int,
    layer: str,
    mode: str,
) -> dict:
    seen_u, seen_occ, seen_pg = pool_signatures(graphs, seen_ids, size, layer, mode)
    un_u, un_occ, un_pg = pool_signatures(graphs, unseen_ids, size, layer, mode)
    inter = seen_u & un_u

    # occurrence-weighted: each Unseen occurrence matches if its signature ∈ Seen unique
    matched_occ = sum(c for sig, c in un_occ.items() if sig in seen_u)
    total_occ = sum(un_occ.values())

    witnesses = {}
    for ug in unseen_ids:
        w = []
        for it in un_pg[ug]:
            sig = it["signature"]
            if sig not in seen_u:
                w.append(
                    {
                        "nodes": it["nodes"],
                        "matched": False,
                        "matched_seen_graphs": [],
                    }
                )
                continue
            matched_seen = [
                sg
                for sg in seen_ids
                if any(x["signature"] == sig for x in seen_pg[sg])
            ]
            w.append(
                {
                    "nodes": it["nodes"],
                    "matched": True,
                    "matched_seen_graphs": matched_seen,
                    "signature_digest": _sig_digest(sig),
                }
            )
        witnesses[ug] = w

    return {
        "layer": layer,
        "mode": mode,
        "size": size,
        "seen_unique": len(seen_u),
        "unseen_unique": len(un_u),
        "intersection_unique": len(inter),
        "unique_coverage_ratio": (len(inter) / len(un_u)) if un_u else None,
        "unique_fraction": f"{len(inter)}/{len(un_u)}" if un_u else "N/A",
        "unseen_occurrences": total_occ,
        "matched_occurrences": matched_occ,
        "occurrence_coverage_ratio": (matched_occ / total_occ) if total_occ else None,
        "occurrence_fraction": f"{matched_occ}/{total_occ}" if total_occ else "N/A",
        "denominator_unique": "unique_unseen_subgraph_signatures",
        "denominator_occurrence": "unseen_subgraph_occurrences",
        "io_policy": (
            "alpha_renaming_by_first_appearance_under_canonical_node_order"
            if mode == "ops_role_edge_io"
            else "io_not_in_signature"
        ),
        "ops_role_excludes_dependency_kind": mode in ("ops", "ops_role"),
        "witnesses_per_unseen": witnesses,
    }


def _sig_digest(sig: tuple) -> str:
    # short stable digest for reports
    import hashlib
    import json

    blob = json.dumps(sig, sort_keys=False, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def self_check_duplicate_labels() -> dict:
    """Unit geometry: two nodes same Layer2 label, one edge — signature ID-independent."""
    g1 = {
        "nodes": [
            {"node_id": "a", "layer1": "X", "layer2": "Op", "normalized_clip_role": "A"},
            {"node_id": "b", "layer1": "X", "layer2": "Op", "normalized_clip_role": "B"},
        ],
        "edges": [
            {
                "from_node": "a",
                "to_node": "b",
                "normalized_dependency_kind": "data",
            }
        ],
    }
    g2 = {
        "nodes": [
            {"node_id": "z", "layer1": "X", "layer2": "Op", "normalized_clip_role": "B"},
            {"node_id": "y", "layer1": "X", "layer2": "Op", "normalized_clip_role": "A"},
        ],
        "edges": [
            {
                "from_node": "y",
                "to_node": "z",
                "normalized_dependency_kind": "data",
            }
        ],
    }
    s1 = enumerate_subgraphs(g1, 2, "layer2", "ops_role")[0]["signature"]
    s2 = enumerate_subgraphs(g2, 2, "layer2", "ops_role")[0]["signature"]
    # same structure with swapped ids but same role→edge pattern under isomorphism
    s1_ops = enumerate_subgraphs(g1, 2, "layer2", "ops")[0]["signature"]
    s2_ops = enumerate_subgraphs(g2, 2, "layer2", "ops")[0]["signature"]
    return {
        "ops_equal_under_id_permutation": s1_ops == s2_ops,
        "ops_role_equal_for_isomorphic_role_edge": s1 == s2,
        "sig_ops": s1_ops,
        "sig_ops_role": s1,
    }
