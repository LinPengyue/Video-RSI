#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

WB = Path(__file__).resolve().parents[2]
R1 = WB / "seen_pilot_run_001"
R2 = WB / "seen_pilot_run_002"
REV = R2 / "scientific_reviews"
ENG = R2 / "eng"


class Run002AdjudicationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idx = json.loads((REV / "INDEX.json").read_text(encoding="utf-8"))
        cls.cat = json.loads((R2 / "CATALOG.json").read_text(encoding="utf-8"))
        cls.man = json.loads((R2 / "MANIFEST.json").read_text(encoding="utf-8"))
        cls.repair = json.loads((REV / "engineering_checks/SP205_A_media_repair.json").read_text(encoding="utf-8"))
        cls.handoff = json.loads(
            (REV / "handoff/run_002_scientific_adjudications_all6_v1.json").read_text(encoding="utf-8")
        )
        cls.r1_idx = json.loads((R1 / "scientific_reviews/INDEX.json").read_text(encoding="utf-8"))
        cls.tracka = json.loads(
            (WB.parents[1] / "track_a/TRACK_A_MIN_EXPERIMENT_READINESS.json").read_text(encoding="utf-8")
        )
        cls.iso = json.loads((R2 / "ISOLATION_CHECK.json").read_text(encoding="utf-8"))

    def _rec(self, pid: str) -> dict:
        return json.loads((REV / "RECORDS_BY_PACK" / f"{pid}.json").read_text(encoding="utf-8"))

    def test_six_decisions_distinct(self):
        d = self.idx["decisions"]
        self.assertEqual(set(d), {"SP201", "SP202", "SP203", "SP204", "SP205", "DN201"})
        self.assertEqual(d["SP201"], "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH")
        self.assertEqual(d["SP202"], "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH")
        self.assertEqual(d["SP203"], "DEFER_NEEDS_EVIDENCE_RELOCALIZATION")
        self.assertEqual(d["SP204"], "USER_REJECTED_AS_COMPOSITIONAL_CANDIDATE")
        self.assertEqual(d["SP205"], "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH")
        self.assertEqual(d["DN201"], "DEFER_TARGET_EVENT_RELOCALIZATION")
        self.assertEqual(
            self.idx["approved_compositional_candidates"],
            ["SP201", "SP202", "SP205"],
        )
        self.assertEqual(self.idx["user_assigned_unseen"], ["SP205"])
        self.assertEqual(self.idx["approved_but_split_unassigned"], ["SP201", "SP202"])

    def test_sp201_sp202_approved_and_shared_video_noted(self):
        a = self._rec("SP201")
        b = self._rec("SP202")
        self.assertEqual(a["video_id"], b["video_id"])
        self.assertIn("SP202", a["shared_video_with"])
        self.assertIn("SP201", b.get("shared_B_window_with", []) + b.get("shared_video_with", []))
        self.assertEqual(a["user_split_assignment"], "UNASSIGNED")
        self.assertEqual(b["user_split_assignment"], "UNASSIGNED")
        self.assertFalse(a["formal_seen_train"])
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

    def test_sp205_v05_approved_user_assigned_unseen(self):
        r = self._rec("SP205")
        self.assertEqual(r["graph_version"], "v0.5")
        self.assertEqual(r["user_decision"], "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH")
        self.assertEqual(r["user_split_decision"], "USER_ASSIGNED_UNSEEN")
        self.assertEqual(r["user_split_assignment"], "UNSEEN")
        self.assertFalse(r["formal_unseen"])
        self.assertFalse(r["formal_seen_train"])
        self.assertFalse(r["train_exposed"])
        g = r["directed_program_graph"]
        self.assertEqual(g["new_required_operator"], "CompareTemporalOrder")
        self.assertEqual(g["removed_required_operator"], "TemporalSuccessor")
        self.assertEqual(len(g["nodes"]), 7)
        self.assertEqual(len(g["edges"]), 7)
        self.assertFalse(r["evidence"]["middle_interval_required_for_v05"])
        self.assertTrue((REV / "APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS/SP205_v0.5.json").exists())
        self.assertTrue((REV / "HISTORY/SP205_v0.4_conditional.json").exists())
        # media SHA retained
        a_path = R2 / "media/SP205/A_wgBlACG927Y_202_370.mp4"
        self.assertEqual(hashlib.sha256(a_path.read_bytes()).hexdigest(), r["media_sha256"]["A"])
        # v0.4 repair audit retained but superseded for v0.5
        self.assertEqual(self.repair.get("applicability_to_v05"), "SUPERSEDED_NOT_REQUIRED_FOR_COMPARE_TEMPORAL_ORDER")
        self.assertTrue(self.idx["sp205_promoted_scientific"])
        self.assertTrue(self.idx["sp205_v04_blocker_superseded"])
        sp205 = next(i for i in self.cat["items"] if i["pack_id"] == "SP205")
        self.assertTrue(sp205["clips"]["A"].endswith("202_370.mp4"))
        self.assertEqual(sp205["scientific_review"]["user_decision"], "USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH")
        self.assertEqual(sp205["scientific_review"]["graph_version"], "v0.5")
        self.assertTrue(sp205["scientific_review"].get("user_assigned_unseen"))

    def test_video_group_isolation_wgBl(self):
        self.assertIn("wgBlACG927Y", self.iso["user_assigned_unseen_video_groups"])
        grp = self.iso["user_assigned_unseen_video_groups"]["wgBlACG927Y"]
        self.assertTrue(grp["forbid_in_seen_train"])
        self.assertFalse(grp["formal_unseen"])
        dn = self._rec("DN201")
        self.assertIn("SP205", dn["shared_video_with"])
        self.assertIn("training", dn["split_group_isolation_note"].lower())

    def test_gates_and_run001_untouched(self):
        for it in self.cat["items"]:
            self.assertFalse(it.get("formal_seen_train"))
            self.assertFalse(it.get("formal_gold"))
            self.assertFalse(it.get("train_exposed"))
            self.assertFalse(it.get("formal_unseen"))
        for g in (
            "formal_seen_train",
            "formal_unseen",
            "formal_gold",
            "train_exposed",
            "seen_pool_frozen",
            "approve_expensive_track_a_rsi",
        ):
            self.assertFalse(self.idx[g])
            self.assertFalse(self.cat["scientific_adjudication_ingest"][g])
        self.assertEqual(len(self.r1_idx["records"]), 5)
        self.assertEqual(len(self.r1_idx.get("approved_compositional_candidate_graphs", [])), 3)
        self.assertEqual(self.tracka["overall_status"], "NOT_READY")
        self.assertFalse(self.tracka["seen_pilot_context"]["approve_expensive_track_a_rsi"])

    def test_approved_graphs_include_sp205_v05(self):
        names = sorted(p.name for p in (REV / "APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS").glob("*.json"))
        self.assertEqual(names, ["SP201_v0.2.json", "SP202_v0.3.json", "SP205_v0.5.json"])

    def test_handoff_six_records_match(self):
        self.assertEqual(len(self.handoff["records"]), 6)
        self.assertEqual(self.handoff["validation"]["counts_expected"]["approved"], 3)

    def test_legacy_ingest_refuses_v05_rollback(self):
        proc = subprocess.run(
            [sys.executable, str(ENG / "ingest_scientific_adjudications_v1.py")],
            cwd=str(WB),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("REFUSING", proc.stderr)
        # SP205 still v0.5 after refused legacy run
        r = self._rec("SP205")
        self.assertEqual(r["graph_version"], "v0.5")
        self.assertEqual(r["user_split_decision"], "USER_ASSIGNED_UNSEEN")


if __name__ == "__main__":
    unittest.main()
