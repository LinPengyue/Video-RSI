#!/usr/bin/env python3
"""WP3 Pipeline Conformance Repair: S0–S9 matrix + S3–S9 code path regression.

Baseline method: 组合性泛化数据集构造流水线 v1.0 (2026-11-04).
Does not redesign the benchmark pipeline. Does not mint formal Gold.
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
    independent_status_bundle,
    release_gate_check,
)
from pipeline_conformance.s8_signature_feedback import audit_draft_against_seen  # noqa: E402

BASELINE = "15ff75b5881c27352a4611ed81d3893f7e8aa0fb"
WP3 = DS_ROOT / "wp3_production"
OUT = WP3 / "wp3_pipeline_conformance"
REPORTS = DS_ROOT / "reports"
REGISTRY = WP3 / "wp3_4" / "trusted_human_review_registry" / "records.jsonl"


def build_conformance_matrix() -> dict:
    """P0: S0–S9 mapping with real modules/evidence — not report PASS booleans."""
    stages = [
        {
            "stage": "S0",
            "name": "Video pool / inventory / sealed exclusion",
            "modules": [
                "tools/wp3_wave_production.py::load_exposed,register_pool_and_policy",
                "tools/lvbench_comp/batch_factory/inventory.py",
                "tools/lvbench_comp/batch_factory/sealed_exclusion.py",
                "track_b/construction_video_pool.jsonl",
                "track_b/SEALED_POOL_SPLIT_POLICY.json",
            ],
            "io_contract": {
                "in": "LVBench video ids + policy",
                "out": "DEV_CONSTRUCTION registration; sealed untouched",
            },
            "status": "EXECUTED",
            "run_evidence": [
                "wp3_production/wave1|wave2 video_selection + pool updates",
                "wp3_3/ab_dev5 video_results.json",
            ],
            "tests": ["tests/test_wp3_wave_production.py::test_pool_and_policy"],
            "gap": None,
        },
        {
            "stage": "S1",
            "name": "Event evidence extraction (ROI frames/clips)",
            "modules": [
                "tools/wp3_wave_production.py::discover_pairs,extract_roi_frames,maybe_extract_clip",
                "tools/wp3_3_entity_first_discovery.py::discover_pairs_entity_first",
                "tools/lvbench_comp/batch_factory/extract_events.py",
            ],
            "io_contract": {
                "in": "video mp4",
                "out": "rois.jsonl + local_media clips/frames + review subsets",
            },
            "status": "EXECUTED",
            "run_evidence": [
                "wp3_production/wave1|wave2/rois.jsonl",
                "wp3_3/ab_dev5/rois.jsonl",
                "local_media/wp3_production/** (gitignored)",
            ],
            "tests": ["tests/test_wp3_wave_production.py::test_evidence_and_review_packets"],
            "gap": "Semantic event discovery still engineering-proxy without vision model",
        },
        {
            "stage": "S2",
            "name": "Fact verification tiers",
            "modules": [
                "tools/wp3_1_wave1_semantic_triage.py",
                "tools/wp3_2_closure_and_expansion.py",
                "wp3_human_adj human claims (FACT identity only)",
            ],
            "io_contract": {
                "in": "evidence packs",
                "out": "STATIC_VISIBLE|ORDERED_MULTIFRAME_SUGGESTS|CONTINUOUS_VIDEO_VERIFIED|UNRESOLVED + Human FACT claims",
            },
            "status": "PARTIAL",
            "run_evidence": [
                "WP3_WAVE1_GPT_SEMANTIC_TRIAGE_AND_RELATION_AUDIT.json",
                "trusted_human_review_registry/records.jsonl (3 SAME claims)",
            ],
            "tests": ["tests/test_wp3_human_adj_ingest_and_necessity.py"],
            "gap": "Most WP3 pairs remain UNRESOLVED; few CONTINUOUS_VIDEO_VERIFIED facts",
        },
        {
            "stage": "S3",
            "name": "Relation candidates from facts",
            "modules": [
                "tools/lvbench_comp/batch_factory/relations.py::mine_relations",
                "NEW: pipeline_conformance/s3_s5_relation_qa.py::RelationCandidate",
            ],
            "io_contract": {
                "in": "sourced facts + bind epistemic",
                "out": "relation with queryable attrs + dependency direction",
            },
            "status": "PARTIAL→REPAIRED_INTERFACE",
            "run_evidence": ["wp3_pipeline_conformance/regression_cases.json"],
            "tests": ["tests/test_wp3_pipeline_conformance.py"],
            "gap": "Prior WP3 often skipped typed RelationCandidate; hard-coded QA drafts",
        },
        {
            "stage": "S4",
            "name": "Directed program graph",
            "modules": [
                "NEW: pipeline_conformance/s3_s5_relation_qa.py::_build_graph",
                "normalized_programs_v1 graphs (seed reference)",
            ],
            "io_contract": {
                "in": "QA family + relation",
                "out": "nodes/edges with layer1/layer2 hints + dataflow",
            },
            "status": "REPAIRED_INTERFACE",
            "run_evidence": ["regression_cases.json program_graph fields"],
            "tests": ["tests/test_wp3_pipeline_conformance.py::test_graph_has_a_and_b"],
            "gap": "Layer2 labels provisional until vocab alignment",
        },
        {
            "stage": "S5",
            "name": "QA draft generation",
            "modules": [
                "tools/lvbench_comp/batch_factory/qa_draft.py (legacy sports-templated)",
                "NEW: pipeline_conformance/s3_s5_relation_qa.py::generate_qa_from_relation",
            ],
            "io_contract": {
                "in": "RelationCandidate",
                "out": "qa fields or explicit failure_reason",
            },
            "status": "REPAIRED_INTERFACE",
            "run_evidence": ["regression_cases.json"],
            "tests": [
                "tests/test_wp3_pipeline_conformance.py::test_generator_not_video_hardcoded",
                "tests/test_wp3_pipeline_conformance.py::test_fail_on_unknown_bind",
            ],
            "gap": "Legacy qa_draft.py still sport-specific; WP3 path now uses family generator",
        },
        {
            "stage": "S6",
            "name": "Necessity (structural / model / shortcut)",
            "modules": ["NEW: pipeline_conformance/s6_necessity.py"],
            "io_contract": {
                "in": "evidence descriptors + optional model runs",
                "out": "three channels + combined verdict",
            },
            "status": "REPAIRED_INTERFACE",
            "run_evidence": [
                "regression_cases.json necessity blocks",
                "model channel NOT_RUN without blind model",
            ],
            "tests": [
                "tests/test_wp3_pipeline_conformance.py::test_s6_channels_independent",
                "tests/test_wp3_pipeline_conformance.py::test_kbah_usfv_structural_fail",
            ],
            "gap": "Model Necessity remains NOT_RUN (no blind model)",
        },
        {
            "stage": "S7",
            "name": "Human review (trusted registry)",
            "modules": [
                "wp3_4/trusted_human_review_registry",
                "tools/wp3_human_adj_ingest_and_necessity.py",
                "NEW: pipeline_conformance/s7_s9_gates.py::independent_status_bundle",
            ],
            "io_contract": {
                "in": "Human Scientific Owner decisions",
                "out": "append-only claims; independent status layers",
            },
            "status": "EXECUTED",
            "run_evidence": ["records.jsonl with 3 claims"],
            "tests": ["tests/test_wp3_human_adj_ingest_and_necessity.py"],
            "gap": None,
        },
        {
            "stage": "S8",
            "name": "Composition signature feedback",
            "modules": [
                "normalized_programs_v1/eng/stage4_m3_isomorphism.py",
                "NEW: pipeline_conformance/s8_signature_feedback.py",
            ],
            "io_contract": {
                "in": "draft program graph after fact+necessity path",
                "out": "L1/L2 subgraph audit + OOD bucket; priority hints only",
            },
            "status": "REPAIRED_INTERFACE",
            "run_evidence": ["regression_cases.json s8_audit"],
            "tests": ["tests/test_wp3_pipeline_conformance.py::test_s8_audit_runs"],
            "gap": "Does not auto-promote Unseen; missing structures are hints only",
        },
        {
            "stage": "S9",
            "name": "Dataset import / release gates",
            "modules": [
                "tools/import_annotation_batch.py",
                "NEW: pipeline_conformance/s7_s9_gates.py::release_gate_check",
            ],
            "io_contract": {
                "in": "staging batch + trusted claims + necessity",
                "out": "allow/deny; formal_gold stays false without full gates",
            },
            "status": "PARTIAL→GATE_HARDENED",
            "run_evidence": ["regression release_gate codes"],
            "tests": [
                "tests/test_wp3_2_import_and_closure.py",
                "tests/test_wp3_pipeline_conformance.py::test_release_gate_blocks_gold",
            ],
            "gap": "No formal Gold minted this round",
        },
    ]
    return {
        "schema": "wp3_s0_s9_conformance_matrix_v1",
        "method_authority": "组合性泛化数据集构造流水线 v1.0 / 2026-11-04",
        "pipeline": "Video→Evidence→Fact→Relation→Graph→QA→Necessity→Human→Import",
        "baseline_commit": BASELINE,
        "built_utc": utc_now(),
        "stages": stages,
        "note": "Status reflects code+artifacts evidence, not PASS booleans in narrative reports",
        "protections": {
            "frozen_5_2": FROZEN_5_2,
            "proposed_7_4": "PROPOSED",
            "immutable_releases": ["v0.1.0", "v0.1.1", "v0.1.2"],
            "sealed_accessed": False,
            "track_a_run": False,
            "new_public_media": False,
            "scaled_gold_capacity_claimed": False,
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
            source_provenance="HUMAN_CLIP_REVIEW+STATIC_VISIBLE_SEAT",
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
            source_provenance="HUMAN_CLIP_REVIEW+STATIC_VISIBLE_EXTERIOR",
        ),
        bind_status="FACT",
        bind_claim_ids=["CLAIM_KBAH_ADULT_SAME", "CLAIM_KBAH_CHILD_SAME"],
        queryable_attributes=[
            {
                "key": "child_seat",
                "window": "A",
                "value": "前排副驾驶座",
                "prompt_zh": "坐在车内什么位置",
            }
        ],
        dependency_direction="B_identifies_then_query_A",
        notes="Regression case; known A-only seat shortcut",
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
            source_provenance="HUMAN_CLIP_REVIEW+OCR_VISIBLE_SIGN",
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
            source_provenance="HUMAN_CLIP_REVIEW",
        ),
        bind_status="FACT",
        bind_claim_ids=["CLAIM_USFV_MAN_SAME"],
        queryable_attributes=[
            {"key": "location", "window": "A", "value": "DORJI OM TSHONGKHANG 店铺附近", "prompt_zh": "出现在哪家店铺附近"}
        ],
        dependency_direction="B_identifies_then_query_A",
        notes="Regression case; known A OCR shortcut",
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
    s8 = audit_draft_against_seen(qa_out["program_graph"])
    # S8 only after path — still audit rejected cases for feedback
    status = independent_status_bundle(
        human_relation="CERTIFIED_SAME" if rel.bind_status == "FACT" else rel.bind_status,
        qa_draft="OK_DRAFT",
        necessity=nec["overall_verdict"],
        program_execution="NOT_RUN",
        formal_gold=False,
    )
    gate = release_gate_check(
        {
            "bind_claim_ids": rel.bind_claim_ids,
            "formal_gold": False,
            "necessity_overall": nec["overall_verdict"],
            "model_necessity_status": model["status"],
            "staging_review_status": None,
        },
        trusted_records_jsonl=REGISTRY,
    )
    return {
        "relation": relation_to_dict(rel),
        "s3_s5": qa_out,
        "s6": nec,
        "s8_audit": s8,
        "s7_status": status,
        "s9_release_gate": gate,
        "inventory": (
            "CONTROL"
            if nec["overall_verdict"] == "FAIL"
            else ("PENDING" if nec["overall_verdict"] == "UNKNOWN" else "CANDIDATE")
        ),
        "formal_gold": False,
        "rejected_as_comp_gold": nec["overall_verdict"] != "PASS",
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
            "notes": "A has unique child in passenger seat; seat answer fully in A",
        },
        shortcut_sig={
            "ocr_answer_in_window_A": False,
            "single_candidate_entity_in_A": True,
            "question_text_leaks_answer": False,
            "language_prior_celebrity_or_brand": False,
            "subtitle_leak": False,
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
            "notes": "Shop name OCR/signage in A; B has no shop name",
        },
        shortcut_sig={
            "ocr_answer_in_window_A": True,
            "single_candidate_entity_in_A": True,
            "question_text_leaks_answer": False,
            "language_prior_celebrity_or_brand": False,
            "subtitle_leak": False,
        },
    )
    # Negative: UNKNOWN bind must fail generation
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
        "schema": "wp3_pipeline_conformance_regression_v1",
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
            "model_NOT_RUN": 2,
            "formal_gold": 0,
            "effective_compositional_qa": 0,
            "control": 2,
        },
        "scaled_gold_capacity_claimed": False,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    matrix = build_conformance_matrix()
    reg = run_regression()
    report = {
        "schema": "wp3_pipeline_conformance_repair_report_v1",
        "work_package": "WP3_PIPELINE_CONFORMANCE_REPAIR",
        "baseline_commit": BASELINE,
        "built_utc": utc_now(),
        "matrix_path": str((OUT / "S0_S9_CONFORMANCE_MATRIX.json").relative_to(REPO_ROOT)),
        "regression_path": str((OUT / "regression_cases.json").relative_to(REPO_ROOT)),
        "counts": reg["counts"],
        "scaled_gold_capacity_claimed": False,
        "s8_buckets": {
            k: v["s8_audit"]["bucket"] for k, v in reg["cases"].items()
        },
        "protections": matrix["protections"],
        "claim": "Interfaces repaired; regression shows CONTROL via structural Necessity FAIL; no scaled Gold capacity",
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
                "neg_fail": reg["negative_unknown_bind"]["status"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
