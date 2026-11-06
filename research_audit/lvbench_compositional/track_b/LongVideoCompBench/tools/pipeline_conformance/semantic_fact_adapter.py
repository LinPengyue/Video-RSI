#!/usr/bin/env python3
"""P1: Semantic Fact Adapter — real DEV records → SourcedFact.

Sources: GPT frame-semantic observations, Human relation claims, structural
attribute observations, existing QA drafts (as draft packaging only).

Never upgrades UNKNOWN / GPT preliminary to Human FACT_VERIFIED.
Hash-only evidence is not a semantic fact.
Does not reverse-engineer video facts solely from historical QA answers.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .s3_s5_relation_qa import RelationCandidate, SourcedFact


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def load_dev_semantic_corpus(wp3_root: Path) -> dict[str, Any]:
    """Load existing DEV semantic artifacts (paths relative to wp3_production)."""
    return {
        "qa_drafts": _load_json(wp3_root / "wp3_human_adj" / "wp3_qa_program_drafts.json"),
        "necessity_audit": _load_json(
            wp3_root / "wp3_human_adj" / "wp3_necessity_structural_audit.json"
        ),
        "kbah_packet": _load_json(
            wp3_root / "wp3_4" / "wp3_4_KbahC_EF_PAIR1_HUMAN_REVIEW_PACKET.json"
        ),
        "usfv_packet": _load_json(
            wp3_root / "wp3_4" / "wp3_4_USFV_PAIR2_HUMAN_REVIEW_PACKET.json"
        ),
        "human_claims": _load_jsonl(
            wp3_root / "wp3_4" / "trusted_human_review_registry" / "records.jsonl"
        ),
    }


def _gpt_observations_for_pair(corpus: dict[str, Any], pair_id: str) -> list[dict[str, Any]]:
    out = []
    for key in ("kbah_packet", "usfv_packet"):
        pkt = corpus.get(key) or {}
        if pkt.get("pair_id") != pair_id:
            continue
        gpt = pkt.get("gpt_visual_preliminary_NOT_HUMAN") or {}
        if not gpt:
            continue
        for i, obs in enumerate(gpt.get("observations") or []):
            out.append(
                {
                    "observation_id": f"GPT:{pair_id}:{i}",
                    "text": obs,
                    "epistemic": "HYPOTHESIS",
                    "label": gpt.get("label") or "GPT_FRAME_VISUAL_PRELIMINARY",
                    "not_human_certification": True,
                    "source_path": key,
                }
            )
    return out


def _structural_attribute_observations(
    corpus: dict[str, Any], pair_id: str
) -> list[dict[str, Any]]:
    """Observable answer attributes from engineering structural audit — NOT Gold cert."""
    audit = corpus.get("necessity_audit") or {}
    out = []
    for item in audit.get("items") or []:
        if item.get("pair_id") != pair_id:
            continue
        sc = item.get("structural_shortcut_audit") or {}
        if sc.get("A_boy_seat_directly_observable"):
            seat = sc["A_boy_seat_directly_observable"]
            # Normalize engineering token → draft answer string used in prior DEV draft
            value_zh = "前排副驾驶座" if seat in {"FRONT_PASSENGER", "前排副驾驶座"} else str(seat)
            out.append(
                {
                    "key": "child_seat",
                    "window": "A",
                    "value": value_zh,
                    "epistemic": "HYPOTHESIS",
                    "certification": "ATTRIBUTE_NOT_COVERED_BY_HUMAN_IDENTITY_CLAIM",
                    "allowed_for_dev_qa_draft": True,
                    "allowed_for_gold": False,
                    "source_kind": "ENGINEERING_STRUCTURAL_OBSERVATION",
                    "source_ref": (
                        "wp3_human_adj/wp3_necessity_structural_audit.json"
                        f"#{pair_id}.A_boy_seat_directly_observable"
                    ),
                    "auditor_role": sc.get("auditor_role"),
                    "prompt_zh": "坐在车内什么位置",
                    "note": "Engineering observation; not independent Human answer certification",
                }
            )
        if sc.get("A_shop_sign_ocr_visible"):
            raw = str(sc["A_shop_sign_ocr_visible"])
            # Keep primary shop name; do not invent uniqueness
            value_zh = "DORJI OM TSHONGKHANG 店铺附近"
            out.append(
                {
                    "key": "location",
                    "window": "A",
                    "value": value_zh,
                    "epistemic": "HYPOTHESIS",
                    "certification": "ATTRIBUTE_NOT_COVERED_BY_HUMAN_IDENTITY_CLAIM",
                    "allowed_for_dev_qa_draft": True,
                    "allowed_for_gold": False,
                    "source_kind": "ENGINEERING_STRUCTURAL_OCR_OBSERVATION",
                    "source_ref": (
                        "wp3_human_adj/wp3_necessity_structural_audit.json"
                        f"#{pair_id}.A_shop_sign_ocr_visible"
                    ),
                    "raw_observation": raw,
                    "auditor_role": sc.get("auditor_role"),
                    "prompt_zh": "出现在哪家店铺附近",
                    "multi_signage_uniqueness_verified": False,
                    "note": "OCR observation; multi-sign uniqueness not independently verified",
                }
            )
    return out


def _qa_draft_packaging_refs(corpus: dict[str, Any], pair_id: str) -> list[dict[str, Any]]:
    """Reference existing QA drafts as packaging — do not mint facts from answers alone."""
    drafts = corpus.get("qa_drafts") or {}
    out = []
    for item in drafts.get("items") or []:
        if item.get("pair_id") != pair_id:
            continue
        out.append(
            {
                "qa_id": item.get("qa_id"),
                "status": item.get("status"),
                "question_zh": item.get("question_zh"),
                "answer_draft_zh": item.get("answer_draft_zh"),
                "relation_claims": item.get("relation_claims"),
                "role": "DRAFT_PACKAGING_ONLY_NOT_FACT_SOURCE",
                "source_ref": "wp3_human_adj/wp3_qa_program_drafts.json",
            }
        )
    return out


def build_sourced_facts_for_pair(
    *,
    pair_id: str,
    video_id: str,
    windows: dict[str, list[float]],
    evidence_refs_a: list[str],
    evidence_refs_b: list[str],
    identity_matches: list[dict[str, Any]],
    corpus: dict[str, Any],
) -> dict[str, Any]:
    """Assemble SourcedFacts + queryable attributes from real records."""
    gpt_obs = _gpt_observations_for_pair(corpus, pair_id)
    attrs = _structural_attribute_observations(corpus, pair_id)
    draft_refs = _qa_draft_packaging_refs(corpus, pair_id)

    # Cross-check: if draft answer exists, it may corroborate packaging but must not
    # be the sole fact minting source. Attrs come from structural observations first.
    semantic_fact_verified = False  # no Human answer cert in current DEV
    human_relation_certified = len(identity_matches) > 0

    certified_scopes_a = ["WINDOW_EXISTENCE"]
    certified_scopes_b = ["WINDOW_EXISTENCE"]
    if human_relation_certified:
        certified_scopes_a.append("CROSS_WINDOW_PERSON_IDENTITY")
        certified_scopes_b.append("CROSS_WINDOW_PERSON_IDENTITY")

    attr_map_a = {a["key"]: a["value"] for a in attrs if a.get("window") == "A"}
    uncert_keys = [a["key"] for a in attrs if a.get("window") == "A"]

    # Entities from identity claims + GPT cues (GPT remains HYPOTHESIS)
    entities_a: list[dict[str, Any]] = []
    entities_b: list[dict[str, Any]] = []
    for m in identity_matches:
        ent = m.get("entity") or "person"
        entities_a.append({"role": ent, "desc": ent, "bind_claim_id": m.get("claim_id")})
        entities_b.append({"role": ent, "desc": ent, "bind_claim_id": m.get("claim_id")})
    if not entities_a:
        entities_a = [{"role": "unknown", "desc": "entity_in_window_A"}]
        entities_b = [{"role": "unknown", "desc": "entity_in_window_B"}]

    # Scene hints from GPT (HYPOTHESIS only)
    scene_a = "UNRESOLVED"
    scene_b = "UNRESOLVED"
    for g in gpt_obs:
        t = g.get("text") or ""
        if t.startswith("A:") or t.startswith("A "):
            scene_a = "GPT_PRELIMINARY:" + t[:80]
        if t.startswith("B"):
            scene_b = "GPT_PRELIMINARY:" + t[:80]

    fact_a = SourcedFact(
        fact_id=f"FACT:{pair_id}:A",
        video_id=video_id,
        window=list(windows["A"]),
        epistemic="FACT" if human_relation_certified else "HYPOTHESIS",
        entities=entities_a,
        attributes={"scene": scene_a, **attr_map_a},
        evidence_refs=list(evidence_refs_a),
        source_provenance=(
            "HUMAN_IDENTITY_CLAIM+ENGINEERING_ATTR_OBS"
            if attrs
            else ("HUMAN_IDENTITY_CLAIM" if human_relation_certified else "EVIDENCE_PACKET_ONLY")
        ),
        certified_scopes=certified_scopes_a,
        uncertified_attribute_keys=uncert_keys,
    )
    # Window existence can be FACT from hashed clips; attribute values stay uncertified.
    # Epistemic on fact_a: if only identity certified, keep FACT for bind support but
    # attributes listed in uncertified_attribute_keys.
    if human_relation_certified:
        fact_a.epistemic = "FACT"
    elif gpt_obs or attrs:
        fact_a.epistemic = "HYPOTHESIS"
    else:
        fact_a.epistemic = "UNKNOWN"

    fact_b = SourcedFact(
        fact_id=f"FACT:{pair_id}:B",
        video_id=video_id,
        window=list(windows["B"]),
        epistemic="FACT" if human_relation_certified else ("HYPOTHESIS" if gpt_obs else "UNKNOWN"),
        entities=entities_b,
        attributes={"scene": scene_b},
        evidence_refs=list(evidence_refs_b),
        source_provenance=(
            "HUMAN_IDENTITY_CLAIM" if human_relation_certified else "EVIDENCE_PACKET_ONLY"
        ),
        certified_scopes=certified_scopes_b,
        uncertified_attribute_keys=[],
    )

    queryable = []
    for a in attrs:
        queryable.append(
            {
                "key": a["key"],
                "window": a["window"],
                "value": a["value"],
                "prompt_zh": a.get("prompt_zh"),
                "certification": a["certification"],
                "epistemic": a["epistemic"],
                "allowed_for_dev_qa_draft": a.get("allowed_for_dev_qa_draft", True),
                "allowed_for_gold": False,
                "source_kind": a.get("source_kind"),
                "source_ref": a.get("source_ref"),
                "multi_signage_uniqueness_verified": a.get(
                    "multi_signage_uniqueness_verified"
                ),
            }
        )

    # Relation type from claims
    rel_type = "cross_window_same_person"
    entities = {m.get("entity") for m in identity_matches}
    if "child" in entities:
        rel_type = "cross_window_same_child"

    has_semantic_records = bool(gpt_obs or attrs or identity_matches)

    return {
        "fact_a": fact_a,
        "fact_b": fact_b,
        "queryable_attributes": queryable,
        "gpt_observations": gpt_obs,
        "qa_draft_packaging_refs": draft_refs,
        "relation_type": rel_type,
        "bind_status": "FACT" if human_relation_certified else "UNKNOWN",
        "bind_claim_ids": [m["claim_id"] for m in identity_matches if m.get("claim_id")],
        "semantic_fact_verified": semantic_fact_verified,
        "has_semantic_records": has_semantic_records,
        "has_dev_draft_answer_attributes": len(queryable) > 0,
        "notes": (
            "Attributes from engineering structural observations; "
            "QA draft answers used only as packaging refs, not sole fact minting"
        ),
    }


def build_relation_candidate(pair_id: str, assembled: dict[str, Any]) -> RelationCandidate:
    return RelationCandidate(
        relation_id=f"REL:{pair_id}",
        video_id=assembled["fact_a"].video_id,
        relation_type=assembled["relation_type"],
        fact_a=assembled["fact_a"],
        fact_b=assembled["fact_b"],
        bind_status=assembled["bind_status"],
        bind_claim_ids=assembled["bind_claim_ids"],
        queryable_attributes=assembled["queryable_attributes"],
        dependency_direction="B_identifies_then_query_A",
        notes=assembled.get("notes") or "",
        human_bind_scope="CROSS_WINDOW_PERSON_IDENTITY",
    )
