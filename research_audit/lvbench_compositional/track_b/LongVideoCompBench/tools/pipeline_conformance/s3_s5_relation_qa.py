#!/usr/bin/env python3
"""S4–S5 (Word v1.0): Relation discovery interface + original QA & program-graph draft.

Uses sourced facts only. Distinguishes FACT / HYPOTHESIS / UNKNOWN.
Does not hardcode per-video questions as the generator itself.

Program graphs require typed I/O: both Locate ports feed Bind; Bind feeds Query.
Presence of A/B nodes + edges alone is not EXECUTABLE_PASS.
Without a real graph executor, execution status remains PROGRAM_EXECUTION_NOT_RUN.
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
    # What Human / automated sources actually certify (scope-limited)
    certified_scopes: list[str] = field(default_factory=list)
    uncertified_attribute_keys: list[str] = field(default_factory=list)

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
    # Human SAME certifies identity only — never answer attributes by default
    human_bind_scope: str = "CROSS_WINDOW_PERSON_IDENTITY"


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


def _typed_node(
    nid: str,
    op: str,
    *,
    layer1: str,
    layer2: str,
    window: str | None,
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    evidence_refs: list[str],
    constraints: dict[str, Any] | None = None,
    attrs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "node_id": nid,
        "op": op,
        "raw_operator": op,
        "layer1": layer1,
        "layer2": layer2,
        "normalized_clip_role": window,
        "raw_clip_role": window,
        "inputs": inputs,
        "outputs": outputs,
        "evidence_refs": evidence_refs,
        "constraints": constraints or {},
    }
    if attrs:
        node["attrs"] = attrs
    return node


def _build_graph(
    family_id: str,
    rel: RelationCandidate,
    attr_key: str,
) -> dict[str, Any]:
    """Build directed program graph with typed I/O dataflow.

    Required topology:
      Locate(B) ──entity_ref──┐
                              ├─→ CrossIntervalSamePersonBind ──bound──→ Query(*)
      Locate(A) ──entity_ref──┘
    """
    fam = QA_FAMILIES[family_id]
    ops = fam["graph_ops"]
    assert len(ops) == 4
    (op_b, win_b), (op_a, win_a), (op_bind, _), (op_q, win_q) = ops

    n_locate_b = _typed_node(
        "n_locate_B",
        op_b,
        layer1=fam["layer1_hint"][0],
        layer2=fam["layer2_hint"][0],
        window=win_b,
        inputs=[
            {
                "name": "clip",
                "type": "VideoWindow",
                "role": "B",
                "window": rel.fact_b.window,
            }
        ],
        outputs=[{"name": "entity_ref", "type": "EntityRef", "role": "B"}],
        evidence_refs=list(rel.fact_b.evidence_refs),
        constraints={"must_observe_window": "B"},
    )
    n_locate_a = _typed_node(
        "n_locate_A",
        op_a,
        layer1=fam["layer1_hint"][1],
        layer2=fam["layer2_hint"][1],
        window=win_a,
        inputs=[
            {
                "name": "clip",
                "type": "VideoWindow",
                "role": "A",
                "window": rel.fact_a.window,
            }
        ],
        outputs=[{"name": "entity_ref", "type": "EntityRef", "role": "A"}],
        evidence_refs=list(rel.fact_a.evidence_refs),
        constraints={"must_observe_window": "A"},
    )
    n_bind = _typed_node(
        "n_bind",
        op_bind,
        layer1=fam["layer1_hint"][2],
        layer2=fam["layer2_hint"][2],
        window=None,
        inputs=[
            {"name": "entity_ref_B", "type": "EntityRef", "role": "B"},
            {"name": "entity_ref_A", "type": "EntityRef", "role": "A"},
        ],
        outputs=[{"name": "bound_entity", "type": "BoundEntityRef"}],
        evidence_refs=list(rel.bind_claim_ids),
        constraints={
            "bind_status": rel.bind_status,
            "human_scope": rel.human_bind_scope,
            "does_not_certify_answer_attributes": True,
        },
    )
    q_attrs = {"attribute": attr_key} if "Attribute" in op_q or attr_key else {}
    if "Location" in op_q:
        q_attrs = {"attribute": "location"}
    n_query = _typed_node(
        "n_query",
        op_q,
        layer1=fam["layer1_hint"][3],
        layer2=fam["layer2_hint"][3],
        window=win_q,
        inputs=[
            {"name": "bound_entity", "type": "BoundEntityRef"},
            {"name": "attribute_key", "type": "AttributeKey"},
        ],
        outputs=[{"name": "answer", "type": "AnswerValue"}],
        evidence_refs=list(rel.fact_a.evidence_refs),
        constraints={"query_window": "A", "requires_bind_output": True},
        attrs=q_attrs or None,
    )
    nodes = [n_locate_b, n_locate_a, n_bind, n_query]
    edges = [
        {
            "from": "n_locate_B",
            "to": "n_bind",
            "from_port": "entity_ref",
            "to_port": "entity_ref_B",
            "type": "dataflow",
            "value_type": "EntityRef",
        },
        {
            "from": "n_locate_A",
            "to": "n_bind",
            "from_port": "entity_ref",
            "to_port": "entity_ref_A",
            "type": "dataflow",
            "value_type": "EntityRef",
        },
        {
            "from": "n_bind",
            "to": "n_query",
            "from_port": "bound_entity",
            "to_port": "bound_entity",
            "type": "dataflow",
            "value_type": "BoundEntityRef",
        },
    ]
    graph = {
        "program_id": f"lvcb:pg:{rel.relation_id}:{family_id}",
        "family_id": family_id,
        "nodes": nodes,
        "edges": edges,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "formal_gold": False,
        "signature_shorthand": "→".join(op for op, _ in fam["graph_ops"]),
        "dataflow_topology": "LocateB+LocateA→Bind→Query",
        "program_execution": "PROGRAM_EXECUTION_NOT_RUN",
        "executable_pass": False,
        "executor_available": False,
    }
    graph["semantic_validation"] = validate_program_graph_semantics(graph)
    return graph


def validate_program_graph_semantics(graph: dict[str, Any]) -> dict[str, Any]:
    """Validate typed I/O and required dataflow. Never grants EXECUTABLE_PASS."""
    codes: list[str] = []
    nodes = {n["node_id"]: n for n in graph.get("nodes") or []}
    edges = graph.get("edges") or []

    if len(nodes) < 3:
        codes.append("TOO_FEW_NODES")

    # Require typed ports on every node
    for nid, n in nodes.items():
        if not n.get("inputs"):
            codes.append(f"MISSING_INPUTS:{nid}")
        if not n.get("outputs"):
            codes.append(f"MISSING_OUTPUTS:{nid}")
        if "evidence_refs" not in n:
            codes.append(f"MISSING_EVIDENCE_REFS:{nid}")

    out_index: dict[tuple[str, str], str] = {}
    for nid, n in nodes.items():
        for o in n.get("outputs") or []:
            out_index[(nid, o["name"])] = o["type"]

    in_index: dict[tuple[str, str], str] = {}
    for nid, n in nodes.items():
        for i in n.get("inputs") or []:
            in_index[(nid, i["name"])] = i["type"]

    bind_fed_by: set[str] = set()
    query_fed_by_bind = False
    for e in edges:
        frm = e.get("from") or e.get("from_node")
        to = e.get("to") or e.get("to_node")
        fp = e.get("from_port")
        tp = e.get("to_port")
        if not frm or not to:
            codes.append("EDGE_MISSING_ENDPOINT")
            continue
        if frm not in nodes or to not in nodes:
            codes.append(f"EDGE_UNKNOWN_NODE:{frm}->{to}")
            continue
        if not fp or not tp:
            codes.append(f"EDGE_MISSING_PORTS:{frm}->{to}")
            continue
        src_t = out_index.get((frm, fp))
        dst_t = in_index.get((to, tp))
        if src_t is None:
            codes.append(f"EDGE_UNKNOWN_FROM_PORT:{frm}.{fp}")
        if dst_t is None:
            codes.append(f"EDGE_UNKNOWN_TO_PORT:{to}.{tp}")
        if src_t and dst_t and src_t != dst_t:
            codes.append(f"EDGE_TYPE_MISMATCH:{frm}.{fp}:{src_t}->{to}.{tp}:{dst_t}")
        if to == "n_bind" and frm.startswith("n_locate"):
            bind_fed_by.add(frm)
        if frm == "n_bind" and to == "n_query":
            query_fed_by_bind = True

    if "n_bind" in nodes:
        if "n_locate_A" not in bind_fed_by or "n_locate_B" not in bind_fed_by:
            codes.append("BIND_REQUIRES_BOTH_LOCATE_INPUTS")
        if "n_query" in nodes and not query_fed_by_bind:
            codes.append("QUERY_REQUIRES_BIND_OUTPUT")

    # A/B nodes alone without typed dataflow must not pass
    roles = {n.get("normalized_clip_role") for n in nodes.values()}
    if roles >= {"A", "B"} and not edges:
        codes.append("AB_NODES_WITHOUT_EDGES_INSUFFICIENT")

    ok = len(codes) == 0
    return {
        "status": "OK" if ok else "FAIL",
        "codes": codes,
        "executable_pass": False,  # never true without a real executor
        "program_execution": "PROGRAM_EXECUTION_NOT_RUN",
        "note": "Semantic I/O OK ≠ EXECUTABLE_PASS; executor not available",
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

    if rel.bind_status == "UNKNOWN":
        return {
            "status": "FAIL",
            "failure_reason": "bind_status_UNKNOWN_cannot_mint_qa",
        }

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

    fid = candidates[0]
    if "same_person_bind_query_earlier_attribute" in candidates and rel.queryable_attributes:
        fid = "same_person_bind_query_earlier_attribute"
    elif "same_person_bind_query_earlier_location" in candidates:
        if "location" in rel.fact_a.attributes or any(
            a.get("key") == "location" for a in rel.queryable_attributes
        ):
            fid = "same_person_bind_query_earlier_location"

    fam = QA_FAMILIES[fid]
    attr_key = None
    attr_val = None
    attr_prompt = None
    attr_certification = None
    for qa in rel.queryable_attributes:
        if qa.get("window") == "A" and qa.get("value") not in (None, ""):
            attr_key = qa.get("key")
            attr_val = qa.get("value")
            attr_prompt = qa.get("prompt_zh") or f"的{attr_key}是什么"
            attr_certification = qa.get("certification") or "NOT_HUMAN_CERTIFIED"
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
        attr_certification = "NOT_HUMAN_CERTIFIED"
        if not attr_val:
            return {
                "status": "FAIL",
                "failure_reason": "missing_A_location_attribute",
            }

    # Human bind must not silently certify answer attributes
    if attr_key and attr_key in (rel.fact_a.uncertified_attribute_keys or []):
        attr_certification = "ATTRIBUTE_NOT_COVERED_BY_HUMAN_IDENTITY_CLAIM"
    if attr_certification in (None, "HUMAN_IDENTITY_IMPLIES_ANSWER"):
        return {
            "status": "FAIL",
            "failure_reason": "illegal_human_identity_upgraded_to_answer_certification",
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
    if graph["semantic_validation"]["status"] != "OK":
        return {
            "status": "FAIL",
            "failure_reason": "program_graph_semantic_validation_failed:"
            + ",".join(graph["semantic_validation"]["codes"]),
            "program_graph": graph,
        }

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
            "answer_attribute_key": attr_key,
            "answer_certification": attr_certification,
            "windows_seconds": [rel.fact_a.window, rel.fact_b.window],
            "evidence_refs": list(
                dict.fromkeys(rel.fact_a.evidence_refs + rel.fact_b.evidence_refs)
            ),
            "relation_id": rel.relation_id,
            "bind_claim_ids": rel.bind_claim_ids,
            "bind_scope": rel.human_bind_scope,
            "bind_does_not_certify_answer": True,
            "epistemic": fact_tags,
            "operator_signature": graph["signature_shorthand"],
            "necessity": "PENDING_S6",
            "source_provenance": {
                "fact_a": rel.fact_a.source_provenance,
                "fact_b": rel.fact_b.source_provenance,
                "fact_a_certified_scopes": rel.fact_a.certified_scopes,
                "fact_b_certified_scopes": rel.fact_b.certified_scopes,
                "fact_a_uncertified_attributes": rel.fact_a.uncertified_attribute_keys,
            },
            "review_status": "DRAFT",
            "split_assignment": "DEV_CONSTRUCTION",
            "formal_gold": False,
            "generator": "pipeline_conformance.s3_s5_relation_qa.v2",
            "family_template_id": fid,
            "question_built_from_template": True,
            "not_video_hardcoded": True,
        },
        "program_graph": graph,
        "queryable_attributes": rel.queryable_attributes,
        "dependency_direction": rel.dependency_direction,
        "quality_checks": {
            "uses_family_template": True,
            "question_contains_filled_slots": all(
                "{" + k + "}" not in question for k in ctx
            ),
            "generator_has_no_video_id_branch": True,
            "self_declared_not_video_hardcoded_insufficient_alone": True,
        },
    }


def relation_to_dict(rel: RelationCandidate) -> dict:
    return {
        "relation_id": rel.relation_id,
        "video_id": rel.video_id,
        "relation_type": rel.relation_type,
        "bind_status": rel.bind_status,
        "bind_claim_ids": rel.bind_claim_ids,
        "human_bind_scope": rel.human_bind_scope,
        "dependency_direction": rel.dependency_direction,
        "queryable_attributes": rel.queryable_attributes,
        "fact_a": asdict(rel.fact_a),
        "fact_b": asdict(rel.fact_b),
        "notes": rel.notes,
    }
