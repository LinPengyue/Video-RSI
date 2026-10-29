"""Simulated typed-evidence executor over synthetic world state.

Used for local logic tests only — not a claim of video generalization.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .contracts import (
    AmbiguityFlag,
    EntityCandidate,
    EvidenceRef,
    OperationName,
    OperationRequest,
    OperationResult,
    TimeSpan,
)
from .evidence_graph import BindingEdge, EvidenceDependencyGraph, EvidenceNode


@dataclass
class WorldFact:
    """A simulated observable fact at a time span."""

    fact_id: str
    entity_id: str
    property_name: str
    property_value: Any
    time: TimeSpan
    modalities: list[str] = field(default_factory=lambda: ["visual"])
    referring_cues: list[str] = field(default_factory=list)


@dataclass
class SimulatedWorld:
    facts: list[WorldFact]
    entities: dict[str, EntityCandidate]

    def facts_in(self, span: TimeSpan | None = None) -> list[WorldFact]:
        if span is None:
            return list(self.facts)
        return [f for f in self.facts if f.time.overlaps(span)]


@dataclass
class AgentMemory:
    bound_entity: EntityCandidate | None = None
    evidence_index: dict[str, EvidenceRef] = field(default_factory=dict)
    pending_gaps: list[str] = field(default_factory=list)
    selected_events: list[str] = field(default_factory=list)
    excluded_events: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    last_result: OperationResult | None = None
    recovery_stack: list[dict[str, Any]] = field(default_factory=list)


class TypedEvidenceExecutor:
    """Execute typed ops against a SimulatedWorld with recovery hooks."""

    def __init__(self, world: SimulatedWorld, genome: dict[str, Any] | None = None) -> None:
        self.world = world
        self.memory = AgentMemory()
        self.genome = genome or default_genome()
        self.budget = int(self.genome.get("search_budget", 5))

    def run(self, request: OperationRequest) -> OperationResult:
        if self.budget <= 0:
            result = OperationResult(
                op=request.op,
                ok=False,
                failure_code="BUDGET_EXHAUSTED",
                message="No search/verify budget remaining.",
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
                budget_spent=0,
            )
            self.memory.last_result = result
            return result

        handler = {
            OperationName.LOCATE_EVENT: self._locate_event,
            OperationName.RESOLVE_REFERENCE: self._resolve_reference,
            OperationName.TRACK_IDENTITY: self._track_identity,
            OperationName.QUERY_PROPERTY: self._query_property,
            OperationName.VERIFY_ANSWER: self._verify_answer,
        }[request.op]
        result = handler(request)
        self.budget -= result.budget_spent
        self.memory.tool_calls.append({"op": request.op.value, "ok": result.ok, "failure": result.failure_code})
        self.memory.last_result = result
        if not result.ok:
            self._maybe_recover(result)
        return result

    def run_program(self, program: list[dict[str, Any]]) -> list[OperationResult]:
        results = []
        for step in program:
            op = OperationName(step["op"])
            req = OperationRequest(op=op, inputs=step.get("inputs", {}), budget_remaining=self.budget)
            results.append(self.run(req))
            if not results[-1].ok and self.genome.get("abort_on_hard_fail", False):
                break
        return results

    def _maybe_recover(self, failed: OperationResult) -> None:
        """Choose a *different* follow-up op based on failure mode (not identical retry)."""
        strategy = self.genome.get("recovery_strategy", "relocate_then_resolve")
        if strategy == "none" or self.budget <= 0:
            self.memory.recovery_stack.append(
                {
                    "failed_op": failed.op.value,
                    "failure_code": failed.failure_code,
                    "strategy": strategy,
                    "action": "skip",
                    "resolved": False,
                }
            )
            return

        cue = str(failed.outputs.get("cue") or failed.message or "")
        action: OperationRequest | None = None
        if failed.failure_code == "AMBIGUOUS_REFERENCE" and strategy in {
            "investigate_conflict",
            "relocate_then_resolve",
            "rebind_from_a",
        }:
            # Prefer a more specific referring expression; else locate a distinctive cue and bind.
            alt = self.genome.get("fallback_referring_expression")
            if alt:
                action = OperationRequest(OperationName.RESOLVE_REFERENCE, {"referring_expression": alt})
            else:
                action = OperationRequest(
                    OperationName.LOCATE_EVENT,
                    {"cue": self.genome.get("disambiguation_cue", "opens the meeting"), "widen": True},
                )
        elif failed.failure_code in {"MISSING_EVIDENCE", "IDENTITY_LOST"} and strategy == "relocate_then_resolve":
            action = OperationRequest(OperationName.LOCATE_EVENT, {"cue": cue, "widen": True})
        elif failed.failure_code == "ENTITY_UNBOUND" and strategy in {
            "relocate_then_resolve",
            "rebind_from_a",
        }:
            alt = self.genome.get("fallback_referring_expression")
            if alt:
                action = OperationRequest(OperationName.RESOLVE_REFERENCE, {"referring_expression": alt})
            else:
                action = OperationRequest(OperationName.LOCATE_EVENT, {"cue": cue, "widen": True})
        elif failed.failure_code == "MISSING_EVIDENCE" and strategy == "investigate_conflict":
            action = OperationRequest(
                OperationName.TRACK_IDENTITY,
                {"target_span": {"start_s": 20.0, "end_s": 35.0}},
            )

        if action is None:
            self.memory.recovery_stack.append(
                {
                    "failed_op": failed.op.value,
                    "failure_code": failed.failure_code,
                    "strategy": strategy,
                    "action": "no_applicable_recovery",
                    "resolved": False,
                }
            )
            return

        # Avoid identical no-op retries (same op + same cue/expression without widen).
        same_op = failed.op == action.op and not action.inputs.get("widen")
        same_resolve = (
            same_op
            and action.op == OperationName.RESOLVE_REFERENCE
            and action.inputs.get("referring_expression") == failed.outputs.get("cue")
        )
        same_locate = (
            same_op
            and action.op == OperationName.LOCATE_EVENT
            and action.inputs.get("cue") == failed.outputs.get("cue")
        )
        if same_resolve or same_locate:
            self.memory.recovery_stack.append(
                {
                    "failed_op": failed.op.value,
                    "failure_code": failed.failure_code,
                    "strategy": strategy,
                    "action": "blocked_identical_retry",
                    "resolved": False,
                }
            )
            return

        # Temporarily disable nested recovery to prevent recursion storms.
        prev = self.genome.get("recovery_strategy")
        self.genome["recovery_strategy"] = "none"
        result = self.run(action)
        rebound = False
        # After a successful locate during ambiguity/unbound recovery, bind entity from evidence.
        if (
            result.ok
            and action.op == OperationName.LOCATE_EVENT
            and self.memory.bound_entity is None
            and result.outputs.get("fact_ids")
        ):
            fid = result.outputs["fact_ids"][0]
            fact = next((f for f in self.world.facts if f.fact_id == fid), None)
            if fact is not None and fact.entity_id in self.world.entities:
                self.memory.bound_entity = deepcopy(self.world.entities[fact.entity_id])
                rebound = True
        self.genome["recovery_strategy"] = prev
        self.memory.recovery_stack.append(
            {
                "failed_op": failed.op.value,
                "failure_code": failed.failure_code,
                "strategy": strategy,
                "action": action.op.value,
                "action_inputs": action.inputs,
                "resolved": bool(result.ok),
                "rebound_entity": rebound,
                "bound_after": self.memory.bound_entity.entity_id if self.memory.bound_entity else None,
                "budget_after": self.budget,
                "evidence_delta": list(result.outputs.get("fact_ids") or []),
            }
        )

    def _locate_event(self, request: OperationRequest) -> OperationResult:
        cue = str(request.inputs.get("cue", "")).lower()
        widen = bool(request.inputs.get("widen", False))
        hits = []
        for fact in self.world.facts:
            blob = " ".join([fact.fact_id, fact.entity_id, fact.property_name, str(fact.property_value)] + fact.referring_cues).lower()
            if cue and cue in blob:
                hits.append(fact)
            elif widen and any(tok in blob for tok in cue.split() if len(tok) > 3):
                hits.append(fact)
        if not hits:
            self.memory.pending_gaps.append(f"locate:{cue}")
            return OperationResult(
                op=OperationName.LOCATE_EVENT,
                ok=False,
                failure_code="MISSING_EVIDENCE",
                message=f"No event located for cue={cue!r}",
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
                outputs={"cue": cue},
            )
        evidence = [
            EvidenceRef(
                evidence_id=f"ev_{f.fact_id}",
                source="SIMULATED",
                time=f.time,
                modality=f.modalities[0],
                description=f"{f.property_name}={f.property_value}",
            )
            for f in hits
        ]
        for ev in evidence:
            self.memory.evidence_index[ev.evidence_id] = ev
        self.memory.selected_events.extend(f.fact_id for f in hits)
        return OperationResult(
            op=OperationName.LOCATE_EVENT,
            ok=True,
            outputs={"fact_ids": [f.fact_id for f in hits], "cue": cue},
            evidence=evidence,
            ambiguity=AmbiguityFlag.MULTI_CANDIDATE if len(hits) > 1 else AmbiguityFlag.NONE,
        )

    def _resolve_reference(self, request: OperationRequest) -> OperationResult:
        expr = str(request.inputs.get("referring_expression", "")).lower()
        matches: list[EntityCandidate] = []
        for ent in self.world.entities.values():
            bag = " ".join([ent.referring_expression, *ent.aliases, ent.entity_id]).lower()
            if expr and expr in bag:
                matches.append(deepcopy(ent))
        # Also match via fact cues.
        for fact in self.world.facts:
            if any(expr in c.lower() for c in fact.referring_cues) or expr in fact.entity_id.lower():
                ent = self.world.entities.get(fact.entity_id)
                if ent and all(m.entity_id != ent.entity_id for m in matches):
                    matches.append(deepcopy(ent))
        if not matches:
            return OperationResult(
                op=OperationName.RESOLVE_REFERENCE,
                ok=False,
                failure_code="ENTITY_UNBOUND",
                message=f"Cannot resolve {expr!r}",
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
                outputs={"cue": expr},
            )
        if len(matches) > 1:
            return OperationResult(
                op=OperationName.RESOLVE_REFERENCE,
                ok=False,
                failure_code="AMBIGUOUS_REFERENCE",
                message="Multiple entity candidates",
                entity_candidates=matches,
                ambiguity=AmbiguityFlag.MULTI_CANDIDATE,
            )
        self.memory.bound_entity = matches[0]
        return OperationResult(
            op=OperationName.RESOLVE_REFERENCE,
            ok=True,
            outputs={"entity_id": matches[0].entity_id},
            entity_candidates=matches,
            ambiguity=AmbiguityFlag.NONE,
        )

    def _track_identity(self, request: OperationRequest) -> OperationResult:
        entity_id = request.inputs.get("entity_id") or (
            self.memory.bound_entity.entity_id if self.memory.bound_entity else None
        )
        target_span = request.inputs.get("target_span")
        if entity_id is None:
            return OperationResult(
                op=OperationName.TRACK_IDENTITY,
                ok=False,
                failure_code="ENTITY_UNBOUND",
                message="No bound entity to track",
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
            )
        span = None
        if isinstance(target_span, dict):
            span = TimeSpan(float(target_span["start_s"]), float(target_span["end_s"]))
        present = [f for f in self.world.facts_in(span) if f.entity_id == entity_id]
        if not present:
            return OperationResult(
                op=OperationName.TRACK_IDENTITY,
                ok=False,
                failure_code="IDENTITY_LOST",
                message=f"Entity {entity_id} not observed in target span",
                ambiguity=AmbiguityFlag.LOW_VISIBILITY,
                outputs={"entity_id": entity_id},
            )
        return OperationResult(
            op=OperationName.TRACK_IDENTITY,
            ok=True,
            outputs={"entity_id": entity_id, "observed_fact_ids": [f.fact_id for f in present]},
            evidence=[
                EvidenceRef("ev_" + present[0].fact_id, "SIMULATED", present[0].time, present[0].modalities[0], "identity_track")
            ],
        )

    def _query_property(self, request: OperationRequest) -> OperationResult:
        entity_id = request.inputs.get("entity_id") or (
            self.memory.bound_entity.entity_id if self.memory.bound_entity else None
        )
        prop = str(request.inputs.get("property_name", ""))
        require_bound = bool(self.genome.get("query_requires_bound_entity", True))
        if require_bound and entity_id is None:
            return OperationResult(
                op=OperationName.QUERY_PROPERTY,
                ok=False,
                failure_code="ENTITY_UNBOUND",
                message="query_property requires a bound entity",
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
            )
        hits = [f for f in self.world.facts if f.entity_id == entity_id and f.property_name == prop]
        if not hits:
            self.memory.pending_gaps.append(f"query:{entity_id}:{prop}")
            return OperationResult(
                op=OperationName.QUERY_PROPERTY,
                ok=False,
                failure_code="MISSING_EVIDENCE",
                message=f"No property {prop} for {entity_id}",
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
                outputs={"entity_id": entity_id, "property_name": prop},
            )
        value = hits[0].property_value
        return OperationResult(
            op=OperationName.QUERY_PROPERTY,
            ok=True,
            outputs={"entity_id": entity_id, "property_name": prop, "property_value": value},
            evidence=[EvidenceRef("ev_" + hits[0].fact_id, "SIMULATED", hits[0].time, hits[0].modalities[0], str(value))],
        )

    def _verify_answer(self, request: OperationRequest) -> OperationResult:
        """Grant credit only via EvidenceDependencyGraph — not bare timestamps/flags."""
        answer = request.inputs.get("answer")
        if answer is None:
            return OperationResult(
                op=OperationName.VERIFY_ANSWER,
                ok=False,
                failure_code="EMPTY_ANSWER",
                message="No answer to verify",
            )

        graph = EvidenceDependencyGraph(answer=answer)
        # Prefer explicit evidence payload; else reconstruct from world + memory.
        explicit = request.inputs.get("evidence_graph")
        if isinstance(explicit, dict):
            for node in explicit.get("nodes", []):
                graph.add_node(EvidenceNode(**node))
            for edge in explicit.get("bindings", []):
                graph.add_binding(BindingEdge(**edge))
        else:
            interval_a = request.inputs.get("interval_a") or {"start_s": 0.0, "end_s": 10.0}
            interval_b = request.inputs.get("interval_b") or {"start_s": 20.0, "end_s": 35.0}
            span_a = TimeSpan(float(interval_a["start_s"]), float(interval_a["end_s"]), "A")
            span_b = TimeSpan(float(interval_b["start_s"]), float(interval_b["end_s"]), "B")
            forged_ids = set(request.inputs.get("forged_evidence_ids") or [])
            for fact in self.world.facts_in(span_a):
                graph.add_node(
                    EvidenceNode(
                        evidence_id=f"A_{fact.fact_id}",
                        entity_id=fact.entity_id,
                        interval_label="A",
                        supports_answer=False,
                        forged=fact.fact_id in forged_ids,
                    )
                )
            for fact in self.world.facts_in(span_b):
                supports = fact.property_value == answer or str(fact.property_value) == str(answer)
                graph.add_node(
                    EvidenceNode(
                        evidence_id=f"B_{fact.fact_id}",
                        entity_id=fact.entity_id,
                        interval_label="B",
                        supports_answer=supports,
                        forged=fact.fact_id in forged_ids,
                    )
                )
            if self.memory.bound_entity is not None:
                # Binding must come from an A-side observation.
                a_ids = [n.evidence_id for n in graph.nodes.values() if n.interval_label == "A" and n.entity_id == self.memory.bound_entity.entity_id]
                if a_ids:
                    graph.add_binding(
                        BindingEdge(
                            referring_expression=self.memory.bound_entity.referring_expression,
                            entity_id=self.memory.bound_entity.entity_id,
                            from_evidence_id=a_ids[0],
                        )
                    )

        decision = graph.evaluate()
        strong = decision.get("composition_credit") == "STRONG_COMPOSITION"
        control = str(decision.get("composition_credit", "")).startswith("CONTROL_ONLY")
        return OperationResult(
            op=OperationName.VERIFY_ANSWER,
            ok=bool(decision.get("ok")),
            failure_code=None if decision.get("ok") else decision.get("composition_credit"),
            message="; ".join(decision.get("reasons") or []),
            ambiguity=AmbiguityFlag.SINGLE_CLIP_SUFFICIENT
            if control
            else (AmbiguityFlag.NONE if strong else AmbiguityFlag.MISSING_EVIDENCE),
            outputs={
                "answer": answer,
                "composition_credit": decision.get("composition_credit"),
                "bound_entity": decision.get("bound_entity")
                or (self.memory.bound_entity.entity_id if self.memory.bound_entity else None),
                "reasons": decision.get("reasons"),
                "strong_composition": strong,
            },
        )


def default_genome() -> dict[str, Any]:
    return {
        "search_budget": 5,
        "recovery_strategy": "relocate_then_resolve",  # none | relocate_then_resolve | investigate_conflict | rebind_from_a
        "query_requires_bound_entity": True,
        "verify_requires_dual_evidence": True,
        "abort_on_hard_fail": False,
        "disambiguation_cue": "opens the meeting",
        "fallback_referring_expression": None,
        "op_order_template": [
            "locate_event",
            "resolve_reference",
            "track_identity",
            "query_property",
            "verify_answer",
        ],
    }
