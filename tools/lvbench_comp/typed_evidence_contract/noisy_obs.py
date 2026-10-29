"""Oracle facts (eval-only) vs noisy observations (agent-visible).

The synthetic agent must not silently read oracle entity_id / gold values
except through observation channels that can be corrupted.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .contracts import EntityCandidate, TimeSpan
from .executor import SimulatedWorld, WorldFact


@dataclass
class ObservationNoise:
    """Corruption applied when projecting oracle world → agent observations."""

    drop_entity_prob: float = 0.0
    misleading_caption: str | None = None
    lookalike_alias: str | None = None
    time_offset_s: float = 0.0
    forge_fact_id: str | None = None
    strip_audio_cues: bool = False
    scramble_names: bool = False
    seed_tag: str = ""


def project_observations(oracle: SimulatedWorld, noise: ObservationNoise | None = None) -> tuple[SimulatedWorld, dict[str, Any]]:
    """Return agent-visible world + leakage log (oracle ids still exist underneath for scoring)."""
    noise = noise or ObservationNoise()
    w = deepcopy(oracle)
    leakage: dict[str, Any] = {
        "used_oracle_entity_id_directly": False,
        "noise": noise.__dict__,
        "corruptions": [],
    }

    if noise.time_offset_s:
        for f in w.facts:
            f.time = TimeSpan(f.time.start_s + noise.time_offset_s, f.time.end_s + noise.time_offset_s, f.time.label)
        leakage["corruptions"].append("time_offset")

    if noise.misleading_caption:
        w.facts.append(
            WorldFact(
                "mislead_caption",
                "entity_y",
                "caption",
                noise.misleading_caption,
                TimeSpan(0, 5, "A"),
                referring_cues=[noise.misleading_caption],
            )
        )
        leakage["corruptions"].append("misleading_caption")

    if noise.lookalike_alias:
        # Add a lookalike that shares a surface form with the target
        w.entities["entity_lookalike"] = EntityCandidate(
            "entity_lookalike",
            noise.lookalike_alias,
            aliases=[noise.lookalike_alias, "speaker"],
            confidence=0.5,
        )
        leakage["corruptions"].append("lookalike_alias")

    if noise.forge_fact_id:
        w.facts.append(
            WorldFact(
                noise.forge_fact_id,
                "entity_y",
                "action",
                "FORGED_ACTION",
                TimeSpan(25, 30, "B"),
                referring_cues=["forged"],
            )
        )
        leakage["corruptions"].append("forged_evidence")

    if noise.scramble_names:
        for e in w.entities.values():
            e.referring_expression = f"blurred_person_{e.entity_id[-1]}"
            e.aliases = []
        leakage["corruptions"].append("scramble_names")

    if noise.strip_audio_cues:
        for f in w.facts:
            f.modalities = [m for m in f.modalities if m != "audio"] or ["visual"]
            f.referring_cues = [c for c in f.referring_cues if "bark" not in c and "audio" not in c]
        leakage["corruptions"].append("strip_audio")

    return w, leakage


def make_family_worlds() -> dict[str, SimulatedWorld]:
    """Several independently generated scenario families (oracle)."""
    families: dict[str, SimulatedWorld] = {}

    def base(ax: str, ay: str, loc_x: str = "stage_left", *, audio: bool = False) -> SimulatedWorld:
        ents = {
            "entity_x": EntityCandidate("entity_x", "the first speaker", aliases=["speaker_a"], confidence=0.9),
            "entity_y": EntityCandidate("entity_y", "the second speaker", aliases=["speaker_b"], confidence=0.9),
        }
        facts = [
            WorldFact("a1", "entity_x", "role_event", "speaks_first", TimeSpan(0, 5, "A"), referring_cues=["first speaker", "opens the meeting"]),
            WorldFact("a2", "entity_y", "role_event", "speaks_second", TimeSpan(0, 5, "A"), referring_cues=["second speaker"]),
            WorldFact("b1", "entity_x", "action", ax, TimeSpan(25, 30, "B"), referring_cues=["later action"]),
            WorldFact("b2", "entity_y", "action", ay, TimeSpan(25, 30, "B"), referring_cues=["later action other"]),
            WorldFact("l1", "entity_x", "location", loc_x, TimeSpan(25, 30, "B"), referring_cues=["location"]),
            WorldFact("l2", "entity_y", "location", "stage_right", TimeSpan(25, 30, "B"), referring_cues=["location other"]),
        ]
        if audio:
            facts.append(
                WorldFact(
                    "aud1",
                    "entity_x",
                    "audio_event",
                    "bark_burst",
                    TimeSpan(0, 5, "A"),
                    modalities=["audio"],
                    referring_cues=["bark", "audio cue"],
                )
            )
            ents["entity_x"].aliases = list(ents["entity_x"].aliases) + ["bark source"]
        return SimulatedWorld(facts=facts, entities=ents)

    families["meeting_jacket"] = base("removes_jacket", "waves_hand")
    families["concert_bow"] = base("takes_bow", "claps", loc_x="orchestra_pit")
    families["lab_point"] = base("points_chart", "nods", loc_x="whiteboard")
    families["av_bark"] = base("fetches_stick", "sits", audio=True)
    return families
