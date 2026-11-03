#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

PILOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
TB = ROOT / "research_audit/lvbench_compositional/track_b"


class FamilyLevelPilotV01Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((PILOT / "PILOT_CONFIG.json").read_text(encoding="utf-8"))
        cls.inv = json.loads((PILOT / "PILOT_INVENTORY.json").read_text(encoding="utf-8"))
        cls.integ = json.loads((PILOT / "reports/ENGINEERING_INTEGRITY_REPORT.json").read_text(encoding="utf-8"))
        cls.mf = json.loads((PILOT / "p2_multiframe_link/MULTIFRAME_DIGEST.json").read_text(encoding="utf-8"))
        cls.p3 = json.loads((PILOT / "p3_new_video_discovery/batch_manifest.json").read_text(encoding="utf-8"))
        cls.gate = json.loads((PILOT / "RUN_004_GATE.json").read_text(encoding="utf-8"))
        cls.sealed = json.loads((TB / "SEALED_POOL_SPLIT_POLICY.json").read_text(encoding="utf-8"))

    def test_roles_and_counts(self):
        self.assertEqual(self.cfg["seen"], ["SP001", "SP002", "SP005", "SP201", "SP202"])
        self.assertEqual(self.cfg["unseen"], ["P7_VTCD_C2", "P7_TJR_R3"])
        self.assertEqual(set(self.cfg["hold"]), {"P7_R4_F1", "P7_R4_F2", "SP205"})
        self.assertEqual(self.inv["counts"]["total"], 10)

    def test_formal_gates_false(self):
        for doc in (self.cfg, self.inv, self.integ, self.mf, self.p3, self.gate):
            for g in (
                "formal_seen_train",
                "formal_unseen",
                "formal_gold",
                "train_exposed",
                "seen_pool_frozen",
                "approve_expensive_track_a_rsi",
            ):
                self.assertFalse(doc[g], g)

    def test_open_ended_only(self):
        for it in self.inv["items"]:
            self.assertEqual(it["qa_format"], "OPEN_ENDED")
            self.assertFalse(it["multichoice_auto_generated"])

    def test_sp201_sp202_isolation_group(self):
        a = next(i for i in self.inv["items"] if i["item_id"] == "SP201")
        b = next(i for i in self.inv["items"] if i["item_id"] == "SP202")
        self.assertEqual(a["video_id"], b["video_id"])
        self.assertEqual(a["isolation_group"], b["isolation_group"])
        self.assertTrue(self.integ["isolation"]["sp201_sp202_same_group"])

    def test_seen_unseen_video_disjoint(self):
        self.assertTrue(self.integ["isolation"]["seen_unseen_video_disjoint"])
        self.assertEqual(self.integ["isolation"]["status"], "PASS")

    def test_sealed_untouched(self):
        self.assertTrue(self.integ["isolation"]["sealed_reservoir_untouched"])
        self.assertEqual(self.sealed["sealed_reservoir"]["status"], "UNTOUCHED_PLACEHOLDER")

    def test_structural_ok(self):
        self.assertTrue(self.integ["structural_consistency"]["all_ok"])

    def test_semantic_eq_unauthenticated(self):
        for p in self.integ["computable_structure_comparison"]["pairwise"]:
            self.assertEqual(p["semantic_equivalence"], "UNAUTHENTICATED_NO_APPROVED_RULE")

    def test_necessity_not_model_ablation(self):
        for row in self.integ["a_only_b_only_human_audit"]:
            self.assertEqual(row["disclaimer"], "HUMAN_JUDGMENT_NOT_INDEPENDENT_MODEL_ABLATION")

    def test_multiframe_zero_qualifying(self):
        self.assertEqual(self.mf["prior_feasibility_summary"]["n_run004_qualifying_relations"], 0)
        self.assertEqual(self.mf["recheck_evidence_sha"]["status"], "PASS")
        self.assertTrue(self.mf["run_003_untouched"] if "run_003_untouched" in self.mf else True)

    def test_p3_budget_and_pending(self):
        self.assertLessEqual(self.p3["n_rois"], 4)
        for roi in self.p3["rois"]:
            self.assertLessEqual(roi["n_frames"], 16)
            self.assertEqual(roi["observation_slot"]["status"], "PENDING_GPT_VISUAL_OBSERVATION")
        self.assertEqual(self.p3["run_004_status"], "NOT_STARTED")

    def test_run_004_not_started(self):
        self.assertEqual(self.gate["run_004_status"], "NOT_STARTED")
        self.assertEqual(self.gate["status"], "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE")

    def test_provenance_snapshots_exist(self):
        for name in (
            "SP001_v0.3.json",
            "SP201_v0.2.json",
            "SP205_v0.5.json",
            "P7_VTCD_C2.json",
            "P7_TJR_R3.json",
        ):
            self.assertTrue((PILOT / "provenance_snapshots" / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
