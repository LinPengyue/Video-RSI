"""Executable program / dependency schemas for true structural leave-out.

Text signature labels alone are insufficient. Two tasks with different
`signature` strings but identical executed op DAGs must hash equal and
must NOT count as Unseen compositional generalization.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OpNode:
    op: str
    role: str  # e.g. bind_referent | track_forward | track_reverse | query_prop | verify
    inputs_schema: tuple[str, ...] = ()
    modality: str = "visual"


@dataclass(frozen=True)
class DepEdge:
    src_role: str
    dst_role: str
    kind: str  # entity_id | time_span | evidence_ref | answer


@dataclass
class ProgramSchema:
    """Executable operator dependency graph (not a free-text signature)."""

    schema_id: str
    nodes: list[OpNode]
    edges: list[DepEdge]
    direction: str  # forward | reverse
    entity_cardinality: str  # single | multi_candidate_b
    modalities: tuple[str, ...] = ("visual",)
    notes: str = ""

    def graph_payload(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "op": n.op,
                    "role": n.role,
                    "inputs_schema": list(n.inputs_schema),
                    "modality": n.modality,
                }
                for n in self.nodes
            ],
            "edges": [{"src": e.src_role, "dst": e.dst_role, "kind": e.kind} for e in self.edges],
            "direction": self.direction,
            "entity_cardinality": self.entity_cardinality,
            "modalities": list(self.modalities),
        }

    def graph_hash(self) -> str:
        blob = json.dumps(self.graph_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def compile_program(self, *, referring: str, property_name: str, answer_slot: str = "from_query") -> list[dict[str, Any]]:
        """Compile genome-independent default program from schema roles."""
        program: list[dict[str, Any]] = []
        for n in self.nodes:
            if n.op == "locate_event":
                program.append({"op": "locate_event", "inputs": {"cue": referring}, "role": n.role})
            elif n.op == "resolve_reference":
                program.append({"op": "resolve_reference", "inputs": {"referring_expression": referring}, "role": n.role})
            elif n.op == "track_identity":
                span = {"start_s": 25.0, "end_s": 30.0} if self.direction == "forward" else {"start_s": 0.0, "end_s": 5.0}
                # Reverse: bind at late span then track earlier.
                if n.role == "track_reverse":
                    span = {"start_s": 0.0, "end_s": 5.0}
                elif n.role == "track_forward":
                    span = {"start_s": 25.0, "end_s": 30.0}
                program.append({"op": "track_identity", "inputs": {"target_span": span}, "role": n.role})
            elif n.op == "query_property":
                program.append({"op": "query_property", "inputs": {"property_name": property_name}, "role": n.role})
            elif n.op == "verify_answer":
                ia, ib = ({"start_s": 0.0, "end_s": 5.0}, {"start_s": 25.0, "end_s": 30.0})
                if self.direction == "reverse":
                    # Index from late event (B) then verify early property (A) still as dual intervals.
                    pass
                program.append(
                    {
                        "op": "verify_answer",
                        "inputs": {"interval_a": ia, "interval_b": ib, "answer_slot": answer_slot},
                        "role": n.role,
                    }
                )
        return program


# --- Canonical schemas used in stress suite ---

SCHEMA_FORWARD_PERSON_ACTION = ProgramSchema(
    schema_id="forward_person_action",
    nodes=[
        OpNode("resolve_reference", "bind_referent", ("referring_expression",)),
        OpNode("track_identity", "track_forward", ("entity_id", "target_span")),
        OpNode("query_property", "query_prop", ("entity_id", "property_name")),
        OpNode("verify_answer", "verify", ("answer", "interval_a", "interval_b")),
    ],
    edges=[
        DepEdge("bind_referent", "track_forward", "entity_id"),
        DepEdge("track_forward", "query_prop", "entity_id"),
        DepEdge("query_prop", "verify", "answer"),
        DepEdge("bind_referent", "verify", "evidence_ref"),
    ],
    direction="forward",
    entity_cardinality="multi_candidate_b",
    modalities=("visual",),
)

SCHEMA_FORWARD_PERSON_LOCATION = ProgramSchema(
    schema_id="forward_person_location",
    nodes=[
        OpNode("resolve_reference", "bind_referent", ("referring_expression",)),
        OpNode("track_identity", "track_forward", ("entity_id", "target_span")),
        OpNode("query_property", "query_location", ("entity_id", "property_name=location")),
        OpNode("verify_answer", "verify", ("answer", "interval_a", "interval_b")),
    ],
    edges=[
        DepEdge("bind_referent", "track_forward", "entity_id"),
        DepEdge("track_forward", "query_location", "entity_id"),
        DepEdge("query_location", "verify", "answer"),
        DepEdge("bind_referent", "verify", "evidence_ref"),
    ],
    direction="forward",
    entity_cardinality="multi_candidate_b",
    modalities=("visual",),
)

SCHEMA_REVERSE_EVENT_TO_PRIOR_ACTION = ProgramSchema(
    schema_id="reverse_event_to_prior_action",
    nodes=[
        OpNode("locate_event", "index_late_event", ("cue",), "visual"),
        OpNode("resolve_reference", "bind_referent", ("referring_expression",)),
        OpNode("track_identity", "track_reverse", ("entity_id", "target_span")),
        OpNode("query_property", "query_early_prop", ("entity_id", "property_name")),
        OpNode("verify_answer", "verify", ("answer", "interval_a", "interval_b")),
    ],
    edges=[
        DepEdge("index_late_event", "bind_referent", "evidence_ref"),
        DepEdge("bind_referent", "track_reverse", "entity_id"),
        DepEdge("track_reverse", "query_early_prop", "entity_id"),
        DepEdge("query_early_prop", "verify", "answer"),
    ],
    direction="reverse",
    entity_cardinality="multi_candidate_b",
    modalities=("visual",),
    notes="Held-out structure: late-event index then reverse track — not a label rename of forward DAG.",
)

SCHEMA_AV_REID_THEN_QUERY = ProgramSchema(
    schema_id="av_reid_then_query",
    nodes=[
        OpNode("locate_event", "index_audio_cue", ("cue",), "audio"),
        OpNode("resolve_reference", "bind_av", ("referring_expression",), "audio+visual"),
        OpNode("track_identity", "track_forward", ("entity_id", "target_span"), "visual"),
        OpNode("query_property", "query_prop", ("entity_id", "property_name"), "visual"),
        OpNode("verify_answer", "verify", ("answer", "interval_a", "interval_b"), "audio+visual"),
    ],
    edges=[
        DepEdge("index_audio_cue", "bind_av", "evidence_ref"),
        DepEdge("bind_av", "track_forward", "entity_id"),
        DepEdge("track_forward", "query_prop", "entity_id"),
        DepEdge("query_prop", "verify", "answer"),
    ],
    direction="forward",
    entity_cardinality="multi_candidate_b",
    modalities=("audio", "visual"),
    notes="Held-out structure: audio locate before visual bind.",
)


def assert_structural_leave_out(train: list[ProgramSchema], held_out: list[ProgramSchema]) -> dict[str, Any]:
    train_hashes = {s.schema_id: s.graph_hash() for s in train}
    held_hashes = {s.schema_id: s.graph_hash() for s in held_out}
    leaked = sorted(set(train_hashes.values()) & set(held_hashes.values()))
    return {
        "ok": not leaked,
        "train_hashes": train_hashes,
        "held_out_hashes": held_hashes,
        "leaked_graph_hashes": leaked,
        "note": "Text signature overlap is irrelevant if graph hashes differ; hash collision = invalid Unseen claim.",
    }
