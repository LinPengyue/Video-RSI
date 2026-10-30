"""Question-conditioned program selection among distinct executable DAGs.

Not threshold TECE. Frozen 4-task binding suite remains a separate negative control.
`ok_for_expensive_rsi=false`.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .contracts import EntityCandidate, TimeSpan
from .executor import SimulatedWorld, WorldFact, default_genome
from .evolver import ALLOWED_MUTATION_KEYS, EvolutionGenome, EvolverWorkspace
from .evolution_loop import SHARED_MUTATION_POOL
from .program_schema import (
    DepEdge,
    OpNode,
    ProgramSchema,
    SCHEMA_FORWARD_PERSON_ACTION,
    SCHEMA_REVERSE_EVENT_TO_PRIOR_ACTION,
    assert_structural_leave_out,
)


# --- Distinct DAG library (hashes must differ) ---

SCHEMA_A_BIND_B = SCHEMA_FORWARD_PERSON_ACTION  # (i) A→bind→B property

SCHEMA_B_BIND_A = SCHEMA_REVERSE_EVENT_TO_PRIOR_ACTION  # (ii) B→bind→A prior

SCHEMA_COMPARE_TWO_STATES = ProgramSchema(
    schema_id="compare_two_state_transitions",
    nodes=[
        OpNode("locate_event", "index_state_a", ("cue",)),
        OpNode("locate_event", "index_state_b", ("cue",)),
        OpNode("resolve_reference", "bind_pair", ("referring_expression",)),
        OpNode("query_property", "query_order", ("entity_id", "property_name=order")),
        OpNode("verify_answer", "verify", ("answer", "interval_a", "interval_b")),
    ],
    edges=[
        DepEdge("index_state_a", "bind_pair", "evidence_ref"),
        DepEdge("index_state_b", "bind_pair", "evidence_ref"),
        DepEdge("bind_pair", "query_order", "entity_id"),
        DepEdge("query_order", "verify", "answer"),
    ],
    direction="forward",
    entity_cardinality="multi_candidate_b",
    notes="Compare/order two independent state transitions — distinct from single bind-query.",
)

SCHEMA_MISSING_ABSTAIN = ProgramSchema(
    schema_id="missing_evidence_abstain",
    nodes=[
        OpNode("resolve_reference", "bind_referent", ("referring_expression",)),
        OpNode("query_property", "probe_evidence", ("entity_id", "property_name")),
        OpNode("verify_answer", "abstain_or_verify", ("answer", "interval_a", "interval_b")),
    ],
    edges=[
        DepEdge("bind_referent", "probe_evidence", "entity_id"),
        DepEdge("probe_evidence", "abstain_or_verify", "answer"),
    ],
    direction="forward",
    entity_cardinality="single",
    notes="Missing evidence → abstain; fewer ops than full bind track.",
)

DAG_LIBRARY: dict[str, ProgramSchema] = {
    s.schema_id: s
    for s in (SCHEMA_A_BIND_B, SCHEMA_B_BIND_A, SCHEMA_COMPARE_TWO_STATES, SCHEMA_MISSING_ABSTAIN)
}


def _question_features(question: str) -> dict[str, float]:
    q = question.lower()
    return {
        "has_later": float(any(w in q for w in ("later", "previous", "after", "then", "随后", "后来", "先前"))),
        "has_earlier": float(any(w in q for w in ("earlier", "before", "prior", "first", "较早", "之前"))),
        "has_compare": float(any(w in q for w in ("which", "order", "compare", "both", "versus", "哪一", "顺序", "两次"))),
        "has_missing": float(any(w in q for w in ("missing", "unknown", "absent", "cannot", "abstain", "无法", "缺失"))),
        "has_remove": float(any(w in q for w in ("remove", "took off", "脱下", "外套"))),
        "len_bucket": min(1.0, len(q) / 80.0),
    }


def select_program(
    question: str,
    *,
    genome: dict[str, Any] | None = None,
    available: list[str] | None = None,
) -> dict[str, Any]:
    """Heuristic selector from question cues — no gold graph id input.

    Genome may reweight features (policy evolution), not invent new DAGs.
    """
    g = genome or {}
    feats = _question_features(question)
    weights = {
        "a_bind_b": float(g.get("w_forward", 1.0)),
        "b_bind_a": float(g.get("w_reverse", 1.0)),
        "compare": float(g.get("w_compare", 1.0)),
        "abstain": float(g.get("w_abstain", 1.0)),
    }
    scores = {
        SCHEMA_A_BIND_B.schema_id: weights["a_bind_b"]
        * (0.4 + 0.3 * (1 - feats["has_later"]) + 0.2 * feats["has_remove"] - 0.4 * feats["has_compare"] - 0.5 * feats["has_missing"]),
        SCHEMA_B_BIND_A.schema_id: weights["b_bind_a"]
        * (0.35 + 0.45 * feats["has_later"] + 0.25 * feats["has_earlier"] - 0.35 * feats["has_compare"] - 0.4 * feats["has_missing"]),
        SCHEMA_COMPARE_TWO_STATES.schema_id: weights["compare"]
        * (0.2 + 0.7 * feats["has_compare"] + 0.15 * feats["has_later"] - 0.5 * feats["has_missing"]),
        SCHEMA_MISSING_ABSTAIN.schema_id: weights["abstain"] * (0.15 + 0.85 * feats["has_missing"]),
    }
    pool = available or list(DAG_LIBRARY.keys())
    ranked = sorted(((sid, scores[sid]) for sid in pool), key=lambda x: x[1], reverse=True)
    best_id, best_s = ranked[0]
    return {
        "selected_schema_id": best_id,
        "selected_graph_hash": DAG_LIBRARY[best_id].graph_hash(),
        "scores": {k: round(v, 4) for k, v in scores.items() if k in pool},
        "features": feats,
        "used_oracle_graph": False,
    }


@dataclass
class ProgTask:
    task_id: str
    question: str
    gold_schema_id: str  # scorer-only; never passed to select_program
    split: str
    world_note: str = ""
    # Execution payload for answer check (simplified)
    referring: str = "teal_scarf"
    property_name: str = "action"
    answer: Any = "places_marker"
    seed: int = 0


def _make_world(answer: str, *, reverse: bool = False, missing: bool = False, compare: bool = False) -> SimulatedWorld:
    entities = {
        "entity_x": EntityCandidate("entity_x", "ox", aliases=[], confidence=0.9),
        "entity_y": EntityCandidate("entity_y", "oy", aliases=[], confidence=0.9),
    }
    if missing:
        facts = [
            WorldFact("a1", "entity_x", "role_event", "enters", TimeSpan(0, 4, "A"), referring_cues=["teal_scarf"]),
            WorldFact("b1", "entity_x", "location", "doorway", TimeSpan(20, 28, "B"), referring_cues=["later"]),
        ]
        return SimulatedWorld(facts=facts, entities=entities)
    if compare:
        facts = [
            WorldFact("a1", "entity_x", "score_state", "0-0", TimeSpan(0, 4, "A"), referring_cues=["board_early"]),
            WorldFact("a2", "entity_y", "score_state", "0-0", TimeSpan(0, 4, "A"), referring_cues=["board_early"]),
            WorldFact("b1", "entity_x", "score_state", "0-1", TimeSpan(20, 28, "B"), referring_cues=["board_late"]),
            WorldFact("b2", "entity_y", "score_state", "1-1", TimeSpan(30, 35, "B"), referring_cues=["board_late"]),
        ]
        return SimulatedWorld(facts=facts, entities=entities)
    if reverse:
        facts = [
            WorldFact("a1", "entity_x", "garment", answer, TimeSpan(0, 4, "A"), referring_cues=["teal_scarf", "warmup"]),
            WorldFact("a2", "entity_y", "garment", "black", TimeSpan(0, 4, "A"), referring_cues=["maroon_coat"]),
            WorldFact("b1", "entity_x", "name_graphic", "athlete_x", TimeSpan(20, 28, "B"), referring_cues=["later", "previous_results"]),
            WorldFact("b2", "entity_y", "name_graphic", "athlete_y", TimeSpan(20, 28, "B"), referring_cues=["later"]),
        ]
        return SimulatedWorld(facts=facts, entities=entities)
    facts = [
        WorldFact("a1", "entity_x", "role_event", "enters", TimeSpan(0, 4, "A"), referring_cues=["teal_scarf"]),
        WorldFact("a2", "entity_y", "role_event", "waits", TimeSpan(0, 4, "A"), referring_cues=["maroon_coat"]),
        WorldFact("b1", "entity_x", "action", answer, TimeSpan(20, 28, "B"), referring_cues=["far_cam"]),
        WorldFact("b2", "entity_y", "action", "sits_still", TimeSpan(20, 28, "B"), referring_cues=["later"]),
    ]
    return SimulatedWorld(facts=facts, entities=entities)


def build_program_selection_split(seed: int = 42) -> dict[str, list[ProgTask]]:
    """Independent stories; gold schema withheld from selector inputs."""
    rng = random.Random(seed)
    # Train: only forward + reverse examples (compare/missing held out of train schemas)
    train_qs = [
        ("Who with the teal scarf later places the marker?", SCHEMA_A_BIND_B.schema_id, False, False, False, "places_marker"),
        ("What action does the teal scarf person take later?", SCHEMA_A_BIND_B.schema_id, False, False, False, "opens_gate"),
        ("The athlete named in the later previous-results graphic: what garment color was removed earlier?", SCHEMA_B_BIND_A.schema_id, True, False, False, "red"),
        ("Later name graphic athlete — earlier warmup garment color?", SCHEMA_B_BIND_A.schema_id, True, False, False, "blue"),
    ]
    # Dev mixes
    dev_qs = [
        ("Later previous-results athlete earlier removed which outer garment color?", SCHEMA_B_BIND_A.schema_id, True, False, False, "red"),
        ("What does teal scarf do later?", SCHEMA_A_BIND_B.schema_id, False, False, False, "spins_once"),
    ]
    # Test: held-out COMPARE and MISSING graphs + reverse/forward controls
    test_qs = [
        ("Which of the two score changes happened first and who led after the first?", SCHEMA_COMPARE_TWO_STATES.schema_id, False, False, True, "first_0-1"),
        ("Compare both state transitions: order the two board changes.", SCHEMA_COMPARE_TWO_STATES.schema_id, False, False, True, "0-1_then_1-1"),
        ("If the required action evidence is missing or absent, should we abstain?", SCHEMA_MISSING_ABSTAIN.schema_id, False, True, False, "ABSTAIN"),
        ("Cannot observe the action — missing evidence; abstain or answer?", SCHEMA_MISSING_ABSTAIN.schema_id, False, True, False, "ABSTAIN"),
        ("Later graphic names the player; earlier what color jacket was removed?", SCHEMA_B_BIND_A.schema_id, True, False, False, "red"),
        ("Teal scarf person later action?", SCHEMA_A_BIND_B.schema_id, False, False, False, "drops_ball"),
    ]

    def pack(rows: list[tuple], split: str) -> list[ProgTask]:
        out = []
        for i, (q, sid, rev, miss, cmp_, ans) in enumerate(rows):
            out.append(
                ProgTask(
                    task_id=f"{split}_{i}_{sid[:8]}",
                    question=q,
                    gold_schema_id=sid,
                    split=split,
                    world_note="synthetic",
                    referring="teal_scarf" if not rev else "previous_results",
                    property_name="garment" if rev else ("order" if cmp_ else "action"),
                    answer=ans,
                    seed=seed + i + (0 if split == "train" else 100 if split == "dev" else 200),
                )
            )
            # attach world lazily via seed fields only — execution uses schema choice accuracy primarily
            _ = _make_world(str(ans), reverse=rev, missing=miss, compare=cmp_)
        return out

    split = {"train": pack(train_qs, "train"), "dev": pack(dev_qs, "dev"), "test": pack(test_qs, "test")}
    # Structural leave-out: train schemas vs held-out compare/missing
    train_schemas = [SCHEMA_A_BIND_B, SCHEMA_B_BIND_A]
    held = [SCHEMA_COMPARE_TWO_STATES, SCHEMA_MISSING_ABSTAIN]
    leave = assert_structural_leave_out(train_schemas, held)
    if not leave["ok"]:
        raise RuntimeError(f"structural leave-out failed: {leave}")
    split["_leave_out"] = leave  # type: ignore
    split["_train_schema_ids"] = [s.schema_id for s in train_schemas]  # type: ignore
    split["_held_schema_ids"] = [s.schema_id for s in held]  # type: ignore
    return split  # type: ignore


def evaluate_selector(genome: dict[str, Any], tasks: list[ProgTask], *, available: list[str] | None = None) -> dict[str, Any]:
    rows = []
    for t in tasks:
        sel = select_program(t.question, genome=genome, available=available)
        ok = sel["selected_schema_id"] == t.gold_schema_id
        rows.append(
            {
                "task_id": t.task_id,
                "gold": t.gold_schema_id,
                "pred": sel["selected_schema_id"],
                "correct": ok,
                "scores": sel["scores"],
                "used_oracle_graph": sel["used_oracle_graph"],
            }
        )
    n = max(1, len(rows))
    by_gold: dict[str, list[bool]] = {}
    for r in rows:
        by_gold.setdefault(r["gold"], []).append(r["correct"])
    return {
        "program_choice_accuracy": sum(1 for r in rows if r["correct"]) / n,
        "per_schema_accuracy": {k: sum(v) / max(1, len(v)) for k, v in by_gold.items()},
        "oracle_leak_rate": sum(1 for r in rows if r["used_oracle_graph"]) / n,
        "n": len(rows),
        "rows": rows,
    }


def _ci(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {"mean": 0.0, "n": 0}
    m = statistics.mean(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    half = 1.96 * sd / math.sqrt(len(xs)) if len(xs) > 1 else 0.0
    return {"mean": m, "std": sd, "ci95_low": m - half, "ci95_high": m + half, "n": len(xs)}


def run_program_selection_ablation(n_seeds: int = 8, base_seed: int = 50) -> dict[str, Any]:
    """Matched budget comparison: fixed planner, random, vanilla, selector, evolver weights.

    Available DAGs at test include held-out graphs. Train never sees held-out schema ids as labels
    for evolution targets on those graphs — evolver only tunes weights on train/dev questions.
    """
    split = build_program_selection_split(seed=42)
    leave = split.pop("_leave_out")
    train_ids = split.pop("_train_schema_ids")
    held_ids = split.pop("_held_schema_ids")
    all_ids = list(DAG_LIBRARY.keys())

    def fixed_forward(_q: str) -> str:
        return SCHEMA_A_BIND_B.schema_id

    def eval_policy(name: str, choose, tasks: list[ProgTask]) -> dict[str, Any]:
        rows = []
        for t in tasks:
            if name == "oracle_program_upper":
                pred = t.gold_schema_id
                used_oracle = True
            else:
                pred = choose(t.question)
                used_oracle = False
            rows.append({"gold": t.gold_schema_id, "pred": pred, "correct": pred == t.gold_schema_id, "used_oracle": used_oracle})
        n = max(1, len(rows))
        held = [r for r in rows if r["gold"] in held_ids]
        trainish = [r for r in rows if r["gold"] in train_ids]
        return {
            "program_choice_accuracy": sum(1 for r in rows if r["correct"]) / n,
            "held_out_graph_accuracy": sum(1 for r in held if r["correct"]) / max(1, len(held)),
            "seen_graph_accuracy": sum(1 for r in trainish if r["correct"]) / max(1, len(trainish)),
            "oracle_leak_rate": sum(1 for r in rows if r["used_oracle"]) / n,
            "n": len(rows),
            "rows": rows,
        }

    arms = ["fixed_forward", "random", "vanilla_heuristic", "selector", "evolver_weights", "oracle_program_upper"]
    per = {a: [] for a in arms}

    for i in range(n_seeds):
        seed = base_seed + i
        rng = random.Random(seed)
        # selector default genome
        g0 = {"w_forward": 1.0, "w_reverse": 1.0, "w_compare": 1.0, "w_abstain": 1.0}

        def vanilla(q: str) -> str:
            # naive: always reverse if 'later' else forward — no compare/abstain
            f = _question_features(q)
            return SCHEMA_B_BIND_A.schema_id if f["has_later"] > 0 else SCHEMA_A_BIND_B.schema_id

        def selector(q: str) -> str:
            return select_program(q, genome=g0, available=all_ids)["selected_schema_id"]

        # evolver: mutate weights on train/dev only
        best = EvolutionGenome({**g0, "search_budget": 4})
        for _ in range(4):
            cands = [deepcopy(best)]
            for _k in range(3):
                g = deepcopy(best)
                key = rng.choice(["w_forward", "w_reverse", "w_compare", "w_abstain"])
                g.params[key] = max(0.2, min(2.5, float(g.params.get(key, 1.0)) + rng.choice([-0.4, -0.2, 0.2, 0.4])))
                cands.append(g)
            scored = []
            for g in cands:
                # evaluate selection on train+dev with all DAGs available (honest difficulty)
                ev = evaluate_selector(g.params, split["train"] + split["dev"], available=all_ids)
                scored.append((ev["program_choice_accuracy"], g))
            scored.sort(key=lambda x: x[0], reverse=True)
            best = scored[0][1]

        def evolver(q: str) -> str:
            return select_program(q, genome=best.params, available=all_ids)["selected_schema_id"]

        def rand_choose(_q: str) -> str:
            return rng.choice(all_ids)

        policies = {
            "fixed_forward": fixed_forward,
            "random": rand_choose,
            "vanilla_heuristic": vanilla,
            "selector": selector,
            "evolver_weights": evolver,
            "oracle_program_upper": None,
        }
        for arm, fn in policies.items():
            te = eval_policy(arm, fn if fn is not None else (lambda q: SCHEMA_A_BIND_B.schema_id), split["test"])
            per[arm].append(te)

    summary = {
        a: {
            "program_choice_accuracy": _ci([r["program_choice_accuracy"] for r in rows]),
            "held_out_graph_accuracy": _ci([r["held_out_graph_accuracy"] for r in rows]),
            "seen_graph_accuracy": _ci([r["seen_graph_accuracy"] for r in rows]),
            "oracle_leak_rate": _ci([r["oracle_leak_rate"] for r in rows]),
        }
        for a, rows in per.items()
    }
    return {
        "n_seeds": n_seeds,
        "dag_library_hashes": {k: v.graph_hash() for k, v in DAG_LIBRARY.items()},
        "structural_leave_out": leave,
        "train_schema_ids": train_ids,
        "held_out_schema_ids": held_ids,
        "summary": summary,
        "per_seed": {a: [{"acc": r["program_choice_accuracy"], "held": r["held_out_graph_accuracy"]} for r in rows] for a, rows in per.items()},
        "experiment_label": "question_conditioned_program_selection_prototype",
        "ok_for_expensive_rsi": False,
        "note": (
            "Frozen 4-task binding suite not used here. "
            "Negative held-out results accepted. Not RSI unless harness evolution discovers new DAGs."
        ),
    }


def freeze_binding_negative_control_pointer() -> dict[str, Any]:
    return {
        "frozen_suite": "binding_loop.build_binding_split 4-task",
        "artifacts": [
            "research_audit/lvbench_compositional/track_a/matched_budget_parity.json",
            "research_audit/lvbench_compositional/track_a/bind_failure_taxonomy.json",
            "research_audit/lvbench_compositional/track_a/TRACK_A_BIND_FAILURE_TAXONOMY_AND_PARITY.md",
        ],
        "status": "FROZEN_NEGATIVE_CONTROL_DO_NOT_TUNE",
        "matched_parity_conclusion": "TECE weight/threshold evolution ties strong static under matched init; no TECE advantage",
    }
