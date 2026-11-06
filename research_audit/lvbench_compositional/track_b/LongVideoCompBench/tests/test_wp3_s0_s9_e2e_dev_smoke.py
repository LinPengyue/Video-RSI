#!/usr/bin/env python3
"""E2E DEV smoke + semantic bridge + formal certification negatives."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
OUT = ROOT / "wp3_production" / "wp3_s0_s9_e2e_dev_smoke"
REPORTS = ROOT / "reports"
REPO = Path(__file__).resolve().parents[5]

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(TOOLS))

from pipeline_conformance.formal_certification import evaluate_formal_ready  # noqa: E402
from pipeline_conformance.media_hash_audit import evidence_flags  # noqa: E402
from pipeline_conformance.s6_necessity import combine_necessity, model_necessity  # noqa: E402
from tools.lvbench_comp.batch_factory.s0_s9_production import (  # noqa: E402
    PRODUCTION_ENTRY,
    load_evidence_pairs_from_rois,
    process_evidence_pair,
)


class TestWP3S0S9E2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (OUT / "WP3_S0_S9_E2E_DEV_SMOKE_SUMMARY.json").read_text()
        )
        cls.report = json.loads((OUT / "S0_S9_DEV_SMOKE_REPORT.json").read_text())
        cls.media = json.loads((OUT / "MEDIA_HASH_AUDIT.json").read_text())

    def test_engineering_wired_not_scientific_closed_loop(self):
        eng = self.summary["pipeline_engineering_completion"]
        self.assertTrue(eng["wired_into_formal_batch_entry"])
        self.assertTrue(eng["semantic_fact_adapter"])
        self.assertFalse(eng["production_closed_loop_scientific_claimed"])
        self.assertFalse(PRODUCTION_ENTRY["production_closed_loop_scientific"])

    def test_scientific_rates_are_separate(self):
        rates = self.summary["scientific_rates"]
        for key in (
            "evidence_manifest_complete",
            "media_hash_reverified",
            "semantic_facts_available",
            "relation_candidates_verified",
            "qa_drafts_generated",
            "program_graph_semantic_validation",
            "program_execution_verified",
            "structural_necessity_verified",
            "formal_gold",
        ):
            self.assertIn(key, rates)
        self.assertEqual(rates["formal_gold"]["numerator"], 0)
        self.assertEqual(rates["program_execution_verified"]["numerator"], 0)
        # Hash presence must not equal semantic_fact_verified conflation in flags helper
        f = evidence_flags(
            manifest_has_ab_hashes=True,
            media_hash_reverified=True,
            semantic_fact_verified=False,
            human_relation_certified=True,
        )
        self.assertTrue(f["evidence_manifest_complete"])
        self.assertFalse(f["semantic_fact_verified"])

    def test_full_path_exists_without_fabricated_attrs(self):
        self.assertGreaterEqual(len(self.report.get("full_path_pairs") or []), 1)
        for r in self.report["results"]:
            if r.get("exit") == "FULL_PATH":
                attrs = (r.get("relation") or {}).get("queryable_attributes") or []
                self.assertTrue(attrs)
                for a in attrs:
                    self.assertFalse(a.get("allowed_for_gold"))
                    self.assertEqual(
                        a.get("certification"),
                        "ATTRIBUTE_NOT_COVERED_BY_HUMAN_IDENTITY_CLAIM",
                    )
                    self.assertTrue(a.get("source_ref"))
                self.assertEqual(
                    (r.get("qa") or {}).get("answer_certification"),
                    "ATTRIBUTE_NOT_COVERED_BY_HUMAN_IDENTITY_CLAIM",
                )
                self.assertIn(
                    r.get("classification"), {"CONTROL", "PENDING", "DEV"}
                )

    def test_early_exit_without_semantics(self):
        found = False
        for r in self.report["results"]:
            if r.get("exit") == "NO_SEMANTIC_FACTS":
                found = True
                self.assertIsNone(r.get("relation"))
                self.assertEqual(r["classification"], "PENDING")
        self.assertTrue(found)

    def test_media_equivalence_documented_for_hash_divergence(self):
        # Kbah/USFV ROI vs registry hashes differ; equivalence map must be present
        for item in self.media["items"]:
            if item["pair_id"] in {"KbahC-QCKU8_EF_PAIR1", "USfvmoalqsw_PAIR2"}:
                eq = item.get("media_equivalence") or {}
                self.assertIn(
                    eq.get("equivalence_class"),
                    {
                        "SAME_SOURCE_VIDEO_SAME_WINDOW_REEXTRACT",
                        "REGISTRY_ONLY",
                        "UNRESOLVED",
                    },
                )
                flags = item.get("flags") or {}
                self.assertFalse(flags.get("semantic_fact_verified"))

    def test_no_hardcoded_empty_queryables_in_production(self):
        src = (
            REPO / "tools/lvbench_comp/batch_factory/s0_s9_production.py"
        ).read_text()
        # Forbid assigning empty queryables in RelationCandidate construction
        self.assertNotIn("queryable_attributes=[],", src)
        self.assertNotIn("queryable_attributes = []", src)
        self.assertIn("semantic_fact_adapter", src)

    def test_formal_cert_rejects_embedded_store_backed_bypass(self):
        reg = (
            ROOT
            / "wp3_production/wp3_4/trusted_human_review_registry/records.jsonl"
        )
        item = {
            "qa_id": "fake",
            "program_id": "fake_pg",
            "video_id": "KbahC-QCKU8",
            "windows": {"A": [90.0, 100.0], "B": [2160.0, 2170.0]},
            "clip_sha256": {
                "A": "58812c619252d45f070c9372e49e1146a287840a16ff355fc1ec699a5b8b4fba",
                "B": "2afce6b5de756c29e5844dfef299a98f02bb4024e334ca26618d0dea44facc6c",
            },
            "bind_claim_ids": ["CLAIM_KBAH_ADULT_SAME"],
            "necessity_store_backed": True,
            "necessity_record": {
                "overall_verdict": "PASS",
                "strict_necessity_proof": True,
                "model": {"status": "RUN", "verdict": "SUPPORTS_NECESSITY"},
            },
            "formal_gold": False,
        }
        r = evaluate_formal_ready(item, trusted_records_jsonl=reg)
        self.assertFalse(r["formal_ready"])
        self.assertIn("REJECT_EMBEDDED_NECESSITY_BYPASS", r["codes"])

    def test_model_necessity_requires_b_only_and_artifacts(self):
        def _run(label, correct, artifact=True):
            d = {
                "run_id": f"r_{label}",
                "model_version": "test",
                "input_condition": label,
                "evidence_isolation": "ISOLATED",
                "raw_output": "x",
                "correct": correct,
            }
            if artifact:
                d["raw_output_sha256"] = "abc"
            return d

        # Text-only raw_output → NOT_RUN
        m0 = model_necessity(
            blind_model_available=True,
            a_only_run=_run("A_only", False, artifact=False),
            b_only_run=_run("B_only", False, artifact=False),
            ab_run=_run("A_plus_B", True, artifact=False),
        )
        self.assertEqual(m0["status"], "NOT_RUN")

        m = model_necessity(
            blind_model_available=True,
            a_only_run=_run("A_only", False),
            b_only_run=_run("B_only", True),
            ab_run=_run("A_plus_B", True),
        )
        self.assertEqual(m["status"], "RUN")
        self.assertEqual(m["verdict"], "INCONCLUSIVE_MISSING_B_ONLY_FAILURE")
        st = {
            "channel": "structural",
            "verdict": "PASS",
            "strict_proof": True,
            "reason": "x",
            "trail": {},
        }
        c = combine_necessity(
            st, m, {"blocks_strict_necessity_pass": False, "findings": []}
        )
        self.assertNotEqual(c["overall_verdict"], "PASS")

    def test_incomplete_roi_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "rois.jsonl"
            p.write_text(
                json.dumps(
                    {
                        "pair_id": "X_PAIR",
                        "video_id": "X",
                        "role": "early",
                        "t_start": 0,
                        "t_end": 1,
                        "local_clip": {},
                        "semantics": "UNRESOLVED",
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "pair_id": "X_PAIR",
                        "video_id": "X",
                        "role": "late",
                        "t_start": 10,
                        "t_end": 11,
                        "local_clip": {},
                        "semantics": "UNRESOLVED",
                    }
                )
                + "\n"
            )
            pairs = load_evidence_pairs_from_rois(p)
            reg = (
                ROOT
                / "wp3_production/wp3_4/trusted_human_review_registry/records.jsonl"
            )
            out = process_evidence_pair(pairs[0], trusted_records_jsonl=reg)
            self.assertEqual(out["classification"], "REJECT")

    def test_reports_mirrored(self):
        self.assertTrue((REPORTS / "WP3_S0_S9_E2E_DEV_SMOKE_SUMMARY.json").exists())
        self.assertGreaterEqual(self.summary["n_pairs"], 1)
        self.assertEqual(self.summary["protections"]["formal_gold"], 0)


if __name__ == "__main__":
    unittest.main()
