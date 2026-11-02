#!/usr/bin/env python3
"""Deterministic structure / isolation checks for approved program graphs.

Does NOT assign Seen/Unseen/Gold. Does NOT mutate scientific classifications.
Does NOT auto-merge scientifically unapproved operator aliases.
"""
from __future__ import annotations

import itertools
import json
from collections import Counter, defaultdict
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
        and len(g.get("nodes") or []) > 0
    )


def _canon_json(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)


def _norm_list(v: Any) -> tuple:
    if v is None:
        return tuple()
    if isinstance(v, (list, tuple)):
        return tuple(sorted(_canon_json(i) for i in v))
    return (_canon_json(v),)


def _time_conditions_key(node_or_edge_field: Any) -> str:
    """Canonicalize confirmed time constraints; pending markers remain explicit."""
    return _canon_json(node_or_edge_field)


def node_signature(n: dict) -> tuple:
    """Typed node signature independent of node_id.

    Operator aliases are NOT normalized: types compared as exact strings.
    """
    return (
        n.get("operator_type"),
        _norm_list(n.get("inputs")),
        _norm_list(n.get("outputs")),
        n.get("clip_role"),
        _time_conditions_key(n.get("time_conditions")),
    )


def _first_node_vocab(g: dict) -> str | None:
    if g.get("operator_vocab_version"):
        return g.get("operator_vocab_version")
    for n in g.get("nodes") or []:
        if n.get("operator_vocab_version"):
            return n["operator_vocab_version"]
    return None


def _node_type_multiset(g: dict) -> Counter:
    return Counter(n.get("operator_type") for n in g.get("nodes") or [])


def _edge_label(e: dict, id_to_sig: dict[str, tuple]) -> tuple:
    return (
        id_to_sig.get(e.get("from_node")),
        id_to_sig.get(e.get("to_node")),
        e.get("dependency_kind"),
        _time_conditions_key(e.get("required_time_condition")),
    )


def _edge_multiset_by_signature(g: dict) -> Counter:
    id_to_sig = {n["node_id"]: node_signature(n) for n in g.get("nodes") or []}
    return Counter(_edge_label(e, id_to_sig) for e in g.get("edges") or [])


def find_node_bijections(g1: dict, g2: dict) -> list[dict[str, str]]:
    """Return all signature-consistent bijections mapping g1 node_id -> g2 node_id."""
    nodes1 = list(g1.get("nodes") or [])
    nodes2 = list(g2.get("nodes") or [])
    if len(nodes1) != len(nodes2):
        return []
    by_sig1: dict[tuple, list[str]] = defaultdict(list)
    by_sig2: dict[tuple, list[str]] = defaultdict(list)
    for n in nodes1:
        by_sig1[node_signature(n)].append(n["node_id"])
    for n in nodes2:
        by_sig2[node_signature(n)].append(n["node_id"])
    if set(by_sig1) != set(by_sig2):
        return []
    for sig in by_sig1:
        if len(by_sig1[sig]) != len(by_sig2[sig]):
            return []

    sigs = list(by_sig1.keys())
    # Build cartesian product of permutations within each signature class
    per_sig_maps = []
    for sig in sigs:
        left = by_sig1[sig]
        right = by_sig2[sig]
        per_sig_maps.append([dict(zip(left, perm)) for perm in itertools.permutations(right)])

    bijections: list[dict[str, str]] = []
    for combo in itertools.product(*per_sig_maps):
        m: dict[str, str] = {}
        for part in combo:
            m.update(part)
        bijections.append(m)
    return bijections


def edges_match_under_bijection(g1: dict, g2: dict, bij: dict[str, str]) -> bool:
    def edge_key(e: dict, remap: dict[str, str] | None = None) -> tuple:
        frm = e.get("from_node")
        to = e.get("to_node")
        if remap is not None:
            frm = remap.get(frm, frm)
            to = remap.get(to, to)
        return (frm, to, e.get("dependency_kind"), _time_conditions_key(e.get("required_time_condition")))

    c1 = Counter(edge_key(e, bij) for e in g1.get("edges") or [])
    c2 = Counter(edge_key(e, None) for e in g2.get("edges") or [])
    return c1 == c2


def full_digraph_equivalent(g1: dict, g2: dict) -> dict[str, Any]:
    """Node-ID-independent typed directed-graph equivalence.

    Checks exact match of:
      - operator_type (no unapproved alias merging)
      - inputs / outputs
      - clip_role
      - time_conditions on nodes
      - directed dependency edges (kind + required_time_condition) under a signature-consistent bijection
    """
    out: dict[str, Any] = {
        "check": "full_directed_graph_equivalence",
        "record_ids": [g1.get("graph_id"), g2.get("graph_id")],
        "vocab_versions": [_first_node_vocab(g1), _first_node_vocab(g2)],
        "status": None,
        "equivalent": False,
        "basis": [],
        "matching_mode": "typed_digraph_isomorphism_node_id_independent",
    }
    if g1.get("is_demo") or g2.get("is_demo") or g1.get("user_confirmation_status") == DEMO or g2.get("user_confirmation_status") == DEMO:
        out["status"] = "REFUSED_DEMO_GRAPH"
        out["basis"].append("Demo graphs are excluded from scientific equivalence.")
        return out
    if not _is_approved(g1) or not _is_approved(g2):
        out["status"] = "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION"
        out["basis"].append("One or both graphs lack USER_APPROVED_STRUCTURED_GRAPH with nodes.")
        return out
    v1, v2 = out["vocab_versions"]
    if v1 != v2:
        out["status"] = "NOT_EQUIVALENT_VOCAB_MISMATCH"
        out["basis"].append(f"operator_vocab_version mismatch: {v1!r} vs {v2!r}")
        return out

    bijections = find_node_bijections(g1, g2)
    if not bijections:
        out["status"] = "NOT_EQUIVALENT_NODE_SIGNATURES"
        out["basis"].append("No signature-consistent node bijection (type/io/clip_role/time_conditions).")
        out["operator_multiset_equal"] = _node_type_multiset(g1) == _node_type_multiset(g2)
        out["operator_set_equal"] = set(_node_type_multiset(g1)) == set(_node_type_multiset(g2))
        return out

    for bij in bijections:
        if edges_match_under_bijection(g1, g2, bij):
            out["status"] = "EQUIVALENT"
            out["equivalent"] = True
            out["basis"].append(
                "Found signature-consistent node bijection preserving directed edges, dependency kinds, and time conditions."
            )
            out["example_bijection"] = bij
            return out

    out["status"] = "NOT_EQUIVALENT_EDGES"
    out["basis"].append("Node signatures match under some bijection(s), but directed edges/time constraints do not.")
    out["candidate_bijection_count"] = len(bijections)
    return out


def operator_set_overlap(g1: dict, g2: dict) -> dict[str, Any]:
    """Atomic operator overlap only — NEVER full-graph equivalence."""
    out = {
        "check": "atomic_operator_set_overlap",
        "record_ids": [g1.get("graph_id"), g2.get("graph_id")],
        "status": None,
        "is_full_graph_equivalence": False,
        "warning": "Operator-set coincidence must not be treated as directed-graph equivalence. No alias merging.",
    }
    if not _is_approved(g1) or not _is_approved(g2):
        out["status"] = "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION"
        return out
    s1 = set(_node_type_multiset(g1).keys())
    s2 = set(_node_type_multiset(g2).keys())
    out["status"] = "OK"
    out["operators_left"] = sorted(x for x in s1 if x is not None)
    out["operators_right"] = sorted(x for x in s2 if x is not None)
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
    e1 = _edge_multiset_by_signature(g1)
    e2 = _edge_multiset_by_signature(g2)
    inter = e1 & e2
    out["status"] = "OK"
    out["signature_labeled_edge_intersection"] = {str(k): int(v) for k, v in inter.items()}
    out["only_left"] = {str(k): int(e1[k] - inter.get(k, 0)) for k in e1 if e1[k] > inter.get(k, 0)}
    out["only_right"] = {str(k): int(e2[k] - inter.get(k, 0)) for k in e2 if e2[k] > inter.get(k, 0)}
    out["full_signature_edge_multiset_equal"] = e1 == e2
    out["node_type_multiset_equal"] = _node_type_multiset(g1) == _node_type_multiset(g2)
    return out


def video_uid_cross_check(records: list[dict], train_ids: set[str] | None = None, test_ids: set[str] | None = None) -> dict[str, Any]:
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
    out = {
        "check": "video_id_uid_cross_check",
        "status": "OK",
        "duplicate_qa_uids": {u: ids for u, ids in by_uid.items() if len(ids) > 1},
        "videos_with_multiple_records": {v: ids for v, ids in by_video.items() if len(ids) > 1},
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
    out = {
        "check": "approved_seen_train_vs_unseen_target_conflict",
        "status": None,
        "conflicts": [],
        "basis": [],
        "note": "Candidate bucket labels do not alter a frozen training set; compare only explicitly provided approved graph lists.",
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
            "note": "Approved structured graphs alone do not make coverage computable without frozen Seen train pool and train-exposure evidence.",
        }
    return {"status": "COMPUTABLE_INTERFACE_READY", "code": "READY_BUT_NO_AUTO_FILL"}
