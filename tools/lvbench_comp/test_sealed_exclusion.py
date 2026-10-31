"""Regression: run_001/002 exposed inventory IDs ⊆ sealed exclusion register."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.lvbench_comp.batch_factory.sealed_exclusion import (
    POLICY_PATH,
    assert_run_inventories_subset_of_exclusion,
    collect_run_inventory_video_ids,
    load_sealed_exclusion_ids,
)


AUDIT_MISSING = {"S8vPx-u9p_A", "iA_69g87Ilw", "hROKtPqktO8"}


class TestSealedExclusion(unittest.TestCase):
    def test_all_run001_run002_exposed_IDs_subset_of_sealed_exclusion(self) -> None:
        assert_run_inventories_subset_of_exclusion()
        run_ids = collect_run_inventory_video_ids("run_001", "run_002", "run_002_patch_regen")
        self.assertTrue(AUDIT_MISSING.issubset(run_ids) or AUDIT_MISSING.issubset(load_sealed_exclusion_ids()))
        exposed = load_sealed_exclusion_ids()
        self.assertTrue(AUDIT_MISSING.issubset(exposed))

    def test_sealed_reservoir_untouched_placeholder(self) -> None:
        data = json.loads(POLICY_PATH.read_text())
        self.assertEqual(data["sealed_reservoir"].get("current_ids"), [])
        self.assertFalse(data.get("ok_for_expensive_rsi", True))

    def test_construction_pool_subset_of_exclusion(self) -> None:
        pool = Path(
            "research_audit/lvbench_compositional/track_b/construction_video_pool.jsonl"
        )
        exposed = load_sealed_exclusion_ids()
        missing = []
        for line in pool.read_text().splitlines():
            if not line.strip():
                continue
            vid = json.loads(line)["construction_video_id"]
            if vid not in exposed:
                missing.append(vid)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
