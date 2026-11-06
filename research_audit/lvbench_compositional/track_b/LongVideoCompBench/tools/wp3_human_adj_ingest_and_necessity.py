#!/usr/bin/env python3
"""Ingest Human Scientific Owner identity adjudications + QA/Necessity scaffolding.

Does NOT re-ask Human for identity.
Does NOT expand relation cert into formal_gold.
Does NOT forge blind A-only/B-only/A+B model runs.
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

BASELINE = "2faa6a035e39e60fd42c4375d31396bb1cb7066b"
WP3 = DS_ROOT / "wp3_production"
OUT = WP3 / "wp3_human_adj"
REPORTS = DS_ROOT / "reports"
REGISTRY = WP3 / "wp3_4" / "trusted_human_review_registry"
REGISTRY_RECORDS = REGISTRY / "records.jsonl"

CLIP = {
    "KbahC-QCKU8_EF_PAIR1": {
        "A": {
            "path": "research_audit/lvbench_compositional/track_b/local_media/wp3_production/wp3_human_adjudication/KbahC-QCKU8_EF_PAIR1/A_090_100.mp4",
            "sha256": "58812c619252d45f070c9372e49e1146a287840a16ff355fc1ec699a5b8b4fba",
            "window": [90.0, 100.0],
        },
        "B": {
            "path": "research_audit/lvbench_compositional/track_b/local_media/wp3_production/wp3_human_adjudication/KbahC-QCKU8_EF_PAIR1/B_2160_2170.mp4",
            "sha256": "2afce6b5de756c29e5844dfef299a98f02bb4024e334ca26618d0dea44facc6c",
            "window": [2160.0, 2170.0],
        },
    },
    "USfvmoalqsw_PAIR2": {
        "A": {
            "path": "research_audit/lvbench_compositional/track_b/local_media/wp3_production/wp3_human_adjudication/USfvmoalqsw_PAIR2/A_2355_2365.mp4",
            "sha256": "654a22bd87d1782d438b7b8a423daac17c674bc5f8e1cfa2b233b98da51c7163",
            "window": [2355.0, 2365.0],
        },
        "B": {
            "path": "research_audit/lvbench_compositional/track_b/local_media/wp3_production/wp3_human_adjudication/USfvmoalqsw_PAIR2/B_4620_4630.mp4",
            "sha256": "4b92d850427a80ba5750b63d5f5c349410ee6261f43669bb162e52e4b7b022b6",
            "window": [4620.0, 4630.0],
        },
    },
}


def append_registry(record: dict) -> None:
    REGISTRY.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_RECORDS.exists():
        REGISTRY_RECORDS.write_text("", encoding="utf-8")
    with REGISTRY_RECORDS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_human_claims() -> list[dict]:
    """Three independent claim IDs; raw rationale preserved; features normalized separately."""
    ts = utc_now()
    claims = [
        {
            "record_id": "lvcb:hreview:KbahC-QCKU8_EF_PAIR1:adult_same:20261106",
            "claim_id": "CLAIM_KBAH_ADULT_SAME",
            "pair_id": "KbahC-QCKU8_EF_PAIR1",
            "source_video_id": "KbahC-QCKU8",
            "windows": {"A": [90.0, 100.0], "B": [2160.0, 2170.0]},
            "clip_sha256": {
                "A": CLIP["KbahC-QCKU8_EF_PAIR1"]["A"]["sha256"],
                "B": CLIP["KbahC-QCKU8_EF_PAIR1"]["B"]["sha256"],
            },
            "local_clip_paths": {
                "A": CLIP["KbahC-QCKU8_EF_PAIR1"]["A"]["path"],
                "B": CLIP["KbahC-QCKU8_EF_PAIR1"]["B"]["path"],
            },
            "reviewer_identity": "USER_CHAT_HUMAN_SCIENTIFIC_OWNER",
            "reviewer_role": "HUMAN_SCIENTIFIC_OWNER",
            "source": "DIRECT_USER_CONFIRMATION_IN_CHAT",
            "decision_scope": "CROSS_WINDOW_PERSON_IDENTITY",
            "entity": "adult_male",
            "decision": "SAME",
            "raw_rationale_verbatim_zh": (
                "成年男性戴眼镜、迷彩外套；孩子头发有金色与深色，穿黑色卫衣，"
                "早期黑色卫衣在蓝色外套下面。"
            ),
            "normalized_features_separate": {
                "adult": ["glasses", "camouflage_jacket"],
                "note": "Child features belong to CLAIM_KBAH_CHILD_SAME; kept here only because raw text mentioned both",
            },
            "timestamp_utc": ts,
            "baseline_commit": BASELINE,
            "provenance_chain": [
                "user_watched_local_original_clips",
                "DIRECT_USER_CONFIRMATION_IN_CHAT",
                "append_only_trusted_registry",
            ],
            "does_not_certify": ["QA_GOLD", "NECESSITY_PASS", "FORMAL_GOLD"],
            "reask_human_identity": False,
        },
        {
            "record_id": "lvcb:hreview:KbahC-QCKU8_EF_PAIR1:child_same:20261106",
            "claim_id": "CLAIM_KBAH_CHILD_SAME",
            "pair_id": "KbahC-QCKU8_EF_PAIR1",
            "source_video_id": "KbahC-QCKU8",
            "windows": {"A": [90.0, 100.0], "B": [2160.0, 2170.0]},
            "clip_sha256": {
                "A": CLIP["KbahC-QCKU8_EF_PAIR1"]["A"]["sha256"],
                "B": CLIP["KbahC-QCKU8_EF_PAIR1"]["B"]["sha256"],
            },
            "local_clip_paths": {
                "A": CLIP["KbahC-QCKU8_EF_PAIR1"]["A"]["path"],
                "B": CLIP["KbahC-QCKU8_EF_PAIR1"]["B"]["path"],
            },
            "reviewer_identity": "USER_CHAT_HUMAN_SCIENTIFIC_OWNER",
            "reviewer_role": "HUMAN_SCIENTIFIC_OWNER",
            "source": "DIRECT_USER_CONFIRMATION_IN_CHAT",
            "decision_scope": "CROSS_WINDOW_PERSON_IDENTITY",
            "entity": "child",
            "decision": "SAME",
            "raw_rationale_verbatim_zh": (
                "成年男性戴眼镜、迷彩外套；孩子头发有金色与深色，穿黑色卫衣，"
                "早期黑色卫衣在蓝色外套下面。"
            ),
            "normalized_features_separate": {
                "child": [
                    "hair_blonde_and_dark_tones",
                    "black_hoodie",
                    "early_black_hoodie_under_blue_outer_jacket",
                ]
            },
            "timestamp_utc": ts,
            "baseline_commit": BASELINE,
            "provenance_chain": [
                "user_watched_local_original_clips",
                "DIRECT_USER_CONFIRMATION_IN_CHAT",
                "append_only_trusted_registry",
            ],
            "does_not_certify": ["QA_GOLD", "NECESSITY_PASS", "FORMAL_GOLD"],
            "reask_human_identity": False,
        },
        {
            "record_id": "lvcb:hreview:USfvmoalqsw_PAIR2:man_same:20261106",
            "claim_id": "CLAIM_USFV_MAN_SAME",
            "pair_id": "USfvmoalqsw_PAIR2",
            "source_video_id": "USfvmoalqsw",
            "windows": {"A": [2355.0, 2365.0], "B": [4620.0, 4630.0]},
            "clip_sha256": {
                "A": CLIP["USfvmoalqsw_PAIR2"]["A"]["sha256"],
                "B": CLIP["USfvmoalqsw_PAIR2"]["B"]["sha256"],
            },
            "local_clip_paths": {
                "A": CLIP["USfvmoalqsw_PAIR2"]["A"]["path"],
                "B": CLIP["USfvmoalqsw_PAIR2"]["B"]["path"],
            },
            "reviewer_identity": "USER_CHAT_HUMAN_SCIENTIFIC_OWNER",
            "reviewer_role": "HUMAN_SCIENTIFIC_OWNER",
            "source": "DIRECT_USER_CONFIRMATION_IN_CHAT",
            "decision_scope": "CROSS_WINDOW_PERSON_IDENTITY",
            "entity": "adult_male_plaid",
            "decision": "SAME",
            "raw_rationale_verbatim_zh": (
                "格子衣着及面部特征，尤其大眼睛、略有斜视、高鼻梁、偏薄嘴唇、较短眉毛及尖耳轮廓。"
            ),
            "normalized_features_separate": {
                "clothing": ["plaid_gho_or_checkered_garment"],
                "face": [
                    "large_eyes",
                    "mild_strabismus_or_gaze_asymmetry",
                    "high_nose_bridge",
                    "thin_lips",
                    "short_eyebrows",
                    "pointed_ear_contour",
                ],
                "note": "Clothing similarity alone is insufficient; Human cited facial features",
            },
            "timestamp_utc": ts,
            "baseline_commit": BASELINE,
            "provenance_chain": [
                "user_watched_local_original_clips",
                "DIRECT_USER_CONFIRMATION_IN_CHAT",
                "append_only_trusted_registry",
            ],
            "does_not_certify": ["QA_GOLD", "NECESSITY_PASS", "FORMAL_GOLD"],
            "reask_human_identity": False,
        },
    ]
    # idempotent: rewrite records.jsonl for these three IDs only if empty or append if missing
    existing = []
    if REGISTRY_RECORDS.exists() and REGISTRY_RECORDS.read_text().strip():
        existing = [
            json.loads(ln)
            for ln in REGISTRY_RECORDS.read_text().splitlines()
            if ln.strip()
        ]
    have = {r.get("claim_id") for r in existing}
    for c in claims:
        if c["claim_id"] not in have:
            append_registry(c)
            write_json(OUT / "human_claims" / f"{c['claim_id']}.json", c)
            write_json(REPORTS / f"wp3_human_{c['claim_id']}.json", c)
        else:
            write_json(OUT / "human_claims" / f"{c['claim_id']}.json", c)
            write_json(REPORTS / f"wp3_human_{c['claim_id']}.json", c)
    # refresh meta count
    meta_path = REGISTRY / "REGISTRY_META.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    n = sum(1 for ln in REGISTRY_RECORDS.read_text().splitlines() if ln.strip())
    meta.update(
        {
            "schema": "wp3_4_trusted_human_review_registry_v1",
            "updated_utc": utc_now(),
            "records_this_round": 3,
            "records_total": n,
            "last_ingest": "WP3_HUMAN_ADJ_IDENTITY_THREE_CLAIMS",
        }
    )
    write_json(meta_path, meta)
    return claims


def write_qa_and_graphs() -> dict:
    kbah_graph = {
        "program_id": "lvcb:pg:KbahC-QCKU8_EF_PAIR1_seat_draft",
        "formal_gold": False,
        "signature_family": "SamePersonBind→QueryEarlier*",
        "ood_bucket": "NEW_VIDEO_NEW_QA_OLD_SIGNATURE_FAMILY",
        "atomic_covered_ood_candidate": False,
        "nodes": [
            {"node_id": "n0", "op": "LocateChild", "window": "B", "attrs": {"cue": "boy_with_camo_adult_outside_restaurant"}},
            {"node_id": "n1", "op": "LocateChild", "window": "A", "attrs": {"cue": "boy_in_vehicle"}},
            {"node_id": "n2", "op": "LocateAdult", "window": "B", "attrs": {"cue": "camo_jacket_glasses_man"}},
            {"node_id": "n3", "op": "LocateAdult", "window": "A", "attrs": {"cue": "camo_jacket_glasses_driver"}},
            {"node_id": "n4", "op": "CrossIntervalSamePersonBind", "binds": ["child_A", "child_B"]},
            {"node_id": "n5", "op": "CrossIntervalSamePersonBind", "binds": ["adult_A", "adult_B"], "optional_support": True},
            {"node_id": "n6", "op": "QueryEarlierSeatPosition", "window": "A", "target": "child"},
        ],
        "edges": [
            {"from": "n0", "to": "n4", "type": "entity_ref"},
            {"from": "n1", "to": "n4", "type": "entity_ref"},
            {"from": "n2", "to": "n5", "type": "entity_ref"},
            {"from": "n3", "to": "n5", "type": "entity_ref"},
            {"from": "n4", "to": "n6", "type": "bound_entity"},
            {"from": "n1", "to": "n6", "type": "spatial_context"},
        ],
        "shorthand_not_executable": "LocateChild(B)→CrossIntervalSamePersonBind(A,B)→QueryEarlierSeatPosition(A)",
    }
    usfv_graph = {
        "program_id": "lvcb:pg:USfvmoalqsw_PAIR2_shop_draft",
        "formal_gold": False,
        "signature_family": "SamePersonBind→QueryEarlier*",
        "ood_bucket": "NEW_VIDEO_NEW_QA_OLD_SIGNATURE_FAMILY",
        "atomic_covered_ood_candidate": False,
        "nodes": [
            {"node_id": "n0", "op": "LocatePerson", "window": "B", "attrs": {"cue": "plaid_man_by_forest_stream"}},
            {"node_id": "n1", "op": "LocatePerson", "window": "A", "attrs": {"cue": "plaid_man_on_urban_street"}},
            {"node_id": "n2", "op": "CrossIntervalSamePersonBind", "binds": ["person_A", "person_B"]},
            {"node_id": "n3", "op": "DetectShopSign", "window": "A", "attrs": {"candidate_signs": ["DORJI OM TSHONGKHANG", "TANDIN TSHONGKHANG"]}},
            {"node_id": "n4", "op": "QueryEarlierShopSign", "window": "A", "target": "bound_person"},
        ],
        "edges": [
            {"from": "n0", "to": "n2", "type": "entity_ref"},
            {"from": "n1", "to": "n2", "type": "entity_ref"},
            {"from": "n2", "to": "n4", "type": "bound_entity"},
            {"from": "n3", "to": "n4", "type": "ocr_candidates"},
            {"from": "n1", "to": "n3", "type": "co_located"},
        ],
        "shorthand_not_executable": "LocatePerson(B)→CrossIntervalSamePersonBind(A,B)→QueryEarlierShopSign(A)",
    }
    doc = {
        "schema": "wp3_human_adj_qa_program_drafts_v1",
        "built_utc": utc_now(),
        "baseline_commit": BASELINE,
        "formal_gold": False,
        "items": [
            {
                "qa_id": "lvcb:qa:KbahC-QCKU8_EF_PAIR1_seat_draft",
                "pair_id": "KbahC-QCKU8_EF_PAIR1",
                "question_zh": "后来在餐馆外与穿迷彩外套男子同行的男孩，之前坐在车内什么位置？",
                "answer_draft_zh": "前排副驾驶座。",
                "relation_claims": ["CLAIM_KBAH_ADULT_SAME", "CLAIM_KBAH_CHILD_SAME"],
                "program_graph": kbah_graph,
                "status": "DRAFT_ONLY",
            },
            {
                "qa_id": "lvcb:qa:USfvmoalqsw_PAIR2_shop_draft",
                "pair_id": "USfvmoalqsw_PAIR2",
                "question_zh": "后来在林间溪流旁说话的格子衣男子，更早出现在哪家店铺附近？",
                "answer_draft_zh": "DORJI OM TSHONGKHANG 店铺附近。",
                "relation_claims": ["CLAIM_USFV_MAN_SAME"],
                "program_graph": usfv_graph,
                "status": "DRAFT_ONLY",
            },
        ],
    }
    write_json(OUT / "wp3_qa_program_drafts.json", doc)
    write_json(REPORTS / "wp3_qa_program_drafts.json", doc)
    return doc


def write_necessity() -> dict:
    """Structural shortcut audit; no forged blind model A/B/A+B runs."""
    kbah = {
        "pair_id": "KbahC-QCKU8_EF_PAIR1",
        "qa_id": "lvcb:qa:KbahC-QCKU8_EF_PAIR1_seat_draft",
        "blind_model_ab_tests": {
            "status": "NOT_RUN_NO_BLIND_MODEL_OR_INDEPENDENT_REVIEWER",
            "forged": False,
            "A_only": None,
            "B_only": None,
            "A_plus_B": None,
        },
        "structural_shortcut_audit": {
            "auditor_role": "cursor_engineering_structural_not_human_scientific_owner",
            "A_unique_boy": True,
            "A_boy_seat_directly_observable": "FRONT_PASSENGER",
            "A_only_sufficient_for_seat_answer": True,
            "reason_A_only": (
                "A shows exactly one child, clearly in front passenger seat; "
                "seat answer does not require B once the question points at 'the boy'."
            ),
            "B_bind_affects_answer_content": False,
            "B_within_roi_subject_switch": True,
            "B_switch_note": (
                "B~2160 interior: boy with different older bearded adult (not camo jacket); "
                "B~2167–2170 exterior: camo glasses man + child outside bakery/seafood house."
            ),
            "human_SAME_does_not_imply_necessity_pass": True,
        },
        "necessity_verdict": "FAIL",
        "necessity_reason": (
            "Strict compositional Necessity fails: A-only uniquely determines seat; "
            "CrossIntervalSamePersonBind is not required for the answer payload. "
            "Retain as CONTROL with certified identity relations."
        ),
        "inventory": "CONTROL_RELATION_CERTIFIED_NOT_COMP_GOLD",
        "formal_gold": False,
        "enter_independent_gold_review": False,
    }
    usfv = {
        "pair_id": "USfvmoalqsw_PAIR2",
        "qa_id": "lvcb:qa:USfvmoalqsw_PAIR2_shop_draft",
        "blind_model_ab_tests": {
            "status": "NOT_RUN_NO_BLIND_MODEL_OR_INDEPENDENT_REVIEWER",
            "forged": False,
            "A_only": None,
            "B_only": None,
            "A_plus_B": None,
        },
        "structural_shortcut_audit": {
            "auditor_role": "cursor_engineering_structural_not_human_scientific_owner",
            "A_unique_plaid_man_in_focus": True,
            "A_shop_sign_ocr_visible": "DORJI OM TSHONGKHANG (also TANDIN TSHONGKHANG nearby)",
            "A_only_sufficient_for_shop_answer": True,
            "reason_A_only": (
                "Shop sign is readable in A behind/beside the plaid man; "
                "answer string is available without B. B does not supply the shop name."
            ),
            "B_excludes_other_person_or_place_candidates": "NOT_REQUIRED_FOR_OCR_ANSWER",
            "B_has_shop_name": False,
            "human_SAME_does_not_imply_necessity_pass": True,
        },
        "necessity_verdict": "FAIL",
        "necessity_reason": (
            "Strict compositional Necessity fails: A-only OCR/signage yields the shop answer; "
            "SamePersonBind does not contribute to answer computation. CONTROL."
        ),
        "inventory": "CONTROL_RELATION_CERTIFIED_NOT_COMP_GOLD",
        "formal_gold": False,
        "enter_independent_gold_review": False,
    }
    doc = {
        "schema": "wp3_human_adj_necessity_audit_v1",
        "built_utc": utc_now(),
        "baseline_commit": BASELINE,
        "rule": "Human SAME ≠ Necessity PASS; no forged A/B/A+B model scores",
        "items": [kbah, usfv],
        "counts": {
            "necessity_PASS": 0,
            "necessity_FAIL": 2,
            "necessity_UNKNOWN": 0,
            "blind_ab_tests_completed": 0,
            "effective_compositional_qa": 0,
            "control_with_certified_relation": 2,
            "formal_gold": 0,
        },
    }
    write_json(OUT / "wp3_necessity_structural_audit.json", doc)
    write_json(REPORTS / "wp3_necessity_structural_audit.json", doc)
    return doc


def write_layered_status(claims, qa, nec) -> dict:
    layers = {
        "schema": "wp3_human_adj_layered_status_v1",
        "built_utc": utc_now(),
        "baseline_commit": BASELINE,
        "layers": {
            "human_relation_certification": {
                "n": 3,
                "claim_ids": [c["claim_id"] for c in claims],
                "scope": "CROSS_WINDOW_PERSON_IDENTITY_ONLY",
            },
            "qa_draft": {"n": 2, "formal_gold": False},
            "program_graph_draft": {"n": 2, "formal_gold": False},
            "a_only_b_only_ab_model_tests": {
                "status": "NOT_RUN_NO_BLIND_MODEL",
                "forged": False,
            },
            "shortcut_audit": {"status": "COMPLETE_STRUCTURAL", "both_fail_strict_necessity": True},
            "necessity_verdict": {"Kbah": "FAIL", "USFV": "FAIL"},
            "gold_status": {"formal_gold": False, "independent_gold_review": "NOT_ENTERED"},
        },
        "inventory": {
            "effective_compositional_qa": 0,
            "control": 2,
            "relation_certified_pending_better_qa": 2,
        },
        "protections": {
            "frozen_5_2": FROZEN_5_2,
            "proposed_7_4_status": "PROPOSED",
            "proposed_7_4_seen": PROPOSED_7_4_SEEN,
            "proposed_7_4_unseen": PROPOSED_7_4_UNSEEN,
            "immutable_releases": ["v0.1.0", "v0.1.1", "v0.1.2"],
            "track_a_run": False,
            "new_public_media": False,
        },
    }
    write_json(OUT / "WP3_HUMAN_ADJ_INGEST_AND_NECESSITY_REPORT.json", layers)
    write_json(REPORTS / "WP3_HUMAN_ADJ_INGEST_AND_NECESSITY_REPORT.json", layers)
    # also snapshot pack
    write_json(
        OUT / "status_snapshot.json",
        {
            "claims": [c["claim_id"] for c in claims],
            "qa": [i["qa_id"] for i in qa["items"]],
            "necessity": nec["counts"],
        },
    )
    return layers


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "human_claims").mkdir(parents=True, exist_ok=True)
    claims = write_human_claims()
    qa = write_qa_and_graphs()
    nec = write_necessity()
    report = write_layered_status(claims, qa, nec)
    print(
        json.dumps(
            {
                "claims": [c["claim_id"] for c in claims],
                "necessity": nec["counts"],
                "formal_gold": False,
                "registry": str(REGISTRY_RECORDS.relative_to(REPO_ROOT)),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
