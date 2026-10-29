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
    recovery_stack: list[str] = field(default_factory=list)


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
        strategy = self.genome.get("recovery_strategy", "relocate_then_resolve")
        self.memory.recovery_stack.append(f"{failed.op.value}:{failed.failure_code}:{strategy}")
        if strategy == "none" or self.budget <= 0:
            return
        if failed.failure_code in {"MISSING_EVIDENCE", "ENTITY_UNBOUND"} and strategy in {
            "relocate_then_resolve",
            "investigate_conflict",
        }:
            # Recovery attempt: widen search once.
            widen = OperationRequest(
                op=OperationName.LOCATE_EVENT,
                inputs={"cue": failed.outputs.get("cue") or failed.message, "widen": True},
            )
            self.run(widen)

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
        answer = request.inputs.get("answer")
        require_dual = bool(self.genome.get("verify_requires_dual_evidence", True))
        evidence_ids = list(request.inputs.get("evidence_ids") or self.memory.evidence_index.keys())
        a_span = request.inputs.get("interval_a")
        b_span = request.inputs.get("interval_b")
        single_clip_ok = bool(request.inputs.get("single_clip_sufficient", False))

        if require_dual and (not a_span or not b_span):
            return OperationResult(
                op=OperationName.VERIFY_ANSWER,
                ok=False,
                failure_code="DUAL_EVIDENCE_REQUIRED",
                message="A+B intervals required for strong composition credit",
                ambiguity=AmbiguityFlag.SINGLE_CLIP_SUFFICIENT if single_clip_ok else AmbiguityFlag.MISSING_EVIDENCE,
                outputs={"answer": answer, "composition_credit": "DENIED_SINGLE_OR_MISSING"},
            )
        if single_clip_ok and require_dual:
            return OperationResult(
                op=OperationName.VERIFY_ANSWER,
                ok=True,
                outputs={
                    "answer": answer,
                    "composition_credit": "CONTROL_ONLY_NOT_STRONG_COMPOSITION",
                    "reason": "Answerable from one clip; not counted as strong composition success",
                },
                ambiguity=AmbiguityFlag.SINGLE_CLIP_SUFFICIENT,
            )
        if answer is None:
            return OperationResult(
                op=OperationName.VERIFY_ANSWER,
                ok=False,
                failure_code="EMPTY_ANSWER",
                message="No answer to verify",
            )
        return OperationResult(
            op=OperationName.VERIFY_ANSWER,
            ok=True,
            outputs={
                "answer": answer,
                "composition_credit": "STRONG_IF_BINDING_USED",
                "evidence_ids": evidence_ids,
                "bound_entity": self.memory.bound_entity.entity_id if self.memory.bound_entity else None,
            },
            ambiguity=AmbiguityFlag.NONE,
        )


def default_genome() -> dict[str, Any]:
    return {
        "search_budget": 5,
        "recovery_strategy": "relocate_then_resolve",  # none | relocate_then_resolve | investigate_conflict
        "query_requires_bound_entity": True,
        "verify_requires_dual_evidence": True,
        "abort_on_hard_fail": False,
        "op_order_template": [
            "locate_event",
            "resolve_reference",
            "track_identity",
            "query_property",
            "verify_answer",
        ],
    }
