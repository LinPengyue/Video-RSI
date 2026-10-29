#!/usr/bin/env python3
"""Checks for LVBench compositional generalization v2 artifacts."""

from __future__ import annotations

import csv
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "research_audit/lvbench_compositional/v2"
CLEAN = ROOT / "research_audit/lvbench_compositional/qa_v1_clean/candidates.jsonl"
V1 = ROOT / "research_audit/lvbench_compositional/qa_v1"
V0 = ROOT / "research_audit/lvbench_compositional/qa_v0"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class BuildCompQAV2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.candidates = _rows(V2 / "candidates.jsonl")
        cls.pending = _rows(V2 / "candidate_pairs_pending.jsonl")
        with (V2 / "sample_review.csv").open(encoding="utf-8", newline="") as handle:
            cls.sample = list(csv.DictReader(handle))
        with (V2 / "composition_statistics.csv").open(encoding="utf-8", newline="") as handle:
            cls.stats = list(csv.DictReader(handle))
        cls.feasibility = (V2 / "split_feasibility.md").read_text(encoding="utf-8")

    def test_sample_review_covers_ten_items(self) -> None:
        self.assertEqual(len(self.sample), 10)
        ids = {row["id"] for row in self.sample}
        expected = {
            "LVCOMP-V1-008", "LVCOMP-V1-010", "LVCOMP-V1-012", "LVCOMP-V1-017", "LVCOMP-V1-022",
            "LVCOMP-V1-029", "LVCOMP-V1-030", "LVCOMP-V1-032", "LVCOMP-V1-038", "LVCOMP-V1-043",
        }
        self.assertEqual(ids, expected)
        for row in self.sample:
            self.assertIn(row["verdict"], {"SUPPORTED", "UNCERTAIN", "CONTRADICTED"})

    def test_candidates_have_schemas_and_source_trace(self) -> None:
        self.assertGreaterEqual(len(self.candidates), 50)
        questions = []
        for row in self.candidates:
            self.assertTrue(row["source_uids"])
            self.assertEqual(len(row["source_uids"]), 2)
            self.assertEqual(len(row["source_questions"]), 2)
            self.assertEqual(len(row["source_answers"]), 2)
            self.assertIn("composition_schema", row)
            self.assertIn("+", row["composition_schema"])
            self.assertFalse(row["video_verified"])
            self.assertIn(row["review_status"], {"PENDING_VIDEO_REVIEW", "NEEDS_VERIFICATION"})
            questions.append(" ".join(row["new_question"].lower().split()))
        self.assertEqual(len(questions), len(set(questions)))

    def test_clean_ids_are_preserved_as_sources(self) -> None:
        clean_ids = {json.loads(line)["id"] for line in CLEAN.read_text(encoding="utf-8").splitlines() if line.strip()}
        from_clean = {row["source_v1_id"] for row in self.candidates if row.get("origin") == "v1_clean"}
        self.assertEqual(from_clean, clean_ids)

    def test_statistics_match_candidates(self) -> None:
        total = sum(int(row["n_questions"]) for row in self.stats)
        self.assertEqual(total, len(self.candidates))
        self.assertTrue((V2 / "REPORT.md").is_file())
        self.assertTrue((V2 / "README.md").is_file())
        self.assertIn("INSUFFICIENT_COMPOSITION_COVERAGE", self.feasibility)

    def test_split_has_no_source_leak_if_present(self) -> None:
        path = V2 / "seen_unseen_split.json"
        if not path.is_file():
            self.assertIn("INSUFFICIENT_COMPOSITION_COVERAGE", self.feasibility)
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
        by_id = {row["id"]: row for row in self.candidates}
        train = [by_id[i] for i in payload["train_ids"]]
        test = [by_id[i] for i in payload["test_ids"]]
        train_videos = {row["video_id"] for row in train}
        test_videos = {row["video_id"] for row in test}
        self.assertFalse(train_videos & test_videos)
        train_uids = {(row["video_id"], uid) for row in train for uid in row["source_uids"]}
        test_uids = {(row["video_id"], uid) for row in test for uid in row["source_uids"]}
        self.assertFalse(train_uids & test_uids)
        self.assertEqual(payload["status"], "EXPERIMENTAL_ONLY")

    def test_prior_audit_files_unchanged(self) -> None:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--exit-code",
                "--",
                str(V0),
                str(V1),
                "research_audit/lvbench_compositional/qa_v1_clean",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
