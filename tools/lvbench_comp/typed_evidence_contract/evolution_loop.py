"""Evolver closed loop with structural leave-out and matched-budget controls.

Synthetic results validate mechanism design only — not real video RSI gains.

Important protocol changes vs prior prototype:
- Unseen leave-out is by *executed program graph hash*, not text signature labels.
- Train / Dev / Test: mutate on train, select on dev, evaluate test once.
- Matched mutation space across Random / Vanilla / TECE (Vanilla no longer budget-only).
- run_task respects genome op_order_template when present; otherwise schema program.
"""

from __future__ import annotations

import math
import random
import statistics
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .contracts import EntityCandidate, OperationName, OperationRequest, TimeSpan
from .evidence_graph import EvidenceDependencyGraph
from .executor import SimulatedWorld, TypedEvidenceExecutor, WorldFact, default_genome
from .evolver import ALLOWED_MUTATION_KEYS, EvolutionGenome, EvolverWorkspace
from .necessity import evaluate_necessity
from .noisy_obs import ObservationNoise, make_family_worlds, project_observations
from .program_schema import (
    SCHEMA_AV_REID_THEN_QUERY,
    SCHEMA_FORWARD_PERSON_ACTION,
    SCHEMA_FORWARD_PERSON_LOCATION,
    SCHEMA_REVERSE_EVENT_TO_PRIOR_ACTION,
    ProgramSchema,
    assert_structural_leave_out,
)


@dataclass
class SynthTask:
    task_id: str
    signature: str  # human label only — NOT used for leave-out
    schema: ProgramSchema
    referring_expression: str
    property_name: str
    answer: Any
    world: SimulatedWorld
    split: str  # train | dev | test
    family: str = "meeting_jacket"
    needs_recovery: bool = False
    noise: ObservationNoise | None = None
    # Explicit: prior 1.00/1.00 tasks that only differ by label are flagged.
    legacy_label_only_unseen: bool = False

    @property
    def graph_hash(self) -> str:
        return self.schema.graph_hash()

    @property
    def held_out(self) -> bool:
        return self.split == "test"


def _world_pair(
    answer_x: str = "removes_jacket",
    answer_y: str = "waves_hand",
    *,
    ambiguous_alias: bool = False,
    location_x: str = "stage_left",
) -> SimulatedWorld:
    aliases_x = ["speaker_a", "speaker"] if ambiguous_alias else ["speaker_a"]
    aliases_y = ["speaker_b", "speaker"] if ambiguous_alias else ["speaker_b"]
    entities = {
        "entity_x": EntityCandidate("entity_x", "the first speaker", aliases=aliases_x, confidence=0.9),
        "entity_y": EntityCandidate("entity_y", "the second speaker", aliases=aliases_y, confidence=0.9),
    }
    facts = [
        WorldFact("a1", "entity_x", "role_event", "speaks_first", TimeSpan(0, 5, "A"), referring_cues=["first speaker", "opens the meeting"]),
        WorldFact("a2", "entity_y", "role_event", "speaks_second", TimeSpan(0, 5, "A"), referring_cues=["second speaker"]),
        WorldFact("b1", "entity_x", "action", answer_x, TimeSpan(25, 30, "B"), referring_cues=["later action"]),
        WorldFact("b2", "entity_y", "action", answer_y, TimeSpan(25, 30, "B"), referring_cues=["later action other"]),
        WorldFact("l1", "entity_x", "location", location_x, TimeSpan(25, 30, "B"), referring_cues=["location"]),
        WorldFact("l2", "entity_y", "location", "stage_right", TimeSpan(25, 30, "B"), referring_cues=["location other"]),
    ]
    return SimulatedWorld(facts=facts, entities=entities)


def build_structural_split() -> dict[str, list[SynthTask]]:
    """Train/dev use forward schemas; test holds out reverse + AV schemas."""
    families = make_family_worlds()
    train = [
        SynthTask(
            "train_fwd_action_clear",
            "identify_person + describe_action",
            SCHEMA_FORWARD_PERSON_ACTION,
            "first speaker",
            "action",
            "removes_jacket",
            families["meeting_jacket"],
            "train",
            family="meeting_jacket",
        ),
        SynthTask(
            "train_fwd_location_clear",
            "identify_person + describe_location",
            SCHEMA_FORWARD_PERSON_LOCATION,
            "second speaker",
            "location",
            "stage_right",
            families["meeting_jacket"],
            "train",
            family="meeting_jacket",
        ),
        SynthTask(
            "train_fwd_action_amb",
            "identify_person + describe_action",
            SCHEMA_FORWARD_PERSON_ACTION,
            "speaker",
            "action",
            "points_chart",
            _world_pair("points_chart", "nods", ambiguous_alias=True),
            "train",
            family="lab_point",
            needs_recovery=True,
        ),
    ]
    dev = [
        SynthTask(
            "dev_fwd_action",
            "identify_person + describe_action",
            SCHEMA_FORWARD_PERSON_ACTION,
            "speaker",
            "action",
            "takes_bow",
            _world_pair("takes_bow", "claps", ambiguous_alias=True),
            "dev",
            family="concert_bow",
            needs_recovery=True,
        ),
        SynthTask(
            "dev_fwd_location",
            "identify_person + describe_location",
            SCHEMA_FORWARD_PERSON_LOCATION,
            "first speaker",
            "location",
            "orchestra_pit",
            families["concert_bow"],
            "dev",
            family="concert_bow",
        ),
    ]
    # True structural Unseen: reverse temporal DAG + AV DAG (different graph hashes)
    test = [
        SynthTask(
            "test_reverse_prior_action",
            "reverse_event_to_prior_action",
            SCHEMA_REVERSE_EVENT_TO_PRIOR_ACTION,
            "speaker",
            "role_event",
            "speaks_first",
            _world_pair("takes_bow", "claps", ambiguous_alias=True),
            "test",
            family="concert_bow",
            needs_recovery=True,
        ),
        SynthTask(
            "test_av_reid",
            "av_reid_then_query",
            SCHEMA_AV_REID_THEN_QUERY,
            "bark source",
            "action",
            "fetches_stick",
            families["av_bark"],
            "test",
            family="av_bark",
            noise=ObservationNoise(strip_audio_cues=False),
        ),
        # Noisy perception family on reverse structure
        SynthTask(
            "test_reverse_noisy_lookalike",
            "reverse_event_to_prior_action",
            SCHEMA_REVERSE_EVENT_TO_PRIOR_ACTION,
            "speaker",
            "role_event",
            "speaks_first",
            _world_pair("removes_jacket", "waves_hand", ambiguous_alias=True),
            "test",
            family="meeting_jacket",
            needs_recovery=True,
            noise=ObservationNoise(lookalike_alias="the first speaker", misleading_caption="second speaker opens the meeting"),
        ),
    ]
    return {"train": train, "dev": dev, "test": test}


def build_task_split() -> tuple[list[SynthTask], list[SynthTask]]:
    """Back-compat: train+dev as 'seen', test as 'unseen'."""
    splits = build_structural_split()
    return splits["train"] + splits["dev"], splits["test"]


def split_witness(splits: dict[str, list[SynthTask]] | None = None) -> dict[str, Any]:
    splits = splits or build_structural_split()
    train_schemas = [t.schema for t in splits["train"] + splits["dev"]]
    test_schemas = [t.schema for t in splits["test"]]
    # Unique by schema_id
    uniq_train = {s.schema_id: s for s in train_schemas}
    uniq_test = {s.schema_id: s for s in test_schemas}
    leave = assert_structural_leave_out(list(uniq_train.values()), list(uniq_test.values()))
    # Exhaustive leakage: any test task graph hash in train/dev?
    train_hashes = {t.graph_hash for t in splits["train"] + splits["dev"]}
    test_hashes = {t.graph_hash for t in splits["test"]}
    # Also check legacy label-only trap
    legacy = [
        {
            "warning": "Prior prototype used same property_name=action and same world DAG for Seen/Unseen labels",
            "status": "FIXED_IN_STRUCTURAL_SPLIT",
        }
    ]
    return {
        "leave_out_ok": leave["ok"] and not (train_hashes & test_hashes),
        "structural_check": leave,
        "train_dev_graph_hashes": sorted(train_hashes),
        "test_graph_hashes": sorted(test_hashes),
        "intersecting_hashes": sorted(train_hashes & test_hashes),
        "tasks": {
            split: [
                {
                    "task_id": t.task_id,
                    "signature_label": t.signature,
                    "schema_id": t.schema.schema_id,
                    "graph_hash": t.graph_hash,
                    "direction": t.schema.direction,
                    "modalities": list(t.schema.modalities),
                    "property_name": t.property_name,
                    "family": t.family,
                }
                for t in tasks
            ]
            for split, tasks in splits.items()
        },
        "legacy_warnings": legacy,
    }


SHARED_MUTATION_POOL = [
    {"search_budget": 3},
    {"search_budget": 6},
    {"search_budget": 8},
    {"recovery_strategy": "none"},
    {"recovery_strategy": "relocate_then_resolve"},
    {"recovery_strategy": "investigate_conflict"},
    {"recovery_strategy": "rebind_from_a"},
    {"verify_requires_dual_evidence": True},
    {"query_requires_bound_entity": True},
    {"disambiguation_cue": "opens the meeting"},
    {"disambiguation_cue": "first speaker"},
    {"fallback_referring_expression": "first speaker"},
    {"fallback_referring_expression": None},
    {
        "op_order_template": [
            "resolve_reference",
            "track_identity",
            "query_property",
            "verify_answer",
        ]
    },
    {
        "op_order_template": [
            "locate_event",
            "resolve_reference",
            "track_identity",
            "query_property",
            "verify_answer",
        ]
    },
]

MUTATION_POOL = SHARED_MUTATION_POOL  # alias


def mutate_random(genome: EvolutionGenome, rng: random.Random) -> dict[str, Any]:
    patch = deepcopy(rng.choice(SHARED_MUTATION_POOL))
    return {k: v for k, v in patch.items() if k in ALLOWED_MUTATION_KEYS}


def _program_for_task(genome: dict[str, Any], task: SynthTask) -> list[dict[str, Any]]:
    """Prefer genome op_order_template; else compile from schema."""
    template = genome.get("op_order_template")
    if template:
        program = []
        for op in template:
            if op == "locate_event":
                cue = genome.get("disambiguation_cue") or task.referring_expression
                program.append({"op": op, "inputs": {"cue": cue}})
            elif op == "resolve_reference":
                program.append({"op": op, "inputs": {"referring_expression": task.referring_expression}})
            elif op == "track_identity":
                span = {"start_s": 25, "end_s": 30} if task.schema.direction == "forward" else {"start_s": 0, "end_s": 5}
                if task.schema.direction == "reverse":
                    # After binding on late event, track to early span
                    span = {"start_s": 0, "end_s": 5}
                program.append({"op": op, "inputs": {"target_span": span}})
            elif op == "query_property":
                program.append({"op": op, "inputs": {"property_name": task.property_name}})
            elif op == "verify_answer":
                program.append(
                    {
                        "op": op,
                        "inputs": {
                            "interval_a": {"start_s": 0.0, "end_s": 5.0},
                            "interval_b": {"start_s": 25.0, "end_s": 30.0},
                        },
                    }
                )
        return program
    return task.schema.compile_program(referring=task.referring_expression, property_name=task.property_name)


def run_task(genome: dict[str, Any], task: SynthTask) -> dict[str, Any]:
    oracle = deepcopy(task.world)
    agent_world, leakage = project_observations(oracle, task.noise)
    g = deepcopy(genome)
    # Disable evidence-graph verify if ablated
    use_graph = g.pop("_use_evidence_graph", True)
    use_recovery = g.get("recovery_strategy", "none")
    if g.get("_disable_recovery"):
        g["recovery_strategy"] = "none"

    ex = TypedEvidenceExecutor(agent_world, g)
    program = _program_for_task(g, task)
    results = []
    pred = None
    for step in program:
        op = OperationName(step["op"])
        inputs = dict(step.get("inputs") or {})
        if op == OperationName.VERIFY_ANSWER:
            inputs["answer"] = pred
            if not use_graph:
                # Ablation: accept dual timestamps without graph (legacy weak verify)
                inputs["evidence_graph"] = {
                    "nodes": [
                        {"evidence_id": "A0", "entity_id": "entity_x", "interval_label": "A", "supports_answer": False},
                        {"evidence_id": "B0", "entity_id": "entity_x", "interval_label": "B", "supports_answer": True},
                    ],
                    "bindings": [
                        {"referring_expression": task.referring_expression, "entity_id": "entity_x", "from_evidence_id": "A0"}
                    ],
                }
        r = ex.run(OperationRequest(op, inputs))
        results.append(r)
        if op == OperationName.QUERY_PROPERTY and r.ok:
            pred = r.outputs.get("property_value")
        if op == OperationName.LOCATE_EVENT and r.ok and ex.memory.bound_entity is None:
            # Schema may locate before resolve; do not read oracle ids here.
            pass

    verify = next((r for r in results if r.op == OperationName.VERIFY_ANSWER), None)
    credit = verify.outputs.get("composition_credit") if verify else None
    evidence_path_valid = bool(verify and verify.outputs.get("composition_credit") in {
        "STRONG_COMPOSITION",
        "PATH_VALID_NECESSITY_UNPROVEN",
    })
    # Prefer explicit flag from graph if present
    if verify and "reasons" in (verify.outputs or {}):
        # re-read from message not available; use credit
        pass

    # Necessity via masked oracle world (evaluation-only), same question
    nec = evaluate_necessity(
        oracle,
        referring=task.referring_expression,
        property_name=task.property_name,
        gold_answer=task.answer,
        genome=g,
        evidence_path_valid=evidence_path_valid,
        ab_pred=pred,
    )

    # Recovery oracle-leak heuristic: rebound entity_id matches a WorldFact.entity_id without resolve ok
    resolve = next((r for r in results if r.op == OperationName.RESOLVE_REFERENCE), None)
    oracle_bind_leak = False
    if ex.memory.recovery_stack and ex.memory.bound_entity is not None:
        if resolve is not None and not resolve.ok:
            # Bound via locate→fact.entity_id — privileged structure
            oracle_bind_leak = any(r.get("rebound_entity") for r in ex.memory.recovery_stack)
            leakage["used_oracle_entity_id_directly"] = oracle_bind_leak

    semantic = nec.semantic_answer_correct
    # Primary success for evolution: semantic on train/dev; report all three on test
    correct_strong = semantic and nec.composition_necessary and evidence_path_valid

    return {
        "task_id": task.task_id,
        "signature": task.signature,
        "schema_id": task.schema.schema_id,
        "graph_hash": task.graph_hash,
        "split": task.split,
        "family": task.family,
        "held_out": task.held_out,
        "pred": pred,
        "gold": task.answer,
        "credit": credit,
        "evidence_path_valid": nec.evidence_path_valid,
        "semantic_answer_correct": nec.semantic_answer_correct,
        "composition_necessary": nec.composition_necessary,
        "a_only_solves": nec.a_only_solves,
        "b_only_solves": nec.b_only_solves,
        "correct_strong": correct_strong,
        "budget_left": ex.budget,
        "recovery": list(ex.memory.recovery_stack),
        "calls": len(ex.memory.tool_calls),
        "bound": ex.memory.bound_entity.entity_id if ex.memory.bound_entity else None,
        "leakage": leakage,
        "oracle_bind_via_recovery": oracle_bind_leak,
        "use_recovery": use_recovery,
    }


def evaluate(genome: dict[str, Any], tasks: list[SynthTask], *, metric: str = "semantic") -> dict[str, Any]:
    rows = [run_task(genome, t) for t in tasks]
    n = max(1, len(rows))
    if metric == "strict_composition":
        acc = sum(1 for r in rows if r["correct_strong"]) / n
    else:
        acc = sum(1 for r in rows if r["semantic_answer_correct"]) / n
    cost = sum(r["calls"] for r in rows) / n
    return {
        "accuracy": acc,
        "strict_composition_rate": sum(1 for r in rows if r["correct_strong"]) / n,
        "evidence_path_rate": sum(1 for r in rows if r["evidence_path_valid"]) / n,
        "necessity_rate": sum(1 for r in rows if r["composition_necessary"]) / n,
        "avg_calls": cost,
        "oracle_leak_rate": sum(1 for r in rows if r["oracle_bind_via_recovery"]) / n,
        "rows": rows,
    }


def _initial_genome(mode: str) -> EvolutionGenome:
    base = {**default_genome(), "recovery_strategy": "none", "search_budget": 4}
    if mode == "fixed_rebind":
        # Non-evolving strong baseline: fixed recovery policy
        base["recovery_strategy"] = "rebind_from_a"
        base["disambiguation_cue"] = "opens the meeting"
        base["search_budget"] = 6
    return EvolutionGenome(base)


def evolve(
    *,
    train_tasks: list[SynthTask],
    dev_tasks: list[SynthTask],
    test_tasks: list[SynthTask],
    generations: int = 8,
    population: int = 6,
    seed: int = 0,
    mode: str = "tece",
) -> dict[str, Any]:
    """Modes with matched mutation access unless noted.

    fixed | fixed_rebind | random | vanilla | tece |
    tece_minus_graph | tece_minus_recovery | tece_minus_verify
    """
    rng = random.Random(seed)
    train_hashes = {t.graph_hash for t in train_tasks + dev_tasks}
    for t in test_tasks:
        if t.graph_hash in train_hashes:
            raise RuntimeError(f"structural leave-out violated: {t.task_id} hash={t.graph_hash}")

    initial = _initial_genome(mode if mode != "tece_minus_recovery" else "fixed")
    if mode == "tece_minus_recovery":
        initial.params["recovery_strategy"] = "none"
        initial.params["_disable_recovery"] = True
    if mode == "tece_minus_graph":
        initial.params["_use_evidence_graph"] = False
    if mode == "tece_minus_verify":
        initial.params["verify_requires_dual_evidence"] = False
        initial.params["_use_evidence_graph"] = False

    history: list[dict[str, Any]] = []
    best = deepcopy(initial)

    non_evolving = mode in {"fixed", "fixed_rebind"}
    if non_evolving:
        return {
            "mode": mode,
            "best_genome": best.params,
            "train": evaluate(best.params, train_tasks),
            "dev": evaluate(best.params, dev_tasks),
            "test_once": evaluate(best.params, test_tasks),
            "history": [],
            "strategy_changed": False,
            "selection_split": "none",
            "note": "Synthetic only; not a real-video RSI claim.",
        }

    for gen in range(generations):
        candidates = [deepcopy(best)]
        for _ in range(population - 1):
            g = deepcopy(best)
            # Matched mutation space: random, vanilla, tece all draw from SHARED_MUTATION_POOL
            patch = mutate_random(g, rng)
            if mode.startswith("tece") and rng.random() < 0.5:
                # TECE-intended bias: prefer recovery/disambiguation mutations (documented)
                patch = {
                    "recovery_strategy": rng.choice(
                        ["none", "relocate_then_resolve", "investigate_conflict", "rebind_from_a"]
                    )
                }
                if rng.random() < 0.5:
                    patch["fallback_referring_expression"] = rng.choice([None, "first speaker"])
            if mode == "tece_minus_recovery":
                patch["recovery_strategy"] = "none"
                patch["_disable_recovery"] = True
            ws = EvolverWorkspace(g)
            # Allow internal ablation flags through propose by merging after
            decision = ws.propose({k: v for k, v in patch.items() if k in ALLOWED_MUTATION_KEYS})
            for k, v in patch.items():
                if k.startswith("_"):
                    g.params[k] = v
            if decision["accepted"] or any(k.startswith("_") for k in patch):
                candidates.append(g)

        scored = []
        for g in candidates:
            # Select on DEV only — never on test
            ev = evaluate(g.params, dev_tasks, metric="semantic")
            score = ev["accuracy"] - (0.02 * ev["avg_calls"] if mode.startswith("tece") else 0.0)
            scored.append((score, g, ev))
        scored.sort(key=lambda x: x[0], reverse=True)
        winner_score, winner, winner_ev = scored[0]
        changed = winner.params != best.params
        history.append(
            {
                "generation": gen,
                "best_score": winner_score,
                "dev_accuracy": winner_ev["accuracy"],
                "avg_calls": winner_ev["avg_calls"],
                "genome": {k: v for k, v in winner.params.items() if not str(k).startswith("_")},
                "changed": changed,
            }
        )
        best = winner

    # Test evaluated once after selection
    return {
        "mode": mode,
        "best_genome": {k: v for k, v in best.params.items() if not str(k).startswith("_")},
        "train": evaluate(best.params, train_tasks),
        "dev": evaluate(best.params, dev_tasks),
        "test_once": evaluate(best.params, test_tasks),
        "history": history,
        "strategy_changed": any(h["changed"] for h in history),
        "selection_split": "dev",
        "note": "Synthetic only; not a real-video RSI claim. Test evaluated once.",
    }


def run_ablation_suite(seed: int = 7) -> dict[str, Any]:
    """Legacy entry: structural split, single seed, matched arms."""
    splits = build_structural_split()
    arms = (
        "fixed",
        "fixed_rebind",
        "random",
        "vanilla",
        "tece",
        "tece_minus_graph",
        "tece_minus_recovery",
        "tece_minus_verify",
    )
    return {
        arm: evolve(
            train_tasks=splits["train"],
            dev_tasks=splits["dev"],
            test_tasks=splits["test"],
            seed=seed,
            mode=arm,
        )
        for arm in arms
    }


def _ci95(vals: list[float]) -> dict[str, float]:
    if not vals:
        return {"mean": 0.0, "std": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "n": 0}
    m = statistics.mean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    # Normal approx
    half = 1.96 * sd / math.sqrt(len(vals)) if len(vals) > 1 else 0.0
    return {"mean": m, "std": sd, "ci95_low": m - half, "ci95_high": m + half, "n": len(vals), "median": statistics.median(vals)}


def run_multiseed_stress(
    n_seeds: int = 20,
    base_seed: int = 100,
    generations: int = 6,
    population: int = 5,
) -> dict[str, Any]:
    splits = build_structural_split()
    witness = split_witness(splits)
    arms = ["fixed", "fixed_rebind", "random", "vanilla", "tece", "tece_minus_recovery"]
    per_arm: dict[str, list[dict[str, Any]]] = {a: [] for a in arms}
    failure_cases: list[dict[str, Any]] = []

    for i in range(n_seeds):
        seed = base_seed + i
        for arm in arms:
            res = evolve(
                train_tasks=splits["train"],
                dev_tasks=splits["dev"],
                test_tasks=splits["test"],
                seed=seed,
                mode=arm,
                generations=generations,
                population=population,
            )
            test = res["test_once"]
            per_arm[arm].append(
                {
                    "seed": seed,
                    "dev_acc": res["dev"]["accuracy"],
                    "test_semantic": test["accuracy"],
                    "test_strict": test["strict_composition_rate"],
                    "test_necessity": test["necessity_rate"],
                    "test_path": test["evidence_path_rate"],
                    "oracle_leak": test["oracle_leak_rate"],
                    "avg_calls": test["avg_calls"],
                    "strategy_changed": res["strategy_changed"],
                    "best_recovery": res["best_genome"].get("recovery_strategy"),
                }
            )
            # Collect failure rows
            for row in test["rows"]:
                if not row["semantic_answer_correct"] or not row["composition_necessary"]:
                    failure_cases.append(
                        {
                            "seed": seed,
                            "arm": arm,
                            "task_id": row["task_id"],
                            "schema_id": row["schema_id"],
                            "family": row["family"],
                            "semantic": row["semantic_answer_correct"],
                            "necessary": row["composition_necessary"],
                            "path": row["evidence_path_valid"],
                            "a_only": row["a_only_solves"],
                            "b_only": row["b_only_solves"],
                            "pred": row["pred"],
                            "gold": row["gold"],
                            "oracle_leak": row["oracle_bind_via_recovery"],
                            "credit": row["credit"],
                        }
                    )

    summary = {}
    for arm, rows in per_arm.items():
        summary[arm] = {
            "test_semantic": _ci95([r["test_semantic"] for r in rows]),
            "test_strict_composition": _ci95([r["test_strict"] for r in rows]),
            "test_necessity": _ci95([r["test_necessity"] for r in rows]),
            "oracle_leak": _ci95([r["oracle_leak"] for r in rows]),
            "avg_calls": _ci95([r["avg_calls"] for r in rows]),
            "strategy_changed_rate": sum(1 for r in rows if r["strategy_changed"]) / max(1, len(rows)),
        }

    # Pareto sample: mean success vs mean cost for TECE vs fixed_rebind
    return {
        "n_seeds": n_seeds,
        "witness": witness,
        "summary": summary,
        "per_seed": per_arm,
        "failure_cases_sample": failure_cases[:80],
        "failure_count": len(failure_cases),
        "interpretation": (
            "Do NOT read any synthetic score as real-video RSI compositional generalization. "
            "If matched controls erase TECE advantage, that negative result is scientifically useful."
        ),
    }
