#!/usr/bin/env python3
"""S3–S5: reusable Relation → QA family + directed program graph.

Uses sourced facts only. Distinguishes FACT / HYPOTHESIS / UNKNOWN.
Does not hardcode per-video questions as the generator itself.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


EPISTEMIC = {"FACT", "HYPOTHESIS", "UNKNOWN"}


@dataclass
class SourcedFact:
    fact_id: str
    video_id: str
    window: list[float]
    epistemic: str  # FACT | HYPOTHESIS | UNKNOWN
    entities: list[dict[str, Any]]
    attributes: dict[str, Any]
    evidence_refs: list[str] = field(default_factory=list)
    source_provenance: str = ""

    def validate(self) -> list[str]:
        errs = []
        if self.epistemic not in EPISTEMIC:
            errs.append(f"bad_epistemic:{self.epistemic}")
        if not self.video_id:
            errs.append("missing_video_id")
        if not (isinstance(self.window, list) and len(self.window) == 2):
            errs.append("bad_window")
        if not self.evidence_refs and self.epistemic == "FACT":
            errs.append("FACT_requires_evidence_refs")
        return errs


@dataclass
class RelationCandidate:
    relation_id: str
    video_id: str
    relation_type: str
    fact_a: SourcedFact
    fact_b: SourcedFact
    bind_status: str  # FACT | HYPOTHESIS | UNKNOWN
    bind_claim_ids: list[str] = field(default_factory=list)
    queryable_attributes: list[dict[str, Any]] = field(default_factory=list)
    dependency_direction: str = "B_identifies_then_query_A"
    notes: str = ""


# Family templates (generic; filled from relation attributes — not video_id switches)
QA_FAMILIES: dict[str, dict[str, Any]] = {
    "same_person_bind_query_earlier_attribute": {
        "required_relation_types": [
            "cross_window_same_person",
            "cross_window_same_child",
        ],
        "required_bind": ["FACT", "HYPOTHESIS"],
        "question_template_zh": "后来在{b_scene}的{b_entity_desc}，更早时{a_attr_prompt}？",
        "answer_from": "a_attribute_value",
        "graph_ops": [
            ("LocateEntity", "B"),
            ("LocateEntity", "A"),
            ("CrossIntervalSamePersonBind", None),
            ("QueryEarlierAttribute", "A"),
        ],
        "layer1_hint": [
            "ENTITY_IDENTIFICATION",
            "ENTITY_IDENTIFICATION",
            "CROSS_WINDOW_ENTITY_BIND",
            "BOUND_ATTRIBUTE_QUERY",
        ],
        "layer2_hint": [
            "LocatePersonByAppearance",
            "LocatePersonByAppearance",
            "CrossIntervalSamePersonBind",
            "QueryEarlierAttribute",
        ],
    },
    "same_person_bind_query_earlier_location": {
        "required_relation_types": ["cross_window_same_person"],
        "required_bind": ["FACT", "HYPOTHESIS"],
        "question_template_zh": "后来在{b_scene}的{b_entity_desc}，更早出现在什么地点/店铺附近？",
        "answer_from": "a_location_value",
        "graph_ops": [
            ("LocateEntity", "B"),
            ("LocateEntity", "A"),
            ("CrossIntervalSamePersonBind", None),
            ("QueryEarlierLocation", "A"),
        ],
        "layer1_hint": [
            "ENTITY_IDENTIFICATION",
            "ENTITY_IDENTIFICATION",
            "CROSS_WINDOW_ENTITY_BIND",
            "SCENE_LOCALIZATION",
        ],
        "layer2_hint": [
            "LocatePersonByAppearance",
            "LocatePersonByAppearance",
            "CrossIntervalSamePersonBind",
            "QueryEarlierLocation",
        ],
    },
}


def _fill(template: str, ctx: dict[str, str]) -> str:
    out = template
    for k, v in ctx.items():
        out = out.replace("{" + k + "}", v)
    return out


def _build_graph(family_id: str, rel: RelationCandidate, attr_key: str) -> dict[str, Any]:
    fam = QA_FAMILIES[family_id]
    nodes = []
    edges = []
    for i, (op, win) in enumerate(fam["graph_ops"]):
        nid = f"n{i}"
        node: dict[str, Any] = {
            "node_id": nid,
            "op": op,
            "raw_operator": op,
            "layer1": fam["layer1_hint"][i],
            "layer2": fam["layer2_hint"][i],
            "normalized_clip_role": win,
            "raw_clip_role": win,
        }
        if op == "QueryEarlierAttribute":
            node["attrs"] = {"attribute": attr_key}
        nodes.append(node)
        if i > 0:
            edges.append({"from": f"n{i-1}", "to": nid, "type": "dataflow"})
    # Ensure A-side locate feeds query when query is on A
    if len(nodes) >= 4:
        edges.append({"from": "n1", "to": "n3", "type": "spatial_context"})
    return {
        "program_id": f"lvcb:pg:{rel.relation_id}:{family_id}",
        "family_id": family_id,
        "nodes": nodes,
        "edges": edges,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "formal_gold": False,
        "signature_shorthand": "→".join(op for op, _ in fam["graph_ops"]),
    }


def generate_qa_from_relation(
    rel: RelationCandidate,
    *,
    family_id: str | None = None,
) -> dict[str, Any]:
    """Return {status: OK|FAIL, qa?, program_graph?, failure_reason?}."""
    errs = rel.fact_a.validate() + rel.fact_b.validate()
    if rel.fact_a.video_id != rel.fact_b.video_id or rel.fact_a.video_id != rel.video_id:
        errs.append("video_id_mismatch")
    if rel.bind_status not in EPISTEMIC:
        errs.append(f"bad_bind_status:{rel.bind_status}")
    if errs:
        return {"status": "FAIL", "failure_reason": "invalid_facts:" + ",".join(errs)}

    # Reject UNKNOWN-only binds for QA minting
    if rel.bind_status == "UNKNOWN":
        return {
            "status": "FAIL",
            "failure_reason": "bind_status_UNKNOWN_cannot_mint_qa",
        }

    # Choose family
    candidates = []
    for fid, fam in QA_FAMILIES.items():
        if family_id and fid != family_id:
            continue
        if rel.relation_type not in fam["required_relation_types"]:
            continue
        if rel.bind_status not in fam["required_bind"]:
            continue
        candidates.append(fid)
    if not candidates:
        return {
            "status": "FAIL",
            "failure_reason": (
                f"no_qa_family_for_relation_type={rel.relation_type};"
                f"bind={rel.bind_status}"
            ),
        }

    # Prefer attribute family if queryable attrs present
    fid = candidates[0]
    if "same_person_bind_query_earlier_attribute" in candidates and rel.queryable_attributes:
        fid = "same_person_bind_query_earlier_attribute"
    elif "same_person_bind_query_earlier_location" in candidates:
        # need location on A
        if "location" in rel.fact_a.attributes or any(
            a.get("key") == "location" for a in rel.queryable_attributes
        ):
            fid = "same_person_bind_query_earlier_location"

    fam = QA_FAMILIES[fid]
    # Resolve answer attribute
    attr_key = None
    attr_val = None
    attr_prompt = None
    for qa in rel.queryable_attributes:
        if qa.get("window") == "A" and qa.get("value") not in (None, ""):
            attr_key = qa.get("key")
            attr_val = qa.get("value")
            attr_prompt = qa.get("prompt_zh") or f"的{attr_key}是什么"
            break
    if fid.endswith("attribute") and not attr_val:
        return {
            "status": "FAIL",
            "failure_reason": "missing_queryable_A_attribute_value",
        }
    if fid.endswith("location"):
        attr_key = "location"
        attr_val = rel.fact_a.attributes.get("location")
        attr_prompt = "出现在什么地点/店铺附近"
        if not attr_val:
            return {
                "status": "FAIL",
                "failure_reason": "missing_A_location_attribute",
            }

    b_ents = rel.fact_b.entities or [{"desc": "目标人物"}]
    b_desc = b_ents[0].get("desc") or "目标人物"
    b_scene = rel.fact_b.attributes.get("scene") or "另一时段场景"
    ctx = {
        "b_scene": str(b_scene),
        "b_entity_desc": str(b_desc),
        "a_attr_prompt": str(attr_prompt),
    }
    question = _fill(fam["question_template_zh"], ctx)
    graph = _build_graph(fid, rel, attr_key or "attribute")

    # Epistemic tags on outputs
    fact_tags = {
        "fact_a": rel.fact_a.epistemic,
        "fact_b": rel.fact_b.epistemic,
        "bind": rel.bind_status,
    }
    return {
        "status": "OK",
        "failure_reason": None,
        "family_id": fid,
        "qa": {
            "qa_id": f"lvcb:qa:{rel.relation_id}:{fid}",
            "video_id": rel.video_id,
            "question": question,
            "answer": str(attr_val),
            "windows_seconds": [rel.fact_a.window, rel.fact_b.window],
            "evidence_refs": list(
                dict.fromkeys(rel.fact_a.evidence_refs + rel.fact_b.evidence_refs)
            ),
            "relation_id": rel.relation_id,
            "bind_claim_ids": rel.bind_claim_ids,
            "epistemic": fact_tags,
            "operator_signature": graph["signature_shorthand"],
            "necessity": "PENDING_S6",
            "source_provenance": {
                "fact_a": rel.fact_a.source_provenance,
                "fact_b": rel.fact_b.source_provenance,
            },
            "review_status": "DRAFT",
            "split_assignment": "DEV_CONSTRUCTION",
            "formal_gold": False,
            "generator": "pipeline_conformance.s3_s5_relation_qa.v1",
            "not_video_hardcoded": True,
        },
        "program_graph": graph,
        "queryable_attributes": rel.queryable_attributes,
        "dependency_direction": rel.dependency_direction,
    }


def relation_to_dict(rel: RelationCandidate) -> dict:
    return {
        "relation_id": rel.relation_id,
        "video_id": rel.video_id,
        "relation_type": rel.relation_type,
        "bind_status": rel.bind_status,
        "bind_claim_ids": rel.bind_claim_ids,
        "dependency_direction": rel.dependency_direction,
        "queryable_attributes": rel.queryable_attributes,
        "fact_a": asdict(rel.fact_a),
        "fact_b": asdict(rel.fact_b),
        "notes": rel.notes,
    }
