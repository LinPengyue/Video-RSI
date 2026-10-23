"""Offline score.py alignment test against local gitignored labels (no API)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from run_batch import load_items
from score import score
from solver_full_workspace.engine.common import read_jsonl

ITEMS = Path("research_audit/mlvu_test_prep/mlvu_test_mc_items.jsonl")
LABELS = Path("research_audit/mlvu_test_prep/labels.local.jsonl")
SMOKE_IDS = Path("research_audit/mlvu_test_prep/sample_ids_n10.json")


class ScoreLabelsOffline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not LABELS.is_file():
            raise unittest.SkipTest("labels.local.jsonl missing; run validate_and_build_labels.py first")

    def test_labels_cover_all_502_and_are_AF(self):
        items = load_items(ITEMS, check_media=False)
        labels = read_jsonl(LABELS)
        self.assertEqual(len(items), 502)
        self.assertEqual(len(labels), 502)
        item_ids = [r["sample_id"] for r in items]
        label_ids = [r["sample_id"] for r in labels]
        self.assertEqual(sorted(item_ids), sorted(label_ids))
        self.assertTrue(all(r["answer"] in "ABCDEF" for r in labels))

    def test_perfect_predictions_score_100(self):
        items = load_items(ITEMS, check_media=False)
        labels = {r["sample_id"]: r for r in read_jsonl(LABELS)}
        preds = []
        for row in items:
            sid = row["sample_id"]
            preds.append(
                {
                    "sample_id": sid,
                    "status": "answered",
                    "answer": labels[sid]["answer"],
                    "usage": {"qwen_frames": 1},
                }
            )
        # score() expects predictions as list-like indexed by sample_id via indexed()
        out = score(items, preds, list(labels.values()))
        self.assertEqual(out["status"], "complete")
        self.assertEqual(out["micro_accuracy_percent"], 100.0)
        self.assertEqual(out["observed_correct"], 502)

    def test_smoke_subset_alignment_and_mismatch_detection(self):
        smoke = json.loads(SMOKE_IDS.read_text())["sample_ids"]
        items_all = load_items(ITEMS, check_media=False)
        by_id = {r["sample_id"]: r for r in items_all}
        labels_all = {r["sample_id"]: r for r in read_jsonl(LABELS)}
        items = [by_id[s] for s in smoke]
        labels = [labels_all[s] for s in smoke]
        # Correct on all but flip first answer
        preds = []
        for i, row in enumerate(items):
            gold = labels_all[row["sample_id"]]["answer"]
            wrong = next(x for x in "ABCDEF" if x != gold)
            preds.append(
                {
                    "sample_id": row["sample_id"],
                    "status": "answered",
                    "answer": wrong if i == 0 else gold,
                    "usage": {"qwen_frames": 2},
                }
            )
        out = score(items, preds, labels)
        self.assertEqual(out["n"], 10)
        self.assertEqual(out["observed_correct"], 9)
        self.assertAlmostEqual(out["micro_accuracy_percent"], 90.0)


if __name__ == "__main__":
    unittest.main()
