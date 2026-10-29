"""Oracle-free observation interface for the synthetic agent.

Oracle SimulatedWorld (with gold entity_id / property values) is scorer-only.
The agent receives ObservationBundle with ephemeral track IDs and surface cues only.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from .contracts import TimeSpan
from .executor import SimulatedWorld, WorldFact


@dataclass
class ObsEntity:
    """Agent-visible entity hypothesis — no oracle entity_id."""

    track_id: str
    surface_forms: list[str]
    confidence: float = 0.5


@dataclass
class ObsFact:
    """Agent-visible observation — no gold property_value as privileged field name.

    `observed_value` is what a noisy detector reports; may be wrong/missing.
    Linking to other observations uses track_id only.
    """

    obs_id: str
    track_id: str
    property_name: str
    observed_value: Any
    time: TimeSpan
    modalities: list[str] = field(default_factory=lambda: ["visual"])
    referring_cues: list[str] = field(default_factory=list)
    evidence_group: str = ""  # A | B | context


@dataclass
class ObservationBundle:
    entities: dict[str, ObsEntity]
    facts: list[ObsFact]
    # Soft linking hypotheses only (track_id pairs), never oracle ids
    link_hypotheses: list[dict[str, Any]] = field(default_factory=list)

    def facts_in(self, span: TimeSpan | None = None) -> list[ObsFact]:
        if span is None:
            return list(self.facts)
        return [f for f in self.facts if f.time.overlaps(span)]

    def facts_in_groups(self, groups: set[str]) -> list[ObsFact]:
        return [f for f in self.facts if f.evidence_group in groups]

    def to_agent_dict(self) -> dict[str, Any]:
        """Serialize agent view; assert no oracle keys."""
        payload = {
            "entities": {k: asdict(v) for k, v in self.entities.items()},
            "facts": [asdict(f) for f in self.facts],
            "link_hypotheses": self.link_hypotheses,
        }
        blob = json.dumps(payload)
        forbidden = ("entity_x", "entity_y", "oracle", "gold_answer", "entity_id")
        # entity_id string must not appear as a field name in serialized agent view
        if '"entity_id"' in blob or '"gold_' in blob:
            raise RuntimeError("oracle field leaked into agent observation serialization")
        for tok in ("entity_x", "entity_y"):
            if tok in blob:
                raise RuntimeError(f"oracle stable id {tok} leaked into observations")
        return payload


@dataclass
class OracleMap:
    """Scorer-only: ephemeral track_id → oracle entity_id; obs → gold values."""

    track_to_oracle: dict[str, str]
    gold_answer: Any
    gold_property: str
    scenario_id: str


def _ephemeral_track(scenario_id: str, oracle_entity_id: str, salt: str) -> str:
    h = hashlib.sha256(f"{scenario_id}:{oracle_entity_id}:{salt}".encode()).hexdigest()[:10]
    return f"trk_{h}"


def project_oracle_free(
    oracle: SimulatedWorld,
    *,
    scenario_id: str,
    gold_answer: Any,
    gold_property: str,
    salt: str = "s0",
    noise_drop_tracks: set[str] | None = None,
    misleading_cue: str | None = None,
) -> tuple[ObservationBundle, OracleMap]:
    """Build agent observations without oracle entity ids or stable cross-family ids."""
    track_to_oracle: dict[str, str] = {}
    oracle_to_track: dict[str, str] = {}
    entities: dict[str, ObsEntity] = {}
    for oid, ent in oracle.entities.items():
        tid = _ephemeral_track(scenario_id, oid, salt)
        oracle_to_track[oid] = tid
        track_to_oracle[tid] = oid
        if noise_drop_tracks and tid in noise_drop_tracks:
            continue
        entities[tid] = ObsEntity(
            track_id=tid,
            surface_forms=[ent.referring_expression, *list(ent.aliases)],
            confidence=float(ent.confidence),
        )

    facts: list[ObsFact] = []
    for i, f in enumerate(oracle.facts):
        tid = oracle_to_track.get(f.entity_id)
        if tid is None or tid not in entities:
            continue
        group = f.time.label if f.time.label in {"A", "B"} else ("A" if f.time.end_s <= 10 else "B")
        facts.append(
            ObsFact(
                obs_id=f"obs_{scenario_id}_{i}",
                track_id=tid,
                property_name=f.property_name,
                observed_value=f.property_value,  # detector readout; scorer compares separately
                time=deepcopy(f.time),
                modalities=list(f.modalities),
                referring_cues=list(f.referring_cues),
                evidence_group=group,
            )
        )

    if misleading_cue:
        # Attach misleading cue to a non-target track if possible
        other = next((t for t in entities if track_to_oracle[t] != track_to_oracle.get(next(iter(entities)))), None)
        if other is None and entities:
            other = next(iter(entities))
        if other is not None:
            facts.append(
                ObsFact(
                    obs_id=f"obs_{scenario_id}_mislead",
                    track_id=other,
                    property_name="caption",
                    observed_value=misleading_cue,
                    time=TimeSpan(0, 5, "A"),
                    referring_cues=[misleading_cue],
                    evidence_group="A",
                )
            )

    bundle = ObservationBundle(entities=entities, facts=facts)
    bundle.to_agent_dict()  # fail fast on leaks
    omap = OracleMap(
        track_to_oracle=track_to_oracle,
        gold_answer=gold_answer,
        gold_property=gold_property,
        scenario_id=scenario_id,
    )
    return bundle, omap


def mask_observations(bundle: ObservationBundle, keep_groups: set[str]) -> ObservationBundle:
    """Neutral mask: only change which evidence groups are exposed. No alias rewriting."""
    b = ObservationBundle(
        entities=deepcopy(bundle.entities),
        facts=[deepcopy(f) for f in bundle.facts if f.evidence_group in keep_groups],
        link_hypotheses=deepcopy(bundle.link_hypotheses),
    )
    # Drop entities that no longer appear in any exposed fact (optional; keep lexicon intact)
    return b
