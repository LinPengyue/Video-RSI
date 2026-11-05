#!/usr/bin/env python3
"""WP3 wave production acceptance: evidence packs exist; no false Gold/SUPPORTED."""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[5]
WP3 = ROOT / "wp3_production"
TRACK_B = ROOT.parent
POOL = TRACK_B / "construction_video_pool.jsonl"
POLICY = TRACK_B / "SEALED_POOL_SPLIT_POLICY.json"

WAVE1 = {"USfvmoalqsw", "16Z-XQh9jhk", "CgvJqGxzRfE", "KktLi3UifPY", "gXnhqF0TqqI"}
WAVE2 = {"xECIRjlxM3U", "Aiem1w_TvaA", "ihfjEFGdZdc", "wgBlACG927Y", "W-BnDvXXfOs"}


class TestWP3WaveProduction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((WP3 / "WP3_WAVE_PRODUCTION_REPORT.json").read_text())
        cls.cov = json.loads((WP3 / "composition_signature_coverage.json").read_text())
        cls.staging = json.loads(
            (ROOT / "staging" / "wp3_wave1_wave2_draft_batch.json").read_text()
        )

    def test_ten_new_videos(self):
        self.assertEqual(set(self.report["video_lists"]["wave1"]), WAVE1)
        self.assertEqual(set(self.report["video_lists"]["wave2"]), WAVE2)
        self.assertEqual(self.report["production_metrics"]["n_new_videos"], 10)

    def test_no_false_certification(self):
        m = self.report["production_metrics"]
        self.assertEqual(m["n_semantic_events_certified"], 0)
        self.assertEqual(m["n_fact_verified"], 0)
        self.assertEqual(m["n_formal_gold"], 0)
        self.assertEqual(m["n_human_approved"], 0)
        self.assertEqual(m["n_cross_window_relations_valid"], 0)
        self.assertEqual(self.report["run_004_gate"], "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE")
        self.assertFalse(self.report["wp2_3_required"])

    def test_evidence_and_review_packets(self):
        self.assertGreaterEqual(self.report["production_metrics"]["n_rois_evidence_windows"], 40)
        self.assertGreaterEqual(self.report["production_metrics"]["n_relation_hypotheses"], 20)
        for pkt in self.report["paths"]["review_packets"]:
            self.assertTrue((REPO / pkt).is_file())
        for wave, vids in (("wave1", WAVE1), ("wave2", WAVE2)):
            for vid in vids:
                vr = WP3 / wave / "videos" / vid / "review_frames"
                self.assertTrue(vr.is_dir(), vid)
                jpgs = list(vr.rglob("*.jpg"))
                self.assertGreaterEqual(len(jpgs), 8, vid)

    def test_staging_not_gold_and_not_import_ready(self):
        self.assertEqual(self.staging["status"], "STAGING_ONLY_NOT_IMPORTED")
        self.assertFalse(self.staging["formal_gold"])
        for it in self.staging["items"]:
            self.assertFalse(it["formal_gold"])
            self.assertFalse(it["import_ready"])
            self.assertEqual(it["review_status"], "DRAFT")
            self.assertIsNone(it["question"])
            self.assertIsNone(it["answer"])

    def test_pool_and_policy(self):
        pool_ids = {
            json.loads(l)["construction_video_id"]
            for l in POOL.read_text().splitlines()
            if l.strip()
        }
        self.assertTrue(WAVE1.issubset(pool_ids))
        self.assertTrue(WAVE2.issubset(pool_ids))
        pol = json.loads(POLICY.read_text())
        exposed = set(pol["exposed_or_construction"])
        self.assertTrue((WAVE1 | WAVE2).issubset(exposed))
        self.assertEqual(pol["sealed_reservoir"]["current_ids"], [])
        self.assertTrue(pol["reconciliation_wp3"]["sealed_reservoir_untouched"])

    def test_prior_releases_immutable(self):
        for ver in ("v0.1.0", "v0.1.1", "v0.1.2"):
            m = json.loads((ROOT / "releases" / ver / "manifest.json").read_text())
            for f in m["files"]:
                p = ROOT / "releases" / ver / f["path"]
                h = hashlib.sha256(p.read_bytes()).hexdigest()
                self.assertEqual(h, f["sha256"], f"{ver}:{f['path']}")

    def test_splits_policy_unchanged(self):
        splits = json.loads((ROOT / "data" / "splits.json").read_text())
        self.assertEqual(splits["frozen_5_2"]["status"], "FROZEN_FOR_TRACK_A_MINIMAL_VALIDATION")
        self.assertEqual(splits["proposed_7_4_dev"]["status"], "PROPOSED")
        self.assertEqual(self.report["proposed_7_4_status"], "PROPOSED")
        self.assertTrue(self.report["frozen_5_2_unchanged"])
        self.assertEqual(self.cov["ood_policy"]["proposed_7_4_status"], "PROPOSED")

    def test_events_unresolved(self):
        for wave in ("wave1", "wave2"):
            path = WP3 / wave / "events_UNRESOLVED.jsonl"
            rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
            self.assertGreaterEqual(len(rows), 20)
            for r in rows:
                self.assertEqual(r["event_certification"], "UNRESOLVED")
                self.assertFalse(r["is_newly_discovered_semantic"])


if __name__ == "__main__":
    unittest.main()
