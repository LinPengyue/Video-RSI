"""Executable evidence-dependency checks for composition credit.

Rule of thumb:
  Evidence A → Entity Binding → Evidence B → Answer
Two timestamps alone never grant strong composition success.
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
        """Return composition credit decision with reasons."""
        reasons: list[str] = []
        a_nodes = [n for n in self.nodes.values() if n.interval_label == "A"]
        b_nodes = [n for n in self.nodes.values() if n.interval_label == "B"]

        if any(n.forged for n in self.nodes.values()):
            return {
                "ok": False,
                "composition_credit": "DENIED_FORGED_EVIDENCE",
                "reasons": ["forged evidence present"],
            }
        if not a_nodes and not b_nodes:
            return {
                "ok": False,
                "composition_credit": "DENIED_MISSING_EVIDENCE",
                "reasons": ["missing Evidence A and B"],
            }
        if not a_nodes or not b_nodes:
            # Single-interval answerability is a control path — never STRONG composition.
            if any(n.supports_answer for n in self.nodes.values()):
                missing = "A" if not a_nodes else "B"
                return {
                    "ok": True,
                    "composition_credit": "CONTROL_ONLY_SINGLE_INTERVAL",
                    "reasons": [f"answer supported with only interval {'B' if missing == 'A' else 'A'}; missing {missing}"],
                }
            return {
                "ok": False,
                "composition_credit": "DENIED_MISSING_A" if not a_nodes else "DENIED_MISSING_B",
                "reasons": [f"missing Evidence {'A' if not a_nodes else 'B'}"],
            }

        if not self.bindings:
            reasons.append("no entity binding from A to B")
            # If B alone supports answer, mark shortcut control.
            if any(n.supports_answer for n in b_nodes):
                return {
                    "ok": True,
                    "composition_credit": "CONTROL_ONLY_B_SHORTCUT",
                    "reasons": reasons + ["B alone supports answer"],
                }
            return {
                "ok": False,
                "composition_credit": "DENIED_NO_BINDING",
                "reasons": reasons,
            }

        bound_ids = {e.entity_id for e in self.bindings}
        a_entities = {n.entity_id for n in a_nodes if n.entity_id}
        b_entities = {n.entity_id for n in b_nodes if n.entity_id}
        if len(bound_ids) != 1:
            return {
                "ok": False,
                "composition_credit": "DENIED_AMBIGUOUS_BINDING",
                "reasons": [f"ambiguous bindings={sorted(bound_ids)}"],
            }
        entity = next(iter(bound_ids))
        if entity not in a_entities or entity not in b_entities:
            return {
                "ok": False,
                "composition_credit": "DENIED_CROSS_ENTITY_INTERVALS",
                "reasons": [
                    f"bound entity {entity} not present in both intervals",
                    f"A={sorted(a_entities)} B={sorted(b_entities)}",
                ],
            }

        supporting = [n for n in b_nodes if n.entity_id == entity and n.supports_answer]
        if not supporting:
            return {
                "ok": False,
                "composition_credit": "DENIED_ANSWER_UNSUPPORTED",
                "reasons": ["no B evidence for bound entity supports the answer"],
            }

        # Strong composition only when A binding is necessary: B evidence without
        # the referring path would be ambiguous or unbound.
        if len(b_entities) > 1:
            reasons.append("B has multiple entities; binding from A disambiguates")
        else:
            reasons.append("binding links A referent to B property")

        return {
            "ok": True,
            "composition_credit": "STRONG_COMPOSITION",
            "bound_entity": entity,
            "reasons": reasons,
        }
