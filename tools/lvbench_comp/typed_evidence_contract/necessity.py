"""Composition necessity via masked A-only / B-only / A+B execution.

Three judgments are kept separate:
  evidence_path_valid  — provenance chain structurally ok
  semantic_answer_correct — predicted answer matches oracle gold
  composition_necessary — neither A-only nor B-only solves the same question
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .contracts import OperationName, OperationRequest
from .executor import SimulatedWorld, TypedEvidenceExecutor, WorldFact


@dataclass
class NecessityResult:
    evidence_path_valid: bool
    semantic_answer_correct: bool
    composition_necessary: bool
    a_only_solves: bool
    b_only_solves: bool
    ab_solves: bool
    details: dict[str, Any]


def _mask_world(world: SimulatedWorld, keep_labels: set[str]) -> SimulatedWorld:
    w = deepcopy(world)
    w.facts = [f for f in w.facts if (f.time.label or "") in keep_labels or f.time.label in keep_labels]
    # Also keep facts whose span overlaps intended intervals via label A/B
    return w


def _answer_from_run(ex: TypedEvidenceExecutor, referring: str, prop: str, genome: dict[str, Any]) -> dict[str, Any]:
    r1 = ex.run(OperationRequest(OperationName.RESOLVE_REFERENCE, {"referring_expression": referring}))
    r2 = ex.run(OperationRequest(OperationName.TRACK_IDENTITY, {"target_span": {"start_s": 25, "end_s": 30}}))
    r3 = ex.run(OperationRequest(OperationName.QUERY_PROPERTY, {"property_name": prop}))
    pred = r3.outputs.get("property_value")
    return {
        "resolve_ok": r1.ok,
        "track_ok": r2.ok,
        "query_ok": r3.ok,
        "pred": pred,
        "bound": ex.memory.bound_entity.entity_id if ex.memory.bound_entity else None,
        "calls": len(ex.memory.tool_calls),
    }


def evaluate_necessity(
    world: SimulatedWorld,
    *,
    referring: str,
    property_name: str,
    gold_answer: Any,
    genome: dict[str, Any],
    evidence_path_valid: bool,
    ab_pred: Any | None = None,
) -> NecessityResult:
    """Run the same question under A-only, B-only, and (cached) A+B predictions."""
    # A-only: remove B-interval facts
    world_a = deepcopy(world)
    world_a.facts = [f for f in world_a.facts if f.time.label == "A" or (f.time.end_s <= 10)]
    # More precise: keep only early span
    world_a.facts = [f for f in world.facts if f.time.end_s <= 10]
    ex_a = TypedEvidenceExecutor(world_a, deepcopy(genome))
    a_run = _answer_from_run(ex_a, referring, property_name, genome)
    a_solves = bool(a_run["query_ok"] and a_run["pred"] == gold_answer)

    # B-only: remove A-interval facts; also clear ability to bind via A cues
    world_b = deepcopy(world)
    world_b.facts = [f for f in world.facts if f.time.start_s >= 20]
    # Strip referring cues that would allow binding without A scene
    for f in world_b.facts:
        f.referring_cues = [c for c in f.referring_cues if "speaker" not in c.lower() and "first" not in c.lower()]
    # Keep entity aliases but require bound entity — without A resolve cues, resolve should fail
    # unless expression matches entity referring_expression directly.
    entities_b = deepcopy(world.entities)
    for e in entities_b.values():
        # Weaken surface forms so B-only cannot resolve the referring phrase from A role
        if referring.lower() in (e.referring_expression.lower(), *[a.lower() for a in e.aliases]):
            # Keep ambiguous alias path if present; for unique "first speaker" remove exact match
            if referring.lower() == e.referring_expression.lower():
                e.referring_expression = f"unknown:{e.entity_id}"
                e.aliases = [a for a in e.aliases if a.lower() != referring.lower()]
    world_b.entities = entities_b
    ex_b = TypedEvidenceExecutor(world_b, deepcopy(genome))
    b_run = _answer_from_run(ex_b, referring, property_name, genome)
    b_solves = bool(b_run["query_ok"] and b_run["pred"] == gold_answer)

    if ab_pred is None:
        ex_ab = TypedEvidenceExecutor(deepcopy(world), deepcopy(genome))
        ab_run = _answer_from_run(ex_ab, referring, property_name, genome)
        ab_pred = ab_run["pred"]
        ab_ok = bool(ab_run["query_ok"])
    else:
        ab_ok = ab_pred is not None
        ab_run = {"pred": ab_pred}

    ab_solves = bool(ab_ok and ab_pred == gold_answer)
    semantic = ab_solves
    necessary = ab_solves and (not a_solves) and (not b_solves)

    return NecessityResult(
        evidence_path_valid=evidence_path_valid,
        semantic_answer_correct=semantic,
        composition_necessary=necessary,
        a_only_solves=a_solves,
        b_only_solves=b_solves,
        ab_solves=ab_solves,
        details={"a_only": a_run, "b_only": b_run, "ab": ab_run},
    )


def b_only_shortcut_control_world(world: SimulatedWorld, answer: Any) -> SimulatedWorld:
    """Negative control: A→B link exists but B alone shows the answer on a single entity."""
    w = deepcopy(world)
    # Collapse B to a single entity that directly exposes the answer with a unique visible label
    w.facts = [f for f in w.facts if not (f.time.start_s >= 20 and f.property_name == "action" and f.entity_id != "entity_x")]
    # Add a B-only readable badge that equals the answer (shortcut)
    if w.facts:
        badge = WorldFact(
            "badge_b",
            "entity_x",
            "visible_label",
            answer,
            deepcopy(next(f.time for f in w.facts if f.time.start_s >= 20)),
            referring_cues=["name badge shows answer", "first speaker"],
        )
        # Make referring resolveable from B alone
        badge.time.label = "B"
        w.facts.append(badge)
        for e in w.entities.values():
            if e.entity_id == "entity_x" and "first speaker" not in e.aliases:
                e.aliases = list(e.aliases) + ["first speaker"]
    return w
