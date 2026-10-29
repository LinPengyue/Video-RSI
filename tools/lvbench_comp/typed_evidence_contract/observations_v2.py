"""Scene-local observations: A-local and B-local track IDs are disjoint.

Cross-scene identity exists ONLY in the scorer oracle map, never prewired
into agent-visible track_ids. Binding must use noisy attribute cues.
"""

from __future__ import annotations

import hashlib
import json
import random
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from .contracts import TimeSpan
from .executor import SimulatedWorld
from .observations import ObsEntity, ObsFact, ObservationBundle


@dataclass
class CrossSceneOracle:
    """Scorer-only correspondence A-local track ↔ B-local track ↔ gold."""

    scenario_id: str
    a_track_to_oracle: dict[str, str]
    b_track_to_oracle: dict[str, str]
    # Correct match pairs (a_tid, b_tid) — NEVER given to agent as hard IDs
    gold_matches: list[tuple[str, str]]
    gold_answer: Any
    gold_property: str
    public_context: dict[str, Any] = field(default_factory=dict)


def _tid(scenario: str, side: str, oracle_id: str, salt: str) -> str:
    h = hashlib.sha256(f"{scenario}|{side}|{oracle_id}|{salt}".encode()).hexdigest()[:10]
    return f"{side}_{h}"


def _attr_cues(oracle_id: str, side: str, rng: random.Random, noise: float = 0.3) -> list[str]:
    """Noisy visual/attribute cues — soft signal, not a hard ID.

    A-side keeps stronger appearance tokens; B-side keeps mostly viewpoint tokens
    plus at most a weak/noisy overlap so binding is nontrivial and B-only cannot
    freely reuse the A referring phrase.
    """
    strong = {
        "entity_x": ["purple_top", "short_hair", "holds_object_A"],
        "entity_y": ["pink_top", "long_hair", "holds_object_B"],
    }
    weak = {
        "entity_x": ["leftish", "medium_build"],
        "entity_y": ["rightish", "slender_build"],
    }
    view = [f"cam_{side}", f"lighting_{rng.choice(['warm', 'cool', 'dim'])}"]
    if side == "A":
        cues = list(strong.get(oracle_id, ["neutral"])) + view
    else:
        cues = list(weak.get(oracle_id, ["neutral"])) + view
        # Occasional weak overlap (not guaranteed) — hypothesis scorer may use it
        # No guaranteed copy of strong A tokens onto B (prevents B-only name reuse).
        if rng.random() < 0.15:
            cues.append(rng.choice(weak.get(oracle_id, ["neutral"])))
    if rng.random() < noise and cues:
        cues.pop(rng.randrange(len(cues)))
        cues.append(rng.choice(["blurry", "occluded", "back_view"]))
    rng.shuffle(cues)
    return cues


def project_scene_local(
    oracle: SimulatedWorld,
    *,
    scenario_id: str,
    gold_answer: Any,
    gold_property: str,
    salt: str = "v2",
    seed: int = 0,
    include_distractor_match_cues: bool = True,
    value_noise: bool = False,
) -> tuple[ObservationBundle, CrossSceneOracle]:
    """A facts get a_* tracks; B facts get b_* tracks — no shared track_id across sides."""
    rng = random.Random(seed)
    a_map: dict[str, str] = {}
    b_map: dict[str, str] = {}
    entities: dict[str, ObsEntity] = {}
    facts: list[ObsFact] = []

    for oid in oracle.entities:
        a_map[oid] = _tid(scenario_id, "a", oid, salt)
        b_map[oid] = _tid(scenario_id, "b", oid, salt)

    # Scene-local entity lists (surface forms are local nicknames, not global oracle names)
    for oid, ent in oracle.entities.items():
        a_tid, b_tid = a_map[oid], b_map[oid]
        a_cues = _attr_cues(oid, "A", rng)
        b_cues = _attr_cues(oid, "B", rng)
        # Local referring forms — do NOT copy global "the first speaker" into both sides identically
        # as a free cross-scene name bridge. Use side-local descriptors + attribute cues.
        entities[a_tid] = ObsEntity(
            track_id=a_tid,
            surface_forms=[f"person_in_A_{oid[-1]}", *a_cues[:2]],
            confidence=0.6 + 0.2 * rng.random(),
        )
        entities[b_tid] = ObsEntity(
            track_id=b_tid,
            surface_forms=[f"person_in_B_{oid[-1]}", *b_cues[:2]],
            confidence=0.6 + 0.2 * rng.random(),
        )

    for i, f in enumerate(oracle.facts):
        group = f.time.label if f.time.label in {"A", "B"} else ("A" if f.time.end_s <= 10 else "B")
        tid = a_map[f.entity_id] if group == "A" else b_map[f.entity_id]
        val = f.property_value
        if value_noise and rng.random() < 0.15 and group == "B":
            val = f"noisy_{val}"
        # Soft attribute cues + fact-local detector strings (may include unique_b_cue etc.).
        # Do NOT copy global oracle person names across both sides.
        cues = _attr_cues(f.entity_id, group, rng)
        local_extra = [c for c in f.referring_cues if c not in {"first speaker", "second speaker", "speaker", "speaker_a", "speaker_b"}]
        cues = list(dict.fromkeys(cues + local_extra))
        facts.append(
            ObsFact(
                obs_id=f"obs_{scenario_id}_{group}_{i}",
                track_id=tid,
                property_name=f.property_name,
                observed_value=val,
                time=deepcopy(f.time),
                modalities=list(f.modalities),
                referring_cues=cues,
                evidence_group=group,
            )
        )

    # Soft link hypotheses: unordered candidate pairs with scores — includes distractors
    gold_matches = [(a_map[oid], b_map[oid]) for oid in oracle.entities]
    link_hypotheses: list[dict[str, Any]] = []
    a_tids = list(a_map.values())
    b_tids = list(b_map.values())
    for a_tid in a_tids:
        for b_tid in b_tids:
            correct = (a_tid, b_tid) in gold_matches or (a_tid, b_tid) in [(g[0], g[1]) for g in gold_matches]
            # Score from cue overlap only
            a_cues = set(entities[a_tid].surface_forms)
            b_cues = set(entities[b_tid].surface_forms)
            overlap = len(a_cues & b_cues)
            score = 0.2 * overlap + (0.5 if correct else 0.0) * (0.4 + 0.3 * rng.random())
            if not include_distractor_match_cues and not correct:
                continue
            link_hypotheses.append(
                {
                    "a_track": a_tid,
                    "b_track": b_tid,
                    "score": round(min(1.0, score), 3),
                    "cue_overlap": sorted(a_cues & b_cues),
                    # Explicitly NOT a hard identity
                    "status": "HYPOTHESIS_ONLY",
                }
            )
    rng.shuffle(link_hypotheses)

    # Public context identical across masks — no side-specific oracle names
    public_context = {
        "domain": "synthetic_dual_interval",
        "available_properties": sorted({f.property_name for f in facts}),
        "note": "No global person names; binding requires cross-scene match hypotheses.",
    }

    bundle = ObservationBundle(entities=entities, facts=facts, link_hypotheses=link_hypotheses)
    # Assert: no track_id appears in both A and B facts
    a_ids = {f.track_id for f in facts if f.evidence_group == "A"}
    b_ids = {f.track_id for f in facts if f.evidence_group == "B"}
    if a_ids & b_ids:
        raise RuntimeError(f"cross-scene track bridge leaked: {a_ids & b_ids}")
    bundle.to_agent_dict()

    omap = CrossSceneOracle(
        scenario_id=scenario_id,
        a_track_to_oracle=a_map,
        b_track_to_oracle=b_map,
        gold_matches=gold_matches,
        gold_answer=gold_answer,
        gold_property=gold_property,
        public_context=public_context,
    )
    return bundle, omap


def mask_scene_local(
    bundle: ObservationBundle,
    keep_groups: set[str],
    *,
    public_context: dict[str, Any] | None = None,
) -> ObservationBundle:
    """Neutral mask: keep only facts in groups; entity list = those appearing in kept facts.

    Public context is identical metadata (not side-specific names).
    """
    kept_facts = [deepcopy(f) for f in bundle.facts if f.evidence_group in keep_groups]
    kept_tids = {f.track_id for f in kept_facts}
    entities = {tid: deepcopy(bundle.entities[tid]) for tid in kept_tids if tid in bundle.entities}
    # Link hypotheses only among surviving tracks
    links = [
        deepcopy(h)
        for h in bundle.link_hypotheses
        if h.get("a_track") in kept_tids and h.get("b_track") in kept_tids
    ]
    # If single-side mask, drop cross links entirely
    if keep_groups == {"A"} or keep_groups == {"B"}:
        links = []
    out = ObservationBundle(entities=entities, facts=kept_facts, link_hypotheses=links)
    # Attach public context as a non-entity annotation via link channel marker
    if public_context is not None:
        out.link_hypotheses = list(out.link_hypotheses) + [{"public_context": public_context, "status": "CONTEXT"}]
    return out


def assert_no_oracle_bridge(bundle: ObservationBundle) -> dict[str, Any]:
    a_ids = {f.track_id for f in bundle.facts if f.evidence_group == "A"}
    b_ids = {f.track_id for f in bundle.facts if f.evidence_group == "B"}
    return {
        "ok": not (a_ids & b_ids),
        "a_tracks": sorted(a_ids),
        "b_tracks": sorted(b_ids),
        "intersection": sorted(a_ids & b_ids),
        "n_link_hypotheses": sum(1 for h in bundle.link_hypotheses if h.get("status") == "HYPOTHESIS_ONLY"),
    }


def binding_impossible_from_ids_alone(bundle: ObservationBundle) -> bool:
    """Adversarial check: unique A/B track string equality cannot solve binding."""
    a_ids = {f.track_id for f in bundle.facts if f.evidence_group == "A"}
    b_ids = {f.track_id for f in bundle.facts if f.evidence_group == "B"}
    return len(a_ids & b_ids) == 0
