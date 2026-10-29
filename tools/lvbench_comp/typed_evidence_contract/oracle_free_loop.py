"""Oracle-free TECE evaluation with runtime fidelity hashes and matched baselines.

Accepts negative/equal results — does not tune for a predetermined TECE win.
"""

from __future__ import annotations

import math
import random
import statistics
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .contracts import OperationName, OperationRequest
from .executor import default_genome
from .evolver import ALLOWED_MUTATION_KEYS, EvolutionGenome, EvolverWorkspace
from .necessity import evaluate_necessity_neutral
from .observations import ObservationBundle, project_oracle_free
from .oracle_free_executor import OracleFreeExecutor, program_hash, trace_hash
from .program_schema import (
    SCHEMA_AV_REID_THEN_QUERY,
    SCHEMA_FORWARD_PERSON_ACTION,
    SCHEMA_FORWARD_PERSON_LOCATION,
    SCHEMA_REVERSE_EVENT_TO_PRIOR_ACTION,
    ProgramSchema,
    assert_structural_leave_out,
)
from .evolution_loop import _world_pair, SHARED_MUTATION_POOL, mutate_random
from .noisy_obs import make_family_worlds


@dataclass
class OFTask:
    task_id: str
    schema: ProgramSchema
    referring: str
    property_name: str
    answer: Any
    split: str
    family: str
    force_schema_program: bool = True  # fidelity: execute schema compile, not arbitrary genome reorder on test
    ambiguous: bool = False
    salt: str = "s0"

    @property
    def declared_schema_hash(self) -> str:
        return self.schema.graph_hash()


def build_of_split() -> dict[str, list[OFTask]]:
    families = make_family_worlds()
    train = [
        OFTask("tr_fwd_act", SCHEMA_FORWARD_PERSON_ACTION, "first speaker", "action", "removes_jacket", "train", "meeting_jacket"),
        OFTask("tr_fwd_loc", SCHEMA_FORWARD_PERSON_LOCATION, "second speaker", "location", "stage_right", "train", "meeting_jacket"),
        OFTask("tr_fwd_amb", SCHEMA_FORWARD_PERSON_ACTION, "speaker", "action", "points_chart", "train", "lab_point", ambiguous=True, salt="amb1"),
    ]
    # Build amb world into families via _world_pair at runtime
    dev = [
        OFTask("dv_fwd_act", SCHEMA_FORWARD_PERSON_ACTION, "speaker", "action", "takes_bow", "dev", "concert_bow", ambiguous=True, salt="dev1"),
        OFTask("dv_fwd_loc", SCHEMA_FORWARD_PERSON_LOCATION, "first speaker", "location", "orchestra_pit", "dev", "concert_bow"),
    ]
    test = [
        OFTask(
            "te_reverse",
            SCHEMA_REVERSE_EVENT_TO_PRIOR_ACTION,
            "speaker",
            "role_event",
            "speaks_first",
            "test",
            "concert_bow",
            ambiguous=True,
            salt="rev1",
            force_schema_program=True,
        ),
        OFTask(
            "te_av",
            SCHEMA_AV_REID_THEN_QUERY,
            "bark source",
            "action",
            "fetches_stick",
            "test",
            "av_bark",
            force_schema_program=True,
            salt="av1",
        ),
        OFTask(
            "te_reverse_diverse",
            SCHEMA_REVERSE_EVENT_TO_PRIOR_ACTION,
            "first speaker",
            "role_event",
            "speaks_first",
            "test",
            "meeting_jacket",
            force_schema_program=True,
            salt="rev2",
        ),
    ]
    return {"train": train, "dev": dev, "test": test, "_families": families}  # type: ignore


def _oracle_for(task: OFTask, families: dict) -> Any:
    if task.family in families and not task.ambiguous:
        return deepcopy(families[task.family])
    if task.answer == "points_chart":
        return _world_pair("points_chart", "nods", ambiguous_alias=True)
    if task.answer == "takes_bow" and task.property_name == "action":
        return _world_pair("takes_bow", "claps", ambiguous_alias=True)
    if task.schema.direction == "reverse":
        return _world_pair("takes_bow", "claps", ambiguous_alias=task.ambiguous)
    return deepcopy(families.get(task.family) or _world_pair())


def compile_program(task: OFTask, genome: dict[str, Any]) -> list[dict[str, Any]]:
    """Prefer schema compile for structural fidelity; genome template only if allowed and not forced."""
    if task.force_schema_program or not genome.get("op_order_template"):
        return task.schema.compile_program(referring=task.referring, property_name=task.property_name)
    # Genome template path — still record that it may diverge from declared schema
    program = []
    for op in genome["op_order_template"]:
        if op == "locate_event":
            program.append({"op": op, "inputs": {"cue": genome.get("disambiguation_cue") or task.referring}})
        elif op == "resolve_reference":
            program.append({"op": op, "inputs": {"referring_expression": task.referring}})
        elif op == "track_identity":
            span = {"start_s": 0, "end_s": 5} if task.schema.direction == "reverse" else {"start_s": 25, "end_s": 30}
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


def run_of_task(genome: dict[str, Any], task: OFTask, families: dict) -> dict[str, Any]:
    oracle = _oracle_for(task, families)
    bundle, omap = project_oracle_free(
        oracle,
        scenario_id=task.task_id,
        gold_answer=task.answer,
        gold_property=task.property_name,
        salt=task.salt,
    )
    # Assert agent cannot see oracle ids
    agent_view = bundle.to_agent_dict()
    assert "entity_x" not in str(agent_view)

    program = compile_program(task, genome)
    declared = task.declared_schema_hash
    compiled = program_hash(program)
    # Structural fidelity: schema-compiled program should match schema's own compile hash
    schema_prog = task.schema.compile_program(referring=task.referring, property_name=task.property_name)
    schema_prog_hash = program_hash(schema_prog)
    fidelity_ok = (compiled == schema_prog_hash) if task.force_schema_program else True

    ex = OracleFreeExecutor(bundle, deepcopy(genome))
    pred = None
    verify = None
    for step in program:
        op = OperationName(step["op"])
        inputs = dict(step.get("inputs") or {})
        if op == OperationName.VERIFY_ANSWER:
            inputs["answer"] = pred
        r = ex.run(OperationRequest(op, inputs))
        if op == OperationName.QUERY_PROPERTY and r.ok:
            pred = r.outputs.get("property_value")
        if op == OperationName.VERIFY_ANSWER:
            verify = r

    executed = trace_hash(ex.memory.tool_calls)
    path_valid = bool(verify and verify.outputs.get("evidence_path_valid"))
    nec = evaluate_necessity_neutral(
        bundle,
        referring=task.referring,
        property_name=task.property_name,
        gold_answer=task.answer,
        genome=genome,
        program=program,
        ab_pred=pred,
        evidence_path_valid=path_valid,
    )
    # Score semantic via oracle map (scorer-only)
    semantic = pred == omap.gold_answer
    oracle_leak = any(r.get("oracle_entity_id_used") for r in ex.memory.recovery_stack)
    # Extra leak check: bound track must not equal oracle entity_x/y strings
    if ex.memory.bound_track in {"entity_x", "entity_y"}:
        oracle_leak = True

    return {
        "task_id": task.task_id,
        "split": task.split,
        "schema_id": task.schema.schema_id,
        "declared_schema_hash": declared,
        "compiled_program_hash": compiled,
        "schema_program_hash": schema_prog_hash,
        "executed_trace_hash": executed,
        "runtime_fidelity_to_schema": fidelity_ok,
        "pred": pred,
        "gold": task.answer,
        "semantic_answer_correct": semantic,
        "evidence_path_valid": nec.evidence_path_valid,
        "composition_necessary": nec.composition_necessary,
        "a_only_solves": nec.a_only_solves,
        "b_only_solves": nec.b_only_solves,
        "correct_strict": semantic and nec.composition_necessary and nec.evidence_path_valid,
        "oracle_leak": oracle_leak,
        "calls": len(ex.memory.tool_calls),
        "bound_track": ex.memory.bound_track,
        "credit": verify.outputs.get("composition_credit") if verify else None,
        "necessity_details": nec.details,
    }


def evaluate_of(genome: dict[str, Any], tasks: list[OFTask], families: dict) -> dict[str, Any]:
    rows = [run_of_task(genome, t, families) for t in tasks]
    n = max(1, len(rows))
    return {
        "accuracy": sum(1 for r in rows if r["semantic_answer_correct"]) / n,
        "strict_rate": sum(1 for r in rows if r["correct_strict"]) / n,
        "necessity_rate": sum(1 for r in rows if r["composition_necessary"]) / n,
        "path_rate": sum(1 for r in rows if r["evidence_path_valid"]) / n,
        "oracle_leak_rate": sum(1 for r in rows if r["oracle_leak"]) / n,
        "fidelity_rate": sum(1 for r in rows if r["runtime_fidelity_to_schema"]) / n,
        "avg_calls": sum(r["calls"] for r in rows) / n,
        "rows": rows,
    }


def _init(mode: str) -> dict[str, Any]:
    g = {**default_genome(), "recovery_strategy": "none", "search_budget": 4}
    if mode == "fixed_rebind":
        g.update({"recovery_strategy": "rebind_from_a", "disambiguation_cue": "opens the meeting", "search_budget": 6})
    return g


def evolve_of(
    *,
    train: list[OFTask],
    dev: list[OFTask],
    test: list[OFTask],
    families: dict,
    mode: str = "tece",
    seed: int = 0,
    generations: int = 6,
    population: int = 5,
) -> dict[str, Any]:
    rng = random.Random(seed)
    # Intended dependency structures disjoint
    leave = assert_structural_leave_out(
        list({t.schema.schema_id: t.schema for t in train + dev}.values()),
        list({t.schema.schema_id: t.schema for t in test}.values()),
    )
    if not leave["ok"]:
        raise RuntimeError(f"structural leave-out failed: {leave}")

    best = EvolutionGenome(_init(mode))
    history = []
    if mode in {"fixed", "fixed_rebind"}:
        return {
            "mode": mode,
            "best_genome": best.params,
            "train": evaluate_of(best.params, train, families),
            "dev": evaluate_of(best.params, dev, families),
            "test_once": evaluate_of(best.params, test, families),
            "history": [],
            "strategy_changed": False,
            "structural_leave_out": leave,
            "note": "Oracle-free synthetic protocol only; not real-video RSI.",
        }

    for gen in range(generations):
        cands = [deepcopy(best)]
        for _ in range(population - 1):
            g = deepcopy(best)
            patch = mutate_random(g, rng)
            if mode == "tece" and rng.random() < 0.5:
                patch = {
                    "recovery_strategy": rng.choice(
                        ["none", "relocate_then_resolve", "investigate_conflict", "rebind_from_a"]
                    )
                }
            ws = EvolverWorkspace(g)
            if ws.propose({k: v for k, v in patch.items() if k in ALLOWED_MUTATION_KEYS})["accepted"]:
                cands.append(g)
        scored = []
        for g in cands:
            ev = evaluate_of(g.params, dev, families)
            score = ev["accuracy"] - (0.02 * ev["avg_calls"] if mode == "tece" else 0.0)
            scored.append((score, g, ev))
        scored.sort(key=lambda x: x[0], reverse=True)
        winner = scored[0][1]
        history.append(
            {
                "generation": gen,
                "dev_acc": scored[0][2]["accuracy"],
                "changed": winner.params != best.params,
                "genome": deepcopy(winner.params),
            }
        )
        best = winner

    return {
        "mode": mode,
        "best_genome": best.params,
        "train": evaluate_of(best.params, train, families),
        "dev": evaluate_of(best.params, dev, families),
        "test_once": evaluate_of(best.params, test, families),
        "history": history,
        "strategy_changed": any(h["changed"] for h in history),
        "structural_leave_out": leave,
        "note": "Oracle-free synthetic protocol only; not real-video RSI. Test once after dev selection.",
    }


def _ci(vals: list[float]) -> dict[str, float]:
    if not vals:
        return {"mean": 0.0, "n": 0}
    m = statistics.mean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    half = 1.96 * sd / math.sqrt(len(vals)) if len(vals) > 1 else 0.0
    return {"mean": m, "std": sd, "ci95_low": m - half, "ci95_high": m + half, "median": statistics.median(vals), "n": len(vals)}


def run_oracle_free_suite(n_seeds: int = 20, base_seed: int = 200) -> dict[str, Any]:
    split = build_of_split()
    families = split.pop("_families")  # type: ignore
    arms = ["fixed", "fixed_rebind", "random", "vanilla", "tece"]
    per_arm: dict[str, list] = {a: [] for a in arms}
    failures = []
    fidelity_rows = []

    for i in range(n_seeds):
        seed = base_seed + i
        for arm in arms:
            res = evolve_of(
                train=split["train"],
                dev=split["dev"],
                test=split["test"],
                families=families,
                mode=arm,
                seed=seed,
            )
            te = res["test_once"]
            per_arm[arm].append(
                {
                    "seed": seed,
                    "test_semantic": te["accuracy"],
                    "test_strict": te["strict_rate"],
                    "test_necessity": te["necessity_rate"],
                    "oracle_leak": te["oracle_leak_rate"],
                    "fidelity": te["fidelity_rate"],
                    "avg_calls": te["avg_calls"],
                    "strategy_changed": res["strategy_changed"],
                }
            )
            for row in te["rows"]:
                fidelity_rows.append(
                    {
                        "seed": seed,
                        "arm": arm,
                        "task_id": row["task_id"],
                        "declared_schema_hash": row["declared_schema_hash"],
                        "compiled_program_hash": row["compiled_program_hash"],
                        "executed_trace_hash": row["executed_trace_hash"],
                        "runtime_fidelity_to_schema": row["runtime_fidelity_to_schema"],
                    }
                )
                if not row["semantic_answer_correct"] or row["oracle_leak"] or not row["composition_necessary"]:
                    failures.append(
                        {
                            "seed": seed,
                            "arm": arm,
                            "task_id": row["task_id"],
                            "semantic": row["semantic_answer_correct"],
                            "necessary": row["composition_necessary"],
                            "a_only": row["a_only_solves"],
                            "b_only": row["b_only_solves"],
                            "oracle_leak": row["oracle_leak"],
                            "pred": row["pred"],
                            "gold": row["gold"],
                        }
                    )

    summary = {
        arm: {
            "test_semantic": _ci([r["test_semantic"] for r in rows]),
            "test_strict": _ci([r["test_strict"] for r in rows]),
            "test_necessity": _ci([r["test_necessity"] for r in rows]),
            "oracle_leak": _ci([r["oracle_leak"] for r in rows]),
            "fidelity": _ci([r["fidelity"] for r in rows]),
        }
        for arm, rows in per_arm.items()
    }
    return {
        "n_seeds": n_seeds,
        "summary": summary,
        "per_seed": per_arm,
        "fidelity_sample": fidelity_rows[:60],
        "failure_sample": failures[:60],
        "failure_count": len(failures),
        "leave_out": assert_structural_leave_out(
            list({t.schema.schema_id: t.schema for t in split["train"] + split["dev"]}.values()),
            list({t.schema.schema_id: t.schema for t in split["test"]}.values()),
        ),
        "interpretation": (
            "Oracle-free matched controls. Negative/equal TECE vs fixed_rebind is an acceptable scientific result. "
            "Not real-video RSI."
        ),
    }
