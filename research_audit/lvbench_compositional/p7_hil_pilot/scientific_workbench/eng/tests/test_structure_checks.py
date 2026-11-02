#!/usr/bin/env python3
"""Unit tests for deterministic structure checks (typed digraph isomorphism)."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = ROOT.parent
sys.path.insert(0, str(ROOT))
from structure_checks import (  # noqa: E402
    APPROVED,
    coverage_status,
    full_digraph_equivalent,
    operator_set_overlap,
    seen_train_vs_unseen_target_conflict,
    subgraph_and_edge_overlap,
    video_uid_cross_check,
)

DEMO = json.loads((WB / "data" / "DEMO_STRUCTURED_GRAPHS.json").read_text(encoding="utf-8"))
LIB = json.loads((WB / "data" / "PROGRAM_GRAPH_LIBRARY_v1.json").read_text(encoding="utf-8"))
APPROVED_DIR = WB / "data" / "approved_graphs_v0.2"


def _approve(g: dict) -> dict:
    x = copy.deepcopy(g)
    x["is_demo"] = False
    x["user_confirmation_status"] = APPROVED
    return x


def _load_approved(wid: str) -> dict:
    return json.loads((APPROVED_DIR / f"{wid}.json").read_text(encoding="utf-8"))


class StructureChecksTest(unittest.TestCase):
    def test_approved_v02_graphs_loaded(self):
        for wid in ["P7_R4_F2", "P7_VTCD_C2", "P7_TJR_R3", "P7_R4_F1"]:
            g = _load_approved(wid)
            self.assertEqual(g["user_confirmation_status"], APPROVED)
            self.assertEqual(g["structure_version"], "v0.2")
            self.assertFalse(g["formal_unseen"])
            self.assertFalse(g["formal_gold"])
            self.assertTrue(g["nodes"])
            self.assertTrue(g["edges"])

    def test_pending_raw_records_not_auto_equivalent(self):
        pending = [r for r in LIB["records"] if r.get("user_confirmation_status") != APPROVED]
        self.assertGreaterEqual(len(pending), 1)
        eq = full_digraph_equivalent(pending[0], pending[min(1, len(pending) - 1)])
        self.assertEqual(eq["status"], "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION")
        self.assertFalse(eq["equivalent"])

    def test_demo_refused_for_scientific_equivalence(self):
        g1, g2 = DEMO["graphs"][0], DEMO["graphs"][2]
        eq = full_digraph_equivalent(g1, g2)
        self.assertEqual(eq["status"], "REFUSED_DEMO_GRAPH")

    def test_node_rename_still_equivalent(self):
        g = _load_approved("P7_VTCD_C2")
        renamed = copy.deepcopy(g)
        mapping = {}
        for i, n in enumerate(renamed["nodes"]):
            new_id = f"renamed_{i}"
            mapping[n["node_id"]] = new_id
            n["node_id"] = new_id
        for e in renamed["edges"]:
            e["from_node"] = mapping[e["from_node"]]
            e["to_node"] = mapping[e["to_node"]]
            e["edge_id"] = e["edge_id"] + "_r"
        eq = full_digraph_equivalent(g, renamed)
        self.assertTrue(eq["equivalent"], eq)
        self.assertEqual(eq["status"], "EQUIVALENT")

    def test_clip_role_swap_not_equivalent(self):
        g = _load_approved("P7_TJR_R3")
        bad = copy.deepcopy(g)
        # swap clip roles on first two distinct-role nodes if possible
        roles = [(i, n.get("clip_role")) for i, n in enumerate(bad["nodes"])]
        a_idx = next(i for i, r in roles if r == "A")
        b_idx = next(i for i, r in roles if r == "B")
        bad["nodes"][a_idx]["clip_role"], bad["nodes"][b_idx]["clip_role"] = (
            bad["nodes"][b_idx]["clip_role"],
            bad["nodes"][a_idx]["clip_role"],
        )
        eq = full_digraph_equivalent(g, bad)
        self.assertFalse(eq["equivalent"])
        self.assertIn(eq["status"], {"NOT_EQUIVALENT_NODE_SIGNATURES", "NOT_EQUIVALENT_EDGES"})

    def test_dependency_edge_change_not_equivalent(self):
        g = _load_approved("P7_R4_F2")
        bad = copy.deepcopy(g)
        self.assertTrue(bad["edges"])
        bad["edges"][0]["dependency_kind"] = "temporal" if bad["edges"][0]["dependency_kind"] != "temporal" else "control"
        eq = full_digraph_equivalent(g, bad)
        self.assertFalse(eq["equivalent"])
        self.assertEqual(eq["status"], "NOT_EQUIVALENT_EDGES")

    def test_time_condition_change_not_equivalent(self):
        g = _load_approved("P7_VTCD_C2")
        bad = copy.deepcopy(g)
        # alter confirmed approx offset on B name node
        for n in bad["nodes"]:
            if n.get("operator_type") == "ReadNameGraphic":
                n["time_conditions"] = [{"kind": "playback_offset_approx", "clip_local_s_approx": 99, "status": "CHANGED"}]
                break
        eq = full_digraph_equivalent(g, bad)
        self.assertFalse(eq["equivalent"])
        self.assertEqual(eq["status"], "NOT_EQUIVALENT_NODE_SIGNATURES")

    def test_no_auto_alias_merge(self):
        g = _load_approved("P7_R4_F1")
        aliased = copy.deepcopy(g)
        for n in aliased["nodes"]:
            if n["operator_type"] == "DetectActionEvent":
                n["operator_type"] = "DetectAction"  # unapproved alias
        eq = full_digraph_equivalent(g, aliased)
        self.assertFalse(eq["equivalent"])

    def test_operator_set_overlap_is_not_full_equivalence(self):
        a = _approve(DEMO["graphs"][0])
        c = _approve(DEMO["graphs"][1])
        ov = operator_set_overlap(a, c)
        self.assertEqual(ov["status"], "OK")
        self.assertFalse(ov["is_full_graph_equivalence"])

    def test_subgraph_edge_overlap(self):
        a = _approve(DEMO["graphs"][0])
        c = _approve(DEMO["graphs"][1])
        sg = subgraph_and_edge_overlap(a, c)
        self.assertEqual(sg["status"], "OK")
        self.assertFalse(sg["is_full_graph_equivalence"])

    def test_video_uid_cross_check_without_split(self):
        res = video_uid_cross_check(LIB["records"])
        self.assertEqual(res["train_test_video_leakage"], "N_A_NO_USER_APPROVED_TRAIN_TEST_SPLIT")

    def test_bucket_label_change_does_not_alter_train_pool_argument(self):
        conflict = seen_train_vs_unseen_target_conflict([], [])
        self.assertEqual(conflict["status"], "NOT_COMPUTABLE_MISSING_APPROVED_POOLS")
        approved = [_load_approved(w) for w in ["P7_R4_F2", "P7_VTCD_C2"]]
        # Even with approved graphs, without designated Seen-train vs Unseen-target pools conflict is not auto-declared from preclassification
        conflict2 = seen_train_vs_unseen_target_conflict([], approved)
        self.assertEqual(conflict2["status"], "NOT_COMPUTABLE_MISSING_APPROVED_POOLS")

    def test_coverage_not_computable_with_approved_graphs_but_no_train_pool(self):
        st = coverage_status(
            has_normalized_graphs=True,
            has_frozen_train_pool=False,
            has_valid_train_evidence=False,
        )
        self.assertEqual(st["status"], "尚不可计算")

    def test_four_approved_not_pairwise_identical(self):
        graphs = [_load_approved(w) for w in ["P7_R4_F2", "P7_VTCD_C2", "P7_TJR_R3", "P7_R4_F1"]]
        for i in range(len(graphs)):
            for j in range(i + 1, len(graphs)):
                eq = full_digraph_equivalent(graphs[i], graphs[j])
                self.assertFalse(eq["equivalent"], f"{graphs[i]['graph_id']} vs {graphs[j]['graph_id']}")


if __name__ == "__main__":
    unittest.main()
