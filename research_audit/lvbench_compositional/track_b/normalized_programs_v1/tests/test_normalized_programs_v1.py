#!/usr/bin/env python3
"""Tests for Stage 2 normalization gate (expect BLOCKED until authoritative graphs complete)."""
from __future__ import annotations

import json
import runpy
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENG = ROOT / "eng"


class TestNormalizedProgramsV1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys

        old = sys.argv
        try:
            sys.argv = [str(ENG / "build_normalized_programs_v1.py")]
            runpy.run_path(str(ENG / "build_normalized_programs_v1.py"), run_name="__main__")
        finally:
            sys.argv = old
        cls.val = json.loads((ROOT / "validation_report.json").read_text())
        cls.overlap = json.loads((ROOT / "overlap_metrics.json").read_text())
        cls.manifest = json.loads((ROOT / "source_manifest.json").read_text())
        cls.decisions = json.loads((ROOT / "scientific_decisions.json").read_text())

    def test_stage2_blocked_not_fake_pass(self):
        self.assertEqual(self.val["status"], "BLOCKED")
        self.assertFalse(self.val["stage3_authorized"])

    def test_eleven_slots_recorded(self):
        expected = [
            "SP001",
            "SP002",
            "SP005",
            "SP201",
            "SP202",
            "P7_VTCD_C2",
            "P7_TJR_R3",
            "A",
            "B",
            "P7_R4_F1",
            "P7_R4_F2",
        ]
        self.assertEqual(list(self.val["per_graph"].keys()), expected)
        for gid in expected:
            self.assertTrue((ROOT / "graphs" / f"{gid}.json").is_file())

    def test_a_b_missing(self):
        self.assertEqual(self.val["per_graph"]["A"]["status"], "MISSING")
        self.assertEqual(self.val["per_graph"]["B"]["status"], "MISSING")

    def test_p7_structured_counts(self):
        self.assertEqual(self.val["per_graph"]["P7_VTCD_C2"]["n_nodes"], 5)
        self.assertEqual(self.val["per_graph"]["P7_VTCD_C2"]["n_edges"], 4)
        self.assertEqual(self.val["per_graph"]["P7_TJR_R3"]["n_nodes"], 5)
        self.assertEqual(self.val["per_graph"]["P7_TJR_R3"]["n_edges"], 5)
        self.assertEqual(self.val["per_graph"]["P7_R4_F1"]["n_nodes"], 7)
        self.assertEqual(self.val["per_graph"]["P7_R4_F1"]["n_edges"], 9)
        self.assertEqual(self.val["per_graph"]["P7_R4_F2"]["n_nodes"], 5)
        self.assertEqual(self.val["per_graph"]["P7_R4_F2"]["n_edges"], 4)

    def test_no_invented_edges_on_macro(self):
        for gid in ("SP001", "SP005", "SP201", "SP202"):
            g = json.loads((ROOT / "graphs" / f"{gid}.json").read_text())
            self.assertEqual(g["n_edges"], 0)
            self.assertEqual(g["normalization_status"], "SIDECAR_INCOMPLETE_BLOCKING")

    def test_stage3_metrics_null(self):
        self.assertEqual(self.overlap["status"], "BLOCKED")
        self.assertIsNone(self.overlap["m1"])
        self.assertIsNone(self.overlap["m2"])
        self.assertIsNone(self.overlap["m3"])
        self.assertIsNone(self.overlap["m4"])

    def test_totals_not_60_54(self):
        tot = self.val["observed_totals"]
        self.assertNotEqual(
            (tot["nodes"], tot["edges"]),
            (60, 54),
            msg="If this becomes 60/54 without resolving A/B and Seen edges, investigate fabrication",
        )

    def test_ambiguities_listed(self):
        ids = {a["id"] for a in self.decisions["ambiguities"]}
        self.assertIn("MISSING_GRAPH_A", ids)
        self.assertIn("MISSING_GRAPH_B", ids)


if __name__ == "__main__":
    unittest.main()
