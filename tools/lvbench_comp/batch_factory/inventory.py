"""B1 — video inventory for DEV_CONSTRUCTION pool."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

FFPROBE = os.environ.get(
    "LVBENCH_FFPROBE",
    "/home/descfly/.cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffprobe",
)
DEFAULT_VIDEO_ROOT = Path("/home/descfly/lpy/dataset/LVBench/videos")


def _sha256_file(path: Path, limit_mb: float = 32.0) -> str:
    """Partial checksum for large files (first N MB) + size for stability without full read."""
    h = hashlib.sha256()
    size = path.stat().st_size
    h.update(f"size:{size}|".encode())
    with path.open("rb") as f:
        remain = int(limit_mb * 1024 * 1024)
        while remain > 0:
            chunk = f.read(min(1024 * 1024, remain))
            if not chunk:
                break
            h.update(chunk)
            remain -= len(chunk)
    return h.hexdigest()


def _duration(path: Path) -> float | None:
    if not Path(FFPROBE).exists():
        return None
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        return float(out.stdout.strip()) if out.stdout.strip() else None
    except Exception:
        return None


def load_pool_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    rows = []
    with manifest_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def build_inventory(
    manifest_path: Path,
    *,
    pool: str = "DEV_CONSTRUCTION",
    max_videos: int | None = 12,
    video_root: Path = DEFAULT_VIDEO_ROOT,
) -> list[dict[str, Any]]:
    rows = load_pool_manifest(manifest_path)
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("pool") != pool:
            continue
        vid = row["construction_video_id"]
        media = video_root / f"{vid}.mp4"
        status = "OK"
        dur = None
        checksum = None
        if not media.exists():
            status = "MEDIA_UNAVAILABLE"
        else:
            dur = _duration(media)
            try:
                checksum = _sha256_file(media)
            except Exception:
                checksum = None
                status = "CHECKSUM_FAILED"
        out.append(
            {
                "video_id": vid,
                "pool": pool,
                "not_sealed_final": bool(row.get("not_sealed_final", True)),
                "media_path": str(media) if media.exists() else None,
                "media_status": status,
                "duration_s": dur,
                "checksum_partial_sha256": checksum,
                "github_seed_assets": row.get("github_visible_assets") or [],
                "previously_exposed": True,  # construction pool videos are DEV_EXPOSED
                "source_pack": row.get("source_pack"),
                "genre_guess": _genre_guess(vid),
            }
        )
        if max_videos is not None and len(out) >= max_videos:
            break
    return out


def _genre_guess(video_id: str) -> str:
    known = {
        "T1yhBv1ytzw": "football_broadcast",
        "VTCDQYYKA9o": "table_tennis",
        "Z86xysw5Ncc": "athletics",
        "JPPMz8fEml0": "documentary_travel",
        "QWXlvx1GoTY": "tech_talk",
        "S8vPx-u9p_A": "unlabeled_lvbench",
        "iA_69g87Ilw": "unlabeled_lvbench",
        "hROKtPqktO8": "unlabeled_lvbench",
    }
    return known.get(video_id, "unknown")
