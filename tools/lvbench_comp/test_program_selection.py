#!/usr/bin/env python3
"""Program selection among distinct DAGs; frozen binding suite untouched."""

from __future__ import annotations

import unittest

from tools.lvbench_comp.typed_evidence_contract.program_selection import (
    DAG_LIBRARY,
    SCHEMA_COMPARE_TWO_STATES,
    SCHEMA_MISSING_ABSTAIN,
    build_program_selection_split,
    freeze_binding_negative_control_pointer,
    run_program_selection_ablation,
    select_program,
)
from tools.lvbench_comp.typed_evidence_contract.program_schema import assert_structural_leave_out


class ProgramSelectionTest(unittest.TestCase):
    def test_dag_hashes_distinct(self) -> None:
        hs = [s.graph_hash() for s in DAG_LIBRARY.values()]
        self.assertEqual(len(hs), len(set(hs)))

    def test_structural_leave_out(self) -> None:
        split = build_program_selection_split()
        self.assertTrue(split["_leave_out"]["ok"])
        self.assertIn(SCHEMA_COMPARE_TWO_STATES.schema_id, split["_held_schema_ids"])
        self.assertIn(SCHEMA_MISSING_ABSTAIN.schema_id, split["_held_schema_ids"])

    def test_selector_no_oracle_graph(self) -> None:
        r = select_program("Later previous-results athlete earlier removed which color jacket?")
        self.assertFalse(r["used_oracle_graph"])
        self.assertIn(r["selected_schema_id"], DAG_LIBRARY)

    def test_ablation_accepts_no_evolver_win(self) -> None:
        out = run_program_selection_ablation(n_seeds=2, base_seed=60)
        self.assertFalse(out["ok_for_expensive_rsi"])
        self.assertEqual(out["summary"]["oracle_program_upper"]["oracle_leak_rate"]["mean"], 1.0)
        # Evolver need not beat selector
        self.assertIn("selector", out["summary"])
        self.assertIn("evolver_weights", out["summary"])

    def test_frozen_binding_pointer(self) -> None:
        p = freeze_binding_negative_control_pointer()
        self.assertEqual(p["status"], "FROZEN_NEGATIVE_CONTROL_DO_NOT_TUNE")


if __name__ == "__main__":
    unittest.main()
