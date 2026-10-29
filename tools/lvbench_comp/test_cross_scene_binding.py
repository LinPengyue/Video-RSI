#!/usr/bin/env python3
"""Scene-local track IDs: no oracle identity bridge across A/B."""

from __future__ import annotations

import unittest

from tools.lvbench_comp.typed_evidence_contract.binding_executor import (
    CrossSceneBindingExecutor,
    evaluate_necessity_v2,
)
from tools.lvbench_comp.typed_evidence_contract.binding_loop import (
    build_binding_split,
    run_bind_task,
    run_binding_ablation,
)
from tools.lvbench_comp.typed_evidence_contract.evolution_loop import _world_pair
from tools.lvbench_comp.typed_evidence_contract.executor import default_genome
from tools.lvbench_comp.typed_evidence_contract.observations_v2 import (
    assert_no_oracle_bridge,
    binding_impossible_from_ids_alone,
    mask_scene_local,
    project_scene_local,
)


class CrossSceneBindingTest(unittest.TestCase):
    def test_a_b_track_ids_disjoint(self) -> None:
        world = _world_pair()
        bundle, omap = project_scene_local(
            world, scenario_id="bridge0", gold_answer="removes_jacket", gold_property="action", seed=1
        )
        bridge = assert_no_oracle_bridge(bundle)
        self.assertTrue(bridge["ok"])
        self.assertEqual(bridge["intersection"], [])
        self.assertTrue(binding_impossible_from_ids_alone(bundle))
        for a_tid, b_tid in omap.gold_matches:
            self.assertTrue(a_tid.startswith("a_"))
            self.assertTrue(b_tid.startswith("b_"))
            self.assertNotEqual(a_tid, b_tid)

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
        self.assertFalse(any(h.get("status") == "HYPOTHESIS_ONLY" for h in b_only.link_hypotheses))

    def test_necessity_distinguishes_dual_vs_shortcut(self) -> None:
        split = build_binding_split()
        dual = [t for t in split["test"] if t.kind == "dual_necessary"]
        shortcut = [t for t in split["test"] if t.kind == "b_only_shortcut"]
        self.assertGreaterEqual(len(dual), 2)
        self.assertGreaterEqual(len(shortcut), 2)
        g = {**default_genome(), "recovery_strategy": "rebind_from_a", "bind_score_threshold": 0.25, "search_budget": 6}
        for task in dual:
            row = run_bind_task(g, task, mode="program_selection")
            self.assertTrue(row["bridge_ok"])
            self.assertFalse(row["b_only"], msg=task.task_id)
        for task in shortcut:
            row = run_bind_task(g, task, mode="program_selection")
            self.assertTrue(row["b_only"], msg=task.task_id)

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

    def test_ablation_bridge_ok_and_tece_not_forced(self) -> None:
        """Negative result allowed: TECE need not beat fixed_rebind."""
        out = run_binding_ablation(n_seeds=3, base_seed=301)
        for arm in ("fixed", "fixed_rebind", "tece", "oracle_program_upper"):
            self.assertIn(arm, out["summary"])
            self.assertGreaterEqual(out["summary"][arm]["bridge_ok"]["mean"], 0.99)


if __name__ == "__main__":
    unittest.main()
