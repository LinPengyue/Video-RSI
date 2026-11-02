#!/usr/bin/env python3
"""Engineering-only builder for Seen Human Annotation Pilot run_001.

Does NOT certify formal Seen / freeze train pool / assign Gold / adjudicate science.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]  # Video-RSI
WB = Path(__file__).resolve().parents[2]  # scientific_workbench
PILOT = Path(__file__).resolve().parents[1]  # seen_pilot_run_001
REPO_AUDIT = ROOT / "research_audit" / "lvbench_compositional"

FFMPEG = Path.home() / ".cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffmpeg"
FFPROBE = FFMPEG.parent / "ffprobe"
LV_VIDEOS = Path("/home/descfly/lpy/dataset/LVBench/videos")

RUN_ID = "seen_pilot_run_001"
STATUS = "PENDING_HUMAN_VIDEO_REVIEW"
POINT_PAD_BEFORE = 5.0
POINT_PAD_AFTER = 10.0
MIN_CLIP_S = 3.0

# Hard-isolated pilot picks: remaining historical train videos NOT in
# Unseen/approved-graph/test holdout sets. Prefer non-construction-exposed
# when possible; construction_exposed is recorded but is NOT a hard Seen block.
SELECTED = [
    {
        "pack_id": "SP001",
        "qa_uid": "LVCOMP-V2-036",
        "video_id": "aJI8XTa_DII",
        "reason": "Remaining historical train video; identify_person+query_location; dual windows; not Unseen/test/approved-graph; not construction-exposed.",
    },
    {
        "pack_id": "SP002",
        "qa_uid": "LVCOMP-V2-045",
        "video_id": "vHlSoxg8WHo",
        "reason": "Remaining historical train video; identify_person+query_relation; dual windows; not Unseen/test/approved-graph; not construction-exposed.",
    },
    {
        "pack_id": "SP003",
        "qa_uid": "LVCOMP-V2-100",
        "video_id": "2LH3JCGkEBU",
        "reason": "Remaining historical train video; identify_event_result+query_action; dual windows; not Unseen/test/approved-graph; not construction-exposed.",
    },
    {
        "pack_id": "SP004",
        "qa_uid": "LVCOMP-V2-037",
        "video_id": "f8DKD78BrQA",
        "reason": "Remaining historical train video; identify_event_result+query_action; point-like dual refs with padded extract; not Unseen/test/approved-graph; not construction-exposed.",
    },
    {
        "pack_id": "SP005",
        "qa_uid": "LVCOMP-V2-026",
        "video_id": "KLIa2UaE2KE",
        "reason": "Remaining historical train video; identify_person+query_location; short dual windows; not Unseen/test/approved-graph; not construction-exposed.",
    },
]

_MMSS = re.compile(r"^(\d+):([0-5]\d(?:\.\d+)?)$")
_HHMMSS = re.compile(r"^(\d+):([0-5]\d):([0-5]\d(?:\.\d+)?)$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_ts(s: str) -> float:
    s = s.strip()
    m = _HHMMSS.match(s)
    if m:
        return int(m.group(1)) * 3600 + int(float(m.group(2))) * 60 + float(m.group(3))
    m = _MMSS.match(s)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    raise ValueError(f"unparsed timestamp: {s}")


def parse_range(ref: str) -> tuple[float, float]:
    a, b = ref.split("-", 1)
    return parse_ts(a), parse_ts(b)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ffprobe_duration(path: Path) -> float | None:
    if not FFPROBE.exists() or not path.exists():
        return None
    r = subprocess.run(
        [str(FFPROBE), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return None
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def extract_clip(src: Path, dst: Path, start: float, end: float) -> dict:
    dur = max(end - start, MIN_CLIP_S)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not FFMPEG.exists():
        return {"extract_status": "MEDIA_UNAVAILABLE", "reason": "ffmpeg_binary_missing", "path": str(dst)}
    if not src.exists():
        return {"extract_status": "MEDIA_UNAVAILABLE", "reason": "source_video_missing", "path": str(dst)}
    cmd = [
        str(FFMPEG),
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(src),
        "-t",
        f"{dur:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(dst),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        return {
            "extract_status": "MEDIA_UNAVAILABLE",
            "reason": "ffmpeg_failed",
            "stderr_tail": (r.stderr or "")[-500:],
            "path": str(dst),
        }
    return {
        "extract_status": "OK",
        "path": str(dst),
        "bytes": dst.stat().st_size,
        "sha256": sha256_file(dst),
        "t_start_s": start,
        "t_end_s": start + dur,
        "duration_s": dur,
        "ffmpeg": str(FFMPEG),
    }


def load_candidates() -> dict[str, dict]:
    path = REPO_AUDIT / "v2" / "candidates.jsonl"
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            o = json.loads(line)
            out[o["id"]] = o
    return out


def build_exclusion() -> dict:
    split = json.loads((REPO_AUDIT / "v2_1" / "pilot_split.json").read_text(encoding="utf-8"))
    sealed = json.loads((REPO_AUDIT / "track_b" / "SEALED_POOL_SPLIT_POLICY.json").read_text(encoding="utf-8"))
    approved_vids, approved_uids = set(), set()
    for p in (WB / "data" / "approved_graphs_v0.2").glob("P7_*.json"):
        g = json.loads(p.read_text(encoding="utf-8"))
        approved_vids.add(g["video_id"])
        approved_uids.add(g["qa_uid"])
    cat = json.loads((REPO_AUDIT / "p7_hil_pilot" / "round_004" / "CANDIDATE_CATALOG.json").read_text(encoding="utf-8"))
    unseen_vids = {x["video_id"] for x in cat.get("unseen_structure_candidates", [])}
    judg = json.loads((WB / "SCIENTIFIC_JUDGMENTS_DIRECTED_PROGRAMS_CORRECTED_F1_F3.json").read_text(encoding="utf-8"))
    wb_cat = json.loads((WB / "WORKBENCH_CATALOG.json").read_text(encoding="utf-8"))
    wb_map = {it["workbench_id"]: it for it in wb_cat["items"]}
    wb_unseen_vids, wb_unseen_uids = set(), set()
    for uid, item in judg.get("items", {}).items():
        if item.get("bucket_seen_unseen_control_or_hold") == "Unseen":
            wb_unseen_uids.add(uid)
            if uid in wb_map:
                wb_unseen_vids.add(wb_map[uid]["video_id"])
    v3 = json.loads((REPO_AUDIT / "targeted_v3" / "strict_split_pilot.json").read_text(encoding="utf-8"))
    v21_test = set(split.get("test_videos", []))
    v3_test = set(v3.get("test_videos", []))
    composition_protect = {
        "VTCDQYYKA9o",
        "TJR1oYDDTwg",
        "Cm73ma6Ibcs",
        "LLSJrEgOOtw",
        "Z86xysw5Ncc",
        "xi6r3hZe5Tg",
    }
    hard_exclude_videos = sorted(
        approved_vids | unseen_vids | wb_unseen_vids | composition_protect | v21_test | v3_test
    )
    hard_exclude_uids = sorted(
        approved_uids | wb_unseen_uids | set(split.get("test_ids", [])) | set(v3.get("test_ids", []))
    )
    exposed = sorted(sealed.get("exposed_or_construction", []))
    sealed_res = sealed.get("sealed_reservoir", {}).get("current_ids", [])
    return {
        "run_id": RUN_ID,
        "created_utc": utc_now(),
        "hard_exclude_videos": hard_exclude_videos,
        "hard_exclude_qa_uids": hard_exclude_uids,
        "sources": {
            "approved_structured_graphs_v0.2": sorted(approved_vids),
            "approved_qa_uids": sorted(approved_uids),
            "round4_unseen_structure_candidates": sorted(unseen_vids),
            "workbench_user_preclass_unseen": sorted(wb_unseen_vids),
            "v2_1_test_videos": sorted(v21_test),
            "v3_test_videos": sorted(v3_test),
            "composition_protect_extra": sorted(composition_protect),
        },
        "informational_not_hard_block": {
            "construction_exposed_or_assistant_discovery": exposed,
            "note": "Exposed/construction videos are ineligible for sealed blind final reservoir, but are NOT automatically formal Seen. For this Seen pilot, hard isolation is Unseen/approved-graph/test only; construction_exposed is recorded per pack.",
            "sealed_reservoir_current_ids": sealed_res,
        },
        "historical_train_pool_note": {
            "source": "v2_1/pilot_split.json train_ids",
            "historical_train_n": len(split["train_ids"]),
            "label_status": "HISTORICAL_CANDIDATE_ONLY_NOT_FORMAL_SEEN",
        },
    }


def window_plan(ref: str, video_dur: float | None) -> dict:
    t0, t1 = parse_range(ref)
    basis = {
        "source_time_reference": ref,
        "parsed_start_s": t0,
        "parsed_end_s": t1,
        "padding_applied": False,
    }
    start, end = t0, t1
    if abs(t1 - t0) < 1e-6:
        start = max(0.0, t0 - POINT_PAD_BEFORE)
        end = t0 + POINT_PAD_AFTER
        basis["padding_applied"] = True
        basis["pad_before_s"] = POINT_PAD_BEFORE
        basis["pad_after_s"] = POINT_PAD_AFTER
        basis["note"] = "Point-like official time reference; engineering pad only — not a scientific timing approval."
    if end - start < MIN_CLIP_S:
        end = start + MIN_CLIP_S
        basis["min_duration_enforced_s"] = MIN_CLIP_S
    if video_dur is not None:
        start = min(max(0.0, start), max(0.0, video_dur - MIN_CLIP_S))
        end = min(end, video_dur)
        if end <= start:
            end = min(video_dur, start + MIN_CLIP_S)
        basis["video_duration_s"] = video_dur
    return {"start_s": start, "end_s": end, "basis": basis}


def main() -> int:
    cands = load_candidates()
    exclusion = build_exclusion()
    hard_v = set(exclusion["hard_exclude_videos"])
    hard_u = set(exclusion["hard_exclude_qa_uids"])
    exposed = set(exclusion["informational_not_hard_block"]["construction_exposed_or_assistant_discovery"])

    (PILOT / "media").mkdir(parents=True, exist_ok=True)
    (PILOT / "review_packs").mkdir(parents=True, exist_ok=True)

    catalog_items = []
    isolation_blocks = []
    manifest_files = []
    blank_items = {}

    for sel in SELECTED:
        qa_uid = sel["qa_uid"]
        video_id = sel["video_id"]
        pack_id = sel["pack_id"]
        workbench_id = f"SEEN_PILOT_{pack_id}"

        if video_id in hard_v or qa_uid in hard_u:
            isolation_blocks.append(
                {
                    "pack_id": pack_id,
                    "video_id": video_id,
                    "qa_uid": qa_uid,
                    "blocked": True,
                    "reasons": [
                        *(["video_in_hard_exclude"] if video_id in hard_v else []),
                        *(["qa_uid_in_hard_exclude"] if qa_uid in hard_u else []),
                    ],
                }
            )
            continue

        o = cands[qa_uid]
        assert o["video_id"] == video_id
        src = LV_VIDEOS / f"{video_id}.mp4"
        vdur = ffprobe_duration(src)
        refs = o.get("time_references") or []
        if len(refs) < 2:
            isolation_blocks.append(
                {
                    "pack_id": pack_id,
                    "video_id": video_id,
                    "qa_uid": qa_uid,
                    "blocked": True,
                    "reasons": ["missing_dual_time_references"],
                }
            )
            continue

        plan_a = window_plan(refs[0], vdur)
        plan_b = window_plan(refs[1], vdur)
        media_dir = PILOT / "media" / pack_id
        rel_a = f"seen_pilot_run_001/media/{pack_id}/A_{video_id}_{int(plan_a['start_s'])}_{int(plan_a['end_s'])}.mp4"
        rel_b = f"seen_pilot_run_001/media/{pack_id}/B_{video_id}_{int(plan_b['start_s'])}_{int(plan_b['end_s'])}.mp4"
        path_a = WB / rel_a
        path_b = WB / rel_b
        # ensure under pilot media
        path_a = media_dir / path_a.name
        path_b = media_dir / path_b.name
        rel_a = f"seen_pilot_run_001/media/{pack_id}/{path_a.name}"
        rel_b = f"seen_pilot_run_001/media/{pack_id}/{path_b.name}"

        ex_a = extract_clip(src, path_a, plan_a["start_s"], plan_a["end_s"])
        ex_b = extract_clip(src, path_b, plan_b["start_s"], plan_b["end_s"])
        media_status = "OK"
        if ex_a.get("extract_status") != "OK" or ex_b.get("extract_status") != "OK":
            media_status = "MEDIA_UNAVAILABLE"

        pack = {
            "run_id": RUN_ID,
            "pack_id": pack_id,
            "workbench_id": workbench_id,
            "user_confirmation_status": STATUS,
            "formal_seen_train": False,
            "formal_unseen": False,
            "formal_gold": False,
            "train_exposed": False,
            "historical_train_label_present": True,
            "historical_train_label_status": "HISTORICAL_CANDIDATE_ONLY_NOT_FORMAL_SEEN",
            "construction_exposed": video_id in exposed,
            "video_id": video_id,
            "qa_uid": qa_uid,
            "source": {
                "candidates_jsonl": "research_audit/lvbench_compositional/v2/candidates.jsonl",
                "pilot_split": "research_audit/lvbench_compositional/v2_1/pilot_split.json",
                "source_uids": o.get("source_uids"),
                "composition_schema_historical": o.get("composition_schema"),
                "origin": o.get("origin"),
                "phase": o.get("phase"),
                "video_verified_field_in_source": o.get("video_verified"),
            },
            "selection_reason": sel["reason"],
            "qa_clue_unverified": {
                "question": o.get("new_question"),
                "answer": o.get("new_answer"),
                "status": "UNVERIFIED_HISTORICAL_CLUE_ONLY",
                "source_questions": o.get("source_questions"),
                "source_answers": o.get("source_answers"),
            },
            "intervals": {
                "A": plan_a,
                "B": plan_b,
                "official_time_references": refs,
                "timestamp_precision": "FROM_OFFICIAL_CANDIDATE_TIME_REFERENCES_PLUS_ENGINEERING_PAD_IF_POINTLIKE",
            },
            "media": {
                "status": media_status,
                "source_full_video": str(src) if src.exists() else None,
                "source_full_sha256": sha256_file(src) if src.exists() else None,
                "A": {
                    **ex_a,
                    "relpath": rel_a if ex_a.get("extract_status") == "OK" else None,
                    "window_basis": plan_a["basis"],
                },
                "B": {
                    **ex_b,
                    "relpath": rel_b if ex_b.get("extract_status") == "OK" else None,
                    "window_basis": plan_b["basis"],
                },
            },
            "human_review_form_fields": {
                "events": "",
                "persons": "",
                "objects": "",
                "actions": "",
                "temporal_relations": "",
                "identity_binding": "",
                "a_only_sufficient": "",
                "b_only_sufficient": "",
                "a_plus_b_supports_user_answer": "",
                "directed_program_draft": "",
                "rationale_and_open_issues": "",
                "reviewer": "",
                "reviewed_utc": "",
            },
            "forbidden_auto_labels": [
                "USER_APPROVED_STRUCTURED_GRAPH",
                "FORMAL_SEEN_TRAIN",
                "TRAIN_EXPOSED",
                "GOLD",
            ],
        }
        pack_path = PILOT / "review_packs" / f"{pack_id}_{video_id}.json"
        pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for side, ex in (("A", ex_a), ("B", ex_b)):
            if ex.get("extract_status") == "OK":
                manifest_files.append(
                    {
                        "role": f"{pack_id}_{side}",
                        "relpath": pack["media"][side]["relpath"],
                        "sha256": ex["sha256"],
                        "bytes": ex["bytes"],
                    }
                )
        catalog_items.append(
            {
                "workbench_id": workbench_id,
                "pack_id": pack_id,
                "section": "seen_pilot_run_001",
                "qa_uid": qa_uid,
                "video_id": video_id,
                "user_confirmation_status": STATUS,
                "formal_seen_train": False,
                "formal_gold": False,
                "train_exposed": False,
                "media_status": media_status,
                "clips": {
                    "A": pack["media"]["A"].get("relpath"),
                    "B": pack["media"]["B"].get("relpath"),
                },
                "intervals": pack["intervals"],
                "qa_clue_unverified": pack["qa_clue_unverified"],
                "pack_path": f"seen_pilot_run_001/review_packs/{pack_path.name}",
                "construction_exposed": pack["construction_exposed"],
                "selection_reason": sel["reason"],
            }
        )
        blank_items[workbench_id] = {
            "user_confirmation_status": STATUS,
            "formal_seen_train": False,
            "formal_gold": False,
            "train_exposed": False,
            "media_status": media_status,
            "events": "",
            "persons": "",
            "objects": "",
            "actions": "",
            "temporal_relations": "",
            "identity_binding": "",
            "a_only_sufficient": "",
            "b_only_sufficient": "",
            "a_plus_b_supports_user_answer": "",
            "directed_program_draft": "",
            "rationale_and_open_issues": "",
            "reviewer": "",
            "reviewed_utc": "",
            "pilot_unknown_keep": "PRESERVE_ON_ROUNDTRIP",
        }
        isolation_blocks.append(
            {
                "pack_id": pack_id,
                "video_id": video_id,
                "qa_uid": qa_uid,
                "blocked": False,
                "hard_exclude_hit": False,
                "construction_exposed": video_id in exposed,
                "media_status": media_status,
            }
        )

    # Isolation check summary against Unseen/test
    selected_vids = {x["video_id"] for x in catalog_items}
    selected_uids = {x["qa_uid"] for x in catalog_items}
    leak_v = sorted(selected_vids & hard_v)
    leak_u = sorted(selected_uids & hard_u)
    isolation = {
        "run_id": RUN_ID,
        "created_utc": utc_now(),
        "status": "PASS" if not leak_v and not leak_u and catalog_items else "FAIL",
        "selected_count": len(catalog_items),
        "selected_video_ids": sorted(selected_vids),
        "selected_qa_uids": sorted(selected_uids),
        "hard_exclude_video_leakage": leak_v,
        "hard_exclude_uid_leakage": leak_u,
        "block_if_any_unseen_or_test_video_in_seen_candidates": bool(leak_v or leak_u),
        "historical_train_label_does_not_certify_formal_seen": True,
        "packs": isolation_blocks,
        "notes": [
            "Old train labels remain HISTORICAL_CANDIDATE_ONLY_NOT_FORMAL_SEEN.",
            "No pack is auto-marked USER_APPROVED_STRUCTURED_GRAPH / FORMAL_SEEN_TRAIN / TRAIN_EXPOSED / GOLD.",
            "MEDIA_UNAVAILABLE packs must not display as human-reviewed.",
        ],
    }

    catalog = {
        "run_id": RUN_ID,
        "created_utc": utc_now(),
        "user_confirmation_status_uniform": STATUS,
        "formal_seen_train": False,
        "formal_gold": False,
        "train_exposed": False,
        "does_not_overwrite_approved_unseen_graphs": True,
        "items": catalog_items,
    }
    judgments_blank = {
        "schema": "p7_seen_pilot_judgments_v1",
        "run_id": RUN_ID,
        "exported_utc": None,
        "disclaimer": "Seen pilot human review draft only; Cursor did not adjudicate formal Seen/Unseen/Gold.",
        "workbench_version": "v2",
        "items": blank_items,
    }
    manifest = {
        "run_id": RUN_ID,
        "created_utc": utc_now(),
        "files": manifest_files,
        "pack_json_sha256": {},
    }
    for p in sorted((PILOT / "review_packs").glob("*.json")):
        manifest["pack_json_sha256"][p.name] = sha256_file(p)

    (PILOT / "EXCLUSION_LIST.json").write_text(json.dumps(exclusion, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PILOT / "ISOLATION_CHECK.json").write_text(json.dumps(isolation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PILOT / "CATALOG.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PILOT / "JUDGMENTS_BLANK.json").write_text(json.dumps(judgments_blank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PILOT / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    selection = {
        "run_id": RUN_ID,
        "selected": SELECTED,
        "count": len(catalog_items),
        "target_range": [4, 6],
        "note": "Do not pad with isolation-failing videos. Historical train label ≠ formal Seen.",
    }
    (PILOT / "SELECTION.json").write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"isolation_status": isolation["status"], "n": len(catalog_items), "media": [i["media_status"] for i in catalog_items]}, indent=2))
    return 0 if isolation["status"] == "PASS" and catalog_items else 1


if __name__ == "__main__":
    sys.exit(main())
