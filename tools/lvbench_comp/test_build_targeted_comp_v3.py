#!/usr/bin/env python3
"""Checks for targeted compositional QA v3."""

from __future__ import annotations

import csv
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "research_audit/lvbench_compositional/targeted_v3"
UNSEEN = "identify_person + query_action"
META = Path("/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl")


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class TargetedV3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.unseen = _jsonl(V3 / "unseen_candidates.jsonl")
        cls.seen = _jsonl(V3 / "seen_candidates.jsonl")
        cls.split = json.loads((V3 / "strict_split_pilot.json").read_text(encoding="utf-8"))
        with (V3 / "video_pool_selection.csv").open(encoding="utf-8", newline="") as handle:
            cls.pool = list(csv.DictReader(handle))
        with META.open(encoding="utf-8") as handle:
            cls.uid_index = {}
            for line in handle:
                rec = json.loads(line)
                for qa in rec["qa"]:
                    cls.uid_index[(rec["key"], str(qa["uid"]))] = qa

    def test_new_items_trace_to_real_uids(self) -> None:
        for row in self.unseen + self.seen:
            for uid in row.get("related_official_uids") or []:
                self.assertIn((row["video_id"], str(uid)), self.uid_index)

    def test_no_duplicate_questions_within_unseen(self) -> None:
        norms = [" ".join(row["new_question"].lower().split()) for row in self.unseen]
        self.assertEqual(len(norms), len(set(norms)))

    def test_unseen_schema_absent_from_seen_train(self) -> None:
        train_ids = set(self.split["train_ids"])
        by_id = {row["question_id"]: row for row in self.seen + self.unseen}
        for cid in train_ids:
            self.assertNotEqual(by_id[cid]["composition_schema"], UNSEEN)
        self.assertEqual(self.split["validation"]["unseen_schema_in_train"], 0)

    def test_video_and_uid_isolation(self) -> None:
        self.assertEqual(self.split["validation"]["video_overlap"], [])
        self.assertEqual(self.split["validation"]["uid_overlap"], [])
        self.assertTrue(self.split["validation"]["ok"])
        self.assertFalse(set(self.split["train_videos"]) & set(self.split["test_videos"]))

    def test_contradicted_excluded(self) -> None:
        all_ids = set(self.split["train_ids"]) | set(self.split["test_ids"])
        self.assertNotIn("LVCOMP-V3-SEED-038", all_ids)
        for row in self.unseen:
            self.assertNotEqual(row.get("source_v2_id"), "LVCOMP-V2-038")

    def test_pool_and_outputs_exist(self) -> None:
        self.assertGreaterEqual(len(self.pool), 10)
        self.assertTrue((V3 / "REPORT.md").is_file())
        self.assertTrue((V3 / "composition_statistics.csv").is_file())
        self.assertTrue((V3 / "sample_quality_review.csv").is_file())
        self.assertGreaterEqual(len([row for row in self.unseen if row.get("origin") == "v3_targeted_official"]), 1)

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
                "research_audit/lvbench_compositional/pilot_v2_2",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
