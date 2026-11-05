#!/usr/bin/env python3
"""WP3.2 import integrity negatives + closure report checks."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
from import_annotation_batch import import_batch  # noqa: E402

REPORT = ROOT / "wp3_production" / "WP3_2_CLOSURE_AND_EXPANSION_REPORT.json"


def _write(batch: dict) -> Path:
    td = tempfile.mkdtemp()
    p = Path(td) / "batch.json"
    p.write_text(json.dumps(batch))
    return p


VALID_NODES = [
    {"node_id": "n1", "op": "LocatePerson", "raw_operator": "LocatePerson"},
    {"node_id": "n2", "op": "CrossIntervalSamePersonBind", "raw_operator": "CrossIntervalSamePersonBind"},
]
VALID_EDGES = [{"source": "n1", "target": "n2"}]


class TestWP32ImportAndClosure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text())

    def test_import_ready_cannot_bypass_unresolved(self):
        batch = {
            "batch_id": "neg_ready_bypass",
            "items": [
                {
                    "source_item_id": "FAKE_PAIR_BYPASS",
                    "import_ready": True,
                    "semantic_certification": "UNRESOLVED",
                    "relation_evidence_tier": "HYPOTHESIS_ONLY",
                    "question": "q",
                    "answer": "a",
                    "formal_gold": False,
                    "split_assignment": "PENDING",
                    "windows_seconds": [[1, 2], [10, 11]],
                    "program_graph": {"nodes": VALID_NODES, "edges": VALID_EDGES},
                    "graph_approval_status": "HUMAN_APPROVED",
                    "human_approved": True,
                    "evidence_pack": {
                        "A": {"source_frame_refs": ["a"], "source_hashes": {"a": "x"}},
                        "B": {"source_frame_refs": ["b"], "source_hashes": {"b": "y"}},
                    },
                }
            ],
        }
        result = import_batch(_write(batch), apply=False)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(
            any(e["code"] == "SEMANTICS_NOT_CERTIFIED_FOR_IMPORT" for e in result["errors"])
        )

    def test_forged_graph_approval_cannot_save_unknown_ops(self):
        batch = {
            "batch_id": "neg_forged_graph",
            "items": [
                {
                    "source_item_id": "NEG_FORGED_GRAPH",
                    "import_ready": True,
                    "question": "q",
                    "answer": "a",
                    "formal_gold": False,
                    "split_assignment": "PENDING",
                    "program_graph": {
                        "nodes": [
                            {"node_id": "n1", "op": "UNKNOWN_PENDING_SEMANTIC_REVIEW"}
                        ],
                        "edges": [],
                        "status": "DRAFT_PLACEHOLDER_NOT_EXECUTABLE",
                    },
                    "graph_approval_status": "HUMAN_APPROVED",
                }
            ],
        }
        result = import_batch(_write(batch), apply=False)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(
            any(e["code"] == "ILLEGAL_OR_MISSING_PROGRAM_GRAPH" for e in result["errors"])
        )

    def test_missing_b_window_rejected(self):
        batch = {
            "batch_id": "neg_missing_b",
            "items": [
                {
                    "source_item_id": "FAKE_PAIR_NOB",
                    "import_ready": True,
                    "semantic_certification": "HUMAN_APPROVED",
                    "independent_review": {
                        "reviewer_role": "HUMAN_SCIENTIFIC_OWNER",
                        "review_status": "HUMAN_APPROVED",
                        "scope": "VIDEO_BINDING",
                        "source_type": "DIRECT_USER_CONFIRMATION_IN_CHAT",
                    },
                    "question": "q",
                    "answer": "a",
                    "formal_gold": False,
                    "split_assignment": "PENDING",
                    "windows_seconds": [[1, 2]],
                    "program_graph": {"nodes": VALID_NODES, "edges": VALID_EDGES},
                    "evidence_pack": {
                        "A": {"source_frame_refs": ["a"], "source_hashes": {"a": "x"}},
                        "B": {"source_frame_refs": ["b"], "source_hashes": {"b": "y"}},
                    },
                }
            ],
        }
        result = import_batch(_write(batch), apply=False)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(any(e["code"] == "WP3_MISSING_B_WINDOW" for e in result["errors"]))

    def test_bad_graph_edge_rejected(self):
        batch = {
            "batch_id": "neg_bad_edge",
            "items": [
                {
                    "source_item_id": "NEG_BAD_EDGE",
                    "import_ready": True,
                    "question": "q",
                    "answer": "a",
                    "formal_gold": False,
                    "split_assignment": "PENDING",
                    "program_graph": {
                        "nodes": VALID_NODES,
                        "edges": [{"source": "n1", "target": "MISSING"}],
                    },
                }
            ],
        }
        result = import_batch(_write(batch), apply=False)
        self.assertEqual(result["status"], "REJECTED")
        self.assertTrue(
            any(
                e["code"] in {"ILLEGAL_OR_MISSING_PROGRAM_GRAPH", "GRAPH_EDGE_INCOMPLETE"}
                for e in result["errors"]
            )
        )

    def test_missing_reviewer_provenance_rejected(self):
        batch = {
            "batch_id": "neg_no_rev",
            "items": [
                {
                    "source_item_id": "FAKE_PAIR_NOREV",
                    "import_ready": True,
                    "semantic_certification": "HUMAN_APPROVED",
                    "human_approved": True,
                    "question": "q",
                    "answer": "a",
                    "formal_gold": False,
                    "split_assignment": "PENDING",
                    "windows_seconds": [[1, 2], [3, 4]],
                    "program_graph": {"nodes": VALID_NODES, "edges": VALID_EDGES},
                    "evidence_pack": {
                        "A": {"source_frame_refs": ["a"], "source_hashes": {"a": "x"}},
                        "B": {"source_frame_refs": ["b"], "source_hashes": {"b": "y"}},
                    },
                }
            ],
        }
        result = import_batch(_write(batch), apply=False)
        self.assertEqual(result["status"], "REJECTED")
        codes = {e["code"] for e in result["errors"]}
        self.assertTrue(
            codes
            & {
                "MISSING_REVIEWER_PROVENANCE",
                "SEMANTICS_NOT_CERTIFIED_FOR_IMPORT",
            }
        )

    def test_example_batch_still_validates(self):
        result = import_batch(ROOT / "staging" / "example_batch.json", apply=False)
        self.assertEqual(result["status"], "VALIDATED_READY")

    def test_closure_report(self):
        self.assertEqual(self.report["work_package"], "WP3.2")
        self.assertEqual(
            self.report["p1_USFV_PAIR2"]["human_adjudication_status"],
            "NOT_OBTAINED_THIS_ROUND",
        )
        self.assertFalse(self.report["p1_USFV_PAIR2"]["formal_gold"])
        self.assertIn("ihfjEFGdZdc_PAIR1", self.report["p2_pass_candidates"])
        self.assertIn("W-BnDvXXfOs_PAIR2", self.report["p2_pass_candidates"])
        self.assertEqual(
            self.report["p3_discovery"]["winner_for_effective_yield"], "entity_event_first"
        )
        self.assertTrue(self.report["frozen_5_2_unchanged"])
        self.assertEqual(self.report["proposed_7_4_status"], "PROPOSED")

    def test_releases_immutable(self):
        for ver in ("v0.1.0", "v0.1.1", "v0.1.2"):
            m = json.loads((ROOT / "releases" / ver / "manifest.json").read_text())
            for f in m["files"]:
                p = ROOT / "releases" / ver / f["path"]
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), f["sha256"])


if __name__ == "__main__":
    unittest.main()
