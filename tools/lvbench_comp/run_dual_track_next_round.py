#!/usr/bin/env python3
"""Dual-track next round: Shared review logging, Track A readiness, Track B discovery.

No RSI runs, no auto-SUPPORTED, no formal split assignment.
"""

from __future__ import annotations

import csv
import json
import math
import re
import shutil
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
META = Path("/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl")
VIDEO_DIR = Path("/home/descfly/lpy/dataset/LVBench/videos")
FFMPEG = Path.home() / ".cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffmpeg"
FFPROBE = Path.home() / ".cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffprobe"
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")

SHARED = ROOT / "research_audit/lvbench_compositional/video_grounded_pilot"
TRACK_A = ROOT / "research_audit/lvbench_compositional/track_a"
TRACK_B = ROOT / "research_audit/lvbench_compositional/track_b"
BASELINE = "db62562f03904a79dec8d5988f6ae9250ccd5517"


def parse_mmss_range(text: str) -> tuple[float, float]:
    a, b = [p.strip() for p in text.split("-", 1)]

    def one(tok: str) -> float:
        parts = tok.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

    return one(a), one(b)


def format_ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}" if h else f"{m:02d}:{s:06.3f}"


def run(cmd: list[str], timeout: float = 240.0) -> None:
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-2000:] or "ffmpeg failed")


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        [str(FFPROBE), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return float(out.stdout.strip())


def probe_has_audio(path: Path) -> bool:
    out = subprocess.run(
        [str(FFPROBE), "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(out.stdout.strip())


def cut_clip(source: Path, dest: Path, start: float, end: float, has_audio: bool) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.2, end - start)
    preroll = 15.0
    pre = max(0.0, start - preroll)
    fine = start - pre
    cmd = [
        str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{pre:.3f}", "-i", str(source), "-ss", f"{fine:.3f}", "-t", f"{duration:.3f}",
        "-map", "0:v:0", "-vf", "scale=960:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
    ]
    if has_audio:
        cmd += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "96k"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(dest)]
    run(cmd)
    return {"path": str(dest), "bytes": dest.stat().st_size, "start": start, "end": end, "audio": has_audio and probe_has_audio(dest)}


def contact_sheet(clip: Path, dest: Path, video_start: float, n: int = 8) -> dict:
    frame_dir = dest.parent / f"{dest.stem}_frames"
    if frame_dir.exists():
        shutil.rmtree(frame_dir)
    frame_dir.mkdir(parents=True)
    dur = probe_duration(clip)
    offsets = [((i + 0.5) / n) * dur for i in range(n)]
    srt = frame_dir / "timestamps.srt"

    def srt_clock(sec: float) -> str:
        h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60); ms = int(round((sec - int(sec)) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, off in enumerate(offsets, 1):
        lines.append(f"{i}\n{srt_clock(off)} --> {srt_clock(min(dur, off + 0.4))}\n{format_ts(video_start + off)}\n")
    srt.write_text("\n".join(lines), encoding="utf-8")
    burned = FONT.is_file()
    for i, off in enumerate(offsets, 1):
        out_frame = frame_dir / f"frame_{i:02d}.jpg"
        vf = "scale=480:-2"
        if burned:
            sub = str(srt).replace("\\", "\\\\").replace(":", "\\:").replace("'", r"\'")
            fonts = str(FONT.parent).replace("\\", "\\\\").replace(":", "\\:")
            style = "FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=0,Alignment=8,MarginV=12"
            vf = f"scale=480:-2,subtitles={sub}:fontsdir={fonts}:force_style='{style}'"
        run([str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{off:.3f}", "-i", str(clip), "-frames:v", "1", "-vf", vf, "-q:v", "4", str(out_frame)], timeout=60)
    cols, rows = 4, int(math.ceil(n / 4))
    run([str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", "-start_number", "1", "-i", str(frame_dir / "frame_%02d.jpg"), "-frames:v", "1", "-vf", f"tile={cols}x{rows}:nb_frames={n}:padding=4:margin=4:color=black", "-q:v", "4", str(dest)], timeout=60)
    return {"path": str(dest), "bytes": dest.stat().st_size}


def resolve_answer(qa: dict) -> str:
    opts = dict(re.findall(r"\(([A-D])\)\s*([^\n(]+)", qa["question"]))
    return opts.get(str(qa["answer"]).strip(), str(qa["answer"]))


def load_qa(video_id: str, uids: list[str]) -> list[dict]:
    want = {str(u) for u in uids}
    for line in META.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec["key"] != video_id:
            continue
        out = []
        for qa in rec["qa"]:
            if str(qa["uid"]) in want:
                out.append(
                    {
                        "uid": str(qa["uid"]),
                        "question": qa["question"],
                        "answer_letter": qa["answer"],
                        "answer_text": resolve_answer(qa),
                        "time_reference": qa.get("time_reference"),
                        "question_type": qa.get("question_type"),
                    }
                )
        return out
    return []


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Shared: independent review logging
# ---------------------------------------------------------------------------

INDEPENDENT_REVIEWS = [
    {
        "candidate_id": "VG-001",
        "video_id": "JTa_Ue2MSwc",
        "prior_status": "PENDING_HUMAN_REVIEW",
        "new_status": "VISUALLY_SUPPORTED_BUT_NOT_NOVEL",
        "review_source": "INDEPENDENT_EXTERNAL_REVIEW",
        "not_cursor_video_confirmation": True,
        "rationale": "UID 5132 correct answer already covers Sierra vs Kindall conflict; single-clip shortcut exists. Keep only as positive control, not formal Unseen.",
        "enter_formal_unseen": False,
        "retain_as": "POSITIVE_CONTROL_ONLY",
        "data_partition_status": "UNASSIGNED",
        "applicable_track": "BOTH_CANDIDATE",
    },
    {
        "candidate_id": "VG-002",
        "video_id": "_T2Avd3tFHc",
        "prior_status": "PENDING_HUMAN_REVIEW",
        "new_status": "UNCERTAIN_AGENT",
        "review_source": "INDEPENDENT_EXTERNAL_REVIEW",
        "not_cursor_video_confirmation": True,
        "rationale": "Bell-ringing scene has multiple participants; Mikhail cannot be confirmed as the unique action agent.",
        "enter_formal_unseen": False,
        "retain_as": "REJECT_OR_REWORK_FACT_B",
        "data_partition_status": "UNASSIGNED",
        "applicable_track": "A_DEV",
    },
    {
        "candidate_id": "VG-003",
        "video_id": "TJR1oYDDTwg",
        "prior_status": "PENDING_HUMAN_REVIEW",
        "new_status": "NO_CLEAR_NEW_FACT",
        "review_source": "INDEPENDENT_EXTERNAL_REVIEW",
        "not_cursor_video_confirmation": True,
        "rationale": "Prince identity matching is feasible, but the proposed Fact B window lacks a reliable independent follow-up action.",
        "enter_formal_unseen": False,
        "retain_as": "REJECT_OR_REWORK_FACT_B",
        "data_partition_status": "UNASSIGNED",
        "applicable_track": "B_CANDIDATE",
    },
]


def update_shared() -> None:
    SHARED.mkdir(parents=True, exist_ok=True)
    with (SHARED / "independent_review.jsonl").open("w", encoding="utf-8") as handle:
        for row in INDEPENDENT_REVIEWS:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Update evidence candidates statuses without inventing Cursor visual support.
    path = SHARED / "evidence_candidates.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {r["candidate_id"]: r for r in INDEPENDENT_REVIEWS}
    for row in rows:
        rev = by_id.get(row["candidate_id"])
        if not rev:
            continue
        row["status"] = rev["new_status"]
        row["independent_review_source"] = rev["review_source"]
        row["independent_review_rationale"] = rev["rationale"]
        row["enter_formal_unseen"] = False
        row["data_partition_status"] = "UNASSIGNED"
        row["cursor_did_not_visually_confirm"] = True
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    (SHARED / "FILTER_RULES.md").write_text(
        """# Shared filter rules (post independent review)

1. Independent external review conclusions are authoritative over Cursor-extracted media status.
2. Do **not** rewrite independent review as Cursor video confirmation.
3. None of VG-001/002/003 enter formal Unseen as currently stated.
4. VG-001 may be retained only as a **positive control** (`VISUALLY_SUPPORTED_BUT_NOT_NOVEL`).
5. `UNCERTAIN_AGENT` / `NO_CLEAR_NEW_FACT` require Fact B rework or rejection.
6. Prefer event-first discovery: clear observable event → agent → other-interval identity/condition clue.
7. Always separate `fact_novelty` from `composition_novelty` against official Q/options/answer coverage.
8. Reject significant single-clip shortcuts for formal sets; controls may keep them if labeled.
9. `data_partition_status` remains `UNASSIGNED` until an explicit dual-track assignment protocol.
10. Track B sealed final-test videos/schemas must not guide Track A harness/evolver tuning.
""",
        encoding="utf-8",
    )

    manifest = json.loads((SHARED / "review_manifest.json").read_text(encoding="utf-8"))
    manifest["independent_review_applied"] = True
    manifest["independent_review_file"] = "independent_review.jsonl"
    for cand in manifest.get("candidates", []):
        rev = by_id.get(cand["candidate_id"])
        if rev:
            cand["status"] = rev["new_status"]
            cand["review_source"] = rev["review_source"]
            cand["enter_formal_unseen"] = False
            cand["data_partition_status"] = "UNASSIGNED"
    (SHARED / "review_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = (SHARED / "REPORT.md").read_text(encoding="utf-8")
    block = """

## Independent review (Shared)

Source: `INDEPENDENT_EXTERNAL_REVIEW` (not Cursor video confirmation). All remain `data_partition_status=UNASSIGNED`.

| ID | New status | Formal Unseen |
|---|---|---|
| VG-001 | VISUALLY_SUPPORTED_BUT_NOT_NOVEL | No (positive control only) |
| VG-002 | UNCERTAIN_AGENT | No |
| VG-003 | NO_CLEAR_NEW_FACT | No |

See `independent_review.jsonl` and `FILTER_RULES.md`.
"""
    if "## Independent review (Shared)" not in report:
        (SHARED / "REPORT.md").write_text(report.rstrip() + "\n" + block, encoding="utf-8")


# ---------------------------------------------------------------------------
# Track A
# ---------------------------------------------------------------------------

def build_track_a() -> dict:
    TRACK_A.mkdir(parents=True, exist_ok=True)
    inventory = [
        {
            "item_id": "LVCOMP-V2-002",
            "kind": "VERIFIED_COMPOSITION_QUESTION",
            "video_id": "JTa_Ue2MSwc",
            "schema": "identify_person + query_action",
            "facts_verified": True,
            "composition_verified": True,
            "source": "pilot_v2_2/test_video_review.csv",
            "note": "Both Fact A/B and composition visually supported in v2.2 review.",
            "usable_as_formal_unseen_alone": False,
            "reason": "Only 1 video; need more supported items/videos. Also related to positive-control family.",
        },
        {
            "item_id": "LVCOMP-V2-003",
            "kind": "VERIFIED_COMPOSITION_QUESTION",
            "video_id": "JTa_Ue2MSwc",
            "schema": "identify_person + query_action",
            "facts_verified": True,
            "composition_verified": True,
            "source": "pilot_v2_2/test_video_review.csv",
            "note": "Slap composition supported; same video as 002.",
            "usable_as_formal_unseen_alone": False,
            "reason": "Same-video concentration; insufficient for multi-video Unseen gate.",
        },
        {
            "item_id": "LVCOMP-V2-100",
            "kind": "VERIFIED_PRIMITIVE_QUERY_ACTION",
            "video_id": "2LH3JCGkEBU",
            "schema": "identify_event_result + query_action",
            "facts_verified": False,
            "composition_verified": False,
            "action_primitive_status": "ACTION_PRIMITIVE_VALID",
            "source": "pilot_v2_2/train_primitive_audit.csv",
            "note": "Semantic audit only for Seen-B action alignment; not a full video-supported composition.",
            "usable_as_formal_unseen_alone": False,
            "reason": "Train-side primitive evidence, not Unseen composition.",
        },
        {
            "item_id": "LVCOMP-V2-015/024/025/031",
            "kind": "PENDING_OR_UNCERTAIN_COMPOSITION",
            "video_id": "mixed",
            "schema": "identify_person + query_action",
            "facts_verified": False,
            "composition_verified": False,
            "source": "pilot_v2_2/test_video_review.csv",
            "note": "UNCERTAIN in v2.2; facts or composition not fully confirmed.",
            "usable_as_formal_unseen_alone": False,
            "reason": "Do not equate official Fact A/B text with composition validity.",
        },
        {
            "item_id": "VG-001",
            "kind": "INDEPENDENT_REVIEW_POSITIVE_CONTROL",
            "video_id": "JTa_Ue2MSwc",
            "schema": "identify_person + query_action",
            "facts_verified": "EXTERNAL_REVIEW_CLAIMS_VISUAL_SUPPORT",
            "composition_verified": False,
            "source": "independent_review.jsonl",
            "note": "VISUALLY_SUPPORTED_BUT_NOT_NOVEL; single-clip shortcut; not novel Unseen.",
            "usable_as_formal_unseen_alone": False,
            "reason": "Positive control only.",
        },
        {
            "item_id": "v3_new_unseen_U-001..007",
            "kind": "UNVERIFIED_STRUCTURAL_CANDIDATES",
            "video_id": "mixed",
            "schema": "identify_person + query_action",
            "facts_verified": False,
            "composition_verified": False,
            "source": "targeted_v3/unseen_candidates.jsonl",
            "note": "Official-QA-traceable structure only; PENDING_HUMAN_REVIEW.",
            "usable_as_formal_unseen_alone": False,
            "reason": "No video certification.",
        },
    ]
    write_csv(TRACK_A / "verified_inventory.csv", inventory)

    protocol = {
        "name": "track_a_min_protocol_draft_v0",
        "frozen_video_model": True,
        "initial_harness_policy": "Start from a declared Initial Harness snapshot. Do NOT reuse H_S1 as a strict held-out final evaluator (prior LVBench exposure).",
        "evolution_set_requirements": [
            "Primitive A instances present",
            "Primitive B instances present",
            "Target composition signature absent (strict leave-out)",
        ],
        "isolation": {
            "no_video_overlap_train_test": True,
            "no_uid_overlap_train_test": True,
            "development_vs_final_test": "Separate sealed final test; development may iterate",
        },
        "shortcut_checks": ["single_clip_answerability", "name_leak_in_question", "official_qa_semantic_coverage"],
        "arms": [
            {"arm_id": "no_harness", "description": "Frozen model, no harness tools/planner beyond raw VLM"},
            {"arm_id": "fixed_strong_planner", "description": "Fixed strong planner/prompt; no evolver updates"},
            {"arm_id": "vanilla_rsi", "description": "Existing RSI loop without new composition-oriented mechanisms"},
            {"arm_id": "new_rsi", "description": "RSI with hypothesized composition-transfer mechanisms"},
        ],
        "ablations_under_fair_budget": [
            {"arm_id": "harness_only", "description": "Allow harness edits/tools without evolver search"},
            {"arm_id": "harness_plus_evolver", "description": "Harness + evolver with matched step/token budget"},
        ],
        "fair_budget_notes": "Match max tool calls, frames, tokens, and wall-clock per item across arms; no arm-specific leakage from sealed B tests.",
    }
    (TRACK_A / "protocol_draft.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    matrix = {
        "baselines": protocol["arms"],
        "ablations": protocol["ablations_under_fair_budget"],
        "mechanism_hypotheses": [
            {
                "id": "H1_transferable_entity_binder",
                "claim": "A harness skill that stores (referring_expression → entity_trace → later_interval_query) and reuses binding checks will improve Unseen identify_person+query_action without schema memorization.",
                "not_just_prompt_rewrite": True,
                "targets_error_mode": "entity binding failure / wrong agent across intervals",
            },
            {
                "id": "H2_evidence_dependency_verifier",
                "claim": "Before final answer, require explicit dual-interval evidence tickets; reject answers supportable from one clip alone. Evolver mutates verification predicates, not only surface prompts.",
                "not_just_prompt_rewrite": True,
                "targets_error_mode": "single-clip shortcut / premature answer",
            },
        ],
        "dry_run_only": True,
    }
    (TRACK_A / "experiment_matrix.json").write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Lightweight config check (no model calls)
    config = {
        "experiment": "track_a_comp_rsi_prep",
        "dry_run": True,
        "forbid_paid_api": True,
        "forbid_hs1_as_final_judge": True,
        "arms_required": [a["arm_id"] for a in protocol["arms"]],
        "isolation_checks": ["schema_leaveout", "video_disjoint", "uid_disjoint", "shortcut_flag_present"],
        "min_supported_unseen_items_to_start": 6,
        "min_supported_unseen_videos": 3,
        "min_valid_seen_query_action_items": 4,
        "min_valid_seen_query_action_videos": 3,
        "min_seen_identify_person_items": 8,
        "current_counts": {
            "supported_composition_questions": 2,
            "supported_composition_videos": 1,
            "valid_query_action_train_audited": 1,
            "status": "BLOCKED",
        },
    }
    (TRACK_A / "configs" / "dry_run_arms.json").parent.mkdir(parents=True, exist_ok=True)
    (TRACK_A / "configs" / "dry_run_arms.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    check = {
        "ok_for_expensive_rsi": False,
        "checks": {
            "supported_unseen_items_ge_6": False,
            "supported_unseen_videos_ge_3": False,
            "valid_seen_query_action_ge_4": False,
            "hs1_not_used_as_final": True,
            "dry_run_config_present": True,
        },
        "blockers": [
            "Only 2 video-supported composition questions on 1 video (JTa).",
            "Seen query_action VALID audit still too thin for multi-video transfer claims.",
            "v3 new Unseen remain UNVERIFIED; VG-001/002/003 cannot fill Unseen.",
        ],
    }
    (TRACK_A / "config_check_result.json").write_text(json.dumps(check, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readiness = f"""# TRACK A READINESS

Role: minimal strict compositional generalization benchmark + Video Agent RSI method prep.  
Baseline shared commit: `{BASELINE}`  
This round: **no expensive RSI / no paid API**.

## 1. Verified inventory (summary)

| Class | Count / status |
|---|---|
| Verified composition questions (facts+composition) | **2** (`LVCOMP-V2-002/003`, both `JTa_Ue2MSwc`) |
| Verified composition videos | **1** |
| Action-primitive VALID (train audit) | **1** (`LVCOMP-V2-100`) |
| Independent-review positive control | VG-001 (`VISUALLY_SUPPORTED_BUT_NOT_NOVEL`) |
| Unverified structural Unseen (v3) | 7 new + several seeds |
| Rejected/blocked for Unseen | VG-002 `UNCERTAIN_AGENT`, VG-003 `NO_CLEAR_NEW_FACT` |

**Do not equate correct Fact A/B text with a valid composition question.**

Details: `verified_inventory.csv`.

## 2. Minimal evaluation protocol draft

See `protocol_draft.json`.

- Evolution set contains primitives A and B separately.
- Target signature (`identify_person + query_action` for first study) **strict leave-out**.
- Train/test: no video overlap, no UID overlap.
- Shortcut audit required.
- Development set ≠ sealed final test.
- **Initial Harness only** for new runs; **H_S1 must not** be the strict final judge (prior full LVBench exposure).

## 3. Lightweight experiment framework

- Config skeleton: `configs/dry_run_arms.json`
- Arm matrix: `experiment_matrix.json`
- Config check result: `config_check_result.json` → `ok_for_expensive_rsi=false`

Arms: `no_harness`, `fixed_strong_planner`, `vanilla_rsi`, `new_rsi`; ablations `harness_only`, `harness_plus_evolver` under fair budget.

## 4. Mechanism hypotheses (composition transfer)

1. **H1 transferable entity binder** — reusable referring-expression → entity-trace → later-interval query skill (not a fixed prompt template).
2. **H2 evidence-dependency verifier** — require dual-interval evidence tickets; evolver mutates verification predicates to block single-clip answers.

## 5. Missing samples to start a credible diagnostic run

Minimum gate (draft):

- ≥6 video-supported Unseen composition items
- ≥3 Unseen videos
- ≥4 VALID Seen query_action items across ≥3 videos
- ≥8 Seen identify_person items across ≥4 videos
- Shortcut labels complete; sealed final held out

**Current:** far below gate → **BLOCKED**.

## 6. Estimated cost / blockers

- Cost if unblocked later: small dry diagnostic (tens of items × 4 arms) before any large RSI; still requires human video review hours first.
- Blockers: supported Unseen diversity; Seen-B action alignment; contamination risk if H_S1 reused as judge; Track B sealed tests must not tune A.

## Status

**Track A method prep: READY FOR PLANNING / NOT READY FOR RSI EXECUTION.**
"""
    (TRACK_A / "TRACK_A_READINESS.md").write_text(readiness, encoding="utf-8")
    return check


# ---------------------------------------------------------------------------
# Track B
# ---------------------------------------------------------------------------

TRACK_B_CANDIDATES = [
    {
        "candidate_id": "TB-001",
        "video_id": "_T2Avd3tFHc",
        "video_type": "travel_vlog",
        "discovery_mode": "event_first_rework_VG002",
        "composition_signature": "identify_person + query_location",
        "primitive_operations": ["identify_person", "query_location"],
        "bridge_entity": "Mikhail",
        "fact_event": {
            "role": "FACT_B_LOCATION",
            "content": "The first place the elder goes with the vlogger team is a bar.",
            "time": "05:30-05:50",
            "uids": ["2876"],
            "source": "OFFICIAL_QA",
        },
        "fact_identity": {
            "role": "FACT_A_IDENTITY",
            "content": "The elder who joins the travel is Mikhail.",
            "time": "04:44-04:44",
            "uids": ["2873"],
            "source": "OFFICIAL_QA",
        },
        "composed_question_sketch": "Where does the elder who joins the vlogger on their travel first go with the team?",
        "composed_answer_sketch": "A bar",
        "fact_novelty": "LOW",
        "composition_novelty": "MEDIUM",
        "official_semantic_coverage": "Both facts appear in official QA; composition replaces the name Mikhail with the joining-elder referring expression before asking location.",
        "single_clip_shortcut_risk": "MEDIUM",
        "agent_clarity": "HIGH_IF_ELDER_VISUALLY_UNIQUE",
        "extract": True,
        "status": "PENDING_INDEPENDENT_REVIEW",
        "data_partition_status": "UNASSIGNED",
        "applicable_track": "BOTH_CANDIDATE",
    },
    {
        "candidate_id": "TB-002",
        "video_id": "_T2Avd3tFHc",
        "video_type": "travel_vlog",
        "discovery_mode": "event_first_rework_VG002",
        "composition_signature": "identify_person + query_location",
        "primitive_operations": ["identify_person", "query_location"],
        "bridge_entity": "Mikhail",
        "fact_event": {
            "role": "FACT_B_LOCATION",
            "content": "Vlogger team members invite Mikhail to the hotel on the first night.",
            "time": "15:58-16:07",
            "uids": ["2890"],
            "source": "OFFICIAL_QA",
        },
        "fact_identity": {
            "role": "FACT_A_IDENTITY",
            "content": "The elder who joins the travel is Mikhail.",
            "time": "04:44-04:44",
            "uids": ["2873"],
            "source": "OFFICIAL_QA",
        },
        "composed_question_sketch": "Where do the vlogger team members invite the elder who joins their travel on the first night?",
        "composed_answer_sketch": "The hotel",
        "fact_novelty": "LOW",
        "composition_novelty": "LOW_MEDIUM",
        "official_semantic_coverage": "UID 2890 already names Mikhail in the question; novelty depends on replacing the name with the joining-elder cue from 2873 without leaking the hotel answer elsewhere.",
        "single_clip_shortcut_risk": "HIGH_IF_NAME_LEFT_IN_QUESTION",
        "agent_clarity": "HIGH",
        "extract": True,
        "status": "PENDING_INDEPENDENT_REVIEW",
        "data_partition_status": "UNASSIGNED",
        "applicable_track": "A_DEV",
    },
    {
        "candidate_id": "TB-003",
        "video_id": "TJR1oYDDTwg",
        "video_type": "story_animation",
        "discovery_mode": "event_first_rework_VG003",
        "composition_signature": "identify_person + query_action",
        "primitive_operations": ["identify_person", "query_action"],
        "bridge_entity": "Prince",
        "fact_event": {
            "role": "FACT_B_ACTION",
            "content": "During the performance, the prince plays the drum set (princess plays guitar).",
            "time": "20:04-20:13",
            "uids": ["273"],
            "source": "OFFICIAL_QA",
        },
        "fact_identity": {
            "role": "FACT_A_IDENTITY",
            "content": "After the king talks to the green dragon, the one who embraces the king is the Prince.",
            "time": "05:18-05:22",
            "uids": ["257"],
            "source": "OFFICIAL_QA",
        },
        "composed_question_sketch": "What instrument does the person who embraces the king after the green-dragon talk play during the later performance?",
        "composed_answer_sketch": "Drum set",
        "fact_novelty": "LOW",
        "composition_novelty": "MEDIUM",
        "official_semantic_coverage": "273 already pairs prince with drums; composition hides the name behind the embrace event. Rejected prior Fact B (post-net) stays discarded.",
        "single_clip_shortcut_risk": "MEDIUM",
        "agent_clarity": "MEDIUM_STYLIZED",
        "extract": True,
        "status": "PENDING_INDEPENDENT_REVIEW",
        "data_partition_status": "UNASSIGNED",
        "applicable_track": "B_CANDIDATE",
    },
    {
        "candidate_id": "TB-004",
        "video_id": "vaL_vSdZKZo",
        "video_type": "documentary_interview",
        "discovery_mode": "event_first_new_video",
        "composition_signature": "identify_person + query_action",
        "primitive_operations": ["identify_person", "query_action"],
        "bridge_entity": "woman_at_steering_wheel_pearl_earrings",
        "fact_event": {
            "role": "FACT_B_ACTION",
            "content": "When she got down the ladder, she wears a hard hat and shoots into the sea with a gun.",
            "time": "06:17-06:27",
            "uids": ["1612"],
            "source": "OFFICIAL_QA",
        },
        "fact_identity": {
            "role": "FACT_A_IDENTITY",
            "content": "The woman who sits at the steering wheel wears pearl-style earrings.",
            "time": "06:01-06:13",
            "uids": ["1611"],
            "source": "OFFICIAL_QA",
        },
        "composed_question_sketch": "What does the woman who sits at the steering wheel do after getting down the ladder?",
        "composed_answer_sketch": "Puts on a hard hat and shoots into the sea with a gun",
        "fact_novelty": "LOW",
        "composition_novelty": "HIGH",
        "official_semantic_coverage": "1612 identifies her as 'woman with pearl earrings', not 'steering wheel'; binding via 1611 is required if the composed question uses the steering-wheel cue.",
        "single_clip_shortcut_risk": "MEDIUM_CLOSE_TIMESTAMPS",
        "agent_clarity": "HIGH_IF_SAME_WOMAN",
        "extract": True,
        "status": "PENDING_INDEPENDENT_REVIEW",
        "data_partition_status": "UNASSIGNED",
        "applicable_track": "BOTH_CANDIDATE",
    },
    {
        "candidate_id": "TB-005",
        "video_id": "evYm0cELO3I",
        "video_type": "food_vlog",
        "discovery_mode": "event_first_new_video",
        "composition_signature": "identify_object + query_action",
        "primitive_operations": ["identify_object", "query_action"],
        "bridge_entity": "Lobster",
        "fact_event": {
            "role": "FACT_B_ACTION",
            "content": "From 04:19-04:45 the chef cooks Lobster Quesadilla.",
            "time": "04:19-04:45",
            "uids": ["2763"],
            "source": "OFFICIAL_QA",
        },
        "fact_identity": {
            "role": "FACT_A_IDENTITY",
            "content": "The animal that appears at 00:07 is a lobster.",
            "time": "00:07-00:07",
            "uids": ["2754"],
            "source": "OFFICIAL_QA",
        },
        "composed_question_sketch": "What happens from 04:19-04:45 involving the animal that appears at 00:07?",
        "composed_answer_sketch": "The chef cooks Lobster Quesadilla",
        "fact_novelty": "LOW",
        "composition_novelty": "MEDIUM",
        "official_semantic_coverage": "Both facts official; composition binds early animal ID to later cooking event.",
        "single_clip_shortcut_risk": "MEDIUM_IF_DISH_NAME_VISIBLE",
        "agent_clarity": "HIGH_OBJECT",
        "extract": True,
        "status": "PENDING_INDEPENDENT_REVIEW",
        "data_partition_status": "UNASSIGNED",
        "applicable_track": "BOTH_CANDIDATE",
    },
    {
        "candidate_id": "TB-006",
        "video_id": "LLSJrEgOOtw",
        "video_type": "nature_vlog",
        "discovery_mode": "event_first_new_video",
        "composition_signature": "identify_object + query_action",
        "primitive_operations": ["identify_object", "query_action"],
        "bridge_entity": "dog",
        "fact_event": {
            "role": "FACT_B_ACTION",
            "content": "From 02:03-04:09 the two people pick beech nut and play with the dog.",
            "time": "02:03-04:09",
            "uids": ["3229"],
            "source": "OFFICIAL_QA",
        },
        "fact_identity": {
            "role": "FACT_A_IDENTITY",
            "content": "The animal that appears first playing with wood alone is the dog.",
            "time": "00:25-00:30",
            "uids": ["3224"],
            "source": "OFFICIAL_QA",
        },
        "composed_question_sketch": "What happens from 02:03-04:09 involving the animal that first appears playing with wood alone?",
        "composed_answer_sketch": "People pick beech nuts and play with the dog",
        "fact_novelty": "LOW",
        "composition_novelty": "MEDIUM",
        "official_semantic_coverage": "Official event answer already mentions the dog; composition still requires linking the first-animal identity.",
        "single_clip_shortcut_risk": "MEDIUM",
        "agent_clarity": "HIGH_OBJECT",
        "extract": True,
        "status": "PENDING_INDEPENDENT_REVIEW",
        "data_partition_status": "UNASSIGNED",
        "applicable_track": "B_CANDIDATE",
    },
    {
        "candidate_id": "TB-007",
        "video_id": "Cm73ma6Ibcs",
        "video_type": "drama",
        "discovery_mode": "event_first_new_video",
        "composition_signature": "condition_event + later_action",
        "primitive_operations": ["identify_event_result", "query_action"],
        "bridge_entity": "protagonist",
        "fact_event": {
            "role": "FACT_B_ACTION",
            "content": "When knocked down in the snow, the protagonist wipes her face with snow on the ground.",
            "time": "50:00-50:10",
            "uids": ["75"],
            "source": "OFFICIAL_QA",
        },
        "fact_identity": {
            "role": "FACT_A_CONDITION",
            "content": "After the gunman threatens the cook, the protagonist pushes the table aside and stands up to confront him.",
            "time": "04:19-08:41",
            "uids": ["61"],
            "source": "OFFICIAL_QA",
        },
        "composed_question_sketch": "What does the protagonist who confronts the gunman after the cook is threatened later use to wipe her face when knocked down in the snow?",
        "composed_answer_sketch": "Snow on the ground",
        "fact_novelty": "LOW",
        "composition_novelty": "MEDIUM_HIGH",
        "official_semantic_coverage": "Neither official QA alone asks the cross-interval binding; both facts are official.",
        "single_clip_shortcut_risk": "LOW_MEDIUM",
        "agent_clarity": "HIGH_PROTAGONIST_ROLE",
        "extract": True,
        "status": "PENDING_INDEPENDENT_REVIEW",
        "data_partition_status": "UNASSIGNED",
        "applicable_track": "B_CANDIDATE",
    },
    {
        "candidate_id": "TB-008",
        "video_id": "vaL_vSdZKZo",
        "video_type": "documentary_interview",
        "discovery_mode": "event_first_new_video",
        "composition_signature": "identify_person + query_attribute",
        "primitive_operations": ["identify_person", "query_attribute"],
        "bridge_entity": "man_after_Sergey",
        "fact_event": {
            "role": "FACT_B_ATTRIBUTE",
            "content": "The man interviewed after Sergey Sarancha holds a pair of glasses.",
            "time": "52:31-52:40",
            "uids": ["1630"],
            "source": "OFFICIAL_QA",
        },
        "fact_identity": {
            "role": "FACT_A_CONDITION",
            "content": "Sergey Sarancha clinked glasses with everyone before eating.",
            "time": "51:47-52:18",
            "uids": ["1629"],
            "source": "OFFICIAL_QA",
        },
        "composed_question_sketch": "What does the man interviewed after Sergey Sarancha (who clinked glasses before eating) hold?",
        "composed_answer_sketch": "A pair of glasses",
        "fact_novelty": "LOW",
        "composition_novelty": "LOW",
        "official_semantic_coverage": "1630 already encodes the temporal identify cue; limited composition novelty — kept as borderline contrast item.",
        "single_clip_shortcut_risk": "HIGH",
        "agent_clarity": "MEDIUM",
        "extract": False,
        "status": "BORDERLINE_SKIP_EXTRACT",
        "data_partition_status": "UNASSIGNED",
        "applicable_track": "B_CANDIDATE",
        "fail_reason": "Official question already contains the identify cue; weak composition novelty / high shortcut.",
    },
]

FUNNEL = [
    {"stage": "priority_videos_screened", "n": 12, "note": "_T2Avd3tFHc TJR vaL Cm73 xECI evYm 20lTg uusf O14 pe_Ldd Z4HG hjoD"},
    {"stage": "raw_event_bridge_hits", "n": 33, "note": "Automatic name/bridge scan"},
    {"stage": "rejected_wrong_agent_or_noise", "n": 20, "note": "e.g. villain-car↔prince, With-token noise, self-name leaks"},
    {"stage": "rejected_low_composition_novelty", "n": 5, "note": "Official Q already fully binds entity+answer"},
    {"stage": "vg002_vg003_alt_factB_kept", "n": 3, "note": "TB-001/002/003 replace bell/post-net proposals"},
    {"stage": "promising_pending_review", "n": 7, "note": "TB-001..007; TB-008 borderline not extracted"},
    {"stage": "media_extracted", "n": 7, "note": "Local clips+sheets only for extract=True"},
]


def extract_tb_candidate(cand: dict, media_root: Path) -> dict:
    vid = cand["video_id"]
    source = VIDEO_DIR / f"{vid}.mp4"
    dest = media_root / cand["candidate_id"]
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    has_audio = probe_has_audio(source)
    media = {}
    for key, fact in [("fact_A", cand["fact_identity"]), ("fact_B", cand["fact_event"])]:
        start, end = parse_mmss_range(fact["time"])
        pad = 4.0
        dur = probe_duration(source)
        ws, we = max(0.0, start - pad), min(dur, end + pad)
        clip = dest / f"{key}_clip.mp4"
        sheet = dest / f"{key}_contact_sheet.jpg"
        clip_meta = cut_clip(source, clip, ws, we, has_audio)
        sheet_meta = contact_sheet(clip, sheet, ws)
        media[key] = {
            "requested_time": fact["time"],
            "window": f"{format_ts(ws)}-{format_ts(we)}",
            "clip": str(clip.relative_to(TRACK_B)),
            "contact_sheet": str(sheet.relative_to(TRACK_B)),
            "bytes": clip_meta["bytes"],
        }
    uids = sorted(set(cand["fact_identity"]["uids"]) | set(cand["fact_event"]["uids"]))
    official = load_qa(vid, uids)
    (dest / "official_qa.json").write_text(json.dumps(official, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    notes = {k: cand[k] for k in cand if k != "extract"}
    notes["status_note"] = "PENDING_INDEPENDENT_REVIEW; not SUPPORTED; not formal QA"
    (dest / "candidate_notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return media


def build_track_b() -> dict:
    TRACK_B.mkdir(parents=True, exist_ok=True)
    media_root = TRACK_B / "local_media"
    media_root.mkdir(exist_ok=True)

    write_csv(TRACK_B / "discovery_funnel.csv", FUNNEL)

    extracted = []
    pending = []
    for cand in TRACK_B_CANDIDATES:
        row = dict(cand)
        if cand.get("extract"):
            media = extract_tb_candidate(cand, media_root)
            row["media"] = media
            extracted.append(cand["candidate_id"])
        else:
            row["media"] = None
        pending.append(row)

    with (TRACK_B / "candidates_pending_review.jsonl").open("w", encoding="utf-8") as handle:
        for row in pending:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    manifest = {
        "phase": "track_b_event_first_discovery",
        "role": "TRACK_B + SHARED discovery",
        "auto_supported": False,
        "formal_qa_minted": False,
        "data_partition_status_all": "UNASSIGNED",
        "n_pending_review": sum(1 for c in pending if c["status"] == "PENDING_INDEPENDENT_REVIEW"),
        "extracted_ids": extracted,
        "signatures_probed": sorted({c["composition_signature"] for c in TRACK_B_CANDIDATES}),
        "review_instructions": [
            "Judge Fact A and Fact B visually from clips/sheets.",
            "Confirm same agent/object across intervals.",
            "Score fact_novelty vs composition_novelty using official Q/options/answer.",
            "Flag single-clip shortcuts.",
            "Do not mark SUPPORTED in this pack automatically.",
        ],
    }

    report = f"""# TRACK B CONSTRUCTION REPORT

Event-first discovery round. No formal QA minting. No auto-SUPPORTED. All `UNASSIGNED`.

## Method change

Previous failure mode: start from person-ID QA → hunt an action (led to uncertain agents / non-novel facts).  
This round: **clear observable event → determine subject → other-interval identity/condition clue → composition candidate**.

## VG-002 / VG-003 rework

| Old | Independent status | New alternative |
|---|---|---|
| VG-002 bell ringing | `UNCERTAIN_AGENT` | **TB-001/TB-002** Mikhail → bar / hotel (`identify_person + query_location`) |
| VG-003 post-net action | `NO_CLEAR_NEW_FACT` | **TB-003** embrace-identified Prince → drum performance (`identify_person + query_action`) |

## Screens

- Priority videos screened: **12** (mixed vlog/doc/drama/animation/food/nature)
- Raw automatic bridges: **33**
- Promising pending review kept: **7** extracted (+1 borderline skipped)
- Signatures probed: `identify_person + query_action`, `identify_person + query_location`, `identify_object + query_action`, `condition_event + later_action`, (`identify_person + query_attribute` borderline)

## Promising pending set

`TB-001` … `TB-007` in `candidates_pending_review.jsonl` — for **next independent review**.

## Failure reasons (distribution)

See `discovery_funnel.csv`: wrong-agent/noise, low composition novelty / official already binds, high shortcut, unclear agent.

## Evidence pack

- Path: `local_media/lvbench_track_b_pending_review.zip`
- Contains only filtered promising clips/sheets/QA/notes (not full videos)

## Cost note

Extraction limited to 7 candidates; avoided packing rejected scan hits.

## Status

**Track B discovery: ADVANCED (pending independent review) / NOT a formal benchmark increment.**
"""
    (TRACK_B / "TRACK_B_CONSTRUCTION_REPORT.md").write_text(report, encoding="utf-8")

    zip_path = media_root / "lvbench_track_b_pending_review.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("TRACK_B_CONSTRUCTION_REPORT.md", report)
        zf.writestr("candidates_pending_review.jsonl", (TRACK_B / "candidates_pending_review.jsonl").read_text(encoding="utf-8"))
        zf.writestr("discovery_funnel.csv", (TRACK_B / "discovery_funnel.csv").read_text(encoding="utf-8"))
        zf.writestr("review_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for cid in extracted:
            base = media_root / cid
            for name in [
                "fact_A_clip.mp4",
                "fact_B_clip.mp4",
                "fact_A_contact_sheet.jpg",
                "fact_B_contact_sheet.jpg",
                "official_qa.json",
                "candidate_notes.json",
            ]:
                path = base / name
                if path.is_file():
                    zf.write(path, arcname=f"local_media/{cid}/{name}")

    manifest["zip"] = {
        "path": str(zip_path.relative_to(ROOT)),
        "bytes": zip_path.stat().st_size,
        "extracted_ids": extracted,
    }
    report2 = report.replace(
        "- Path: `local_media/lvbench_track_b_pending_review.zip`\n- Contains only filtered promising clips/sheets/QA/notes (not full videos)",
        f"- Path: `local_media/lvbench_track_b_pending_review.zip`\n- Size bytes: {zip_path.stat().st_size} ({zip_path.stat().st_size/1e6:.1f} MB)\n- Contains only filtered promising clips/sheets/QA/notes (not full videos)",
    )
    (TRACK_B / "TRACK_B_CONSTRUCTION_REPORT.md").write_text(report2, encoding="utf-8")
    (TRACK_B / "review_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    update_shared()
    a = build_track_a()
    b = build_track_b()
    summary = {
        "shared_reviews": len(INDEPENDENT_REVIEWS),
        "track_a_ok_for_rsi": a["ok_for_expensive_rsi"],
        "track_b_extracted": b["extracted_ids"],
        "track_b_pending": b["n_pending_review"],
        "track_b_zip_mb": round(b["zip"]["bytes"] / 1e6, 2),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
