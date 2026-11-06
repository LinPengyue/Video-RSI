#!/usr/bin/env python3
"""WP3.3 regression: clarification labels, Bugatti downgrade, prospective EF, AB, protections."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
WP3 = ROOT / "wp3_production"
OUT = WP3 / "wp3_3"
REPORTS = ROOT / "reports"


class TestWP33(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clar = json.loads((OUT / "WP3_3_DISCOVERY_EVAL_CLARIFICATION.json").read_text())
        cls.bug = json.loads((OUT / "wp3_3_bugatti_ihfjEFGdZdc_evidence_audit.json").read_text())
        cls.other = json.loads((OUT / "wp3_3_other_candidate_status.json").read_text())
        cls.ab = json.loads((OUT / "wp3_3_ab_prospective_discovery.json").read_text())
        cls.triage = json.loads((OUT / "ab_dev5" / "blind_triage.json").read_text())
        cls.sig = json.loads((OUT / "wp3_3_composition_signature_audit.json").read_text())
        cls.report = json.loads((OUT / "WP3_3_COMPOSITIONAL_EVIDENCE_SCALE_REPORT.json").read_text())
        cls.wp32_disc = json.loads((WP3 / "wp3_2_discovery_method_comparison.json").read_text())

    def test_p0_clarification_does_not_rewrite_wp32(self):
        self.assertEqual(
            self.clar["corrected_supported_claim"],
            "RETROSPECTIVE_SEMANTIC_RERANKING_FEASIBLE",
        )
        self.assertEqual(
            self.clar["unsupported_claim"],
            "PROSPECTIVE_ENTITY_FIRST_DISCOVERY_SUPERIOR",
        )
        self.assertTrue(self.clar["historical_artifact_not_rewritten"])
        # Historical WP3.2 artifact still claims entity_event_first winner (immutable history)
        self.assertEqual(
            self.wp32_disc["head_to_head"]["winner_for_effective_yield"],
            "entity_event_first",
        )

    def test_bugatti_same_object_not_established(self):
        self.assertEqual(
            self.bug["cross_window"]["same_physical_object_continuity"]["verdict"],
            "NOT_ESTABLISHED",
        )
        self.assertEqual(self.bug["qa_policy"]["same_object_state_change_qa"], "NOT_EMITTED")
        self.assertEqual(self.bug["fact_verified_count"], 0)
        self.assertFalse(self.bug["formal_gold"])

    def test_pair2_pending_voice_control(self):
        self.assertEqual(
            self.other["USfvmoalqsw_PAIR2"]["relation_status"],
            "PENDING_HUMAN_IDENTITY_ADJUDICATION",
        )
        self.assertEqual(self.other["W-BnDvXXfOs_PAIR2"]["updated_status"], "CONTROL")
        self.assertFalse(self.other["W-BnDvXXfOs_PAIR2"]["count_as_valid_comp_qa"])

    def test_entity_first_module_self_check(self):
        r = subprocess.run(
            [sys.executable, str(TOOLS / "wp3_3_entity_first_discovery.py"), "--self-check"],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(r.stdout)
        self.assertTrue(data["ok"])
        self.assertIsNone(data["model_stack"]["semantic_vision_model"])
        self.assertTrue(data["model_stack"]["human_gpt_assisted_adjudication_required"])

    def test_ab_prospective_independent(self):
        self.assertEqual(len(self.ab["videos"]), 5)
        self.assertEqual(self.ab["split"], "DEV_ONLY_NOT_SEALED")
        self.assertTrue(self.ab["fairness"]["independent_generators"])
        self.assertTrue(self.ab["fairness"]["not_retrospective_rerank"])
        self.assertFalse(self.ab["fairness"]["official_answers_as_targets"])
        # No cross-method duplicate pairs counted in this run
        vr = json.loads((OUT / "ab_dev5" / "video_results.json").read_text())
        self.assertEqual(sum(len(v["cross_method_duplicates"]) for v in vr["videos"]), 0)
        self.assertEqual(
            self.triage["summary"]["candidate_yield"]["histogram_first_PASS_CANDIDATE"], 0
        )
        self.assertEqual(
            self.triage["summary"]["candidate_yield"]["entity_first_PASS_CANDIDATE"], 1
        )
        self.assertIn("KbahC-QCKU8_EF_PAIR1", [p["pair_id"] for p in self.triage["pairs"] if p["decision"] == "PASS_CANDIDATE"])
        # Must not declare prospective superiority as proven
        self.assertFalse(self.ab.get("head_to_head_candidate_yield", {}).get("declare_prospective_superior", True))

    def test_no_auto_gold_and_signatures_unverified(self):
        self.assertEqual(self.report["counts"]["formal_gold"], 0)
        self.assertEqual(self.report["counts"]["FACT_VERIFIED"], 0)
        self.assertFalse(self.report["scale_recommendation"]["recommend_expand_to_50_100_qa"])
        self.assertEqual(self.sig["counts"]["frozen_unseen_promotions"], 0)
        self.assertTrue(self.sig["frozen_5_2_unchanged"])
        self.assertEqual(self.sig["proposed_7_4_status"], "PROPOSED")
        for c in self.sig["candidates"]:
            if c.get("label"):
                self.assertEqual(c["label"], "PROPOSED_SIGNATURE_UNVERIFIED")

    def test_releases_immutable(self):
        for ver in ("v0.1.0", "v0.1.1", "v0.1.2"):
            m = json.loads((ROOT / "releases" / ver / "manifest.json").read_text())
            for f in m["files"]:
                p = ROOT / "releases" / ver / f["path"]
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), f["sha256"])

    def test_reports_mirrored(self):
        for name in (
            "WP3_3_DISCOVERY_EVAL_CLARIFICATION.json",
            "WP3_3_COMPOSITIONAL_EVIDENCE_SCALE_REPORT.json",
        ):
            self.assertTrue((OUT / name).exists())
            self.assertTrue((REPORTS / name).exists())


if __name__ == "__main__":
    unittest.main()
