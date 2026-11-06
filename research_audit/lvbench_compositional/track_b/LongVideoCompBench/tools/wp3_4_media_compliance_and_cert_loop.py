#!/usr/bin/env python3
"""WP3.4: media compliance patch + first certification loop scaffolding.

Does NOT auto-certify identity, Necessity PASS, or formal_gold.
Does NOT rewrite WP3.3 history or force-push media out of git history.
Does NOT run Track A / expensive RSI / new video scans.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    DS_ROOT,
    FROZEN_5_2,
    PROPOSED_7_4_SEEN,
    PROPOSED_7_4_UNSEEN,
    REPO_ROOT,
    utc_now,
    write_json,
    sha256_file,
)

BASELINE = "ea1b79dadc897cd5d2be95b79548d01a3c3924cc"
WP3 = DS_ROOT / "wp3_production"
OUT = WP3 / "wp3_4"
REPORTS = DS_ROOT / "reports"
REGISTRY = OUT / "trusted_human_review_registry"
MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".webm", ".mkv", ".mov"}

# Post-WP3.2 policy: new third-party review media must not be Git-tracked until
# redistribution is cleared. Wave1/2 stills remain prior exposure (erratum notes).
FORBIDDEN_TRACKED_PREFIXES = [
    "research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wp3_3/ab_dev5/videos/",
]


def git_ls_files(pathspec: str | None = None) -> list[str]:
    cmd = ["git", "-C", str(REPO_ROOT), "ls-files"]
    if pathspec:
        cmd.append(pathspec)
    out = subprocess.check_output(cmd, text=True)
    return [ln for ln in out.splitlines() if ln.strip()]


def tracked_media_under(prefix: str) -> list[str]:
    files = git_ls_files(prefix)
    return [f for f in files if Path(f).suffix.lower() in MEDIA_EXTS]


def frame_hashes(dir_path: Path) -> list[dict[str, Any]]:
    rows = []
    if not dir_path.exists():
        return rows
    for p in sorted(dir_path.glob("*.jpg")):
        rows.append(
            {
                "name": p.name,
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
                "local_only": True,
                "not_for_github_redistribution": True,
            }
        )
    return rows


def write_p0_media_erratum() -> dict:
    ab_tracked_now = tracked_media_under(
        "research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production/wp3_3/ab_dev5/videos"
    )
    all_wp3 = tracked_media_under(
        "research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production"
    )
    compact_path = OUT / "media_hash_manifest_ab_dev5_jpgs_compact.json"
    if not compact_path.exists():
        raise SystemExit("missing compact hash manifest; run hash step first")
    compact = json.loads(compact_path.read_text())

    erratum = {
        "schema": "wp3_3_media_erratum_v1",
        "built_utc": utc_now(),
        "baseline_commit_with_exposure": BASELINE,
        "issue": (
            "WP3.3 commit ea1b79da force-added 160 AB DEV review JPGs to the public Git "
            "tree while reports still claimed no_public_third_party_media_added=true."
        ),
        "correction_this_round": {
            "action": "git_rm_cached_current_tree_only",
            "force_push": False,
            "history_rewrite": False,
            "history_still_contains_blobs": True,
            "history_cleanup": "DEFER_TO_REPO_ADMIN_IF_RIGHTS_REVIEW_REQUIRES",
            "n_files_untracked_from_head_tree": 160,
            "local_nonpublic_retention": (
                "research_audit/lvbench_compositional/track_b/local_media/"
                "wp3_production/wp3_3/ab_dev5_review_frames_untracked"
            ),
            "hash_manifest_compact": str(compact_path.relative_to(REPO_ROOT)),
            "n_sha256_retained": compact["n_files"],
        },
        "current_tree_audit": {
            "wp3_3_ab_dev5_videos_tracked_media": len(ab_tracked_now),
            "all_wp3_production_tracked_media": len(all_wp3),
            "prior_wave1_wave2_review_stills_still_tracked": True,
            "prior_wave_note": (
                "Wave1/2 review stills remain Git-tracked as prior exposure under "
                "WP3.1 LICENSE_UNCONFIRMED_STOP_NEW_PUBLIC_MEDIA continuity policy; "
                "WP3.4 primary remediation targets the WP3.3 AB 160-frame addition."
            ),
        },
        "policy_going_forward": {
            "no_github_image_submission_to_gpt_until_license_clear": True,
            "tests_must_audit_git_ls_files": True,
            "report_booleans_insufficient": True,
        },
        "status": "ERRATUM_RECORDED_CURRENT_TREE_UNTRACKED_PENDING_ADMIN_HISTORY",
    }
    write_json(OUT / "WP3_3_MEDIA_ERRATUM.json", erratum)
    write_json(REPORTS / "WP3_3_MEDIA_ERRATUM.json", erratum)
    return erratum


def write_p1_kbah_packet() -> dict:
    early_dir = (
        WP3
        / "wp3_3/ab_dev5/videos/KbahC-QCKU8/entity_first/review_frames/"
        / "KbahC-QCKU8_EF_PAIR1_EARLY_90_100"
    )
    late_dir = (
        WP3
        / "wp3_3/ab_dev5/videos/KbahC-QCKU8/entity_first/review_frames/"
        / "KbahC-QCKU8_EF_PAIR1_LATE_2160_2170"
    )
    # Prefer working-tree local files (untracked) or local_media mirror
    local_mirror = (
        REPO_ROOT
        / "research_audit/lvbench_compositional/track_b/local_media/wp3_production/"
        / "wp3_3/ab_dev5_review_frames_untracked/KbahC-QCKU8/entity_first/review_frames"
    )
    if not early_dir.exists():
        early_dir = local_mirror / "KbahC-QCKU8_EF_PAIR1_EARLY_90_100"
        late_dir = local_mirror / "KbahC-QCKU8_EF_PAIR1_LATE_2160_2170"

    packet = {
        "schema": "wp3_4_human_review_packet_v1",
        "pair_id": "KbahC-QCKU8_EF_PAIR1",
        "video_id": "KbahC-QCKU8",
        "built_utc": utc_now(),
        "baseline_commit": BASELINE,
        "discovery_method": "ENTITY_EVENT_FIRST_STABILITY_PROXY_V1",
        "prior_status": "PASS_CANDIDATE",
        "current_status": "AWAITING_HUMAN_SCIENTIFIC_OWNER",
        "auto_certified": False,
        "formal_gold": False,
        "windows": {"A": [90.0, 100.0], "B": [2160.0, 2170.0]},
        "evidence_local_nonpublic": {
            "A_review_frames": frame_hashes(early_dir),
            "B_review_frames": frame_hashes(late_dir),
            "A_clip": "research_audit/lvbench_compositional/track_b/local_media/wp3_production/wp3_3/KbahC-QCKU8/entity_first/KbahC-QCKU8_EF_PAIR1_EARLY_90_100/clip.mp4",
            "B_clip": "research_audit/lvbench_compositional/track_b/local_media/wp3_production/wp3_3/KbahC-QCKU8/entity_first/KbahC-QCKU8_EF_PAIR1_LATE_2160_2170/clip.mp4",
            "github_images_attached": False,
        },
        "gpt_visual_preliminary_NOT_HUMAN": {
            "label": "CURSOR_GPT_FRAME_VISUAL_PRELIMINARY",
            "not_human_certification": True,
            "observations": [
                "A: adult male (glasses, camo jacket) driving; child passenger in blue jacket; snow outside",
                "B mid: adult+child outside bakery/seafood house in snow; adult still camo jacket",
                "B ROI may include restaurant interior/exterior cuts — subject thrash risk inside 10s",
            ],
        },
        "minimum_human_decisions_required": [
            {
                "id": "H1_identity_bind",
                "question": "Is the adult in A the same physical person as the adult visible with the child in B?",
                "allowed": ["SAME_PERSON", "DIFFERENT", "UNRESOLVED"],
            },
            {
                "id": "H2_child_bind",
                "question": "Is the child in A the same child in B (clothing may change)?",
                "allowed": ["SAME_CHILD", "DIFFERENT", "UNRESOLVED"],
            },
            {
                "id": "H3_late_roi_subject_stability",
                "question": "Within B [2160–2170], does the primary adult identity remain stable, or does the ROI switch subjects/scenes?",
                "allowed": ["STABLE", "SWITCHES", "UNRESOLVED"],
            },
            {
                "id": "H4_a_only_adult_shortcut",
                "question": "If the answer targets the adult's earlier location, can A-only (unique adult male in cabin) answer without B?",
                "allowed": ["SHORTCUT_YES", "SHORTCUT_NO", "UNRESOLVED"],
            },
            {
                "id": "H5_necessity_gate",
                "question": "Does a cross-window QA require both A and B with the bind participating in the answer (not OCR/signage alone)?",
                "allowed": ["NECESSITY_PASS", "NECESSITY_FAIL", "UNKNOWN"],
                "note": "Do NOT auto-mark PASS; Human Scientific Owner only",
            },
        ],
        "qa_draft_blocked_until_human": True,
        "necessity_status": "NOT_RUN_AWAITING_HUMAN_FACTS",
        "signature_if_forced": {
            "draft": "LocatePerson→CrossIntervalSamePersonBind→QueryEarlierLocation",
            "label": "PROPOSED_SIGNATURE_UNVERIFIED",
            "ood": "NEW_VIDEO_NEW_QA_OLD_SIGNATURE_FAMILY_NOT_UNSEEN",
            "promote_unseen": False,
        },
        "human_adjudication": {
            "status": "NOT_OBTAINED_THIS_ROUND",
            "reviewer_identity": None,
            "reviewer_role": None,
            "decisions": {},
            "trusted_registry_record_id": None,
        },
    }
    write_json(OUT / "wp3_4_KbahC_EF_PAIR1_HUMAN_REVIEW_PACKET.json", packet)
    write_json(REPORTS / "wp3_4_KbahC_EF_PAIR1_HUMAN_REVIEW_PACKET.json", packet)
    return packet


def write_p1_usfv_packet() -> dict:
    prior = json.loads((WP3 / "wp3_2_USFV_PAIR2_HUMAN_REVIEW_PACKET.json").read_text())
    packet = {
        "schema": "wp3_4_human_review_packet_v1",
        "pair_id": "USfvmoalqsw_PAIR2",
        "video_id": "USfvmoalqsw",
        "built_utc": utc_now(),
        "baseline_commit": BASELINE,
        "prior_packet": str(
            (WP3 / "wp3_2_USFV_PAIR2_HUMAN_REVIEW_PACKET.json").relative_to(REPO_ROOT)
        ),
        "prior_status": "PENDING_HUMAN_IDENTITY_ADJUDICATION",
        "current_status": "PENDING_HUMAN_IDENTITY_ADJUDICATION",
        "auto_certified_same_person": False,
        "formal_gold": False,
        "windows": prior["windows"],
        "evidence_retained": {
            "dual_clip_packet": True,
            "frame_sha256_A": prior["evidence"][0]["frame_sha256"],
            "frame_sha256_B": prior["evidence"][1]["frame_sha256"],
            "github_new_images_this_round": False,
        },
        "signature_vs_historical_A": {
            "historical_A": "LocatePersonByAppearance/DetectPersonAndAppearance→CrossIntervalSamePersonBind→QueryLocation",
            "draft": "LocatePerson→CrossIntervalSamePersonBind→QueryEarlierLocation",
            "overlap": "SAME_FAMILY_CrossIntervalSamePersonBind_to_QueryLocation",
            "repetition": "OLD_SIGNATURE_FAMILY_ON_NEW_VIDEO",
            "atomic_novel_ood": False,
            "label": "PROPOSED_SIGNATURE_UNVERIFIED",
            "promote_unseen": False,
        },
        "minimum_human_decisions_required": [
            {
                "id": "H1_same_person",
                "question": "Is the plaid-gho man at the urban street (A) the same person speaking by the forest stream (B)?",
                "allowed": ["SAME_PERSON", "DIFFERENT", "UNRESOLVED"],
            },
            {
                "id": "H2_clothing_only_risk",
                "question": "Could clothing match alone mislead without face/body continuity on continuous clips?",
                "allowed": ["HIGH_RISK", "LOW_RISK", "UNRESOLVED"],
            },
            {
                "id": "H3_necessity",
                "question": "If identity holds, does QueryEarlierLocation require A+B (no OCR/shop-name single-window leak)?",
                "allowed": ["NECESSITY_PASS", "NECESSITY_FAIL", "UNKNOWN"],
            },
        ],
        "chatgpt_visual_match_NOT_HUMAN": prior.get("chatgpt_visual_match"),
        "necessity_status": "PROVISIONAL_PENDING_HUMAN",
        "human_adjudication": {
            "status": "NOT_OBTAINED_THIS_ROUND",
            "reviewer_identity": None,
            "reviewer_role": None,
            "decisions": {},
            "trusted_registry_record_id": None,
        },
    }
    write_json(OUT / "wp3_4_USFV_PAIR2_HUMAN_REVIEW_PACKET.json", packet)
    write_json(REPORTS / "wp3_4_USFV_PAIR2_HUMAN_REVIEW_PACKET.json", packet)
    # keep status file aligned
    write_json(
        WP3 / "wp3_4_USFV_PAIR2_STATUS.json",
        {
            "pair_id": "USfvmoalqsw_PAIR2",
            "relation_status": "PENDING_HUMAN_IDENTITY_ADJUDICATION",
            "qa_status": "AUDIT_DRAFT_ONLY",
            "necessity_status": "PROVISIONAL_PENDING_HUMAN",
            "human_adjudication_status": "NOT_OBTAINED_THIS_ROUND",
            "formal_gold": False,
            "import_ready": False,
            "auto_certified": False,
        },
    )
    return packet


def write_p2_necessity_gate(kbah: dict, usfv: dict) -> dict:
    """Necessity/QA only after human facts — blocked this round."""
    doc = {
        "schema": "wp3_4_necessity_and_qa_gate_v1",
        "built_utc": utc_now(),
        "rule": "Run A-only/B-only/A+B Necessity only after Human Scientific Owner certifies cross-window facts",
        "candidates": [
            {
                "pair_id": kbah["pair_id"],
                "human_facts_certified": False,
                "qa_emitted": False,
                "program_graph_emitted": False,
                "necessity_a_only": "NOT_RUN",
                "necessity_b_only": "NOT_RUN",
                "necessity_a_plus_b": "NOT_RUN",
                "necessity_final": "NOT_RUN_AWAITING_HUMAN",
                "shortcut_checks_pending": [
                    "single_window_unique_adult",
                    "language_prompt_leak",
                    "subtitle_ocr",
                    "bakery_signage_background",
                    "bind_participates_in_answer",
                ],
                "control_if_necessity_fails": True,
                "formal_gold": False,
                "dev_import": False,
            },
            {
                "pair_id": usfv["pair_id"],
                "human_facts_certified": False,
                "qa_emitted": False,
                "program_graph_emitted": False,
                "necessity_final": "PROVISIONAL_PENDING_HUMAN",
                "formal_gold": False,
                "dev_import": False,
            },
        ],
        "counts": {
            "qa_with_program_graph": 0,
            "necessity_PASS": 0,
            "necessity_FAIL": 0,
            "necessity_UNKNOWN_or_pending": 2,
            "formal_gold": 0,
            "dev_import_certified": 0,
        },
    }
    write_json(OUT / "wp3_4_necessity_qa_gate.json", doc)
    write_json(REPORTS / "wp3_4_necessity_qa_gate.json", doc)
    return doc


def init_trusted_registry() -> dict:
    """Append-only trusted human review registry (separate from staging)."""
    REGISTRY.mkdir(parents=True, exist_ok=True)
    readme = {
        "schema": "wp3_4_trusted_human_review_registry_v1",
        "built_utc": utc_now(),
        "path": str(REGISTRY.relative_to(REPO_ROOT)),
        "append_only": True,
        "separated_from_staging": True,
        "required_fields": [
            "record_id",
            "reviewer_identity",
            "reviewer_role",
            "source_video_id",
            "windows",
            "reviewed_evidence_hashes",
            "decision",
            "decision_scope",
            "timestamp_utc",
            "provenance_chain",
        ],
        "rejection_rule": (
            "Staging self-filled review_status=HUMAN_APPROVED alone cannot mint formal_gold; "
            "a matching trusted registry record with reviewer_identity is required."
        ),
        "records_jsonl": str((REGISTRY / "records.jsonl").relative_to(REPO_ROOT)),
        "records_this_round": 0,
        "note": "Empty registry is correct until a real Human Scientific Owner submits.",
    }
    records = REGISTRY / "records.jsonl"
    if not records.exists():
        records.write_text("", encoding="utf-8")
    write_json(REGISTRY / "REGISTRY_META.json", readme)
    write_json(OUT / "wp3_4_trusted_review_registry_meta.json", readme)
    write_json(REPORTS / "wp3_4_trusted_review_registry_meta.json", readme)
    return readme


def write_p4_eval_correction() -> dict:
    ab = json.loads((WP3 / "wp3_3" / "wp3_3_ab_prospective_discovery.json").read_text())
    triage = json.loads((WP3 / "wp3_3" / "ab_dev5" / "blind_triage.json").read_text())
    compute = ab.get("compute_cost_seconds") or {}
    doc = {
        "schema": "wp3_4_discovery_eval_correction_v1",
        "built_utc": utc_now(),
        "preserves_wp3_3_ab_artifact": str(
            (WP3 / "wp3_3" / "wp3_3_ab_prospective_discovery.json").relative_to(REPO_ROOT)
        ),
        "historical_ab_not_rewritten": True,
        "fixed_method_conclusion": "INDEPENDENT_STABILITY_PROXY_DISCOVERY_PILOT_INCONCLUSIVE",
        "must_not_claim": [
            "PROSPECTIVE_ENTITY_FIRST_DISCOVERY_SUPERIOR",
            "EF_PROVEN_BETTER_THAN_HF",
            "Kbah_IS_UNSEEN_OOD",
        ],
        "counts": {
            "HF_PASS_CANDIDATE": triage["summary"]["candidate_yield"][
                "histogram_first_PASS_CANDIDATE"
            ],
            "HF_pairs": 10,
            "EF_PASS_CANDIDATE": triage["summary"]["candidate_yield"][
                "entity_first_PASS_CANDIDATE"
            ],
            "EF_pairs": 10,
            "certified_relations": 0,
            "certified_new_signatures": 0,
            "formal_gold": 0,
            "FACT_VERIFIED": 0,
            "Necessity_PASS": 0,
        },
        "cost": {
            "histogram_seconds": compute.get("histogram_seconds"),
            "entity_first_seconds": compute.get("entity_first_seconds"),
            "extract_seconds": compute.get("extract_seconds"),
            "EF_compute_higher_than_HF": (
                (compute.get("entity_first_seconds") or 0)
                > (compute.get("histogram_seconds") or 0)
            ),
        },
        "kbah_status": "PASS_CANDIDATE_ONLY_NOT_UNSEEN",
    }
    write_json(OUT / "WP3_4_DISCOVERY_EVAL_CORRECTION.json", doc)
    write_json(REPORTS / "WP3_4_DISCOVERY_EVAL_CORRECTION.json", doc)
    return doc


def estimate_cert_cost() -> dict:
    return {
        "schema": "wp3_4_certification_cost_estimate_v1",
        "built_utc": utc_now(),
        "per_certifiable_qa_actual_this_round": None,
        "reason_null": "0 QA certified this round; cannot amortize",
        "observed_prep_cost_for_one_candidate_packet": {
            "human_reviewer_minutes_estimated_minimum": 25,
            "includes": [
                "watch both 10s clips continuously",
                "answer H1–H5 identity/stability/shortcut items",
                "write trusted registry record",
                "if facts pass: draft QA + A/B/A+B necessity (~+20 min)",
                "independent second Human for Gold gate (~+20–40 min)",
            ],
            "compute_seconds_discovery_amortized_note": "EF discovery ~3× HF wall time on same 5-video budget",
            "blocking_item": "Human Scientific Owner adjudication not obtained",
        },
        "bottleneck": "HUMAN_CERTIFICATION_NOT_SCANNING",
    }


def write_final_report(erratum, kbah, usfv, nec, reg, evalc, cost) -> dict:
    report = {
        "schema": "wp3_4_media_compliance_and_cert_loop_report_v1",
        "work_package": "WP3.4",
        "baseline_commit": BASELINE,
        "built_utc": utc_now(),
        "p0_media": {
            "erratum": erratum["status"],
            "ab_dev5_tracked_media_now": erratum["current_tree_audit"][
                "wp3_3_ab_dev5_videos_tracked_media"
            ],
            "history_still_exposed": True,
            "force_push": False,
        },
        "p1_human_packets": {
            "KbahC-QCKU8_EF_PAIR1": kbah["current_status"],
            "USfvmoalqsw_PAIR2": usfv["current_status"],
            "auto_certified": False,
        },
        "p2_counts": nec["counts"],
        "p3_registry": {
            "path": reg["path"],
            "records_this_round": reg["records_this_round"],
            "staging_alone_cannot_mint_gold": True,
        },
        "p4_eval": {
            "conclusion": evalc["fixed_method_conclusion"],
            "HF": f"{evalc['counts']['HF_PASS_CANDIDATE']}/10",
            "EF": f"{evalc['counts']['EF_PASS_CANDIDATE']}/10",
            "certified_relations": 0,
            "gold": 0,
        },
        "certification_cost": cost,
        "protections": {
            "immutable_releases": ["v0.1.0", "v0.1.1", "v0.1.2"],
            "frozen_5_2": FROZEN_5_2,
            "proposed_7_4": {
                "seen": PROPOSED_7_4_SEEN,
                "unseen": PROPOSED_7_4_UNSEEN,
                "status": "PROPOSED",
            },
            "track_a_modified": False,
            "track_a_rsi_run": False,
            "new_video_scan": False,
            "no_auto_gold": True,
        },
    }
    write_json(OUT / "WP3_4_MEDIA_COMPLIANCE_AND_CERT_LOOP_REPORT.json", report)
    write_json(REPORTS / "WP3_4_MEDIA_COMPLIANCE_AND_CERT_LOOP_REPORT.json", report)
    return report


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # Ensure compact manifest exists (created by prior shell step)
    if not (OUT / "media_hash_manifest_ab_dev5_jpgs_compact.json").exists():
        raise SystemExit("run hash manifest step before orchestrator")
    erratum = write_p0_media_erratum()
    kbah = write_p1_kbah_packet()
    usfv = write_p1_usfv_packet()
    nec = write_p2_necessity_gate(kbah, usfv)
    reg = init_trusted_registry()
    evalc = write_p4_eval_correction()
    cost = estimate_cert_cost()
    write_json(OUT / "wp3_4_certification_cost_estimate.json", cost)
    report = write_final_report(erratum, kbah, usfv, nec, reg, evalc, cost)
    print(
        json.dumps(
            {
                "ab_tracked_media": report["p0_media"]["ab_dev5_tracked_media_now"],
                "kbah": kbah["current_status"],
                "usfv": usfv["current_status"],
                "eval": evalc["fixed_method_conclusion"],
                "gold": 0,
                "necessity_pass": 0,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
