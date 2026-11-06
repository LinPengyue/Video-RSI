#!/usr/bin/env python3
"""E2E DEV smoke + formal certification negatives."""
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
from pipeline_conformance.s6_necessity import combine_necessity, model_necessity  # noqa: E402
from pipeline_conformance.s8_signature_feedback import audit_draft_against_seen  # noqa: E402
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

    def test_engineering_wired_not_scientific_closed_loop(self):
        eng = self.summary["pipeline_engineering_completion"]
        self.assertTrue(eng["wired_into_formal_batch_entry"])
        self.assertFalse(eng["production_closed_loop_scientific_claimed"])
        self.assertTrue(PRODUCTION_ENTRY["wired_into_formal_batch_entry"])
        self.assertFalse(PRODUCTION_ENTRY["production_closed_loop_scientific"])

    def test_scientific_rates_separate_from_engineering(self):
        rates = self.summary["scientific_rates"]
        for key in (
            "evidence_verified",
            "qa_family_generated",
            "structural_necessity_verified",
            "program_execution_verified",
            "atomic_covered_composition_ood_verified",
            "independent_gold_certified",
        ):
            self.assertIn(key, rates)
            self.assertIn("numerator", rates[key])
        # Engineering completion must not equal scientific Gold
        self.assertEqual(rates["independent_gold_certified"]["numerator"], 0)
        self.assertEqual(rates["program_execution_verified"]["numerator"], 0)
        self.assertEqual(rates["atomic_covered_composition_ood_verified"]["numerator"], 0)

    def test_no_fabricated_relations_without_semantics(self):
        for r in self.report["results"]:
            if r.get("exit") == "NO_SEMANTIC_FACTS":
                self.assertIsNone(r.get("relation"))
                self.assertEqual(r["classification"], "PENDING")

    def test_results_are_data_driven(self):
        # Production path source must not embed hardcoded Necessity FAIL for video ids
        src = (
            REPO
            / "tools/lvbench_comp/batch_factory/s0_s9_production.py"
        ).read_text()
        self.assertNotIn("KbahC-QCKU8", src)
        self.assertNotIn("USfvmoalqsw", src)
        self.assertNotIn('necessity_overall": "FAIL"', src)
        self.assertNotIn("overall_verdict\"] = \"FAIL\"", src)

    def test_identity_bind_does_not_mint_answer_attrs(self):
        for r in self.report["results"]:
            if r.get("identity_claims"):
                rel = r.get("relation") or {}
                self.assertEqual(rel.get("queryable_attributes"), [])
                if r.get("exit") == "QA_FAMILY_FAILED":
                    self.assertIn("missing", (r.get("failure_reason") or "").lower())

    def test_formal_cert_rejects_caller_declared_pass(self):
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
            "necessity_overall": "PASS",  # caller string — ignored
            "model_necessity_status": "RUN",
            "program_execution": "EXECUTABLE_PASS",
            "self_declared_necessity_pass": True,
            "answer_certified_by_human_relation": True,
            "formal_gold": False,
        }
        r = evaluate_formal_ready(item, trusted_records_jsonl=reg)
        self.assertFalse(r["formal_ready"])
        self.assertTrue(any("SELF_DECLARED" in c for c in r["codes"]))
        self.assertIn("HUMAN_SAME_CANNOT_CERTIFY_ANSWER", r["codes"])
        self.assertTrue(any("MISSING_NECESSITY" in c or "MODEL_NECESSITY" in c for c in r["codes"]))

    def test_model_necessity_requires_b_only_fail(self):
        def _run(label, correct):
            return {
                "run_id": f"r_{label}",
                "model_version": "test",
                "input_condition": label,
                "evidence_isolation": "ISOLATED",
                "raw_output": "x",
                "correct": correct,
            }

        m = model_necessity(
            blind_model_available=True,
            a_only_run=_run("A_only", False),
            b_only_run=_run("B_only", True),  # B succeeds → cannot claim necessity
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
        c = combine_necessity(st, m, {"blocks_strict_necessity_pass": False, "findings": []})
        self.assertNotEqual(c["overall_verdict"], "PASS")

        m2 = model_necessity(
            blind_model_available=True,
            a_only_run=_run("A_only", False),
            b_only_run=_run("B_only", False),
            ab_run=_run("A_plus_B", True),
        )
        self.assertEqual(m2["verdict"], "SUPPORTS_NECESSITY")

    def test_s8_training_exposure_unconfirmed_blocks_ood(self):
        # Minimal graph with Seen L1 labels but unnormalized L2
        g = {
            "program_id": "draft_test",
            "nodes": [
                {
                    "node_id": "n_locate_B",
                    "op": "LocateEntity",
                    "layer1": "ENTITY_IDENTIFICATION",
                    "layer2": "LocatePersonByAppearance",
                    "normalized_clip_role": "B",
                },
                {
                    "node_id": "n_locate_A",
                    "op": "LocateEntity",
                    "layer1": "ENTITY_IDENTIFICATION",
                    "layer2": "LocatePersonByAppearance",
                    "normalized_clip_role": "A",
                },
                {
                    "node_id": "n_bind",
                    "op": "CrossIntervalSamePersonBind",
                    "layer1": "CROSS_WINDOW_ENTITY_BIND",
                    "layer2": "CrossIntervalSamePersonBind",
                    "normalized_clip_role": None,
                },
                {
                    "node_id": "n_query",
                    "op": "QueryEarlierAttribute",
                    "layer1": "BOUND_ATTRIBUTE_QUERY",
                    "layer2": "QueryEarlierAttribute",
                    "normalized_clip_role": "A",
                },
            ],
            "edges": [
                {"from": "n_locate_B", "to": "n_bind"},
                {"from": "n_locate_A", "to": "n_bind"},
                {"from": "n_bind", "to": "n_query"},
            ],
            "semantic_validation": {"status": "OK"},
        }
        s8 = audit_draft_against_seen(g)
        self.assertEqual(
            s8["gates"]["training_exposure_check"]["status"], "UNCONFIRMED"
        )
        self.assertFalse(s8["gates"]["all_pass"])
        self.assertFalse(s8["atomic_covered_ood_candidate"])

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
            self.assertEqual(len(pairs), 1)
            self.assertFalse(pairs[0]["evidence_packet_complete"])
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
