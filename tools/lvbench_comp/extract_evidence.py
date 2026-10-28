#!/usr/bin/env python3
"""Extract local video evidence for LVBench-Compositional phase 1.

This tool reads official LVBench metadata, cuts audio-backed clips with
ffmpeg, and writes keyframes plus a contact sheet. It does not call a video
model or an LLM, and it does not decide whether a compositional item is valid.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


PHASE = "lvbench-compositional-phase1-evidence"
COMPOSITION_VALIDITY = "NOT_ASSESSED"
DEFAULT_MEDIA_REL = Path("research_audit/lvbench_compositional/phase1/local_media")
FRAME_MIN = 8
FRAME_MAX = 12
DEFAULT_FRAMES = 10
DEFAULT_CONTEXT_SECONDS = 20.0
POINT_STRICT_SECONDS = 1.0
SEEK_PREROLL_SECONDS = 20.0
DURATION_TOLERANCE_SECONDS = 0.5
BOUNDS_EPSILON_SECONDS = 0.05

REVIEW_COLUMNS = [
    "candidate_id",
    "video_id",
    "source_uids",
    "source_time_references",
    "candidate_dependency",
    "candidate_question",
    "candidate_answer",
    "evidence_a_required",
    "evidence_b_required",
    "single_segment_shortcut",
    "entity_identity_consistent",
    "answer_unambiguous",
    "composition_signature",
    "unseen_split_feasible",
    "visual_verification_status",
    "review_decision",
]
PENDING_FIELDS = [
    "candidate_question",
    "candidate_answer",
    "evidence_a_required",
    "evidence_b_required",
    "single_segment_shortcut",
    "entity_identity_consistent",
    "answer_unambiguous",
    "visual_verification_status",
    "review_decision",
]
UNKNOWN_FIELDS = [
    "composition_signature",
    "unseen_split_feasible",
]
FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
]
FFPROBE_CACHE = Path.home() / ".cache" / "lvbench-comp" / "ffprobe"

_MMSS = re.compile(r"^(\d+):([0-5]\d(?:\.\d+)?)$")
_HHMMSS = re.compile(r"^(\d+):([0-5]\d):([0-5]\d(?:\.\d+)?)$")
_VIDEO_ID = re.compile(r"^[-A-Za-z0-9_]+$")


class EvidenceError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def parse_timestamp(token: str) -> float:
    """Parse MM:SS or HH:MM:SS. Minutes may exceed 59 in the two-field form."""
    text = token.strip()
    if not text or text.lower() == "none":
        raise EvidenceError(
            "time_parse_error",
            f"Unparseable timestamp {token!r}. Expected MM:SS or HH:MM:SS.",
        )
    matched = _HHMMSS.fullmatch(text)
    if matched:
        hours, minutes, seconds = matched.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    matched = _MMSS.fullmatch(text)
    if matched:
        minutes, seconds = matched.groups()
        return int(minutes) * 60 + float(seconds)
    raise EvidenceError(
        "time_parse_error",
        f"Unparseable timestamp {token!r}. Expected MM:SS or HH:MM:SS.",
    )


def parse_time_reference(reference: str) -> tuple[float, float]:
    if not isinstance(reference, str):
        raise EvidenceError(
            "time_parse_error",
            f"time_reference must be a string, got {type(reference).__name__}.",
        )
    text = reference.strip()
    if "–" in text or "—" in text:
        raise EvidenceError(
            "time_parse_error",
            f"time_reference {reference!r} uses a non-ASCII dash. Expected START-END.",
        )
    if text.count("-") != 1:
        raise EvidenceError(
            "time_parse_error",
            f"time_reference {reference!r} must contain one START-END interval.",
        )
    left, right = text.split("-")
    start = parse_timestamp(left)
    end = parse_timestamp(right)
    if end < start:
        raise EvidenceError(
            "time_range_inverted",
            f"time_reference {reference!r} ends before it starts "
            f"({start:.3f}s > {end:.3f}s).",
            {"start_seconds": start, "end_seconds": end},
        )
    return start, end


def format_timestamp(seconds: float) -> str:
    if seconds < 0 or not math.isfinite(seconds):
        raise EvidenceError("time_parse_error", f"Cannot format timestamp {seconds!r}.")
    total_ms = int(round(seconds * 1000))
    whole, millis = divmod(total_ms, 1000)
    hours, rem = divmod(whole, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_metadata(path: Path) -> list[dict]:
    if not path.is_file():
        raise EvidenceError("metadata_missing", f"Metadata file not found: {path}")
    records = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise EvidenceError(
                    "metadata_parse_error",
                    f"{path}:{lineno}: {exc}",
                ) from exc
    if not records:
        raise EvidenceError("metadata_parse_error", f"Metadata file is empty: {path}")
    return records


def index_records(records: list[dict]) -> tuple[dict[str, dict], dict[str, list[str]]]:
    by_video: dict[str, dict] = {}
    uid_videos: dict[str, list[str]] = {}
    for record in records:
        video_id = str(record.get("key", ""))
        if video_id in by_video:
            raise EvidenceError(
                "duplicate_video_id",
                f"Metadata contains duplicate video id {video_id}.",
            )
        by_video[video_id] = record
        seen_here: set[str] = set()
        for qa in record.get("qa") or []:
            uid = str(qa.get("uid", ""))
            if uid in seen_here:
                raise EvidenceError(
                    "duplicate_uid",
                    f"UID {uid} is repeated inside video {video_id}.",
                )
            seen_here.add(uid)
            uid_videos.setdefault(uid, []).append(video_id)
    for uid, videos in uid_videos.items():
        if len(videos) != 1:
            raise EvidenceError(
                "duplicate_uid",
                f"UID {uid} appears on multiple videos: {', '.join(videos)}.",
            )
    return by_video, uid_videos


def validate_video_id(video_id: str) -> str:
    if not isinstance(video_id, str) or not _VIDEO_ID.fullmatch(video_id):
        raise EvidenceError(
            "invalid_video_id",
            f"Video id {video_id!r} is not a single LVBench key.",
        )
    return video_id


def official_qa(record: dict, uid: str) -> dict:
    for qa in record.get("qa") or []:
        if str(qa.get("uid")) == uid:
            return qa
    raise EvidenceError("uid_not_in_metadata", f"UID {uid} is not on this video.")


def match_case(records: list[dict], video_id: str, uids: list[str]) -> dict:
    validate_video_id(video_id)
    if not uids:
        raise EvidenceError("uid_missing", "At least one UID is required.")
    normalized = [str(uid).strip() for uid in uids]
    if any(not uid for uid in normalized):
        raise EvidenceError("uid_missing", "UID list contains an empty id.")
    by_video, uid_videos = index_records(records)
    record = by_video.get(video_id)
    if record is None:
        raise EvidenceError(
            "video_id_not_in_metadata",
            f"Video id {video_id} is not in the metadata. Case stopped.",
        )
    mismatches = []
    selected = []
    for uid in normalized:
        owners = uid_videos.get(uid, [])
        if owners != [video_id]:
            mismatches.append(
                {
                    "uid": uid,
                    "requested_video_id": video_id,
                    "actual_video_ids": owners,
                }
            )
            continue
        selected.append(official_qa(record, uid))
    if mismatches:
        rendered = []
        for item in mismatches:
            owners = item["actual_video_ids"]
            if owners:
                where = "belongs to " + ", ".join(owners)
            else:
                where = "does not appear in this metadata file"
            rendered.append(f"UID {item['uid']} {where}, not {video_id}")
        raise EvidenceError(
            "uid_video_mismatch",
            "UID and video id do not match. Case stopped. " + "; ".join(rendered) + ".",
            {"mismatches": mismatches},
        )
    return {"record": record, "qas": selected, "uids": normalized}


def assert_official_bounds(uid: str, reference: str, start: float, end: float, duration: float) -> None:
    if start < -BOUNDS_EPSILON_SECONDS or end > duration + BOUNDS_EPSILON_SECONDS:
        raise EvidenceError(
            "time_out_of_bounds",
            (
                f"UID {uid} time_reference {reference} maps to "
                f"{start:.3f}-{end:.3f}s, outside probed duration {duration:.3f}s. "
                "Case stopped."
            ),
            {
                "uid": uid,
                "time_reference": reference,
                "start_seconds": start,
                "end_seconds": end,
                "duration_seconds": duration,
            },
        )


def plan_window(
    start: float,
    end: float,
    duration: float,
    *,
    mode: str,
    context_seconds: float,
    point_strict_seconds: float,
) -> dict:
    point = abs(end - start) <= 1e-6
    notes = []
    if mode == "context":
        requested_start = start - context_seconds
        requested_end = end + context_seconds
    elif mode == "strict":
        if point:
            requested_start = start
            requested_end = start + point_strict_seconds
            notes.append(
                "Official time_reference has zero duration. "
                f"The strict clip is a {point_strict_seconds:.3f}s decode window "
                "starting at that point, not the official interval."
            )
        else:
            requested_start = start
            requested_end = end
    else:
        raise EvidenceError("internal_error", f"Unknown window mode {mode}.")

    clamped_start = min(max(0.0, requested_start), duration)
    clamped_end = min(max(0.0, requested_end), duration)
    clamps = []
    if clamped_start - requested_start > 1e-3:
        clamps.append("start_clamped_to_0")
    if requested_end - clamped_end > 1e-3:
        clamps.append("end_clamped_to_duration")
    span = clamped_end - clamped_start
    if span < 0.05:
        raise EvidenceError(
            "empty_window",
            f"{mode} window for {start:.3f}-{end:.3f}s is empty after clamping "
            f"to duration {duration:.3f}s.",
            {"mode": mode, "requested_start": requested_start, "requested_end": requested_end},
        )
    return {
        "mode": mode,
        "requested_start_seconds": round(requested_start, 3),
        "requested_end_seconds": round(requested_end, 3),
        "start_seconds": round(clamped_start, 3),
        "end_seconds": round(clamped_end, 3),
        "duration_seconds": round(span, 3),
        "clamps": clamps,
        "notes": notes,
        "point_reference": point,
    }


def windows_overlap(left: dict, right: dict) -> bool:
    return left["start_seconds"] < right["end_seconds"] and right["start_seconds"] < left["end_seconds"]


def discover_repo_root(start: Path) -> Path | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    root = completed.stdout.strip()
    return Path(root) if root else None


def path_is_gitignored(repo_root: Path, path: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "check-ignore", "-q", "--", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def ensure_output_untracked(output_dir: Path, repo_root: Path | None) -> None:
    """Refuse to write clips or images into a path Git would track."""
    if repo_root is None:
        return
    output_dir = output_dir.resolve()
    repo_root = repo_root.resolve()
    try:
        output_dir.relative_to(repo_root)
    except ValueError:
        return
    probes = [
        output_dir / "clip.mp4",
        output_dir / "frame.jpg",
        output_dir / "contact_sheet.png",
    ]
    ignored = [path_is_gitignored(repo_root, probe) for probe in probes]
    if not all(ignored):
        raise EvidenceError(
            "output_not_gitignored",
            "Refusing to write video or contact-sheet files into a Git-tracked path: "
            f"{output_dir}. Use {DEFAULT_MEDIA_REL} or a directory outside the repository.",
            {"output_dir": str(output_dir)},
        )


def resolve_tool(explicit: Path | None, env_name: str, executable: str, extra: list[Path]) -> Path:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit))
    env_value = os.environ.get(env_name)
    if env_value:
        candidates.append(Path(env_value))
    found = shutil.which(executable)
    if found:
        candidates.append(Path(found))
    if executable == "ffmpeg":
        try:
            import imageio_ffmpeg  # type: ignore

            candidates.append(Path(imageio_ffmpeg.get_ffmpeg_exe()))
        except Exception:
            pass
    candidates.extend(extra)
    seen = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise EvidenceError(
        f"{executable}_missing",
        f"{executable} was not found. Pass --{executable} or set {env_name}.",
    )


def resolve_font(explicit: Path | None) -> Path | None:
    if explicit is not None:
        path = Path(explicit)
        if not path.is_file():
            raise EvidenceError("font_missing", f"Font not found: {path}")
        return path
    for candidate in FONT_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def tool_version(binary: Path) -> str:
    completed = subprocess.run(
        [str(binary), "-version"],
        check=False,
        capture_output=True,
        text=True,
    )
    text = completed.stdout or completed.stderr
    return text.splitlines()[0] if text else ""


def run_command(command: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr or ""
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        raise EvidenceError(
            "ffmpeg_failed",
            f"Command timed out after {timeout:.0f}s: {command[0]}",
            {"command": command, "stderr": stderr[-4000:], "timeout_seconds": timeout},
        ) from exc


def probe_media(ffprobe: Path, path: Path, timeout: float) -> dict:
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    completed = run_command(command, timeout)
    if completed.returncode != 0 or not completed.stdout.strip():
        stderr = (completed.stderr or "").strip()
        raise EvidenceError(
            "ffprobe_failed",
            f"ffprobe failed for {path}. {stderr}".strip(),
            {"command": command, "stderr": stderr[-4000:], "returncode": completed.returncode},
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise EvidenceError(
            "ffprobe_failed",
            f"ffprobe did not return JSON for {path}: {exc}",
            {"stdout": completed.stdout[-2000:]},
        ) from exc
    streams = payload.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    if video is None:
        raise EvidenceError("ffprobe_failed", f"ffprobe found no video stream in {path}.")
    format_info = payload.get("format") or {}
    try:
        duration = float(format_info.get("duration") or video.get("duration"))
    except (TypeError, ValueError) as exc:
        raise EvidenceError(
            "ffprobe_failed",
            f"ffprobe did not report a duration for {path}.",
        ) from exc
    if not math.isfinite(duration) or duration <= 0:
        raise EvidenceError("ffprobe_failed", f"Invalid probed duration {duration!r} for {path}.")
    rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
    fps = _parse_rate(rate)
    return {
        "duration_seconds": duration,
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": fps,
        "fps_raw": rate,
        "codec": video.get("codec_name"),
        "has_audio": any(item.get("codec_type") == "audio" for item in streams),
        "tool": "ffprobe",
        "ffprobe": str(ffprobe),
    }


def _parse_rate(rate: str) -> float | None:
    if not rate or rate == "0/0":
        return None
    if "/" in str(rate):
        num, den = str(rate).split("/", 1)
        try:
            denominator = float(den)
            if denominator == 0:
                return None
            return float(num) / denominator
        except ValueError:
            return None
    try:
        return float(rate)
    except ValueError:
        return None


def extract_clip(
    ffmpeg: Path,
    source: Path,
    dest: Path,
    start: float,
    end: float,
    *,
    has_audio: bool,
    timeout: float,
) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    pre = max(0.0, start - SEEK_PREROLL_SECONDS)
    fine = start - pre
    duration = end - start
    command = [
        str(ffmpeg),
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
    ]
    if has_audio:
        command += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "128k"]
    command += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    completed = run_command(command, timeout)
    if completed.returncode != 0 or not dest.is_file():
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise EvidenceError(
            "ffmpeg_failed",
            "ffmpeg failed while cutting "
            f"{format_timestamp(start)}-{format_timestamp(end)}. {stderr}".strip(),
            {
                "command": command,
                "stderr": stderr[-4000:],
                "returncode": completed.returncode,
            },
        )
    return {"command": command, "stderr": (completed.stderr or "").strip()[-2000:]}


def sample_offsets(duration: float, count: int) -> list[float]:
    if count < FRAME_MIN or count > FRAME_MAX:
        raise EvidenceError(
            "invalid_frame_count",
            f"Frame count must be between {FRAME_MIN} and {FRAME_MAX}, got {count}.",
        )
    if duration <= 0:
        raise EvidenceError("empty_window", "Cannot sample frames from an empty window.")
    return [((index + 0.5) / count) * duration for index in range(count)]


def write_keyframes(
    ffmpeg: Path,
    clip: Path,
    frame_dir: Path,
    offsets: list[float],
    video_start: float,
    uid: str,
    font: Path | None,
    timeout: float,
) -> tuple[list[dict], bool]:
    frame_dir.mkdir(parents=True, exist_ok=True)
    burned = font is not None
    frames = []
    for index, offset in enumerate(offsets, 1):
        video_time = video_start + offset
        stamp = format_timestamp(video_time)
        path = frame_dir / f"frame_{index:02d}.jpg"
        label = f"uid={uid}  t={stamp}"
        text_path = frame_dir / f"frame_{index:02d}.txt"
        text_path.write_text(label + "\n", encoding="utf-8")
        srt_path = frame_dir / f"frame_{index:02d}.srt"
        srt_path.write_text(
            "1\n00:00:00,000 --> 01:00:00,000\n" + label + "\n",
            encoding="utf-8",
        )
        command = [
            str(ffmpeg),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(clip),
            "-ss",
            f"{offset:.3f}",
            "-frames:v",
            "1",
        ]
        if font is not None:
            command += ["-vf", _subtitle_filter(font, srt_path)]
        command += ["-q:v", "3", str(path)]
        completed = run_command(command, timeout)
        if completed.returncode != 0 or not path.is_file():
            stderr = (completed.stderr or completed.stdout or "").strip()
            raise EvidenceError(
                "ffmpeg_failed",
                f"ffmpeg failed while writing keyframe {index} at {stamp}. {stderr}".strip(),
                {"command": command, "stderr": stderr[-4000:], "returncode": completed.returncode},
            )
        frames.append(
            {
                "index": index,
                "clip_offset_seconds": round(offset, 3),
                "video_timestamp_seconds": round(video_time, 3),
                "video_timestamp": stamp,
                "path": str(path),
                "timestamp_burn_in": burned,
            }
        )
    return frames, burned


def _subtitle_filter(font: Path, srt_path: Path) -> str:
    """Burn a timestamp with libass. This ffmpeg build has no drawtext filter."""
    subtitle = _filter_path(srt_path)
    fonts = _filter_path(font.parent)
    style = (
        "FontName=DejaVu Sans,FontSize=22,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=0,"
        "Alignment=8,MarginV=16"
    )
    return f"subtitles={subtitle}:fontsdir={fonts}:force_style='{style}'"


def _filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", r"\'")


def write_contact_sheet(ffmpeg: Path, frame_dir: Path, count: int, dest: Path, timeout: float) -> None:
    columns = 4
    rows = int(math.ceil(count / columns))
    command = [
        str(ffmpeg),
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
        f"tile={columns}x{rows}:nb_frames={count}:padding=4:margin=4:color=black",
        "-q:v",
        "3",
        str(dest),
    ]
    completed = run_command(command, timeout)
    if completed.returncode != 0 or not dest.is_file():
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise EvidenceError(
            "ffmpeg_failed",
            f"ffmpeg failed while writing the contact sheet. {stderr}".strip(),
            {"command": command, "stderr": stderr[-4000:], "returncode": completed.returncode},
        )


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def extract_window_media(
    *,
    ffmpeg: Path,
    ffprobe: Path,
    source: Path,
    window: dict,
    dest_dir: Path,
    uid: str,
    has_audio: bool,
    frames: int,
    font: Path | None,
    timeout: float,
    output_root: Path,
) -> dict:
    dest_dir.mkdir(parents=True, exist_ok=True)
    clip = dest_dir / "clip.mp4"
    sheet = dest_dir / "contact_sheet.jpg"
    frame_dir = dest_dir / "frames"
    cut = extract_clip(
        ffmpeg,
        source,
        clip,
        window["start_seconds"],
        window["end_seconds"],
        has_audio=has_audio,
        timeout=timeout,
    )
    clip_probe = probe_media(ffprobe, clip, timeout)
    requested = window["end_seconds"] - window["start_seconds"]
    delta = abs(clip_probe["duration_seconds"] - requested)
    if delta > DURATION_TOLERANCE_SECONDS:
        raise EvidenceError(
            "clip_duration_mismatch",
            (
                f"UID {uid} {window['mode']} clip duration is "
                f"{clip_probe['duration_seconds']:.3f}s; requested {requested:.3f}s."
            ),
            {"probe": clip_probe, "requested_duration_seconds": requested},
        )
    if has_audio and not clip_probe["has_audio"]:
        raise EvidenceError(
            "ffmpeg_failed",
            f"UID {uid} {window['mode']} clip dropped the source audio.",
            {"probe": clip_probe},
        )
    offsets = sample_offsets(clip_probe["duration_seconds"], frames)
    keyframes, burned = write_keyframes(
        ffmpeg,
        clip,
        frame_dir,
        offsets,
        window["start_seconds"],
        uid,
        font,
        timeout,
    )
    write_contact_sheet(ffmpeg, frame_dir, frames, sheet, timeout)
    for frame in keyframes:
        frame["path"] = _rel(Path(frame["path"]), output_root)
    return {
        **window,
        "status": "extracted",
        "clip_path": _rel(clip, output_root),
        "clip_sha256": sha256_file(clip),
        "clip_probe": clip_probe,
        "duration_error_seconds": round(delta, 3),
        "seek": {
            "mode": "hybrid_preroll_then_accurate_trim",
            "preroll_seconds": SEEK_PREROLL_SECONDS,
        },
        "audio_retained": bool(clip_probe["has_audio"]),
        "timestamp_burn_in": burned,
        "timestamp_method": "libass_subtitles" if burned else None,
        "contact_sheet": _rel(sheet, output_root),
        "keyframes": keyframes,
        "ffmpeg_stderr": cut["stderr"],
    }


def _base_result(video_id: str, uids: list[str], metadata_path: Path, video_root: Path) -> dict:
    return {
        "phase": PHASE,
        "composition_validity": COMPOSITION_VALIDITY,
        "review_fields_written": False,
        "ok": False,
        "case_status": "error",
        "media_extracted": False,
        "error_code": None,
        "message": "",
        "video_id": video_id,
        "uids": [str(uid) for uid in uids],
        "metadata_path": str(metadata_path),
        "video_root": str(video_root),
        "details": {},
        "segments": [],
    }


def _fail(result: dict, exc: EvidenceError) -> dict:
    result["ok"] = False
    result["case_status"] = "missing_video" if exc.code == "missing_video" else "error"
    result["media_extracted"] = False
    result["error_code"] = exc.code
    result["message"] = exc.message
    result["details"] = exc.details
    result["composition_validity"] = COMPOSITION_VALIDITY
    return result


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def segment_from_qa(video_id: str, qa: dict, parsed: tuple[float, float] | None, parse_error: str | None) -> dict:
    segment = {
        "video_id": video_id,
        "uid": str(qa.get("uid")),
        "question": qa.get("question"),
        "question_type": qa.get("question_type"),
        "answer": qa.get("answer"),
        "time_reference": qa.get("time_reference"),
        "official_qa": qa,
        "extractions": [],
    }
    if parsed is not None:
        start, end = parsed
        segment["start_seconds"] = round(start, 3)
        segment["end_seconds"] = round(end, 3)
        segment["point_reference"] = abs(end - start) <= 1e-6
    if parse_error:
        segment["time_parse_error"] = parse_error
    return segment


def extract_case(
    *,
    video_id: str,
    uids: list[str],
    metadata_path: Path,
    video_root: Path,
    output_dir: Path,
    context_seconds: float = DEFAULT_CONTEXT_SECONDS,
    frames: int = DEFAULT_FRAMES,
    ffmpeg: Path | None = None,
    ffprobe: Path | None = None,
    font: Path | None = None,
    repo_root: Path | None = None,
    point_strict_seconds: float = POINT_STRICT_SECONDS,
    include_strict: bool = True,
    timeout_seconds: float = 1800,
) -> dict:
    metadata_path = Path(metadata_path)
    video_root = Path(video_root)
    output_dir = Path(output_dir)
    result = _base_result(video_id, uids, metadata_path, video_root)
    result["context_seconds"] = context_seconds
    result["frames"] = frames
    output_allowed = False
    try:
        if context_seconds < 0:
            raise EvidenceError("invalid_context", "Context seconds must be >= 0.")
        if frames < FRAME_MIN or frames > FRAME_MAX:
            raise EvidenceError(
                "invalid_frame_count",
                f"Frame count must be between {FRAME_MIN} and {FRAME_MAX}, got {frames}.",
            )
        if repo_root is None:
            repo_root = discover_repo_root(Path.cwd())
        ensure_output_untracked(output_dir, repo_root)
        output_allowed = True
        records = load_metadata(metadata_path)
        result["metadata_sha256"] = sha256_file(metadata_path)
        matched = match_case(records, video_id, uids)
        record = matched["record"]
        result["video_info"] = record.get("video_info")
        parsed_segments = []
        for qa in matched["qas"]:
            reference = qa.get("time_reference")
            try:
                parsed = parse_time_reference(reference)
                parsed_segments.append((qa, parsed, None))
            except EvidenceError as exc:
                parsed_segments.append((qa, None, exc.message))
                result["segments"].append(segment_from_qa(video_id, qa, None, exc.message))
                raise EvidenceError(
                    exc.code,
                    f"UID {qa.get('uid')} time_reference {reference!r}: {exc.message} Case stopped.",
                    exc.details,
                ) from exc
            result["segments"].append(segment_from_qa(video_id, qa, parsed, None))

        video_path = video_root / f"{video_id}.mp4"
        result["video_path"] = str(video_path)
        result["video_exists"] = video_path.is_file()
        if not video_path.is_file():
            raise EvidenceError(
                "missing_video",
                f"Video file is missing: {video_path}. Metadata for this case was recorded. "
                "No clip was marked extracted.",
                {"video_path": str(video_path)},
            )

        ffprobe_bin = resolve_tool(ffprobe, "LVBENCH_FFPROBE", "ffprobe", [FFPROBE_CACHE])
        ffmpeg_bin = resolve_tool(ffmpeg, "LVBENCH_FFMPEG", "ffmpeg", [])
        font_path = resolve_font(font)
        if font_path is None:
            raise EvidenceError(
                "font_missing",
                "No font was found for timestamp burn-in. Pass --font.",
            )
        result["tools"] = {
            "ffmpeg": str(ffmpeg_bin),
            "ffmpeg_version": tool_version(ffmpeg_bin),
            "ffprobe": str(ffprobe_bin),
            "ffprobe_version": tool_version(ffprobe_bin),
            "font": str(font_path) if font_path else None,
        }
        probe = probe_media(ffprobe_bin, video_path, timeout_seconds)
        result["probe"] = probe
        result["video_sha256"] = sha256_file(video_path)
        result["video_size_bytes"] = video_path.stat().st_size
        minutes = (record.get("video_info") or {}).get("duration_minutes")
        if isinstance(minutes, (int, float)):
            result["metadata_duration_seconds"] = float(minutes) * 60
            result["probe_minus_metadata_seconds"] = round(
                probe["duration_seconds"] - float(minutes) * 60,
                3,
            )
        for segment in result["segments"]:
            assert_official_bounds(
                segment["uid"],
                segment["time_reference"],
                segment["start_seconds"],
                segment["end_seconds"],
                probe["duration_seconds"],
            )

        plans = []
        for segment in result["segments"]:
            modes = ["context"]
            if include_strict:
                modes.append("strict")
            segment_plans = []
            for mode in modes:
                plan = plan_window(
                    segment["start_seconds"],
                    segment["end_seconds"],
                    probe["duration_seconds"],
                    mode=mode,
                    context_seconds=context_seconds,
                    point_strict_seconds=point_strict_seconds,
                )
                plan["uid"] = segment["uid"]
                segment_plans.append(plan)
            plans.append(segment_plans)
        result["window_overlaps"] = _overlap_report(plans)

        case_dir = output_dir / video_id
        for segment, segment_plans in zip(result["segments"], plans):
            for plan in segment_plans:
                media = extract_window_media(
                    ffmpeg=ffmpeg_bin,
                    ffprobe=ffprobe_bin,
                    source=video_path,
                    window=plan,
                    dest_dir=case_dir / f"uid_{segment['uid']}" / plan["mode"],
                    uid=segment["uid"],
                    has_audio=bool(probe["has_audio"]),
                    frames=frames,
                    font=font_path,
                    timeout=timeout_seconds,
                    output_root=output_dir,
                )
                segment["extractions"].append(media)
        result["ok"] = True
        result["case_status"] = "extracted"
        result["media_extracted"] = True
        result["message"] = (
            "Clips and contact sheets were written. "
            "composition_validity remains NOT_ASSESSED."
        )
    except EvidenceError as exc:
        _fail(result, exc)
    if output_allowed and isinstance(video_id, str) and _VIDEO_ID.fullmatch(video_id):
        _write_json(output_dir / video_id / "case_result.json", result)
    return result


def _overlap_report(plans: list[list[dict]]) -> list[dict]:
    flat = [plan for segment_plans in plans for plan in segment_plans]
    overlaps = []
    for index, left in enumerate(flat):
        for right in flat[index + 1 :]:
            if left["mode"] != right["mode"] or left["uid"] == right["uid"]:
                continue
            if windows_overlap(left, right):
                overlaps.append(
                    {
                        "mode": left["mode"],
                        "uids": [left["uid"], right["uid"]],
                        "overlap_start_seconds": round(max(left["start_seconds"], right["start_seconds"]), 3),
                        "overlap_end_seconds": round(min(left["end_seconds"], right["end_seconds"]), 3),
                    }
                )
    return overlaps


def source_qa_rows(result: dict) -> list[dict]:
    rows = []
    if result.get("error_code") in {"uid_video_mismatch", "video_id_not_in_metadata", "uid_missing"}:
        return rows
    for segment in result.get("segments") or []:
        qa = segment.get("official_qa")
        if not qa:
            continue
        rows.append(
            {
                "video_id": result.get("video_id"),
                "video_info": result.get("video_info"),
                "video_path": result.get("video_path"),
                "video_exists": result.get("video_exists"),
                "qa": qa,
            }
        )
    return rows


def merge_audit(audit_dir: Path, result: dict) -> None:
    audit_dir.mkdir(parents=True, exist_ok=True)
    qa_path = audit_dir / "source_qa.jsonl"
    existing_qa = []
    if qa_path.is_file():
        existing_qa = [
            json.loads(line)
            for line in qa_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    fresh = {(row["video_id"], str(row["qa"]["uid"])): row for row in source_qa_rows(result)}
    merged_qa = []
    seen = set()
    for row in existing_qa:
        key = (row.get("video_id"), str((row.get("qa") or {}).get("uid")))
        if key in fresh:
            merged_qa.append(fresh[key])
            seen.add(key)
        else:
            merged_qa.append(row)
    for key, row in fresh.items():
        if key not in seen:
            merged_qa.append(row)
    qa_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in merged_qa),
        encoding="utf-8",
    )

    manifest_path = audit_dir / "evidence_manifest.json"
    manifest = {
        "phase": PHASE,
        "composition_validity": COMPOSITION_VALIDITY,
        "note": (
            "Extraction status only. Video-dependent review fields are not decided here "
            "and must stay PENDING or UNKNOWN until a person watches the clips."
        ),
        "cases": [],
    }
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["phase"] = PHASE
        manifest["composition_validity"] = COMPOSITION_VALIDITY
    public = _public_case(result)
    cases = [item for item in manifest.get("cases", []) if item.get("video_id") != result.get("video_id")]
    cases.append(public)
    manifest["cases"] = cases
    _write_json(manifest_path, manifest)


def _public_case(result: dict) -> dict:
    hidden = {"official_qa"}
    segments = []
    for segment in result.get("segments") or []:
        copied = {key: value for key, value in segment.items() if key not in hidden}
        segments.append(copied)
    exported = dict(result)
    exported["segments"] = segments
    return exported


def build_review_csv(metadata_path: Path, seed_rows: list[dict], dest: Path) -> None:
    records = load_metadata(Path(metadata_path))
    by_video, _uid_videos = index_records(records)
    table = []
    for seed in seed_rows:
        video_id = validate_video_id(str(seed["video_id"]))
        uids = [str(uid) for uid in seed["source_uids"]]
        record = by_video.get(video_id)
        if record is None:
            raise EvidenceError(
                "video_id_not_in_metadata",
                f"Candidate {seed.get('candidate_id')} video {video_id} is not in metadata.",
            )
        references = []
        for uid in uids:
            owners = [key for key, item in by_video.items() if any(str(qa.get("uid")) == uid for qa in item.get("qa") or [])]
            if owners != [video_id]:
                raise EvidenceError(
                    "uid_video_mismatch",
                    f"Candidate {seed.get('candidate_id')} UID {uid} does not belong to {video_id}.",
                    {"uid": uid, "actual_video_ids": owners, "requested_video_id": video_id},
                )
            qa = official_qa(record, uid)
            reference = qa.get("time_reference")
            parse_time_reference(reference)
            references.append(str(reference))
        dependency = str(seed.get("candidate_dependency") or "").strip()
        if not dependency:
            raise EvidenceError(
                "candidate_seed_invalid",
                f"Candidate {seed.get('candidate_id')} is missing candidate_dependency.",
            )
        row = {column: "" for column in REVIEW_COLUMNS}
        row["candidate_id"] = str(seed["candidate_id"])
        row["video_id"] = video_id
        row["source_uids"] = "|".join(uids)
        row["source_time_references"] = "|".join(references)
        row["candidate_dependency"] = dependency
        for field in PENDING_FIELDS:
            row[field] = "PENDING"
        for field in UNKNOWN_FIELDS:
            row[field] = "UNKNOWN"
        table.append(row)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(table)


def _load_seed(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise EvidenceError("candidate_seed_invalid", "Candidate seed must be a JSON list.")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract LVBench compositional phase-1 video evidence.")
    parser.add_argument("--video-id")
    parser.add_argument("--uids", help="Comma-separated official UIDs.")
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--video-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--audit-dir", type=Path)
    parser.add_argument("--context-seconds", type=float, default=DEFAULT_CONTEXT_SECONDS)
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--ffprobe", type=Path)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=1800)
    parser.add_argument("--write-review-csv", action="store_true")
    parser.add_argument("--candidate-seed", type=Path)
    parser.add_argument("--review-csv", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.write_review_csv:
            if not args.metadata or not args.candidate_seed or not args.review_csv:
                raise EvidenceError(
                    "arguments",
                    "--write-review-csv requires --metadata, --candidate-seed, and --review-csv.",
                )
            build_review_csv(args.metadata, _load_seed(args.candidate_seed), args.review_csv)
            print(json.dumps({"ok": True, "review_csv": str(args.review_csv), "judgments": "PENDING"}))
            return 0
        missing = [
            name
            for name, value in (
                ("--video-id", args.video_id),
                ("--uids", args.uids),
                ("--metadata", args.metadata),
                ("--video-root", args.video_root),
            )
            if not value
        ]
        if missing:
            raise EvidenceError("arguments", "Missing arguments: " + ", ".join(missing))
        output_dir = args.output_dir
        if output_dir is None:
            root = discover_repo_root(Path.cwd()) or Path.cwd()
            output_dir = root / DEFAULT_MEDIA_REL
        uids = [part.strip() for part in str(args.uids).split(",") if part.strip()]
        result = extract_case(
            video_id=args.video_id,
            uids=uids,
            metadata_path=args.metadata,
            video_root=args.video_root,
            output_dir=output_dir,
            context_seconds=args.context_seconds,
            frames=args.frames,
            ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe,
            font=args.font,
            timeout_seconds=args.timeout_seconds,
        )
        if args.audit_dir is not None:
            merge_audit(args.audit_dir, result)
        summary = {
            "ok": result["ok"],
            "case_status": result["case_status"],
            "error_code": result["error_code"],
            "message": result["message"],
            "video_id": result["video_id"],
            "media_extracted": result["media_extracted"],
            "composition_validity": result["composition_validity"],
        }
        print(json.dumps(summary, ensure_ascii=False))
        return 0 if result["ok"] else 2
    except EvidenceError as exc:
        print(json.dumps({"ok": False, "error_code": exc.code, "message": exc.message}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
