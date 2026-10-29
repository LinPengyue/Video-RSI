"""Fair cross-scene binding experiments (oracle-bridge free).

Negative TECE results are acceptable and should be reported.
"""

from __future__ import annotations

import math
import random
import statistics
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .binding_executor import CrossSceneBindingExecutor, evaluate_necessity_v2
from .evolution_loop import _world_pair, SHARED_MUTATION_POOL
from .executor import SimulatedWorld, WorldFact, default_genome
from .evolver import ALLOWED_MUTATION_KEYS, EvolutionGenome, EvolverWorkspace
from .contracts import TimeSpan, EntityCandidate
from .observations_v2 import assert_no_oracle_bridge, binding_impossible_from_ids_alone, project_scene_local


@dataclass
class BindTask:
    task_id: str
    kind: str  # dual_necessary | b_only_shortcut
    referring_a_cue: str
    property_name: str
    answer: Any
    split: str
    world: SimulatedWorld
    seed: int = 0


def _dual_necessary_world(answer: str = "removes_jacket") -> SimulatedWorld:
    """Property only on B; identifying cue only discriminative on A attributes."""
    entities = {
        "entity_x": EntityCandidate("entity_x", "oracle_x", aliases=[], confidence=0.9),
        "entity_y": EntityCandidate("entity_y", "oracle_y", aliases=[], confidence=0.9),
    }
    facts = [
        WorldFact("a1", "entity_x", "role_event", "opens", TimeSpan(0, 5, "A"), referring_cues=["purple_top", "short_hair"]),
        WorldFact("a2", "entity_y", "role_event", "waits", TimeSpan(0, 5, "A"), referring_cues=["pink_top", "long_hair"]),
        WorldFact("b1", "entity_x", "action", answer, TimeSpan(25, 30, "B"), referring_cues=["later"]),
        WorldFact("b2", "entity_y", "action", "waves_hand", TimeSpan(25, 30, "B"), referring_cues=["later"]),
    ]
    return SimulatedWorld(facts=facts, entities=entities)


def _b_shortcut_world(answer: str = "removes_jacket") -> SimulatedWorld:
    """B alone has unique referring cue + answer (shortcut control)."""
    entities = {
        "entity_x": EntityCandidate("entity_x", "oracle_x", aliases=[], confidence=0.9),
        "entity_y": EntityCandidate("entity_y", "oracle_y", aliases=[], confidence=0.9),
    }
    facts = [
        WorldFact("a1", "entity_x", "role_event", "opens", TimeSpan(0, 5, "A"), referring_cues=["purple_top"]),
        WorldFact("a2", "entity_y", "role_event", "waits", TimeSpan(0, 5, "A"), referring_cues=["pink_top"]),
        WorldFact(
            "b1",
            "entity_x",
            "action",
            answer,
            TimeSpan(25, 30, "B"),
            referring_cues=["purple_top", "name_badge_answer", "unique_b_cue"],
        ),
        WorldFact("b2", "entity_y", "action", "waves_hand", TimeSpan(25, 30, "B"), referring_cues=["pink_top"]),
    ]
    return SimulatedWorld(facts=facts, entities=entities)


def build_binding_split() -> dict[str, list[BindTask]]:
    train = [
        BindTask("tr_dual_1", "dual_necessary", "purple_top", "action", "removes_jacket", "train", _dual_necessary_world(), 1),
        BindTask("tr_dual_2", "dual_necessary", "purple_top", "action", "points_chart", "train", _dual_necessary_world("points_chart"), 2),
        BindTask("tr_short_1", "b_only_shortcut", "unique_b_cue", "action", "removes_jacket", "train", _b_shortcut_world(), 3),
    ]
    dev = [
        BindTask("dv_dual", "dual_necessary", "purple_top", "action", "takes_bow", "dev", _dual_necessary_world("takes_bow"), 4),
        BindTask("dv_short", "b_only_shortcut", "unique_b_cue", "action", "takes_bow", "dev", _b_shortcut_world("takes_bow"), 5),
    ]
    test = [
        BindTask("te_dual_a", "dual_necessary", "purple_top", "action", "fetches_stick", "test", _dual_necessary_world("fetches_stick"), 11),
        BindTask("te_dual_b", "dual_necessary", "purple_top", "action", "claps_sign", "test", _dual_necessary_world("claps_sign"), 12),
        BindTask("te_short_a", "b_only_shortcut", "unique_b_cue", "action", "fetches_stick", "test", _b_shortcut_world("fetches_stick"), 13),
        BindTask("te_short_b", "b_only_shortcut", "unique_b_cue", "action", "nods_deep", "test", _b_shortcut_world("nods_deep"), 14),
    ]
    return {"train": train, "dev": dev, "test": test}


def run_bind_task(genome: dict[str, Any], task: BindTask, *, mode: str) -> dict[str, Any]:
    bundle, omap = project_scene_local(
        task.world,
        scenario_id=task.task_id,
        gold_answer=task.answer,
        gold_property=task.property_name,
        salt=f"{task.task_id}_{task.seed}",
        seed=task.seed,
    )
    bridge = assert_no_oracle_bridge(bundle)
    nec = evaluate_necessity_v2(
        bundle,
        omap,
        referring_a_cue=task.referring_a_cue,
        property_name=task.property_name,
        genome=genome,
        mode=mode,
    )
    # Expected necessity by generation
    expect_necessary = task.kind == "dual_necessary"
    expect_shortcut = task.kind == "b_only_shortcut"
    return {
        "task_id": task.task_id,
        "kind": task.kind,
        "mode": mode,
        "split": task.split,
        "bridge_ok": bridge["ok"],
        "ids_alone_impossible": binding_impossible_from_ids_alone(bundle),
        "semantic": nec["semantic_answer_correct"],
        "necessary": nec["composition_necessary"],
        "a_only": nec["a_only_solves"],
        "b_only": nec["b_only_solves"],
        "path": nec["evidence_path_valid"],
        "expect_necessary": expect_necessary,
        "expect_b_shortcut": expect_shortcut,
        "necessity_matches_generation": (
            (expect_necessary and nec["composition_necessary"] and not nec["b_only_solves"] and not nec["a_only_solves"])
            or (expect_shortcut and nec["b_only_solves"])
        ),
        "details": nec["details"],
        "used_oracle_match": nec["details"]["ab"].get("used_oracle_match"),
    }


def evaluate_mode(genome: dict[str, Any], tasks: list[BindTask], mode: str) -> dict[str, Any]:
    rows = [run_bind_task(genome, t, mode=mode) for t in tasks]
    n = max(1, len(rows))
    dual = [r for r in rows if r["kind"] == "dual_necessary"]
    short = [r for r in rows if r["kind"] == "b_only_shortcut"]
    return {
        "accuracy": sum(1 for r in rows if r["semantic"]) / n,
        "necessity_rate": sum(1 for r in rows if r["necessary"]) / n,
        "bridge_ok_rate": sum(1 for r in rows if r["bridge_ok"]) / n,
        "generation_agreement": sum(1 for r in rows if r["necessity_matches_generation"]) / n,
        "dual_semantic": sum(1 for r in dual if r["semantic"]) / max(1, len(dual)),
        "shortcut_b_only_detected": sum(1 for r in short if r["b_only"]) / max(1, len(short)),
        "rows": rows,
    }


def evolve_binding(
    *,
    train: list[BindTask],
    dev: list[BindTask],
    test: list[BindTask],
    mode: str,
    seed: int = 0,
    generations: int = 5,
    population: int = 4,
    agent_mode: str = "program_selection",
) -> dict[str, Any]:
    """mode: fixed | fixed_rebind | random | vanilla | tece | oracle_program_upper"""
    rng = random.Random(seed)
    if mode == "oracle_program_upper":
        g = {**default_genome(), "recovery_strategy": "rebind_from_a", "search_budget": 6, "bind_score_threshold": 0.1}
        return {
            "mode": mode,
            "agent_mode": "oracle_program",
            "best_genome": g,
            "train": evaluate_mode(g, train, "oracle_program"),
            "dev": evaluate_mode(g, dev, "oracle_program"),
            "test_once": evaluate_mode(g, test, "oracle_program"),
            "strategy_changed": False,
            "note": "Diagnostic upper bound with gold match; NOT transferable discovery.",
        }

    g0 = {**default_genome(), "recovery_strategy": "none", "search_budget": 4, "bind_score_threshold": 0.45}
    if mode == "fixed_rebind":
        g0.update({"recovery_strategy": "rebind_from_a", "bind_score_threshold": 0.25, "search_budget": 6})
    best = EvolutionGenome(g0)
    history = []
    if mode in {"fixed", "fixed_rebind"}:
        return {
            "mode": mode,
            "agent_mode": agent_mode,
            "best_genome": best.params,
            "train": evaluate_mode(best.params, train, agent_mode),
            "dev": evaluate_mode(best.params, dev, agent_mode),
            "test_once": evaluate_mode(best.params, test, agent_mode),
            "strategy_changed": False,
            "note": "Oracle-bridge-free; not real-video RSI.",
        }

    for gen in range(generations):
        cands = [deepcopy(best)]
        for _ in range(population - 1):
            g = deepcopy(best)
            patch = deepcopy(rng.choice(SHARED_MUTATION_POOL + [
                {"bind_score_threshold": 0.2},
                {"bind_score_threshold": 0.35},
                {"bind_score_threshold": 0.5},
            ]))
            # allow bind_score_threshold via direct merge if not in ALLOWED
            ws = EvolverWorkspace(g)
            legal = {k: v for k, v in patch.items() if k in ALLOWED_MUTATION_KEYS}
            ws.propose(legal)
            if "bind_score_threshold" in patch:
                g.params["bind_score_threshold"] = patch["bind_score_threshold"]
            if mode == "tece" and rng.random() < 0.5:
                g.params["recovery_strategy"] = rng.choice(
                    ["none", "relocate_then_resolve", "rebind_from_a", "investigate_conflict"]
                )
            cands.append(g)
        scored = []
        for g in cands:
            # evolver_policy uses program_selection agent path (no gold match)
            am = "evolver_policy" if mode == "tece" else agent_mode
            # map evolver_policy -> program_selection executor behavior
            exec_mode = "program_selection"
            ev = evaluate_mode(g.params, dev, exec_mode)
            score = ev["accuracy"] + 0.25 * ev["generation_agreement"] - 0.02 * 0
            scored.append((score, g, ev))
        scored.sort(key=lambda x: x[0], reverse=True)
        winner = scored[0][1]
        history.append({"generation": gen, "dev_acc": scored[0][2]["accuracy"], "changed": winner.params != best.params})
        best = winner

    return {
        "mode": mode,
        "agent_mode": agent_mode,
        "best_genome": best.params,
        "train": evaluate_mode(best.params, train, "program_selection"),
        "dev": evaluate_mode(best.params, dev, "program_selection"),
        "test_once": evaluate_mode(best.params, test, "program_selection"),
        "history": history,
        "strategy_changed": any(h["changed"] for h in history),
        "note": "Oracle-bridge-free program_selection path; negative TECE result OK.",
    }


def _ci(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"mean": 0.0, "n": 0}
    m = statistics.mean(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    half = 1.96 * sd / math.sqrt(len(xs)) if len(xs) > 1 else 0.0
    return {"mean": m, "std": sd, "ci95_low": m - half, "ci95_high": m + half, "n": len(xs)}


def run_binding_ablation(n_seeds: int = 15, base_seed: int = 300) -> dict[str, Any]:
    split = build_binding_split()
    arms = ["fixed", "fixed_rebind", "random", "vanilla", "tece", "oracle_program_upper"]
    per = {a: [] for a in arms}
    failures = []
    for i in range(n_seeds):
        seed = base_seed + i
        for arm in arms:
            res = evolve_binding(
                train=split["train"],
                dev=split["dev"],
                test=split["test"],
                mode=arm,
                seed=seed,
            )
            te = res["test_once"]
            per[arm].append(
                {
                    "seed": seed,
                    "acc": te["accuracy"],
                    "necessity": te["necessity_rate"],
                    "bridge_ok": te["bridge_ok_rate"],
                    "gen_agree": te["generation_agreement"],
                    "dual_sem": te["dual_semantic"],
                    "shortcut_detect": te["shortcut_b_only_detected"],
                }
            )
            for row in te["rows"]:
                if not row["bridge_ok"] or (row["kind"] == "dual_necessary" and row["b_only"]):
                    failures.append({"seed": seed, "arm": arm, **{k: row[k] for k in ("task_id", "kind", "semantic", "necessary", "a_only", "b_only", "bridge_ok")}})
    summary = {
        a: {
            "acc": _ci([r["acc"] for r in rows]),
            "necessity": _ci([r["necessity"] for r in rows]),
            "bridge_ok": _ci([r["bridge_ok"] for r in rows]),
            "generation_agreement": _ci([r["gen_agree"] for r in rows]),
            "dual_semantic": _ci([r["dual_sem"] for r in rows]),
            "shortcut_detect": _ci([r["shortcut_detect"] for r in rows]),
        }
        for a, rows in per.items()
    }
    return {
        "n_seeds": n_seeds,
        "summary": summary,
        "per_seed": per,
        "failure_sample": failures[:50],
        "interpretation": (
            "No shared A/B track_id. TECE advantage not required. "
            "oracle_program_upper is diagnostic only. Not real-video RSI."
        ),
    }
