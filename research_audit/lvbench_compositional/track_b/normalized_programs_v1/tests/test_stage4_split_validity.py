#!/usr/bin/env python3
"""Stage-4 split validity / corrected M3 tests."""
from __future__ import annotations

import json
import runpy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENG = ROOT / "eng"


class TestStage4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old = sys.argv
        try:
            sys.argv = [str(ENG / "build_stage4_split_validity_audit.py")]
            runpy.run_path(
                str(ENG / "build_stage4_split_validity_audit.py"), run_name="__main__"
            )
        finally:
            sys.argv = old
        cls.audit = json.loads((ROOT / "stage4_split_validity_audit.json").read_text())
        cls.m3 = cls.audit["m3_corrected"]

    def test_stage3_historical_preserved(self):
        hist = ROOT / "reports" / "stage3_historical" / "overlap_metrics_08b5483.json"
        self.assertTrue(hist.is_file())
        old = json.loads(hist.read_text())
        self.assertEqual(old.get("status"), "COMPUTED")
        # current overlap_metrics.json must still exist (not deleted)
        self.assertTrue((ROOT / "overlap_metrics.json").is_file())

    def test_layer1_reference_fractions(self):
        self.assertTrue(self.m3["reference_check_all_match"])
        self.assertEqual(self.m3["layer1"]["ops"]["2_node"]["unique_fraction"], "3/7")
        self.assertEqual(self.m3["layer1"]["ops"]["3_node"]["unique_fraction"], "1/7")
        self.assertEqual(self.m3["layer1"]["ops_role"]["2_node"]["unique_fraction"], "3/8")
        self.assertEqual(self.m3["layer1"]["ops_role"]["3_node"]["unique_fraction"], "0/8")

    def test_ops_role_excludes_edge_kind(self):
        cell = self.m3["layer1"]["ops_role"]["2_node"]
        self.assertTrue(cell["ops_role_excludes_dependency_kind"])

    def test_duplicate_label_self_check(self):
        sc = self.m3["duplicate_label_self_check"]
        self.assertTrue(sc["ops_equal_under_id_permutation"])
        self.assertTrue(sc["ops_role_equal_for_isomorphic_role_edge"])

    def test_both_layers_present(self):
        for layer in ("layer1", "layer2"):
            for mode in ("ops", "ops_role", "ops_role_edge", "ops_role_edge_io"):
                for size in ("2_node", "3_node"):
                    cell = self.m3[layer][mode][size]
                    self.assertIn("unique_fraction", cell)
                    self.assertIn("occurrence_fraction", cell)
                    self.assertIn("witnesses_per_unseen", cell)

    def test_m4_trivial_size_mismatch(self):
        pairs = self.audit["m4_reinterpretation"]["pairs"]
        self.assertTrue(any(p["status"] == "TRIVIAL_SIZE_MISMATCH" for p in pairs))
        # C2 is 5 nodes; no Seen is 5 nodes
        c2 = self.audit["m4_reinterpretation"]["size_notes"]["P7_VTCD_C2"]
        self.assertEqual(c2["seen_with_same_n_nodes"], [])

    def test_novelty_na_not_zero_when_absent(self):
        for ug in ("P7_VTCD_C2", "P7_TJR_R3"):
            block = self.audit["novelty_decomposition"][ug]["subgraph_2_layer2_ops"]
            val = block["seen_atom_only_structural_overlap_layer2_ops"]["value"]
            # If N/A, must be string N/A; if fraction, must look like a/b
            if val == "N/A":
                self.assertIsNone(block["seen_atom_only_structural_overlap_layer2_ops"]["ratio"])
            else:
                self.assertRegex(val, r"^\d+/\d+$")

    def test_validity_judgments_present(self):
        v = self.audit["scientific_validity"]
        for k in ("A", "B", "C", "D", "E"):
            self.assertIn("judgment", v[k])
        self.assertEqual(v["B"]["judgment"], "NO_NOT_PURE")
        self.assertEqual(v["C"]["judgment"], "YES")


if __name__ == "__main__":
    unittest.main()
