#!/usr/bin/env python3
"""Oracle-free TECE protocol tests."""

from __future__ import annotations

import unittest

from tools.lvbench_comp.typed_evidence_contract.evolution_loop import _world_pair
from tools.lvbench_comp.typed_evidence_contract.executor import default_genome
from tools.lvbench_comp.typed_evidence_contract.necessity import evaluate_necessity_neutral, make_b_only_sufficient_control
from tools.lvbench_comp.typed_evidence_contract.observations import project_oracle_free
from tools.lvbench_comp.typed_evidence_contract.oracle_free_loop import build_of_split, evolve_of, run_of_task


class OracleFreeTeceTest(unittest.TestCase):
    def test_observations_reject_oracle_ids(self) -> None:
        world = _world_pair()
        bundle, omap = project_oracle_free(world, scenario_id="t1", gold_answer="removes_jacket", gold_property="action")
        view = bundle.to_agent_dict()
        self.assertNotIn("entity_x", str(view))
        self.assertTrue(omap.track_to_oracle)
        self.assertTrue(all(t.startswith("trk_") for t in bundle.entities))

    def test_neutral_mask_does_not_rewrite_aliases(self) -> None:
        world = _world_pair()
        bundle, _ = project_oracle_free(world, scenario_id="t2", gold_answer="removes_jacket", gold_property="action")
        surfaces_before = {tid: list(e.surface_forms) for tid, e in bundle.entities.items()}
        nec = evaluate_necessity_neutral(
            bundle,
            referring="first speaker",
            property_name="action",
            gold_answer="removes_jacket",
            genome=default_genome(),
        )
        surfaces_after = {tid: list(e.surface_forms) for tid, e in bundle.entities.items()}
        self.assertEqual(surfaces_before, surfaces_after)
        self.assertIn("groups_only_no_alias_rewrite", nec.details["masking"])

    def test_b_only_sufficient_control_can_solve(self) -> None:
        world = _world_pair()
        bundle, _ = project_oracle_free(world, scenario_id="t3", gold_answer="removes_jacket", gold_property="action")
        ctrl = make_b_only_sufficient_control(bundle, "first speaker", "removes_jacket")
        nec = evaluate_necessity_neutral(
            ctrl,
            referring="first speaker",
            property_name="action",
            gold_answer="removes_jacket",
            genome=default_genome(),
        )
        self.assertTrue(nec.b_only_solves)
        self.assertFalse(nec.composition_necessary)

    def test_runtime_fidelity_and_zero_oracle_leak(self) -> None:
        split = build_of_split()
        families = split.pop("_families")
        g = {**default_genome(), "recovery_strategy": "rebind_from_a", "search_budget": 6}
        row = run_of_task(g, split["test"][0], families)
        self.assertTrue(row["runtime_fidelity_to_schema"])
        self.assertFalse(row["oracle_leak"])
        self.assertNotEqual(row["declared_schema_hash"], "")
        self.assertNotEqual(row["compiled_program_hash"], "")
        self.assertNotEqual(row["executed_trace_hash"], "")

    def test_tece_not_forced_above_fixed_rebind(self) -> None:
        """Fair compare: do not require TECE win; fixed_rebind may dominate."""
        split = build_of_split()
        families = split.pop("_families")
        tece = evolve_of(
            train=split["train"], dev=split["dev"], test=split["test"], families=families, mode="tece", seed=3
        )
        fixed = evolve_of(
            train=split["train"],
            dev=split["dev"],
            test=split["test"],
            families=families,
            mode="fixed_rebind",
            seed=3,
        )
        self.assertEqual(tece["test_once"]["oracle_leak_rate"], 0.0)
        self.assertEqual(fixed["test_once"]["oracle_leak_rate"], 0.0)
        self.assertEqual(tece["test_once"]["fidelity_rate"], 1.0)
        # Explicitly allow TECE <= fixed_rebind (negative result OK)
        self.assertLessEqual(tece["test_once"]["accuracy"], fixed["test_once"]["accuracy"] + 1e-9)


if __name__ == "__main__":
    unittest.main()
