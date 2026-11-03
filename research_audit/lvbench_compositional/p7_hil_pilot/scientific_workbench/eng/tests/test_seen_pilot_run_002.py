#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

WB = Path(__file__).resolve().parents[2]
R1 = WB / "seen_pilot_run_001"
R2 = WB / "seen_pilot_run_002"


class SeenPilotRun002Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads((R2 / "CANDIDATE_SUPPLY_AUDIT.json").read_text(encoding="utf-8"))
        cls.catalog = json.loads((R2 / "CATALOG.json").read_text(encoding="utf-8"))
        cls.isolation = json.loads((R2 / "ISOLATION_CHECK.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((R2 / "MANIFEST.json").read_text(encoding="utf-8"))
        cls.r1 = json.loads((R1 / "CATALOG.json").read_text(encoding="utf-8"))
        cls.ex = json.loads((R1 / "EXCLUSION_LIST.json").read_text(encoding="utf-8"))
        cls.tracka = json.loads(
            (WB.parents[1] / "track_a" / "TRACK_A_MIN_EXPERIMENT_READINESS.json").read_text(encoding="utf-8")
        )

    def test_supply_audit_honest(self):
        self.assertGreaterEqual(self.audit["remaining_after_hard_and_run001"]["n_qa"], 1)
        self.assertIn("NEW human-confirmed compositional graph supply is 0", self.audit["honest_supply_verdict"])

    def test_priority_pack_count_and_gates(self):
        n = len(self.catalog["items"])
        self.assertGreaterEqual(n, 1)
        self.assertLessEqual(n, 6)
        self.assertEqual(self.catalog.get("auto_approved_structured_graphs"), 0)
        for it in self.catalog["items"]:
            self.assertIn(
                it["user_confirmation_status"],
                {"PENDING_HUMAN_VIDEO_REVIEW", "SCIENTIFIC_REVIEW_INGESTED"},
            )
            self.assertFalse(it["formal_seen_train"])
            self.assertFalse(it["formal_gold"])
            self.assertFalse(it["train_exposed"])

    def test_isolation_vs_hard_and_run001(self):
        self.assertEqual(self.isolation["status"], "PASS")
        self.assertEqual(self.isolation["overlap_hard_exclude"], [])
        self.assertEqual(self.isolation["overlap_run_001"], [])
        hard = set(self.ex["hard_exclude_videos"])
        r1v = {it["video_id"] for it in self.r1["items"]}
        for it in self.catalog["items"]:
            self.assertNotIn(it["video_id"], hard)
            self.assertNotIn(it["video_id"], r1v)

    def test_run001_not_overwritten(self):
        # run_001 still has scientific review ingest
        self.assertTrue(self.r1.get("scientific_review_ingest"))
        self.assertEqual(self.r1["scientific_review_ingest"]["user_approved_compositional_candidate_graphs"], 3)
        idx = json.loads((R1 / "scientific_reviews" / "INDEX.json").read_text(encoding="utf-8"))
        self.assertEqual(len(idx["records"]), 5)

    def test_manifest_and_media(self):
        for entry in self.manifest["files"]:
            if entry["role"].startswith("DN"):
                continue
            p = WB / entry["relpath"]
            self.assertTrue(p.exists(), entry["relpath"])
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), entry["sha256"])
        for it in self.catalog["items"]:
            self.assertEqual(it["media_status"], "OK")

    def test_track_a_readiness_not_ready(self):
        self.assertEqual(self.tracka["overall_status"], "NOT_READY")
        self.assertFalse(self.tracka["seen_pilot_context"]["approve_expensive_track_a_rsi"])
        statuses = {c["status"] for c in self.tracka["checklist"]}
        self.assertTrue(statuses <= {"READY", "NOT_READY", "NOT_VERIFIED"})
        self.assertNotIn("READY", {self.tracka["overall_status"]})

    def test_ui_markers(self):
        index = (WB / "index.html").read_text(encoding="utf-8")
        self.assertIn("seen-pilot-2", index)
        app = (WB / "v2" / "app.js").read_text(encoding="utf-8")
        self.assertIn("seen_pilot_run_002", app)
        self.assertIn("renderSeenPilot2Pane", app)


if __name__ == "__main__":
    unittest.main()
