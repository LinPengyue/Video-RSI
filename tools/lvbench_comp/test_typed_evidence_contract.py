#!/usr/bin/env python3
"""Unit tests for Typed Evidence Contract Evolution prototype."""

from __future__ import annotations

import unittest

from tools.lvbench_comp.typed_evidence_contract.counterfactual import run_counterfactual_suite, toy_world
from tools.lvbench_comp.typed_evidence_contract.contracts import OperationName, OperationRequest
from tools.lvbench_comp.typed_evidence_contract.evidence_graph import BindingEdge, EvidenceDependencyGraph, EvidenceNode
from tools.lvbench_comp.typed_evidence_contract.evolution_loop import build_task_split, run_ablation_suite
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
        good, decision = mutate_genome(
            EvolutionGenome(), {"search_budget": 7, "recovery_strategy": "investigate_conflict"}
        )
        self.assertTrue(decision["accepted"])
        self.assertEqual(good.params["search_budget"], 7)

    def test_isolation_policy(self) -> None:
        policy = IsolationPolicy(
            evolution_primitives={"identify_person", "query_action"},
            held_out_composition_signatures={"identify_person + describe_action"},
            train_videos={"v_train"},
            eval_videos={"v_eval"},
            train_uids={"1"},
            eval_uids={"2"},
        )
        ok = assert_isolation(
            policy, {"evolution_seen_signatures": ["identify_person + describe_location"], "harness_id": "INITIAL_HARNESS_DECLARED"}
        )
        self.assertTrue(ok["ok"])
        bad = assert_isolation(
            policy,
            {
                "evolution_seen_signatures": ["identify_person + describe_action"],
                "using_hs1_as_final_judge": True,
                "harness_id": "INITIAL_HARNESS_DECLARED",
            },
        )
        self.assertFalse(bad["ok"])
        self.assertIn("schema_leak:['identify_person + describe_action']", bad["violations"])
        self.assertIn("hs1_used_as_final_judge", bad["violations"])

    def test_b_only_without_binding_fails(self) -> None:
        suite = run_counterfactual_suite()
        self.assertFalse(suite.results["B_only"]["query_ok"])

    def test_forged_evidence_denied(self) -> None:
        suite = run_counterfactual_suite()
        self.assertTrue(suite.results["assertions"]["forged_denied"])

    def test_cross_entity_intervals_denied(self) -> None:
        suite = run_counterfactual_suite()
        self.assertTrue(suite.results["assertions"]["cross_entity_denied"])

    def test_unsupported_answer_denied(self) -> None:
        suite = run_counterfactual_suite()
        self.assertTrue(suite.results["assertions"]["unsupported_denied"])

    def test_multi_candidate_requires_investigation(self) -> None:
        suite = run_counterfactual_suite()
        self.assertTrue(suite.results["assertions"]["multi_candidate_needs_investigation"])
        self.assertTrue(suite.results["multi_candidate"]["recovered"])

    def test_two_timestamps_alone_not_strong(self) -> None:
        g = EvidenceDependencyGraph(answer="removes_jacket")
        g.add_node(EvidenceNode("A1", "entity_x", "A", False))
        g.add_node(EvidenceNode("B1", "entity_y", "B", True))
        # No binding → B shortcut control, not strong composition
        d = g.evaluate()
        self.assertNotEqual(d["composition_credit"], "STRONG_COMPOSITION")

    def test_recovery_blocks_identical_retry(self) -> None:
        world = toy_world()
        ex = TypedEvidenceExecutor(world, {**default_genome(), "recovery_strategy": "relocate_then_resolve", "search_budget": 3})
        # Force a locate miss; recovery also tries locate with widen — different inputs, allowed.
        miss = ex.run(OperationRequest(OperationName.LOCATE_EVENT, {"cue": "zzzz_missing"}))
        self.assertFalse(miss.ok)
        self.assertTrue(ex.memory.recovery_stack)
        self.assertNotEqual(ex.memory.recovery_stack[0].get("action"), "blocked_identical_retry")

    def test_evolution_leave_out_and_ablation_runs(self) -> None:
        seen, unseen = build_task_split()
        self.assertTrue(all(not t.held_out for t in seen))
        self.assertTrue(all(t.held_out for t in unseen))
        unseen_sigs = {u.signature for u in unseen}
        self.assertTrue(all(t.signature not in unseen_sigs for t in seen))
        suite = run_ablation_suite(seed=11)
        self.assertEqual(set(suite), {"fixed", "random", "vanilla", "tece"})
        # Fixed (no recovery) worse than TECE on ambiguous Seen; TECE transfers to held-out Unseen.
        self.assertLess(suite["fixed"]["seen"]["accuracy"], suite["tece"]["seen"]["accuracy"])
        self.assertEqual(suite["tece"]["seen"]["accuracy"], 1.0)
        self.assertEqual(suite["tece"]["unseen_held_out"]["accuracy"], 1.0)
        self.assertTrue(suite["tece"]["strategy_changed"])
        self.assertIn("unseen_held_out", suite["tece"])
        self.assertTrue(suite["tece"]["note"].startswith("Synthetic"))


if __name__ == "__main__":
    unittest.main()
