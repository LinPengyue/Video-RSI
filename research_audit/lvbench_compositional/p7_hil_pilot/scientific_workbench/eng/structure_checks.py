#!/usr/bin/env python3
"""Deterministic structure / isolation checks for approved program graphs.

Does NOT assign Seen/Unseen/Gold. Does NOT mutate scientific classifications.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


APPROVED = "USER_APPROVED_STRUCTURED_GRAPH"
PENDING = "PENDING_STRUCTURED_CONFIRMATION"
DEMO = "DEMO_NOT_SCIENTIFIC"


def _is_approved(g: dict) -> bool:
    return (
        g.get("user_confirmation_status") == APPROVED
        and not g.get("is_demo", False)
        and isinstance(g.get("nodes"), list)
        and isinstance(g.get("edges"), list)
    )


def _node_type_multiset(g: dict) -> Counter:
    return Counter(n.get("operator_type") for n in g.get("nodes") or [])


def _edge_multiset(g: dict) -> Counter:
    # Edges keyed by (from_type, to_type, dependency_kind) under node_id->type map.
    # For exact digraph equality we also expose id-based form when node_ids align
    # via explicit certified mapping; default uses type-labeled edges after sorting
    # node ids within equal type classes only when bijection is unique.
    id_to_type = {n["node_id"]: n.get("operator_type") for n in g.get("nodes") or []}
    c = Counter()
    for e in g.get("edges") or []:
        c[(id_to_type.get(e.get("from_node")), id_to_type.get(e.get("to_node")), e.get("dependency_kind"))] += 1
    return c


def _id_edge_multiset(g: dict) -> Counter:
    return Counter((e.get("from_node"), e.get("to_node"), e.get("dependency_kind")) for e in g.get("edges") or [])


def _node_id_type_map(g: dict) -> dict:
    return {n["node_id"]: n.get("operator_type") for n in g.get("nodes") or []}


def full_digraph_equivalent(g1: dict, g2: dict) -> dict[str, Any]:
    """Exact full directed program graph equivalence under approved graphs.

    Requires identical node_id sets with identical operator_type per id OR a
    unique type-consistent rename is not auto-invented: we require identical
    (node_id, operator_type) pairs and identical id-based directed edges.
    Operator-set-only match is reported separately and is NOT equivalence.
    """
    out = {
        "check": "full_directed_graph_equivalence",
        "record_ids": [g1.get("graph_id"), g2.get("graph_id")],
        "vocab_versions": [
            g1.get("operator_vocab_version") or _first_node_vocab(g1),
            g2.get("operator_vocab_version") or _first_node_vocab(g2),
        ],
        "status": None,
        "equivalent": False,
        "basis": [],
    }
    if g1.get("is_demo") or g2.get("is_demo"):
        out["status"] = "REFUSED_DEMO_GRAPH"
        out["basis"].append("Demo graphs are excluded from scientific equivalence.")
        return out
    if not _is_approved(g1) or not _is_approved(g2):
        out["status"] = "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION"
        out["basis"].append("One or both graphs lack USER_APPROVED_STRUCTURED_GRAPH.")
        return out
    v1 = out["vocab_versions"][0]
    v2 = out["vocab_versions"][1]
    if v1 != v2:
        out["status"] = "NOT_EQUIVALENT_VOCAB_MISMATCH"
        out["basis"].append(f"operator_vocab_version mismatch: {v1!r} vs {v2!r}")
        return out
    m1 = _node_id_type_map(g1)
    m2 = _node_id_type_map(g2)
    if m1 != m2:
        out["status"] = "NOT_EQUIVALENT_NODE_MAP"
        out["basis"].append("node_id→operator_type maps differ (no silent remapping).")
        # still report operator-set coincidence without calling it equivalence
        out["operator_set_equal"] = set(m1.values()) == set(m2.values())
        out["operator_multiset_equal"] = _node_type_multiset(g1) == _node_type_multiset(g2)
        return out
    e1 = _id_edge_multiset(g1)
    e2 = _id_edge_multiset(g2)
    if e1 != e2:
        out["status"] = "NOT_EQUIVALENT_EDGES"
        out["basis"].append("directed edge multisets differ")
        out["operator_multiset_equal"] = True
        return out
    out["status"] = "EQUIVALENT"
    out["equivalent"] = True
    out["basis"].append("Identical approved node_id→type map and directed edge multiset under same vocab version.")
    return out


def _first_node_vocab(g: dict) -> str | None:
    for n in g.get("nodes") or []:
        if n.get("operator_vocab_version"):
            return n["operator_vocab_version"]
    return g.get("operator_vocab_version")


def operator_set_overlap(g1: dict, g2: dict) -> dict[str, Any]:
    """Atomic operator overlap only — NEVER full-graph equivalence."""
    out = {
        "check": "atomic_operator_set_overlap",
        "record_ids": [g1.get("graph_id"), g2.get("graph_id")],
        "status": None,
        "is_full_graph_equivalence": False,
        "warning": "Operator-set coincidence must not be treated as directed-graph equivalence.",
    }
    if not _is_approved(g1) or not _is_approved(g2):
        out["status"] = "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION"
        return out
    s1 = set(_node_type_multiset(g1).elements())
    # Counter.elements expands multiplicity; for set overlap use keys
    s1 = set(_node_type_multiset(g1).keys())
    s2 = set(_node_type_multiset(g2).keys())
    out["status"] = "OK"
    out["operators_left"] = sorted(s1)
    out["operators_right"] = sorted(s2)
    out["intersection"] = sorted(s1 & s2)
    out["only_left"] = sorted(s1 - s2)
    out["only_right"] = sorted(s2 - s1)
    out["multiset_equal"] = _node_type_multiset(g1) == _node_type_multiset(g2)
    return out


def subgraph_and_edge_overlap(g1: dict, g2: dict) -> dict[str, Any]:
    out = {
        "check": "subgraph_and_dependency_edge_overlap",
        "record_ids": [g1.get("graph_id"), g2.get("graph_id")],
        "status": None,
        "is_full_graph_equivalence": False,
    }
    if not _is_approved(g1) or not _is_approved(g2):
        out["status"] = "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION"
        return out
    e1 = _edge_multiset(g1)
    e2 = _edge_multiset(g2)
    inter = e1 & e2
    out["status"] = "OK"
    out["type_labeled_edge_intersection"] = {str(k): int(v) for k, v in inter.items()}
    out["only_left"] = {str(k): int(e1[k]) for k in e1 if k not in inter or e1[k] > inter[k]}
    out["only_right"] = {str(k): int(e2[k]) for k in e2 if k not in inter or e2[k] > inter[k]}
    out["full_type_edge_multiset_equal"] = e1 == e2
    out["node_type_multiset_equal"] = _node_type_multiset(g1) == _node_type_multiset(g2)
    return out


def video_uid_cross_check(records: list[dict], train_ids: set[str] | None = None, test_ids: set[str] | None = None) -> dict[str, Any]:
    """Engineering isolation facts. Does not assign split membership scientifically."""
    by_video: dict[str, list[str]] = {}
    by_uid: dict[str, list[str]] = {}
    for r in records:
        vid = r.get("video_id")
        uid = r.get("qa_uid") or r.get("graph_id")
        rid = r.get("graph_id") or uid
        if vid:
            by_video.setdefault(vid, []).append(rid)
        if uid:
            by_uid.setdefault(uid, []).append(rid)
    dup_uid = {u: ids for u, ids in by_uid.items() if len(ids) > 1}
    multi_video = {v: ids for v, ids in by_video.items() if len(ids) > 1}
    out = {
        "check": "video_id_uid_cross_check",
        "status": "OK",
        "duplicate_qa_uids": dup_uid,
        "videos_with_multiple_records": multi_video,
        "record_ids": [r.get("graph_id") for r in records],
        "approved_train_test_split_provided": train_ids is not None and test_ids is not None,
    }
    if train_ids is None or test_ids is None:
        out["train_test_video_leakage"] = "N_A_NO_USER_APPROVED_TRAIN_TEST_SPLIT"
        out["train_test_uid_leakage"] = "N_A_NO_USER_APPROVED_TRAIN_TEST_SPLIT"
        return out
    train_vids = {r["video_id"] for r in records if r.get("graph_id") in train_ids or r.get("qa_uid") in train_ids}
    test_vids = {r["video_id"] for r in records if r.get("graph_id") in test_ids or r.get("qa_uid") in test_ids}
    train_uids = {r.get("qa_uid") for r in records if r.get("graph_id") in train_ids or r.get("qa_uid") in train_ids}
    test_uids = {r.get("qa_uid") for r in records if r.get("graph_id") in test_ids or r.get("qa_uid") in test_ids}
    out["train_test_video_leakage"] = sorted(train_vids & test_vids)
    out["train_test_uid_leakage"] = sorted((train_uids & test_uids) - {None})
    return out


def seen_train_vs_unseen_target_conflict(
    seen_train_graphs: list[dict],
    unseen_target_graphs: list[dict],
) -> dict[str, Any]:
    """Flag full-graph equivalence collisions between approved Seen-train and Unseen-target graphs."""
    out = {
        "check": "approved_seen_train_vs_unseen_target_conflict",
        "status": None,
        "conflicts": [],
        "basis": [],
        "note": "Changing a candidate bucket label must not by itself alter a frozen training set; this check only compares explicitly provided approved graph lists.",
    }
    if not seen_train_graphs or not unseen_target_graphs:
        out["status"] = "NOT_COMPUTABLE_MISSING_APPROVED_POOLS"
        out["basis"].append("Need non-empty USER_APPROVED_STRUCTURED_GRAPH lists for both Seen-train and Unseen-target.")
        return out
    if any(not _is_approved(g) for g in seen_train_graphs + unseen_target_graphs):
        out["status"] = "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION"
        return out
    conflicts = []
    for s in seen_train_graphs:
        for u in unseen_target_graphs:
            eq = full_digraph_equivalent(s, u)
            if eq.get("equivalent"):
                conflicts.append({"seen_train": s.get("graph_id"), "unseen_target": u.get("graph_id"), "detail": eq})
    out["conflicts"] = conflicts
    out["status"] = "CONFLICT" if conflicts else "NO_FULL_GRAPH_CONFLICT"
    return out


def coverage_status(
    *,
    has_normalized_graphs: bool,
    has_frozen_train_pool: bool,
    has_valid_train_evidence: bool,
) -> dict[str, Any]:
    if not (has_normalized_graphs and has_frozen_train_pool and has_valid_train_evidence):
        return {
            "status": "尚不可计算",
            "code": "NOT_COMPUTABLE",
            "reasons": {
                "has_normalized_graphs": has_normalized_graphs,
                "has_frozen_train_pool": has_frozen_train_pool,
                "has_valid_train_evidence": has_valid_train_evidence,
            },
            "layers": {
                "user_confirmed_exists": "NOT_COMPUTABLE",
                "approved_as_train_sample": "NOT_COMPUTABLE",
                "controlled_train_exposure": "NOT_COMPUTABLE",
            },
        }
    return {"status": "COMPUTABLE_INTERFACE_READY", "code": "READY_BUT_NO_AUTO_FILL"}
