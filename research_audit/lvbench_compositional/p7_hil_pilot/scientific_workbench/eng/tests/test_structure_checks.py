#!/usr/bin/env python3
"""Unit tests for deterministic structure checks."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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

DEMO = json.loads((ROOT.parent / "data" / "DEMO_STRUCTURED_GRAPHS.json").read_text(encoding="utf-8"))
LIB = json.loads((ROOT.parent / "data" / "PROGRAM_GRAPH_LIBRARY_v1.json").read_text(encoding="utf-8"))


def _approve(g: dict) -> dict:
    x = copy.deepcopy(g)
    x["is_demo"] = False
    x["user_confirmation_status"] = APPROVED
    return x


class StructureChecksTest(unittest.TestCase):
    def test_pending_raw_records_not_auto_equivalent(self):
        r0, r1 = LIB["records"][0], LIB["records"][1]
        eq = full_digraph_equivalent(r0, r1)
        self.assertEqual(eq["status"], "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION")
        self.assertFalse(eq["equivalent"])

    def test_demo_refused_for_scientific_equivalence(self):
        g1, g2 = DEMO["graphs"][0], DEMO["graphs"][2]
        eq = full_digraph_equivalent(g1, g2)
        self.assertEqual(eq["status"], "REFUSED_DEMO_GRAPH")

    def test_approved_full_graph_match_and_mismatch(self):
        a = _approve(DEMO["graphs"][0])
        b = _approve(DEMO["graphs"][2])  # clone
        c = _approve(DEMO["graphs"][1])  # different query op
        eq_ok = full_digraph_equivalent(a, b)
        self.assertTrue(eq_ok["equivalent"])
        self.assertEqual(eq_ok["status"], "EQUIVALENT")
        eq_bad = full_digraph_equivalent(a, c)
        self.assertFalse(eq_bad["equivalent"])
        self.assertIn(eq_bad["status"], {"NOT_EQUIVALENT_NODE_MAP", "NOT_EQUIVALENT_EDGES"})

    def test_operator_set_overlap_is_not_full_equivalence(self):
        a = _approve(DEMO["graphs"][0])
        c = _approve(DEMO["graphs"][1])
        ov = operator_set_overlap(a, c)
        self.assertEqual(ov["status"], "OK")
        self.assertFalse(ov["is_full_graph_equivalence"])
        self.assertIn("IdentifyPerson", ov["intersection"])
        self.assertIn("QueryAction", ov["only_left"])
        self.assertIn("QueryAttribute", ov["only_right"])

    def test_subgraph_edge_overlap(self):
        a = _approve(DEMO["graphs"][0])
        c = _approve(DEMO["graphs"][1])
        sg = subgraph_and_edge_overlap(a, c)
        self.assertEqual(sg["status"], "OK")
        self.assertFalse(sg["is_full_graph_equivalence"])
        self.assertTrue(len(sg["type_labeled_edge_intersection"]) >= 1)

    def test_video_uid_cross_check_without_split(self):
        res = video_uid_cross_check(LIB["records"])
        self.assertEqual(res["train_test_video_leakage"], "N_A_NO_USER_APPROVED_TRAIN_TEST_SPLIT")
        self.assertIn("VTCDQYYKA9o", res["videos_with_multiple_records"])

    def test_video_uid_leakage_with_explicit_split(self):
        # Engineering fact when a hypothetical approved split is supplied
        records = [
            {"graph_id": "g1", "qa_uid": "u1", "video_id": "V"},
            {"graph_id": "g2", "qa_uid": "u2", "video_id": "V"},
        ]
        res = video_uid_cross_check(records, train_ids={"g1"}, test_ids={"g2"})
        self.assertEqual(res["train_test_video_leakage"], ["V"])

    def test_bucket_label_change_does_not_alter_train_pool_argument(self):
        # Passing empty train pool remains not computable even if library has pre-Unseen labels
        conflict = seen_train_vs_unseen_target_conflict([], [])
        self.assertEqual(conflict["status"], "NOT_COMPUTABLE_MISSING_APPROVED_POOLS")
        pre_unseen = [r for r in LIB["records"] if r.get("user_preclassification_bucket") == "Unseen"]
        self.assertGreaterEqual(len(pre_unseen), 1)
        # preclassification alone cannot create approved train/unseen pools
        conflict2 = seen_train_vs_unseen_target_conflict(pre_unseen, pre_unseen)
        self.assertEqual(conflict2["status"], "NOT_COMPUTABLE_PENDING_STRUCTURED_CONFIRMATION")

    def test_coverage_not_computable_without_prereqs(self):
        st = coverage_status(
            has_normalized_graphs=False,
            has_frozen_train_pool=False,
            has_valid_train_evidence=False,
        )
        self.assertEqual(st["status"], "尚不可计算")

    def test_seen_unseen_conflict_when_approved_pools_collide(self):
        a = _approve(DEMO["graphs"][0])
        b = _approve(DEMO["graphs"][2])
        conflict = seen_train_vs_unseen_target_conflict([a], [b])
        self.assertEqual(conflict["status"], "CONFLICT")
        self.assertEqual(len(conflict["conflicts"]), 1)


if __name__ == "__main__":
    unittest.main()
