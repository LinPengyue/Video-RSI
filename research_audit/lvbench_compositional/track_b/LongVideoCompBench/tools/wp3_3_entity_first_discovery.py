#!/usr/bin/env python3
"""Prospective entity/event-first candidate discovery (WP3.3 P3).

Pipeline:
  Video Evidence → Entity/Event Anchors → Distant Matching → Relation Proposal → QA Feasibility

This is NOT retrospective reranking of histogram-first pairs.

Without local semantic models (torch/clip/ultralytics unavailable), anchors are
ENGINEERING PROXIES (within-window stability + appearance fingerprint matching)
plus Human/GPT-assisted visual adjudication. Do not claim fully automated
semantic entity discovery.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DS_ROOT, REPO_ROOT, utc_now, write_json  # noqa: E402
from wp3_wave_production import (  # noqa: E402
    COARSE_STEP_S,
    FFMPEG,
    FFPROBE,
    MAX_PAIRS_PER_VIDEO,
    MIN_PAIR_GAP_S,
    ROI_WINDOW_S,
    VIDEO_ROOT,
    RoiSpec,
    _make_pair,
    extract_gray_hist,
    extract_roi_frames,
    ffprobe_duration,
    hist_l1,
    maybe_extract_clip,
    copy_review_subset,
    partial_sha256,
    run_cmd,
)

WP3 = DS_ROOT / "wp3_production"
METHOD_ID = "ENTITY_EVENT_FIRST_STABILITY_PROXY_V1"
MODEL_STACK = {
    "semantic_vision_model": None,
    "reason": "torch/clip/ultralytics/PIL/cv2 not available in runtime",
    "engineering_proxy": "ffmpeg_gray_hist_stability_and_fingerprint_match",
    "human_gpt_assisted_adjudication_required": True,
    "must_not_claim": "FULLY_AUTOMATED_SEMANTIC_ENTITY_DISCOVERY",
}


@dataclass
class Anchor:
    t: float
    thrash: float
    brightness: float
    fingerprint: list[int]
    anchor_score: float
    priority_penalty: str | None


def _brightness(hist: list[int]) -> float:
    # Approximate mean gray from 16-bin hist (bin centers 8,24,...,248)
    total = sum(hist) or 1
    acc = 0.0
    for i, c in enumerate(hist):
        acc += c * ((i << 4) + 8)
    return acc / total


def _window_stats(media: Path, center: float, work: Path) -> Anchor | None:
    """Within-window thrash + fingerprint at center (entity-stability proxy)."""
    offsets = (-3.0, 0.0, 3.0)
    hists: list[list[int]] = []
    for off in offsets:
        t = max(1.0, center + off)
        h = extract_gray_hist(media, t, work / f"_ef_{center:.1f}_{off}.raw")
        if h is None:
            return None
        hists.append(h)
    thrash = sum(hist_l1(hists[i], hists[j]) for i in range(3) for j in range(i + 1, 3)) / 3.0
    bright = sum(_brightness(h) for h in hists) / 3.0
    penalty = None
    if bright < 28.0:
        penalty = "UNDEREXPOSED"
    elif thrash > 0.55:
        penalty = "WITHIN_WINDOW_SUBJECT_THRASH"
    # Prefer stable, adequately lit windows
    score = (1.0 - min(1.0, thrash)) * (1.0 if 28.0 <= bright <= 230.0 else 0.25)
    if penalty:
        score *= 0.15
    return Anchor(
        t=round(center, 3),
        thrash=round(thrash, 6),
        brightness=round(bright, 3),
        fingerprint=hists[1],
        anchor_score=round(score, 6),
        priority_penalty=penalty,
    )


def discover_pairs_entity_first(
    video_id: str, media: Path, duration: float, work: Path
) -> tuple[list[tuple[RoiSpec, RoiSpec]], dict[str, Any]]:
    """Independent entity/event-first discovery (not histogram peak pairing).

    Selects low-thrash anchors, then pairs distant windows with high fingerprint
    similarity (continuity hypothesis), unlike histogram-first which prefers
    high scene-change peaks.
    """
    work.mkdir(parents=True, exist_ok=True)
    times: list[float] = []
    t = 5.0
    while t < duration - 5.0:
        times.append(t)
        t += COARSE_STEP_S
    if len(times) > 80:
        step = len(times) / 80.0
        times = [times[int(i * step)] for i in range(80)]

    anchors: list[Anchor] = []
    for tt in times:
        a = _window_stats(media, tt, work)
        if a is not None:
            anchors.append(a)

    usable = [a for a in anchors if a.priority_penalty is None]
    if len(usable) < 4:
        usable = sorted(anchors, key=lambda x: -x.anchor_score)[:8]

    usable = sorted(usable, key=lambda x: -x.anchor_score)[:16]
    candidates: list[tuple[float, float, float, float, float]] = []
    # score, gap, sim, t_a, t_b
    for i, a in enumerate(usable):
        for b in usable[i + 1 :]:
            gap = abs(b.t - a.t)
            if gap < MIN_PAIR_GAP_S:
                continue
            sim = 1.0 - min(1.0, hist_l1(a.fingerprint, b.fingerprint))
            # Entity-first: reward appearance continuity across distance
            score = sim * 2.0 + min(gap, 1500.0) / 1500.0 + 0.5 * (a.anchor_score + b.anchor_score)
            early, late = (a.t, b.t) if a.t < b.t else (b.t, a.t)
            candidates.append((score, gap, sim, early, late))
    candidates.sort(reverse=True)

    pairs: list[tuple[RoiSpec, RoiSpec]] = []
    used: list[float] = []
    pair_meta: list[dict[str, Any]] = []
    for score, gap, sim, early, late in candidates:
        if any(abs(early - u) < 90 or abs(late - u) < 90 for u in used):
            continue
        pairs.append(
            _make_pair(video_id, early, late, score=score, pair_idx=len(pairs))
        )
        # Rewrite pair_id namespace to avoid colliding with histogram PAIR ids
        e, l = pairs[-1]
        pid = f"{video_id}_EF_PAIR{len(pairs)}"
        e.pair_id = pid
        l.pair_id = pid
        e.roi_id = f"{pid}_EARLY_{int(e.t_start)}_{int(e.t_end)}"
        l.roi_id = f"{pid}_LATE_{int(l.t_start)}_{int(l.t_end)}"
        used.extend([early, late])
        pair_meta.append(
            {
                "pair_id": pid,
                "early_t": early,
                "late_t": late,
                "gap_s": round(gap, 3),
                "fingerprint_similarity": round(sim, 6),
                "discovery_score": round(score, 6),
                "method": METHOD_ID,
            }
        )
        if len(pairs) >= MAX_PAIRS_PER_VIDEO:
            break

    diagnostics = {
        "method": METHOD_ID,
        "model_stack": MODEL_STACK,
        "n_coarse_samples": len(times),
        "n_anchors_computed": len(anchors),
        "n_usable_anchors": len(usable),
        "n_pairs": len(pairs),
        "pair_meta": pair_meta,
        "top_anchor_penalties": Counterish(anchors),
    }
    return pairs, diagnostics


def Counterish(anchors: list[Anchor]) -> dict[str, int]:
    out: dict[str, int] = {"OK": 0, "UNDEREXPOSED": 0, "WITHIN_WINDOW_SUBJECT_THRASH": 0}
    for a in anchors:
        key = a.priority_penalty or "OK"
        out[key] = out.get(key, 0) + 1
    return out


def fingerprint_overlap(
    hist_pair_centers: list[tuple[float, float]],
    ef_pair_centers: list[tuple[float, float]],
    tol: float = 45.0,
) -> list[dict[str, Any]]:
    """Dedup overlapping pairs across methods (same windows ≈ same relation)."""
    dups = []
    for i, (a0, a1) in enumerate(hist_pair_centers):
        for j, (b0, b1) in enumerate(ef_pair_centers):
            if abs(a0 - b0) <= tol and abs(a1 - b1) <= tol:
                dups.append(
                    {
                        "histogram_pair_index": i,
                        "entity_first_pair_index": j,
                        "centers": {"hist": [a0, a1], "ef": [b0, b1]},
                        "action": "DEDUP_COUNT_ONCE",
                    }
                )
    return dups


def self_check() -> dict[str, Any]:
    """Lightweight unit self-check without video I/O."""
    assert METHOD_ID.startswith("ENTITY_EVENT_FIRST")
    assert MODEL_STACK["semantic_vision_model"] is None
    assert MODEL_STACK["human_gpt_assisted_adjudication_required"] is True
    # Similarity preference differs from change preference
    h1 = [10] * 16
    h2 = [10] * 16
    h3 = [0] * 16
    h3[0] = 160
    assert hist_l1(h1, h2) < hist_l1(h1, h3)
    return {"ok": True, "method": METHOD_ID, "model_stack": MODEL_STACK}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--video-id")
    args = ap.parse_args()
    if args.self_check:
        print(json.dumps(self_check(), indent=2))
        return 0
    if not args.video_id:
        raise SystemExit("need --self-check or --video-id")
    media = VIDEO_ROOT / f"{args.video_id}.mp4"
    dur = ffprobe_duration(media)
    if dur is None:
        raise SystemExit("no duration")
    work = WP3 / "_work_ef" / args.video_id
    pairs, diag = discover_pairs_entity_first(args.video_id, media, dur, work)
    out = {
        "video_id": args.video_id,
        "pairs": [
            {
                "pair_id": a.pair_id,
                "early": asdict(a),
                "late": asdict(b),
            }
            for a, b in pairs
        ],
        "diagnostics": diag,
        "built_utc": utc_now(),
    }
    write_json(WP3 / "entity_first_discovery" / f"{args.video_id}.json", out)
    print(json.dumps({"n_pairs": len(pairs), "diag_keys": list(diag)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
