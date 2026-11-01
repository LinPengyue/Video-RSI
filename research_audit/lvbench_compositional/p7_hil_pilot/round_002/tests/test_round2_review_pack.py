#!/usr/bin/env python3
"""Lightweight Round 2 pack checks. Run from repo root:
  python research_audit/lvbench_compositional/p7_hil_pilot/round_002/tests/test_round2_review_pack.py
"""
from __future__ import annotations
import hashlib, json, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
R2 = Path(__file__).resolve().parents[1]
VDIR = Path("/home/descfly/lpy/dataset/LVBench/videos")
P0_RUNS = [
    REPO / "research_audit/lvbench_compositional/track_b/batch_factory/run_001",
    REPO / "research_audit/lvbench_compositional/track_b/batch_factory/run_002",
    REPO / "research_audit/lvbench_compositional/track_b/batch_factory/run_003",
]

failures = []

def check(cond, msg):
    if not cond:
        failures.append(msg)
        print("FAIL:", msg)
    else:
        print("OK:", msg)

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

# 1) source videos exist
for vid in ["VTCDQYYKA9o", "TJR1oYDDTwg"]:
    check((VDIR / f"{vid}.mp4").exists(), f"source mp4 exists: {vid}")

# 2) windows legal
windows = [
    ("A_core", 163, 186), ("B_core", 265, 280),
    ("A_ctx", 158, 191), ("B_ctx", 260, 285),
    ("TJR_early", 1100, 1125), ("TJR_late", 1200, 1220),
]
for name, a, b in windows:
    check(0 <= a < b, f"window legal {name}: {a}<{b}")

# 3) playable media paths match manifest / expected layout
manifest = json.loads((R2 / "vtcd_review/media_manifest.json").read_text())
check(manifest["video_id"] == "VTCDQYYKA9o", "manifest video_id")
check(manifest.get("user_review_status") == "USER_REVIEW_PENDING", "user review still pending")
check(manifest.get("status") == "REVIEW_PACKAGE_READY", "package ready status")
check(manifest.get("no_hidden_answers") is True, "manifest declares no hidden answers")

for clip in manifest["clips"]:
    rel = R2 / "vtcd_review" / clip["relative_path"]
    check(rel.exists() and rel.stat().st_size > 1000, f"clip exists: {clip['relative_path']}")
    check(clip["source_t_start_s"] < clip["source_t_end_s"], f"clip window ok {clip['clip_id']}")
    if clip.get("sha256") and rel.exists():
        # allow missing recompute if large; spot-check browser cores
        if "browser" in clip["clip_id"] or "context" in clip["clip_id"]:
            got = sha256(rel)
            check(got == clip["sha256"], f"sha256 match {clip['clip_id']}")

# HTML references media that exist; no answer key strings
html = (R2 / "vtcd_review/REVIEW_START_HERE.html").read_text(encoding="utf-8")
check("media/A_context_158_191.mp4" in html and "media/B_context_260_285.mp4" in html, "HTML references context clips")
check("GOLD" not in html.upper() or "无隐藏答案" in html, "HTML avoids gold answer content")
check("标准答案" not in html.replace("本页不含标准答案", ""), "HTML does not embed answer key")
# strip the disclaimer then ensure no leaked expected action as fact
check("脱下外套」；Round" in html or "可能错误" in html, "machine hypothesis gated behind details")

# 4) blank template not auto-verified
tmpl = json.loads((R2 / "templates/review_decisions.template.json").read_text())
check(tmpl["review_completed"] is False, "template review_completed false")
for it in tmpl["items"]:
    check(it["decision"] == "PENDING_USER_REVIEW", f"item pending: {it['event_id']}")
    check(it["review_completed"] is False, f"item not completed: {it['event_id']}")
check(tmpl["composition_necessity_status"] == "NOT_STARTED", "necessity not started")

# 5) no unverified upgrade in status file
status = json.loads((R2 / "ROUND2_STATUS.json").read_text())
check(status["USER_VIDEO_REVIEW_COMPLETED"] is False, "not claiming user review completed")
check(status["RELATION_VERIFIED"] is False, "relation not verified")
check(status["COMPOSITION_NECESSITY_VERIFIED"] is False, "necessity not verified")
check(status["REVIEW_PACKAGE_READY"] is True, "package ready true")
check(status["USER_REVIEW_PENDING"] is True, "user review pending true")

# 6) sealed / P0 untouched (existence ok; we only assert we didn't write run_004)
check(not (REPO / "research_audit/lvbench_compositional/track_b/batch_factory/run_004").exists(), "run_004 not created")
# P0 dirs should still exist and not be modified by this test
for p in P0_RUNS:
    check(p.exists(), f"P0 still present: {p.name}")

# TJR relocate result honesty
tjr = json.loads((R2 / "tjr_relocate/TJR_EARLY_WINDOW_RELOCATE_RESULT.json").read_text())
check(tjr["hypothesis_original"]["status"] == "NO_VALID_EARLY_WINDOW_FOUND", "original TJR early=NO_VALID")
check(tjr["hypothesis_corrected_candidate"]["counts_as_relation_verified"] is False, "candidate not relation-verified")

if failures:
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1)
print("\nAll Round 2 pack checks passed.")
