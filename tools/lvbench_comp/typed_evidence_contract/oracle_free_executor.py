"""Executor over ObservationBundle — cannot read oracle entity_id / gold answers.

Recovery may only rebind to ephemeral track_ids present in observations.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .contracts import AmbiguityFlag, OperationName, OperationRequest, OperationResult, TimeSpan
from .evidence_graph import BindingEdge, EvidenceDependencyGraph, EvidenceNode
from .executor import default_genome
from .observations import ObservationBundle, ObsEntity, ObsFact


@dataclass
class OFMemory:
    bound_track: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    recovery_stack: list[dict[str, Any]] = field(default_factory=list)
    pending_gaps: list[str] = field(default_factory=list)
    selected_obs: list[str] = field(default_factory=list)


class OracleFreeExecutor:
    def __init__(self, bundle: ObservationBundle, genome: dict[str, Any] | None = None) -> None:
        # Defensive copy of agent view only
        self.bundle = ObservationBundle(
            entities=deepcopy(bundle.entities),
            facts=deepcopy(bundle.facts),
            link_hypotheses=deepcopy(bundle.link_hypotheses),
        )
        self.bundle.to_agent_dict()
        self.genome = genome or default_genome()
        self.budget = int(self.genome.get("search_budget", 5))
        self.memory = OFMemory()

    def run(self, request: OperationRequest) -> OperationResult:
        if self.budget <= 0:
            result = OperationResult(
                op=request.op,
                ok=False,
                failure_code="BUDGET_EXHAUSTED",
                message="budget exhausted",
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
                budget_spent=0,
            )
            return result
        handler = {
            OperationName.LOCATE_EVENT: self._locate,
            OperationName.RESOLVE_REFERENCE: self._resolve,
            OperationName.TRACK_IDENTITY: self._track,
            OperationName.QUERY_PROPERTY: self._query,
            OperationName.VERIFY_ANSWER: self._verify,
        }[request.op]
        result = handler(request)
        self.budget -= result.budget_spent
        self.memory.tool_calls.append({"op": request.op.value, "ok": result.ok, "failure": result.failure_code})
        if not result.ok:
            self._recover(result)
        return result

    def _recover(self, failed: OperationResult) -> None:
        strategy = self.genome.get("recovery_strategy", "none")
        if strategy == "none" or self.budget <= 0:
            self.memory.recovery_stack.append(
                {"failed_op": failed.op.value, "strategy": strategy, "action": "skip", "resolved": False}
            )
            return
        action = None
        if failed.failure_code == "AMBIGUOUS_REFERENCE":
            alt = self.genome.get("fallback_referring_expression")
            if alt:
                action = OperationRequest(OperationName.RESOLVE_REFERENCE, {"referring_expression": alt})
            else:
                cue = self.genome.get("disambiguation_cue", "opens the meeting")
                action = OperationRequest(OperationName.LOCATE_EVENT, {"cue": cue, "widen": True})
        elif failed.failure_code in {"ENTITY_UNBOUND", "MISSING_EVIDENCE"}:
            cue = str(failed.outputs.get("cue") or "")
            action = OperationRequest(OperationName.LOCATE_EVENT, {"cue": cue, "widen": True})
        if action is None:
            self.memory.recovery_stack.append(
                {"failed_op": failed.op.value, "strategy": strategy, "action": "no_applicable", "resolved": False}
            )
            return
        prev = self.genome.get("recovery_strategy")
        self.genome["recovery_strategy"] = "none"
        result = self.run(action)
        rebound = False
        if result.ok and action.op == OperationName.LOCATE_EVENT and self.memory.bound_track is None:
            # Bind only via track_id from observation hits — never oracle entity_id
            tids = result.outputs.get("track_ids") or []
            if tids and tids[0] in self.bundle.entities:
                self.memory.bound_track = tids[0]
                rebound = True
        self.genome["recovery_strategy"] = prev
        self.memory.recovery_stack.append(
            {
                "failed_op": failed.op.value,
                "strategy": strategy,
                "action": action.op.value,
                "resolved": result.ok,
                "rebound_track": rebound,
                "bound_after": self.memory.bound_track,
                # Explicit: recovery does not expose oracle ids
                "oracle_entity_id_used": False,
            }
        )

    def _locate(self, request: OperationRequest) -> OperationResult:
        cue = str(request.inputs.get("cue", "")).lower()
        widen = bool(request.inputs.get("widen", False))
        hits: list[ObsFact] = []
        for fact in self.bundle.facts:
            blob = " ".join([fact.obs_id, fact.track_id, fact.property_name, str(fact.observed_value)] + fact.referring_cues).lower()
            if cue and cue in blob:
                hits.append(fact)
            elif widen and any(tok in blob for tok in cue.split() if len(tok) > 3):
                hits.append(fact)
        if not hits:
            return OperationResult(
                op=OperationName.LOCATE_EVENT,
                ok=False,
                failure_code="MISSING_EVIDENCE",
                message=f"no locate for {cue!r}",
                outputs={"cue": cue},
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
            )
        self.memory.selected_obs.extend(h.obs_id for h in hits)
        return OperationResult(
            op=OperationName.LOCATE_EVENT,
            ok=True,
            outputs={"obs_ids": [h.obs_id for h in hits], "track_ids": [h.track_id for h in hits], "cue": cue},
            ambiguity=AmbiguityFlag.MULTI_CANDIDATE if len({h.track_id for h in hits}) > 1 else AmbiguityFlag.NONE,
        )

    def _resolve(self, request: OperationRequest) -> OperationResult:
        expr = str(request.inputs.get("referring_expression", "")).lower()
        matches: list[ObsEntity] = []
        for ent in self.bundle.entities.values():
            bag = " ".join(ent.surface_forms + [ent.track_id]).lower()
            if expr and expr in bag:
                matches.append(ent)
        for fact in self.bundle.facts:
            if any(expr in c.lower() for c in fact.referring_cues):
                ent = self.bundle.entities.get(fact.track_id)
                if ent and all(m.track_id != ent.track_id for m in matches):
                    matches.append(ent)
        if not matches:
            return OperationResult(
                op=OperationName.RESOLVE_REFERENCE,
                ok=False,
                failure_code="ENTITY_UNBOUND",
                message=f"cannot resolve {expr!r}",
                outputs={"cue": expr},
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
            )
        if len(matches) > 1:
            return OperationResult(
                op=OperationName.RESOLVE_REFERENCE,
                ok=False,
                failure_code="AMBIGUOUS_REFERENCE",
                message="multiple track candidates",
                outputs={"cue": expr, "track_ids": [m.track_id for m in matches]},
                ambiguity=AmbiguityFlag.MULTI_CANDIDATE,
            )
        self.memory.bound_track = matches[0].track_id
        return OperationResult(
            op=OperationName.RESOLVE_REFERENCE,
            ok=True,
            outputs={"track_id": matches[0].track_id},
            ambiguity=AmbiguityFlag.NONE,
        )

    def _track(self, request: OperationRequest) -> OperationResult:
        tid = request.inputs.get("track_id") or self.memory.bound_track
        if tid is None:
            return OperationResult(
                op=OperationName.TRACK_IDENTITY,
                ok=False,
                failure_code="ENTITY_UNBOUND",
                message="no bound track",
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
            )
        span = None
        ts = request.inputs.get("target_span")
        if isinstance(ts, dict):
            span = TimeSpan(float(ts["start_s"]), float(ts["end_s"]))
        present = [f for f in self.bundle.facts_in(span) if f.track_id == tid]
        if not present:
            return OperationResult(
                op=OperationName.TRACK_IDENTITY,
                ok=False,
                failure_code="IDENTITY_LOST",
                message=f"track {tid} not in span",
                outputs={"track_id": tid},
                ambiguity=AmbiguityFlag.LOW_VISIBILITY,
            )
        return OperationResult(
            op=OperationName.TRACK_IDENTITY,
            ok=True,
            outputs={"track_id": tid, "obs_ids": [f.obs_id for f in present]},
        )

    def _query(self, request: OperationRequest) -> OperationResult:
        tid = request.inputs.get("track_id") or self.memory.bound_track
        prop = str(request.inputs.get("property_name", ""))
        if self.genome.get("query_requires_bound_entity", True) and tid is None:
            return OperationResult(
                op=OperationName.QUERY_PROPERTY,
                ok=False,
                failure_code="ENTITY_UNBOUND",
                message="query requires bound track",
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
            )
        hits = [f for f in self.bundle.facts if f.track_id == tid and f.property_name == prop]
        if not hits:
            self.memory.pending_gaps.append(f"query:{tid}:{prop}")
            return OperationResult(
                op=OperationName.QUERY_PROPERTY,
                ok=False,
                failure_code="MISSING_EVIDENCE",
                message=f"no {prop} for {tid}",
                outputs={"track_id": tid, "property_name": prop},
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
            )
        return OperationResult(
            op=OperationName.QUERY_PROPERTY,
            ok=True,
            outputs={"track_id": tid, "property_name": prop, "property_value": hits[0].observed_value},
        )

    def _verify(self, request: OperationRequest) -> OperationResult:
        answer = request.inputs.get("answer")
        if answer is None:
            return OperationResult(op=OperationName.VERIFY_ANSWER, ok=False, failure_code="EMPTY_ANSWER", message="no answer")
        graph = EvidenceDependencyGraph(answer=answer)
        # Build from exposed observations only; support label from observed_value match (not oracle flag)
        for fact in self.bundle.facts:
            label = fact.evidence_group if fact.evidence_group in {"A", "B"} else "B"
            graph.add_node(
                EvidenceNode(
                    evidence_id=fact.obs_id,
                    entity_id=fact.track_id,  # ephemeral track id, not oracle
                    interval_label=label,
                    supports_answer=(fact.observed_value == answer or str(fact.observed_value) == str(answer)),
                    forged=False,
                    modality=fact.modalities[0] if fact.modalities else "visual",
                    oracle_support_label=False,
                )
            )
        if self.memory.bound_track:
            a_ids = [
                n.evidence_id
                for n in graph.nodes.values()
                if n.interval_label == "A" and n.entity_id == self.memory.bound_track
            ]
            if a_ids:
                graph.add_binding(
                    BindingEdge(
                        referring_expression="bound_track",
                        entity_id=self.memory.bound_track,
                        from_evidence_id=a_ids[0],
                    )
                )
        decision = graph.evaluate()
        credit = decision.get("composition_credit")
        path_valid = bool(decision.get("evidence_path_valid")) or credit in {
            "STRONG_COMPOSITION",
            "PATH_VALID_NECESSITY_UNPROVEN",
        }
        return OperationResult(
            op=OperationName.VERIFY_ANSWER,
            ok=bool(decision.get("ok")),
            failure_code=None if decision.get("ok") else credit,
            message="; ".join(decision.get("reasons") or []),
            outputs={
                "answer": answer,
                "composition_credit": credit,
                "evidence_path_valid": path_valid,
                "composition_necessary_hint": bool(decision.get("composition_necessary_hint")),
                "strong_composition": credit == "STRONG_COMPOSITION",
                "bound_track": self.memory.bound_track,
                "oracle_support_used": False,
            },
        )


def program_hash(program: list[dict[str, Any]]) -> str:
    blob = json.dumps(program, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def trace_hash(tool_calls: list[dict[str, Any]]) -> str:
    blob = json.dumps(tool_calls, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
