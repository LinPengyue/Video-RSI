#!/usr/bin/env python3
"""Regression for Seen Pilot run_001 scientific review ingest."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

WB = Path(__file__).resolve().parents[2]
PILOT = WB / "seen_pilot_run_001"
REV = PILOT / "scientific_reviews"
sys.path.insert(0, str(WB / "eng"))
sys.path.insert(0, str(PILOT / "eng"))

from seen_pilot_isolation import assert_seen_pilot_isolation  # noqa: E402


class SeenPilotScientificReviewIngestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads((REV / "RAW_seen_pilot_run_001_scientific_review.json").read_text(encoding="utf-8"))
        cls.index = json.loads((REV / "INDEX.json").read_text(encoding="utf-8"))
        cls.catalog = json.loads((PILOT / "CATALOG.json").read_text(encoding="utf-8"))
        cls.exclusion = json.loads((PILOT / "EXCLUSION_LIST.json").read_text(encoding="utf-8"))
        cls.sha = hashlib.sha256((REV / "RAW_seen_pilot_run_001_scientific_review.json").read_bytes()).hexdigest()
        cls.approved_unseen = json.loads((WB / "data" / "PROGRAM_GRAPH_LIBRARY_v1.json").read_text(encoding="utf-8"))

    def test_five_records_match_ids_and_windows(self):
        self.assertEqual(len(self.index["records"]), 5)
        by_raw = {r["pack_id"]: r for r in self.raw["reviews"]}
        by_cat = {it["pack_id"]: it for it in self.catalog["items"]}
        for pack_id in ["SP001", "SP002", "SP003", "SP004", "SP005"]:
            rec = json.loads((REV / "RECORDS_BY_PACK" / f"{pack_id}.json").read_text(encoding="utf-8"))
            raw = by_raw[pack_id]
            cat = by_cat[pack_id]
            self.assertEqual(rec["video_id"], raw["video_id"])
            self.assertEqual(rec["qa_uid"], raw["qa_uid"])
            self.assertEqual(rec["windows_seconds"], raw["windows_seconds"])
            wa, wb = cat["intervals"]["A"], cat["intervals"]["B"]
            self.assertEqual([int(wa["start_s"]), int(wa["end_s"])], raw["windows_seconds"]["A"])
            self.assertEqual([int(wb["start_s"]), int(wb["end_s"])], raw["windows_seconds"]["B"])
            # raw judgment retained
            self.assertEqual(rec["raw_scientific_judgment"], raw)

    def test_only_three_approved_compositional_candidates(self):
        approved = [r for r in self.index["records"] if r["compositional_candidate_graph_approved"]]
        self.assertEqual({r["pack_id"] for r in approved}, {"SP001", "SP002", "SP005"})
        not_app = [r for r in self.index["records"] if not r["compositional_candidate_graph_approved"]]
        self.assertEqual({r["pack_id"] for r in not_app}, {"SP003", "SP004"})
        graph_files = sorted(p.name for p in (REV / "APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS").glob("*.json"))
        self.assertEqual(graph_files, ["SP001_v0.3.json", "SP002_v0.2.json", "SP005_v0.2.json"])
        for bad in ("SP003", "SP004"):
            self.assertFalse(any(bad in n for n in graph_files))

    def test_sp005_retraction_preserved_and_not_b_only(self):
        rec = json.loads((REV / "RECORDS_BY_PACK" / "SP005.json").read_text(encoding="utf-8"))
        hist = rec["raw_scientific_judgment"]["correction_history"]
        self.assertIn("PREVIOUS_B_ONLY_SHORTCUT_CLASSIFICATION_RETRACTED", hist)
        self.assertNotEqual(rec["classification"], "B_ONLY_SHORTCUT_CONFIRMED")
        self.assertIn("B_ONLY_SHORTCUT_CONFIRMED", rec.get("forbidden_labels", []))
        self.assertEqual(rec["graph_decision"], "USER_APPROVED_STRUCTURED_GRAPH")
        self.assertEqual(rec["composition_necessity"], "USER_SUPPORTED_A_REQUIRED_FOR_TARGET_SELECTION")

    def test_sp004_uncertainty_preserved(self):
        rec = json.loads((REV / "RECORDS_BY_PACK" / "SP004.json").read_text(encoding="utf-8"))
        self.assertEqual(
            rec["classification"],
            "A_ONLY_ORDER_SHORTCUT_RISK_WITH_UNRESOLVED_DESCRIPTION_REFERENT",
        )
        self.assertEqual(rec["composition_necessity"], "NOT_ESTABLISHED")
        self.assertEqual(rec["graph_decision"], "COMPOSITION_GRAPH_NOT_APPROVED")

    def test_sp002_subtitle_boundary_engineering_check(self):
        eng = json.loads((REV / "engineering_checks" / "SP002_A_subtitle_boundary.json").read_text(encoding="utf-8"))
        self.assertEqual(eng["coverage_status"], "COVERED_IN_EXISTING_A_CLIP")
        self.assertTrue(eng["not_scientific_adjudication"])
        self.assertFalse(eng["conflicts_with_scientific_review"])
        frames = list((REV / "engineering_checks" / "SP002_A_boundary_frames").glob("*.jpg"))
        self.assertGreaterEqual(len(frames), 3)

    def test_gates_and_isolation_unchanged(self):
        for it in self.catalog["items"]:
            self.assertFalse(it.get("formal_seen_train"))
            self.assertFalse(it.get("formal_unseen"))
            self.assertFalse(it.get("formal_gold"))
            self.assertFalse(it.get("train_exposed"))
            self.assertFalse(it.get("seen_pool_frozen"))
            self.assertFalse(it.get("approve_expensive_track_a_rsi"))
        res = assert_seen_pilot_isolation(
            catalog_items=self.catalog["items"],
            hard_exclude_videos=self.exclusion["hard_exclude_videos"],
            hard_exclude_uids=self.exclusion["hard_exclude_qa_uids"],
        )
        self.assertEqual(res["status"], "PASS")
        # Unseen approved library untouched (still 4)
        approved = [
            r
            for r in self.approved_unseen["records"]
            if r.get("user_confirmation_status") == "USER_APPROVED_STRUCTURED_GRAPH"
        ]
        self.assertEqual(len(approved), 4)
        pilot_vids = {it["video_id"] for it in self.catalog["items"]}
        unseen_vids = {r["video_id"] for r in approved}
        self.assertEqual(pilot_vids & unseen_vids, set())

    def test_idempotent_reingest_no_duplicate_or_drift(self):
        before_idx_sha = self.index["source_sha256"]
        before_keys = {
            name: json.loads((REV / "RECORDS_BY_PACK" / name).read_text(encoding="utf-8"))["ingest"]["idempotency_key"]
            for name in ["SP001.json", "SP002.json", "SP003.json", "SP004.json", "SP005.json"]
        }
        r = subprocess.run(
            [sys.executable, str(PILOT / "eng" / "ingest_scientific_review.py")],
            cwd="/home/descfly/lpy/Video-RSI",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        after_names = sorted(p.name for p in (REV / "RECORDS_BY_PACK").glob("*.json"))
        self.assertEqual(after_names, ["SP001.json", "SP002.json", "SP003.json", "SP004.json", "SP005.json"])
        idx = json.loads((REV / "INDEX.json").read_text(encoding="utf-8"))
        self.assertEqual(idx["source_sha256"], before_idx_sha)
        self.assertTrue(idx.get("idempotent_replay"))
        for name, key in before_keys.items():
            rec = json.loads((REV / "RECORDS_BY_PACK" / name).read_text(encoding="utf-8"))
            self.assertEqual(rec["ingest"]["idempotency_key"], key)
            self.assertEqual(rec["ingest"]["source_sha256"], before_idx_sha)
        self.assertEqual(len(idx["approved_compositional_candidate_graphs"]), 3)

    def test_headline_counts(self):
        self.assertIn("3 USER_APPROVED", self.index["headline"])
        self.assertIn("2 NOT APPROVED", self.index["headline"])
        self.assertIn("0 formal Seen", self.index["headline"])
        self.assertEqual(self.sha, self.index["source_sha256"])


if __name__ == "__main__":
    unittest.main()
