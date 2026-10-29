#!/usr/bin/env python3
"""Checks for the v2.1 strict Novel Composition Pilot."""

from __future__ import annotations

import csv
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "research_audit/lvbench_compositional/v2"
V21 = ROOT / "research_audit/lvbench_compositional/v2_1"
UNSEEN = "identify_person + query_action"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class BuildCompQAV21Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.candidates = _rows(V2 / "candidates.jsonl")
        cls.by_id = {row["id"]: row for row in cls.candidates}
        with (V21 / "schema_audit.csv").open(encoding="utf-8", newline="") as handle:
            cls.audit = list(csv.DictReader(handle))
        with (V21 / "primitive_coverage.csv").open(encoding="utf-8", newline="") as handle:
            cls.prim = list(csv.DictReader(handle))
        cls.validation = json.loads((V21 / "split_validation.json").read_text(encoding="utf-8"))
        cls.report = (V21 / "REPORT.md").read_text(encoding="utf-8")
        cls.pilot_path = V21 / "pilot_split.json"
        cls.pilot = json.loads(cls.pilot_path.read_text(encoding="utf-8")) if cls.pilot_path.is_file() else None

    def test_schema_audit_marks_animal_mismatches(self) -> None:
        by = {row["id"]: row for row in self.audit}
        self.assertEqual(by["LVCOMP-V2-106"]["schema_verdict"], "SCHEMA_MISMATCH")
        self.assertEqual(by["LVCOMP-V2-113"]["schema_verdict"], "SCHEMA_MISMATCH")
        self.assertEqual(by["LVCOMP-V2-114"]["schema_verdict"], "SCHEMA_MISMATCH")
        self.assertEqual(by["LVCOMP-V2-106"]["entity_kind"], "animal")
        valid = [row for row in self.audit if row["schema_verdict"] == "SCHEMA_VALID"]
        self.assertEqual(len(valid), 6)
        self.assertTrue(all(row["entity_kind"] in {"person", "anthropomorphic_character"} for row in valid))

    def test_unseen_schema_absent_from_train(self) -> None:
        self.assertIsNotNone(self.pilot)
        assert self.pilot is not None
        self.assertEqual(self.validation["unseen_schema_in_train_count"], 0)
        for cid in self.pilot["train_ids"]:
            self.assertNotEqual(self.by_id[cid]["composition_schema"], UNSEEN)

    def test_video_and_uid_isolation(self) -> None:
        assert self.pilot is not None
        train = [self.by_id[cid] for cid in self.pilot["train_ids"]]
        test = [self.by_id[cid] for cid in self.pilot["test_ids"]]
        self.assertFalse({row["video_id"] for row in train} & {row["video_id"] for row in test})
        train_uids = {(row["video_id"], uid) for row in train for uid in row["source_uids"]}
        test_uids = {(row["video_id"], uid) for row in test for uid in row["source_uids"]}
        self.assertFalse(train_uids & test_uids)
        self.assertEqual(self.validation["train_test_video_overlap"], [])
        self.assertEqual(self.validation["train_test_uid_overlap"], [])

    def test_contradicted_excluded(self) -> None:
        assert self.pilot is not None
        all_ids = set(self.pilot["train_ids"]) | set(self.pilot["test_ids"])
        self.assertNotIn("LVCOMP-V2-038", all_ids)
        self.assertTrue(self.validation["v2_038_excluded"])
        self.assertEqual(self.validation["contradicted_in_train"], [])
        self.assertEqual(self.validation["contradicted_in_test"], [])

    def test_primitive_coverage_rows_exist(self) -> None:
        prims = {row["primitive"]: row for row in self.prim}
        self.assertIn("identify_person", prims)
        self.assertIn("query_action", prims)
        self.assertGreaterEqual(int(prims["identify_person"]["strict_n"]), 1)
        self.assertGreaterEqual(int(prims["query_action"]["strict_n"]), 1)
        self.assertTrue(prims["identify_person"]["strict_schemas"])
        self.assertTrue(prims["query_action"]["strict_schemas"])
        self.assertNotIn(UNSEEN, prims["identify_person"]["strict_schemas"])
        self.assertNotIn(UNSEEN, prims["query_action"]["strict_schemas"])

    def test_counts_match_files(self) -> None:
        assert self.pilot is not None
        self.assertEqual(len(self.pilot["test_ids"]), self.pilot["structural_counts"]["test_n"])
        self.assertEqual(len(self.pilot["train_ids"]), self.pilot["structural_counts"]["train_n"])
        self.assertEqual(len(self.pilot["test_videos"]), self.pilot["structural_counts"]["test_videos"])
        self.assertEqual(len(self.audit), 9)
        self.assertIn("STRUCTURAL_PILOT_FEASIBLE_BUT_UNVERIFIED", self.report)
        self.assertEqual(self.pilot["status"], "PILOT_ONLY_NOT_VIDEO_CERTIFIED")
        self.assertTrue(self.validation["ok"])

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
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
