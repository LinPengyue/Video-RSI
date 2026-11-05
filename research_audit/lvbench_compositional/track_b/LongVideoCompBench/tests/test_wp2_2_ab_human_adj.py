#!/usr/bin/env python3
"""WP2.2 tests: human A/B adjudication ingest + v0.1.2 immutability of prior releases."""
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


class TestWP22ABHumanAdj(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Idempotent: only re-apply if v0.1.2 missing (do not rewrite frozen release).
        if not (ROOT / "releases" / "v0.1.2" / "manifest.json").is_file():
            runpy.run_path(
                str(TOOLS / "apply_ab_human_adjudication_v0_1_2.py"), run_name="__main__"
            )
        cls.report = json.loads(
            (ROOT / "reports" / "WP2_2_AB_HUMAN_ADJUDICATION_REPORT.json").read_text()
        )
        cls.manifest = json.loads(
            (ROOT / "releases" / "v0.1.2" / "manifest.json").read_text()
        )

    def test_gates_pass(self):
        self.assertEqual(run_gates()["overall"], "PASS")

    def test_ab_fields(self):
        qas = {q["source_item_id"]: q for q in read_jsonl(ROOT / "data" / "qa_items.jsonl")}
        self.assertEqual(qas["A"]["video_id"], "hROKtPqktO8")
        self.assertEqual(qas["B"]["video_id"], "iA_69g87Ilw")
        for sid in ("A", "B"):
            self.assertEqual(qas[sid]["record_completeness"], "PARTIAL")
            self.assertEqual(qas[sid]["answer_status"], "CHAT_RECONSTRUCTED_QA_DRAFT")
            self.assertFalse(qas[sid]["formal_gold"])
            bundle = qas[sid]["composition_attributes"]["status_bundle"]
            self.assertEqual(bundle["human_relation_adjudication_status"], "HUMAN_APPROVED")
            self.assertEqual(
                bundle["formal_qa_windows_status"], "ROI_RELATED_NOT_FULL_QA_WINDOWS"
            )
            self.assertFalse(bundle["formal_gold_status"])

    def test_human_adjudication_records(self):
        rows = read_jsonl(ROOT / "annotations" / "ab_human_adjudications_wp2_2.jsonl")
        self.assertEqual(len(rows), 2)
        by = {r["source_item_id"]: r for r in rows}
        self.assertEqual(by["A"]["reviewer_role"], "HUMAN_SCIENTIFIC_OWNER")
        self.assertEqual(by["A"]["source_type"], "DIRECT_USER_CONFIRMATION_IN_CHAT")
        self.assertEqual(by["A"]["scope"], "VIDEO_BINDING_AND_CROSS_WINDOW_RELATION")
        self.assertEqual(
            by["A"]["cross_window_relation"]["operator"], "CrossIntervalSamePersonBind"
        )
        self.assertEqual(
            by["B"]["cross_window_relation"]["operator"], "CrossViewSameRoomBind"
        )
        self.assertEqual(by["A"]["rois"]["A"]["start"], 500)
        self.assertEqual(by["A"]["rois"]["B"]["end"], 1265)
        self.assertEqual(by["B"]["rois"]["A"]["start"], 358)
        self.assertEqual(by["B"]["rois"]["B"]["end"], 910)

    def test_prior_releases_immutable(self):
        v010 = {
            q["source_item_id"]: q
            for q in read_jsonl(ROOT / "releases/v0.1.0/data/qa_items.jsonl")
        }
        v011 = {
            q["source_item_id"]: q
            for q in read_jsonl(ROOT / "releases/v0.1.1/data/qa_items.jsonl")
        }
        self.assertIsNone(v010["A"]["video_id"])
        self.assertEqual(v011["A"]["record_completeness"], "GRAPH_ONLY")
        self.assertTrue((ROOT / "reports/AB_SOURCE_RECOVERY_AUDIT.json").is_file())
        self.assertEqual(self.manifest["version"], "v0.1.2")
        self.assertEqual(self.manifest["parent_release"], "v0.1.1")

    def test_splits_unchanged(self):
        splits = json.loads((ROOT / "data" / "splits.json").read_text())
        self.assertEqual(
            splits["frozen_5_2"]["seen"] + splits["frozen_5_2"]["unseen"], FROZEN_5_2
        )
        self.assertEqual(splits["proposed_7_4_dev"]["status"], "PROPOSED")
        self.assertEqual(splits["proposed_7_4_dev"]["seen"], PROPOSED_7_4_SEEN)
        wp1 = [x["item_id"] for x in json.loads((WP1 / "qa_items.json").read_text())["items"]]
        self.assertEqual(wp1, FROZEN_5_2)

    def test_roi_not_full_windows(self):
        qas = {q["source_item_id"]: q for q in read_jsonl(ROOT / "data" / "qa_items.jsonl")}
        for sid in ("A", "B"):
            fw = qas[sid]["composition_attributes"]["formal_windows_seconds"]
            self.assertEqual(
                fw["status"], "NOT_AUTHORIZED_AS_COMPLETE_QA_WINDOWS"
            )


if __name__ == "__main__":
    unittest.main()
