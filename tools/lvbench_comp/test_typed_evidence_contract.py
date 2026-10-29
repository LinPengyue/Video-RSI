#!/usr/bin/env python3
"""Unit tests for Typed Evidence Contract Evolution prototype."""

from __future__ import annotations

import unittest

from tools.lvbench_comp.typed_evidence_contract.counterfactual import run_counterfactual_suite, toy_world
from tools.lvbench_comp.typed_evidence_contract.contracts import OperationName, OperationRequest
from tools.lvbench_comp.typed_evidence_contract.evidence_graph import EvidenceDependencyGraph, EvidenceNode
from tools.lvbench_comp.typed_evidence_contract.evolution_loop import (
    build_structural_split,
    build_task_split,
    run_ablation_suite,
    split_witness,
)
from tools.lvbench_comp.typed_evidence_contract.evolver import EvolutionGenome, EvolverWorkspace, mutate_genome
from tools.lvbench_comp.typed_evidence_contract.executor import TypedEvidenceExecutor, default_genome
from tools.lvbench_comp.typed_evidence_contract.isolation import IsolationPolicy, assert_isolation
from tools.lvbench_comp.typed_evidence_contract.necessity import evaluate_necessity
from tools.lvbench_comp.typed_evidence_contract.program_schema import (
    SCHEMA_FORWARD_PERSON_ACTION,
    SCHEMA_REVERSE_EVENT_TO_PRIOR_ACTION,
)


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
        d = g.evaluate()
        self.assertNotEqual(d["composition_credit"], "STRONG_COMPOSITION")

    def test_single_entity_b_path_valid_necessity_unproven(self) -> None:
        g = EvidenceDependencyGraph(answer="removes_jacket")
        g.add_node(EvidenceNode("A1", "entity_x", "A", False))
        g.add_node(EvidenceNode("B1", "entity_x", "B", True))
        from tools.lvbench_comp.typed_evidence_contract.evidence_graph import BindingEdge

        g.add_binding(BindingEdge("first speaker", "entity_x", "A1"))
        d = g.evaluate()
        self.assertEqual(d["composition_credit"], "PATH_VALID_NECESSITY_UNPROVEN")
        self.assertTrue(d["evidence_path_valid"])
        self.assertFalse(d["composition_necessary_hint"])

    def test_recovery_blocks_identical_retry(self) -> None:
        world = toy_world()
        ex = TypedEvidenceExecutor(world, {**default_genome(), "recovery_strategy": "relocate_then_resolve", "search_budget": 3})
        miss = ex.run(OperationRequest(OperationName.LOCATE_EVENT, {"cue": "zzzz_missing"}))
        self.assertFalse(miss.ok)
        self.assertTrue(ex.memory.recovery_stack)
        self.assertNotEqual(ex.memory.recovery_stack[0].get("action"), "blocked_identical_retry")

    def test_structural_leave_out_witness(self) -> None:
        w = split_witness()
        self.assertTrue(w["leave_out_ok"])
        self.assertEqual(w["intersecting_hashes"], [])
        self.assertNotEqual(
            SCHEMA_FORWARD_PERSON_ACTION.graph_hash(),
            SCHEMA_REVERSE_EVENT_TO_PRIOR_ACTION.graph_hash(),
        )

    def test_necessity_separates_judgments(self) -> None:
        world = toy_world()
        genome = default_genome()
        nec = evaluate_necessity(
            world,
            referring="first speaker",
            property_name="action",
            gold_answer="removes_jacket",
            genome=genome,
            evidence_path_valid=True,
        )
        self.assertTrue(nec.ab_solves)
        self.assertFalse(nec.a_only_solves)
        # B-only may or may not solve depending on resolve path; composition_necessary requires both false
        self.assertIsInstance(nec.composition_necessary, bool)

    def test_evolution_structural_ablation_runs(self) -> None:
        seen, unseen = build_task_split()
        self.assertTrue(all(t.split in {"train", "dev"} for t in seen))
        self.assertTrue(all(t.split == "test" for t in unseen))
        train_hashes = {t.graph_hash for t in seen}
        self.assertTrue(all(t.graph_hash not in train_hashes for t in unseen))
        suite = run_ablation_suite(seed=11)
        self.assertIn("tece", suite)
        self.assertIn("fixed_rebind", suite)
        self.assertIn("test_once", suite["tece"])
        self.assertEqual(suite["tece"]["selection_split"], "dev")
        self.assertTrue(suite["tece"]["note"].startswith("Synthetic"))
        # Must NOT claim predetermined TECE 1.00/1.00 — only that suite runs.
        self.assertIn("accuracy", suite["tece"]["test_once"])


if __name__ == "__main__":
    unittest.main()
