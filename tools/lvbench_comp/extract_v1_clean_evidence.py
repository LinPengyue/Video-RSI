#!/usr/bin/env python3
"""Extract review clips for the cleaned compositional candidates.

Phase 1 clips are copied when their recorded sha256 still matches the file.
This script does not judge whether a candidate is factually correct.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from extract_evidence import (
    extract_case,
    parse_time_reference,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[2]
PHASE1_MEDIA = ROOT / "research_audit/lvbench_compositional/phase1/local_media"
PHASE1_MANIFEST = ROOT / "research_audit/lvbench_compositional/phase1/evidence_manifest.json"
METADATA = Path("/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl")
VIDEO_ROOT = Path("/home/descfly/lpy/dataset/LVBench/videos")
FFMPEG = Path(
    "/home/descfly/miniconda3/envs/videorsi/lib/python3.12/site-packages/"
    "imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
)
FFPROBE = Path("/home/descfly/.cache/lvbench-comp/ffprobe")

# Ten items, ten videos. 007 would repeat JTa_Ue2MSwc, which 043 already uses.
SELECTED = ["010", "012", "017", "022", "029", "030", "032", "038", "043", "008"]
REUSE_UIDS = {
    ("_T2Avd3tFHc", "2873"),
    ("_T2Avd3tFHc", "2890"),
    ("q01CUy_gwdU", "120"),
    ("q01CUy_gwdU", "121"),
}


def _phase1_windows() -> dict[tuple[str, str, str], dict]:
    payload = json.loads(PHASE1_MANIFEST.read_text(encoding="utf-8"))
    windows = {}
    for case in payload["cases"]:
        for segment in case["segments"]:
            for window in segment["extractions"]:
                windows[(case["video_id"], str(segment["uid"]), window["mode"])] = window
    return windows


def _copy_reused(video_id: str, uid: str, media_root: Path, windows_meta: dict[tuple[str, str, str], dict]) -> dict:
    source = PHASE1_MEDIA / video_id / f"uid_{uid}"
    target = media_root / video_id / f"uid_{uid}"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    windows = {}
    for mode in ("strict", "context"):
        clip = target / mode / "clip.mp4"
        digest = sha256_file(clip)
        meta = windows_meta[(video_id, uid, mode)]
        if digest != meta["clip_sha256"]:
            raise SystemExit(f"phase1 hash mismatch for {video_id} {uid} {mode}")
        windows[mode] = {
            "clip_path": str(clip.relative_to(media_root)),
            "clip_sha256": digest,
            "contact_sheet": str((target / mode / "contact_sheet.jpg").relative_to(media_root)),
            "frame_count": len(list((target / mode / "frames").glob("frame_*.jpg"))),
            "reused_from_phase1": True,
            "start_seconds": meta["start_seconds"],
            "end_seconds": meta["end_seconds"],
        }
    return windows


def _extract(video_id: str, uids: list[str], media_root: Path) -> dict:
    result = extract_case(
        video_id=video_id,
        uids=uids,
        metadata_path=METADATA,
        video_root=VIDEO_ROOT,
        output_dir=media_root,
        context_seconds=20,
        frames=10,
        ffmpeg=FFMPEG,
        ffprobe=FFPROBE,
        repo_root=ROOT,
    )
    if not result.get("ok"):
        raise SystemExit(f"extract failed for {video_id}: {result.get('message')}")
    by_uid = {}
    for segment in result["segments"]:
        windows = {}
        for window in segment["extractions"]:
            windows[window["mode"]] = {
                "clip_path": window["clip_path"],
                "clip_sha256": window["clip_sha256"],
                "contact_sheet": window["contact_sheet"],
                "frame_count": len(window["keyframes"]),
                "reused_from_phase1": False,
                "start_seconds": window["start_seconds"],
                "end_seconds": window["end_seconds"],
            }
        by_uid[str(segment["uid"])] = windows
    return by_uid


def build_index(candidates_path: Path, media_root: Path) -> dict:
    rows = [json.loads(line) for line in candidates_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {row["id"].rsplit("-", 1)[-1]: row for row in rows}
    media_root.mkdir(parents=True, exist_ok=True)
    phase1_windows = _phase1_windows()
    extracted: dict[tuple[str, str], dict] = {}
    grouped: dict[str, list[str]] = {}
    selected_rows = []
    for number in SELECTED:
        row = by_id[number]
        selected_rows.append(row)
        if (row["video_id"], row["source_uids"][0]) in REUSE_UIDS:
            continue
        grouped.setdefault(row["video_id"], [])
        for uid in row["source_uids"]:
            if uid not in grouped[row["video_id"]]:
                grouped[row["video_id"]].append(uid)
    for video_id, uids in grouped.items():
        print(f"extract {video_id} {uids}", flush=True)
        extracted.update({(video_id, uid): windows for uid, windows in _extract(video_id, uids, media_root).items()})
    items = []
    for row in selected_rows:
        uids = []
        for uid in row["source_uids"]:
            key = (row["video_id"], uid)
            if key in REUSE_UIDS:
                windows = _copy_reused(row["video_id"], uid, media_root, phase1_windows)
            else:
                windows = extracted[key]
            reference = row["time_references"][row["source_uids"].index(uid)]
            official_start, official_end = parse_time_reference(reference)
            uids.append(
                {
                    "uid": uid,
                    "time_reference": reference,
                    "official_start_seconds": official_start,
                    "official_end_seconds": official_end,
                    "windows": windows,
                }
            )
        items.append(
            {
                "id": row["id"],
                "video_id": row["video_id"],
                "composition_type": row["composition_type"],
                "question": row["new_question"],
                "answer": row["new_answer"],
                "review_status": row["review_status"],
                "video_verified": False,
                "uids": uids,
            }
        )
    return {
        "selected_ids": [row["id"] for row in selected_rows],
        "video_count": len({row["video_id"] for row in selected_rows}),
        "items": items,
        "judgment": "PENDING_VIDEO_REVIEW",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract clips for the cleaned QA review set.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    args = parser.parse_args(argv)
    index = build_index(args.candidates, args.media_root)
    args.index.parent.mkdir(parents=True, exist_ok=True)
    args.index.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"items": len(index["items"]), "videos": index["video_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
