#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

WB = Path(__file__).resolve().parents[2]
R1 = WB / "seen_pilot_run_001"
R2 = WB / "seen_pilot_run_002"
REV = R2 / "scientific_reviews"


class Run002AdjudicationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idx = json.loads((REV / "INDEX.json").read_text(encoding="utf-8"))
        cls.cat = json.loads((R2 / "CATALOG.json").read_text(encoding="utf-8"))
        cls.man = json.loads((R2 / "MANIFEST.json").read_text(encoding="utf-8"))
        cls.repair = json.loads((REV / "engineering_checks/SP205_A_media_repair.json").read_text(encoding="utf-8"))
        cls.r1_idx = json.loads((R1 / "scientific_reviews/INDEX.json").read_text(encoding="utf-8"))
        cls.tracka = json.loads(
            (WB.parents[1] / "track_a/TRACK_A_MIN_EXPERIMENT_READINESS.json").read_text(encoding="utf-8")
        )

    def _rec(self, pid: str) -> dict:
        return json.loads((REV / "RECORDS_BY_PACK" / f"{pid}.json").read_text(encoding="utf-8"))

    def test_six_decisions_distinct(self):
        d = self.idx["decisions"]
        self.assertEqual(set(d), {"SP201", "SP202", "SP203", "SP204", "SP205", "DN201"})
        self.assertEqual(d["SP201"], "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH")
        self.assertEqual(d["SP202"], "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH")
        self.assertEqual(d["SP203"], "DEFER_NEEDS_EVIDENCE_RELOCALIZATION")
        self.assertEqual(d["SP204"], "USER_REJECTED_AS_COMPOSITIONAL_CANDIDATE")
        self.assertEqual(d["SP205"], "CONDITIONAL_USER_APPROVAL_PENDING_ENGINEERING_ACCEPTANCE")
        self.assertEqual(d["DN201"], "DEFER_TARGET_EVENT_RELOCALIZATION")

    def test_sp201_sp202_approved_and_shared_video_noted(self):
        a = self._rec("SP201")
        b = self._rec("SP202")
        self.assertEqual(a["video_id"], b["video_id"])
        self.assertIn("SP202", a["shared_video_with"])
        self.assertIn("SP201", b.get("shared_B_window_with", []) + b.get("shared_video_with", []))
        self.assertTrue((REV / "APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS/SP201_v0.2.json").exists())
        self.assertTrue((REV / "APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS/SP202_v0.3.json").exists())

    def test_sp204_rejected_not_overridable(self):
        r = self._rec("SP204")
        self.assertEqual(r["user_decision"], "USER_REJECTED_AS_COMPOSITIONAL_CANDIDATE")
        self.assertIn("RELATION_UNVERIFIED", r["rejection_reason"])
        self.assertEqual(r["promotion_gate"], "REJECTED_NOT_OVERRIDABLE_BY_AUTOSCREEN")

    def test_sp203_dn201_no_auto_upgrade(self):
        for pid in ("SP203", "DN201"):
            r = self._rec(pid)
            self.assertTrue(r["user_decision"].startswith("DEFER"))
            self.assertFalse(r["relocalization"]["auto_approved"])
            self.assertFalse(r["relocalization"]["candidate_event_found"])
            self.assertEqual(r["promotion_gate"], "NO_AUTO_UPGRADE")

    def test_sp205_restored_but_not_promoted(self):
        self.assertTrue(self.repair["conditional_promotion"]["gates"]["A_media_restored_03_22_to_06_10"])
        self.assertFalse(self.repair["conditional_promotion"]["gates"]["critical_temporal_relation_model_accessible"])
        self.assertFalse(self.repair["conditional_promotion"]["promoted"])
        self.assertFalse(self.idx["sp205_promoted"])
        a_path = WB / self.repair["after"]["relpath"]
        self.assertTrue(a_path.exists())
        self.assertEqual(hashlib.sha256(a_path.read_bytes()).hexdigest(), self.repair["after"]["sha256"])
        # catalog points to restored A
        sp205 = next(i for i in self.cat["items"] if i["pack_id"] == "SP205")
        self.assertTrue(sp205["clips"]["A"].endswith("202_370.mp4"))
        self.assertEqual(sp205["scientific_review"]["user_decision"], "CONDITIONAL_USER_APPROVAL_PENDING_ENGINEERING_ACCEPTANCE")

    def test_gates_and_run001_untouched(self):
        for it in self.cat["items"]:
            self.assertFalse(it.get("formal_seen_train"))
            self.assertFalse(it.get("formal_gold"))
            self.assertFalse(it.get("train_exposed"))
        self.assertEqual(len(self.r1_idx["records"]), 5)
        self.assertEqual(len(self.r1_idx.get("approved_compositional_candidate_graphs", [])), 3)
        self.assertEqual(self.tracka["overall_status"], "NOT_READY")
        self.assertFalse(self.tracka["seen_pilot_context"]["approve_expensive_track_a_rsi"])

    def test_no_approved_graph_for_sp205_sp203_sp204_dn201(self):
        names = [p.name for p in (REV / "APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS").glob("*.json")]
        self.assertEqual(sorted(names), ["SP201_v0.2.json", "SP202_v0.3.json"])


if __name__ == "__main__":
    unittest.main()
