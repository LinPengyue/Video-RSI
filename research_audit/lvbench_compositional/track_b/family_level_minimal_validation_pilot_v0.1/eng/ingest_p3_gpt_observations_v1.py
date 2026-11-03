#!/usr/bin/env python3
"""Ingest user-approved P3 GPT multiframe observations (engineering only).

Status for all records: GPT_OBSERVATION_PENDING_HUMAN_SCIENTIFIC_ADJUDICATION.
Does NOT mint QA, Gold, formal Seen/Unseen, or unlock run_004.
Does NOT convert hypotheses into certified events.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

PILOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
P3 = PILOT / "p3_new_video_discovery"
OBS = P3 / "gpt_observations"
GATES = {
    "formal_seen_train": False,
    "formal_unseen": False,
    "formal_gold": False,
    "train_exposed": False,
    "seen_pool_frozen": False,
    "approve_expensive_track_a_rsi": False,
}
PILOT_ARTIFACT = "cce7499c5c94e6f7fe3e2b930164f841dce52474"
RECORD_STATUS = "GPT_OBSERVATION_PENDING_HUMAN_SCIENTIFIC_ADJUDICATION"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def dump(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# User-approved GPT observations (scientific content authored upstream; Cursor only stores).
OBSERVATIONS = [
    {
        "roi_id": "hROKtPqktO8_ROI_500_510",
        "video_id": "hROKtPqktO8",
        "t_start_s": 500,
        "t_end_s": 510,
        "relation_status": "NO_QUALIFYING_COMPOSITIONAL_RELATION",
        "direct_visual_observations": [
            "Storefront / shop-front scenes visible in sampled frames.",
            "Street scenes with pedestrians and a dog visible.",
            "Coast / shoreline scenes visible.",
            "Woman recording a selfie-style video visible.",
            "Multiple shot / camera cuts across the 500–510s window.",
        ],
        "inferences_and_hypotheses": [
            {
                "claim": "Shot order does not by itself establish causal event relations across cuts.",
                "tier": "JUDGMENT_NOT_CERTIFIED_EVENT",
                "must_not_upgrade_to": ["causal_chain", "directed_compositional_program"],
            }
        ],
        "forbidden_claims": [
            "Infer causal event sequence solely from cut order",
            "Mint compositional QA from this ROI",
        ],
    },
    {
        "roi_id": "hROKtPqktO8_ROI_1255_1265",
        "video_id": "hROKtPqktO8",
        "t_start_s": 1255,
        "t_end_s": 1265,
        "relation_status": "IDENTITY_HYPOTHESIS_ONLY",
        "direct_visual_observations": [
            "Rocky terrain / landscape visible.",
            "Hillside / slope scenery visible.",
            "A woman appears in later frames of this ROI.",
        ],
        "inferences_and_hypotheses": [
            {
                "claim": "Cannot prove the person completed a mountain-climbing action from these stills.",
                "tier": "JUDGMENT_NOT_CERTIFIED_EVENT",
                "must_not_upgrade_to": ["completed_climb_action"],
            },
            {
                "claim": "Possible cross-interval identity link to the woman visible in 500–510s; NOT authenticated.",
                "tier": "UNAUTHENTICATED_IDENTITY_HYPOTHESIS",
                "related_roi_id": "hROKtPqktO8_ROI_500_510",
                "must_not_upgrade_to": ["CrossIntervalSamePersonBind", "certified_identity"],
            },
        ],
        "forbidden_claims": [
            "Certify climb completion",
            "Auto-approve cross-ROI person bind to 500–510s woman",
        ],
    },
    {
        "roi_id": "iA_69g87Ilw_ROI_358_368",
        "video_id": "iA_69g87Ilw",
        "t_start_s": 358,
        "t_end_s": 368,
        "relation_status": "NO_QUALIFYING_COMPOSITIONAL_RELATION",
        "direct_visual_observations": [
            "A hand points toward fruit on a fruit platter / bowl.",
            "Camera subsequently turns toward a rest / lounge area.",
        ],
        "inferences_and_hypotheses": [
            {
                "claim": "Cannot infer that fruit was taken, eaten, or transferred.",
                "tier": "JUDGMENT_NOT_CERTIFIED_EVENT",
                "must_not_upgrade_to": ["take_fruit", "eat_fruit", "transfer_fruit", "purchase"],
            }
        ],
        "forbidden_claims": [
            "Pointing = taking/eating fruit",
            "Camera pan = completed object-state change",
        ],
    },
    {
        "roi_id": "iA_69g87Ilw_ROI_900_910",
        "video_id": "iA_69g87Ilw",
        "t_start_s": 900,
        "t_end_s": 910,
        "relation_status": "LOCAL_ACTION_HYPOTHESIS_ONLY",
        "direct_visual_observations": [
            "A man seated in a chair speaks toward the camera.",
            "Later frames show a hand interacting with a Do Not Disturb door hanger / plaque.",
        ],
        "inferences_and_hypotheses": [
            {
                "claim": "Local hanger/plaque pose changes are suggested by ordered stills, but hang / remove / flip completion is not proven.",
                "tier": "LOCAL_STATE_CHANGE_HYPOTHESIS_NOT_CERTIFIED",
                "must_not_upgrade_to": ["hang_complete", "remove_complete", "flip_complete"],
            },
            {
                "claim": "Cannot prove the speaking man and the hand belong to the same agent.",
                "tier": "UNAUTHENTICATED_IDENTITY_HYPOTHESIS",
                "must_not_upgrade_to": ["same_person_bind", "CrossIntervalSamePersonBind"],
            },
        ],
        "forbidden_claims": [
            "Certify completed hang/remove/flip of Do Not Disturb plaque",
            "Assume speaker identity equals hand identity",
        ],
    },
]


def load_roi(roi_id: str) -> dict:
    return json.loads((P3 / "rois" / f"{roi_id}.json").read_text(encoding="utf-8"))


def verify_frames(roi: dict) -> dict:
    mismatches = []
    missing = []
    evidence = []
    for fr in roi["frames"]:
        path = ROOT / fr["path"]
        rec = {
            "frame_id": fr["frame_id"],
            "t_s": fr["t_s"],
            "path": fr["path"],
            "declared_sha256": fr["sha256"],
            "bytes": fr["bytes"],
        }
        if not path.is_file():
            missing.append(fr["frame_id"])
            rec["sha_check"] = "MISSING"
        else:
            actual = sha_file(path)
            rec["actual_sha256"] = actual
            if actual != fr["sha256"]:
                mismatches.append(fr["frame_id"])
                rec["sha_check"] = "MISMATCH"
            else:
                rec["sha_check"] = "OK"
        evidence.append(rec)
    return {
        "n_frames": len(roi["frames"]),
        "n_ok": sum(1 for e in evidence if e.get("sha_check") == "OK"),
        "missing": missing,
        "mismatches": mismatches,
        "status": "PASS" if not missing and not mismatches else "FAIL",
        "evidence": evidence,
    }


def main() -> None:
    OBS.mkdir(parents=True, exist_ok=True)
    ingested_utc = utc_now()
    records = []
    sha_report = {"rois": {}, "overall": "PASS", "unmatched_observations": []}

    for spec in OBSERVATIONS:
        roi = load_roi(spec["roi_id"])
        assert roi["video_id"] == spec["video_id"]
        assert roi["t_start_s"] == spec["t_start_s"]
        assert roi["t_end_s"] == spec["t_end_s"]
        sha = verify_frames(roi)
        sha_report["rois"][spec["roi_id"]] = {
            "status": sha["status"],
            "n_ok": sha["n_ok"],
            "n_frames": sha["n_frames"],
            "missing": sha["missing"],
            "mismatches": sha["mismatches"],
        }
        if sha["status"] != "PASS":
            sha_report["overall"] = "FAIL"

        rec = {
            "schema": "family_level_pilot_p3_gpt_observation_v1",
            "record_status": RECORD_STATUS,
            "relation_status": spec["relation_status"],
            "roi_id": spec["roi_id"],
            "video_id": spec["video_id"],
            "t_start_s": spec["t_start_s"],
            "t_end_s": spec["t_end_s"],
            "ingested_utc": ingested_utc,
            "pilot_artifact_sha": PILOT_ARTIFACT,
            "working_branch": "research/lvbench-comp-video-grounded-evidence",
            "direct_visual_observations": spec["direct_visual_observations"],
            "inferences_and_hypotheses": spec["inferences_and_hypotheses"],
            "forbidden_claims": spec["forbidden_claims"],
            "hypothesis_not_certified_event": True,
            "qa_drafts_generated": 0,
            "auto_upgraded_to_scientific_label": False,
            "evidence": {
                "n_frames": sha["n_frames"],
                "sha_validation": sha["status"],
                "frames": [
                    {
                        "frame_id": e["frame_id"],
                        "t_s": e["t_s"],
                        "path": e["path"],
                        "sha256": e["declared_sha256"],
                        "sha_check": e["sha_check"],
                    }
                    for e in sha["evidence"]
                ],
            },
            "provenance": {
                "source_register": f"p3_new_video_discovery/{spec['video_id']}_SOURCE_REGISTER.json",
                "roi_manifest": f"p3_new_video_discovery/rois/{spec['roi_id']}.json",
                "batch_manifest": "p3_new_video_discovery/batch_manifest.json",
                "observer": "GPT_MULTIFRAME_STILL_OBSERVATION",
                "authority": "USER_APPROVED_FOR_ENGINEERING_INGEST_PENDING_HUMAN_SCIENTIFIC_ADJUDICATION",
                "not_independent_blind_review": True,
                "not_continuous_video_verified": True,
            },
            **GATES,
        }
        out = OBS / f"{spec['roi_id']}.json"
        dump(out, rec)
        records.append(
            {
                "roi_id": spec["roi_id"],
                "video_id": spec["video_id"],
                "relation_status": spec["relation_status"],
                "record_status": RECORD_STATUS,
                "record_path": str(out.relative_to(PILOT)),
                "sha_validation": sha["status"],
            }
        )

        # Update per-ROI observation slot (do not wipe frame list)
        roi["observation_slot"] = {
            "status": RECORD_STATUS,
            "relation_status": spec["relation_status"],
            "gpt_observation_path": str(out.relative_to(PILOT)),
            "pending_human_scientific_adjudication": True,
            "forbid_prefill_by_cursor": True,
            "qa_drafts_generated": 0,
        }
        dump(P3 / "rois" / f"{spec['roi_id']}.json", roi)

    # Expected ROI set completeness
    expected = {s["roi_id"] for s in OBSERVATIONS}
    on_disk = {p.stem for p in (P3 / "rois").glob("*.json")}
    if expected != on_disk:
        sha_report["unmatched_observations"] = {
            "expected_not_on_disk": sorted(expected - on_disk),
            "on_disk_without_observation": sorted(on_disk - expected),
        }
        sha_report["overall"] = "FAIL"

    index = {
        "schema": "p3_gpt_observation_index_v1",
        "ingested_utc": ingested_utc,
        "pilot_artifact_sha": PILOT_ARTIFACT,
        "record_status_uniform": RECORD_STATUS,
        "n_rois": len(records),
        "n_qualifying_compositional_relations": 0,
        "n_identity_hypothesis_only": sum(1 for r in records if r["relation_status"] == "IDENTITY_HYPOTHESIS_ONLY"),
        "n_local_action_hypothesis_only": sum(
            1 for r in records if r["relation_status"] == "LOCAL_ACTION_HYPOTHESIS_ONLY"
        ),
        "n_no_qualifying": sum(
            1 for r in records if r["relation_status"] == "NO_QUALIFYING_COMPOSITIONAL_RELATION"
        ),
        "records": records,
        "sha_validation": sha_report,
        "qa_drafts_generated": 0,
        "run_003_untouched": True,
        "run_004_status": "NOT_STARTED",
        "pilot_roles_unchanged": True,
        **GATES,
    }
    dump(OBS / "INDEX.json", index)
    dump(OBS / "SHA_VALIDATION_REPORT.json", sha_report)

    # Update batch manifest pointers
    man = json.loads((P3 / "batch_manifest.json").read_text(encoding="utf-8"))
    by_roi = {r["roi_id"]: r for r in man["rois"]}
    for spec in OBSERVATIONS:
        by_roi[spec["roi_id"]]["observation_slot"] = {
            "status": RECORD_STATUS,
            "relation_status": spec["relation_status"],
            "gpt_observation_path": f"gpt_observations/{spec['roi_id']}.json",
            "pending_human_scientific_adjudication": True,
            "qa_drafts_generated": 0,
        }
    man["rois"] = [by_roi[r["roi_id"]] for r in man["rois"]]
    man["gpt_observation_ingest"] = {
        "ingested_utc": ingested_utc,
        "index": "gpt_observations/INDEX.json",
        "record_status": RECORD_STATUS,
        "n_rois_observed": len(records),
        "n_qualifying_compositional_relations": 0,
        "sha_validation_overall": sha_report["overall"],
    }
    man["semantics_status"] = RECORD_STATUS
    man["run_004_status"] = "NOT_STARTED"
    for g, v in GATES.items():
        man[g] = v
    dump(P3 / "batch_manifest.json", man)

    # Keep run_004 blocked; update blockers to reflect ingest ≠ admission
    gate = {
        "run_004_status": "NOT_STARTED",
        "status": "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE",
        "blockers": [
            "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE from prior multiframe feasibility (0 qualifying)",
            "P3 GPT observations ingested but PENDING_HUMAN_SCIENTIFIC_ADJUDICATION",
            "0 P3 ROIs with NO_QUALIFYING / hypothesis-only — none admitted as directed composition",
            "No USER scientific upgrade of GPT observations to certified events or QA",
        ],
        "n_qualified_new_candidates": 0,
        "p3_gpt_observation_index": "p3_new_video_discovery/gpt_observations/INDEX.json",
        **GATES,
    }
    dump(PILOT / "RUN_004_GATE.json", gate)

    # Patch review pack / delivery notes without claiming science upgrade
    review_path = PILOT / "p4_scientific_review_pack/REVIEW_PACK.json"
    if review_path.is_file():
        pack = json.loads(review_path.read_text(encoding="utf-8"))
        pack["p3_new_discovery"] = {
            "videos": man["videos"],
            "n_rois": man["n_rois"],
            "n_frames": man["n_frames"],
            "status": RECORD_STATUS,
            "candidates_qualified": 0,
            "relation_statuses": {r["roi_id"]: r["relation_status"] for r in records},
            "note": "GPT observations stored for human adjudication; not auto-upgraded; 0 QA drafts.",
        }
        pack["run_004"] = {
            "status": "NOT_STARTED",
            "blockers": gate["blockers"],
        }
        for g, v in GATES.items():
            pack[g] = v
        dump(review_path, pack)

    delivery_path = PILOT / "DELIVERY_REPORT.json"
    if delivery_path.is_file():
        d = json.loads(delivery_path.read_text(encoding="utf-8"))
        d["p3_gpt_observation_ingest"] = {
            "ingested_utc": ingested_utc,
            "record_status": RECORD_STATUS,
            "n_rois": len(records),
            "sha_validation": sha_report["overall"],
            "n_qualifying": 0,
        }
        d["p5_run_004"] = {
            "status": "NOT_STARTED",
            "reason": "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE; P3 GPT obs pending human adjudication",
        }
        dump(delivery_path, d)

    print(
        json.dumps(
            {
                "ok": sha_report["overall"] == "PASS",
                "n_rois": len(records),
                "sha": sha_report["overall"],
                "run_004": "NOT_STARTED",
                "statuses": {r["roi_id"]: r["relation_status"] for r in records},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
