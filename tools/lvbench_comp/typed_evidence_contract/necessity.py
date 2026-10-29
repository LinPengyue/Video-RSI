"""Neutral masked necessity: same question; only exposed observation groups change.

Do NOT rewrite referring expressions, alias lexicons, or distractor sets when masking.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .contracts import OperationName, OperationRequest
from .observations import ObservationBundle, ObsFact, mask_observations
from .oracle_free_executor import OracleFreeExecutor


@dataclass
class NecessityResult:
    evidence_path_valid: bool
    semantic_answer_correct: bool
    composition_necessary: bool
    a_only_solves: bool
    b_only_solves: bool
    ab_solves: bool
    details: dict[str, Any]


def _run_question(
    bundle: ObservationBundle,
    *,
    referring: str,
    property_name: str,
    genome: dict[str, Any],
    program: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ex = OracleFreeExecutor(bundle, deepcopy(genome))
    if program is None:
        program = [
            {"op": "resolve_reference", "inputs": {"referring_expression": referring}},
            {"op": "track_identity", "inputs": {"target_span": {"start_s": 25, "end_s": 30}}},
            {"op": "query_property", "inputs": {"property_name": property_name}},
            {
                "op": "verify_answer",
                "inputs": {
                    "interval_a": {"start_s": 0.0, "end_s": 5.0},
                    "interval_b": {"start_s": 25.0, "end_s": 30.0},
                },
            },
        ]
    pred = None
    last_verify = None
    for step in program:
        op = OperationName(step["op"])
        inputs = dict(step.get("inputs") or {})
        if op == OperationName.VERIFY_ANSWER:
            inputs["answer"] = pred
        r = ex.run(OperationRequest(op, inputs))
        if op == OperationName.QUERY_PROPERTY and r.ok:
            pred = r.outputs.get("property_value")
        if op == OperationName.VERIFY_ANSWER:
            last_verify = r
    return {
        "pred": pred,
        "query_ok": pred is not None,
        "bound_track": ex.memory.bound_track,
        "calls": len(ex.memory.tool_calls),
        "path_valid": bool(last_verify and last_verify.outputs.get("evidence_path_valid")),
        "credit": last_verify.outputs.get("composition_credit") if last_verify else None,
        "recovery": list(ex.memory.recovery_stack),
        "oracle_id_in_recovery": any(r.get("oracle_entity_id_used") for r in ex.memory.recovery_stack),
    }


def evaluate_necessity_neutral(
    bundle: ObservationBundle,
    *,
    referring: str,
    property_name: str,
    gold_answer: Any,
    genome: dict[str, Any],
    evidence_groups_a: set[str] | None = None,
    evidence_groups_b: set[str] | None = None,
    program: list[dict[str, Any]] | None = None,
    ab_pred: Any | None = None,
    evidence_path_valid: bool | None = None,
) -> NecessityResult:
    """Exact same question under A-only / B-only / A+B; only observation groups change."""
    groups_a = evidence_groups_a or {"A"}
    groups_b = evidence_groups_b or {"B"}

    a_bundle = mask_observations(bundle, groups_a)
    b_bundle = mask_observations(bundle, groups_b)
    ab_bundle = mask_observations(bundle, groups_a | groups_b)

    a_run = _run_question(a_bundle, referring=referring, property_name=property_name, genome=genome, program=program)
    b_run = _run_question(b_bundle, referring=referring, property_name=property_name, genome=genome, program=program)
    if ab_pred is None:
        ab_run = _run_question(ab_bundle, referring=referring, property_name=property_name, genome=genome, program=program)
        ab_pred = ab_run["pred"]
    else:
        ab_run = {"pred": ab_pred, "query_ok": ab_pred is not None, "path_valid": bool(evidence_path_valid)}

    a_solves = bool(a_run.get("query_ok") and a_run.get("pred") == gold_answer)
    b_solves = bool(b_run.get("query_ok") and b_run.get("pred") == gold_answer)
    ab_solves = bool(ab_run.get("query_ok") and ab_pred == gold_answer)
    path = ab_run.get("path_valid") if evidence_path_valid is None else evidence_path_valid
    necessary = bool(ab_solves and (not a_solves) and (not b_solves))

    return NecessityResult(
        evidence_path_valid=bool(path),
        semantic_answer_correct=ab_solves,
        composition_necessary=necessary,
        a_only_solves=a_solves,
        b_only_solves=b_solves,
        ab_solves=ab_solves,
        details={"a_only": a_run, "b_only": b_run, "ab": ab_run, "masking": "groups_only_no_alias_rewrite"},
    )


# Back-compat wrapper used by older evolution_loop (oracle SimulatedWorld path).
def evaluate_necessity(
    world: Any,
    *,
    referring: str,
    property_name: str,
    gold_answer: Any,
    genome: dict[str, Any],
    evidence_path_valid: bool,
    ab_pred: Any | None = None,
) -> NecessityResult:
    """Deprecated oracle-world path: project to observations then neutral-mask."""
    from .observations import project_oracle_free

    bundle, _omap = project_oracle_free(
        world,
        scenario_id="legacy_necessity",
        gold_answer=gold_answer,
        gold_property=property_name,
    )
    return evaluate_necessity_neutral(
        bundle,
        referring=referring,
        property_name=property_name,
        gold_answer=gold_answer,
        genome=genome,
        ab_pred=ab_pred,
        evidence_path_valid=evidence_path_valid,
    )


def make_b_only_sufficient_control(bundle: ObservationBundle, referring: str, answer: Any) -> ObservationBundle:
    """Control: A→B link exists but B alone also carries the referring cue + answer."""
    b = deepcopy(bundle)
    for f in b.facts:
        if f.evidence_group == "B" and f.observed_value == answer:
            if referring not in f.referring_cues:
                f.referring_cues = list(f.referring_cues) + [referring]
    # Ensure an entity surface form matches referring for B-only resolve
    for ent in b.entities.values():
        # attach referring to the track that has the answer on B
        pass
    answer_tracks = {f.track_id for f in b.facts if f.evidence_group == "B" and f.observed_value == answer}
    for tid in answer_tracks:
        if tid in b.entities and referring not in b.entities[tid].surface_forms:
            b.entities[tid].surface_forms = list(b.entities[tid].surface_forms) + [referring]
    return b
