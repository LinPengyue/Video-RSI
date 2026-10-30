#!/usr/bin/env python3
"""Bind failure taxonomy & matched-budget parity tests (no TECE score chasing)."""

from __future__ import annotations

import unittest

from tools.lvbench_comp.typed_evidence_contract.bind_diagnostics import (
    collect_failure_taxonomy,
    instrument_bind_trace,
    matched_budget_ablation,
    run_independent_scenario_eval,
)
from tools.lvbench_comp.typed_evidence_contract.binding_loop import build_binding_split
from tools.lvbench_comp.typed_evidence_contract.executor import default_genome


class BindDiagnosticsTest(unittest.TestCase):
    def test_tece_like_init_rejects_correct_top1_on_dual(self) -> None:
        split = build_binding_split()
        dual = next(t for t in split["test"] if t.kind == "dual_necessary")
        g = {**default_genome(), "recovery_strategy": "none", "bind_score_threshold": 0.45, "search_budget": 4}
        tr = instrument_bind_trace(g, dual)
        self.assertTrue(tr["top1_is_gold"] or tr["failure_axis"] == "resolve_A_failed")
        if tr["top1_is_gold"]:
            self.assertEqual(tr["failure_axis"], "ranking_ok_but_threshold_reject")
            self.assertFalse(tr["bind_ok"])
            self.assertLess(tr["top1_score"], 0.45)

    def test_strong_rebind_accepts_dual(self) -> None:
        split = build_binding_split()
        dual = next(t for t in split["test"] if t.kind == "dual_necessary")
        g = {
            **default_genome(),
            "recovery_strategy": "rebind_from_a",
            "bind_score_threshold": 0.25,
            "search_budget": 6,
        }
        tr = instrument_bind_trace(g, dual)
        self.assertTrue(tr["bind_ok"])
        self.assertTrue(tr["pair_correct_at_bind"])
        self.assertTrue(tr["answer_ok"])

    def test_taxonomy_contains_threshold_reject_axis(self) -> None:
        tax = collect_failure_taxonomy()
        self.assertIn("ranking_ok_but_threshold_reject", tax["arm_failure_counts"]["tece_like_init"])
        self.assertEqual(tax["suite"], "frozen_4task_negative_control")

    def test_matched_parity_does_not_require_tece_win(self) -> None:
        out = matched_budget_ablation(n_seeds=2, base_seed=710)
        self.assertFalse(out["ok_for_expensive_rsi"])
        # Evolution need not beat matched static
        self.assertIn("matched_static", out["summary"])
        self.assertIn("matched_tece_evolve", out["summary"])
        self.assertIn("strong_fixed_rebind_ref", out["summary"])

    def test_independent_scenarios_not_frozen_answers(self) -> None:
        out = run_independent_scenario_eval(n=10, seed=901)
        frozen_answers = {"fetches_stick", "claps_sign", "nods_deep", "removes_jacket", "takes_bow", "points_chart"}
        rows = out["arms"]["strong_fixed_rebind"]["rows"]
        # At least some independent answers differ from frozen set
        inds = [r for r in rows if r["kind"] == "dual_necessary"]
        self.assertGreaterEqual(len(inds), 1)
        self.assertEqual(out["arms"]["weak_tece_like_init"]["missing_should_not_answer"], 1.0)


if __name__ == "__main__":
    unittest.main()
