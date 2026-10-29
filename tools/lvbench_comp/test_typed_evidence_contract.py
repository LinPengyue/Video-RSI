#!/usr/bin/env python3
"""Unit tests for Typed Evidence Contract Evolution prototype."""

from __future__ import annotations

import unittest

from tools.lvbench_comp.typed_evidence_contract.counterfactual import run_counterfactual_suite, toy_world
from tools.lvbench_comp.typed_evidence_contract.contracts import OperationName, OperationRequest
from tools.lvbench_comp.typed_evidence_contract.evolver import EvolutionGenome, EvolverWorkspace, mutate_genome
from tools.lvbench_comp.typed_evidence_contract.executor import TypedEvidenceExecutor, default_genome
from tools.lvbench_comp.typed_evidence_contract.isolation import IsolationPolicy, assert_isolation


class TypedEvidenceContractTest(unittest.TestCase):
    def test_missing_evidence_reports_gap(self) -> None:
        world = toy_world()
        world.facts = [f for f in world.facts if f.property_name != "action" or f.entity_id != "entity_x"]
        ex = TypedEvidenceExecutor(world)
        ex.run(OperationRequest(OperationName.RESOLVE_REFERENCE, {"referring_expression": "first speaker"}))
        result = ex.run(OperationRequest(OperationName.QUERY_PROPERTY, {"property_name": "action"}))
        self.assertFalse(result.ok)
        self.assertEqual(result.failure_code, "MISSING_EVIDENCE")
        self.assertTrue(any(g.startswith("query:") for g in ex.memory.pending_gaps))

    def test_subject_swap_changes_query_object(self) -> None:
        suite = run_counterfactual_suite()
        self.assertTrue(suite.results["assertions"]["binding_changes_query_target"])
        self.assertEqual(suite.results["A_plus_B"]["value"], "removes_jacket")
        self.assertEqual(suite.results["subject_swap"]["value"], "waves_hand")

    def test_single_clip_not_strong_composition(self) -> None:
        suite = run_counterfactual_suite()
        self.assertTrue(suite.results["assertions"]["single_clip_not_strong_success"])

    def test_failure_triggers_recovery(self) -> None:
        suite = run_counterfactual_suite()
        self.assertTrue(suite.results["assertions"]["failure_triggers_recovery"])

    def test_evolver_rejects_illegal_mutations(self) -> None:
        genome = EvolutionGenome()
        ws = EvolverWorkspace(genome)
        bad = ws.propose({"update_frozen_video_model_weights": True, "search_budget": 9})
        self.assertFalse(bad["accepted"])
        good, decision = mutate_genome(EvolutionGenome(), {"search_budget": 7, "recovery_strategy": "investigate_conflict"})
        self.assertTrue(decision["accepted"])
        self.assertEqual(good.params["search_budget"], 7)

    def test_isolation_policy(self) -> None:
        policy = IsolationPolicy(
            evolution_primitives={"identify_person", "query_action"},
            held_out_composition_signatures={"identify_person + query_action"},
            train_videos={"v_train"},
            eval_videos={"v_eval"},
            train_uids={"1"},
            eval_uids={"2"},
        )
        ok = assert_isolation(policy, {"evolution_seen_signatures": ["identify_person + query_location"], "harness_id": "INITIAL_HARNESS_DECLARED"})
        self.assertTrue(ok["ok"])
        bad = assert_isolation(
            policy,
            {
                "evolution_seen_signatures": ["identify_person + query_action"],
                "using_hs1_as_final_judge": True,
                "harness_id": "INITIAL_HARNESS_DECLARED",
            },
        )
        self.assertFalse(bad["ok"])
        self.assertIn("schema_leak:['identify_person + query_action']", bad["violations"])
        self.assertIn("hs1_used_as_final_judge", bad["violations"])

    def test_b_only_without_binding_fails(self) -> None:
        suite = run_counterfactual_suite()
        self.assertFalse(suite.results["B_only"]["query_ok"])


if __name__ == "__main__":
    unittest.main()
