"""Counterfactual diagnostic suite on simulated traces."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .contracts import EntityCandidate, OperationName, OperationRequest, TimeSpan
from .executor import SimulatedWorld, TypedEvidenceExecutor, WorldFact, default_genome


def toy_world() -> SimulatedWorld:
    """Generic A/B world: entity X acts at interval A; property at interval B."""
    entities = {
        "entity_x": EntityCandidate("entity_x", "the first speaker", aliases=["speaker_a"], confidence=0.9),
        "entity_y": EntityCandidate("entity_y", "the second speaker", aliases=["speaker_b"], confidence=0.9),
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
            "b1",
            "entity_x",
            "action",
            "removes_jacket",
            TimeSpan(25, 30, "B"),
            referring_cues=["later action"],
        ),
        WorldFact(
            "b2",
            "entity_y",
            "action",
            "waves_hand",
            TimeSpan(25, 30, "B"),
            referring_cues=["later action other"],
        ),
        WorldFact(
            "s1",
            "entity_x",
            "visible_label",
            "removes_jacket",
            TimeSpan(25, 30, "B_only_shortcut"),
            referring_cues=["name badge shows answer"],
        ),
    ]
    return SimulatedWorld(facts=facts, entities=entities)


@dataclass
class CounterfactualSuite:
    results: dict[str, Any]


def _run_full(world: SimulatedWorld, referring: str, prop: str = "action") -> dict[str, Any]:
    ex = TypedEvidenceExecutor(world, default_genome())
    r1 = ex.run(OperationRequest(OperationName.RESOLVE_REFERENCE, {"referring_expression": referring}))
    r2 = ex.run(OperationRequest(OperationName.TRACK_IDENTITY, {"target_span": {"start_s": 25, "end_s": 30}}))
    r3 = ex.run(OperationRequest(OperationName.QUERY_PROPERTY, {"property_name": prop}))
    r4 = ex.run(
        OperationRequest(
            OperationName.VERIFY_ANSWER,
            {
                "answer": r3.outputs.get("property_value"),
                "interval_a": {"start_s": 0, "end_s": 5},
                "interval_b": {"start_s": 25, "end_s": 30},
                "single_clip_sufficient": False,
            },
        )
    )
    return {
        "resolve_ok": r1.ok,
        "track_ok": r2.ok,
        "query_ok": r3.ok,
        "verify_ok": r4.ok,
        "value": r3.outputs.get("property_value"),
        "credit": r4.outputs.get("composition_credit"),
        "bound": ex.memory.bound_entity.entity_id if ex.memory.bound_entity else None,
        "gaps": list(ex.memory.pending_gaps),
        "recovery": list(ex.memory.recovery_stack),
    }


def run_counterfactual_suite(world: SimulatedWorld | None = None) -> CounterfactualSuite:
    world = world or toy_world()

    # A+B full path
    full = _run_full(deepcopy(world), "first speaker")

    # A-only: remove B facts for entity_x action
    world_a = deepcopy(world)
    world_a.facts = [f for f in world_a.facts if not (f.entity_id == "entity_x" and f.property_name == "action")]
    a_only = _run_full(world_a, "first speaker")

    # B-only: remove A referring cue / role event; try to query without resolve
    world_b = deepcopy(world)
    world_b.facts = [f for f in world_b.facts if f.fact_id != "a1"]
    ex_b = TypedEvidenceExecutor(world_b, default_genome())
    # Skip resolve — query directly should fail if binding required
    q_b = ex_b.run(OperationRequest(OperationName.QUERY_PROPERTY, {"property_name": "action", "entity_id": None}))
    b_only = {
        "query_ok": q_b.ok,
        "failure": q_b.failure_code,
        "gaps": list(ex_b.memory.pending_gaps),
        "recovery": list(ex_b.memory.recovery_stack),
    }

    # Subject swap: bind to entity_y instead
    swapped = _run_full(deepcopy(world), "second speaker")

    # Single-clip shortcut control
    ex_s = TypedEvidenceExecutor(deepcopy(world), default_genome())
    ex_s.run(OperationRequest(OperationName.RESOLVE_REFERENCE, {"referring_expression": "first speaker"}))
    ex_s.run(OperationRequest(OperationName.QUERY_PROPERTY, {"property_name": "action"}))
    v_s = ex_s.run(
        OperationRequest(
            OperationName.VERIFY_ANSWER,
            {
                "answer": "removes_jacket",
                "single_clip_sufficient": True,
                # deliberately omit dual intervals
            },
        )
    )
    shortcut = {
        "verify_ok": v_s.ok,
        "credit": v_s.outputs.get("composition_credit"),
        "ambiguity": v_s.ambiguity.value,
        "failure": v_s.failure_code,
    }

    # Failure triggers recovery
    ex_r = TypedEvidenceExecutor(deepcopy(world), {**default_genome(), "search_budget": 4})
    miss = ex_r.run(OperationRequest(OperationName.LOCATE_EVENT, {"cue": "nonexistent_event_zzz"}))
    recovery = {
        "initial_fail": not miss.ok,
        "recovery_stack": list(ex_r.memory.recovery_stack),
        "tool_calls": ex_r.memory.tool_calls,
    }

    return CounterfactualSuite(
        results={
            "A_plus_B": full,
            "A_only": a_only,
            "B_only": b_only,
            "subject_swap": swapped,
            "single_clip_shortcut": shortcut,
            "failure_recovery": recovery,
            "assertions": {
                "missing_evidence_reported": (not a_only["query_ok"]) or bool(a_only["gaps"]) or (a_only["value"] is None),
                "binding_changes_query_target": full["bound"] != swapped["bound"] and full["value"] != swapped["value"],
                "single_clip_not_strong_success": shortcut["credit"]
                in {None, "CONTROL_ONLY_NOT_STRONG_COMPOSITION", "DENIED_SINGLE_OR_MISSING"}
                or shortcut["failure"] == "DUAL_EVIDENCE_REQUIRED",
                "failure_triggers_recovery": bool(recovery["recovery_stack"]),
            },
        }
    )
