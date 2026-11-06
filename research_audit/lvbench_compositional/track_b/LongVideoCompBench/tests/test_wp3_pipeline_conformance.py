#!/usr/bin/env python3
"""WP3 pipeline conformance scientific correction tests + negatives."""
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
REGISTRY = (
    ROOT / "wp3_production" / "wp3_4" / "trusted_human_review_registry" / "records.jsonl"
)

sys.path.insert(0, str(TOOLS))
from pipeline_conformance.s3_s5_relation_qa import (  # noqa: E402
    QA_FAMILIES,
    RelationCandidate,
    SourcedFact,
    generate_qa_from_relation,
    validate_program_graph_semantics,
)
from pipeline_conformance.s6_necessity import (  # noqa: E402
    combine_necessity,
    model_necessity,
    shortcut_audit,
    structural_necessity,
)
from pipeline_conformance.s7_s9_gates import release_gate_check  # noqa: E402
from pipeline_conformance.s8_signature_feedback import (  # noqa: E402
    audit_draft_against_seen,
    load_seen_graphs,
    normalize_layer2_operator,
    seen_layer_vocab,
)


WORD_NAMES = [
    "视频登记",
    "事件发现",
    "证据封包",
    "语义审查",
    "关系发现",
    "原创 QA 与程序图草案",
    "必要性审查",
    "答案与程序图科学审批",
    "结构审计",
    "版本入库",
]


class TestWP3PipelineConformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = json.loads((OUT / "S0_S9_CONFORMANCE_MATRIX.json").read_text())
        cls.reg = json.loads((OUT / "regression_cases.json").read_text())
        cls.report = json.loads(
            (OUT / "WP3_PIPELINE_CONFORMANCE_REPAIR_REPORT.json").read_text()
        )

    def test_matrix_word_v1_names(self):
        stages = self.matrix["stages"]
        self.assertEqual([s["stage"] for s in stages], [f"S{i}" for i in range(10)])
        self.assertEqual([s["name_zh"] for s in stages], WORD_NAMES)
        self.assertEqual(self.matrix["word_stage_names_zh"], WORD_NAMES)
        for s in stages:
            self.assertTrue(s["modules"])
            self.assertIn("run_evidence", s)
            self.assertIn("incomplete", s)

    def test_generator_quality_not_only_self_declare(self):
        """Template QA quality must not rely only on not_video_hardcoded=true."""
        src = (TOOLS / "pipeline_conformance" / "s3_s5_relation_qa.py").read_text()
        # No per-video hardcode branches in generator
        self.assertNotIn('if rel.video_id ==', src)
        self.assertNotIn('if video_id ==', src)
        for case in self.reg["cases"].values():
            qa = case["s3_s5"]["qa"]
            qc = case["s3_s5"]["quality_checks"]
            self.assertTrue(qc["uses_family_template"])
            self.assertTrue(qc["question_contains_filled_slots"])
            self.assertTrue(qc["generator_has_no_video_id_branch"])
            self.assertTrue(qc["self_declared_not_video_hardcoded_insufficient_alone"])
            self.assertIn(qa["family_template_id"], QA_FAMILIES)
            self.assertTrue(qa["question_built_from_template"])
            self.assertFalse(qa["formal_gold"])
            # answer attrs not certified by Human identity
            self.assertEqual(
                qa["answer_certification"],
                "ATTRIBUTE_NOT_COVERED_BY_HUMAN_IDENTITY_CLAIM",
            )
            self.assertTrue(qa["bind_does_not_certify_answer"])

    def test_graph_dataflow_both_locates_to_bind(self):
        for case in self.reg["cases"].values():
            g = case["s3_s5"]["program_graph"]
            self.assertEqual(g["dataflow_topology"], "LocateB+LocateA→Bind→Query")
            self.assertEqual(g["program_execution"], "PROGRAM_EXECUTION_NOT_RUN")
            self.assertFalse(g["executable_pass"])
            pairs = {(e["from"], e["to"]) for e in g["edges"]}
            self.assertIn(("n_locate_B", "n_bind"), pairs)
            self.assertIn(("n_locate_A", "n_bind"), pairs)
            self.assertIn(("n_bind", "n_query"), pairs)
            # Sequential locate→locate chain is not the required topology
            self.assertNotIn(("n_locate_B", "n_locate_A"), pairs)
            sv = g["semantic_validation"]
            self.assertEqual(sv["status"], "OK")
            self.assertFalse(sv["executable_pass"])
            for n in g["nodes"]:
                self.assertTrue(n.get("inputs"))
                self.assertTrue(n.get("outputs"))
                self.assertIn("evidence_refs", n)

    def test_bad_edges_fail_semantic_validation(self):
        bad = {
            "nodes": [
                {
                    "node_id": "n_locate_A",
                    "inputs": [{"name": "clip", "type": "VideoWindow"}],
                    "outputs": [{"name": "entity_ref", "type": "EntityRef"}],
                    "evidence_refs": [],
                    "normalized_clip_role": "A",
                },
                {
                    "node_id": "n_locate_B",
                    "inputs": [{"name": "clip", "type": "VideoWindow"}],
                    "outputs": [{"name": "entity_ref", "type": "EntityRef"}],
                    "evidence_refs": [],
                    "normalized_clip_role": "B",
                },
            ],
            "edges": [],  # A/B nodes without required dataflow
        }
        r = validate_program_graph_semantics(bad)
        self.assertEqual(r["status"], "FAIL")
        self.assertFalse(r["executable_pass"])
        self.assertEqual(r["program_execution"], "PROGRAM_EXECUTION_NOT_RUN")

        mismatched = {
            "nodes": [
                {
                    "node_id": "n_locate_B",
                    "inputs": [{"name": "clip", "type": "VideoWindow"}],
                    "outputs": [{"name": "entity_ref", "type": "EntityRef"}],
                    "evidence_refs": ["e"],
                },
                {
                    "node_id": "n_locate_A",
                    "inputs": [{"name": "clip", "type": "VideoWindow"}],
                    "outputs": [{"name": "entity_ref", "type": "EntityRef"}],
                    "evidence_refs": ["e"],
                },
                {
                    "node_id": "n_bind",
                    "inputs": [
                        {"name": "entity_ref_B", "type": "EntityRef"},
                        {"name": "entity_ref_A", "type": "EntityRef"},
                    ],
                    "outputs": [{"name": "bound_entity", "type": "BoundEntityRef"}],
                    "evidence_refs": [],
                },
                {
                    "node_id": "n_query",
                    "inputs": [{"name": "bound_entity", "type": "BoundEntityRef"}],
                    "outputs": [{"name": "answer", "type": "AnswerValue"}],
                    "evidence_refs": [],
                },
            ],
            "edges": [
                # Wrong: only B feeds bind; A missing; type ok on existing
                {
                    "from": "n_locate_B",
                    "to": "n_bind",
                    "from_port": "entity_ref",
                    "to_port": "entity_ref_B",
                },
                {
                    "from": "n_bind",
                    "to": "n_query",
                    "from_port": "bound_entity",
                    "to_port": "bound_entity",
                },
            ],
        }
        r2 = validate_program_graph_semantics(mismatched)
        self.assertEqual(r2["status"], "FAIL")
        self.assertIn("BIND_REQUIRES_BOTH_LOCATE_INPUTS", r2["codes"])

    def test_fail_on_unknown_bind(self):
        self.assertEqual(self.reg["negative_unknown_bind"]["status"], "FAIL")
        self.assertIn("UNKNOWN", self.reg["negative_unknown_bind"]["failure_reason"])

    def test_s6_provenance_classes(self):
        for name, case in self.reg["cases"].items():
            nec = case["s6"]
            self.assertEqual(nec["model"]["status"], "NOT_RUN")
            self.assertFalse(nec["model"]["forged"])
            self.assertFalse(nec["strict_necessity_proof"])
            self.assertFalse(nec["structural_strict_proof"])
            trail = nec["structural"]["trail"]
            self.assertIn("provenance", trail)
            classes = trail["provenance"]["classes"]
            self.assertIn("engineer_unverified_shortcut_hypothesis", classes)
            self.assertTrue(nec["human_identity_does_not_imply_pass"])
            self.assertEqual(case["inventory"], "CONTROL")

        # USFV: multi-signage → structural UNKNOWN (not strict FAIL proof)
        usfv = self.reg["cases"]["USfvmoalqsw_PAIR2"]["s6"]["structural"]
        self.assertEqual(usfv["verdict"], "UNKNOWN")
        self.assertFalse(usfv["strict_proof"])
        self.assertTrue(usfv["control_risk"])

        # Kbah: provisional FAIL without strict proof
        kbah = self.reg["cases"]["KbahC-QCKU8_EF_PAIR1"]["s6"]["structural"]
        self.assertEqual(kbah["verdict"], "FAIL")
        self.assertFalse(kbah["strict_proof"])

    def test_forged_model_run_rejected(self):
        st = {
            "channel": "structural",
            "verdict": "PASS",
            "strict_proof": True,
            "reason": "x",
            "trail": {},
        }
        sc = shortcut_audit({})
        # Missing raw outputs → NOT_RUN, cannot PASS
        m = model_necessity(
            blind_model_available=True,
            a_only_run={"run_id": "r1", "correct": False},
            b_only_run={"run_id": "r2", "correct": False},
            ab_run={"run_id": "r3", "correct": True},
        )
        self.assertEqual(m["status"], "NOT_RUN")
        c = combine_necessity(st, m, sc)
        self.assertNotEqual(c["overall_verdict"], "PASS")

        forged = model_necessity(
            blind_model_available=True,
            a_only_run={
                "run_id": "f1",
                "model_version": "x",
                "input_condition": "A",
                "evidence_isolation": "ok",
                "raw_output": "no",
                "correct": False,
                "forged": True,
            },
            b_only_run={
                "run_id": "f2",
                "model_version": "x",
                "input_condition": "B",
                "evidence_isolation": "ok",
                "raw_output": "no",
                "correct": False,
            },
            ab_run={
                "run_id": "f3",
                "model_version": "x",
                "input_condition": "AB",
                "evidence_isolation": "ok",
                "raw_output": "yes",
                "correct": True,
            },
        )
        self.assertEqual(forged["status"], "NOT_RUN")
        self.assertTrue(forged["forged"])

    def test_s8_l1_covered_l2_uncovered_not_pure_ood(self):
        for name, case in self.reg["cases"].items():
            s8 = case["s8_audit"]
            self.assertEqual(
                s8["provisional_label_before_recompute"],
                "STRUCTURAL_NOVELTY_CANDIDATE_UNVERIFIED",
            )
            self.assertTrue(s8["atomic_covered_in_seen_layer1"])
            self.assertFalse(s8["atomic_covered_in_seen_layer2"])
            self.assertTrue(s8["layer1_coverage_does_not_imply_layer2"])
            self.assertFalse(s8["atomic_covered_ood_candidate"])
            self.assertNotEqual(s8["bucket"], "ATOMIC_COVERED_COMPOSITION_OOD_CANDIDATE")
            self.assertEqual(s8["bucket"], "L1_COVERED_L2_UNCOVERED_OR_UNKNOWN")
            self.assertFalse(s8["freeze_unseen"])

    def test_unnormalized_ops_not_forced_equivalent(self):
        seen = load_seen_graphs()
        _, seen_l2 = seen_layer_vocab(seen)
        r = normalize_layer2_operator("CrossIntervalSamePersonBind", seen_l2)
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertIsNone(r["normalized"])
        r2 = normalize_layer2_operator("LocatePersonByAppearance", seen_l2)
        self.assertEqual(r2["status"], "UNKNOWN")
        # Exact Seen label works
        sample = next(iter(seen_l2))
        r3 = normalize_layer2_operator(sample, seen_l2)
        self.assertEqual(r3["status"], "EXACT")
        self.assertEqual(r3["normalized"], sample)

    def test_human_claim_does_not_certify_answer(self):
        for case in self.reg["cases"].values():
            self.assertTrue(case["human_identity_does_not_certify_answer"])
            rel = case["relation"]
            self.assertEqual(rel["human_bind_scope"], "CROSS_WINDOW_PERSON_IDENTITY")
            for key in rel["fact_a"]["uncertified_attribute_keys"]:
                self.assertTrue(key)

    def test_release_gate_requires_claim_chain(self):
        for case in self.reg["cases"].values():
            gate = case["s9_release_gate"]
            self.assertFalse(gate["allowed"])
            self.assertFalse(gate["formal_gold"])
            self.assertFalse(gate["production_closed_loop_claimed"])
            self.assertIn("NECESSITY_NOT_PASS", gate["codes"])
            self.assertIn("PROGRAM_EXECUTION_NOT_PASS", gate["codes"])

        # Claim ID only, no chain → blocked
        fake_item = {
            "bind_claim_ids": ["CLAIM_FAKE_ONLY_ID"],
            "video_id": "KbahC-QCKU8",
            "formal_gold": False,
            "necessity_overall": "PASS",
            "model_necessity_status": "RUN",
            "necessity_strict_proof": True,
            "program_execution": "EXECUTABLE_PASS",
            "claim_id_only_without_chain": True,
        }
        g = release_gate_check(fake_item, trusted_records_jsonl=REGISTRY)
        self.assertFalse(g["allowed"])
        self.assertTrue(
            any("MISSING_TRUSTED_REGISTRY_CLAIMS" in c for c in g["codes"])
            or "CLAIM_ID_ONLY_WITHOUT_SOURCE_CHAIN" in g["codes"]
        )

        # Existing claim but answer certified by human relation → blocked
        real = {
            "bind_claim_ids": ["CLAIM_KBAH_ADULT_SAME"],
            "video_id": "KbahC-QCKU8",
            "windows": {"A": [90.0, 100.0], "B": [2160.0, 2170.0]},
            "clip_sha256": {
                "A": "58812c619252d45f070c9372e49e1146a287840a16ff355fc1ec699a5b8b4fba",
                "B": "2afce6b5de756c29e5844dfef299a98f02bb4024e334ca26618d0dea44facc6c",
            },
            "formal_gold": False,
            "necessity_overall": "PASS",
            "model_necessity_status": "RUN",
            "necessity_strict_proof": True,
            "program_execution": "EXECUTABLE_PASS",
            "answer_certified_by_human_relation": True,
        }
        g2 = release_gate_check(real, trusted_records_jsonl=REGISTRY)
        self.assertFalse(g2["allowed"])
        self.assertIn("HUMAN_RELATION_MUST_NOT_CERTIFY_ANSWER_ATTRIBUTES", g2["codes"])

    def test_no_scaled_gold_claim(self):
        self.assertFalse(self.report["counts"]["formal_gold"])
        self.assertEqual(self.report["counts"]["effective_compositional_qa"], 0)
        self.assertEqual(self.report["counts"]["atomic_covered_ood"], 0)
        self.assertFalse(self.report["scaled_gold_capacity_claimed"])
        self.assertFalse(self.report["production_closed_loop_claimed"])
        self.assertFalse(self.matrix["protections"]["scaled_gold_capacity_claimed"])
        self.assertFalse(self.matrix["protections"]["production_closed_loop_claimed"])

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
            "strict_proof": True,
            "reason": "x",
            "trail": {},
        }
        sc = shortcut_audit(
            {"ocr_answer_in_window_A": True, "single_candidate_entity_in_A": False}
        )
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
