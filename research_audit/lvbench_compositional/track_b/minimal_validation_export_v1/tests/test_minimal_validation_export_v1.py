#!/usr/bin/env python3
"""WP1 minimal validation export tests."""
from __future__ import annotations

import json
import runpy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENG = ROOT / "eng"
SEEN = ["SP001", "SP002", "SP005", "SP201", "SP202"]
UNSEEN = ["P7_VTCD_C2", "P7_TJR_R3"]


class TestMinimalValidationExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old = sys.argv
        try:
            sys.argv = [str(ENG / "build_minimal_validation_export_v1.py")]
            runpy.run_path(
                str(ENG / "build_minimal_validation_export_v1.py"), run_name="__main__"
            )
        finally:
            sys.argv = old
        cls.qa = json.loads((ROOT / "qa_items.json").read_text())
        cls.graphs = json.loads((ROOT / "program_graphs.json").read_text())
        cls.videos = json.loads((ROOT / "video_manifest.json").read_text())
        cls.split = json.loads((ROOT / "split_manifest.json").read_text())
        cls.report = json.loads((ROOT / "VALIDATION_REPORT.json").read_text())

    def test_validation_pass(self):
        self.assertEqual(self.report["status"], "PASS")
        self.assertEqual(self.report["checks"]["no_false_gold"], "PASS")
        self.assertEqual(self.report["checks"]["join_qa_video"], "PASS")
        self.assertEqual(self.report["checks"]["join_graph_edges"], "PASS")

    def test_fixed_split_only_7(self):
        ids = [x["item_id"] for x in self.qa["items"]]
        self.assertEqual(ids, SEEN + UNSEEN)
        self.assertEqual(self.split["fixed_seen"], SEEN)
        self.assertEqual(self.split["fixed_unseen"], UNSEEN)
        self.assertNotIn("A", ids)
        self.assertNotIn("P7_R4_F1", ids)

    def test_no_formal_gold(self):
        for it in self.qa["items"]:
            self.assertFalse(it["answer"]["formal_gold"])
            self.assertEqual(
                it["answer"]["answer_certification_status"],
                "HUMAN_REFERENCE_OR_HISTORICAL_NOT_FORMAL_GOLD",
            )
            self.assertFalse(it["gates"]["formal_gold"])

    def test_join_keys(self):
        qa = {x["item_id"]: x for x in self.qa["items"]}
        graphs = {x["item_id"]: x for x in self.graphs["graphs"]}
        videos = {x["video_id"]: x for x in self.videos["videos"]}
        self.assertEqual(set(qa), set(graphs))
        for item_id, row in qa.items():
            self.assertIn(row["video_id"], videos)
            g = graphs[item_id]
            nids = {n["node_id"] for n in g["nodes"]}
            for e in g["edges"]:
                self.assertIn(e["from_node"], nids)
                self.assertIn(e["to_node"], nids)

    def test_graph_counts_60_nodes_subset(self):
        total_n = sum(g["n_nodes"] for g in self.graphs["graphs"])
        total_e = sum(g["n_edges"] for g in self.graphs["graphs"])
        # 7 graphs only: 60-4-3-7-9 wait: full 11 is 60; without A/B/F1/F2 = 60-4-3-7-9=37?
        # SP001+2+5+201+202+C2+R3 = 8+6+8+4+4+5+5 = 40 nodes; edges 8+5+7+3+3+4+5=35
        self.assertEqual(total_n, 40)
        self.assertEqual(total_e, 35)

    def test_sidecar_not_frame_certified(self):
        for g in self.graphs["graphs"]:
            if g["normalization_status"] == "CHAT_APPROVED_SIDECAR_INGESTED":
                for n in g["nodes"]:
                    self.assertNotEqual(n.get("evidence_certification"), "FRAME_CERTIFIED")

    def test_p7_windows_not_invented(self):
        for it in self.qa["items"]:
            if it["item_id"].startswith("P7_"):
                self.assertEqual(
                    it["windows"]["status"], "UNKNOWN_PENDING_SOURCE_SECOND_MAPPING"
                )
                self.assertIsNone(it["windows"]["A"])
                self.assertTrue(it["windows"].get("do_not_infer_from_program_graph"))

    def test_readme_exists(self):
        self.assertTrue((ROOT / "README.md").is_file())
        self.assertTrue((ROOT / "schemas" / "qa_items.schema.json").is_file())


if __name__ == "__main__":
    unittest.main()
