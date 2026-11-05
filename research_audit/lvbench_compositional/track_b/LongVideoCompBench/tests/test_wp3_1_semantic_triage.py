#!/usr/bin/env python3
"""WP3.1 Wave1 semantic triage + import-guard regression."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
import sys

sys.path.insert(0, str(TOOLS))
from import_annotation_batch import import_batch  # noqa: E402

AUDIT = ROOT / "wp3_production" / "WP3_WAVE1_GPT_SEMANTIC_TRIAGE_AND_RELATION_AUDIT.json"
REFINED = ROOT / "staging" / "wp3_1_wave1_triage_refined_batch.json"
ORIG_STAGING = ROOT / "staging" / "wp3_wave1_wave2_draft_batch.json"


class TestWP31SemanticTriage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads(AUDIT.read_text())
        cls.refined = json.loads(REFINED.read_text())

    def test_report_exists_and_baseline(self):
        self.assertEqual(self.audit["work_package"], "WP3.1")
        self.assertEqual(
            self.audit["baseline_commit"],
            "1fbe837790fc94de2fd76c616c0578b9c4dec524",
        )
        self.assertTrue(self.audit["observation_rule"]["not_formal_gold"])
        self.assertIn(
            "CONTINUOUS_VIDEO_VERIFIED",
            self.audit["observation_rule"]["stills_must_not_become"],
        )

    def test_priority_decisions(self):
        by = {p["pair_id"]: p for p in self.audit["pairs"] if p.get("priority_rank")}
        self.assertEqual(
            by["USfvmoalqsw_PAIR2"]["decision"],
            "RELATION_FEASIBILITY_PASS_CANDIDATE_PENDING_HUMAN",
        )
        self.assertEqual(
            by["USfvmoalqsw_PAIR2"]["relation_evidence_tier"],
            "ORDERED_MULTIFRAME_SUGGESTS",
        )
        self.assertTrue(by["USfvmoalqsw_PAIR2"]["not_continuous_video_verified"])
        self.assertEqual(
            by["USfvmoalqsw_PAIR1"]["decision"], "REJECT_NO_CLEAR_CROSS_WINDOW_BIND"
        )
        self.assertIn("CONTROL", by["gXnhqF0TqqI_PAIR1"]["decision"])
        self.assertIn("CONTROL", by["16Z-XQh9jhk_PAIR2"]["decision"])
        self.assertTrue(by["KktLi3UifPY_PAIR2"]["decision"].startswith("HOLD"))
        self.assertEqual(
            self.audit["summary"]["relation_feasibility_pass_pending_human"],
            ["USfvmoalqsw_PAIR2"],
        )
        self.assertEqual(self.audit["summary"]["n_formal_gold"], 0)
        self.assertEqual(self.audit["summary"]["n_human_approved"], 0)

    def test_deferred_history_preserved(self):
        deferred = [
            p for p in self.audit["pairs"] if p.get("decision", "").startswith("DEFERRED")
        ]
        self.assertEqual(len(deferred), 5)
        self.assertEqual(self.audit["summary"]["n_deferred_low_priority"], 5)

    def test_roi_naming_sidecar(self):
        side = ROOT / "wp3_production" / "wave1" / "ROI_NAMING_CORRECTION_SIDECAR.jsonl"
        rows = [json.loads(l) for l in side.read_text().splitlines() if l.strip()]
        self.assertGreaterEqual(len(rows), 20)
        for r in rows:
            self.assertEqual(r["offset_seconds"]["named_start_minus_true_start"], 5.0)
            self.assertNotEqual(r["legacy_roi_id"], r["canonical_roi_id"])

    def test_genre_audit_flags_sports_mislabell(self):
        rows = [
            json.loads(l)
            for l in (ROOT / "wp3_production" / "wave1" / "GENRE_LABEL_AUDIT.jsonl")
            .read_text()
            .splitlines()
            if l.strip()
        ]
        by = {r["video_id"]: r for r in rows}
        self.assertEqual(by["16Z-XQh9jhk"]["status"], "AUTO_INCORRECT_VS_FRAMES")
        self.assertEqual(by["16Z-XQh9jhk"]["correction_proposed"], "concert_live_performance")

    def test_import_rejects_wp3_draft_staging(self):
        for path in (ORIG_STAGING, REFINED):
            result = import_batch(path, apply=False)
            self.assertEqual(result["status"], "REJECTED", path.name)
            codes = {e["code"] for e in result["errors"]}
            self.assertTrue(
                codes
                & {
                    "IMPORT_NOT_READY",
                    "SEMANTICS_NOT_CERTIFIED_FOR_IMPORT",
                    "ILLEGAL_OR_MISSING_PROGRAM_GRAPH",
                    "WP3_STUB_REQUIRES_EXPLICIT_IMPORT_READY",
                },
                codes,
            )

    def test_import_rejects_explicit_not_ready(self):
        batch = {
            "batch_id": "neg_wp3_not_ready",
            "items": [
                {
                    "source_item_id": "FAKE_PAIR9",
                    "import_ready": False,
                    "question": "q",
                    "answer": "a",
                    "formal_gold": False,
                    "split_assignment": "PENDING",
                    "program_graph": {
                        "nodes": [{"node_id": "n1", "op": "Locate"}],
                        "edges": [],
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "b.json"
            p.write_text(json.dumps(batch))
            result = import_batch(p, apply=False)
            self.assertEqual(result["status"], "REJECTED")
            self.assertTrue(any(e["code"] == "IMPORT_NOT_READY" for e in result["errors"]))

    def test_prior_releases_immutable(self):
        for ver in ("v0.1.0", "v0.1.1", "v0.1.2"):
            m = json.loads((ROOT / "releases" / ver / "manifest.json").read_text())
            for f in m["files"]:
                p = ROOT / "releases" / ver / f["path"]
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), f["sha256"])

    def test_no_new_public_media_this_round(self):
        media = self.audit["engineering_fixes"]["media_redistribution"]
        self.assertFalse(media["this_round_added_new_public_media_files"])
        self.assertEqual(
            media["status"], "LICENSE_UNCONFIRMED_STOP_NEW_PUBLIC_MEDIA"
        )


if __name__ == "__main__":
    unittest.main()
