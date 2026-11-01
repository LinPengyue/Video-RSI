#!/usr/bin/env python3
"""Rebuild Round 2 local playable media (idempotent). Does not touch P0 or sealed."""
from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]  # Video-RSI root from .../round_002/scripts
# path: repo/research_audit/lvbench_compositional/p7_hil_pilot/round_002/scripts
REPO = Path(__file__).resolve().parents[5]
R2 = Path(__file__).resolve().parents[1]
FFMPEG = Path.home() / ".cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffmpeg"
if not FFMPEG.exists():
    FFMPEG = Path(subprocess.check_output(["which", "ffmpeg"], text=True).strip())
VDIR = Path("/home/descfly/lpy/dataset/LVBench/videos")

CLIPS = [
    ("VTCDQYYKA9o", R2 / "vtcd_review/media/A_core_browser_163_186.mp4", 163.0, 186.0),
    ("VTCDQYYKA9o", R2 / "vtcd_review/media/B_core_browser_265_280.mp4", 265.0, 280.0),
    ("VTCDQYYKA9o", R2 / "vtcd_review/media/A_context_158_191.mp4", 158.0, 191.0),
    ("VTCDQYYKA9o", R2 / "vtcd_review/media/B_context_260_285.mp4", 260.0, 285.0),
    ("TJR1oYDDTwg", R2 / "tjr_relocate/media/early_candidate_dragon_ride_1100_1125.mp4", 1100.0, 1125.0),
    ("TJR1oYDDTwg", R2 / "tjr_relocate/media/late_dual_performers_1200_1220.mp4", 1200.0, 1220.0),
]

def extract(vid, out: Path, t0, t1):
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 1000:
        return "exists"
    src = VDIR / f"{vid}.mp4"
    if not src.exists():
        return f"missing_source:{src}"
    dur = t1 - t0
    r = subprocess.run(
        [str(FFMPEG), "-y", "-ss", f"{t0:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return "ok" if r.returncode == 0 and out.exists() else "fail"

def main():
    results = []
    for vid, out, t0, t1 in CLIPS:
        results.append({"video_id": vid, "out": str(out), "t0": t0, "t1": t1, "status": extract(vid, out, t0, t1)})
    print(json.dumps(results, indent=2))
    if any(r["status"] == "fail" or str(r["status"]).startswith("missing") for r in results):
        sys.exit(1)

if __name__ == "__main__":
    main()
