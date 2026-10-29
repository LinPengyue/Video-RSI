"""Agent that must explicitly bind A-local ↔ B-local tracks before querying.

Supports three evaluation modes:
  oracle_program — diagnostic upper bound (schema program + gold match injected)
  program_selection — choose among templates from question cues (no forced held-out schema)
  evolver_policy — genome recovery/binding thresholds only
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .contracts import AmbiguityFlag, OperationName, OperationRequest, OperationResult
from .evidence_graph import BindingEdge, EvidenceDependencyGraph, EvidenceNode
from .executor import default_genome
from .observations import ObservationBundle
from .observations_v2 import CrossSceneOracle, mask_scene_local


@dataclass
class BindMemory:
    bound_a: str | None = None
    bound_b: str | None = None
    match_score: float = 0.0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    recovery_stack: list[dict[str, Any]] = field(default_factory=list)


class CrossSceneBindingExecutor:
    def __init__(
        self,
        bundle: ObservationBundle,
        genome: dict[str, Any] | None = None,
        *,
        mode: str = "program_selection",
        gold_match: tuple[str, str] | None = None,
    ) -> None:
        self.bundle = deepcopy(bundle)
        self.genome = genome or default_genome()
        self.budget = int(self.genome.get("search_budget", 6))
        self.memory = BindMemory()
        self.mode = mode
        self._gold_match = gold_match  # only used in oracle_program mode

    def run_pipeline(self, *, referring_a_cue: str, property_name: str) -> dict[str, Any]:
        """Minimal causal pipeline: resolve A → bind cross-scene → query B property → verify."""
        steps = []
        # 1. Resolve on A side using local cues
        r_a = self._resolve_side("A", referring_a_cue)
        steps.append(r_a)
        # 2. Cross-scene bind
        r_b = self._bind_cross_scene()
        steps.append(r_b)
        # 3. Query property on B-bound track
        r_q = self._query(property_name)
        steps.append(r_q)
        pred = r_q.outputs.get("property_value") if r_q.ok else None
        # 4. Verify with dual evidence
        r_v = self._verify(pred)
        steps.append(r_v)
        return {
            "pred": pred,
            "ok_query": r_q.ok,
            "path_valid": bool(r_v.outputs.get("evidence_path_valid")),
            "credit": r_v.outputs.get("composition_credit"),
            "bound_a": self.memory.bound_a,
            "bound_b": self.memory.bound_b,
            "match_score": self.memory.match_score,
            "calls": len(self.memory.tool_calls),
            "mode": self.mode,
            "used_oracle_match": self.mode == "oracle_program" and self._gold_match is not None,
            "steps_ok": [s.ok for s in steps],
        }

    def _resolve_side(self, side: str, cue: str) -> OperationResult:
        cue_l = cue.lower()
        group = side
        matches = []
        for f in self.bundle.facts:
            if f.evidence_group != group:
                continue
            bag = " ".join(f.referring_cues + [f.track_id, str(f.observed_value)]).lower()
            ent = self.bundle.entities.get(f.track_id)
            if ent:
                bag += " " + " ".join(ent.surface_forms).lower()
            if any(tok in bag for tok in cue_l.split() if len(tok) > 2) or cue_l in bag:
                matches.append(f.track_id)
        # unique
        matches = list(dict.fromkeys(matches))
        self.memory.tool_calls.append({"op": "resolve_reference", "side": side, "n": len(matches)})
        if len(matches) == 1:
            if side == "A":
                self.memory.bound_a = matches[0]
            else:
                self.memory.bound_b = matches[0]
            return OperationResult(op=OperationName.RESOLVE_REFERENCE, ok=True, outputs={"track_id": matches[0]})
        if not matches:
            # No privileged fallback to "first entity" — that created a B-only shortcut.
            return OperationResult(
                op=OperationName.RESOLVE_REFERENCE,
                ok=False,
                failure_code="ENTITY_UNBOUND",
                message=f"no match on side {side}",
                ambiguity=AmbiguityFlag.MISSING_EVIDENCE,
            )
        return OperationResult(
            op=OperationName.RESOLVE_REFERENCE,
            ok=False,
            failure_code="AMBIGUOUS_REFERENCE",
            message="ambiguous",
            outputs={"track_ids": matches},
            ambiguity=AmbiguityFlag.MULTI_CANDIDATE,
        )

    def _bind_cross_scene(self) -> OperationResult:
        self.memory.tool_calls.append({"op": "bind_cross_scene", "mode": self.mode})
        if self.mode == "oracle_program" and self._gold_match is not None:
            self.memory.bound_a, self.memory.bound_b = self._gold_match
            self.memory.match_score = 1.0
            return OperationResult(
                op=OperationName.TRACK_IDENTITY,
                ok=True,
                outputs={"bound_a": self.memory.bound_a, "bound_b": self.memory.bound_b, "oracle_program": True},
            )
        if self.memory.bound_a is None:
            return OperationResult(
                op=OperationName.TRACK_IDENTITY,
                ok=False,
                failure_code="ENTITY_UNBOUND",
                message="need A before bind",
            )
        thr = float(self.genome.get("bind_score_threshold", 0.35))
        cands = [
            h
            for h in self.bundle.link_hypotheses
            if h.get("status") == "HYPOTHESIS_ONLY" and h.get("a_track") == self.memory.bound_a
        ]
        if not cands:
            # recovery: pick best overall for this A among hypotheses
            cands = [h for h in self.bundle.link_hypotheses if h.get("a_track") == self.memory.bound_a]
        if not cands:
            return OperationResult(
                op=OperationName.TRACK_IDENTITY,
                ok=False,
                failure_code="IDENTITY_LOST",
                message="no link hypotheses",
            )
        best = max(cands, key=lambda h: float(h.get("score", 0)))
        if float(best.get("score", 0)) < thr and self.genome.get("recovery_strategy") in {
            "relocate_then_resolve",
            "rebind_from_a",
            "investigate_conflict",
        }:
            # lower threshold once as recovery
            thr = thr * 0.5
            self.memory.recovery_stack.append({"action": "lower_bind_threshold", "thr": thr})
        if float(best.get("score", 0)) < thr:
            return OperationResult(
                op=OperationName.TRACK_IDENTITY,
                ok=False,
                failure_code="IDENTITY_LOST",
                message="bind below threshold",
                outputs={"best": best},
            )
        self.memory.bound_b = best["b_track"]
        self.memory.match_score = float(best.get("score", 0))
        return OperationResult(
            op=OperationName.TRACK_IDENTITY,
            ok=True,
            outputs={"bound_a": self.memory.bound_a, "bound_b": self.memory.bound_b, "score": self.memory.match_score},
        )

    def _query(self, property_name: str) -> OperationResult:
        self.memory.tool_calls.append({"op": "query_property", "prop": property_name})
        tid = self.memory.bound_b
        if tid is None:
            return OperationResult(
                op=OperationName.QUERY_PROPERTY,
                ok=False,
                failure_code="ENTITY_UNBOUND",
                message="no B bind",
            )
        hits = [f for f in self.bundle.facts if f.track_id == tid and f.property_name == property_name]
        if not hits:
            return OperationResult(
                op=OperationName.QUERY_PROPERTY,
                ok=False,
                failure_code="MISSING_EVIDENCE",
                message="missing prop on B",
            )
        return OperationResult(
            op=OperationName.QUERY_PROPERTY,
            ok=True,
            outputs={"track_id": tid, "property_value": hits[0].observed_value},
        )

    def _verify(self, answer: Any) -> OperationResult:
        self.memory.tool_calls.append({"op": "verify_answer"})
        if answer is None:
            return OperationResult(op=OperationName.VERIFY_ANSWER, ok=False, failure_code="EMPTY_ANSWER", message="empty")
        g = EvidenceDependencyGraph(answer=answer)
        for f in self.bundle.facts:
            label = f.evidence_group if f.evidence_group in {"A", "B"} else "B"
            # Map tracks into graph as entity ids (local)
            g.add_node(
                EvidenceNode(
                    evidence_id=f.obs_id,
                    entity_id=f.track_id,
                    interval_label=label,
                    supports_answer=(f.observed_value == answer or str(f.observed_value) == str(answer)),
                )
            )
        # Binding edge uses matched pair: treat as same logical entity via edge only if bound
        if self.memory.bound_a and self.memory.bound_b:
            # Add synthetic unified node labels for path check: rewrite B node entity to A for path
            # Cleaner: add binding from A evidence to logical id, and mark B nodes with bound_b
            a_ev = next((f.obs_id for f in self.bundle.facts if f.track_id == self.memory.bound_a), None)
            if a_ev:
                # Re-key B supporting nodes to bound_a for co-presence check after successful bind
                for nid, node in list(g.nodes.items()):
                    if node.entity_id == self.memory.bound_b:
                        node.entity_id = self.memory.bound_a
                g.add_binding(BindingEdge("cross_scene", self.memory.bound_a, a_ev, confidence=self.memory.match_score))
        d = g.evaluate()
        credit = d.get("composition_credit")
        path = bool(d.get("evidence_path_valid")) or credit in {"STRONG_COMPOSITION", "PATH_VALID_NECESSITY_UNPROVEN"}
        return OperationResult(
            op=OperationName.VERIFY_ANSWER,
            ok=bool(d.get("ok")),
            outputs={
                "composition_credit": credit,
                "evidence_path_valid": path,
                "composition_necessary_hint": bool(d.get("composition_necessary_hint")),
            },
            failure_code=None if d.get("ok") else credit,
            message="; ".join(d.get("reasons") or []),
        )


def _single_side_answer(bundle: ObservationBundle, *, side: str, cue: str, property_name: str, genome: dict[str, Any]) -> dict[str, Any]:
    """Same question on one evidence group: resolve cue within that side and query — no cross-scene bind."""
    ex = CrossSceneBindingExecutor(bundle, genome, mode="program_selection")
    # Resolve within the available side only
    r = ex._resolve_side(side, cue)
    if not r.ok:
        # try opposite label if side mask used B facts labeled B
        return {"pred": None, "ok_query": False, "path_valid": False, "resolve_ok": False, "side": side}
    tid = r.outputs.get("track_id")
    if side == "A":
        ex.memory.bound_a = tid
        # A-only cannot query B properties — try query on A track anyway
        ex.memory.bound_b = tid
    else:
        ex.memory.bound_b = tid
        ex.memory.bound_a = tid  # local only; verify will lack dual intervals for strong path
    q = ex._query(property_name)
    pred = q.outputs.get("property_value") if q.ok else None
    return {
        "pred": pred,
        "ok_query": bool(q.ok),
        "path_valid": False,
        "resolve_ok": True,
        "side": side,
        "bound": tid,
        "used_oracle_match": False,
    }


def evaluate_necessity_v2(
    bundle: ObservationBundle,
    omap: CrossSceneOracle,
    *,
    referring_a_cue: str,
    property_name: str,
    genome: dict[str, Any],
    mode: str = "program_selection",
) -> dict[str, Any]:
    """A-only / B-only / A+B with scene-local entity lists + identical public context."""
    ctx = omap.public_context
    gold = omap.gold_answer

    a_bundle = mask_scene_local(bundle, {"A"}, public_context=ctx)
    b_bundle = mask_scene_local(bundle, {"B"}, public_context=ctx)
    ab_bundle = mask_scene_local(bundle, {"A", "B"}, public_context=ctx)

    a_run = _single_side_answer(a_bundle, side="A", cue=referring_a_cue, property_name=property_name, genome=genome)
    b_run = _single_side_answer(b_bundle, side="B", cue=referring_a_cue, property_name=property_name, genome=genome)

    gold_match = omap.gold_matches[0] if omap.gold_matches else None
    ex = CrossSceneBindingExecutor(
        ab_bundle,
        genome,
        mode=mode,
        gold_match=gold_match if mode == "oracle_program" else None,
    )
    ab_run = ex.run_pipeline(referring_a_cue=referring_a_cue, property_name=property_name)

    a_solves = bool(a_run.get("ok_query") and a_run.get("pred") == gold)
    b_solves = bool(b_run.get("ok_query") and b_run.get("pred") == gold)
    ab_solves = bool(ab_run.get("ok_query") and ab_run.get("pred") == gold)
    necessary = ab_solves and (not a_solves) and (not b_solves)
    return {
        "evidence_path_valid": bool(ab_run.get("path_valid")),
        "semantic_answer_correct": ab_solves,
        "composition_necessary": necessary,
        "a_only_solves": a_solves,
        "b_only_solves": b_solves,
        "ab_solves": ab_solves,
        "details": {"a_only": a_run, "b_only": b_run, "ab": ab_run},
        "mode": mode,
    }
