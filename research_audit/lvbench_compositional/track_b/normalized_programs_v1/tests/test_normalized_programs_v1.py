#!/usr/bin/env python3
"""Regression tests for Stage2 handoff ingest + Stage3 overlap gate."""
from __future__ import annotations

import json
import runpy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENG = ROOT / "eng"
HANDOFF = (
    ROOT
    / "chat_approved_handoff"
    / "track_b_stage2_chat_approved_handoff_v1.json"
)
EXPECTED_SHA = "c2b5aa2ae864dcefd1d71fd23cf6176de680a24b3ed463ba853b930bd5c345ed"


class TestNormalizedProgramsV1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old = sys.argv
        try:
            sys.argv = [str(ENG / "build_normalized_programs_v1.py")]
            runpy.run_path(str(ENG / "build_normalized_programs_v1.py"), run_name="__main__")
        finally:
            sys.argv = old
        cls.val = json.loads((ROOT / "validation_report.json").read_text())
        cls.overlap = json.loads((ROOT / "overlap_metrics.json").read_text())
        cls.mapping = json.loads((ROOT / "operator_mapping_v1.json").read_text())

    def test_handoff_sha(self):
        import hashlib

        digest = hashlib.sha256(HANDOFF.read_bytes()).hexdigest()
        self.assertEqual(digest, EXPECTED_SHA)

    def test_stage2_pass_60_54(self):
        self.assertEqual(self.val["status"], "PASS")
        self.assertEqual(self.val["observed_totals"], {"nodes": 60, "edges": 54})
        for gate, st in self.val["gates"].items():
            self.assertEqual(st, "PASS", msg=gate)

    def test_per_graph_counts(self):
        exp = {
            "SP001": (8, 8),
            "SP002": (6, 5),
            "SP005": (8, 7),
            "SP201": (4, 3),
            "SP202": (4, 3),
            "A": (4, 3),
            "B": (4, 3),
            "P7_VTCD_C2": (5, 4),
            "P7_TJR_R3": (5, 5),
            "P7_R4_F1": (7, 9),
            "P7_R4_F2": (5, 4),
        }
        for gid, (n, e) in exp.items():
            p = self.val["per_graph"][gid]
            self.assertEqual((p["n_nodes"], p["n_edges"]), (n, e), msg=gid)

    def test_sp005_sp001_corrections(self):
        sp005 = json.loads((ROOT / "graphs" / "SP005.json").read_text())
        by = {n["node_id"]: n for n in sp005["nodes"]}
        self.assertEqual(by["n3"]["layer2"], "SetTargetCountry")
        self.assertEqual(by["n3"]["normalized_inputs"], ["Italy_A"])
        self.assertEqual(by["n3"]["normalized_outputs"], ["target_country"])
        self.assertEqual(by["n3"]["raw_operator"], "CrossClipCountryBind")
        self.assertEqual(by["n5"]["layer2"], "SelectTeamByCountry")
        e = next(e for e in sp005["edges"] if e["from_node"] == "n3" and e["to_node"] == "n5")
        self.assertEqual(e["raw_dependency_kind"], "bind")
        self.assertEqual(e["normalized_dependency_kind"], "data")

        sp001 = json.loads((ROOT / "graphs" / "SP001.json").read_text())
        by = {n["node_id"]: n for n in sp001["nodes"]}
        self.assertEqual(by["s1"]["layer1"], "SCENE_LOCALIZATION")
        self.assertEqual(by["s3"]["normalized_inputs"], ["flags_A", "country_binding"])
        e = next(e for e in sp001["edges"] if e["from_node"] == "s8" and e["to_node"] == "s3")
        self.assertEqual(e["normalized_dependency_kind"], "bind")

    def test_f2_mapping(self):
        f2 = json.loads((ROOT / "graphs" / "P7_R4_F2.json").read_text())
        by = {n["node_id"]: n for n in f2["nodes"]}
        self.assertEqual(by["f2_n1"]["layer1"], "ENTITY_IDENTIFICATION")
        self.assertEqual(by["f2_n4"]["layer1"], "EVENT_DETECTION")
        self.assertEqual(by["f2_n4"]["layer2"], "DetectInteractionEvent")

    def test_no_family_map(self):
        self.assertTrue(self.mapping.get("replaced_engineering_FAMILY_MAP"))
        self.assertIn("operators_by_node", self.mapping)

    def test_chat_sidecar_not_github_original(self):
        a = json.loads((ROOT / "graphs" / "A.json").read_text())
        self.assertEqual(a["normalization_status"], "CHAT_APPROVED_SIDECAR_INGESTED")
        self.assertTrue(
            a["source"].get("kind", "").startswith("conversation_approved")
            or "conversation_approved" in str(a["source"])
        )

    def test_stage3_computed(self):
        self.assertEqual(self.overlap["status"], "COMPUTED")
        self.assertIsNotNone(self.overlap["m1"])
        self.assertIsNotNone(self.overlap["m2"])
        self.assertIsNotNone(self.overlap["m3"])
        self.assertIsNotNone(self.overlap["m4"])
        self.assertEqual(self.overlap["fixed_split"]["seen"], ["SP001", "SP002", "SP005", "SP201", "SP202"])
        self.assertEqual(self.overlap["fixed_split"]["unseen"], ["P7_VTCD_C2", "P7_TJR_R3"])
        self.assertIn("candidate_sensitivity", self.overlap)


if __name__ == "__main__":
    unittest.main()
