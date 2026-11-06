#!/usr/bin/env python3
"""WP3 Pipeline Conformance scientific correction patch.

Baseline method: 组合性泛化数据集构造流水线 v1.0 (2026-11-04) Word numbering.
Does not redesign the benchmark pipeline. Does not mint formal Gold.
Does not claim production closed-loop unless wired into formal batch entry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DS_ROOT,
    FROZEN_5_2,
    PROPOSED_7_4_SEEN,
    PROPOSED_7_4_UNSEEN,
    REPO_ROOT,
    utc_now,
    write_json,
)
from pipeline_conformance.s3_s5_relation_qa import (  # noqa: E402
    RelationCandidate,
    SourcedFact,
    generate_qa_from_relation,
    relation_to_dict,
)
from pipeline_conformance.s6_necessity import (  # noqa: E402
    combine_necessity,
    model_necessity,
    shortcut_audit,
    structural_necessity,
)
from pipeline_conformance.s7_s9_gates import (  # noqa: E402
    INTERFACE_WIRING,
    independent_status_bundle,
    release_gate_check,
)
from pipeline_conformance.s8_signature_feedback import audit_draft_against_seen  # noqa: E402

BASELINE = "b864b3e277b419096aad946096db090b22b902f0"
WP3 = DS_ROOT / "wp3_production"
OUT = WP3 / "wp3_pipeline_conformance"
REPORTS = DS_ROOT / "reports"
REGISTRY = WP3 / "wp3_4" / "trusted_human_review_registry" / "records.jsonl"


def build_conformance_matrix() -> dict:
    """P1: Word v1.0 S0–S9 names — do not renumber to fit new code."""
    stages = [
        {
            "stage": "S0",
            "name_zh": "视频登记",
            "name_en": "Video registration",
            "modules": [
                "tools/wp3_wave_production.py::load_exposed,register_pool_and_policy",
                "tools/lvbench_comp/batch_factory/inventory.py",
                "tools/lvbench_comp/batch_factory/sealed_exclusion.py",
                "track_b/construction_video_pool.jsonl",
                "track_b/SEALED_POOL_SPLIT_POLICY.json",
            ],
            "io_contract": {
                "in": "LVBench video ids + split policy",
                "out": "DEV_CONSTRUCTION registration; sealed untouched",
            },
            "status": "EXECUTED",
            "incomplete": [],
            "run_evidence": [
                "wp3_production/wave1|wave2 video_selection + pool updates",
                "wp3_3/ab_dev5 video_results.json",
            ],
            "tests": ["tests/test_wp3_wave_production.py::test_pool_and_policy"],
        },
        {
            "stage": "S1",
            "name_zh": "事件发现",
            "name_en": "Event discovery",
            "modules": [
                "tools/wp3_wave_production.py::discover_pairs",
                "tools/wp3_3_entity_first_discovery.py::discover_pairs_entity_first",
                "tools/lvbench_comp/batch_factory/extract_events.py",
            ],
            "io_contract": {
                "in": "registered video",
                "out": "candidate event/pair windows (not yet evidence packets)",
            },
            "status": "PARTIAL",
            "incomplete": [
                "Semantic event discovery remains engineering-proxy without dedicated vision model",
            ],
            "run_evidence": [
                "wp3_production/wave1|wave2 pair selections",
                "wp3_3/ab_dev5 discovery results",
            ],
            "tests": ["tests/test_wp3_wave_production.py"],
        },
        {
            "stage": "S2",
            "name_zh": "证据封包",
            "name_en": "Evidence packetization",
            "modules": [
                "tools/wp3_wave_production.py::extract_roi_frames,maybe_extract_clip",
                "tools/wp3_human_adj clip packaging under local_media/.../wp3_human_adjudication/",
                "tools/lvbench_comp/batch_factory/extract_events.py",
            ],
            "io_contract": {
                "in": "event windows",
                "out": "rois.jsonl + local_media clips/frames + SHA bindings",
            },
            "status": "EXECUTED",
            "incomplete": [
                "Public third-party media not uploaded; local_media gitignored",
            ],
            "run_evidence": [
                "wp3_production/wave1|wave2/rois.jsonl",
                "local_media/wp3_production/** (gitignored; SHA in registry)",
            ],
            "tests": ["tests/test_wp3_wave_production.py::test_evidence_and_review_packets"],
        },
        {
            "stage": "S3",
            "name_zh": "语义审查",
            "name_en": "Semantic review",
            "modules": [
                "tools/wp3_1_wave1_semantic_triage.py",
                "tools/wp3_2_closure_and_expansion.py",
                "Human Scientific Owner identity adjudication (scope-limited)",
            ],
            "io_contract": {
                "in": "evidence packets",
                "out": "semantic tiers + scoped Human claims (identity ≠ answer Gold)",
            },
            "status": "PARTIAL",
            "incomplete": [
                "Most pairs remain UNRESOLVED; answer attributes (seat/shop) not Human-certified",
            ],
            "run_evidence": [
                "WP3_WAVE1_GPT_SEMANTIC_TRIAGE_AND_RELATION_AUDIT.json",
                "trusted_human_review_registry/records.jsonl (3 SAME identity claims)",
            ],
            "tests": ["tests/test_wp3_human_adj_ingest_and_necessity.py"],
        },
        {
            "stage": "S4",
            "name_zh": "关系发现",
            "name_en": "Relation discovery",
            "modules": [
                "tools/lvbench_comp/batch_factory/relations.py::mine_relations",
                "pipeline_conformance/s3_s5_relation_qa.py::RelationCandidate",
            ],
            "io_contract": {
                "in": "sourced facts + bind epistemic",
                "out": "relation with queryable attrs + dependency direction",
            },
            "status": "PARTIAL_INTERFACE",
            "incomplete": [
                "Parallel prototype not wired as sole formal batch entry",
                "Prior WP3 often skipped typed RelationCandidate",
            ],
            "run_evidence": ["wp3_pipeline_conformance/regression_cases.json"],
            "tests": ["tests/test_wp3_pipeline_conformance.py"],
        },
        {
            "stage": "S5",
            "name_zh": "原创 QA 与程序图草案",
            "name_en": "Original QA and program-graph draft",
            "modules": [
                "pipeline_conformance/s3_s5_relation_qa.py::generate_qa_from_relation,_build_graph,validate_program_graph_semantics",
                "tools/lvbench_comp/batch_factory/qa_draft.py (legacy sports-templated; not WP3 path)",
            ],
            "io_contract": {
                "in": "RelationCandidate",
                "out": "QA draft + typed I/O program graph or explicit failure_reason; execution=NOT_RUN",
            },
            "status": "REPAIRED_INTERFACE",
            "incomplete": [
                "No real program executor → PROGRAM_EXECUTION_NOT_RUN",
                "Layer2 labels often UNKNOWN vs Seen vocab (no force-merge)",
            ],
            "run_evidence": ["regression_cases.json program_graph + semantic_validation"],
            "tests": [
                "tests/test_wp3_pipeline_conformance.py::test_graph_dataflow_both_locates_to_bind",
                "tests/test_wp3_pipeline_conformance.py::test_bad_edges_fail_semantic_validation",
            ],
        },
        {
            "stage": "S6",
            "name_zh": "必要性审查",
            "name_en": "Necessity review",
            "modules": ["pipeline_conformance/s6_necessity.py"],
            "io_contract": {
                "in": "provenance-tagged evidence + optional validated model runs",
                "out": "structural / model / shortcut channels + combined verdict + strict_proof flag",
            },
            "status": "REPAIRED_INTERFACE",
            "incomplete": [
                "Model Necessity NOT_RUN (no blind model)",
                "USFV multi-signage uniqueness not independently verified",
            ],
            "run_evidence": [
                "regression_cases.json necessity blocks with provenance classes",
                "model channel NOT_RUN without complete run IDs",
            ],
            "tests": [
                "tests/test_wp3_pipeline_conformance.py::test_s6_provenance_classes",
                "tests/test_wp3_pipeline_conformance.py::test_forged_model_run_rejected",
            ],
        },
        {
            "stage": "S7",
            "name_zh": "答案与程序图科学审批",
            "name_en": "Scientific approval of answer and program graph",
            "modules": [
                "pipeline_conformance/s7_s9_gates.py::independent_status_bundle",
                "wp3_4/trusted_human_review_registry (identity claims only)",
            ],
            "io_contract": {
                "in": "QA draft + necessity + graph semantic validation",
                "out": "independent status layers; Human SAME ≠ answer/Gold approval",
            },
            "status": "PARTIAL",
            "incomplete": [
                "No scientific approval yet for seat/shop answer attributes or executable graphs",
            ],
            "run_evidence": [
                "regression s7_status bundles",
                "records.jsonl decision_scope=CROSS_WINDOW_PERSON_IDENTITY",
            ],
            "tests": [
                "tests/test_wp3_pipeline_conformance.py::test_human_claim_does_not_certify_answer",
            ],
        },
        {
            "stage": "S8",
            "name_zh": "结构审计",
            "name_en": "Structure audit",
            "modules": [
                "normalized_programs_v1/eng/stage4_m3_isomorphism.py",
                "pipeline_conformance/s8_signature_feedback.py",
            ],
            "io_contract": {
                "in": "draft program graph",
                "out": "separate L1/L2 coverage + normalized ops + OOD bucket (strict criteria)",
            },
            "status": "REPAIRED_INTERFACE",
            "incomplete": [
                "No auditable L2 alias table yet → draft L2 often UNKNOWN",
            ],
            "run_evidence": ["regression_cases.json s8_audit"],
            "tests": [
                "tests/test_wp3_pipeline_conformance.py::test_s8_l1_covered_l2_uncovered_not_pure_ood",
                "tests/test_wp3_pipeline_conformance.py::test_unnormalized_ops_not_forced_equivalent",
            ],
        },
        {
            "stage": "S9",
            "name_zh": "版本入库",
            "name_en": "Version ingest / release",
            "modules": [
                "tools/import_annotation_batch.py",
                "pipeline_conformance/s7_s9_gates.py::release_gate_check",
            ],
            "io_contract": {
                "in": "staging + trusted claims (full provenance) + necessity + execution",
                "out": "allow/deny; formal_gold false without full gates",
            },
            "status": "GATE_HARDENED_NOT_CLOSED_LOOP",
            "incomplete": [
                "Parallel conformance interface not wired into formal batch entry",
                "No formal Gold minted",
            ],
            "run_evidence": ["regression release_gate codes", "INTERFACE_WIRING"],
            "tests": [
                "tests/test_wp3_pipeline_conformance.py::test_release_gate_requires_claim_chain",
                "tests/test_wp3_2_import_and_closure.py",
            ],
        },
    ]
    return {
        "schema": "wp3_s0_s9_conformance_matrix_v2",
        "method_authority": "组合性泛化数据集构造流水线 v1.0 / 2026-11-04",
        "word_stage_names_zh": [
            "视频登记",
            "事件发现",
            "证据封包",
            "语义审查",
            "关系发现",
            "原创 QA 与程序图草案",
            "必要性审查",
            "答案与程序图科学审批",
            "结构审计",
            "版本入库",
        ],
        "pipeline": "S0→S9 per Word v1.0 (not renumbered for new modules)",
        "baseline_commit": BASELINE,
        "built_utc": utc_now(),
        "stages": stages,
        "interface_wiring": INTERFACE_WIRING,
        "note": "Status reflects code+artifacts evidence, not PASS booleans in narrative reports",
        "protections": {
            "frozen_5_2": FROZEN_5_2,
            "proposed_7_4_seen": PROPOSED_7_4_SEEN,
            "proposed_7_4_unseen": PROPOSED_7_4_UNSEEN,
            "proposed_7_4": "PROPOSED",
            "immutable_releases": ["v0.1.0", "v0.1.1", "v0.1.2"],
            "sealed_accessed": False,
            "track_a_run": False,
            "new_public_media": False,
            "scaled_gold_capacity_claimed": False,
            "production_closed_loop_claimed": False,
            "formal_gold": 0,
        },
    }


def _kbah_relation() -> RelationCandidate:
    return RelationCandidate(
        relation_id="REL_KBAH_EF_PAIR1",
        video_id="KbahC-QCKU8",
        relation_type="cross_window_same_child",
        fact_a=SourcedFact(
            fact_id="KBAH_A_VEHICLE",
            video_id="KbahC-QCKU8",
            window=[90.0, 100.0],
            epistemic="FACT",
            entities=[{"role": "child", "desc": "男孩"}, {"role": "adult", "desc": "戴眼镜迷彩外套男子"}],
            attributes={"scene": "车内", "child_seat": "前排副驾驶座"},
            evidence_refs=[
                "local_media/.../KbahC-QCKU8_EF_PAIR1/A_090_100.mp4#sha256:58812c619252d45f070c9372e49e1146a287840a16ff355fc1ec699a5b8b4fba"
            ],
            source_provenance="HUMAN_CLIP_REVIEW_IDENTITY_PLUS_STATIC_VISIBLE_SEAT_OBSERVATION",
            certified_scopes=["CROSS_WINDOW_PERSON_IDENTITY"],
            uncertified_attribute_keys=["child_seat"],
        ),
        fact_b=SourcedFact(
            fact_id="KBAH_B_OUTSIDE",
            video_id="KbahC-QCKU8",
            window=[2160.0, 2170.0],
            epistemic="FACT",
            entities=[{"role": "child", "desc": "穿黑色卫衣的男孩"}, {"role": "adult", "desc": "迷彩外套男子"}],
            attributes={"scene": "餐馆外"},
            evidence_refs=[
                "local_media/.../KbahC-QCKU8_EF_PAIR1/B_2160_2170.mp4#sha256:2afce6b5de756c29e5844dfef299a98f02bb4024e334ca26618d0dea44facc6c"
            ],
            source_provenance="HUMAN_CLIP_REVIEW_IDENTITY",
            certified_scopes=["CROSS_WINDOW_PERSON_IDENTITY"],
            uncertified_attribute_keys=[],
        ),
        bind_status="FACT",
        bind_claim_ids=["CLAIM_KBAH_ADULT_SAME", "CLAIM_KBAH_CHILD_SAME"],
        queryable_attributes=[
            {
                "key": "child_seat",
                "window": "A",
                "value": "前排副驾驶座",
                "prompt_zh": "坐在车内什么位置",
                "certification": "ATTRIBUTE_NOT_COVERED_BY_HUMAN_IDENTITY_CLAIM",
            }
        ],
        dependency_direction="B_identifies_then_query_A",
        notes="Regression CONTROL; known A-only seat shortcut risk; seat not Human-certified",
        human_bind_scope="CROSS_WINDOW_PERSON_IDENTITY",
    )


def _usfv_relation() -> RelationCandidate:
    return RelationCandidate(
        relation_id="REL_USFV_PAIR2",
        video_id="USfvmoalqsw",
        relation_type="cross_window_same_person",
        fact_a=SourcedFact(
            fact_id="USFV_A_STREET",
            video_id="USfvmoalqsw",
            window=[2355.0, 2365.0],
            epistemic="FACT",
            entities=[{"role": "adult", "desc": "格子衣男子"}],
            attributes={"scene": "城市街道", "location": "DORJI OM TSHONGKHANG 店铺附近"},
            evidence_refs=[
                "local_media/.../USfvmoalqsw_PAIR2/A_2355_2365.mp4#sha256:654a22bd87d1782d438b7b8a423daac17c674bc5f8e1cfa2b233b98da51c7163"
            ],
            source_provenance="HUMAN_CLIP_REVIEW_IDENTITY_PLUS_OCR_VISIBLE_SIGN_OBSERVATION",
            certified_scopes=["CROSS_WINDOW_PERSON_IDENTITY"],
            uncertified_attribute_keys=["location"],
        ),
        fact_b=SourcedFact(
            fact_id="USFV_B_STREAM",
            video_id="USfvmoalqsw",
            window=[4620.0, 4630.0],
            epistemic="FACT",
            entities=[{"role": "adult", "desc": "林间溪流旁说话的格子衣男子"}],
            attributes={"scene": "林间溪流旁"},
            evidence_refs=[
                "local_media/.../USfvmoalqsw_PAIR2/B_4620_4630.mp4#sha256:4b92d850427a80ba5750b63d5f5c349410ee6261f43669bb162e52e4b7b022b6"
            ],
            source_provenance="HUMAN_CLIP_REVIEW_IDENTITY",
            certified_scopes=["CROSS_WINDOW_PERSON_IDENTITY"],
            uncertified_attribute_keys=[],
        ),
        bind_status="FACT",
        bind_claim_ids=["CLAIM_USFV_MAN_SAME"],
        queryable_attributes=[
            {
                "key": "location",
                "window": "A",
                "value": "DORJI OM TSHONGKHANG 店铺附近",
                "prompt_zh": "出现在哪家店铺附近",
                "certification": "ATTRIBUTE_NOT_COVERED_BY_HUMAN_IDENTITY_CLAIM",
            }
        ],
        dependency_direction="B_identifies_then_query_A",
        notes="Regression CONTROL; multi-signage uniqueness NOT independently verified",
        human_bind_scope="CROSS_WINDOW_PERSON_IDENTITY",
    )


def run_one(rel: RelationCandidate, structural_ev: dict, shortcut_sig: dict) -> dict:
    qa_out = generate_qa_from_relation(rel)
    if qa_out["status"] != "OK":
        return {
            "relation": relation_to_dict(rel),
            "s3_s5": qa_out,
            "rejected": True,
        }
    structural = structural_necessity(structural_ev)
    shortcut = shortcut_audit(shortcut_sig)
    model = model_necessity(blind_model_available=False)
    nec = combine_necessity(structural, model, shortcut)
    # S8: provisional label then recompute
    s8 = audit_draft_against_seen(qa_out["program_graph"])
    status = independent_status_bundle(
        human_relation="CERTIFIED_SAME_IDENTITY_ONLY"
        if rel.bind_status == "FACT"
        else rel.bind_status,
        qa_draft="OK_DRAFT_ANSWER_ATTR_NOT_HUMAN_CERTIFIED",
        necessity=nec["overall_verdict"],
        program_execution="PROGRAM_EXECUTION_NOT_RUN",
        formal_gold=False,
    )
    windows_map = {"A": rel.fact_a.window, "B": rel.fact_b.window}
    gate = release_gate_check(
        {
            "bind_claim_ids": rel.bind_claim_ids,
            "video_id": rel.video_id,
            "windows": windows_map,
            "clip_sha256": {
                "A": rel.fact_a.evidence_refs[0].split("sha256:")[-1],
                "B": rel.fact_b.evidence_refs[0].split("sha256:")[-1],
            },
            "formal_gold": False,
            "necessity_overall": nec["overall_verdict"],
            "necessity_strict_proof": nec.get("strict_necessity_proof"),
            "model_necessity_status": model["status"],
            "program_execution": "PROGRAM_EXECUTION_NOT_RUN",
            "answer_certified_by_human_relation": False,
            "staging_review_status": None,
        },
        trusted_records_jsonl=REGISTRY,
    )
    inventory = nec.get("inventory_hint") or (
        "CONTROL" if nec["overall_verdict"] == "FAIL" else "PENDING"
    )
    return {
        "relation": relation_to_dict(rel),
        "s3_s5": qa_out,
        "s6": nec,
        "s8_audit": s8,
        "s7_status": status,
        "s9_release_gate": gate,
        "inventory": inventory,
        "formal_gold": False,
        "rejected_as_comp_gold": True,
        "human_identity_does_not_certify_answer": True,
        "structural_strict_proof": nec.get("structural_strict_proof"),
    }


def run_regression() -> dict:
    kbah = run_one(
        _kbah_relation(),
        structural_ev={
            "answer_localized_window": "A",
            "a_unique_answer_bearing_entity": True,
            "b_contains_answer_payload": False,
            "bind_required_for_answer_payload": False,
            "within_b_subject_switch": True,
            "multi_signage_uniqueness_verified": None,
            "field_provenance": {
                "answer_localized_window": "engineer_unverified_shortcut_hypothesis",
                "a_unique_answer_bearing_entity": "engineer_unverified_shortcut_hypothesis",
                "b_contains_answer_payload": "engineer_unverified_shortcut_hypothesis",
                "bind_required_for_answer_payload": "engineer_unverified_shortcut_hypothesis",
                "within_b_subject_switch": "independently_observed_fact",
            },
            "audited_entity_binds": ["CLAIM_KBAH_ADULT_SAME", "CLAIM_KBAH_CHILD_SAME"],
            "independently_observed_facts": ["within_b_subject_switch_visible_in_clips"],
            "notes": "Seat answer appears A-local; uniqueness not program-computed",
        },
        shortcut_sig={
            "ocr_answer_in_window_A": False,
            "single_candidate_entity_in_A": True,
            "question_text_leaks_answer": False,
            "language_prior_celebrity_or_brand": False,
            "subtitle_leak": False,
            "signal_provenance": {
                "single_candidate_entity_in_A": "engineer_unverified_shortcut_hypothesis",
            },
        },
    )
    usfv = run_one(
        _usfv_relation(),
        structural_ev={
            "answer_localized_window": "A",
            "a_unique_answer_bearing_entity": True,
            "b_contains_answer_payload": False,
            "bind_required_for_answer_payload": False,
            "within_b_subject_switch": False,
            "multi_signage_uniqueness_verified": False,
            "field_provenance": {
                "answer_localized_window": "engineer_unverified_shortcut_hypothesis",
                "a_unique_answer_bearing_entity": "engineer_unverified_shortcut_hypothesis",
                "b_contains_answer_payload": "engineer_unverified_shortcut_hypothesis",
                "bind_required_for_answer_payload": "engineer_unverified_shortcut_hypothesis",
                "multi_signage_uniqueness_verified": "engineer_unverified_shortcut_hypothesis",
            },
            "audited_entity_binds": ["CLAIM_USFV_MAN_SAME"],
            "notes": "Multiple shop signs in A; uniqueness NOT independently verified",
        },
        shortcut_sig={
            "ocr_answer_in_window_A": True,
            "single_candidate_entity_in_A": True,
            "question_text_leaks_answer": False,
            "language_prior_celebrity_or_brand": False,
            "subtitle_leak": False,
            "signal_provenance": {
                "ocr_answer_in_window_A": "engineer_unverified_shortcut_hypothesis",
                "single_candidate_entity_in_A": "engineer_unverified_shortcut_hypothesis",
            },
        },
    )
    bad = RelationCandidate(
        relation_id="REL_NEG_UNKNOWN_BIND",
        video_id="KbahC-QCKU8",
        relation_type="cross_window_same_person",
        fact_a=_kbah_relation().fact_a,
        fact_b=_kbah_relation().fact_b,
        bind_status="UNKNOWN",
        queryable_attributes=_kbah_relation().queryable_attributes,
    )
    neg = generate_qa_from_relation(bad)
    return {
        "schema": "wp3_pipeline_conformance_regression_v2",
        "built_utc": utc_now(),
        "baseline_commit": BASELINE,
        "cases": {"KbahC-QCKU8_EF_PAIR1": kbah, "USfvmoalqsw_PAIR2": usfv},
        "negative_unknown_bind": neg,
        "counts": {
            "generated_ok": 2,
            "necessity_FAIL": sum(
                1
                for c in (kbah, usfv)
                if c.get("s6", {}).get("overall_verdict") == "FAIL"
            ),
            "necessity_PASS": 0,
            "necessity_strict_proof": sum(
                1 for c in (kbah, usfv) if c.get("s6", {}).get("strict_necessity_proof")
            ),
            "model_NOT_RUN": 2,
            "formal_gold": 0,
            "effective_compositional_qa": 0,
            "control": 2,
            "atomic_covered_ood": sum(
                1
                for c in (kbah, usfv)
                if c.get("s8_audit", {}).get("atomic_covered_ood_candidate")
            ),
        },
        "scaled_gold_capacity_claimed": False,
        "production_closed_loop_claimed": False,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    matrix = build_conformance_matrix()
    reg = run_regression()
    report = {
        "schema": "wp3_pipeline_conformance_scientific_correction_report_v1",
        "work_package": "WP3_PIPELINE_CONFORMANCE_SCIENTIFIC_CORRECTION",
        "baseline_commit": BASELINE,
        "built_utc": utc_now(),
        "matrix_path": str((OUT / "S0_S9_CONFORMANCE_MATRIX.json").relative_to(REPO_ROOT)),
        "regression_path": str((OUT / "regression_cases.json").relative_to(REPO_ROOT)),
        "counts": reg["counts"],
        "scaled_gold_capacity_claimed": False,
        "production_closed_loop_claimed": False,
        "s8_buckets": {k: v["s8_audit"]["bucket"] for k, v in reg["cases"].items()},
        "s8_l2_covered": {
            k: v["s8_audit"]["atomic_covered_in_seen_layer2"] for k, v in reg["cases"].items()
        },
        "structural_strict_proof": {
            k: v.get("structural_strict_proof") for k, v in reg["cases"].items()
        },
        "protections": matrix["protections"],
        "interface_wiring": INTERFACE_WIRING,
        "claim": (
            "Scientific correction: L1≠L2 coverage; graph typed I/O; provenance-separated "
            "Necessity; Human identity scope-limited; CONTROL retained without strict "
            "structural proof claims or scaled Gold capacity"
        ),
    }
    write_json(OUT / "S0_S9_CONFORMANCE_MATRIX.json", matrix)
    write_json(OUT / "regression_cases.json", reg)
    write_json(OUT / "WP3_PIPELINE_CONFORMANCE_REPAIR_REPORT.json", report)
    write_json(REPORTS / "S0_S9_CONFORMANCE_MATRIX.json", matrix)
    write_json(REPORTS / "wp3_pipeline_conformance_regression.json", reg)
    write_json(REPORTS / "WP3_PIPELINE_CONFORMANCE_REPAIR_REPORT.json", report)
    print(
        json.dumps(
            {
                "counts": reg["counts"],
                "s8": report["s8_buckets"],
                "strict": report["structural_strict_proof"],
                "neg_fail": reg["negative_unknown_bind"]["status"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
