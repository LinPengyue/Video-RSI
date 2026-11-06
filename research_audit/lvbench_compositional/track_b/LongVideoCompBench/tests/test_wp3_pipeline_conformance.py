#!/usr/bin/env python3
"""WP3 pipeline conformance: S3–S9 interfaces + Kbah/USFV regression + negatives."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
OUT = ROOT / "wp3_production" / "wp3_pipeline_conformance"
REPORTS = ROOT / "reports"

sys.path.insert(0, str(TOOLS))
from pipeline_conformance.s3_s5_relation_qa import (  # noqa: E402
    RelationCandidate,
    SourcedFact,
    generate_qa_from_relation,
)
from pipeline_conformance.s6_necessity import (  # noqa: E402
    combine_necessity,
    model_necessity,
    shortcut_audit,
    structural_necessity,
)
from pipeline_conformance.s7_s9_gates import release_gate_check  # noqa: E402


class TestWP3PipelineConformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = json.loads((OUT / "S0_S9_CONFORMANCE_MATRIX.json").read_text())
        cls.reg = json.loads((OUT / "regression_cases.json").read_text())
        cls.report = json.loads(
            (OUT / "WP3_PIPELINE_CONFORMANCE_REPAIR_REPORT.json").read_text()
        )

    def test_matrix_has_s0_s9(self):
        stages = [s["stage"] for s in self.matrix["stages"]]
        self.assertEqual(stages, [f"S{i}" for i in range(10)])
        for s in self.matrix["stages"]:
            self.assertTrue(s["modules"])
            self.assertIn("run_evidence", s)
            # Must not pretend report PASS replaces evidence
            self.assertNotIn("pass_boolean_only", s)

    def test_generator_not_video_hardcoded(self):
        for case in self.reg["cases"].values():
            qa = case["s3_s5"]["qa"]
            self.assertTrue(qa["not_video_hardcoded"])
            self.assertEqual(qa["generator"], "pipeline_conformance.s3_s5_relation_qa.v1")
            self.assertFalse(qa["formal_gold"])

    def test_graph_has_a_and_b(self):
        for case in self.reg["cases"].values():
            g = case["s3_s5"]["program_graph"]
            roles = {n.get("normalized_clip_role") for n in g["nodes"]}
            self.assertIn("A", roles)
            self.assertIn("B", roles)
            self.assertTrue(g["edges"])

    def test_fail_on_unknown_bind(self):
        self.assertEqual(self.reg["negative_unknown_bind"]["status"], "FAIL")
        self.assertIn("UNKNOWN", self.reg["negative_unknown_bind"]["failure_reason"])

    def test_s6_channels_independent(self):
        for case in self.reg["cases"].values():
            nec = case["s6"]
            self.assertEqual(nec["model"]["status"], "NOT_RUN")
            self.assertFalse(nec["model"]["forged"])
            self.assertIn("structural", nec)
            self.assertIn("shortcut_audit", nec)
            self.assertTrue(nec["human_identity_does_not_imply_pass"])
            # Structural trail must expose inputs
            self.assertIn("trail", nec["structural"])
            self.assertIn("inputs", nec["structural"]["trail"])

    def test_kbah_usfv_structural_fail(self):
        for name in ("KbahC-QCKU8_EF_PAIR1", "USfvmoalqsw_PAIR2"):
            case = self.reg["cases"][name]
            self.assertEqual(case["s6"]["overall_verdict"], "FAIL")
            self.assertEqual(case["inventory"], "CONTROL")
            self.assertTrue(case["rejected_as_comp_gold"])

    def test_s8_audit_runs(self):
        for case in self.reg["cases"].values():
            s8 = case["s8_audit"]
            self.assertIn("bucket", s8)
            self.assertFalse(s8["freeze_unseen"])
            self.assertIn("subgraph_audit", s8)

    def test_release_gate_blocks_gold(self):
        for case in self.reg["cases"].values():
            gate = case["s9_release_gate"]
            self.assertFalse(gate["allowed"])
            self.assertFalse(gate["formal_gold"])
            self.assertIn("NECESSITY_NOT_PASS", gate["codes"])

    def test_no_scaled_gold_claim(self):
        self.assertFalse(self.report["counts"]["formal_gold"])
        self.assertEqual(self.report["counts"]["effective_compositional_qa"], 0)
        self.assertFalse(self.report["scaled_gold_capacity_claimed"])
        self.assertFalse(self.matrix["protections"]["scaled_gold_capacity_claimed"])

    def test_structural_unknown_when_missing_fields(self):
        r = structural_necessity({"answer_localized_window": "A"})
        self.assertEqual(r["verdict"], "UNKNOWN")
        self.assertTrue(r["trail"]["missing_fields"])

    def test_model_not_run_default(self):
        m = model_necessity(blind_model_available=False)
        self.assertEqual(m["status"], "NOT_RUN")
        self.assertIsNone(m["A_only"])

    def test_combine_blocks_pass_on_shortcut(self):
        st = {
            "channel": "structural",
            "verdict": "PASS",
            "reason": "x",
            "trail": {},
        }
        sc = shortcut_audit({"ocr_answer_in_window_A": True, "single_candidate_entity_in_A": False})
        m = model_necessity(blind_model_available=False)
        c = combine_necessity(st, m, sc)
        self.assertEqual(c["overall_verdict"], "FAIL")

    def test_releases_immutable(self):
        for ver in ("v0.1.0", "v0.1.1", "v0.1.2"):
            m = json.loads((ROOT / "releases" / ver / "manifest.json").read_text())
            for f in m["files"]:
                p = ROOT / "releases" / ver / f["path"]
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), f["sha256"])

    def test_reports_mirrored(self):
        self.assertTrue((REPORTS / "S0_S9_CONFORMANCE_MATRIX.json").exists())
        self.assertTrue((REPORTS / "WP3_PIPELINE_CONFORMANCE_REPAIR_REPORT.json").exists())


if __name__ == "__main__":
    unittest.main()
