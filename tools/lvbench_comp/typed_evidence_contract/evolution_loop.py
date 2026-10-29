"""Minimal Evolver closed loop on synthetic Seen / held-out Unseen tasks.

Initial Harness → Candidate Mutation → Evaluation → Selection → Updated Harness

Synthetic results validate mechanism design only — not real video RSI gains.
"""

from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .contracts import EntityCandidate, OperationName, OperationRequest, TimeSpan
from .executor import SimulatedWorld, TypedEvidenceExecutor, WorldFact, default_genome
from .evolver import ALLOWED_MUTATION_KEYS, EvolutionGenome, EvolverWorkspace


@dataclass
class SynthTask:
    task_id: str
    signature: str
    referring_expression: str
    property_name: str
    answer: Any
    world: SimulatedWorld
    held_out: bool = False
    needs_recovery: bool = False


def _world_pair(
    answer_x: str = "removes_jacket",
    answer_y: str = "waves_hand",
    *,
    ambiguous_alias: bool = False,
) -> SimulatedWorld:
    aliases_x = ["speaker_a", "speaker"] if ambiguous_alias else ["speaker_a"]
    aliases_y = ["speaker_b", "speaker"] if ambiguous_alias else ["speaker_b"]
    entities = {
        "entity_x": EntityCandidate("entity_x", "the first speaker", aliases=aliases_x, confidence=0.9),
        "entity_y": EntityCandidate("entity_y", "the second speaker", aliases=aliases_y, confidence=0.9),
    }
    facts = [
        WorldFact(
            "a1",
            "entity_x",
            "role_event",
            "speaks_first",
            TimeSpan(0, 5, "A"),
            referring_cues=["first speaker", "opens the meeting"],
        ),
        WorldFact(
            "a2",
            "entity_y",
            "role_event",
            "speaks_second",
            TimeSpan(0, 5, "A"),
            referring_cues=["second speaker"],
        ),
        WorldFact("b1", "entity_x", "action", answer_x, TimeSpan(25, 30, "B"), referring_cues=["later action"]),
        WorldFact("b2", "entity_y", "action", answer_y, TimeSpan(25, 30, "B"), referring_cues=["later action other"]),
    ]
    return SimulatedWorld(facts=facts, entities=entities)


def build_task_split() -> tuple[list[SynthTask], list[SynthTask]]:
    """Seen signatures for evolution; Unseen composition held out."""
    seen = [
        SynthTask(
            "seen_attr",
            "identify_person + describe_attribute",
            "first speaker",
            "action",
            "removes_jacket",
            _world_pair(),
            held_out=False,
        ),
        SynthTask(
            "seen_loc_style",
            "identify_person + describe_location",
            "second speaker",
            "action",
            "waves_hand",
            _world_pair(),
            held_out=False,
        ),
        # Ambiguous referring expression — Fixed with recovery=none fails; TECE can recover.
        SynthTask(
            "seen_ambiguous_bind",
            "identify_person + describe_attribute",
            "speaker",
            "action",
            "removes_jacket",
            _world_pair(ambiguous_alias=True),
            held_out=False,
            needs_recovery=True,
        ),
    ]
    unseen = [
        SynthTask(
            "unseen_person_action",
            "identify_person + describe_action",
            "speaker",
            "action",
            "takes_bow",
            _world_pair("takes_bow", "claps", ambiguous_alias=True),
            held_out=True,
            needs_recovery=True,
        )
    ]
    return seen, unseen


def run_task(genome: dict[str, Any], task: SynthTask) -> dict[str, Any]:
    ex = TypedEvidenceExecutor(deepcopy(task.world), deepcopy(genome))
    r1 = ex.run(OperationRequest(OperationName.RESOLVE_REFERENCE, {"referring_expression": task.referring_expression}))
    # If resolve failed but recovery rebound entity, continue.
    r2 = ex.run(OperationRequest(OperationName.TRACK_IDENTITY, {"target_span": {"start_s": 25, "end_s": 30}}))
    r3 = ex.run(OperationRequest(OperationName.QUERY_PROPERTY, {"property_name": task.property_name}))
    r4 = ex.run(
        OperationRequest(
            OperationName.VERIFY_ANSWER,
            {
                "answer": r3.outputs.get("property_value"),
                "interval_a": {"start_s": 0, "end_s": 5},
                "interval_b": {"start_s": 25, "end_s": 30},
            },
        )
    )
    strong = bool(r4.outputs.get("strong_composition"))
    correct = r3.ok and r3.outputs.get("property_value") == task.answer and strong
    return {
        "task_id": task.task_id,
        "signature": task.signature,
        "held_out": task.held_out,
        "resolve_ok": r1.ok,
        "query_ok": r3.ok,
        "verify_ok": r4.ok,
        "strong_composition": strong,
        "correct_strong": correct,
        "credit": r4.outputs.get("composition_credit"),
        "budget_left": ex.budget,
        "recovery": list(ex.memory.recovery_stack),
        "calls": len(ex.memory.tool_calls),
        "bound": ex.memory.bound_entity.entity_id if ex.memory.bound_entity else None,
    }


def evaluate(genome: dict[str, Any], tasks: list[SynthTask]) -> dict[str, Any]:
    rows = [run_task(genome, t) for t in tasks]
    n = max(1, len(rows))
    acc = sum(1 for r in rows if r["correct_strong"]) / n
    cost = sum(r["calls"] for r in rows) / n
    return {"accuracy": acc, "avg_calls": cost, "rows": rows}


MUTATION_POOL = [
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
]


def mutate_random(genome: EvolutionGenome, rng: random.Random) -> dict[str, Any]:
    patch = deepcopy(rng.choice(MUTATION_POOL))
    return {k: v for k, v in patch.items() if k in ALLOWED_MUTATION_KEYS}


def evolve(
    *,
    seen_tasks: list[SynthTask],
    unseen_tasks: list[SynthTask],
    generations: int = 8,
    population: int = 6,
    seed: int = 0,
    mode: str = "tece",
) -> dict[str, Any]:
    """mode: fixed | random | vanilla | tece"""
    rng = random.Random(seed)
    assert all(not t.held_out for t in seen_tasks)
    assert all(t.held_out for t in unseen_tasks)
    unseen_sigs = {u.signature for u in unseen_tasks}
    for t in seen_tasks:
        if t.signature in unseen_sigs:
            raise RuntimeError(f"schema leave-out violated: {t.signature}")

    # Fixed / initial: recovery disabled → exposes need for evolvable recovery on ambiguous tasks.
    if mode == "fixed":
        initial = EvolutionGenome({**default_genome(), "recovery_strategy": "none", "search_budget": 4})
    elif mode == "vanilla":
        initial = EvolutionGenome({**default_genome(), "recovery_strategy": "none", "search_budget": 4})
    else:
        initial = EvolutionGenome({**default_genome(), "recovery_strategy": "none", "search_budget": 4})

    history: list[dict[str, Any]] = []
    best = deepcopy(initial)

    if mode == "fixed":
        return {
            "mode": mode,
            "best_genome": best.params,
            "seen": evaluate(best.params, seen_tasks),
            "unseen_held_out": evaluate(best.params, unseen_tasks),
            "history": [],
            "strategy_changed": False,
            "note": "Synthetic only; not a real-video RSI claim.",
        }

    for gen in range(generations):
        candidates = [deepcopy(best)]
        for _ in range(population - 1):
            g = deepcopy(best)
            if mode == "random":
                patch = mutate_random(g, rng)
            elif mode == "vanilla":
                patch = {"search_budget": rng.choice([2, 4, 6, 8])}
            else:  # tece — mutate recovery + disambiguation + budget
                patch = mutate_random(g, rng)
                if rng.random() < 0.6:
                    patch["recovery_strategy"] = rng.choice(
                        ["none", "relocate_then_resolve", "investigate_conflict", "rebind_from_a"]
                    )
                if rng.random() < 0.4:
                    patch["fallback_referring_expression"] = rng.choice([None, "first speaker"])
                if rng.random() < 0.3:
                    patch["disambiguation_cue"] = rng.choice(["opens the meeting", "first speaker", "speaks_first"])
            ws = EvolverWorkspace(g)
            decision = ws.propose(patch)
            if decision["accepted"]:
                candidates.append(g)

        scored = []
        for g in candidates:
            ev = evaluate(g.params, seen_tasks)
            score = ev["accuracy"] - (0.02 * ev["avg_calls"] if mode == "tece" else 0.0)
            scored.append((score, g, ev))
        scored.sort(key=lambda x: x[0], reverse=True)
        winner_score, winner, winner_ev = scored[0]
        changed = winner.params != best.params
        history.append(
            {
                "generation": gen,
                "best_score": winner_score,
                "accuracy": winner_ev["accuracy"],
                "avg_calls": winner_ev["avg_calls"],
                "genome": deepcopy(winner.params),
                "changed": changed,
            }
        )
        best = winner

    return {
        "mode": mode,
        "best_genome": best.params,
        "seen": evaluate(best.params, seen_tasks),
        "unseen_held_out": evaluate(best.params, unseen_tasks),
        "history": history,
        "strategy_changed": any(h["changed"] for h in history),
        "note": "Synthetic only; not a real-video RSI claim.",
    }


def run_ablation_suite(seed: int = 7) -> dict[str, Any]:
    seen, unseen = build_task_split()
    return {
        arm: evolve(seen_tasks=seen, unseen_tasks=unseen, seed=seed, mode=arm)
        for arm in ("fixed", "random", "vanilla", "tece")
    }
