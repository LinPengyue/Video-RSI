#!/usr/bin/env python3
"""WP2.1 regression: A/B recovery audit, v0.1.0 immutability, no invented answers."""
from __future__ import annotations

import json
import runpy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from _common import FROZEN_5_2, PROPOSED_7_4_SEEN, WP1, read_jsonl  # noqa: E402
from validate_dataset import run_gates  # noqa: E402


class TestWP21ABRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Run recovery patch once
        runpy.run_path(str(TOOLS / "recover_ab_sources_v0_1_1.py"), run_name="__main__")
        cls.ab = json.loads(
            (ROOT / "reports" / "AB_SOURCE_RECOVERY_AUDIT.json").read_text()
        )
        cls.win = json.loads(
            (ROOT / "reports" / "WINDOW_RECOVERY_C2_R3_F1_F2_AUDIT.json").read_text()
        )
        cls.v010 = json.loads(
            (ROOT / "releases" / "v0.1.0" / "manifest.json").read_text()
        )
        cls.v011 = json.loads(
            (ROOT / "releases" / "v0.1.1" / "manifest.json").read_text()
        )

    def test_gates_still_pass(self):
        report = run_gates()
        self.assertEqual(report["overall"], "PASS")

    def test_ab_still_graph_only_no_forged_answer(self):
        qas = {q["source_item_id"]: q for q in read_jsonl(ROOT / "data" / "qa_items.jsonl")}
        for sid in ("A", "B"):
            self.assertEqual(qas[sid]["record_completeness"], "GRAPH_ONLY")
            self.assertIsNone(qas[sid]["question"])
            self.assertIsNone(qas[sid]["answer"])
            self.assertIsNone(qas[sid]["video_id"])
            self.assertFalse(qas[sid]["formal_gold"])
        # release snapshot matches
        rel_qas = {
            q["source_item_id"]: q
            for q in read_jsonl(ROOT / "releases/v0.1.1/data/qa_items.jsonl")
        }
        self.assertEqual(rel_qas["A"]["record_completeness"], "GRAPH_ONLY")

    def test_recovery_rate_zero_primary(self):
        for sid in ("A", "B"):
            self.assertEqual(self.ab["recovery_rates"][sid]["n_recovered"], 0)
            self.assertEqual(self.ab["recovery_rates"][sid]["rate"], 0.0)

    def test_graph_io_tokens_not_promoted_as_answers(self):
        blob = json.dumps(self.ab)
        self.assertIn("answer_urban_stairs", blob)
        self.assertIn("NOT_AN_ANSWER", blob)
        self.assertIn("answer_fruit_platter", blob)
        for sid in ("A", "B"):
            self.assertIsNone(self.ab["items"][sid]["answer"]["recovered_value"])

    def test_windows_not_promoted_for_p7(self):
        for iid in ("P7_VTCD_C2", "P7_TJR_R3", "P7_R4_F1", "P7_R4_F2"):
            self.assertIsNone(self.win["items"][iid]["recovered_value"])
            self.assertEqual(
                self.win["items"][iid]["dataset_action"], "WINDOWS_REMAIN_UNKNOWN"
            )
        # live evidence rows still unknown windows for those items
        ev = read_jsonl(ROOT / "data" / "evidence.jsonl")
        for e in ev:
            if any(x in e["evidence_id"] for x in ("P7_VTCD_C2", "P7_TJR_R3", "P7_R4_F1", "P7_R4_F2")):
                if e["evidence_id"].endswith(":UNKNOWN") or e.get("window_start") is None:
                    self.assertIsNone(e.get("window_start"))

    def test_v010_immutable_and_v011_built(self):
        self.assertTrue(self.v010.get("immutable"))
        self.assertEqual(self.v011["version"], "v0.1.1")
        self.assertEqual(self.v011["parent_release"], "v0.1.0")
        self.assertTrue((ROOT / "releases/v0.1.0/data/qa_items.jsonl").is_file())
        # v0.1.0 A still GRAPH_ONLY historically
        old = {
            q["source_item_id"]: q
            for q in read_jsonl(ROOT / "releases/v0.1.0/data/qa_items.jsonl")
        }
        self.assertEqual(old["A"]["record_completeness"], "GRAPH_ONLY")

    def test_splits_unchanged(self):
        splits = json.loads((ROOT / "data" / "splits.json").read_text())
        self.assertEqual(
            splits["frozen_5_2"]["seen"] + splits["frozen_5_2"]["unseen"], FROZEN_5_2
        )
        self.assertEqual(splits["proposed_7_4_dev"]["status"], "PROPOSED")
        self.assertEqual(splits["proposed_7_4_dev"]["seen"], PROPOSED_7_4_SEEN)
        wp1 = json.loads((WP1 / "qa_items.json").read_text())
        self.assertEqual([x["item_id"] for x in wp1["items"]], FROZEN_5_2)

    def test_checklist_exists(self):
        self.assertTrue((ROOT / "reports/HUMAN_SUPPLEMENT_CHECKLIST.md").is_file())


if __name__ == "__main__":
    unittest.main()
