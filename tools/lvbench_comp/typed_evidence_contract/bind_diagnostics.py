"""Diagnose pair-ranking vs bind-acceptance gap; matched-budget parity; independent scenarios.

Frozen 4-task suite is a NEGATIVE CONTROL regression only — do not optimize TECE against it.
"""

from __future__ import annotations

import json
import math
import random
import statistics
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .binding_executor import CrossSceneBindingExecutor, evaluate_necessity_v2
from .binding_loop import BindTask, _b_shortcut_world, _dual_necessary_world, build_binding_split, evaluate_mode
from .contracts import EntityCandidate, TimeSpan
from .executor import SimulatedWorld, WorldFact, default_genome
from .evolver import ALLOWED_MUTATION_KEYS, EvolutionGenome, EvolverWorkspace
from .evolution_loop import SHARED_MUTATION_POOL
from .observations_v2 import pair_ranking_metrics, project_scene_local


def _ci(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"mean": 0.0, "n": 0}
    m = statistics.mean(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    half = 1.96 * sd / math.sqrt(len(xs)) if len(xs) > 1 else 0.0
    return {"mean": m, "std": sd, "ci95_low": m - half, "ci95_high": m + half, "n": len(xs)}


def instrument_bind_trace(
    genome: dict[str, Any],
    task: BindTask,
    *,
    mode: str = "program_selection",
) -> dict[str, Any]:
    """Full AB pipeline trace: resolve → rank → threshold/recovery → bind → query."""
    bundle, omap = project_scene_local(
        task.world,
        scenario_id=f"trace_{task.task_id}",
        gold_answer=task.answer,
        gold_property=task.property_name,
        salt=f"trace|{task.task_id}|{task.seed}",
        seed=task.seed,
    )
    pair = pair_ranking_metrics(bundle, omap)
    gold = set(omap.gold_matches)
    ex = CrossSceneBindingExecutor(bundle, genome, mode=mode)
    r_a = ex._resolve_side("A", task.referring_a_cue)
    resolve_ok = bool(r_a.ok)
    bound_a = ex.memory.bound_a
    # Ranking for resolved A
    cands = [
        h
        for h in bundle.link_hypotheses
        if h.get("status") == "HYPOTHESIS_ONLY" and h.get("a_track") == bound_a
    ]
    ranked = sorted(cands, key=lambda h: float(h.get("score", 0)), reverse=True)
    top1 = ranked[0] if ranked else None
    gold_b = {b for (a, b) in gold if a == bound_a} if bound_a else set()
    top1_is_gold = bool(top1 and top1["b_track"] in gold_b)
    thr0 = float(genome.get("bind_score_threshold", 0.35))
    recovery = genome.get("recovery_strategy", "none")
    r_b = ex._bind_cross_scene()
    bind_ok = bool(r_b.ok)
    reject_reason = None if bind_ok else (r_b.failure_code or r_b.message)
    selected_score = float(top1["score"]) if top1 else None
    # Would top1 pass thr0 without recovery?
    pass_raw = selected_score is not None and selected_score >= thr0
    thr_after = thr0
    if (not pass_raw) and recovery in {"relocate_then_resolve", "rebind_from_a", "investigate_conflict"}:
        thr_after = thr0 * 0.5
    pass_with_recovery = selected_score is not None and selected_score >= thr_after
    r_q = ex._query(task.property_name) if bind_ok else None
    pred = r_q.outputs.get("property_value") if r_q and r_q.ok else None
    failure_axis = "ok"
    if not resolve_ok:
        failure_axis = "resolve_A_failed"
    elif not ranked:
        failure_axis = "no_hypotheses_for_A"
    elif not top1_is_gold and bind_ok:
        failure_axis = "wrong_pair_accepted"
    elif top1_is_gold and not bind_ok:
        failure_axis = "ranking_ok_but_threshold_reject"
    elif not top1_is_gold and not bind_ok:
        failure_axis = "ranking_miss_and_reject"
    elif bind_ok and pred != task.answer:
        failure_axis = "bind_ok_but_wrong_answer"
    return {
        "task_id": task.task_id,
        "kind": task.kind,
        "mode": mode,
        "genome": {
            "recovery_strategy": recovery,
            "bind_score_threshold": thr0,
            "search_budget": genome.get("search_budget"),
        },
        "resolve_ok": resolve_ok,
        "bound_a": bound_a,
        "n_cands": len(ranked),
        "top1_score": selected_score,
        "top1_is_gold": top1_is_gold,
        "gold_b_for_a": sorted(gold_b),
        "pass_raw_threshold": pass_raw,
        "pass_with_recovery": pass_with_recovery,
        "bind_ok": bind_ok,
        "reject_reason": reject_reason,
        "recovery_stack": list(ex.memory.recovery_stack),
        "tool_calls": len(ex.memory.tool_calls),
        "pred": pred,
        "answer_ok": pred == task.answer,
        "pair_accuracy_top1_bundle": pair["pair_accuracy_top1"],
        "failure_axis": failure_axis,
        "pair_correct_at_bind": bool(
            bind_ok and ex.memory.bound_a and ex.memory.bound_b and (ex.memory.bound_a, ex.memory.bound_b) in gold
        ),
    }


def collect_failure_taxonomy(n_per_arm: int = 4) -> dict[str, Any]:
    """Representative traces on frozen suite — diagnosis only, not TECE tuning."""
    split = build_binding_split()
    arms = {
        "strong_fixed_rebind": {
            **default_genome(),
            "recovery_strategy": "rebind_from_a",
            "bind_score_threshold": 0.25,
            "search_budget": 6,
        },
        "tece_like_init": {
            **default_genome(),
            "recovery_strategy": "none",
            "bind_score_threshold": 0.45,
            "search_budget": 4,
        },
        "matched_init_no_recovery": {
            **default_genome(),
            "recovery_strategy": "none",
            "bind_score_threshold": 0.25,
            "search_budget": 6,
        },
        "matched_init_with_recovery": {
            **default_genome(),
            "recovery_strategy": "rebind_from_a",
            "bind_score_threshold": 0.25,
            "search_budget": 6,
        },
    }
    traces: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, dict[str, int]] = {}
    for arm, g in arms.items():
        traces[arm] = []
        counts[arm] = {}
        for task in split["test"]:
            tr = instrument_bind_trace(g, task)
            traces[arm].append(tr)
            counts[arm][tr["failure_axis"]] = counts[arm].get(tr["failure_axis"], 0) + 1
    # Keep 1–2 examples per failure axis across arms
    examples: dict[str, list[dict[str, Any]]] = {}
    for arm, rows in traces.items():
        for tr in rows:
            ax = tr["failure_axis"]
            examples.setdefault(ax, [])
            if len(examples[ax]) < 2:
                examples[ax].append({"arm": arm, **{k: tr[k] for k in (
                    "task_id", "kind", "genome", "top1_score", "top1_is_gold",
                    "pass_raw_threshold", "pass_with_recovery", "bind_ok", "reject_reason",
                    "failure_axis", "pair_correct_at_bind", "answer_ok",
                )}})
    return {
        "suite": "frozen_4task_negative_control",
        "note": "Do not optimize TECE against these tasks.",
        "arm_failure_counts": counts,
        "examples_by_axis": examples,
        "full_traces": traces,
    }


def matched_budget_ablation(n_seeds: int = 10, base_seed: int = 700) -> dict[str, Any]:
    """Exact parity: same init genome / budget / threshold; only evolution differs.

    Also report strong_fixed_rebind as a separate best-practice reference (not weakened).
    """
    split = build_binding_split()
    shared_init = {
        **default_genome(),
        "recovery_strategy": "none",
        "bind_score_threshold": 0.25,
        "search_budget": 6,
    }
    strong_ref = {
        **default_genome(),
        "recovery_strategy": "rebind_from_a",
        "bind_score_threshold": 0.25,
        "search_budget": 6,
    }

    def eval_fixed(g: dict[str, Any]) -> dict[str, Any]:
        return evaluate_mode(g, split["test"], "program_selection")

    def evolve_matched(seed: int) -> dict[str, Any]:
        """TECE-like evolution starting from shared_init (matched)."""
        rng = random.Random(seed)
        best = EvolutionGenome(deepcopy(shared_init))
        for _gen in range(5):
            cands = [deepcopy(best)]
            for _ in range(3):
                g = deepcopy(best)
                patch = deepcopy(
                    rng.choice(
                        SHARED_MUTATION_POOL
                        + [
                            {"bind_score_threshold": 0.15},
                            {"bind_score_threshold": 0.25},
                            {"bind_score_threshold": 0.35},
                            {"bind_score_threshold": 0.45},
                        ]
                    )
                )
                ws = EvolverWorkspace(g)
                legal = {k: v for k, v in patch.items() if k in ALLOWED_MUTATION_KEYS}
                ws.propose(legal)
                if "bind_score_threshold" in patch:
                    g.params["bind_score_threshold"] = patch["bind_score_threshold"]
                if rng.random() < 0.5:
                    g.params["recovery_strategy"] = rng.choice(
                        ["none", "relocate_then_resolve", "rebind_from_a", "investigate_conflict"]
                    )
                cands.append(g)
            scored = []
            for g in cands:
                ev = evaluate_mode(g.params, split["dev"], "program_selection")
                score = ev["accuracy"] + 0.25 * ev["generation_agreement"]
                scored.append((score, g))
            scored.sort(key=lambda x: x[0], reverse=True)
            best = scored[0][1]
        return evaluate_mode(best.params, split["test"], "program_selection")

    per = {"matched_static": [], "matched_tece_evolve": [], "strong_fixed_rebind_ref": []}
    for i in range(n_seeds):
        seed = base_seed + i
        per["matched_static"].append(eval_fixed(shared_init))
        per["matched_tece_evolve"].append(evolve_matched(seed))
        per["strong_fixed_rebind_ref"].append(eval_fixed(strong_ref))

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "acc": _ci([r["accuracy"] for r in rows]),
            "pair_correct_at_bind": _ci([r["pair_correct_at_bind"] for r in rows]),
            "pair_accuracy_top1": _ci([r["pair_accuracy_top1"] for r in rows]),
            "necessity": _ci([r["necessity_rate"] for r in rows]),
            "dual_semantic": _ci([r["dual_semantic"] for r in rows]),
            "shortcut_detect": _ci([r["shortcut_b_only_detected"] for r in rows]),
        }

    return {
        "n_seeds": n_seeds,
        "shared_init": shared_init,
        "strong_ref": strong_ref,
        "summary": {k: summarize(v) for k, v in per.items()},
        "interpretation": (
            "matched_static vs matched_tece_evolve share init/budget/threshold; "
            "strong_fixed_rebind_ref is a separate best-practice baseline (not weakened). "
            "Frozen 4-task suite is negative-control only."
        ),
        "ok_for_expensive_rsi": False,
        "experiment_label": "binding_policy_evolution_only",
    }


def _independent_world(rng: random.Random, *, kind: str) -> tuple[SimulatedWorld, str, str, Any]:
    """Generate a novel multi-entity scenario not in the frozen 4-task answer set."""
    answers = ["places_marker", "lifts_sign", "spins_once", "opens_gate", "drops_ball", "points_left"]
    distractors = ["sits_still", "waves_hand", "looks_away", "ties_shoe"]
    ans = rng.choice(answers)
    cue_a = rng.choice(["teal_scarf", "amber_hat", "silver_badge", "checkered_sleeve"])
    cue_b_weak = rng.choice(["far_cam", "side_angle", "low_light"])
    entities = {
        "entity_x": EntityCandidate("entity_x", "ox", aliases=[], confidence=0.9),
        "entity_y": EntityCandidate("entity_y", "oy", aliases=[], confidence=0.9),
        "entity_z": EntityCandidate("entity_z", "oz", aliases=[], confidence=0.9),
    }
    # Role reversal / missing evidence variants
    if kind == "dual_necessary":
        facts = [
            WorldFact("a1", "entity_x", "role_event", "enters", TimeSpan(0, 4, "A"), referring_cues=[cue_a, "short_hair"]),
            WorldFact("a2", "entity_y", "role_event", "waits", TimeSpan(0, 4, "A"), referring_cues=["maroon_coat", "long_hair"]),
            WorldFact("a3", "entity_z", "role_event", "blocks", TimeSpan(0, 4, "A"), referring_cues=["navy_vest"]),
            WorldFact("b1", "entity_x", "action", ans, TimeSpan(20, 28, "B"), referring_cues=[cue_b_weak]),
            WorldFact("b2", "entity_y", "action", rng.choice(distractors), TimeSpan(20, 28, "B"), referring_cues=["later"]),
            WorldFact("b3", "entity_z", "action", rng.choice(distractors), TimeSpan(20, 28, "B"), referring_cues=["later"]),
        ]
        referring = cue_a
    elif kind == "role_reversal":
        # Property on B for entity_y; cue identifies y on A
        facts = [
            WorldFact("a1", "entity_y", "role_event", "speaks", TimeSpan(0, 4, "A"), referring_cues=[cue_a]),
            WorldFact("a2", "entity_x", "role_event", "listens", TimeSpan(0, 4, "A"), referring_cues=["maroon_coat"]),
            WorldFact("b1", "entity_y", "action", ans, TimeSpan(20, 28, "B"), referring_cues=[cue_b_weak]),
            WorldFact("b2", "entity_x", "action", rng.choice(distractors), TimeSpan(20, 28, "B"), referring_cues=["later"]),
        ]
        entities.pop("entity_z", None)
        referring = cue_a
    elif kind == "missing_evidence":
        # B missing the target property — should fail AB
        facts = [
            WorldFact("a1", "entity_x", "role_event", "enters", TimeSpan(0, 4, "A"), referring_cues=[cue_a]),
            WorldFact("a2", "entity_y", "role_event", "waits", TimeSpan(0, 4, "A"), referring_cues=["maroon_coat"]),
            WorldFact("b1", "entity_x", "location", "doorway", TimeSpan(20, 28, "B"), referring_cues=[cue_b_weak]),
            WorldFact("b2", "entity_y", "action", rng.choice(distractors), TimeSpan(20, 28, "B"), referring_cues=["later"]),
        ]
        entities.pop("entity_z", None)
        referring = cue_a
        ans = "UNOBSERVABLE"
    else:  # b_only_shortcut
        facts = [
            WorldFact("a1", "entity_x", "role_event", "enters", TimeSpan(0, 4, "A"), referring_cues=["maroon_coat"]),
            WorldFact("a2", "entity_y", "role_event", "waits", TimeSpan(0, 4, "A"), referring_cues=["navy_vest"]),
            WorldFact(
                "b1",
                "entity_x",
                "action",
                ans,
                TimeSpan(20, 28, "B"),
                referring_cues=["unique_b_cue", cue_a],
            ),
            WorldFact("b2", "entity_y", "action", rng.choice(distractors), TimeSpan(20, 28, "B"), referring_cues=["later"]),
        ]
        entities.pop("entity_z", None)
        referring = "unique_b_cue"
    return SimulatedWorld(facts=facts, entities=entities), referring, "action" if kind != "missing_evidence" else "action", ans


def build_independent_scenario_suite(n: int = 24, seed: int = 900) -> list[BindTask]:
    rng = random.Random(seed)
    kinds = ["dual_necessary", "dual_necessary", "role_reversal", "b_only_shortcut", "missing_evidence"]
    tasks: list[BindTask] = []
    for i in range(n):
        kind = kinds[i % len(kinds)]
        world, referring, prop, ans = _independent_world(rng, kind=kind)
        # Map missing_evidence to dual_necessary kind label for reporting but expect fail
        label = kind if kind != "role_reversal" else "dual_necessary"
        if kind == "missing_evidence":
            label = "missing_evidence"
        tasks.append(
            BindTask(
                task_id=f"ind_{kind}_{i}",
                kind=label if label != "role_reversal" else "dual_necessary",
                referring_a_cue=referring,
                property_name=prop,
                answer=ans,
                split="independent",
                world=world,
                seed=seed + i,
            )
        )
    return tasks


def run_independent_scenario_eval(n: int = 24, seed: int = 900) -> dict[str, Any]:
    tasks = build_independent_scenario_suite(n=n, seed=seed)
    strong = {
        **default_genome(),
        "recovery_strategy": "rebind_from_a",
        "bind_score_threshold": 0.25,
        "search_budget": 6,
    }
    weak = {
        **default_genome(),
        "recovery_strategy": "none",
        "bind_score_threshold": 0.45,
        "search_budget": 4,
    }
    matched = {
        **default_genome(),
        "recovery_strategy": "none",
        "bind_score_threshold": 0.25,
        "search_budget": 6,
    }

    def run_arm(name: str, g: dict[str, Any]) -> dict[str, Any]:
        rows = []
        for t in tasks:
            if t.kind == "missing_evidence":
                # Expect failure to answer gold UNOBSERVABLE via action query
                tr = instrument_bind_trace(g, t)
                rows.append(
                    {
                        "task_id": t.task_id,
                        "kind": t.kind,
                        "semantic": False,  # cannot correctly observe missing action
                        "pair_correct_at_bind": tr["pair_correct_at_bind"],
                        "top1": tr["top1_is_gold"],
                        "failure_axis": tr["failure_axis"],
                        "bind_ok": tr["bind_ok"],
                    }
                )
                continue
            # reuse evaluate_necessity path via evaluate_mode single-task
            from .binding_loop import run_bind_task

            r = run_bind_task(g, t, mode="program_selection")
            tr = instrument_bind_trace(g, t)
            rows.append(
                {
                    "task_id": t.task_id,
                    "kind": t.kind,
                    "semantic": r["semantic"],
                    "pair_correct_at_bind": r["pair_correct_at_bind"],
                    "top1": r["pair_accuracy_top1"],
                    "failure_axis": tr["failure_axis"],
                    "b_only": r["b_only"],
                    "necessary": r["necessary"],
                }
            )
        dual = [r for r in rows if r["kind"] == "dual_necessary"]
        short = [r for r in rows if r["kind"] == "b_only_shortcut"]
        miss = [r for r in rows if r["kind"] == "missing_evidence"]
        return {
            "arm": name,
            "n": len(rows),
            "acc": sum(1 for r in rows if r.get("semantic")) / max(1, len(rows)),
            "dual_acc": sum(1 for r in dual if r.get("semantic")) / max(1, len(dual)),
            "shortcut_b_detect": sum(1 for r in short if r.get("b_only")) / max(1, len(short)),
            "pair_bind": sum(1 for r in rows if r.get("pair_correct_at_bind")) / max(1, len(rows)),
            "missing_should_not_answer": sum(1 for r in miss if not r.get("semantic")) / max(1, len(miss)),
            "failure_axes": {ax: sum(1 for r in rows if r["failure_axis"] == ax) for ax in {r["failure_axis"] for r in rows}},
            "rows": rows,
        }

    return {
        "n_tasks": n,
        "seed": seed,
        "note": "Independent synthetic scenarios; disjoint from frozen 4-task suite. Not TECE optimization.",
        "arms": {
            "strong_fixed_rebind": run_arm("strong_fixed_rebind", strong),
            "weak_tece_like_init": run_arm("weak_tece_like_init", weak),
            "matched_static": run_arm("matched_static", matched),
        },
        "ok_for_expensive_rsi": False,
    }


def run_full_diagnostics(out_dir: str) -> dict[str, Any]:
    import os

    os.makedirs(out_dir, exist_ok=True)
    tax = collect_failure_taxonomy()
    parity = matched_budget_ablation(n_seeds=10, base_seed=700)
    indep = run_independent_scenario_eval(n=24, seed=900)
    payload = {
        "failure_taxonomy": tax,
        "matched_budget_parity": parity,
        "independent_scenarios": indep,
        "ok_for_expensive_rsi": False,
        "experiment_label": "binding_policy_evolution_only",
    }
    with open(os.path.join(out_dir, "bind_failure_taxonomy.json"), "w") as f:
        json.dump(tax, f, indent=2)
    with open(os.path.join(out_dir, "matched_budget_parity.json"), "w") as f:
        json.dump(parity, f, indent=2)
    with open(os.path.join(out_dir, "independent_scenario_eval.json"), "w") as f:
        json.dump(indep, f, indent=2)
    return payload
