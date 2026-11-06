#!/usr/bin/env python3
"""WP3 Human adj ingest + Necessity: relations certified, no forged AB, no Gold."""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "wp3_production" / "wp3_human_adj"
REG = ROOT / "wp3_production" / "wp3_4" / "trusted_human_review_registry"
REPORTS = ROOT / "reports"


class TestWP3HumanAdj(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(
            (OUT / "WP3_HUMAN_ADJ_INGEST_AND_NECESSITY_REPORT.json").read_text()
        )
        cls.nec = json.loads((OUT / "wp3_necessity_structural_audit.json").read_text())
        cls.qa = json.loads((OUT / "wp3_qa_program_drafts.json").read_text())
        cls.records = [
            json.loads(ln)
            for ln in (REG / "records.jsonl").read_text().splitlines()
            if ln.strip()
        ]

    def test_three_human_claims_in_registry(self):
        ids = {r["claim_id"] for r in self.records}
        self.assertEqual(
            ids,
            {
                "CLAIM_KBAH_ADULT_SAME",
                "CLAIM_KBAH_CHILD_SAME",
                "CLAIM_USFV_MAN_SAME",
            },
        )
        for r in self.records:
            self.assertEqual(r["reviewer_role"], "HUMAN_SCIENTIFIC_OWNER")
            self.assertEqual(r["source"], "DIRECT_USER_CONFIRMATION_IN_CHAT")
            self.assertEqual(r["decision_scope"], "CROSS_WINDOW_PERSON_IDENTITY")
            self.assertEqual(r["decision"], "SAME")
            self.assertFalse(r["reask_human_identity"])
            self.assertIn("FORMAL_GOLD", r["does_not_certify"])
            self.assertTrue(r["raw_rationale_verbatim_zh"])
            self.assertIn("normalized_features_separate", r)

    def test_qa_graphs_have_a_side_nodes(self):
        self.assertFalse(self.qa["formal_gold"])
        for item in self.qa["items"]:
            ops = {n["op"] for n in item["program_graph"]["nodes"]}
            self.assertIn("CrossIntervalSamePersonBind", ops)
            self.assertFalse(item["program_graph"]["atomic_covered_ood_candidate"])
            # A-side locate present
            windows = [n.get("window") for n in item["program_graph"]["nodes"]]
            self.assertIn("A", windows)
            self.assertIn("B", windows)
            self.assertTrue(item["program_graph"]["edges"])

    def test_necessity_fail_no_forged_ab(self):
        self.assertEqual(self.nec["counts"]["necessity_PASS"], 0)
        self.assertEqual(self.nec["counts"]["necessity_FAIL"], 2)
        self.assertEqual(self.nec["counts"]["effective_compositional_qa"], 0)
        self.assertEqual(self.nec["counts"]["control_with_certified_relation"], 2)
        self.assertEqual(self.nec["counts"]["formal_gold"], 0)
        for item in self.nec["items"]:
            self.assertEqual(item["necessity_verdict"], "FAIL")
            self.assertFalse(item["blind_model_ab_tests"]["forged"])
            self.assertIsNone(item["blind_model_ab_tests"]["A_only"])
            self.assertTrue(
                item["structural_shortcut_audit"]["human_SAME_does_not_imply_necessity_pass"]
            )

    def test_no_auto_gold(self):
        self.assertFalse(self.report["layers"]["gold_status"]["formal_gold"])
        self.assertEqual(
            self.report["layers"]["gold_status"]["independent_gold_review"], "NOT_ENTERED"
        )
        self.assertEqual(self.report["protections"]["proposed_7_4_status"], "PROPOSED")
        self.assertFalse(self.report["protections"]["track_a_run"])
        self.assertFalse(self.report["protections"]["new_public_media"])

    def test_releases_immutable(self):
        for ver in ("v0.1.0", "v0.1.1", "v0.1.2"):
            m = json.loads((ROOT / "releases" / ver / "manifest.json").read_text())
            for f in m["files"]:
                p = ROOT / "releases" / ver / f["path"]
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), f["sha256"])

    def test_reports_mirrored(self):
        self.assertTrue((REPORTS / "WP3_HUMAN_ADJ_INGEST_AND_NECESSITY_REPORT.json").exists())
        self.assertTrue((REPORTS / "wp3_necessity_structural_audit.json").exists())


if __name__ == "__main__":
    unittest.main()
