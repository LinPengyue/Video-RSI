#!/usr/bin/env python3
"""Checks for Pilot v2.2 readiness artifacts."""

from __future__ import annotations

import csv
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "research_audit/lvbench_compositional/pilot_v2_2"
V2 = ROOT / "research_audit/lvbench_compositional/v2"
V21 = ROOT / "research_audit/lvbench_compositional/v2_1"
UNSEEN = "identify_person + query_action"
TEST_IDS = {
    "LVCOMP-V2-002",
    "LVCOMP-V2-003",
    "LVCOMP-V2-015",
    "LVCOMP-V2-024",
    "LVCOMP-V2-025",
    "LVCOMP-V2-031",
}
TRAIN_ACTION_IDS = {
    "LVCOMP-V2-100",
    "LVCOMP-V2-112",
    "LVCOMP-V2-115",
    "LVCOMP-V2-116",
}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class PilotV22Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (PILOT / "test_video_review.csv").open(encoding="utf-8", newline="") as handle:
            cls.test_reviews = list(csv.DictReader(handle))
        with (PILOT / "train_primitive_audit.csv").open(encoding="utf-8", newline="") as handle:
            cls.train_audit = list(csv.DictReader(handle))
        cls.revisions = _jsonl(PILOT / "revised_test_questions.jsonl")
        cls.ready = json.loads((PILOT / "pilot_readiness.json").read_text(encoding="utf-8"))
        cls.pilot_split = json.loads((V21 / "pilot_split.json").read_text(encoding="utf-8"))
        cls.candidates = {row["id"]: row for row in _jsonl(V2 / "candidates.jsonl")}

    def test_six_test_items_have_review_status(self) -> None:
        ids = {row["id"] for row in self.test_reviews}
        self.assertEqual(ids, TEST_IDS)
        allowed = {"SUPPORTED", "UNCERTAIN", "CONTRADICTED", "PENDING_HUMAN_REVIEW"}
        for row in self.test_reviews:
            self.assertIn(row["review_status"], allowed)
            self.assertIn(row["source_fact_status"], allowed)
            self.assertIn(row["composition_status"], allowed)
            self.assertIn(row["answer_status"], allowed)

    def test_four_train_action_items_audited(self) -> None:
        ids = {row["id"] for row in self.train_audit}
        self.assertEqual(ids, TRAIN_ACTION_IDS)
        allowed = {
            "ACTION_PRIMITIVE_VALID",
            "ACTION_PRIMITIVE_WEAK",
            "ACTION_PRIMITIVE_MISMATCH",
        }
        for row in self.train_audit:
            self.assertIn(row["action_primitive_status"], allowed)

    def test_revisions_keep_source_uids(self) -> None:
        self.assertEqual(len(self.revisions), 6)
        for row in self.revisions:
            source = self.candidates[row["id"]]
            self.assertEqual(row["source_uids"], source["source_uids"])
            self.assertEqual(row["source_questions"], source["source_questions"])
            self.assertEqual(row["source_answers"], source["source_answers"])
            self.assertFalse(row["video_verified"])

    def test_contradicted_not_in_pilot(self) -> None:
        ids = set(self.pilot_split["train_ids"]) | set(self.pilot_split["test_ids"])
        self.assertNotIn("LVCOMP-V2-038", ids)
        self.assertEqual(self.ready["gates"]["contradicted_in_pilot"], [])

    def test_strict_isolation_still_holds(self) -> None:
        train = [self.candidates[i] for i in self.pilot_split["train_ids"]]
        test = [self.candidates[i] for i in self.pilot_split["test_ids"]]
        self.assertEqual(sum(1 for row in train if row["composition_schema"] == UNSEEN), 0)
        self.assertFalse({row["video_id"] for row in train} & {row["video_id"] for row in test})
        train_uids = {(row["video_id"], uid) for row in train for uid in row["source_uids"]}
        test_uids = {(row["video_id"], uid) for row in test for uid in row["source_uids"]}
        self.assertFalse(train_uids & test_uids)
        self.assertEqual(self.ready["gates"]["schema_leak"], 0)
        self.assertEqual(self.ready["gates"]["video_overlap"], [])
        self.assertEqual(self.ready["gates"]["uid_overlap"], [])

    def test_supported_requires_judgment_not_official_answer_alone(self) -> None:
        judgments = json.loads((PILOT / "judgments.json").read_text(encoding="utf-8"))
        for row in self.test_reviews:
            if row["review_status"] == "SUPPORTED":
                self.assertIn(row["id"], judgments)
                self.assertTrue(row["evidence_timestamp"].strip())
                self.assertNotIn("official answer alone", row["notes"].lower())

    def test_readiness_status_is_consistent(self) -> None:
        self.assertIn(self.ready["status"], {"PILOT_READY_FOR_BASELINE", "PILOT_NOT_READY"})
        supported = sum(1 for row in self.test_reviews if row["review_status"] == "SUPPORTED")
        valid_action = sum(
            1 for row in self.train_audit if row["action_primitive_status"] == "ACTION_PRIMITIVE_VALID"
        )
        if supported < 3 or valid_action < 2:
            self.assertEqual(self.ready["status"], "PILOT_NOT_READY")
            self.assertTrue(self.ready["missing"])

    def test_prior_artifacts_unchanged(self) -> None:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--exit-code",
                "--",
                "research_audit/lvbench_compositional/qa_v0",
                "research_audit/lvbench_compositional/qa_v1",
                "research_audit/lvbench_compositional/qa_v1_clean",
                "research_audit/lvbench_compositional/v2",
                "research_audit/lvbench_compositional/v2_1",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_media_ignored(self) -> None:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(PILOT / "local_media" / "placeholder.mp4")],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
