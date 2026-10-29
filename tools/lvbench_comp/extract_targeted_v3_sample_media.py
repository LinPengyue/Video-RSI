#!/usr/bin/env python3
"""Extract light contact sheets for targeted_v3 sample-review items.

Does not mark SUPPORTED. Writes under targeted_v3/local_media/ (gitignored).
"""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIR = Path("/home/descfly/lpy/dataset/LVBench/videos")
REVIEW = ROOT / "research_audit/lvbench_compositional/targeted_v3/sample_quality_review.csv"
UNSEEN = ROOT / "research_audit/lvbench_compositional/targeted_v3/unseen_candidates.jsonl"
OUT = ROOT / "research_audit/lvbench_compositional/targeted_v3/local_media"
FFMPEG_CANDIDATES = [
    Path.home() / ".cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffmpeg",
    Path("/usr/bin/ffmpeg"),
]


def resolve_ffmpeg() -> Path:
    for path in FFMPEG_CANDIDATES:
        if path.is_file():
            return path
    try:
        import imageio_ffmpeg  # type: ignore

        return Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"ffmpeg not found: {exc}") from exc


def parse_mmss(text: str) -> float | None:
    text = (text or "").strip()
    if not text or "-" not in text:
        return None
    start = text.split("-", 1)[0].strip()
    parts = start.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        return None
    return None


def grab_frame(ffmpeg: Path, video: Path, t: float, out_path: Path) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(ffmpeg),
        "-y",
        "-ss",
        f"{max(0.0, t):.2f}",
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.returncode == 0 and out_path.is_file()


def main() -> int:
    ffmpeg = resolve_ffmpeg()
    by_id = {}
    for line in UNSEEN.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        by_id[row["question_id"]] = row

    with REVIEW.open(encoding="utf-8", newline="") as handle:
        samples = list(csv.DictReader(handle))

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for sample in samples:
        qid = sample["question_id"]
        row = by_id.get(qid)
        if not row:
            continue
        video = VIDEO_DIR / f"{row['video_id']}.mp4"
        if not video.is_file():
            manifest.append({"question_id": qid, "status": "VIDEO_MISSING"})
            continue
        dest = OUT / row["video_id"] / qid
        dest.mkdir(parents=True, exist_ok=True)
        frames = []
        for label, key in (("A", "evidence_A_time"), ("B", "evidence_B_time")):
            t = parse_mmss(row.get(key, ""))
            if t is None:
                continue
            path = dest / f"fact_{label}_{int(t)}s.jpg"
            ok = grab_frame(ffmpeg, video, t + 1.0, path)
            frames.append({"fact": label, "t": t, "path": str(path.relative_to(ROOT)), "ok": ok})
        manifest.append(
            {
                "question_id": qid,
                "video_id": row["video_id"],
                "status": "FRAMES_EXTRACTED" if any(f["ok"] for f in frames) else "EXTRACT_FAILED",
                "frames": frames,
                "review_status_note": "Frames extracted for human review; not auto-SUPPORTED.",
            }
        )
        (dest / "manifest.json").write_text(json.dumps(manifest[-1], indent=2) + "\n", encoding="utf-8")

    (OUT / "sample_extract_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n": len(manifest), "ok": sum(1 for m in manifest if m.get("status") == "FRAMES_EXTRACTED")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
