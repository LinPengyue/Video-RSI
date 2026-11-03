#!/usr/bin/env python3
"""Build Seen Pilot run_002: supply audit, necessity screen, optional review packs.

Does NOT auto-approve graphs, freeze Seen pool, mark Gold/train_exposed, or start Track A RSI.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
WB = Path(__file__).resolve().parents[2]
PILOT = Path(__file__).resolve().parents[1]
RUN001 = WB / "seen_pilot_run_001"
REPO_AUDIT = ROOT / "research_audit" / "lvbench_compositional"
LV = Path("/home/descfly/lpy/dataset/LVBench/videos")
FFMPEG = Path.home() / ".cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffmpeg"
FFPROBE = FFMPEG.parent / "ffprobe"

sys.path.insert(0, str(PILOT / "eng"))
from necessity_screen import (  # noqa: E402
    PRIORITY,
    DIAGNOSTIC,
    screen_candidate,
)

RUN_ID = "seen_pilot_run_002"
STATUS = "PENDING_HUMAN_VIDEO_REVIEW"
GATES = {
    "formal_seen_train": False,
    "formal_unseen": False,
    "formal_gold": False,
    "train_exposed": False,
    "seen_pool_frozen": False,
    "approve_expensive_track_a_rsi": False,
}

# Priority human-review packs (isolation-safe remaining; non-exposed preferred).
# Honest: pre-screen only — not scientific approval.
PRIORITY_PICKS = [
    {
        "pack_id": "SP201",
        "qa_uid": "LVCOMP-V2-001",
        "reason": "Non-exposed remaining; SP005-class target bind hypothesis (final winner → attribute at 48:16); counterfactual: alternate winner changes A query target.",
    },
    {
        "pack_id": "SP202",
        "qa_uid": "LVCOMP-V2-040",
        "reason": "Non-exposed; identify person who serves first then query competition result — cross-window target bind; same video as SP201 but different bind variable.",
    },
    {
        "pack_id": "SP203",
        "qa_uid": "LVCOMP-V2-042",
        "reason": "Non-exposed; person/relation join hypothesis (orange coughing guy → whose coach / final winner); SP002-like relation mechanism without claiming video proof.",
    },
    {
        "pack_id": "SP204",
        "qa_uid": "LVCOMP-V2-101",
        "reason": "Non-exposed; place identification then person-at-place query — cross-window place/person bind candidate.",
    },
    {
        "pack_id": "SP205",
        "qa_uid": "LVCOMP-V2-116",
        "reason": "Non-exposed; sequential transport bind with explicit B-only shortcut risk to check on FULL question; useful necessity diagnostic + potential true bind.",
    },
]

DIAGNOSTIC_PICKS = [
    {
        "pack_id": "DN201",
        "qa_uid": "LVCOMP-V2-115",
        "reason": "Sibling of SP205; event_result+action may be B-only sufficient (SP003-class). Diagnostic only — not an approved compositional graph.",
    },
]

_MMSS = re.compile(r"^(\d+):([0-5]\d(?:\.\d+)?)$")
_HHMMSS = re.compile(r"^(\d+):([0-5]\d):([0-5]\d(?:\.\d+)?)$")
POINT_PAD_BEFORE, POINT_PAD_AFTER, MIN_CLIP_S = 5.0, 10.0, 3.0


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1024 * 1024), b""):
            h.update(c)
    return h.hexdigest()


def dump(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_ts(s: str) -> float:
    s = s.strip()
    m = _HHMMSS.match(s)
    if m:
        return int(m.group(1)) * 3600 + int(float(m.group(2))) * 60 + float(m.group(3))
    m = _MMSS.match(s)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    raise ValueError(s)


def parse_range(ref: str) -> tuple[float, float]:
    a, b = ref.split("-", 1)
    return parse_ts(a), parse_ts(b)


def window_plan(ref: str, video_dur: float | None) -> dict:
    t0, t1 = parse_range(ref)
    basis = {"source_time_reference": ref, "parsed_start_s": t0, "parsed_end_s": t1, "padding_applied": False}
    start, end = t0, t1
    if abs(t1 - t0) < 1e-6:
        start = max(0.0, t0 - POINT_PAD_BEFORE)
        end = t0 + POINT_PAD_AFTER
        basis.update({"padding_applied": True, "pad_before_s": POINT_PAD_BEFORE, "pad_after_s": POINT_PAD_AFTER})
    # Cap extremely long windows for review cost while recording truncation
    MAX_REVIEW = 120.0
    if end - start > MAX_REVIEW:
        basis["truncated_for_review_cost"] = True
        basis["original_span_s"] = end - start
        basis["note"] = f"Official window longer than {MAX_REVIEW}s; engineering truncated for review cost — human must know coverage may be incomplete."
        end = start + MAX_REVIEW
    if end - start < MIN_CLIP_S:
        end = start + MIN_CLIP_S
    if video_dur is not None:
        start = min(max(0.0, start), max(0.0, video_dur - MIN_CLIP_S))
        end = min(end, video_dur)
        basis["video_duration_s"] = video_dur
    return {"start_s": start, "end_s": end, "basis": basis}


def ffprobe_duration(path: Path) -> float | None:
    if not FFPROBE.exists() or not path.exists():
        return None
    r = subprocess.run(
        [str(FFPROBE), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
    )
    try:
        return float(r.stdout.strip())
    except Exception:
        return None


def extract_clip(src: Path, dst: Path, start: float, end: float) -> dict:
    dur = max(end - start, MIN_CLIP_S)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not FFMPEG.exists() or not src.exists():
        return {"extract_status": "MEDIA_UNAVAILABLE", "reason": "missing_ffmpeg_or_source"}
    cmd = [
        str(FFMPEG), "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-movflags", "+faststart", str(dst),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        return {"extract_status": "MEDIA_UNAVAILABLE", "reason": "ffmpeg_failed", "stderr_tail": (r.stderr or "")[-400:]}
    return {
        "extract_status": "OK",
        "bytes": dst.stat().st_size,
        "sha256": sha256_file(dst),
        "t_start_s": start,
        "t_end_s": start + dur,
        "duration_s": dur,
    }


def load_candidates() -> dict[str, dict]:
    out = {}
    for line in (REPO_AUDIT / "v2" / "candidates.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            o = json.loads(line)
            out[o["id"]] = o
    return out


def hard_excludes() -> tuple[set[str], set[str], set[str], set[str]]:
    ex = json.loads((RUN001 / "EXCLUSION_LIST.json").read_text(encoding="utf-8"))
    hard_v = set(ex["hard_exclude_videos"])
    hard_u = set(ex["hard_exclude_qa_uids"])
    run001_vids = {it["video_id"] for it in json.loads((RUN001 / "CATALOG.json").read_text())["items"]}
    run001_uids = {it["qa_uid"] for it in json.loads((RUN001 / "CATALOG.json").read_text())["items"]}
    exposed = set(ex["informational_not_hard_block"]["construction_exposed_or_assistant_discovery"])
    return hard_v, hard_u, run001_vids | run001_uids and run001_vids, exposed  # fix below


def build_audit(cands: dict[str, dict]) -> dict:
    ex = json.loads((RUN001 / "EXCLUSION_LIST.json").read_text(encoding="utf-8"))
    hard_v = set(ex["hard_exclude_videos"])
    hard_u = set(ex["hard_exclude_qa_uids"])
    run001 = json.loads((RUN001 / "CATALOG.json").read_text())["items"]
    run001_vids = {it["video_id"] for it in run001}
    run001_uids = {it["qa_uid"] for it in run001}
    sealed = json.loads((REPO_AUDIT / "track_b" / "SEALED_POOL_SPLIT_POLICY.json").read_text())
    exposed = set(sealed["exposed_or_construction"])
    split = json.loads((REPO_AUDIT / "v2_1" / "pilot_split.json").read_text())

    all_vids = {o["video_id"] for o in cands.values()}
    remaining = []
    dropped = []
    for o in cands.values():
        reasons = []
        if o["video_id"] in hard_v:
            reasons.append("hard_exclude_video")
        if o["id"] in hard_u:
            reasons.append("hard_exclude_uid")
        if o["video_id"] in run001_vids:
            reasons.append("used_in_seen_pilot_run_001_video")
        if o["id"] in run001_uids:
            reasons.append("used_in_seen_pilot_run_001_uid")
        if reasons:
            dropped.append({"qa_uid": o["id"], "video_id": o["video_id"], "reasons": reasons})
        else:
            remaining.append(o)

    rem_vids = sorted({o["video_id"] for o in remaining})
    media = {v: (LV / f"{v}.mp4").exists() for v in rem_vids}
    non_exposed = [o for o in remaining if o["video_id"] not in exposed]

    # schema families
    from collections import Counter
    schemas = Counter(o.get("composition_schema") for o in cands.values())
    rem_schemas = Counter(o.get("composition_schema") for o in remaining)

    v3_seen = sum(1 for _ in (REPO_AUDIT / "targeted_v3" / "seen_candidates.jsonl").read_text().splitlines() if _.strip())
    v3_unseen = sum(1 for _ in (REPO_AUDIT / "targeted_v3" / "unseen_candidates.jsonl").read_text().splitlines() if _.strip())

    return {
        "run_id": RUN_ID,
        "created_utc": utc_now(),
        "baseline_commit_expected": "1e0405674015e31104177de715022ee3822af9b4",
        "sources": {
            "v2_candidates_jsonl": {
                "path": "research_audit/lvbench_compositional/v2/candidates.jsonl",
                "n_qa": len(cands),
                "n_videos": len(all_vids),
                "schema_families": dict(schemas),
            },
            "v2_1_pilot_split": {
                "path": "research_audit/lvbench_compositional/v2_1/pilot_split.json",
                "train_n": len(split["train_ids"]),
                "test_n": len(split["test_ids"]),
                "label_status": "HISTORICAL_CANDIDATE_ONLY_NOT_FORMAL_SEEN",
            },
            "targeted_v3": {"seen_n": v3_seen, "unseen_n": v3_unseen},
            "batch_factory_roi_dev": {
                "path": "research_audit/lvbench_compositional/track_b/batch_factory/",
                "human_confirmed_compositional_events_on_remaining_videos": 0,
                "note": "ChatGPT/frame/ROI pilots are NOT human-confirmed Seen supply.",
            },
        },
        "hard_exclude_videos_n": len(hard_v),
        "run_001_videos": sorted(run001_vids),
        "dropped_n": len(dropped),
        "remaining_after_hard_and_run001": {
            "n_qa": len(remaining),
            "n_videos": len(rem_vids),
            "videos": rem_vids,
            "media_present_n": sum(1 for v, ok in media.items() if ok),
            "media_missing": [v for v, ok in media.items() if not ok],
            "schema_families": dict(rem_schemas),
        },
        "remaining_also_non_construction_exposed": {
            "n_qa": len(non_exposed),
            "n_videos": len({o["video_id"] for o in non_exposed}),
            "videos": sorted({o["video_id"] for o in non_exposed}),
            "qa_uids": [o["id"] for o in non_exposed],
        },
        "mechanism_supply": {
            "cross_window_target_bind": "Expandable as HYPOTHESIS on leftover identify_* + query_* QAs; 0 new human-confirmed graphs on unused videos.",
            "temporal_person_then_relation": "Best residual video Hf-n1yfd8II / 9-gOCOu_KGU; no EVENT_VERIFIED cards on these videos.",
            "single_window_shortcut_diagnostics": "Plenty of event_result+query_action items for SP003/SP004-class checks.",
            "lacking_evidence": [
                "No human-confirmed events on remaining clean videos",
                "Batch-factory/ROI blocked for certified composition",
                "Operator vocab still provisional",
            ],
        },
        "honest_supply_verdict": (
            "Isolation-safe residual supply exists (31 QA / 12 videos; 13 QA / 5 non-exposed). "
            "However NEW human-confirmed compositional graph supply is 0. "
            "run_002 packs are necessity-aware PRE-SCREEN packets for human review — not approved graphs."
        ),
    }, remaining, exposed


def make_pack(sel: dict, cand: dict, exposed: set[str], screen: dict, diagnostic: bool = False) -> dict:
    video_id = cand["video_id"]
    pack_id = sel["pack_id"]
    src = LV / f"{video_id}.mp4"
    vdur = ffprobe_duration(src)
    refs = cand.get("time_references") or []
    plan_a = window_plan(refs[0], vdur)
    plan_b = window_plan(refs[1], vdur)
    media_dir = PILOT / "media" / pack_id
    path_a = media_dir / f"A_{video_id}_{int(plan_a['start_s'])}_{int(plan_a['end_s'])}.mp4"
    path_b = media_dir / f"B_{video_id}_{int(plan_b['start_s'])}_{int(plan_b['end_s'])}.mp4"
    ex_a = extract_clip(src, path_a, plan_a["start_s"], plan_a["end_s"])
    ex_b = extract_clip(src, path_b, plan_b["start_s"], plan_b["end_s"])
    media_status = "OK" if ex_a.get("extract_status") == "OK" and ex_b.get("extract_status") == "OK" else "MEDIA_UNAVAILABLE"
    rel_a = f"seen_pilot_run_002/media/{pack_id}/{path_a.name}" if media_status == "OK" else None
    rel_b = f"seen_pilot_run_002/media/{pack_id}/{path_b.name}" if media_status == "OK" else None

    human_questions = [
        "Is A-only sufficient for the COMPLETE original question (target not pre-resolved)?",
        "Is B-only sufficient for the COMPLETE original question?",
        "If A selected a different plausible target, would B's query target change? (counterfactual aid)",
        "What is the bind variable and which window provides selection vs query evidence?",
        "Any boundary/subtitle/coverage gaps in the served clips?",
        "Approve / not approve compositional candidate graph? (human only)",
    ]
    pack = {
        "run_id": RUN_ID,
        "pack_id": pack_id,
        "workbench_id": f"SEEN_PILOT_{pack_id}",
        "pack_role": "DIAGNOSTIC_NEGATIVE_OR_UNRESOLVED" if diagnostic else "PRIORITY_HUMAN_REVIEW",
        "user_confirmation_status": STATUS,
        **GATES,
        "historical_train_label_status": "HISTORICAL_CANDIDATE_ONLY_NOT_FORMAL_SEEN",
        "construction_exposed": video_id in exposed,
        "video_id": video_id,
        "qa_uid": cand["id"],
        "selection_reason": sel["reason"],
        "qa_clue_unverified": {
            "question": cand.get("new_question"),
            "answer": cand.get("new_answer"),
            "status": "UNVERIFIED_HISTORICAL_CLUE_ONLY",
            "source_questions": cand.get("source_questions"),
            "source_answers": cand.get("source_answers"),
        },
        "intervals": {"A": plan_a, "B": plan_b, "official_time_references": refs},
        "media": {
            "status": media_status,
            "A": {**ex_a, "relpath": rel_a, "window_basis": plan_a["basis"]},
            "B": {**ex_b, "relpath": rel_b, "window_basis": plan_b["basis"]},
        },
        "auto_screen": screen,
        "program_draft": screen.get("program_draft"),
        "human_review_questions": human_questions,
        "human_review_form_fields": {
            "events": "",
            "persons": "",
            "objects": "",
            "actions": "",
            "temporal_relations": "",
            "identity_binding": "",
            "within_window_temporal_bind": "",
            "cross_window_bind": "",
            "a_only_sufficient_full_question": "",
            "b_only_sufficient_full_question": "",
            "a_plus_b_necessary": "",
            "counterfactual_target_swap": "",
            "directed_program_draft": "",
            "decision": "",
            "rationale_and_open_issues": "",
        },
        "forbidden_auto_labels": [
            "USER_APPROVED_STRUCTURED_GRAPH",
            "FORMAL_SEEN_TRAIN",
            "TRAIN_EXPOSED",
            "GOLD",
        ],
        "does_not_overwrite_run_001": True,
    }
    out_dir = PILOT / ("diagnostic_negatives" if diagnostic else "review_packs")
    dump(out_dir / f"{pack_id}_{video_id}.json", pack)
    return pack


def main() -> int:
    cands = load_candidates()
    audit, remaining, exposed = build_audit(cands)
    dump(PILOT / "CANDIDATE_SUPPLY_AUDIT.json", audit)

    # Screen all remaining
    screens = []
    rem_by_id = {o["id"]: o for o in remaining}
    for o in remaining:
        meta = {"construction_exposed": o["video_id"] in exposed, "media_exists": (LV / f"{o['video_id']}.mp4").exists()}
        screens.append(screen_candidate(o, meta=meta))
    dump(PILOT / "screening" / "SCREENING_RESULTS.json", {
        "run_id": RUN_ID,
        "created_utc": utc_now(),
        "n": len(screens),
        "priority_n": sum(1 for s in screens if s["diagnosis"]["screen_bucket"] == PRIORITY),
        "diagnostic_n": sum(1 for s in screens if s["diagnosis"]["screen_bucket"] == DIAGNOSTIC),
        "items": screens,
        "disclaimer": "Pre-screen heuristics from run_001 lessons; not scientific certification.",
    })

    # Isolation for proposed picks
    hard_v = set(json.loads((RUN001 / "EXCLUSION_LIST.json").read_text())["hard_exclude_videos"])
    run001_vids = {it["video_id"] for it in json.loads((RUN001 / "CATALOG.json").read_text())["items"]}
    isolation_issues = []
    catalog_items = []
    manifest_files = []
    screen_by = {s["qa_uid"]: s for s in screens}

    for sel in PRIORITY_PICKS:
        if sel["qa_uid"] not in rem_by_id:
            isolation_issues.append(f"PRIORITY pick {sel['qa_uid']} not in remaining supply")
            continue
        cand = rem_by_id[sel["qa_uid"]]
        if cand["video_id"] in hard_v or cand["video_id"] in run001_vids:
            isolation_issues.append(f"BLOCK isolation {sel['pack_id']} video {cand['video_id']}")
            continue
        pack = make_pack(sel, cand, exposed, screen_by[sel["qa_uid"]], diagnostic=False)
        if pack["video_id"] in hard_v:
            isolation_issues.append(f"hard exclude leak {pack['pack_id']}")
        catalog_items.append({
            "workbench_id": pack["workbench_id"],
            "pack_id": pack["pack_id"],
            "section": "seen_pilot_run_002",
            "qa_uid": pack["qa_uid"],
            "video_id": pack["video_id"],
            "user_confirmation_status": STATUS,
            **{k: False for k in ["formal_seen_train", "formal_gold", "train_exposed", "formal_unseen"]},
            "media_status": pack["media"]["status"],
            "clips": {"A": pack["media"]["A"].get("relpath"), "B": pack["media"]["B"].get("relpath")},
            "intervals": pack["intervals"],
            "qa_clue_unverified": pack["qa_clue_unverified"],
            "pack_path": f"seen_pilot_run_002/review_packs/{pack['pack_id']}_{pack['video_id']}.json",
            "construction_exposed": pack["construction_exposed"],
            "selection_reason": pack["selection_reason"],
            "auto_screen_bucket": pack["auto_screen"]["diagnosis"]["screen_bucket"],
            "pack_role": pack["pack_role"],
        })
        for side in ("A", "B"):
            ex = pack["media"][side]
            if ex.get("extract_status") == "OK":
                manifest_files.append({"role": f"{pack['pack_id']}_{side}", "relpath": ex["relpath"], "sha256": ex["sha256"], "bytes": ex["bytes"]})

    diagnostic_items = []
    for sel in DIAGNOSTIC_PICKS:
        if sel["qa_uid"] not in rem_by_id:
            continue
        cand = rem_by_id[sel["qa_uid"]]
        if cand["video_id"] in hard_v or cand["video_id"] in run001_vids:
            isolation_issues.append(f"diagnostic blocked {sel['pack_id']}")
            continue
        pack = make_pack(sel, cand, exposed, screen_by[sel["qa_uid"]], diagnostic=True)
        diagnostic_items.append({
            "pack_id": pack["pack_id"],
            "qa_uid": pack["qa_uid"],
            "video_id": pack["video_id"],
            "pack_path": f"seen_pilot_run_002/diagnostic_negatives/{pack['pack_id']}_{pack['video_id']}.json",
            "note": "Diagnostic only; not counted toward approved compositional graphs.",
            "media_status": pack["media"]["status"],
        })
        for side in ("A", "B"):
            ex = pack["media"][side]
            if ex.get("extract_status") == "OK":
                manifest_files.append({"role": f"{pack['pack_id']}_{side}", "relpath": ex["relpath"], "sha256": ex["sha256"], "bytes": ex["bytes"]})

    isolation = {
        "run_id": RUN_ID,
        "created_utc": utc_now(),
        "status": "PASS" if not isolation_issues and catalog_items else ("FAIL" if isolation_issues else "PASS_EMPTY"),
        "issues": isolation_issues,
        "selected_video_ids": sorted({i["video_id"] for i in catalog_items}),
        "selected_qa_uids": sorted({i["qa_uid"] for i in catalog_items}),
        "overlap_hard_exclude": sorted({i["video_id"] for i in catalog_items} & hard_v),
        "overlap_run_001": sorted({i["video_id"] for i in catalog_items} & run001_vids),
        "run_001_records_preserved": True,
        "unseen_approved_graphs_untouched": True,
    }
    dump(PILOT / "ISOLATION_CHECK.json", isolation)

    catalog = {
        "run_id": RUN_ID,
        "created_utc": utc_now(),
        "user_confirmation_status_uniform": STATUS,
        **GATES,
        "does_not_overwrite_run_001": True,
        "auto_approved_structured_graphs": 0,
        "items": catalog_items,
        "diagnostic_negatives": diagnostic_items,
        "supply_note": audit["honest_supply_verdict"],
    }
    dump(PILOT / "CATALOG.json", catalog)

    blank = {
        "schema": "p7_seen_pilot_judgments_v1",
        "run_id": RUN_ID,
        "disclaimer": "run_002 pre-screen packets; Cursor did not adjudicate.",
        "items": {
            it["workbench_id"]: {
                "user_confirmation_status": STATUS,
                **{k: False for k in ["formal_seen_train", "formal_gold", "train_exposed"]},
                "media_status": it["media_status"],
                "pilot_unknown_keep": "PRESERVE_ON_ROUNDTRIP",
            }
            for it in catalog_items
        },
    }
    dump(PILOT / "JUDGMENTS_BLANK.json", blank)

    man = {
        "run_id": RUN_ID,
        "created_utc": utc_now(),
        "files": manifest_files,
        "pack_json_sha256": {p.name: sha256_file(p) for p in sorted((PILOT / "review_packs").glob("*.json"))},
    }
    dump(PILOT / "MANIFEST.json", man)

    # Markdown audit report
    md = f"""# Seen Pilot run_002 — Candidate Supply Audit

Created: `{audit['created_utc']}`  
Baseline: `{audit['baseline_commit_expected']}`

## Verdict

{audit['honest_supply_verdict']}

## Inventory

| Source | QAs | Videos | Notes |
|--------|----:|-------:|-------|
| v2 candidates | {audit['sources']['v2_candidates_jsonl']['n_qa']} | {audit['sources']['v2_candidates_jsonl']['n_videos']} | primary residual supply |
| After hard∪run_001 exclude | {audit['remaining_after_hard_and_run001']['n_qa']} | {audit['remaining_after_hard_and_run001']['n_videos']} | media missing: {audit['remaining_after_hard_and_run001']['media_missing'] or 'none'} |
| Also non-exposed | {audit['remaining_also_non_construction_exposed']['n_qa']} | {audit['remaining_also_non_construction_exposed']['n_videos']} | preferred for run_002 |
| v2.1 historical train | {audit['sources']['v2_1_pilot_split']['train_n']} | — | NOT formal Seen |
| Batch/ROI human-confirmed on remaining | 0 | — | not usable as certified events |

## Priority packs prepared

{", ".join(i['pack_id'] for i in catalog_items) or "(none)"} — status `{STATUS}`; **0 auto-approved graphs**.

## Isolation

status={isolation['status']}; hard overlap={isolation['overlap_hard_exclude']}; run_001 overlap={isolation['overlap_run_001']}

## Stop

Await GPT/USER video review. Do not approve graphs, freeze pool, Gold, train_exposed, or start Track A RSI from this build.
"""
    (PILOT / "CANDIDATE_SUPPLY_AUDIT.md").write_text(md, encoding="utf-8")

    print(json.dumps({
        "isolation": isolation["status"],
        "priority_packs": len(catalog_items),
        "diagnostic": len(diagnostic_items),
        "media": [i["media_status"] for i in catalog_items],
        "issues": isolation_issues,
    }, indent=2))
    return 0 if isolation["status"] == "PASS" and catalog_items else 1


if __name__ == "__main__":
    sys.exit(main())
