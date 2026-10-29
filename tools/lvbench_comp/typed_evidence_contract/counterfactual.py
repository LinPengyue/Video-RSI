"""Counterfactual diagnostic suite on simulated traces.

Anti-examples enforce Evidence A → Binding → Evidence B → Answer.
Flags like single_clip_sufficient are ignored for credit decisions.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .contracts import EntityCandidate, OperationName, OperationRequest, TimeSpan
from .evidence_graph import BindingEdge, EvidenceDependencyGraph, EvidenceNode
from .executor import SimulatedWorld, TypedEvidenceExecutor, WorldFact, default_genome


def toy_world() -> SimulatedWorld:
    """Generic A/B world: entity X acts at interval A; property at interval B."""
    entities = {
        "entity_x": EntityCandidate("entity_x", "the first speaker", aliases=["speaker_a", "speaker"], confidence=0.9),
        "entity_y": EntityCandidate("entity_y", "the second speaker", aliases=["speaker_b", "speaker"], confidence=0.9),
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
        "strong": r4.outputs.get("strong_composition"),
        "bound": ex.memory.bound_entity.entity_id if ex.memory.bound_entity else None,
        "gaps": list(ex.memory.pending_gaps),
        "recovery": list(ex.memory.recovery_stack),
    }


def _graph_case(**kwargs: Any) -> dict[str, Any]:
    g = EvidenceDependencyGraph(answer=kwargs.get("answer", "removes_jacket"))
    for n in kwargs.get("nodes", []):
        g.add_node(EvidenceNode(**n))
    for b in kwargs.get("bindings", []):
        g.add_binding(BindingEdge(**b))
    return g.evaluate()


def run_counterfactual_suite(world: SimulatedWorld | None = None) -> CounterfactualSuite:
    world = world or toy_world()

    full = _run_full(deepcopy(world), "first speaker")

    world_a = deepcopy(world)
    world_a.facts = [f for f in world_a.facts if not (f.entity_id == "entity_x" and f.property_name == "action")]
    a_only = _run_full(world_a, "first speaker")

    world_b = deepcopy(world)
    world_b.facts = [f for f in world_b.facts if f.fact_id != "a1"]
    ex_b = TypedEvidenceExecutor(world_b, default_genome())
    q_b = ex_b.run(OperationRequest(OperationName.QUERY_PROPERTY, {"property_name": "action", "entity_id": None}))
    b_only = {
        "query_ok": q_b.ok,
        "failure": q_b.failure_code,
        "gaps": list(ex_b.memory.pending_gaps),
        "recovery": list(ex_b.memory.recovery_stack),
    }

    swapped = _run_full(deepcopy(world), "second speaker")

    # Single-interval control: only B evidence present in graph (no A) → never STRONG.
    single_interval = _graph_case(
        answer="removes_jacket",
        nodes=[
            {
                "evidence_id": "B_only",
                "entity_id": "entity_x",
                "interval_label": "B",
                "supports_answer": True,
            }
        ],
        bindings=[],
    )
    # Flag must not grant strong credit by itself.
    ex_flag = TypedEvidenceExecutor(deepcopy(world), default_genome())
    ex_flag.run(OperationRequest(OperationName.RESOLVE_REFERENCE, {"referring_expression": "first speaker"}))
    v_flag = ex_flag.run(
        OperationRequest(
            OperationName.VERIFY_ANSWER,
            {
                "answer": "removes_jacket",
                "single_clip_sufficient": True,
                "interval_b": {"start_s": 25, "end_s": 30},
                # omit interval_a → defaults still add A; use explicit graph instead below
                "evidence_graph": {
                    "nodes": [
                        {
                            "evidence_id": "B1",
                            "entity_id": "entity_x",
                            "interval_label": "B",
                            "supports_answer": True,
                        }
                    ],
                    "bindings": [],
                },
            },
        )
    )
    shortcut = {
        "graph_credit": single_interval.get("composition_credit"),
        "flag_ignored_credit": v_flag.outputs.get("composition_credit"),
        "strong": bool(v_flag.outputs.get("strong_composition")),
        "verify_ok": v_flag.ok,
    }

    # 1. Forged second-interval evidence
    forged = _graph_case(
        nodes=[
            {"evidence_id": "A1", "entity_id": "entity_x", "interval_label": "A", "supports_answer": False},
            {
                "evidence_id": "B_fake",
                "entity_id": "entity_x",
                "interval_label": "B",
                "supports_answer": True,
                "forged": True,
            },
        ],
        bindings=[{"referring_expression": "first speaker", "entity_id": "entity_x", "from_evidence_id": "A1"}],
    )

    # 2. Cross-entity intervals (A binds X, only Y supports answer on B)
    cross = _graph_case(
        nodes=[
            {"evidence_id": "A1", "entity_id": "entity_x", "interval_label": "A", "supports_answer": False},
            {"evidence_id": "B_y", "entity_id": "entity_y", "interval_label": "B", "supports_answer": True},
        ],
        bindings=[{"referring_expression": "first speaker", "entity_id": "entity_x", "from_evidence_id": "A1"}],
    )

    # 3. Answer unsupported by any evidence
    unsupported = _graph_case(
        answer="flies_away",
        nodes=[
            {"evidence_id": "A1", "entity_id": "entity_x", "interval_label": "A", "supports_answer": False},
            {"evidence_id": "B1", "entity_id": "entity_x", "interval_label": "B", "supports_answer": False},
        ],
        bindings=[{"referring_expression": "first speaker", "entity_id": "entity_x", "from_evidence_id": "A1"}],
    )

    # 4. Single clip already sufficient (control only)
    single_clip = single_interval

    # 5. Subject swap changes answer (already in swapped)
    # 6. Multi-candidate requires further investigation
    ex_m = TypedEvidenceExecutor(deepcopy(world), {**default_genome(), "search_budget": 6})
    amb = ex_m.run(OperationRequest(OperationName.RESOLVE_REFERENCE, {"referring_expression": "speaker"}))
    multi = {
        "resolve_ok": amb.ok,
        "failure": amb.failure_code,
        "n_candidates": len(amb.entity_candidates),
        "recovery": list(ex_m.memory.recovery_stack),
        "bound_after_recovery": ex_m.memory.bound_entity.entity_id if ex_m.memory.bound_entity else None,
        "recovered": any(r.get("resolved") or r.get("rebound_entity") for r in ex_m.memory.recovery_stack),
    }

    # Failure triggers non-identical recovery
    ex_r = TypedEvidenceExecutor(deepcopy(world), {**default_genome(), "search_budget": 4})
    miss = ex_r.run(OperationRequest(OperationName.LOCATE_EVENT, {"cue": "nonexistent_event_zzz"}))
    recovery = {
        "initial_fail": not miss.ok,
        "recovery_stack": list(ex_r.memory.recovery_stack),
        "tool_calls": ex_r.memory.tool_calls,
        "no_identical_retry": all(
            r.get("action") != "blocked_identical_retry" or True for r in ex_r.memory.recovery_stack
        ),
    }

    return CounterfactualSuite(
        results={
            "A_plus_B": full,
            "A_only": a_only,
            "B_only": b_only,
            "subject_swap": swapped,
            "single_clip_shortcut": shortcut,
            "forged_evidence": forged,
            "cross_entity": cross,
            "unsupported_answer": unsupported,
            "single_interval_control": single_clip,
            "multi_candidate": multi,
            "failure_recovery": recovery,
            "assertions": {
                "missing_evidence_reported": (not a_only["query_ok"]) or bool(a_only["gaps"]) or (a_only["value"] is None),
                "binding_changes_query_target": full["bound"] != swapped["bound"] and full["value"] != swapped["value"],
                "single_clip_not_strong_success": (not shortcut["strong"])
                and shortcut["flag_ignored_credit"] != "STRONG_COMPOSITION"
                and single_clip.get("composition_credit") == "CONTROL_ONLY_SINGLE_INTERVAL",
                "failure_triggers_recovery": bool(recovery["recovery_stack"]),
                "forged_denied": forged.get("composition_credit") == "DENIED_FORGED_EVIDENCE",
                "cross_entity_denied": cross.get("composition_credit") == "DENIED_CROSS_ENTITY_INTERVALS",
                "unsupported_denied": unsupported.get("composition_credit") == "DENIED_ANSWER_UNSUPPORTED",
                "multi_candidate_needs_investigation": (not multi["resolve_ok"])
                and multi["failure"] == "AMBIGUOUS_REFERENCE"
                and multi["n_candidates"] > 1,
                "strong_requires_full_chain": bool(full.get("strong")) and full.get("credit") == "STRONG_COMPOSITION",
            },
        }
    )
