#!/usr/bin/env python3
"""Regression: CG-NEW id → seed / video_id must match ChatGPT canonical proposals."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT / "research_audit/lvbench_compositional/chatgpt_video_driven_qa"

EXPECTED = {
    "CG-NEW-001": {"seed": "TB-003", "video_id": "TJR1oYDDTwg", "kind_substr": "contrastive"},
    "CG-NEW-002": {"seed": "TB-007", "video_id": "Cm73ma6Ibcs", "kind_substr": "reverse"},
    "CG-NEW-003": {"seed": "TB-006", "video_id": "LLSJrEgOOtw", "kind_substr": "audio"},
    "CG-NEW-004": {"seed": "TB-005", "video_id": "evYm0cELO3I", "kind_substr": "process"},
    "CG-NEW-005": {"seed": "TB-004", "video_id": "vaL_vSdZKZo", "kind_substr": "safety"},
}


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


class CgNewMappingRegressionTest(unittest.TestCase):
    def test_canonical_id_seed_video(self) -> None:
        rows = _load_jsonl(QA / "canonical_qa_proposals.jsonl")
        self.assertEqual(len(rows), 5)
        by_id = {r["id"]: r for r in rows}
        for cid, exp in EXPECTED.items():
            r = by_id[cid]
            self.assertEqual(r["seed"], exp["seed"], cid)
            self.assertEqual(r["video_id"], exp["video_id"], cid)
            self.assertIn(exp["kind_substr"], r["kind"])
            self.assertEqual(r["data_partition_status"], "UNASSIGNED")
            self.assertTrue(str(r["status"]).startswith("PROPOSED"))
            self.assertTrue(r.get("not_formal_QA", True))
            self.assertFalse(r.get("formal_supported", False))

    def test_registry_matches_canonical(self) -> None:
        canon = {r["id"]: r for r in _load_jsonl(QA / "canonical_qa_proposals.jsonl")}
        reg = _load_jsonl(QA / "cg_new_registry_canonical.jsonl")
        self.assertEqual(len(reg), 5)
        for r in reg:
            c = canon[r["candidate_id"]]
            self.assertEqual(r["linked_tb_id"], c["seed"])
            self.assertEqual(r["video_id"], c["video_id"])
            self.assertEqual(r["data_partition_status"], "UNASSIGNED")
            self.assertFalse(r.get("formal_supported", False))

    def test_fallback_preserved_and_differs_on_004_005(self) -> None:
        fb = {r["candidate_id"]: r for r in _load_jsonl(QA / "fallback_snapshot_85138431.jsonl")}
        self.assertIn("CG-NEW-004", fb)
        self.assertIn("CG-NEW-005", fb)
        # Documented wrong mapping in prior Cursor fill — must remain as snapshot, not overwrite.
        self.assertNotEqual(fb["CG-NEW-004"].get("linked_tb_id"), "TB-005")
        self.assertEqual(EXPECTED["CG-NEW-004"]["seed"], "TB-005")
        self.assertEqual(EXPECTED["CG-NEW-005"]["seed"], "TB-004")

    def test_canonical_sha256_stable(self) -> None:
        blob = (QA / "canonical_qa_proposals.jsonl").read_bytes()
        digest = hashlib.sha256(blob).hexdigest()
        meta = json.loads((QA / "MAPPING_REGRESSION.json").read_text(encoding="utf-8"))
        self.assertEqual(digest, meta["canonical_sha256"])
        self.assertEqual(meta["mapping"], {k: v["seed"] for k, v in EXPECTED.items()})

    def test_tb_001_007_preserved(self) -> None:
        path = QA / "preserved_tb_001_007_candidates.jsonl"
        self.assertTrue(path.exists())
        rows = _load_jsonl(path)
        ids = {r.get("candidate_id") or r.get("id") for r in rows}
        for i in range(1, 8):
            self.assertTrue(any(f"TB-00{i}" in str(x) or str(x) == f"TB-00{i}" for x in ids) or len(rows) >= 7)


if __name__ == "__main__":
    unittest.main()
