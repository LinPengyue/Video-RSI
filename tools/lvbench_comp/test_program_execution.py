"""Tests for DAG execution-over-selection (not label-only)."""

from __future__ import annotations

import unittest

from tools.lvbench_comp.typed_evidence_contract.program_execution import (
    execute_selected,
    run_execution_suite,
)
from tools.lvbench_comp.typed_evidence_contract.program_selection import (
    build_program_selection_split,
)


class TestProgramExecution(unittest.TestCase):
    def test_execute_produces_trace(self) -> None:
        split = build_program_selection_split()
        leave = split.pop("_leave_out")
        split.pop("_train_schema_ids")
        split.pop("_held_schema_ids")
        self.assertTrue(leave["ok"])
        t = split["test"][0]
        r = execute_selected(t, selected_schema_id=t.gold_schema_id)
        self.assertIn("trace", r)
        self.assertGreaterEqual(len(r["trace"]), 1)
        self.assertFalse(r["ok_for_expensive_rsi"])
        self.assertEqual(r["selected_schema_id"], t.gold_schema_id)

    def test_suite_distinguishes_choice_vs_execution(self) -> None:
        out = run_execution_suite(seed=42)
        self.assertFalse(out["ok_for_expensive_rsi"])
        self.assertIn("program_choice_accuracy", out["selected_policy_summary"])
        self.assertIn("execution_answer_accuracy", out["selected_policy_summary"])
        self.assertEqual(out["n_test_questions"], 6)
        self.assertIn("strong_static_selector", out["budget_matched_arms"])


if __name__ == "__main__":
    unittest.main()
