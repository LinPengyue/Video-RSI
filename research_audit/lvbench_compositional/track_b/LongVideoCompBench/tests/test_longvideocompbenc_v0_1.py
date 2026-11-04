#!/usr/bin/env python3
"""WP2 LongVideoCompBench gates + negative rejection tests."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from _common import (  # noqa: E402
    FROZEN_5_2,
    PROPOSED_7_4_SEEN,
    PROPOSED_7_4_UNSEEN,
    SEED_11,
    WP1,
    read_jsonl,
)
from bootstrap_dataset import bootstrap  # noqa: E402
from import_annotation_batch import import_batch  # noqa: E402
from validate_dataset import gate_b_refs, gate_d_split_leakage, load_data, run_gates  # noqa: E402


class TestLongVideoCompBench(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wp1 = json.loads((WP1 / "VALIDATION_REPORT.json").read_text())
        assert wp1.get("status") == "PASS", "WP1 must PASS before data bootstrap"
        cls.bootstrap = bootstrap()
        # stats + validate via run_gates
        cls.report = run_gates()
        # write validation report like CLI
        (ROOT / "reports").mkdir(exist_ok=True)
        (ROOT / "reports" / "validation_report.json").write_text(
            json.dumps(cls.report, indent=2) + "\n"
        )

    def test_gates_pass(self):
        self.assertEqual(self.report["overall"], "PASS")
        for g in self.report["gates"].values():
            self.assertEqual(g["status"], "PASS", g)

    def test_eleven_graphs_nine_or_more_complete_policy(self):
        graphs = read_jsonl(ROOT / "data" / "program_graphs.jsonl")
        qas = read_jsonl(ROOT / "data" / "qa_items.jsonl")
        self.assertEqual(len(graphs), 11)
        self.assertEqual(len(qas), 11)
        ids = {g["source_item_id"] for g in graphs}
        self.assertEqual(ids, set(SEED_11))
        complete = [q for q in qas if q["record_completeness"] == "COMPLETE"]
        graph_only = [q for q in qas if q["record_completeness"] == "GRAPH_ONLY"]
        self.assertGreaterEqual(len(complete), 9)
        self.assertEqual({q["source_item_id"] for q in graph_only}, {"A", "B"})
        self.assertEqual(self.bootstrap["status"], "PARTIAL")

    def test_video_dedup_not_eleven(self):
        videos = read_jsonl(ROOT / "data" / "videos.jsonl")
        self.assertLess(len(videos), 11)
        self.assertGreaterEqual(len(videos), 6)  # WP1 videos + F1/F2

    def test_frozen_and_proposed_splits(self):
        splits = json.loads((ROOT / "data" / "splits.json").read_text())
        self.assertTrue(splits["frozen_5_2"]["immutable"])
        self.assertEqual(splits["frozen_5_2"]["seen"] + splits["frozen_5_2"]["unseen"], FROZEN_5_2)
        self.assertEqual(splits["proposed_7_4_dev"]["status"], "PROPOSED")
        self.assertEqual(splits["proposed_7_4_dev"]["seen"], PROPOSED_7_4_SEEN)
        self.assertEqual(splits["proposed_7_4_dev"]["unseen"], PROPOSED_7_4_UNSEEN)

    def test_wp1_untouched(self):
        qa = json.loads((WP1 / "qa_items.json").read_text())
        self.assertEqual([x["item_id"] for x in qa["items"]], FROZEN_5_2)

    def test_no_frame_cert_auto_upgrade(self):
        for e in read_jsonl(ROOT / "data" / "evidence.jsonl"):
            if e["certification_status"] == "SOURCE_WINDOW_ONLY":
                self.assertNotEqual(e["certification_status"], "FRAME_CERTIFIED")

    def test_negative_dangling_ref(self):
        data = load_data()
        data["qas"] = deepcopy(data["qas"])
        data["qas"][0]["video_id"] = "DOES_NOT_EXIST_VIDEO"
        issues = gate_b_refs(data)
        self.assertTrue(any(i["code"] == "QA_VIDEO_DANGLING" for i in issues))

    def test_negative_duplicate_rejected_on_reimport(self):
        # re-import existing SP001 must fail
        batch = {
            "batch_id": "neg_dup",
            "items": [
                {
                    "source_item_id": "SP001",
                    "question": "x",
                    "answer": "y",
                    "formal_gold": False,
                    "split_assignment": "PENDING",
                    "program_graph": {
                        "nodes": [
                            {"node_id": "n1", "raw_operator": "X", "raw_inputs": [], "raw_outputs": []}
                        ],
                        "edges": [],
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "batch.json"
            p.write_text(json.dumps(batch))
            result = import_batch(p, apply=False)
            self.assertEqual(result["status"], "REJECTED")
            self.assertTrue(any(e["code"] == "DUPLICATE_IMPORT" for e in result["errors"]))

    def test_negative_unapproved_gold(self):
        batch = {
            "batch_id": "neg_gold",
            "items": [
                {
                    "source_item_id": "NEG_GOLD_001",
                    "question": "q",
                    "answer": "a",
                    "formal_gold": True,
                    "split_assignment": "PENDING",
                    "video_id": None,
                    "program_graph": {
                        "nodes": [
                            {"node_id": "n1", "raw_operator": "X", "raw_inputs": [], "raw_outputs": []}
                        ],
                        "edges": [],
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "batch.json"
            p.write_text(json.dumps(batch))
            result = import_batch(p, apply=False)
            self.assertEqual(result["status"], "REJECTED")
            self.assertTrue(any(e["code"] == "UNAPPROVED_GOLD" for e in result["errors"]))

    def test_negative_illegal_split_promotion(self):
        batch = {
            "batch_id": "neg_split",
            "items": [
                {
                    "source_item_id": "NEG_SPLIT_001",
                    "question": "q",
                    "answer": "a",
                    "formal_gold": False,
                    "split_assignment": "SEEN",
                    "program_graph": {
                        "nodes": [
                            {"node_id": "n1", "raw_operator": "X", "raw_inputs": [], "raw_outputs": []}
                        ],
                        "edges": [],
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "batch.json"
            p.write_text(json.dumps(batch))
            result = import_batch(p, apply=False)
            self.assertEqual(result["status"], "REJECTED")
            self.assertTrue(
                any(e["code"] == "ILLEGAL_SPLIT_PROMOTION" for e in result["errors"])
            )

    def test_negative_forged_hash(self):
        batch = {
            "batch_id": "neg_hash",
            "items": [
                {
                    "source_item_id": "NEG_HASH_001",
                    "question": "q",
                    "answer": None,
                    "formal_gold": False,
                    "split_assignment": "PENDING",
                    "video_id": "neg_hash_vid",
                    "video_record": {
                        "video_id": "neg_hash_vid",
                        "source_dataset": "X",
                        "source_video_id": "neg_hash_vid",
                        "source_uri": None,
                        "duration_seconds": None,
                        "media_sha256": "0" * 64,
                        "forged_hash": True,
                        "access_status": "PATH_UNKNOWN",
                        "license_status": "UNKNOWN_NOT_DECLARED_OPEN",
                        "pool": "DEV",
                        "provenance": {},
                    },
                    "program_graph": {
                        "nodes": [
                            {"node_id": "n1", "raw_operator": "X", "raw_inputs": [], "raw_outputs": []}
                        ],
                        "edges": [],
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "batch.json"
            p.write_text(json.dumps(batch))
            result = import_batch(p, apply=False)
            self.assertEqual(result["status"], "REJECTED")
            self.assertTrue(any(e["code"] == "FORGED_VIDEO_HASH" for e in result["errors"]))

    def test_negative_split_promotion_in_splits_json(self):
        data = load_data()
        data["splits"] = deepcopy(data["splits"])
        data["splits"]["proposed_7_4_dev"]["status"] = "HUMAN_APPROVED_FROZEN"
        data["splits"]["proposed_7_4_dev"]["approval_record"] = None
        issues = gate_d_split_leakage(data)
        self.assertTrue(
            any(
                i["code"] in ("ILLEGAL_SPLIT_PROMOTION", "ILLEGAL_SPLIT_PROMOTION_NO_APPROVAL")
                for i in issues
            )
        )

    def test_example_batch_dry_run_accepts_structure(self):
        example = ROOT / "staging" / "example_batch.json"
        result = import_batch(example, apply=False)
        self.assertEqual(result["status"], "VALIDATED_READY")
        self.assertFalse(result["applied"])


if __name__ == "__main__":
    unittest.main()
