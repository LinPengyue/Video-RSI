"""Tests for DAG execution-over-selection and scoring integrity."""

from __future__ import annotations

import inspect
import unittest

from tools.lvbench_comp.typed_evidence_contract.program_execution import (
    execute_selected,
    run_execution_suite,
    schema_to_program,
)
from tools.lvbench_comp.typed_evidence_contract.program_selection import (
    SCHEMA_A_BIND_B,
    SCHEMA_COMPARE_TWO_STATES,
    SCHEMA_MISSING_ABSTAIN,
    ProgTask,
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

    def test_wrong_schema_abstain_not_credited(self) -> None:
        """Selecting abstain DAG on a non-abstain gold must not get answer credit."""
        t = ProgTask(
            task_id="trap_forward",
            question="What does teal scarf do later?",
            gold_schema_id=SCHEMA_A_BIND_B.schema_id,
            split="test",
            referring="teal_scarf",
            property_name="action",
            answer="places_marker",
            seed=1,
        )
        r = execute_selected(t, selected_schema_id=SCHEMA_MISSING_ABSTAIN.schema_id)
        self.assertEqual(r["selected_schema_id"], SCHEMA_MISSING_ABSTAIN.schema_id)
        self.assertNotEqual(r["gold_schema_id"], SCHEMA_MISSING_ABSTAIN.schema_id)
        # Even if DAG abstains due to missing evidence, gold is not ABSTAIN
        self.assertFalse(r["execution_answer_ok"])
        if r.get("explicit_abstain"):
            self.assertIn("wrong_schema_abstain_not_credited", r.get("scorer_notes") or [])

    def test_compare_evidence_path_valid_alone_not_enough(self) -> None:
        """evidence_path_valid must not credit a wrong semantic answer."""
        t = ProgTask(
            task_id="compare_wrong",
            question="Compare both state transitions: order the two board changes.",
            gold_schema_id=SCHEMA_COMPARE_TWO_STATES.schema_id,
            split="test",
            referring="board_early",
            property_name="order",
            answer="0-1_then_1-1",
            seed=2,
        )
        r = execute_selected(t, selected_schema_id=SCHEMA_COMPARE_TWO_STATES.schema_id)
        # Force-check scoring helper path: if pred mismatches gold, not ok
        if r.get("pred") and str(r["pred"]) != str(t.answer):
            self.assertFalse(r["execution_answer_ok"])
        # Substring trap: "1" is substring of gold but must not auto-pass
        from tools.lvbench_comp.typed_evidence_contract import program_execution as pe

        src = inspect.getsource(pe.execute_selected)
        self.assertNotIn('str(gold) in str(pred_out)', src)
        self.assertNotIn('or r.outputs.get("evidence_path_valid")', src)

    def test_oracle_boundary_no_world_facts_in_scorer(self) -> None:
        src = inspect.getsource(execute_selected)
        # Mask setup may touch world.facts; scoring must not scrape it for credit
        scoring = src.split("Answer check", 1)[-1]
        self.assertNotIn("for f in world.facts", scoring)
        self.assertNotIn("[f.property_value for f in world", scoring)
        self.assertNotIn("world.facts if", scoring)
        r = execute_selected(
            ProgTask(
                task_id="bound",
                question="What does teal scarf do later?",
                gold_schema_id=SCHEMA_A_BIND_B.schema_id,
                split="test",
                answer="places_marker",
                seed=3,
            ),
            selected_schema_id=SCHEMA_A_BIND_B.schema_id,
        )
        self.assertFalse(r["oracle_world_scraped"])
        self.assertTrue(r["scorer_sees_gold"])
        self.assertFalse(r["executor_saw_gold_answer"])
        # schema_to_program must not inject gold into executor ops except verify inputs
        prog = schema_to_program(
            __import__(
                "tools.lvbench_comp.typed_evidence_contract.program_selection", fromlist=["DAG_LIBRARY"]
            ).DAG_LIBRARY[SCHEMA_A_BIND_B.schema_id],
            ProgTask(
                task_id="x",
                question="q",
                gold_schema_id=SCHEMA_A_BIND_B.schema_id,
                split="t",
                answer="SECRET_GOLD_SHOULD_NOT_LEAK_TO_QUERY",
                seed=0,
            ),
        )
        for step in prog:
            if step["op"] != "verify_answer":
                self.assertNotIn("SECRET_GOLD_SHOULD_NOT_LEAK_TO_QUERY", str(step.get("inputs")))


if __name__ == "__main__":
    unittest.main()
