#!/usr/bin/env python3
"""Zero-API MLVU-Test path fix, media validation, stratified freeze, safe reports.

Does not call paid APIs. Does not modify harnesses / Solver / Gate.
Does not write answers into public items. Does not invent GT.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREP = Path(__file__).resolve().parent
ITEMS = PREP / "mlvu_test_mc_items.jsonl"
MC_JSON = Path("/home/descfly/lpy/dataset/MLVU_Test/test_multi_choice_tasks.json")
GEN_JSON = Path("/home/descfly/lpy/dataset/MLVU_Test/test_generation_tasks.json")
VIDEO_DIR = Path("/home/descfly/lpy/dataset/MLVU_Test/MLVU_Test/video")
GT_CANDIDATES = [
    Path("/home/descfly/lpy/dataset/MLVU_Test/test-ground-truth/test_mcq_gt.json"),
    Path("/home/descfly/lpy/dataset/MLVU_Test/MLVU_Test/test_mcq_gt.json"),
    Path("/home/descfly/lpy/dataset/MLVU_Test/test_mcq_gt.json"),
]
FFMPEG = Path(
    os.environ.get(
        "FFMPEG_BIN",
        "/home/descfly/miniconda3/envs/videorsi/lib/python3.12/site-packages/"
        "imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2",
    )
)
SEED = 20261023  # new freeze seed (video-disjoint primary/smoke)
OLD_WRONG_SEGMENT = "/MLVU_Test/MLVU_Test/videos/"
NEW_SEGMENT = "/MLVU_Test/MLVU_Test/video/"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode())


def load_jsonl(path: Path) -> list:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fix_paths(rows: list) -> tuple[list, dict]:
    changed = 0
    still_wrong = []
    fixed = []
    for row in rows:
        path = row["video_path"]
        if OLD_WRONG_SEGMENT in path:
            path = path.replace(OLD_WRONG_SEGMENT, NEW_SEGMENT)
            changed += 1
        # Also normalize accidental double/videos typos
        path = path.replace("/videos/", "/video/")
        row = dict(row)
        row["video_path"] = path
        if "/video/" not in path or "/videos/" in path:
            still_wrong.append(row["sample_id"])
        fixed.append(row)
    return fixed, {"paths_rewritten": changed, "still_wrong_ids": still_wrong}


def largest_remainder_alloc(counts: dict[str, int], n: int) -> dict[str, int]:
    types = sorted(counts.keys())
    k = len(types)
    if n < k:
        raise ValueError("n < number of task types; cannot min-1 allocate")
    # First give 1 each, then distribute remaining proportionally.
    rem_n = n - k
    total = sum(counts[t] for t in types)
    raw = {t: rem_n * counts[t] / total for t in types}
    base = {t: 1 + int(raw[t]) for t in types}
    leftover = rem_n - sum(int(raw[t]) for t in types)
    order = sorted(types, key=lambda t: (raw[t] - int(raw[t]), counts[t], t), reverse=True)
    for t in order[:leftover]:
        base[t] += 1
    # Cap by available counts
    for t in types:
        if base[t] > counts[t]:
            raise ValueError(f"allocation {base[t]} > available {counts[t]} for {t}")
    assert sum(base.values()) == n
    return base


def sample_stratified_video_aware(
    rows: list,
    n: int,
    seed: int,
    *,
    banned_videos: set[str] | None = None,
    prefer_unique_video: bool = True,
) -> tuple[list[str], dict]:
    """Stratified by task_type; within type prefer distinct videos; avoid banned_videos when possible."""
    banned_videos = set(banned_videos or ())
    rng = random.Random(seed)
    by_type: dict[str, list] = defaultdict(list)
    for row in rows:
        by_type[row["task_type"]].append(row)
    for t in by_type:
        by_type[t].sort(key=lambda r: r["sample_id"])
        rng.shuffle(by_type[t])

    counts = {t: len(v) for t, v in by_type.items()}
    alloc = largest_remainder_alloc(counts, n)

    chosen = []
    used_videos: set[str] = set()
    video_reuse = 0
    forced_banned = 0
    picked_ids: set[str] = set()

    def try_pick(pool, need, picked, *, allow_banned: bool, allow_reuse: bool) -> None:
        nonlocal video_reuse, forced_banned
        for row in pool:
            if len(picked) >= need:
                return
            if row["sample_id"] in picked_ids:
                continue
            v = Path(row["video_path"]).name
            banned = v in banned_videos
            reused = v in used_videos
            if banned and not allow_banned:
                continue
            if reused and not allow_reuse:
                continue
            if reused:
                video_reuse += 1
            if banned:
                forced_banned += 1
            picked.append(row)
            picked_ids.add(row["sample_id"])
            used_videos.add(v)

    for t, need in sorted(alloc.items()):
        pool = by_type[t]
        picked: list = []
        # Prefer: unique+not-banned → reuse+not-banned → unique+banned → reuse+banned
        try_pick(pool, need, picked, allow_banned=False, allow_reuse=False)
        if prefer_unique_video:
            try_pick(pool, need, picked, allow_banned=False, allow_reuse=True)
        try_pick(pool, need, picked, allow_banned=True, allow_reuse=False)
        try_pick(pool, need, picked, allow_banned=True, allow_reuse=True)
        if len(picked) < need:
            raise RuntimeError(f"cannot fill {need} for {t}; got {len(picked)}")
        chosen.extend(picked[:need])

    chosen.sort(key=lambda r: r["sample_id"])
    ids = [r["sample_id"] for r in chosen]
    vids = [Path(r["video_path"]).name for r in chosen]
    meta = {
        "allocation_by_task_type": alloc,
        "n_unique_videos": len(set(vids)),
        "n_items": len(ids),
        "video_reuse_extra_questions": video_reuse,
        "used_banned_video_count": forced_banned,
        "videos": sorted(set(vids)),
    }
    return ids, meta


def ffmpeg_probe(path: Path) -> dict:
    cmd = [str(FFMPEG), "-hide_banner", "-i", str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    text = (proc.stderr or "") + (proc.stdout or "")
    dur = None
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    has_video = bool(re.search(r"Stream #\d+:\d+.*Video:", text))
    codec = None
    cm = re.search(r"Video:\s*([^\s,(]+)", text)
    if cm:
        codec = cm.group(1)
    return {
        "ok_header": has_video and dur is not None,
        "duration_sec": dur,
        "has_video_stream": has_video,
        "codec": codec,
        "ffmpeg_returncode": proc.returncode,  # often 1 because no output specified
    }


def ffmpeg_decode_smoke(path: Path, frames: int = 8) -> dict:
    # Decode a few frames to null muxer; fail on decode errors.
    cmd = [
        str(FFMPEG),
        "-v",
        "error",
        "-i",
        str(path),
        "-frames:v",
        str(frames),
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0 and not (proc.stderr or "").strip(),
        "returncode": proc.returncode,
        "stderr": (proc.stderr or "")[:500],
    }


def main() -> int:
    if not VIDEO_DIR.is_dir():
        print("VIDEO_DIR missing:", VIDEO_DIR, file=sys.stderr)
        return 2
    if not FFMPEG.is_file():
        print("FFMPEG missing:", FFMPEG, file=sys.stderr)
        return 2

    rows = load_jsonl(ITEMS)
    rows, path_fix = fix_paths(rows)
    write_jsonl(ITEMS, rows)
    items_sha = sha256_file(ITEMS)

    disk_files = sorted(p for p in VIDEO_DIR.iterdir() if p.is_file())
    disk_names = {p.name for p in disk_files}
    zero_byte = [p.name for p in disk_files if p.stat().st_size == 0]
    tiny = [p.name for p in disk_files if 0 < p.stat().st_size < 1024]

    mc = json.loads(MC_JSON.read_text(encoding="utf-8"))
    gen = json.loads(GEN_JSON.read_text(encoding="utf-8"))
    mc_videos = sorted({r["video"] for r in mc})
    gen_videos = sorted({r["video"] for r in gen})
    ann_videos = sorted(set(mc_videos) | set(gen_videos))

    missing_paths = []
    present = 0
    for row in rows:
        p = Path(row["video_path"])
        if p.is_file() and p.stat().st_size > 0:
            present += 1
        else:
            missing_paths.append({"sample_id": row["sample_id"], "video_path": str(p)})

    mc_missing_on_disk = [v for v in mc_videos if v not in disk_names]
    disk_not_in_ann = sorted(disk_names - set(ann_videos))
    ann_not_on_disk = sorted(set(ann_videos) - disk_names)

    # Probe all unique MC videos headers (ffmpeg -i); decode smoke on stratified subset.
    mc_paths = sorted({Path(r["video_path"]) for r in rows})
    probe_failures = []
    duration_mismatches = []
    by_name_duration = {r["video"]: float(r["duration"]) for r in mc}
    # Use first row duration if multi-question same video — durations should agree
    for r in rows:
        name = Path(r["video_path"]).name
        by_name_duration.setdefault(name, float(r["duration"]))

    print(f"Probing {len(mc_paths)} unique MC video headers with ffmpeg...", flush=True)
    for i, path in enumerate(mc_paths):
        if not path.is_file():
            probe_failures.append({"file": path.name, "reason": "missing"})
            continue
        info = ffmpeg_probe(path)
        if not info["ok_header"]:
            probe_failures.append({"file": path.name, "reason": "bad_header", **info})
            continue
        expected = by_name_duration.get(path.name)
        if expected is not None and info["duration_sec"] is not None:
            if abs(info["duration_sec"] - expected) > 1.5:
                duration_mismatches.append(
                    {
                        "file": path.name,
                        "ann_duration": expected,
                        "ffmpeg_duration": info["duration_sec"],
                    }
                )
        if (i + 1) % 50 == 0:
            print(f"  probed {i+1}/{len(mc_paths)}", flush=True)

    # Decode smoke: pick short/long + diverse task types
    by_type = defaultdict(list)
    for row in rows:
        by_type[row["task_type"]].append(row)
    smoke_candidates = []
    for t, lst in sorted(by_type.items()):
        smoke_candidates.append(min(lst, key=lambda r: r["duration"]))
        smoke_candidates.append(max(lst, key=lambda r: r["duration"]))
    # Dedup by video
    seen_v = set()
    decode_targets = []
    for row in smoke_candidates:
        v = Path(row["video_path"]).name
        if v in seen_v:
            continue
        seen_v.add(v)
        decode_targets.append(row)
    decode_targets = decode_targets[:18]  # capped small set
    decode_results = []
    print(f"Decode smoke on {len(decode_targets)} videos...", flush=True)
    for row in decode_targets:
        path = Path(row["video_path"])
        res = ffmpeg_decode_smoke(path)
        decode_results.append(
            {
                "sample_id": row["sample_id"],
                "task_type": row["task_type"],
                "video": path.name,
                "duration": row["duration"],
                **res,
            }
        )

    # GT search
    gt_found = None
    for p in GT_CANDIDATES:
        if p.is_file():
            gt_found = str(p)
            break
    # broader search under dataset root (names only)
    broader = []
    for p in Path("/home/descfly/lpy/dataset/MLVU_Test").rglob("*"):
        if p.is_file() and ("gt" in p.name.lower() or "ground" in p.name.lower() or "label" in p.name.lower()):
            broader.append(str(p))

    # Freeze samples: smoke first (unique videos), then primary avoiding smoke videos.
    # This keeps engineering smoke disjoint from primary video set when the pool allows.
    smoke_ids, smoke_meta = sample_stratified_video_aware(
        rows,
        10,
        SEED + 1,
        prefer_unique_video=True,
    )
    smoke_videos = set(smoke_meta["videos"])
    primary_ids, primary_meta = sample_stratified_video_aware(
        rows,
        200,
        SEED,
        banned_videos=smoke_videos,
        prefer_unique_video=True,
    )
    primary_videos = set(primary_meta["videos"])
    overlap_videos = sorted(primary_videos & smoke_videos)
    overlap_ids = sorted(set(primary_ids) & set(smoke_ids))

    sample_n10 = {
        "seed": SEED + 1,
        "n": 10,
        "role": "smoke",
        "source_items": "research_audit/mlvu_test_prep/mlvu_test_mc_items.jsonl",
        "source_items_sha256": items_sha,
        "method": "stratified_task_type_min1_largest_remainder_prefer_unique_video_smoke_first",
        "allocation_by_task_type": smoke_meta["allocation_by_task_type"],
        "n_unique_videos": smoke_meta["n_unique_videos"],
        "video_overlap_with_primary": overlap_videos,
        "sample_ids": smoke_ids,
        "note": "Engineering smoke IDs. Do not retune harnesses using MLVU answers.",
    }
    sample_n200 = {
        "seed": SEED,
        "n": 200,
        "role": "primary",
        "source_items": "research_audit/mlvu_test_prep/mlvu_test_mc_items.jsonl",
        "source_items_sha256": items_sha,
        "method": "stratified_task_type_min1_largest_remainder_prefer_unique_video_avoid_smoke",
        "allocation_by_task_type": primary_meta["allocation_by_task_type"],
        "n_unique_videos": primary_meta["n_unique_videos"],
        "video_reuse_extra_questions": primary_meta["video_reuse_extra_questions"],
        "used_banned_smoke_video_count": primary_meta["used_banned_video_count"],
        "sample_ids": primary_ids,
        "note": "Primary prep IDs. Do not retune harnesses using MLVU answers.",
    }
    write_json(PREP / "sample_ids_n10.json", sample_n10)
    write_json(PREP / "sample_ids_n200.json", sample_n200)

    # Conversion / path manifest update
    conversion = {
        "items_jsonl": "research_audit/mlvu_test_prep/mlvu_test_mc_items.jsonl",
        "items_sha256": items_sha,
        "n_mc": len(rows),
        "expected_video_root": str(VIDEO_DIR),
        "path_fix": path_fix,
        "videos_present_for_items": present,
        "unique_mc_videos_in_items": len({Path(r["video_path"]).name for r in rows}),
    }
    write_json(PREP / "conversion_manifest.json", conversion)

    media_report = {
        "video_dir": str(VIDEO_DIR),
        "n_files_on_disk": len(disk_files),
        "n_bytes_total": sum(p.stat().st_size for p in disk_files),
        "zero_byte_files": zero_byte,
        "tiny_under_1kb_files": tiny,
        "n_mc_questions": len(rows),
        "n_item_paths_valid_nonzero": present,
        "missing_item_paths": missing_paths,
        "n_unique_mc_videos_annotation": len(mc_videos),
        "mc_videos_missing_on_disk": mc_missing_on_disk,
        "n_generation_videos_annotation": len(gen_videos),
        "n_annotation_union_videos": len(ann_videos),
        "annotation_videos_missing_on_disk": ann_not_on_disk,
        "disk_files_not_in_annotation": disk_not_in_ann,
        "ffmpeg_bin": str(FFMPEG),
        "probe_failures": probe_failures,
        "duration_mismatches_gt_1_5s": duration_mismatches,
        "decode_smoke": decode_results,
        "decode_smoke_pass": all(d["ok"] for d in decode_results),
        "gt_search": {
            "candidates_checked": [str(p) for p in GT_CANDIDATES],
            "found": gt_found,
            "broader_name_hits_under_dataset": broader,
            "local_gt_present": bool(gt_found),
        },
        "samples": {
            "smoke_n10_sha256": sha256_file(PREP / "sample_ids_n10.json"),
            "primary_n200_sha256": sha256_file(PREP / "sample_ids_n200.json"),
            "smoke_unique_videos": smoke_meta["n_unique_videos"],
            "primary_unique_videos": primary_meta["n_unique_videos"],
            "smoke_primary_video_overlap": overlap_videos,
            "smoke_primary_id_overlap": overlap_ids,
        },
        "answers_omitted": True,
    }
    write_json(PREP / "media_validation_report.json", media_report)

    # Console summary (no answers)
    summary = {
        "items_fixed_paths": path_fix,
        "items_sha256": items_sha,
        "paths_valid": f"{present}/{len(rows)}",
        "mc_videos_on_disk": f"{len(mc_videos) - len(mc_missing_on_disk)}/{len(mc_videos)}",
        "disk_files": len(disk_files),
        "ann_union": len(ann_videos),
        "zero_byte": len(zero_byte),
        "probe_failures": len(probe_failures),
        "duration_mismatches": len(duration_mismatches),
        "decode_smoke_pass": media_report["decode_smoke_pass"],
        "gt_present": bool(gt_found),
        "smoke_ids": smoke_ids,
        "primary_n": len(primary_ids),
        "primary_unique_videos": primary_meta["n_unique_videos"],
        "smoke_unique_videos": smoke_meta["n_unique_videos"],
        "video_overlap_smoke_primary": overlap_videos,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if present == len(rows) and not mc_missing_on_disk and not probe_failures and not zero_byte else 1


if __name__ == "__main__":
    raise SystemExit(main())
