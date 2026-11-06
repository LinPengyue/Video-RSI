#!/usr/bin/env python3
"""WP3.4: media git-tracking audit + cert-loop protections (no auto Gold)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[5]
OUT = ROOT / "wp3_production" / "wp3_4"
REPORTS = ROOT / "reports"
MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm", ".mkv", ".mov"}
AB_VIDEOS_PREFIX = (
    "research_audit/lvbench_compositional/track_b/LongVideoCompBench/"
    "wp3_production/wp3_3/ab_dev5/videos/"
)


def git_ls_files(pathspec: str) -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(REPO), "ls-files", pathspec], text=True
    )
    return [ln for ln in out.splitlines() if ln.strip()]


class TestWP34(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.erratum = json.loads((OUT / "WP3_3_MEDIA_ERRATUM.json").read_text())
        cls.report = json.loads(
            (OUT / "WP3_4_MEDIA_COMPLIANCE_AND_CERT_LOOP_REPORT.json").read_text()
        )
        cls.evalc = json.loads((OUT / "WP3_4_DISCOVERY_EVAL_CORRECTION.json").read_text())
        cls.kbah = json.loads(
            (OUT / "wp3_4_KbahC_EF_PAIR1_HUMAN_REVIEW_PACKET.json").read_text()
        )
        cls.usfv = json.loads(
            (OUT / "wp3_4_USFV_PAIR2_HUMAN_REVIEW_PACKET.json").read_text()
        )
        cls.nec = json.loads((OUT / "wp3_4_necessity_qa_gate.json").read_text())
        cls.reg = json.loads((OUT / "trusted_human_review_registry" / "REGISTRY_META.json").read_text())

    def test_ab_dev5_jpgs_not_git_tracked(self):
        """Audit git ls-files, not report booleans."""
        tracked = [
            f
            for f in git_ls_files(AB_VIDEOS_PREFIX)
            if Path(f).suffix.lower() in MEDIA_EXTS
        ]
        self.assertEqual(
            tracked,
            [],
            f"WP3.3 AB review media still tracked ({len(tracked)} files)",
        )

    def test_media_erratum_records_history_exposure(self):
        self.assertTrue(self.erratum["correction_this_round"]["history_still_contains_blobs"])
        self.assertFalse(self.erratum["correction_this_round"]["force_push"])
        self.assertEqual(
            self.erratum["current_tree_audit"]["wp3_3_ab_dev5_videos_tracked_media"], 0
        )
        self.assertTrue(
            self.erratum["policy_going_forward"]["tests_must_audit_git_ls_files"]
        )

    def test_eval_inconclusive_not_superior(self):
        self.assertEqual(
            self.evalc["fixed_method_conclusion"],
            "INDEPENDENT_STABILITY_PROXY_DISCOVERY_PILOT_INCONCLUSIVE",
        )
        self.assertEqual(self.evalc["counts"]["HF_PASS_CANDIDATE"], 0)
        self.assertEqual(self.evalc["counts"]["EF_PASS_CANDIDATE"], 1)
        self.assertEqual(self.evalc["counts"]["formal_gold"], 0)
        self.assertEqual(self.evalc["counts"]["certified_relations"], 0)
        self.assertTrue(self.evalc["cost"]["EF_compute_higher_than_HF"])
        self.assertTrue(self.evalc["historical_ab_not_rewritten"])

    def test_no_auto_human_certification(self):
        self.assertEqual(self.kbah["current_status"], "AWAITING_HUMAN_SCIENTIFIC_OWNER")
        self.assertFalse(self.kbah["auto_certified"])
        self.assertFalse(self.kbah["formal_gold"])
        self.assertEqual(
            self.kbah["human_adjudication"]["status"], "NOT_OBTAINED_THIS_ROUND"
        )
        self.assertEqual(
            self.usfv["current_status"], "PENDING_HUMAN_IDENTITY_ADJUDICATION"
        )
        self.assertFalse(self.usfv["auto_certified_same_person"])
        self.assertFalse(self.usfv["signature_vs_historical_A"]["promote_unseen"])

    def test_necessity_not_auto_pass(self):
        self.assertEqual(self.nec["counts"]["necessity_PASS"], 0)
        self.assertEqual(self.nec["counts"]["formal_gold"], 0)
        self.assertEqual(self.nec["counts"]["qa_with_program_graph"], 0)

    def test_trusted_registry_empty_and_separated(self):
        self.assertTrue(self.reg["append_only"])
        self.assertTrue(self.reg["separated_from_staging"])
        self.assertEqual(self.reg["records_this_round"], 0)
        records = (OUT / "trusted_human_review_registry" / "records.jsonl").read_text()
        self.assertEqual(records.strip(), "")

    def test_report_protections(self):
        self.assertFalse(self.report["protections"]["track_a_modified"])
        self.assertFalse(self.report["protections"]["new_video_scan"])
        self.assertEqual(self.report["protections"]["proposed_7_4"]["status"], "PROPOSED")
        self.assertTrue(self.report["protections"]["no_auto_gold"])

    def test_releases_immutable(self):
        for ver in ("v0.1.0", "v0.1.1", "v0.1.2"):
            m = json.loads((ROOT / "releases" / ver / "manifest.json").read_text())
            for f in m["files"]:
                p = ROOT / "releases" / ver / f["path"]
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), f["sha256"])

    def test_reports_mirrored(self):
        for name in (
            "WP3_3_MEDIA_ERRATUM.json",
            "WP3_4_MEDIA_COMPLIANCE_AND_CERT_LOOP_REPORT.json",
            "WP3_4_DISCOVERY_EVAL_CORRECTION.json",
        ):
            self.assertTrue((OUT / name).exists())
            self.assertTrue((REPORTS / name).exists())


if __name__ == "__main__":
    unittest.main()
