#!/usr/bin/env python3
"""Scene-local binding: no gold-conditioned scores; independent local names."""

from __future__ import annotations

import json
import random
import unittest
from copy import deepcopy

from tools.lvbench_comp.typed_evidence_contract.binding_executor import evaluate_necessity_v2
from tools.lvbench_comp.typed_evidence_contract.binding_loop import (
    build_binding_split,
    run_bind_task,
    run_binding_ablation,
)
from tools.lvbench_comp.typed_evidence_contract.evolution_loop import _world_pair
from tools.lvbench_comp.typed_evidence_contract.executor import default_genome
from tools.lvbench_comp.typed_evidence_contract.observations_v2 import (
    agent_link_signature,
    assert_local_ids_disjoint,
    binding_impossible_from_ids_alone,
    mask_scene_local,
    pair_ranking_metrics,
    permute_gold_matches,
    project_scene_local,
    rename_local_ids,
)


class CrossSceneBindingTest(unittest.TestCase):
    def test_a_b_track_ids_disjoint(self) -> None:
        world = _world_pair()
        bundle, omap = project_scene_local(
            world, scenario_id="bridge0", gold_answer="removes_jacket", gold_property="action", seed=1
        )
        ids = assert_local_ids_disjoint(bundle)
        self.assertTrue(ids["local_ids_disjoint"])
        self.assertEqual(ids["intersection"], [])
        self.assertTrue(binding_impossible_from_ids_alone(bundle))
        for a_tid, b_tid in omap.gold_matches:
            self.assertTrue(a_tid.startswith("a_"))
            self.assertTrue(b_tid.startswith("b_"))
            self.assertNotEqual(a_tid, b_tid)

    def test_no_shared_oracle_name_suffix(self) -> None:
        world = _world_pair()
        bundle, _ = project_scene_local(
            world, scenario_id="nick0", gold_answer="removes_jacket", gold_property="action", seed=9
        )
        surfaces = []
        for e in bundle.entities.values():
            surfaces.extend(e.surface_forms)
        joined = " ".join(surfaces)
        self.assertNotIn("person_in_A_", joined)
        self.assertNotIn("person_in_B_", joined)
        # No entity_x / entity_y leaked into surfaces
        self.assertNotIn("entity_x", joined)
        self.assertNotIn("entity_y", joined)

    def test_link_scores_invariant_to_gold_permutation(self) -> None:
        """Hold observations fixed; permute scorer gold — agent-visible scores unchanged."""
        world = _world_pair()
        bundle, omap = project_scene_local(
            world, scenario_id="perm0", gold_answer="removes_jacket", gold_property="action", seed=3
        )
        sig0 = agent_link_signature(bundle)
        oids = list(omap.a_track_to_oracle.keys())
        if len(oids) >= 2:
            perm = {oids[0]: oids[1], oids[1]: oids[0]}
        else:
            perm = {oids[0]: oids[0]}
        omap2 = permute_gold_matches(omap, perm)
        # Bundle untouched
        self.assertEqual(agent_link_signature(bundle), sig0)
        # Gold pairs may change, but agent scores must not depend on them
        self.assertNotEqual(set(omap.gold_matches), set(omap2.gold_matches))
        # Recomputing pair metrics with new gold changes accuracy, not agent scores
        m1 = pair_ranking_metrics(bundle, omap)
        m2 = pair_ranking_metrics(bundle, omap2)
        self.assertEqual(agent_link_signature(bundle), sig0)
        # After permute, top1 vs (wrong) gold typically drops unless cues alone recover
        self.assertIsInstance(m1["pair_accuracy_top1"], float)
        self.assertIsInstance(m2["pair_accuracy_top1"], float)

    def test_no_gold_term_in_hypothesis_payload(self) -> None:
        world = _world_pair()
        bundle, _ = project_scene_local(
            world, scenario_id="nogold", gold_answer="removes_jacket", gold_property="action", seed=4
        )
        blob = json.dumps(bundle.to_agent_dict())
        self.assertNotIn("is_gold", blob)
        self.assertNotIn("gold_matches", blob)
        for h in bundle.link_hypotheses:
            if h.get("status") == "HYPOTHESIS_ONLY":
                self.assertNotIn("is_gold", h)
                self.assertNotIn("correct", h)
                self.assertIn("score", h)
                self.assertIn("cue_overlap", h)

    def test_rename_local_ids_preserves_relative_scores(self) -> None:
        world = _world_pair()
        bundle, omap = project_scene_local(
            world, scenario_id="ren0", gold_answer="removes_jacket", gold_property="action", seed=5
        )
        scores0 = sorted(float(h["score"]) for h in bundle.link_hypotheses if h.get("status") == "HYPOTHESIS_ONLY")
        nb, no = rename_local_ids(bundle, omap, random.Random(0))
        scores1 = sorted(float(h["score"]) for h in nb.link_hypotheses if h.get("status") == "HYPOTHESIS_ONLY")
        self.assertEqual(scores0, scores1)
        self.assertTrue(assert_local_ids_disjoint(nb)["local_ids_disjoint"])
        # Predictions under fixed_rebind should match after rename (IDs remapped in gold too)
        g = {**default_genome(), "recovery_strategy": "rebind_from_a", "bind_score_threshold": 0.1, "search_budget": 6}
        r0 = evaluate_necessity_v2(bundle, omap, referring_a_cue="purple_top", property_name="action", genome=g)
        r1 = evaluate_necessity_v2(nb, no, referring_a_cue="purple_top", property_name="action", genome=g)
        self.assertEqual(r0["semantic_answer_correct"], r1["semantic_answer_correct"])

    def test_neutral_mask_drops_cross_links_and_foreign_entities(self) -> None:
        world = _world_pair()
        bundle, omap = project_scene_local(
            world, scenario_id="mask0", gold_answer="removes_jacket", gold_property="action", seed=2
        )
        a_only = mask_scene_local(bundle, {"A"}, public_context=omap.public_context)
        b_only = mask_scene_local(bundle, {"B"}, public_context=omap.public_context)
        self.assertTrue(all(f.evidence_group == "A" for f in a_only.facts))
        self.assertTrue(all(f.evidence_group == "B" for f in b_only.facts))
        self.assertTrue(all(tid.startswith("a_") for tid in a_only.entities))
        self.assertTrue(all(tid.startswith("b_") for tid in b_only.entities))
        self.assertFalse(any(h.get("status") == "HYPOTHESIS_ONLY" for h in a_only.link_hypotheses))

    def test_necessity_distinguishes_dual_vs_shortcut(self) -> None:
        split = build_binding_split()
        dual = [t for t in split["test"] if t.kind == "dual_necessary"]
        shortcut = [t for t in split["test"] if t.kind == "b_only_shortcut"]
        self.assertGreaterEqual(len(dual), 2)
        self.assertGreaterEqual(len(shortcut), 2)
        g = {**default_genome(), "recovery_strategy": "rebind_from_a", "bind_score_threshold": 0.15, "search_budget": 6}
        for task in shortcut:
            row = run_bind_task(g, task, mode="program_selection")
            self.assertTrue(row["b_only"], msg=task.task_id)
            self.assertTrue(row["local_ids_disjoint"])

    def test_hard_negative_lookalikes_report_pair_metrics(self) -> None:
        world = _world_pair()
        bundle, omap = project_scene_local(
            world,
            scenario_id="hardneg",
            gold_answer="removes_jacket",
            gold_property="action",
            seed=11,
            lookalike_hard_negatives=True,
        )
        m = pair_ranking_metrics(bundle, omap)
        self.assertIn("pair_accuracy_top1", m)
        self.assertIn("topk_pair_recall", m)
        self.assertTrue(assert_local_ids_disjoint(bundle)["ok"])

    def test_oracle_program_upper_vs_selection_modes(self) -> None:
        split = build_binding_split()
        task = next(t for t in split["test"] if t.kind == "dual_necessary")
        g = {**default_genome(), "bind_score_threshold": 0.1, "recovery_strategy": "rebind_from_a", "search_budget": 6}
        bundle, omap = project_scene_local(
            task.world,
            scenario_id=task.task_id,
            gold_answer=task.answer,
            gold_property=task.property_name,
            salt=f"{task.task_id}_{task.seed}",
            seed=task.seed,
        )
        upper = evaluate_necessity_v2(
            bundle, omap, referring_a_cue=task.referring_a_cue, property_name=task.property_name, genome=g, mode="oracle_program"
        )
        select = evaluate_necessity_v2(
            bundle,
            omap,
            referring_a_cue=task.referring_a_cue,
            property_name=task.property_name,
            genome=g,
            mode="program_selection",
        )
        self.assertEqual(upper["mode"], "oracle_program")
        self.assertEqual(select["mode"], "program_selection")
        self.assertTrue(upper["details"]["ab"].get("used_oracle_match"))
        self.assertFalse(select["details"]["ab"].get("used_oracle_match"))
        self.assertTrue(upper["semantic_answer_correct"])

    def test_fair_ablation_accepts_negative_tece(self) -> None:
        out = run_binding_ablation(n_seeds=3, base_seed=401)
        self.assertEqual(out["experiment_label"], "binding_policy_evolution_only")
        self.assertFalse(out["ok_for_expensive_rsi"])
        for arm in ("fixed", "fixed_rebind", "tece", "oracle_program_upper"):
            self.assertIn(arm, out["summary"])
            self.assertGreaterEqual(out["summary"][arm]["local_ids_disjoint"]["mean"], 0.99)
            self.assertIn("pair_accuracy_top1", out["summary"][arm])


if __name__ == "__main__":
    unittest.main()
