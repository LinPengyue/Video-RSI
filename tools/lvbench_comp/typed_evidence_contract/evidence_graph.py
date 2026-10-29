"""Executable evidence-dependency checks for composition credit.

Rule of thumb:
  Evidence A → Entity Binding → Evidence B → Answer
Two timestamps alone never grant strong composition success.

Judgments are separated:
  evidence_path_valid — provenance chain structurally ok
  composition_necessary_hint — structural hint that B is ambiguous (not a substitute
    for masked A-only/B-only necessity tests in necessity.py)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceNode:
    evidence_id: str
    entity_id: str | None
    interval_label: str  # e.g. A / B
    supports_answer: bool
    forged: bool = False
    modality: str = "visual"
    # Oracle flag: if True, this support label came from evaluator gold, not agent perception.
    oracle_support_label: bool = False


@dataclass
class BindingEdge:
    referring_expression: str
    entity_id: str
    from_evidence_id: str
    confidence: float = 1.0


@dataclass
class EvidenceDependencyGraph:
    nodes: dict[str, EvidenceNode] = field(default_factory=dict)
    bindings: list[BindingEdge] = field(default_factory=list)
    answer: Any = None

    def add_node(self, node: EvidenceNode) -> None:
        self.nodes[node.evidence_id] = node

    def add_binding(self, edge: BindingEdge) -> None:
        self.bindings.append(edge)

    def evaluate(self) -> dict[str, Any]:
        """Return composition credit + separated validity fields."""
        reasons: list[str] = []
        a_nodes = [n for n in self.nodes.values() if n.interval_label == "A"]
        b_nodes = [n for n in self.nodes.values() if n.interval_label == "B"]

        def _pack(**kwargs: Any) -> dict[str, Any]:
            base = {
                "evidence_path_valid": False,
                "composition_necessary_hint": False,
                "oracle_support_used": any(n.oracle_support_label for n in self.nodes.values()),
            }
            base.update(kwargs)
            return base

        if any(n.forged for n in self.nodes.values()):
            return _pack(
                ok=False,
                composition_credit="DENIED_FORGED_EVIDENCE",
                reasons=["forged evidence present"],
            )
        if not a_nodes and not b_nodes:
            return _pack(
                ok=False,
                composition_credit="DENIED_MISSING_EVIDENCE",
                reasons=["missing Evidence A and B"],
            )
        if not a_nodes or not b_nodes:
            if any(n.supports_answer for n in self.nodes.values()):
                missing = "A" if not a_nodes else "B"
                return _pack(
                    ok=True,
                    composition_credit="CONTROL_ONLY_SINGLE_INTERVAL",
                    reasons=[f"answer supported with only interval {'B' if missing == 'A' else 'A'}; missing {missing}"],
                    evidence_path_valid=False,
                    composition_necessary_hint=False,
                )
            return _pack(
                ok=False,
                composition_credit="DENIED_MISSING_A" if not a_nodes else "DENIED_MISSING_B",
                reasons=[f"missing Evidence {'A' if not a_nodes else 'B'}"],
            )

        if not self.bindings:
            reasons.append("no entity binding from A to B")
            if any(n.supports_answer for n in b_nodes):
                return _pack(
                    ok=True,
                    composition_credit="CONTROL_ONLY_B_SHORTCUT",
                    reasons=reasons + ["B alone supports answer"],
                    evidence_path_valid=False,
                    composition_necessary_hint=False,
                )
            return _pack(
                ok=False,
                composition_credit="DENIED_NO_BINDING",
                reasons=reasons,
            )

        bound_ids = {e.entity_id for e in self.bindings}
        a_entities = {n.entity_id for n in a_nodes if n.entity_id}
        b_entities = {n.entity_id for n in b_nodes if n.entity_id}
        if len(bound_ids) != 1:
            return _pack(
                ok=False,
                composition_credit="DENIED_AMBIGUOUS_BINDING",
                reasons=[f"ambiguous bindings={sorted(bound_ids)}"],
            )
        entity = next(iter(bound_ids))
        if entity not in a_entities or entity not in b_entities:
            return _pack(
                ok=False,
                composition_credit="DENIED_CROSS_ENTITY_INTERVALS",
                reasons=[
                    f"bound entity {entity} not present in both intervals",
                    f"A={sorted(a_entities)} B={sorted(b_entities)}",
                ],
            )

        supporting = [n for n in b_nodes if n.entity_id == entity and n.supports_answer]
        if not supporting:
            return _pack(
                ok=False,
                composition_credit="DENIED_ANSWER_UNSUPPORTED",
                reasons=["no B evidence for bound entity supports the answer"],
            )

        # Structural necessity hint: B has multiple entities so binding disambiguates.
        # Single-entity B → path may be valid but necessity is NOT implied (use masked tests).
        multi_b = len(b_entities) > 1
        if multi_b:
            reasons.append("B has multiple entities; binding from A disambiguates")
        else:
            reasons.append(
                "binding links A referent to B property, but B has a single entity — "
                "composition_necessary requires masked A-only/B-only tests"
            )

        return _pack(
            ok=True,
            composition_credit="STRONG_COMPOSITION" if multi_b else "PATH_VALID_NECESSITY_UNPROVEN",
            bound_entity=entity,
            reasons=reasons,
            evidence_path_valid=True,
            composition_necessary_hint=multi_b,
        )
