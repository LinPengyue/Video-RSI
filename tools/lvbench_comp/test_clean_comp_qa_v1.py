#!/usr/bin/env python3
"""Checks for the v1.1 candidate cleanup and its local video evidence."""

from __future__ import annotations

import csv
import json
import subprocess
import unittest
from pathlib import Path

from extract_evidence import parse_time_reference


ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "research_audit/lvbench_compositional/qa_v1/candidates.jsonl"
CLEAN = ROOT / "research_audit/lvbench_compositional/qa_v1_clean"
INDEX = CLEAN / "video_evidence_index.json"
MEDIA = CLEAN / "local_media"
METADATA = Path("/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl")


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _official() -> dict[tuple[str, str], dict]:
    found = {}
    with METADATA.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            for qa in record["qa"]:
                found[(record["key"], str(qa["uid"]))] = qa
    return found


class CleanCandidateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.original = _rows(V1)
        cls.clean = _rows(CLEAN / "candidates.jsonl")
        cls.decisions = _csv(CLEAN / "review_decisions.csv")
        cls.excluded = _csv(CLEAN / "excluded.csv")
        cls.original_by_id = {row["id"]: row for row in cls.original}
        cls.official = _official()

    def test_every_original_has_one_decision(self) -> None:
        ids = [row["id"] for row in self.decisions]
        self.assertEqual(ids, [row["id"] for row in self.original])
        self.assertEqual(len(set(ids)), 45)
        self.assertTrue(all(row["decision"] in {"KEEP", "REVISE", "DROP"} for row in self.decisions))

    def test_drop_and_hold_are_outside_the_clean_set(self) -> None:
        clean_ids = {row["id"] for row in self.clean}
        for row in self.decisions:
            if row["decision"] == "DROP" or row["review_status"] == "HOLD_LABEL_BALANCE":
                self.assertNotIn(row["id"], clean_ids)
                self.assertEqual(row["included_in_clean_set"], "no")
        excluded = {row["id"] for row in self.excluded}
        self.assertEqual(excluded, {"LVCOMP-V1-018", "LVCOMP-V1-039", "LVCOMP-V1-044"})

    def test_source_uids_and_answers_stay_traceable(self) -> None:
        for row in self.clean:
            source = self.original_by_id[row["id"]]
            self.assertEqual(row["source_uids"], source["source_uids"])
            self.assertEqual(row["source_questions"], source["source_questions"])
            self.assertEqual(row["source_answers"], source["source_answers"])
            self.assertEqual(row["time_references"], source["time_references"])
            self.assertFalse(row["video_verified"])
            self.assertIn(row["review_status"], {"PENDING_VIDEO_REVIEW", "NEEDS_VERIFICATION"})
            for uid, question in zip(row["source_uids"], row["source_questions"]):
                official = self.official[(row["video_id"], uid)]
                self.assertEqual(official["question"], question)
            if row["new_answer"] != source["new_answer"]:
                self.assertIn(row["new_answer"].lower(), " ".join(row["source_answers"]).lower())

    def test_questions_are_unique(self) -> None:
        normalized = [" ".join(row["new_question"].lower().split()) for row in self.clean]
        self.assertEqual(len(normalized), len(set(normalized)))

    def test_prior_files_are_unchanged(self) -> None:
        paths = [
            "research_audit/lvbench_compositional/qa_v0",
            "research_audit/lvbench_compositional/qa_v1",
        ]
        result = subprocess.run(
            ["git", "diff", "--exit-code", "--", *paths],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_media_is_ignored_and_times_match_annotations(self) -> None:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", str(MEDIA / "placeholder.mp4")],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(ignored.returncode, 0)
        index = json.loads(INDEX.read_text(encoding="utf-8"))
        self.assertEqual(len(index["items"]), 10)
        self.assertEqual(index["video_count"], 10)
        self.assertFalse(index["video_verified"] if "video_verified" in index else False)
        for item in index["items"]:
            self.assertFalse(item["video_verified"])
            for uid_row in item["uids"]:
                official = self.official[(item["video_id"], uid_row["uid"])]
                self.assertEqual(uid_row["time_reference"], official["time_reference"])
                start, end = parse_time_reference(official["time_reference"])
                self.assertEqual(uid_row["official_start_seconds"], start)
                self.assertEqual(uid_row["official_end_seconds"], end)
                self.assertEqual(set(uid_row["windows"]), {"strict", "context"})
                for mode, window in uid_row["windows"].items():
                    self.assertGreaterEqual(window["frame_count"], 8)
                    self.assertLessEqual(window["frame_count"], 10)
                    self.assertTrue((MEDIA / window["clip_path"]).is_file())
                    self.assertTrue((MEDIA / window["contact_sheet"]).is_file())
                    if mode == "strict" and end > start:
                        self.assertAlmostEqual(window["start_seconds"], start, places=2)
                        self.assertAlmostEqual(window["end_seconds"], end, places=2)
                    if mode == "context":
                        self.assertLessEqual(window["start_seconds"], start)
                        self.assertGreaterEqual(window["end_seconds"], end)


if __name__ == "__main__":
    unittest.main()
