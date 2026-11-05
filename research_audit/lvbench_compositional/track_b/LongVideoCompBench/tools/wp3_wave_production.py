#!/usr/bin/env python3
"""WP3 Wave production: bounded video discovery → evidence packs → review packets.

Does NOT mint SUPPORTED / FACT_VERIFIED / FORMAL_GOLD.
Does NOT unlock run_004.
Does NOT rewrite official LVBench QA into Gold.
Semantics remain UNRESOLVED until Human/GPT review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import struct
import subprocess
import sys
import zlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, DS_ROOT, utc_now, write_json, write_jsonl, sha256_file  # noqa: E402

FFMPEG = Path("/home/descfly/.cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffmpeg")
FFPROBE = Path("/home/descfly/.cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffprobe")
VIDEO_ROOT = Path("/home/descfly/lpy/dataset/LVBench/videos")
META_PATH = Path("/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl")
POOL_PATH = (
    REPO_ROOT / "research_audit/lvbench_compositional/track_b/construction_video_pool.jsonl"
)
POLICY_PATH = (
    REPO_ROOT / "research_audit/lvbench_compositional/track_b/SEALED_POOL_SPLIT_POLICY.json"
)
WP3_ROOT = DS_ROOT / "wp3_production"
LOCAL_MEDIA = (
    REPO_ROOT
    / "research_audit/lvbench_compositional/track_b/local_media/wp3_production"
)
BASELINE_COMMIT = "7950ab00ca40305e2dd6b16f10e20888ded06db7"

# Wave registries: genre labels are DEV heuristics from meta text, not sealed taxonomy.
WAVE1 = [
    {"video_id": "USfvmoalqsw", "genre_guess": "vlog", "reason": "travel vlog; many temporally separated clusters"},
    {"video_id": "16Z-XQh9jhk", "genre_guess": "sports", "reason": "sports broadcast; multi-event timeline"},
    {"video_id": "CgvJqGxzRfE", "genre_guess": "documentary", "reason": "documentary-style; long gaps between clusters"},
    {"video_id": "KktLi3UifPY", "genre_guess": "interview", "reason": "interview/talk content; multi-segment"},
    {"video_id": "gXnhqF0TqqI", "genre_guess": "animation", "reason": "animation cues in meta; unused DEV construction"},
]
WAVE2 = [
    {"video_id": "xECIRjlxM3U", "genre_guess": "drama", "reason": "long drama; densest temporal clusters among unused"},
    {"video_id": "Aiem1w_TvaA", "genre_guess": "sports", "reason": "sports; large inter-cluster gaps"},
    {"video_id": "ihfjEFGdZdc", "genre_guess": "interview", "reason": "interview segments; distinct from Wave1 interview"},
    {"video_id": "wgBlACG927Y", "genre_guess": "vlog", "reason": "travel/transit vlog; complementary to Wave1 vlog"},
    {"video_id": "W-BnDvXXfOs", "genre_guess": "drama", "reason": "drama; independent of Wave2 long-form drama"},
]

FRAMES_PER_ROI = 12  # within 8–16
ROI_WINDOW_S = 10.0
REVIEW_FRAMES_PER_ROI = 4  # committed subset
MAX_PAIRS_PER_VIDEO = 2
MIN_PAIR_GAP_S = 180.0
COARSE_STEP_S = 15.0


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def ffprobe_duration(path: Path) -> float | None:
    r = run_cmd(
        [
            str(FFPROBE),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ]
    )
    try:
        return float(r.stdout.decode().strip())
    except Exception:
        return None


def partial_sha256(path: Path, limit_mb: float = 32.0) -> str:
    h = hashlib.sha256()
    size = path.stat().st_size
    h.update(f"size:{size}|".encode())
    remain = int(limit_mb * 1024 * 1024)
    with path.open("rb") as f:
        while remain > 0:
            chunk = f.read(min(1024 * 1024, remain))
            if not chunk:
                break
            h.update(chunk)
            remain -= len(chunk)
    return h.hexdigest()


def load_exposed() -> set[str]:
    exposed: set[str] = set()
    policy = json.loads(POLICY_PATH.read_text())
    exposed.update(policy.get("exposed_or_construction") or [])
    if POOL_PATH.exists():
        for line in POOL_PATH.read_text().splitlines():
            if line.strip():
                exposed.add(json.loads(line)["construction_video_id"])
    return exposed


def extract_gray_hist(video: Path, t: float, tmp: Path) -> list[int] | None:
    """Extract tiny grayscale frame and return 16-bin histogram (engineering signal only)."""
    tmp.parent.mkdir(parents=True, exist_ok=True)
    if tmp.exists():
        tmp.unlink()
    r = run_cmd(
        [
            str(FFMPEG),
            "-y",
            "-ss",
            f"{t:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            "scale=64:36,format=gray",
            "-f",
            "rawvideo",
            str(tmp),
        ]
    )
    if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        return None
    data = tmp.read_bytes()
    bins = [0] * 16
    for b in data:
        bins[b >> 4] += 1
    tmp.unlink(missing_ok=True)
    return bins


def hist_l1(a: list[int], b: list[int]) -> float:
    return float(sum(abs(x - y) for x, y in zip(a, b))) / max(1, sum(a))


@dataclass
class RoiSpec:
    roi_id: str
    video_id: str
    t_start: float
    t_end: float
    center_s: float
    discovery_score: float
    pair_id: str
    role: str  # early|late


def discover_pairs(video_id: str, media: Path, duration: float, work: Path) -> list[tuple[RoiSpec, RoiSpec]]:
    """Bounded scene-change discovery → up to 2 temporally separated ROI pairs.

    Scores are ENGINEERING_ONLY (histogram change). Not semantic certification.
    """
    times: list[float] = []
    t = 5.0
    while t < duration - 5.0:
        times.append(t)
        t += COARSE_STEP_S
    # Cap coarse samples to keep runtime bounded (~8–12 min video → ~40–50 samples;
    # long videos subsample).
    if len(times) > 80:
        step = len(times) / 80.0
        times = [times[int(i * step)] for i in range(80)]

    tmp = work / "_hist_tmp.raw"
    scores: list[tuple[float, float]] = []  # (t, change)
    prev = None
    for tt in times:
        h = extract_gray_hist(media, tt, tmp)
        if h is None:
            continue
        if prev is not None:
            scores.append((tt, hist_l1(prev, h)))
        prev = h

    if len(scores) < 4:
        # fallback: quartile centers
        qs = [0.2, 0.35, 0.55, 0.75]
        centers = [max(5.0, min(duration - 5.0, duration * q)) for q in qs]
        pairs = []
        for i in range(0, 4, 2):
            a, b = centers[i], centers[i + 1]
            if b - a < MIN_PAIR_GAP_S:
                continue
            pairs.append(_make_pair(video_id, a, b, score=0.0, pair_idx=len(pairs)))
        return pairs[:MAX_PAIRS_PER_VIDEO]

    scores_sorted = sorted(scores, key=lambda x: -x[1])
    peaks: list[float] = []
    for t_peak, sc in scores_sorted:
        if any(abs(t_peak - p) < 60.0 for p in peaks):
            continue
        peaks.append(t_peak)
        if len(peaks) >= 8:
            break
    peaks = sorted(peaks)

    # Greedy pairs with max temporal separation and high combined change.
    peak_score = {t: s for t, s in scores}
    candidates: list[tuple[float, float, float]] = []
    for i, a in enumerate(peaks):
        for b in peaks[i + 1 :]:
            gap = b - a
            if gap < MIN_PAIR_GAP_S:
                continue
            comb = peak_score.get(a, 0) + peak_score.get(b, 0) + min(gap, 1200) / 1200.0
            candidates.append((comb, a, b))
    candidates.sort(reverse=True)
    pairs: list[tuple[RoiSpec, RoiSpec]] = []
    used: list[float] = []
    for comb, a, b in candidates:
        if any(abs(a - u) < 90 or abs(b - u) < 90 for u in used):
            continue
        pairs.append(_make_pair(video_id, a, b, score=comb, pair_idx=len(pairs)))
        used.extend([a, b])
        if len(pairs) >= MAX_PAIRS_PER_VIDEO:
            break
    return pairs


def _make_pair(
    video_id: str, a: float, b: float, *, score: float, pair_idx: int
) -> tuple[RoiSpec, RoiSpec]:
    pair_id = f"{video_id}_PAIR{pair_idx+1}"
    half = ROI_WINDOW_S / 2.0

    def roi(center: float, role: str) -> RoiSpec:
        # Name directories by true [t_start, t_end], not center/(center+window).
        t0 = round(max(0.0, center - half), 3)
        t1 = round(t0 + ROI_WINDOW_S, 3)
        return RoiSpec(
            roi_id=f"{pair_id}_{role.upper()}_{int(t0)}_{int(t1)}",
            video_id=video_id,
            t_start=t0,
            t_end=t1,
            center_s=round(center, 3),
            discovery_score=round(score, 6),
            pair_id=pair_id,
            role=role,
        )

    return roi(a, "early"), roi(b, "late")


def extract_roi_frames(
    media: Path,
    roi: RoiSpec,
    out_dir: Path,
    n_frames: int,
) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    if n_frames <= 1:
        ts = [roi.t_start]
    else:
        ts = [
            roi.t_start + i * (roi.t_end - roi.t_start) / (n_frames - 1)
            for i in range(n_frames)
        ]
    for i, t in enumerate(ts):
        name = f"mf_{i:02d}_t{t:.1f}.jpg"
        path = out_dir / name
        if not (path.exists() and path.stat().st_size > 500):
            r = run_cmd(
                [
                    str(FFMPEG),
                    "-y",
                    "-ss",
                    f"{t:.3f}",
                    "-i",
                    str(media),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "3",
                    str(path),
                ]
            )
            if r.returncode != 0 or not path.exists():
                continue
        rows.append(
            {
                "frame_index": i,
                "t_seconds": round(t, 3),
                "path": str(path.relative_to(REPO_ROOT))
                if path.is_relative_to(REPO_ROOT)
                else str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return rows


def copy_review_subset(
    frames: list[dict[str, Any]], dest_dir: Path, k: int
) -> list[dict[str, Any]]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not frames:
        return []
    idxs = sorted({0, len(frames) // 3, (2 * len(frames)) // 3, len(frames) - 1})[:k]
    out = []
    for i in idxs:
        src = REPO_ROOT / frames[i]["path"]
        if not src.exists():
            src = Path(frames[i]["path"])
        dst = dest_dir / Path(frames[i]["path"]).name
        if src.exists():
            shutil.copy2(src, dst)
            out.append(
                {
                    **frames[i],
                    "path": str(dst.relative_to(REPO_ROOT)),
                    "sha256": sha256_file(dst),
                    "bytes": dst.stat().st_size,
                    "review_subset": True,
                }
            )
    return out


def maybe_extract_clip(media: Path, roi: RoiSpec, out_mp4: Path) -> dict[str, Any] | None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    if not (out_mp4.exists() and out_mp4.stat().st_size > 1000):
        r = run_cmd(
            [
                str(FFMPEG),
                "-y",
                "-ss",
                f"{roi.t_start:.3f}",
                "-i",
                str(media),
                "-t",
                f"{ROI_WINDOW_S:.3f}",
                "-c",
                "copy",
                str(out_mp4),
            ]
        )
        if r.returncode != 0 or not out_mp4.exists():
            return None
    return {
        "path": str(out_mp4.relative_to(REPO_ROOT))
        if out_mp4.is_relative_to(REPO_ROOT)
        else str(out_mp4),
        "t_start": roi.t_start,
        "t_end": roi.t_end,
        "sha256": sha256_file(out_mp4),
        "bytes": out_mp4.stat().st_size,
        "gitignored_local_media": True,
    }


def build_relation_hypothesis(pair_id: str, early: dict, late: dict) -> dict[str, Any]:
    return {
        "relation_id": f"rel:{pair_id}",
        "pair_id": pair_id,
        "video_id": early["video_id"],
        "windows_seconds": [
            [early["t_start"], early["t_end"]],
            [late["t_start"], late["t_end"]],
        ],
        "roi_ids": [early["roi_id"], late["roi_id"]],
        "hypothesis_family_candidates": [
            "CrossIntervalSamePersonBind",
            "CrossViewSameObjectBind",
            "CrossViewSameRoomBind",
            "ConditionThenLaterOutcome",
            "ObjectStateChange",
            "ReverseTemporalQuery",
            "AudioVisualBind",
        ],
        "selected_operator": "UNKNOWN_PENDING_SEMANTIC_REVIEW",
        "event_certification": "UNRESOLVED",
        "fact_status": "UNRESOLVED",
        "relation_status": "HYPOTHESIS_ONLY",
        "notes": (
            "Engineering-selected temporally separated ROI pair. "
            "No semantic event has been certified. Not SUPPORTED."
        ),
    }


def build_qa_stub(rel: dict[str, Any], genre: str) -> dict[str, Any]:
    sid = rel["pair_id"].replace("_", "")
    return {
        "qa_id": f"wp3:qa:{rel['pair_id']}",
        "source_item_id": rel["pair_id"],
        "video_id": rel["video_id"],
        "question": None,
        "answer": None,
        "windows_seconds": rel["windows_seconds"],
        "evidence_refs": rel["roi_ids"],
        "program_graph": None,
        "operator_signature": "UNKNOWN_PENDING_SEMANTIC_REVIEW",
        "necessity": {
            "a_only": "UNKNOWN",
            "b_only": "UNKNOWN",
            "a_plus_b": "UNKNOWN",
            "single_frame_shortcut": "UNKNOWN",
            "subtitle_leak": "UNKNOWN",
            "official_qa_leak_risk": "DEV_META_TIME_HINTS_USED_FOR_DISCOVERY_ONLY",
            "status": "UNKNOWN",
        },
        "source_provenance": {
            "pipeline": "wp3_wave_production",
            "baseline_commit": BASELINE_COMMIT,
            "discovery": "BOUNDED_HISTOGRAM_SCENECHANGE",
            "semantic_certification": "UNRESOLVED",
        },
        "review_status": "DRAFT",
        "certification_ladder": "DRAFT",
        "split_assignment": "DEV_CONSTRUCTION",
        "formal_gold": False,
        "genre_guess": genre,
        "record_completeness": "EVIDENCE_PACK_ONLY",
        "blocked_reason": "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE_UNTIL_HUMAN_OR_GPT_REVIEW",
    }


def register_pool_and_policy(selected: list[dict[str, Any]]) -> dict[str, Any]:
    existing_ids = set()
    rows = []
    if POOL_PATH.exists():
        for line in POOL_PATH.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            rows.append(r)
            existing_ids.add(r["construction_video_id"])

    added = []
    for s in selected:
        vid = s["video_id"]
        if vid in existing_ids:
            continue
        row = {
            "construction_video_id": vid,
            "pool": "DEV_CONSTRUCTION",
            "not_sealed_final": True,
            "never_in_cg_new_chatgpt_discussion": True,
            "source_pack": "wp3_wave_production_2026-11-05",
            "status": "ASSETS_PUBLISHED_PENDING_SEMANTIC_REVIEW",
            "genre_guess": s["genre_guess"],
            "wave": s["wave"],
            "duration_s": s.get("duration_s"),
            "checksum_partial_sha256": s.get("checksum_partial_sha256"),
            "github_visible_assets": s.get("github_visible_assets") or [],
            "cursor_asserted_new_fact": False,
            "note": (
                "WP3 DEV construction registration. Evidence packs extracted; "
                "semantics UNRESOLVED. Not SUPPORTED. Not sealed final."
            ),
        }
        rows.append(row)
        added.append(vid)
        existing_ids.add(vid)

    write_jsonl(POOL_PATH, rows)

    policy = json.loads(POLICY_PATH.read_text())
    before = list(policy.get("exposed_or_construction") or [])
    exposed = set(before)
    newly = [v for v in added if v not in exposed]
    exposed.update(added)
    policy["exposed_or_construction"] = sorted(exposed)
    policy["reconciliation_wp3"] = {
        "utc": utc_now(),
        "added_ids": newly,
        "n_before": len(before),
        "n_after": len(exposed),
        "sealed_reservoir_untouched": True,
        "note": "WP3 DEV exposure only; sealed reservoir unchanged; not Seen/Unseen promotion.",
    }
    write_json(POLICY_PATH, policy)
    return {"pool_added": added, "policy_newly_exposed": newly}


def write_review_packet(wave_dir: Path, wave_name: str, video_reports: list[dict]) -> Path:
    lines = [
        f"# WP3 {wave_name} Human/GPT Semantic Review Packet",
        "",
        f"- baseline_commit: `{BASELINE_COMMIT}`",
        f"- built_utc: `{utc_now()}`",
        "- engineering_status: EVIDENCE_PACKS_READY",
        "- semantic_status: UNRESOLVED (no automatic SUPPORTED)",
        "- run_004: NOT unlocked by this packet",
        "",
        "## Instructions",
        "1. Open review frames in time order under each ROI directory.",
        "2. For each ROI, assign exactly one: `STATIC_VISIBLE` | `ORDERED_MULTIFRAME_SUGGESTS` | `CONTINUOUS_VIDEO_VERIFIED` | `UNRESOLVED`.",
        "3. For each pair, decide whether a true cross-window compositional relation exists.",
        "4. Do **not** copy official LVBench QA text/answers into Gold.",
        "5. Do **not** treat histogram discovery scores as semantic proof.",
        "6. If uncertain, leave `UNRESOLVED`.",
        "",
        "## Videos",
    ]
    for vr in video_reports:
        lines.append(f"### `{vr['video_id']}` ({vr['genre_guess']})")
        lines.append(f"- duration_s: {vr['duration_s']}")
        lines.append(f"- n_pairs: {len(vr['pairs'])}")
        for p in vr["pairs"]:
            lines.append(
                f"- pair `{p['pair_id']}`: early [{p['early']['t_start']}, {p['early']['t_end']}] "
                f"→ late [{p['late']['t_start']}, {p['late']['t_end']}] "
                f"(gap={round(p['late']['t_start']-p['early']['t_end'],1)}s)"
            )
            lines.append(f"  - early frames: `{p['early']['review_frames_dir']}`")
            lines.append(f"  - late frames: `{p['late']['review_frames_dir']}`")
        lines.append("")
    path = wave_dir / "HUMAN_GPT_REVIEW_PACKET.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def process_wave(wave_name: str, wave_specs: list[dict[str, Any]]) -> dict[str, Any]:
    wave_dir = WP3_ROOT / wave_name
    wave_dir.mkdir(parents=True, exist_ok=True)
    local_wave = LOCAL_MEDIA / wave_name
    local_wave.mkdir(parents=True, exist_ok=True)

    video_reports = []
    all_rois = []
    all_relations = []
    all_qa_stubs = []
    all_events = []
    failures = []

    for spec in wave_specs:
        vid = spec["video_id"]
        media = VIDEO_ROOT / f"{vid}.mp4"
        vdir = wave_dir / "videos" / vid
        vdir.mkdir(parents=True, exist_ok=True)
        ldir = local_wave / vid
        ldir.mkdir(parents=True, exist_ok=True)

        if not media.exists():
            failures.append({"video_id": vid, "error": "MEDIA_UNAVAILABLE"})
            continue

        duration = ffprobe_duration(media)
        if not duration:
            failures.append({"video_id": vid, "error": "DURATION_UNAVAILABLE"})
            continue
        checksum = partial_sha256(media)

        pairs = discover_pairs(vid, media, duration, ldir / "_work")
        if not pairs:
            failures.append({"video_id": vid, "error": "NO_PAIR_DISCOVERED"})
            continue

        pair_reports = []
        github_assets = []
        for early, late in pairs:
            pair_rep = {"pair_id": early.pair_id, "early": None, "late": None}
            for roi in (early, late):
                full_dir = ldir / roi.roi_id / "frames"
                review_dir = vdir / "review_frames" / roi.roi_id
                frames = extract_roi_frames(media, roi, full_dir, FRAMES_PER_ROI)
                review = copy_review_subset(frames, review_dir, REVIEW_FRAMES_PER_ROI)
                clip = maybe_extract_clip(media, roi, ldir / roi.roi_id / "clip.mp4")
                roi_row = {
                    "roi_id": roi.roi_id,
                    "video_id": vid,
                    "pair_id": roi.pair_id,
                    "role": roi.role,
                    "t_start": roi.t_start,
                    "t_end": roi.t_end,
                    "center_s": roi.center_s,
                    "discovery_score": roi.discovery_score,
                    "discovery_method": "BOUNDED_HISTOGRAM_SCENECHANGE",
                    "event_certification": "UNRESOLVED",
                    "n_frames_extracted": len(frames),
                    "frames_local": frames,
                    "review_frames": review,
                    "review_frames_dir": str(review_dir.relative_to(REPO_ROOT)),
                    "local_clip": clip,
                    "source_video_sha256_partial": checksum,
                }
                all_rois.append(roi_row)
                pair_rep[roi.role] = roi_row
                for fr in review:
                    github_assets.append(
                        {
                            "github_path": fr["path"],
                            "sha256": fr["sha256"],
                            "bytes": fr["bytes"],
                            "source_local": fr["path"],
                        }
                    )
                # Event stub — explicitly unresolved
                all_events.append(
                    {
                        "event_id": f"evt:{roi.roi_id}",
                        "video_id": vid,
                        "roi_id": roi.roi_id,
                        "time_start_s": roi.t_start,
                        "time_end_s": roi.t_end,
                        "summary": None,
                        "event_certification": "UNRESOLVED",
                        "provenance": "WP3_ENGINEERING_ROI_EXTRACTION",
                        "provenance_tier": "AUTOMATIC_COARSE_FRAME",
                        "is_newly_discovered_semantic": False,
                        "notes": "Frame pack extracted; semantic content not asserted by Cursor.",
                    }
                )
            rel = build_relation_hypothesis(early.pair_id, pair_rep["early"], pair_rep["late"])
            qa = build_qa_stub(rel, spec["genre_guess"])
            all_relations.append(rel)
            all_qa_stubs.append(qa)
            pair_reports.append(pair_rep)

        video_reports.append(
            {
                "video_id": vid,
                "wave": wave_name,
                "genre_guess": spec["genre_guess"],
                "reason": spec["reason"],
                "duration_s": round(duration, 3),
                "checksum_partial_sha256": checksum,
                "media_path": str(media),
                "not_sealed_final": True,
                "split_assignment": "DEV_CONSTRUCTION",
                "pairs": [
                    {
                        "pair_id": p["pair_id"],
                        "early": {
                            "roi_id": p["early"]["roi_id"],
                            "t_start": p["early"]["t_start"],
                            "t_end": p["early"]["t_end"],
                            "review_frames_dir": p["early"]["review_frames_dir"],
                            "n_frames": p["early"]["n_frames_extracted"],
                        },
                        "late": {
                            "roi_id": p["late"]["roi_id"],
                            "t_start": p["late"]["t_start"],
                            "t_end": p["late"]["t_end"],
                            "review_frames_dir": p["late"]["review_frames_dir"],
                            "n_frames": p["late"]["n_frames_extracted"],
                        },
                    }
                    for p in pair_reports
                ],
                "github_visible_assets": github_assets,
                "semantic_status": "UNRESOLVED",
                "formal_gold": False,
            }
        )

    packet = write_review_packet(wave_dir, wave_name, video_reports)
    write_jsonl(wave_dir / "rois.jsonl", all_rois)
    write_jsonl(wave_dir / "events_UNRESOLVED.jsonl", all_events)
    write_jsonl(wave_dir / "relation_hypotheses.jsonl", all_relations)
    write_jsonl(wave_dir / "qa_stubs_DRAFT.jsonl", all_qa_stubs)
    write_json(wave_dir / "video_reports.json", video_reports)
    write_json(wave_dir / "failures.json", failures)

    metrics = {
        "wave": wave_name,
        "n_videos_attempted": len(wave_specs),
        "n_videos_ok": len(video_reports),
        "n_failures": len(failures),
        "n_rois": len(all_rois),
        "n_evidence_windows": len(all_rois),
        "n_frames_extracted_total": sum(r["n_frames_extracted"] for r in all_rois),
        "n_review_frames_committed": sum(len(r["review_frames"]) for r in all_rois),
        "n_relation_hypotheses": len(all_relations),
        "n_qa_stubs_draft": len(all_qa_stubs),
        "n_semantic_events_certified": 0,
        "n_fact_verified": 0,
        "n_human_approved": 0,
        "n_formal_gold": 0,
        "necessity_pass": 0,
        "necessity_fail": 0,
        "necessity_unknown": len(all_qa_stubs),
        "genre_distribution": dict(Counter(v["genre_guess"] for v in video_reports)),
        "review_packet": str(packet.relative_to(REPO_ROOT)),
        "blocked_for_run004": True,
        "block_reason": "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE",
    }
    write_json(wave_dir / "wave_metrics.json", metrics)
    return {
        "metrics": metrics,
        "video_reports": video_reports,
        "failures": failures,
        "relations": all_relations,
        "qa_stubs": all_qa_stubs,
    }


def build_signature_coverage(before_ops: list[str], relations: list[dict]) -> dict[str, Any]:
    """Independent composition signature coverage table (hypotheses only)."""
    atomic = sorted(
        set(before_ops)
        | {
            "IdentifyEntity",
            "QueryAttribute",
            "QueryLocation",
            "QueryEarlierObject",
            "CrossIntervalSamePersonBind",
            "CrossViewSameObjectBind",
            "CrossViewSameRoomBind",
            "ConditionThenLaterOutcome",
            "ObjectStateChange",
            "ReverseTemporalQuery",
            "AudioVisualBind",
        }
    )
    observed_pairs = []
    for r in relations:
        observed_pairs.append(
            {
                "pair_id": r["pair_id"],
                "signature": "UNKNOWN_PENDING_SEMANTIC_REVIEW",
                "status": "HYPOTHESIS_ONLY",
                "ood_bucket": "UNASSIGNED",
            }
        )
    return {
        "schema": "wp3_composition_signature_coverage_v1",
        "built_utc": utc_now(),
        "atomic_operators": atomic,
        "observed_binary_ternary_combinations": observed_pairs,
        "target_unseen_combinations_examples": [
            "IdentifyEntity→QueryEarlierAttribute (atomic-covered OOD if Identify+Query seen separately)",
            "ConditionEvent→LaterOutcome with ObjectStateChange",
            "AudioVisualBind→QuerySpeakerAttribute",
            "ReverseTemporalQuery after CrossViewSameRoomBind",
        ],
        "ood_policy": {
            "primary_unseen_goal": "atomic-covered OOD: atoms in Seen, combination novel",
            "also_track": ["atomic-novel OOD", "mixed OOD", "ID/control"],
            "same_source_video_no_train_test_split": True,
            "proposed_7_4_status": "PROPOSED",
            "frozen_5_2_unchanged": True,
        },
        "note": "No signature promoted to Seen/Unseen; all WP3 pairs pending semantic review.",
    }


def write_staging_batch(all_qa: list[dict], all_rel: list[dict]) -> Path:
    staging = DS_ROOT / "staging" / "wp3_wave1_wave2_draft_batch.json"
    items = []
    for qa, rel in zip(all_qa, all_rel):
        items.append(
            {
                "source_item_id": qa["source_item_id"],
                "video_id": qa["video_id"],
                "question": qa["question"],
                "answer": qa["answer"],
                "answer_status": "UNKNOWN_PENDING_SEMANTIC_REVIEW",
                "windows_seconds": qa["windows_seconds"],
                "evidence_refs": qa["evidence_refs"],
                "program_graph": {
                    "nodes": [
                        {
                            "id": "n0",
                            "op": "UNKNOWN_PENDING_SEMANTIC_REVIEW",
                            "status": "DRAFT",
                        }
                    ],
                    "edges": [],
                    "status": "DRAFT_PLACEHOLDER_NOT_EXECUTABLE",
                },
                "operator_signature": qa["operator_signature"],
                "necessity": qa["necessity"],
                "source_provenance": qa["source_provenance"],
                "review_status": "DRAFT",
                "split_assignment": "PENDING",
                "formal_gold": False,
                "relation_hypothesis": rel,
                "import_ready": False,
                "import_block_reason": "SEMANTICS_UNRESOLVED_AND_QA_TEXT_NULL",
            }
        )
    batch = {
        "batch_id": "wp3_wave1_wave2_draft_2026-11-05",
        "status": "STAGING_ONLY_NOT_IMPORTED",
        "formal_gold": False,
        "items": items,
        "note": (
            "Staging only. Not imported into DEV dataset. "
            "v0.1.0–v0.1.2 immutable. Awaiting Human/GPT semantic review."
        ),
    }
    write_json(staging, batch)
    return staging


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--waves", default="1,2", help="Comma list: 1,2")
    args = ap.parse_args()
    want = {int(x) for x in args.waves.split(",") if x.strip()}

    WP3_ROOT.mkdir(parents=True, exist_ok=True)
    LOCAL_MEDIA.mkdir(parents=True, exist_ok=True)

    exposed_before = load_exposed()
    wp3_ids = {s["video_id"] for s in WAVE1 + WAVE2}
    # Preflight: new relative to pre-WP3 exposure, but allow idempotent re-runs of this pack.
    prior_non_wp3 = exposed_before - wp3_ids
    selected_all = []
    results = {}
    if 1 in want:
        for s in WAVE1:
            if s["video_id"] in prior_non_wp3:
                raise SystemExit(f"REFUSING_EXPOSED_NON_WP3_VIDEO: {s['video_id']}")
            selected_all.append({**s, "wave": "wave1"})
        results["wave1"] = process_wave("wave1", WAVE1)
    if 2 in want:
        for s in WAVE2:
            if s["video_id"] in prior_non_wp3:
                raise SystemExit(f"REFUSING_EXPOSED_NON_WP3_VIDEO: {s['video_id']}")
            selected_all.append({**s, "wave": "wave2"})
        results["wave2"] = process_wave("wave2", WAVE2)

    # Enrich selected with durations/checksums from reports
    by_vid = {}
    for w in results.values():
        for vr in w["video_reports"]:
            by_vid[vr["video_id"]] = vr
    for s in selected_all:
        vr = by_vid.get(s["video_id"], {})
        s["duration_s"] = vr.get("duration_s")
        s["checksum_partial_sha256"] = vr.get("checksum_partial_sha256")
        s["github_visible_assets"] = vr.get("github_visible_assets") or []

    reg = register_pool_and_policy(selected_all)

    all_rel = []
    all_qa = []
    for w in results.values():
        all_rel.extend(w["relations"])
        all_qa.extend(w["qa_stubs"])
    staging = write_staging_batch(all_qa, all_rel)

    # Existing atomic ops from seed graphs (names only)
    before_ops = [
        "Locate",
        "Query",
        "Bind",
        "CrossIntervalSamePersonBind",
        "CrossViewSameRoomBind",
        "Filter",
    ]
    coverage = build_signature_coverage(before_ops, all_rel)
    write_json(WP3_ROOT / "composition_signature_coverage.json", coverage)

    # Aggregate report
    def sum_m(key: str) -> int:
        return sum(int(results[w]["metrics"].get(key, 0)) for w in results)

    report = {
        "schema": "wp3_wave_production_report_v1",
        "work_package": "WP3",
        "baseline_commit": BASELINE_COMMIT,
        "built_utc": utc_now(),
        "engineering_status": "EVIDENCE_PRODUCTION_COMPLETE_SEMANTICS_PENDING",
        "scientific_status": "UNRESOLVED_PENDING_HUMAN_GPT_REVIEW",
        "run_004_status": "NOT_STARTED",
        "run_004_gate": "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE",
        "wp2_3_required": False,
        "immutable_releases_preserved": ["v0.1.0", "v0.1.1", "v0.1.2"],
        "proposed_7_4_status": "PROPOSED",
        "frozen_5_2_unchanged": True,
        "registration": reg,
        "waves": {w: results[w]["metrics"] for w in results},
        "video_lists": {
            w: [v["video_id"] for v in results[w]["video_reports"]] for w in results
        },
        "production_metrics": {
            "n_new_videos": sum_m("n_videos_ok"),
            "n_independent_videos": sum_m("n_videos_ok"),
            "genre_distribution": dict(
                sum(
                    (Counter(results[w]["metrics"]["genre_distribution"]) for w in results),
                    Counter(),
                )
            ),
            "n_rois_evidence_windows": sum_m("n_rois"),
            "n_frames_extracted": sum_m("n_frames_extracted_total"),
            "n_review_frames": sum_m("n_review_frames_committed"),
            "n_semantic_events_certified": 0,
            "n_fact_verified": 0,
            "n_cross_window_relations_valid": 0,
            "n_relation_hypotheses": sum_m("n_relation_hypotheses"),
            "n_independent_qa_families": 0,
            "n_qa_drafts": sum_m("n_qa_stubs_draft"),
            "necessity_pass": 0,
            "necessity_fail": 0,
            "necessity_unknown": sum_m("necessity_unknown"),
            "n_human_approved": 0,
            "n_formal_gold": 0,
            "layer1_layer2_coverage": "UNASSIGNED_PENDING_GRAPH_DESIGN",
            "dedup_leakage": {
                "selected_not_in_prior_exposed": True,
                "same_video_not_marked_sealed_test": True,
                "official_qa_not_promoted": True,
            },
            "yield_notes": (
                "Evidence packs produced for all OK videos. "
                "Effective compositional QA yield = 0 until semantics reviewed."
            ),
        },
        "paths": {
            "wp3_root": str(WP3_ROOT.relative_to(REPO_ROOT)),
            "local_media": str(LOCAL_MEDIA.relative_to(REPO_ROOT)),
            "staging_batch": str(staging.relative_to(REPO_ROOT)),
            "signature_coverage": str(
                (WP3_ROOT / "composition_signature_coverage.json").relative_to(REPO_ROOT)
            ),
            "review_packets": [
                results[w]["metrics"]["review_packet"] for w in results
            ],
        },
        "failure_reasons_and_next_priorities": [
            {
                "failure": "No HUMAN/GPT certified compositional events yet",
                "impact": "0 FACT_VERIFIED / 0 Formal Gold",
                "next": "Review Wave1 packet first; only then mint relation+QA for certified pairs",
            },
            {
                "failure": "Histogram discovery ≠ semantic event",
                "impact": "Pairs may be scene cuts without bindable entities",
                "next": "Prefer pairs where review finds same person/object/room or state change",
            },
            {
                "failure": "Cannot auto-pass Necessity from graph templates",
                "impact": "necessity_unknown for all stubs",
                "next": "Run A-only/B-only after facts exist; reject single-frame shortcuts",
            },
        ],
        "explicit_non_actions": [
            "Did not create WP2.3",
            "Did not modify A/B Gold or reopen same-person/room review",
            "Did not regenerate v0.1.0–v0.1.2",
            "Did not import staging into DEV dataset",
            "Did not unlock run_004",
            "Did not run Track A experiments or paid VLM batches",
            "Did not mark DEV videos as sealed final test",
        ],
    }
    write_json(WP3_ROOT / "WP3_WAVE_PRODUCTION_REPORT.json", report)
    write_json(DS_ROOT / "reports" / "WP3_WAVE_PRODUCTION_REPORT.json", report)

    # Human-readable summary
    md = [
        "# WP3 Wave Production Report",
        "",
        f"- built_utc: `{report['built_utc']}`",
        f"- baseline: `{BASELINE_COMMIT}`",
        f"- engineering: **{report['engineering_status']}**",
        f"- run_004: `{report['run_004_gate']}`",
        "",
        "## Videos",
    ]
    for w in sorted(results):
        md.append(f"### {w}")
        for vid in report["video_lists"][w]:
            md.append(f"- `{vid}`")
    md += [
        "",
        "## Metrics (candidate / verified / gold)",
        f"- new videos: **{report['production_metrics']['n_new_videos']}**",
        f"- ROI/evidence windows: **{report['production_metrics']['n_rois_evidence_windows']}**",
        f"- semantic events certified: **0**",
        f"- FACT_VERIFIED: **0**",
        f"- relation hypotheses: **{report['production_metrics']['n_relation_hypotheses']}**",
        f"- valid cross-window relations: **0**",
        f"- QA stubs (DRAFT): **{report['production_metrics']['n_qa_drafts']}**",
        f"- Necessity PASS/FAIL/UNKNOWN: 0 / 0 / {report['production_metrics']['necessity_unknown']}",
        f"- Human Approved: **0**",
        f"- Formal Gold: **0**",
        "",
        "## Next",
        "1. Human/GPT review Wave1 packet.",
        "2. Certify only non-trivial compositional events.",
        "3. Then design QA + necessity; import via staging only after review.",
    ]
    (WP3_ROOT / "WP3_WAVE_PRODUCTION_REPORT.md").write_text("\n".join(md) + "\n")
    print(json.dumps(report["production_metrics"], ensure_ascii=False, indent=2))
    print("report=", WP3_ROOT / "WP3_WAVE_PRODUCTION_REPORT.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
