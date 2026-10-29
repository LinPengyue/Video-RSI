"""Generic typed evidence contracts for compositional video reasoning.

These interfaces are intentionally item-agnostic: no TB-/CG- specific fields.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class OperationName(str, Enum):
    LOCATE_EVENT = "locate_event"
    RESOLVE_REFERENCE = "resolve_reference"
    TRACK_IDENTITY = "track_identity"
    QUERY_PROPERTY = "query_property"
    VERIFY_ANSWER = "verify_answer"


class AmbiguityFlag(str, Enum):
    NONE = "none"
    MULTI_CANDIDATE = "multi_candidate"
    LOW_VISIBILITY = "low_visibility"
    NAME_LEAK = "name_leak"
    SINGLE_CLIP_SUFFICIENT = "single_clip_sufficient"
    EVIDENCE_CONFLICT = "evidence_conflict"
    MISSING_EVIDENCE = "missing_evidence"


@dataclass
class TimeSpan:
    start_s: float
    end_s: float
    label: str = ""

    def overlaps(self, other: "TimeSpan") -> bool:
        return self.start_s < other.end_s and other.start_s < self.end_s


@dataclass
class EvidenceRef:
    evidence_id: str
    source: str  # e.g. VIDEO_CLIP / OFFICIAL_QA / SIMULATED
    time: TimeSpan | None = None
    modality: str = "visual"  # visual | audio | text
    description: str = ""


@dataclass
class EntityCandidate:
    entity_id: str
    referring_expression: str
    aliases: list[str] = field(default_factory=list)
    confidence: float = 0.0
    bound_evidence_ids: list[str] = field(default_factory=list)
    ambiguity: AmbiguityFlag = AmbiguityFlag.NONE


@dataclass
class OperationRequest:
    op: OperationName
    inputs: dict[str, Any]
    budget_remaining: int = 3


@dataclass
class OperationResult:
    op: OperationName
    ok: bool
    outputs: dict[str, Any] = field(default_factory=dict)
    evidence: list[EvidenceRef] = field(default_factory=list)
    entity_candidates: list[EntityCandidate] = field(default_factory=list)
    ambiguity: AmbiguityFlag = AmbiguityFlag.NONE
    failure_code: str | None = None
    message: str = ""
    budget_spent: int = 1

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["op"] = self.op.value
        payload["ambiguity"] = self.ambiguity.value
        for ent in payload.get("entity_candidates", []):
            ent["ambiguity"] = ent["ambiguity"].value if hasattr(ent["ambiguity"], "value") else ent["ambiguity"]
        return payload


# Shared memory keys used across ops (generic compositional state).
MEMORY_KEYS = (
    "score_or_state",
    "bound_entity",
    "selected_events",
    "excluded_events",
    "pending_gaps",
    "evidence_index",
    "relations",
    "tool_calls",
)
