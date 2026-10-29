#!/usr/bin/env python3
"""Prepare video-grounded evidence packs for identify_person + query_action.

Extracts local clips + contact sheets only. Does NOT mint formal compositional
QA, does NOT mark SUPPORTED, and does NOT invent verified video facts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
META = Path("/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl")
VIDEO_DIR = Path("/home/descfly/lpy/dataset/LVBench/videos")
OUT = ROOT / "research_audit/lvbench_compositional/video_grounded_pilot"
MEDIA = OUT / "local_media"
FFMPEG = Path.home() / ".cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffmpeg"
FFPROBE = Path.home() / ".cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffprobe"
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")

# Three curated evidence attempts. Fact B prefers VIDEO_OBSERVATION candidates.
CANDIDATES: list[dict] = [
    {
        "candidate_id": "VG-001",
        "video_id": "JTa_Ue2MSwc",
        "video_type": "talk_show_interview",
        "prior_complete_comp_qa": True,
        "selection_reason": "Interview show with clear person IDs; use a Sierra window not covered by the known shoe/slap official action QAs.",
        "bridge_entity": "Sierra",
        "fact_A": {
            "content": "The first interviewee is Sierra.",
            "time": "00:29-01:36",
            "source": "OFFICIAL_QA",
            "related_official_uids": ["5130"],
            "context_pad_seconds": 5.0,
        },
        "fact_B": {
            "content": "CANDIDATE VIDEO OBSERVATION (unverified): during the Kindall-on-stage interval, Sierra performs a visible action toward Kindall / on stage.",
            "time": "03:00-03:45",
            "source": "VIDEO_OBSERVATION_CANDIDATE",
            "related_official_uids": ["5132"],
            "related_official_note": "UID 5132 asks a general 'what happens after Kindall comes' question; it is not treated as a verified Sierra-specific action label.",
            "context_pad_seconds": 5.0,
            "observation_prompt_for_reviewer": "Confirm whether Sierra is clearly visible and what concrete action she performs in this window. Do not accept plot memory alone.",
        },
        "identity_ambiguity": "MEDIUM: multiple women on stage; reviewer must confirm the first-interviewee Sierra vs Kindall/others.",
        "shortcut_risk": "SINGLE_CLIP_SHORTCUT_RISK if Fact B alone visually IDs Sierra without Fact A.",
        "status": "PENDING_HUMAN_REVIEW",
    },
    {
        "candidate_id": "VG-002",
        "video_id": "_T2Avd3tFHc",
        "video_type": "travel_vlog",
        "prior_complete_comp_qa": False,
        "selection_reason": "Vlog unused by v3 Unseen compositions; Mikhail is named in official QA, but the bell-ringing clip does not name the actor.",
        "bridge_entity": "Mikhail",
        "fact_A": {
            "content": "The elder who joins the vlogger on their travel is Mikhail.",
            "time": "04:30-05:05",
            "source": "OFFICIAL_QA",
            "related_official_uids": ["2873"],
            "official_time_reference": "04:44-04:44",
            "context_pad_seconds": 8.0,
        },
        "fact_B": {
            "content": "CANDIDATE VIDEO OBSERVATION (unverified): at the bell-ringing moment, Mikhail is the person who rings the bell (or otherwise performs the visible ringing action).",
            "time": "26:35-26:55",
            "source": "VIDEO_OBSERVATION_CANDIDATE",
            "related_official_uids": ["2886"],
            "related_official_note": "UID 2886 only asks which day a team member rings a bell; it does not identify Mikhail or describe the action agent.",
            "context_pad_seconds": 3.0,
            "observation_prompt_for_reviewer": "Identify who rings the bell and describe the action. If Mikhail is absent or ambiguous, mark FAIL for this candidate.",
        },
        "identity_ambiguity": "HIGH until reviewed: several vlogger-team members may be present; official QA does not name the ringer.",
        "shortcut_risk": "MEDIUM: if Mikhail is visually distinctive in the bell clip alone, Fact A may be unnecessary.",
        "status": "PENDING_HUMAN_REVIEW",
    },
    {
        "candidate_id": "VG-003",
        "video_id": "TJR1oYDDTwg",
        "video_type": "story_animation",
        "prior_complete_comp_qa": False,
        "selection_reason": "Story video unused by v3 Unseen compositions; prince can be identified via an embrace event, then checked in a later action window not labeled as prince-action in official QA.",
        "bridge_entity": "Prince",
        "fact_A": {
            "content": "After the king talks to the green dragon, the person who embraces the king is the Prince.",
            "time": "05:15-05:30",
            "source": "OFFICIAL_QA",
            "related_official_uids": ["257"],
            "official_time_reference": "05:18-05:22",
            "context_pad_seconds": 3.0,
        },
        "fact_B": {
            "content": "CANDIDATE VIDEO OBSERVATION (unverified): shortly after the prince saves the green dragon from the net, the prince performs a concrete follow-up action (not the later instrument performance).",
            "time": "13:05-13:35",
            "source": "VIDEO_OBSERVATION_CANDIDATE",
            "related_official_uids": ["266", "267"],
            "related_official_note": "UID 266 identifies who saves the dragon; UID 267 identifies who grasps the villain. Neither is used as a verified prince action label for Fact B.",
            "context_pad_seconds": 2.0,
            "observation_prompt_for_reviewer": "Confirm the prince remains the same character as in Fact A and list any clear action he performs in this window. If only dragons act, mark FAIL.",
        },
        "identity_ambiguity": "MEDIUM: stylized characters; prince vs other human characters must be matched across intervals.",
        "shortcut_risk": "LOW-MEDIUM: the save-scene clip may already imply the prince identity without the embrace fact.",
        "status": "PENDING_HUMAN_REVIEW",
    },
]


def parse_mmss_range(text: str) -> tuple[float, float]:
    start_s, end_s = [part.strip() for part in text.split("-", 1)]

    def one(token: str) -> float:
        parts = token.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        raise ValueError(token)

    return one(start_s), one(end_s)


def format_ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:06.3f}"
    return f"{m:02d}:{s:06.3f}"


def run(cmd: list[str], timeout: float = 180.0) -> None:
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(cmd[-8:])}\n{completed.stderr[-2000:]}"
        )


def probe_duration(path: Path) -> float:
    cmd = [
        str(FFPROBE),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    return float(completed.stdout.strip())


def probe_has_audio(path: Path) -> bool:
    cmd = [
        str(FFPROBE),
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        str(path),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return bool(completed.stdout.strip())


def cut_clip(source: Path, dest: Path, start: float, end: float, has_audio: bool) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.2, end - start)
    preroll = 15.0
    pre = max(0.0, start - preroll)
    fine = start - pre
    cmd = [
        str(FFMPEG),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{pre:.3f}",
        "-i",
        str(source),
        "-ss",
        f"{fine:.3f}",
        "-t",
        f"{duration:.3f}",
        "-map",
        "0:v:0",
        "-vf",
        "scale=960:-2",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "26",
        "-pix_fmt",
        "yuv420p",
    ]
    if has_audio:
        cmd += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "96k"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(dest)]
    run(cmd, timeout=240)
    return {
        "start_seconds": start,
        "end_seconds": end,
        "duration_seconds": round(duration, 3),
        "path": str(dest.relative_to(OUT)),
        "bytes": dest.stat().st_size,
        "audio_retained": has_audio and probe_has_audio(dest),
    }


def write_contact_sheet(clip: Path, dest: Path, video_start: float, n_frames: int = 8) -> dict:
    frame_dir = dest.parent / f"{dest.stem}_frames"
    if frame_dir.exists():
        shutil.rmtree(frame_dir)
    frame_dir.mkdir(parents=True, exist_ok=True)
    clip_dur = probe_duration(clip)
    offsets = [((i + 0.5) / n_frames) * clip_dur for i in range(n_frames)]
    srt = frame_dir / "timestamps.srt"
    lines = []
    for i, off in enumerate(offsets, start=1):
        abs_t = video_start + off
        stamp = format_ts(abs_t)
        # brief subtitle covering the whole clip; each frame burn uses seek
        start = format_ts(off)
        end = format_ts(min(clip_dur, off + max(0.2, clip_dur / n_frames)))
        # SRT clock uses comma
        def srt_clock(sec: float) -> str:
            h = int(sec // 3600)
            m = int((sec % 3600) // 60)
            s = int(sec % 60)
            ms = int(round((sec - int(sec)) * 1000))
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        lines.append(f"{i}\n{srt_clock(off)} --> {srt_clock(min(clip_dur, off + 0.4))}\n{stamp}\n")
    srt.write_text("\n".join(lines), encoding="utf-8")

    burned = FONT.is_file()
    for i, off in enumerate(offsets, start=1):
        out_frame = frame_dir / f"frame_{i:02d}.jpg"
        vf = f"scale=480:-2"
        if burned:
            sub = str(srt).replace("\\", "\\\\").replace(":", "\\:").replace("'", r"\'")
            fonts = str(FONT.parent).replace("\\", "\\\\").replace(":", "\\:")
            style = (
                "FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,"
                "OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=0,Alignment=8,MarginV=12"
            )
            vf = f"scale=480:-2,subtitles={sub}:fontsdir={fonts}:force_style='{style}'"
        cmd = [
            str(FFMPEG),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{off:.3f}",
            "-i",
            str(clip),
            "-frames:v",
            "1",
            "-vf",
            vf,
            "-q:v",
            "4",
            str(out_frame),
        ]
        run(cmd, timeout=60)

    cols = 4
    rows = int(math.ceil(n_frames / cols))
    cmd = [
        str(FFMPEG),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-start_number",
        "1",
        "-i",
        str(frame_dir / "frame_%02d.jpg"),
        "-frames:v",
        "1",
        "-vf",
        f"tile={cols}x{rows}:nb_frames={n_frames}:padding=4:margin=4:color=black",
        "-q:v",
        "4",
        str(dest),
    ]
    run(cmd, timeout=60)
    return {
        "path": str(dest.relative_to(OUT)),
        "bytes": dest.stat().st_size,
        "n_frames": n_frames,
        "timestamp_burn_in": burned,
        "frame_dir": str(frame_dir.relative_to(OUT)),
        "absolute_timestamps": [format_ts(video_start + off) for off in offsets],
    }


def load_official_qa(video_id: str, uids: list[str]) -> list[dict]:
    wanted = {str(u) for u in uids}
    for line in META.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec["key"] != video_id:
            continue
        out = []
        for qa in rec["qa"]:
            if str(qa["uid"]) in wanted:
                out.append(
                    {
                        "uid": str(qa["uid"]),
                        "question": qa["question"],
                        "answer": qa["answer"],
                        "time_reference": qa.get("time_reference"),
                        "question_type": qa.get("question_type"),
                    }
                )
        return out
    return []


def extract_fact_media(video: Path, fact: dict, dest_dir: Path, label: str, has_audio: bool) -> dict:
    start, end = parse_mmss_range(fact["time"])
    pad = float(fact.get("context_pad_seconds", 5.0))
    vid_dur = probe_duration(video)
    win_start = max(0.0, start - pad)
    win_end = min(vid_dur, end + pad)
    clip_path = dest_dir / f"{label}_clip.mp4"
    sheet_path = dest_dir / f"{label}_contact_sheet.jpg"
    clip_meta = cut_clip(video, clip_path, win_start, win_end, has_audio=has_audio)
    sheet_meta = write_contact_sheet(clip_path, sheet_path, win_start)
    return {
        "label": label,
        "requested_time": fact["time"],
        "extracted_window": f"{format_ts(win_start)}-{format_ts(win_end)}",
        "source": fact["source"],
        "content": fact["content"],
        "related_official_uids": fact.get("related_official_uids", []),
        "related_official_note": fact.get("related_official_note"),
        "observation_prompt_for_reviewer": fact.get("observation_prompt_for_reviewer"),
        "clip": clip_meta,
        "contact_sheet": sheet_meta,
    }


def build_zip(manifest: dict, zip_path: Path) -> dict:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("review_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        zf.writestr("REPORT.md", (OUT / "REPORT.md").read_text(encoding="utf-8"))
        zf.writestr("evidence_candidates.jsonl", (OUT / "evidence_candidates.jsonl").read_text(encoding="utf-8"))
        zf.writestr("video_selection.csv", (OUT / "video_selection.csv").read_text(encoding="utf-8"))
        for cand in manifest["candidates"]:
            cid = cand["candidate_id"]
            base = MEDIA / cid
            # package clip + contact sheet + official QA note; skip raw frame dumps to save space
            for rel in [
                f"local_media/{cid}/official_qa.json",
                f"local_media/{cid}/candidate_notes.json",
                f"local_media/{cid}/fact_A_clip.mp4",
                f"local_media/{cid}/fact_A_contact_sheet.jpg",
                f"local_media/{cid}/fact_B_clip.mp4",
                f"local_media/{cid}/fact_B_contact_sheet.jpg",
            ]:
                path = OUT / rel
                if path.is_file():
                    zf.write(path, arcname=rel)
    return {"path": str(zip_path.relative_to(ROOT)), "bytes": zip_path.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    out = args.output_dir
    media = out / "local_media"
    media.mkdir(parents=True, exist_ok=True)

    if not FFMPEG.is_file() or not FFPROBE.is_file():
        raise SystemExit(f"ffmpeg/ffprobe missing under {FFMPEG.parent}")

    rows = []
    selection = []
    manifest_cands = []

    for cand in CANDIDATES:
        vid = cand["video_id"]
        source = VIDEO_DIR / f"{vid}.mp4"
        if not source.is_file():
            selection.append(
                {
                    "video_id": vid,
                    "video_type": cand["video_type"],
                    "planned": "SELECTED",
                    "status": "VIDEO_MISSING",
                    "reason": cand["selection_reason"],
                }
            )
            continue

        dest = media / cand["candidate_id"]
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        has_audio = probe_has_audio(source)
        fact_a_media = extract_fact_media(source, cand["fact_A"], dest, "fact_A", has_audio)
        fact_b_media = extract_fact_media(source, cand["fact_B"], dest, "fact_B", has_audio)

        uids = sorted(
            set(cand["fact_A"].get("related_official_uids", []))
            | set(cand["fact_B"].get("related_official_uids", []))
        )
        official = load_official_qa(vid, uids)
        (dest / "official_qa.json").write_text(json.dumps(official, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        notes = {
            "candidate_id": cand["candidate_id"],
            "composition_schema_target": "identify_person + query_action",
            "bridge_entity": cand["bridge_entity"],
            "identity_ambiguity": cand["identity_ambiguity"],
            "shortcut_risk": cand["shortcut_risk"],
            "status": cand["status"],
            "note": "Evidence preparation only. Not a formal QA item. Not SUPPORTED.",
            "official_vs_observation": {
                "fact_A_source": cand["fact_A"]["source"],
                "fact_B_source": cand["fact_B"]["source"],
            },
        }
        (dest / "candidate_notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        row = {
            "candidate_id": cand["candidate_id"],
            "video_id": vid,
            "video_type": cand["video_type"],
            "prior_complete_comp_qa": cand["prior_complete_comp_qa"],
            "bridge_entity": cand["bridge_entity"],
            "fact_A_content": cand["fact_A"]["content"],
            "fact_A_time": cand["fact_A"]["time"],
            "fact_A_source": cand["fact_A"]["source"],
            "fact_A_related_official_uids": cand["fact_A"].get("related_official_uids", []),
            "fact_B_content": cand["fact_B"]["content"],
            "fact_B_time": cand["fact_B"]["time"],
            "fact_B_source": cand["fact_B"]["source"],
            "fact_B_related_official_uids": cand["fact_B"].get("related_official_uids", []),
            "fact_B_related_official_note": cand["fact_B"].get("related_official_note"),
            "identity_ambiguity": cand["identity_ambiguity"],
            "shortcut_risk": cand["shortcut_risk"],
            "status": cand["status"],
            "media": {
                "fact_A": fact_a_media,
                "fact_B": fact_b_media,
                "official_qa_path": str((dest / "official_qa.json").relative_to(out)),
                "notes_path": str((dest / "candidate_notes.json").relative_to(out)),
            },
            "selection_reason": cand["selection_reason"],
        }
        rows.append(row)
        selection.append(
            {
                "video_id": vid,
                "video_type": cand["video_type"],
                "candidate_id": cand["candidate_id"],
                "prior_complete_comp_qa": cand["prior_complete_comp_qa"],
                "planned_split_note": "evidence_only_no_split",
                "status": "EXTRACTED_PENDING_REVIEW",
                "reason": cand["selection_reason"],
                "fact_A_source": cand["fact_A"]["source"],
                "fact_B_source": cand["fact_B"]["source"],
            }
        )
        manifest_cands.append(
            {
                "candidate_id": cand["candidate_id"],
                "video_id": vid,
                "video_type": cand["video_type"],
                "bridge_entity": cand["bridge_entity"],
                "status": cand["status"],
                "fact_A_window": fact_a_media["extracted_window"],
                "fact_B_window": fact_b_media["extracted_window"],
                "fact_A_clip": fact_a_media["clip"]["path"],
                "fact_B_clip": fact_b_media["clip"]["path"],
                "fact_A_contact_sheet": fact_a_media["contact_sheet"]["path"],
                "fact_B_contact_sheet": fact_b_media["contact_sheet"]["path"],
                "official_qa": "local_media/" + cand["candidate_id"] + "/official_qa.json",
                "reviewer_prompt_fact_B": cand["fact_B"].get("observation_prompt_for_reviewer"),
                "do_not_mark_supported_automatically": True,
            }
        )

    out.mkdir(parents=True, exist_ok=True)
    with (out / "evidence_candidates.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    with (out / "video_selection.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "video_id",
            "video_type",
            "candidate_id",
            "prior_complete_comp_qa",
            "planned_split_note",
            "status",
            "reason",
            "fact_A_source",
            "fact_B_source",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(selection)

    report = f"""# Video-Grounded Composition Evidence Pilot

本轮只做视频证据准备，不生成正式 Compositional QA，不标记 SUPPORTED，不跑 RSI。

## 选择的视频

| ID | video_id | 类型 | 是否已有完整组合 QA |
|---|---|---|---|
| VG-001 | JTa_Ue2MSwc | talk_show_interview | yes（已知 Sierra 鞋/掌掴种子） |
| VG-002 | _T2Avd3tFHc | travel_vlog | no |
| VG-003 | TJR1oYDDTwg | story_animation | no |

## 候选跨事件关系

共尝试 **{len(rows)}** 组 `identify_person + query_action` 候选。

- VG-001 Fact A = 官方第一位受访者 Sierra；Fact B = Kindall 上场区间的 Sierra 动作候选（视频观察，未核实）。
- VG-002 Fact A = 官方老人 Mikhail；Fact B = 敲钟片段中是否为 Mikhail 及其动作（视频观察，未核实）。
- VG-003 Fact A = 官方拥抱国王的 Prince；Fact B = 救龙之后 Prince 的后续动作候选（视频观察，未核实）。

## Fact B 是否来自官方 QA

三组 Fact B 均标记为 `VIDEO_OBSERVATION_CANDIDATE`。相关官方 UID 仅作定位线索，**不作为已核实动作标签**。

## 捷径与歧义

见 `evidence_candidates.jsonl` 中的 `identity_ambiguity` / `shortcut_risk`。均需人工看片，不可自动 SUPPORTED。

## 媒体

- 目录：`research_audit/lvbench_compositional/video_grounded_pilot/local_media/`（gitignored）
- 上传包：`local_media/lvbench_video_grounded_3videos.zip`

这不是正式 Benchmark 数据。
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")

    manifest = {
        "phase": "video_grounded_evidence_pilot",
        "composition_schema_target": "identify_person + query_action",
        "baseline_commit": "ecf25c3214ef6f386023fe4ffb16f5e553810adb",
        "n_videos_attempted": len(CANDIDATES),
        "n_candidates_extracted": len(rows),
        "auto_supported": False,
        "candidates": manifest_cands,
        "review_instructions": [
            "Watch Fact A and Fact B clips independently.",
            "Decide whether Fact A uniquely identifies the bridge entity.",
            "Decide whether Fact B shows a concrete action by the same entity.",
            "Record SINGLE_CLIP_SHORTCUT_RISK if Fact B alone answers the would-be question.",
            "Do not mark SUPPORTED unless both facts are visually confirmed.",
            "Do not invent actions from plot memory if the clip is unclear.",
        ],
    }
    (out / "review_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    zip_meta = build_zip(manifest, media / "lvbench_video_grounded_3videos.zip")
    manifest["zip"] = zip_meta
    (out / "review_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # append zip info into REPORT
    report += f"\n## 证据包\n\n- zip: `{zip_meta['path']}`\n- size_bytes: {zip_meta['bytes']} ({zip_meta['bytes']/1e6:.1f} MB)\n"
    (out / "REPORT.md").write_text(report, encoding="utf-8")

    print(
        json.dumps(
            {
                "candidates": len(rows),
                "zip_mb": round(zip_meta["bytes"] / 1e6, 2),
                "zip": zip_meta["path"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
