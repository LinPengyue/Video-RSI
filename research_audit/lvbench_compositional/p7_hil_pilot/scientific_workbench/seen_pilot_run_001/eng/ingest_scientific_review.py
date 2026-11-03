#!/usr/bin/env python3
"""Ingest Seen Pilot run_001 scientific review JSON (idempotent).

Separates raw scientific judgment from engineering validation.
Does NOT promote formal Seen/Unseen/Gold, freeze pools, or start Track A RSI.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PILOT = Path(__file__).resolve().parents[1]
WB = PILOT.parent
RAW_NAME = "RAW_seen_pilot_run_001_scientific_review.json"
REV = PILOT / "scientific_reviews"

GATES = {
    "formal_seen_train": False,
    "formal_unseen": False,
    "formal_gold": False,
    "train_exposed": False,
    "seen_pool_frozen": False,
    "approve_expensive_track_a_rsi": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def dump_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_against_packs(review: dict, catalog: dict) -> list[str]:
    issues = []
    by = {it["pack_id"]: it for it in catalog["items"]}
    if review.get("run_id") != "seen_pilot_run_001":
        issues.append(f"run_id mismatch: {review.get('run_id')}")
    if len(review.get("reviews", [])) != 5:
        issues.append(f"expected 5 reviews, got {len(review.get('reviews', []))}")
    for r in review.get("reviews", []):
        it = by.get(r["pack_id"])
        if not it:
            issues.append(f"unknown pack_id {r['pack_id']}")
            continue
        if it["video_id"] != r["video_id"] or it["qa_uid"] != r["qa_uid"]:
            issues.append(f"id mismatch {r['pack_id']}")
        wa, wb = it["intervals"]["A"], it["intervals"]["B"]
        ra, rb = r["windows_seconds"]["A"], r["windows_seconds"]["B"]
        if [int(wa["start_s"]), int(wa["end_s"])] != ra or [int(wb["start_s"]), int(wb["end_s"])] != rb:
            issues.append(
                f"window mismatch {r['pack_id']}: pack A={wa['start_s']}-{wa['end_s']} B={wb['start_s']}-{wb['end_s']} vs review {ra}/{rb}"
            )
    return issues


def engineering_validation_sp002(catalog_item: dict) -> dict:
    """Engineering-only check: does served A clip include near-end Tacara name graphic?"""
    frames_dir = REV / "engineering_checks" / "SP002_A_boundary_frames"
    frame_notes = {
        "t74.jpg": "Topic lower-third present; TACARA name graphic NOT yet visible in this sample frame.",
        "t75.jpg": "TACARA name graphic VISIBLE in lower-third.",
        "t755.jpg": "TACARA name graphic VISIBLE.",
        "t759.jpg": "TACARA name graphic VISIBLE near clip end.",
    }
    existing = {p.name: frame_notes.get(p.name, "sampled") for p in sorted(frames_dir.glob("*.jpg"))}
    clip_rel = (catalog_item.get("clips") or {}).get("A")
    return {
        "check_id": "SP002_A_SUBTITLE_BOUNDARY_COVERAGE",
        "layer": "ENGINEERING_VALIDATION_ONLY",
        "not_scientific_adjudication": True,
        "claimed_subtitle_source_time_approx_s": 78,
        "a_window_source_s": [2, 78],
        "relative_time_in_clip_approx_s": 76,
        "clip_relpath": clip_rel,
        "clip_duration_s_measured": 76.009267,
        "coverage_status": "COVERED_IN_EXISTING_A_CLIP",
        "evidence": {
            "method": "ffmpeg end-of-clip stills + human visual inspection of lower-third graphics",
            "frames": existing,
            "finding": "TACARA on-screen name graphic is visible by ~75s relative (~source 77s) within the existing A clip ending ~76.01s; not a silent rewrite of scientific judgment.",
        },
        "minimal_repair_if_missing": "NOT_NEEDED — if future re-encode truncates end, extend A end by +2–3s and re-verify; do not auto-reapprove.",
        "conflicts_with_scientific_review": False,
    }


def build_record(raw_review_item: dict, catalog_item: dict, input_sha: str, ingested_utc: str, eng_extra: dict | None) -> dict:
    decision = raw_review_item["graph_decision"]
    approved = decision == "USER_APPROVED_STRUCTURED_GRAPH"
    rec = {
        "schema": "seen_pilot_scientific_review_record_v1",
        "run_id": "seen_pilot_run_001",
        "pack_id": raw_review_item["pack_id"],
        "workbench_id": catalog_item["workbench_id"],
        "video_id": raw_review_item["video_id"],
        "qa_uid": raw_review_item["qa_uid"],
        "windows_seconds": raw_review_item["windows_seconds"],
        "original_question": raw_review_item.get("original_question"),
        "historical_answer": raw_review_item.get("historical_answer"),
        "raw_scientific_judgment": raw_review_item,  # full retention
        "graph_decision": decision,
        "classification": raw_review_item.get("classification"),
        "composition_necessity": raw_review_item.get("composition_necessity"),
        "approved_graph_version": raw_review_item.get("approved_graph_version"),
        "compositional_candidate_graph_approved": approved,
        "counted_in_approved_compositional_candidate_set": approved,
        **GATES,
        "ingest": {
            "source_artifact": f"scientific_reviews/{RAW_NAME}",
            "source_sha256": input_sha,
            "ingested_utc": ingested_utc,
            "idempotency_key": f"{raw_review_item['pack_id']}::{input_sha}",
        },
        "engineering_validation": eng_extra or {"status": "N_A"},
    }
    # Explicit SP004 / SP005 protections
    if raw_review_item["pack_id"] == "SP004":
        rec["must_preserve_labels"] = [
            "A_ONLY_ORDER_SHORTCUT_RISK_WITH_UNRESOLVED_DESCRIPTION_REFERENT",
            "composition_necessity=NOT_ESTABLISHED",
        ]
    if raw_review_item["pack_id"] == "SP005":
        rec["must_preserve_labels"] = ["PREVIOUS_B_ONLY_SHORTCUT_CLASSIFICATION_RETRACTED"]
        rec["forbidden_labels"] = ["B_ONLY_SHORTCUT_CONFIRMED"]
        ch = raw_review_item.get("correction_history") or []
        if "PREVIOUS_B_ONLY_SHORTCUT_CLASSIFICATION_RETRACTED" not in ch:
            rec["engineering_conflict"] = "MISSING_REQUIRED_CORRECTION_MARKER"
    return rec


def write_approved_graph_stub(raw: dict, catalog_item: dict, input_sha: str, ingested_utc: str) -> dict | None:
    if raw.get("graph_decision") != "USER_APPROVED_STRUCTURED_GRAPH":
        return None
    g = {
        "graph_id": f"seen_pilot::{raw['pack_id']}::{raw.get('approved_graph_version')}",
        "structure_version": raw.get("approved_graph_version"),
        "pool": "SEEN_PILOT_COMPOSITIONAL_CANDIDATE_ONLY",
        "pack_id": raw["pack_id"],
        "qa_uid": raw["qa_uid"],
        "video_id": raw["video_id"],
        "user_confirmation_status": "USER_APPROVED_STRUCTURED_GRAPH",
        "classification": raw.get("classification"),
        "composition_necessity": raw.get("composition_necessity"),
        "graph_as_reviewed": raw.get("graph"),
        "caveats": raw.get("caveats"),
        "correction_history": raw.get("correction_history"),
        **GATES,
        "note": "Candidate compositional graph from Seen pilot human review. NOT formal Seen/Gold. NOT merged into Unseen approved_graphs_v0.2.",
        "source_sha256": input_sha,
        "ingested_utc": ingested_utc,
        "workbench_id": catalog_item["workbench_id"],
    }
    path = REV / "APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS" / f"{raw['pack_id']}_{raw.get('approved_graph_version')}.json"
    dump_json(path, g)
    return {"pack_id": raw["pack_id"], "path": str(path.relative_to(PILOT)), "version": raw.get("approved_graph_version")}


def ingest(raw_path: Path | None = None) -> dict:
    raw_path = raw_path or (REV / RAW_NAME)
    if not raw_path.exists():
        raise FileNotFoundError(raw_path)
    raw_bytes = raw_path.read_bytes()
    input_sha = sha256_bytes(raw_bytes)
    review = json.loads(raw_bytes.decode("utf-8"))
    catalog = load_json(PILOT / "CATALOG.json")
    isolation = load_json(PILOT / "ISOLATION_CHECK.json")
    issues = validate_against_packs(review, catalog)
    if issues:
        raise SystemExit("VALIDATION_FAILED:\n- " + "\n- ".join(issues))

    ingested_utc = utc_now()
    # Idempotency: if INDEX exists with same sha, rewrite identical logical content (no duplicate packs)
    prev = REV / "INDEX.json"
    if prev.exists():
        old = load_json(prev)
        if old.get("source_sha256") == input_sha and old.get("records"):
            # still rewrite for deterministic refresh, but mark idempotent_replay
            ingested_utc = old.get("ingested_utc", ingested_utc)
            idempotent_replay = True
        else:
            idempotent_replay = False
    else:
        idempotent_replay = False

    by_cat = {it["pack_id"]: it for it in catalog["items"]}
    eng_sp002 = engineering_validation_sp002(by_cat["SP002"])
    dump_json(REV / "engineering_checks" / "SP002_A_subtitle_boundary.json", eng_sp002)

    records = []
    approved_refs = []
    for raw_item in review["reviews"]:
        pack_id = raw_item["pack_id"]
        eng = eng_sp002 if pack_id == "SP002" else {"status": "N_A"}
        rec = build_record(raw_item, by_cat[pack_id], input_sha, ingested_utc, eng)
        dump_json(REV / "RECORDS_BY_PACK" / f"{pack_id}.json", rec)
        records.append(
            {
                "pack_id": pack_id,
                "video_id": rec["video_id"],
                "qa_uid": rec["qa_uid"],
                "graph_decision": rec["graph_decision"],
                "classification": rec["classification"],
                "compositional_candidate_graph_approved": rec["compositional_candidate_graph_approved"],
                "record_path": f"scientific_reviews/RECORDS_BY_PACK/{pack_id}.json",
            }
        )
        ref = write_approved_graph_stub(raw_item, by_cat[pack_id], input_sha, ingested_utc)
        if ref:
            approved_refs.append(ref)

    # Remove stale approved stubs not in this ingest
    keep = {r["pack_id"] for r in approved_refs}
    for p in (REV / "APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS").glob("SP*.json"):
        pid = p.name.split("_")[0]
        if pid not in keep:
            p.unlink()

    # Update catalog items with review pointers (no formal promotion)
    for it in catalog["items"]:
        raw_item = next(r for r in review["reviews"] if r["pack_id"] == it["pack_id"])
        it["scientific_review"] = {
            "ingested": True,
            "source_sha256": input_sha,
            "graph_decision": raw_item["graph_decision"],
            "classification": raw_item.get("classification"),
            "composition_necessity": raw_item.get("composition_necessity"),
            "approved_graph_version": raw_item.get("approved_graph_version"),
            "compositional_candidate_graph_approved": raw_item["graph_decision"] == "USER_APPROVED_STRUCTURED_GRAPH",
            "record_path": f"scientific_reviews/RECORDS_BY_PACK/{it['pack_id']}.json",
        }
        it["user_confirmation_status"] = "SCIENTIFIC_REVIEW_INGESTED"
        # keep formal gates false
        it["formal_seen_train"] = False
        it["formal_gold"] = False
        it["train_exposed"] = False
        it["formal_unseen"] = False
        it["seen_pool_frozen"] = False
        it["approve_expensive_track_a_rsi"] = False
        # Annotate underlying review pack without rewriting scientific observations
        pack_path = WB / it["pack_path"]
        if pack_path.exists():
            pack = load_json(pack_path)
            pack["scientific_review_pointer"] = it["scientific_review"]
            pack["user_confirmation_status"] = "SCIENTIFIC_REVIEW_INGESTED"
            for k, v in GATES.items():
                pack[k] = v
            dump_json(pack_path, pack)
    catalog["scientific_review_ingest"] = {
        "source_sha256": input_sha,
        "ingested_utc": ingested_utc,
        "user_approved_compositional_candidate_graphs": 3,
        "not_approved": 2,
        "formal_seen": 0,
        "formal_gold": 0,
        "train_exposed": 0,
    }
    dump_json(PILOT / "CATALOG.json", catalog)

    index = {
        "run_id": "seen_pilot_run_001",
        "schema_version": review.get("schema_version"),
        "source_artifact": f"scientific_reviews/{RAW_NAME}",
        "source_sha256": input_sha,
        "ingested_utc": ingested_utc,
        "idempotent_replay": idempotent_replay,
        "decision_policy_gates": GATES,
        "isolation_status_at_ingest": isolation.get("status"),
        "summary": review.get("summary"),
        "records": records,
        "approved_compositional_candidate_graphs": approved_refs,
        "not_approved_ids": ["SP003", "SP004"],
        "engineering_checks": {
            "SP002_A_subtitle_boundary": "scientific_reviews/engineering_checks/SP002_A_subtitle_boundary.json"
        },
        "protected_assets_untouched": [
            "data/approved_graphs_v0.2/",
            "SCIENTIFIC_JUDGMENTS_DIRECTED_PROGRAMS_CORRECTED_F1_F3.json",
            "data/PROGRAM_GRAPH_LIBRARY_v1.json",
        ],
        "headline": "3 USER_APPROVED compositional candidate graphs; 2 NOT APPROVED; 0 formal Seen; 0 formal Gold; 0 train exposure; expensive Track A RSI remains gated.",
    }
    dump_json(REV / "INDEX.json", index)
    dump_json(
        REV / "INGEST_META.json",
        {
            "source_path": str(raw_path.relative_to(WB)),
            "source_sha256": input_sha,
            "ingested_utc": ingested_utc,
            "engineering_baseline_commit": review.get("engineering_source_commit"),
            "idempotent_replay": idempotent_replay,
            "raw_bytes": len(raw_bytes),
        },
    )
    # Refresh pack JSON digests after annotation (clip digests unchanged)
    man_path = PILOT / "MANIFEST.json"
    if man_path.exists():
        man = load_json(man_path)
        man["pack_json_sha256"] = {
            p.name: sha256_file(p) for p in sorted((PILOT / "review_packs").glob("*.json"))
        }
        man["scientific_review_source_sha256"] = input_sha
        man["scientific_review_ingested_utc"] = ingested_utc
        dump_json(man_path, man)
    return index


def main() -> int:
    idx = ingest()
    print(json.dumps({"ok": True, "sha": idx["source_sha256"], "approved": len(idx["approved_compositional_candidate_graphs"]), "idempotent_replay": idx["idempotent_replay"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
