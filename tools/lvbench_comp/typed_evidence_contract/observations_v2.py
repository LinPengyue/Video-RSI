"""Scene-local observations: A-local and B-local track IDs are disjoint.

Cross-scene identity exists ONLY in the scorer oracle map, never prewired
into agent-visible track_ids or agent-visible link scores.
Binding must use noisy attribute / detector cues only.
"""

from __future__ import annotations

import hashlib
import random
import string
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .executor import SimulatedWorld
from .observations import ObsEntity, ObsFact, ObservationBundle

# Independent local nickname vocabularies — no shared oracle-derived suffix across A/B.
_A_NICKS = [
    "cedar", "maple", "oak", "pine", "birch", "willow", "ash", "elm", "spruce", "fir",
]
_B_NICKS = [
    "harbor", "ridge", "delta", "cove", "mesa", "fjord", "dune", "glen", "reef", "vale",
]


@dataclass
class CrossSceneOracle:
    """Scorer-only correspondence A-local track ↔ B-local track ↔ gold."""

    scenario_id: str
    a_track_to_oracle: dict[str, str]
    b_track_to_oracle: dict[str, str]
    # Correct match pairs (a_tid, b_tid) — NEVER given to agent as hard IDs or score boosts
    gold_matches: list[tuple[str, str]]
    gold_answer: Any
    gold_property: str
    public_context: dict[str, Any] = field(default_factory=dict)


def _tid(scenario: str, side: str, oracle_id: str, salt: str) -> str:
    h = hashlib.sha256(f"{scenario}|{side}|{oracle_id}|{salt}".encode()).hexdigest()[:10]
    return f"{side}_{h}"


def _local_nick(side: str, rng: random.Random, used: set[str]) -> str:
    pool = list(_A_NICKS if side == "A" else _B_NICKS)
    rng.shuffle(pool)
    for n in pool:
        if n not in used:
            used.add(n)
            return n
    # fallback unique token
    while True:
        tok = "".join(rng.choice(string.ascii_lowercase) for _ in range(5))
        if tok not in used:
            used.add(tok)
            return tok


def _attr_cues(
    oracle_id: str,
    side: str,
    rng: random.Random,
    *,
    noise: float = 0.3,
    lookalike: bool = False,
    shared_public_tokens: list[str] | None = None,
) -> list[str]:
    """Noisy visual/attribute cues — soft signal, not a hard ID.

    A-side keeps stronger appearance tokens; B-side keeps mostly viewpoint tokens
    plus optional weak/noisy overlap so binding is nontrivial.
    When lookalike=True, inject shared distractor tokens across wrong identities.
    """
    strong = {
        "entity_x": ["purple_top", "short_hair", "holds_object_A"],
        "entity_y": ["pink_top", "long_hair", "holds_object_B"],
        "entity_z": ["green_top", "curly_hair", "holds_object_C"],
    }
    weak = {
        "entity_x": ["leftish", "medium_build"],
        "entity_y": ["rightish", "slender_build"],
        "entity_z": ["centerish", "tall_build"],
    }
    view = [f"cam_{side}", f"lighting_{rng.choice(['warm', 'cool', 'dim'])}"]
    if side == "A":
        cues = list(strong.get(oracle_id, ["neutral"])) + view
    else:
        cues = list(weak.get(oracle_id, ["neutral"])) + view
        # Occasional weak identity-correlated cue (generative world correlation OK)
        if rng.random() < 0.35:
            cues.append(rng.choice(strong.get(oracle_id, ["neutral"])))
        elif rng.random() < 0.15:
            cues.append(rng.choice(weak.get(oracle_id, ["neutral"])))
    if shared_public_tokens:
        # Public visual tokens identical across scenes when deliberately generated
        cues.extend(shared_public_tokens)
    if lookalike and rng.random() < 0.7:
        # Adversarial: steal a strong cue from another entity
        other = [k for k in strong if k != oracle_id]
        if other:
            cues.append(rng.choice(strong[rng.choice(other)]))
    if rng.random() < noise and cues:
        cues.pop(rng.randrange(len(cues)))
        cues.append(rng.choice(["blurry", "occluded", "back_view"]))
    rng.shuffle(cues)
    return cues


def _cue_overlap_score(a_cues: set[str], b_cues: set[str], rng: random.Random) -> tuple[float, list[str]]:
    """Agent-visible score from observable cue overlap only — no gold term."""
    # Drop side-local camera tokens from overlap (not identity signal)
    drop = {c for c in (a_cues | b_cues) if c.startswith("cam_") or c.startswith("person_") or c.startswith("lighting_")}
    a = a_cues - drop
    b = b_cues - drop
    # Also drop independent nicknames (single-token local labels)
    nick_a = {c for c in a if c in _A_NICKS or (len(c) == 5 and c.isalpha() and c.islower())}
    nick_b = {c for c in b if c in _B_NICKS or (len(c) == 5 and c.isalpha() and c.islower())}
    a -= nick_a
    b -= nick_b
    overlap = sorted(a & b)
    # Jaccard-ish + small reproducible jitter from cues themselves (not gold)
    union = max(1, len(a | b))
    base = len(overlap) / union
    jitter_src = hashlib_sha(f"{sorted(a)}|{sorted(b)}|{rng.random():.6f}")
    jitter = (int(jitter_src[:4], 16) % 100) / 1000.0  # 0–0.099
    score = min(1.0, 0.15 + 0.7 * base + jitter)
    if not overlap:
        score = min(score, 0.22 + jitter * 0.5)
    return round(score, 3), overlap


def hashlib_sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


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
    lookalike_hard_negatives: bool = False,
    shared_public_tokens: list[str] | None = None,
) -> tuple[ObservationBundle, CrossSceneOracle]:
    """A facts get a_* tracks; B facts get b_* tracks — no shared track_id across sides.

    Agent-visible link scores use cue overlap only (no gold_matches boost).
    Surface forms use independent local nicknames (no shared oracle suffix).
    """
    rng = random.Random(seed)
    a_map: dict[str, str] = {}
    b_map: dict[str, str] = {}
    entities: dict[str, ObsEntity] = {}
    facts: list[ObsFact] = []
    used_a: set[str] = set()
    used_b: set[str] = set()

    for oid in oracle.entities:
        a_map[oid] = _tid(scenario_id, "a", oid, salt)
        b_map[oid] = _tid(scenario_id, "b", oid, salt)

    for oid, _ent in oracle.entities.items():
        a_tid, b_tid = a_map[oid], b_map[oid]
        a_cues = _attr_cues(
            oid, "A", rng, lookalike=lookalike_hard_negatives, shared_public_tokens=shared_public_tokens
        )
        b_cues = _attr_cues(
            oid, "B", rng, lookalike=lookalike_hard_negatives, shared_public_tokens=shared_public_tokens
        )
        nick_a = _local_nick("A", rng, used_a)
        nick_b = _local_nick("B", rng, used_b)
        entities[a_tid] = ObsEntity(
            track_id=a_tid,
            surface_forms=[nick_a, *a_cues[:2]],
            confidence=0.6 + 0.2 * rng.random(),
        )
        entities[b_tid] = ObsEntity(
            track_id=b_tid,
            surface_forms=[nick_b, *b_cues[:2]],
            confidence=0.6 + 0.2 * rng.random(),
        )

    for i, f in enumerate(oracle.facts):
        group = f.time.label if f.time.label in {"A", "B"} else ("A" if f.time.end_s <= 10 else "B")
        tid = a_map[f.entity_id] if group == "A" else b_map[f.entity_id]
        val = f.property_value
        if value_noise and rng.random() < 0.15 and group == "B":
            val = f"noisy_{val}"
        cues = _attr_cues(
            f.entity_id, group, rng, lookalike=lookalike_hard_negatives, shared_public_tokens=shared_public_tokens
        )
        local_extra = [
            c
            for c in f.referring_cues
            if c not in {"first speaker", "second speaker", "speaker", "speaker_a", "speaker_b"}
        ]
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

    # Soft link hypotheses: cue-overlap scores ONLY — gold_matches never enters score
    gold_matches = [(a_map[oid], b_map[oid]) for oid in oracle.entities]
    link_hypotheses: list[dict[str, Any]] = []
    a_tids = list(a_map.values())
    b_tids = list(b_map.values())
    for a_tid in a_tids:
        for b_tid in b_tids:
            a_bag = set(entities[a_tid].surface_forms)
            for f in facts:
                if f.track_id == a_tid:
                    a_bag.update(f.referring_cues)
            b_bag = set(entities[b_tid].surface_forms)
            for f in facts:
                if f.track_id == b_tid:
                    b_bag.update(f.referring_cues)
            score, overlap = _cue_overlap_score(a_bag, b_bag, rng)
            # Scorer-only annotation stripped from agent view via to_agent_dict if present;
            # we do NOT attach is_gold to agent hypotheses.
            if not include_distractor_match_cues:
                # Keep only pairs with some cue overlap (still no gold filter)
                if not overlap:
                    continue
            link_hypotheses.append(
                {
                    "a_track": a_tid,
                    "b_track": b_tid,
                    "score": score,
                    "cue_overlap": overlap,
                    "status": "HYPOTHESIS_ONLY",
                }
            )
    rng.shuffle(link_hypotheses)

    public_context = {
        "domain": "synthetic_dual_interval",
        "available_properties": sorted({f.property_name for f in facts}),
        "note": "No global person names; binding requires cross-scene match hypotheses from cues only.",
    }

    bundle = ObservationBundle(entities=entities, facts=facts, link_hypotheses=link_hypotheses)
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
    """Neutral mask: keep only facts in groups; entity list = those appearing in kept facts."""
    kept_facts = [deepcopy(f) for f in bundle.facts if f.evidence_group in keep_groups]
    kept_tids = {f.track_id for f in kept_facts}
    entities = {tid: deepcopy(bundle.entities[tid]) for tid in kept_tids if tid in bundle.entities}
    links = [
        deepcopy(h)
        for h in bundle.link_hypotheses
        if h.get("a_track") in kept_tids and h.get("b_track") in kept_tids
    ]
    if keep_groups == {"A"} or keep_groups == {"B"}:
        links = []
    out = ObservationBundle(entities=entities, facts=kept_facts, link_hypotheses=links)
    if public_context is not None:
        out.link_hypotheses = list(out.link_hypotheses) + [{"public_context": public_context, "status": "CONTEXT"}]
    return out


def assert_local_ids_disjoint(bundle: ObservationBundle) -> dict[str, Any]:
    """A/B track ID sets are disjoint (does NOT measure pairing correctness)."""
    a_ids = {f.track_id for f in bundle.facts if f.evidence_group == "A"}
    b_ids = {f.track_id for f in bundle.facts if f.evidence_group == "B"}
    return {
        "ok": not (a_ids & b_ids),
        "local_ids_disjoint": not (a_ids & b_ids),
        "a_tracks": sorted(a_ids),
        "b_tracks": sorted(b_ids),
        "intersection": sorted(a_ids & b_ids),
        "n_link_hypotheses": sum(1 for h in bundle.link_hypotheses if h.get("status") == "HYPOTHESIS_ONLY"),
    }


# Back-compat alias — old name checked intersection only
def assert_no_oracle_bridge(bundle: ObservationBundle) -> dict[str, Any]:
    return assert_local_ids_disjoint(bundle)


def binding_impossible_from_ids_alone(bundle: ObservationBundle) -> bool:
    a_ids = {f.track_id for f in bundle.facts if f.evidence_group == "A"}
    b_ids = {f.track_id for f in bundle.facts if f.evidence_group == "B"}
    return len(a_ids & b_ids) == 0


def pair_ranking_metrics(bundle: ObservationBundle, omap: CrossSceneOracle) -> dict[str, Any]:
    """Top-1 / top-k pair recall from agent-visible hypothesis scores vs scorer gold."""
    gold = set(omap.gold_matches)
    hyps = [h for h in bundle.link_hypotheses if h.get("status") == "HYPOTHESIS_ONLY"]
    # Per A-track: rank B candidates by score
    by_a: dict[str, list[dict[str, Any]]] = {}
    for h in hyps:
        by_a.setdefault(h["a_track"], []).append(h)
    top1_hits = 0
    topk_hits = 0
    k = 2
    n = 0
    for a_tid, cands in by_a.items():
        gold_b = {b for (a, b) in gold if a == a_tid}
        if not gold_b:
            continue
        n += 1
        ranked = sorted(cands, key=lambda h: float(h.get("score", 0)), reverse=True)
        if ranked and ranked[0]["b_track"] in gold_b:
            top1_hits += 1
        if any(h["b_track"] in gold_b for h in ranked[:k]):
            topk_hits += 1
    # Calibration: mean score of gold pairs vs non-gold
    gold_scores = [float(h["score"]) for h in hyps if (h["a_track"], h["b_track"]) in gold]
    nongold_scores = [float(h["score"]) for h in hyps if (h["a_track"], h["b_track"]) not in gold]
    return {
        "pair_accuracy_top1": top1_hits / max(1, n),
        "topk_pair_recall": topk_hits / max(1, n),
        "n_entities_ranked": n,
        "mean_gold_score": sum(gold_scores) / max(1, len(gold_scores)),
        "mean_nongold_score": sum(nongold_scores) / max(1, len(nongold_scores)),
        "pair_score_gap": (sum(gold_scores) / max(1, len(gold_scores)))
        - (sum(nongold_scores) / max(1, len(nongold_scores))),
    }


def agent_link_signature(bundle: ObservationBundle) -> str:
    """Canonical signature of agent-visible hypotheses (scores + pairs + overlaps)."""
    rows = []
    for h in bundle.link_hypotheses:
        if h.get("status") != "HYPOTHESIS_ONLY":
            continue
        rows.append(
            (
                h["a_track"],
                h["b_track"],
                round(float(h.get("score", 0)), 3),
                tuple(h.get("cue_overlap") or []),
            )
        )
    rows.sort()
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def permute_gold_matches(omap: CrossSceneOracle, perm: dict[str, str]) -> CrossSceneOracle:
    """Permute scorer oracle entity labels; agent bundle must stay unchanged."""
    # perm: old_oracle_id -> new_oracle_id for A side remapping of gold
    new_a = {perm.get(oid, oid): tid for oid, tid in omap.a_track_to_oracle.items()}
    # invert a_track_to_oracle was oid->tid; rebuild gold from tid maps
    # Actually a_track_to_oracle is oid -> tid. Remap oid keys.
    a_by_oid = {perm.get(oid, oid): tid for oid, tid in omap.a_track_to_oracle.items()}
    b_by_oid = dict(omap.b_track_to_oracle)  # leave B or also permute
    # Gold matches: match by remapped oid identity on A only (scorer confusion)
    # Better: permute which A maps to which oracle while keeping B fixed → changes gold pairs
    inv_a = {tid: oid for oid, tid in omap.a_track_to_oracle.items()}
    new_gold = []
    for a_tid, b_tid in omap.gold_matches:
        old_oid = inv_a[a_tid]
        new_oid = perm.get(old_oid, old_oid)
        # After perm, gold says a_tid (still same track) matches b of new_oid
        if new_oid in omap.b_track_to_oracle:
            new_gold.append((a_tid, omap.b_track_to_oracle[new_oid]))
        else:
            new_gold.append((a_tid, b_tid))
    return CrossSceneOracle(
        scenario_id=omap.scenario_id,
        a_track_to_oracle=a_by_oid,
        b_track_to_oracle=b_by_oid,
        gold_matches=new_gold,
        gold_answer=omap.gold_answer,
        gold_property=omap.gold_property,
        public_context=dict(omap.public_context),
    )


def rename_local_ids(bundle: ObservationBundle, omap: CrossSceneOracle, rng: random.Random) -> tuple[ObservationBundle, CrossSceneOracle]:
    """Independently rename A and B local track IDs; update gold map accordingly."""
    a_rename = {tid: f"a_{hashlib.sha256(f'renA|{tid}|{rng.random()}'.encode()).hexdigest()[:10]}" for tid in omap.a_track_to_oracle.values()}
    b_rename = {tid: f"b_{hashlib.sha256(f'renB|{tid}|{rng.random()}'.encode()).hexdigest()[:10]}" for tid in omap.b_track_to_oracle.values()}
    rename = {**a_rename, **b_rename}

    entities = {}
    for tid, ent in bundle.entities.items():
        nt = rename[tid]
        entities[nt] = ObsEntity(track_id=nt, surface_forms=list(ent.surface_forms), confidence=ent.confidence)
    facts = []
    for f in bundle.facts:
        nf = deepcopy(f)
        nf.track_id = rename[f.track_id]
        facts.append(nf)
    links = []
    for h in bundle.link_hypotheses:
        if h.get("status") != "HYPOTHESIS_ONLY":
            links.append(deepcopy(h))
            continue
        nh = deepcopy(h)
        nh["a_track"] = rename[h["a_track"]]
        nh["b_track"] = rename[h["b_track"]]
        links.append(nh)
    new_bundle = ObservationBundle(entities=entities, facts=facts, link_hypotheses=links)
    new_a = {oid: rename[tid] for oid, tid in omap.a_track_to_oracle.items()}
    new_b = {oid: rename[tid] for oid, tid in omap.b_track_to_oracle.items()}
    new_gold = [(rename[a], rename[b]) for a, b in omap.gold_matches]
    new_omap = CrossSceneOracle(
        scenario_id=omap.scenario_id,
        a_track_to_oracle=new_a,
        b_track_to_oracle=new_b,
        gold_matches=new_gold,
        gold_answer=omap.gold_answer,
        gold_property=omap.gold_property,
        public_context=dict(omap.public_context),
    )
    return new_bundle, new_omap
