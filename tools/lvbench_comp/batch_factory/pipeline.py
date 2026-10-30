"""End-to-end Track B batch factory: inventory → events → relations → QA → screen → packets."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from . import EXTRACTOR_VERSION, __version__
from .auto_screen import prioritize_for_human, screen_batch
from .extract_events import extract_for_video
from .human_packets import build_packet
from .inventory import build_inventory
from .qa_draft import draft_qa
from .relations import mine_relations


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def run_factory(
    *,
    manifest: Path,
    output: Path,
    pool: str = "DEV_CONSTRUCTION",
    max_videos: int = 12,
    resume: bool = False,
    human_k: int = 12,
) -> dict[str, Any]:
    t0 = time.time()
    output.mkdir(parents=True, exist_ok=True)
    run_id = output.name

    # B1 inventory
    inventory = build_inventory(manifest, pool=pool, max_videos=max_videos)
    _write_jsonl(output / "video_inventory.jsonl", inventory)

    events_all: list[dict[str, Any]] = []
    evidence_all: list[dict[str, Any]] = []
    extract_status: list[dict[str, Any]] = []
    events_by_video: dict[str, list[dict[str, Any]]] = {}

    for inv in inventory:
        vid = inv["video_id"]
        status_path = output / "extract_status" / f"{vid}.json"
        if resume and status_path.exists():
            st = json.loads(status_path.read_text())
            extract_status.append(st)
            # reload events if present
            eg = output / "per_video" / f"{vid}_events.jsonl"
            if eg.exists():
                evs = [json.loads(l) for l in eg.read_text().splitlines() if l.strip()]
                events_by_video[vid] = evs
                events_all.extend(evs)
            continue
        try:
            result = extract_for_video(inv, output)
        except Exception as e:  # never block batch
            result = {
                "video_id": vid,
                "status": "EXTRACTION_FAILED",
                "events": [],
                "evidence": [],
                "flags": [f"exception:{type(e).__name__}:{e}"],
                "n_events": 0,
            }
        extract_status.append(
            {
                "video_id": vid,
                "status": result["status"],
                "flags": result.get("flags") or [],
                "n_events": result.get("n_events", len(result.get("events") or [])),
                "n_curated": result.get("n_curated", 0),
                "n_coarse": result.get("n_coarse", 0),
            }
        )
        status_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(status_path, extract_status[-1])
        evs = result.get("events") or []
        events_by_video[vid] = evs
        events_all.extend(evs)
        evidence_all.extend(result.get("evidence") or [])
        per = output / "per_video"
        per.mkdir(parents=True, exist_ok=True)
        _write_jsonl(per / f"{vid}_events.jsonl", evs)

    _write_jsonl(output / "event_graphs.jsonl", events_all)
    _write_jsonl(output / "evidence_index.jsonl", evidence_all)
    _write_jsonl(output / "extract_status.jsonl", extract_status)

    # B3 relations
    relations = mine_relations(events_by_video)
    for r in relations:
        r["funnel_level"] = "RELATION_LINKED"
        r["data_partition_status"] = "UNASSIGNED"
        r["formal_supported"] = False
    _write_jsonl(output / "relation_candidates.jsonl", relations)

    events_by_id = {e["event_id"]: e for e in events_all}

    # B4 QA drafts
    drafts = draft_qa(relations, events_by_id)
    # Attach required windows from intervals
    for d in drafts:
        d["required_windows"] = d.get("time_intervals")
        d["question_en"] = None
    _write_jsonl(output / "qa_drafts.jsonl", drafts)

    # B5 auto screen
    screened = screen_batch(drafts, events_by_id)
    _write_jsonl(output / "qa_auto_screen.jsonl", screened)

    drafts_by_id = {d["qa_id"]: d for d in drafts}
    screened_by_id = {s["qa_id"]: s for s in screened}
    prioritized = prioritize_for_human(screened, drafts_by_id, k=human_k)
    _write_jsonl(output / "review_queue_priority.jsonl", prioritized)

    # B6 human packets
    packet_dir = output / "human_review_packets"
    packet = build_packet(
        run_id=run_id,
        prioritized=prioritized,
        drafts_by_id=drafts_by_id,
        screened_by_id=screened_by_id,
        events_by_id=events_by_id,
        out_dir=packet_dir,
    )
    # Blind variants (same items; answer redacted in B/A only views)
    for variant in ("B_ONLY_BLIND", "A_ONLY_BLIND", "A_PLUS_B_ADJUDICATION"):
        vdir = packet_dir / variant
        vdir.mkdir(parents=True, exist_ok=True)
        items = []
        for it in packet["items"]:
            copy = dict(it)
            if variant != "A_PLUS_B_ADJUDICATION":
                copy["provisional_answer_zh"] = "[REDACTED_FOR_BLIND]"
                copy["answer_status"] = "HIDDEN"
            copy["blind_variant"] = variant
            # Restrict windows hint: B_ONLY shows later windows, A_ONLY earlier
            wins = it.get("required_windows") or []
            if variant == "B_ONLY_BLIND" and len(wins) >= 2:
                copy["visible_windows"] = [wins[-1]]
            elif variant == "A_ONLY_BLIND" and len(wins) >= 1:
                copy["visible_windows"] = [wins[0]]
            else:
                copy["visible_windows"] = wins
            items.append(copy)
        _write_json(
            vdir / "packet.json",
            {
                "packet_id": f"{run_id}_{variant}",
                "variant": variant,
                "n_items": len(items),
                "items": items,
                "data_partition_status": "UNASSIGNED",
                "formal_supported": False,
                "human_status": "PENDING_HUMAN",
            },
        )

    # B7 metrics
    grade_counts = Counter(s["grade"] for s in screened)
    mech_counts = Counter(d.get("mechanism") for d in drafts if d.get("retained_as_independent_sample"))
    fam_indep = sum(1 for d in drafts if d.get("retained_as_independent_sample"))
    fam_dup = sum(1 for d in drafts if d.get("duplicate_of_family"))
    videos_ok = sum(1 for s in extract_status if s["status"] in {"OK", "PARTIAL"})
    videos_skip = sum(1 for s in extract_status if s["status"] == "MEDIA_UNAVAILABLE")
    videos_fail = sum(1 for s in extract_status if s["status"] == "EXTRACTION_FAILED")
    genre = Counter(i.get("genre_guess") for i in inventory)
    curated_events = sum(1 for e in events_all if not str(e["event_id"]).endswith(tuple(f"_coarse_vis_{i}" for i in range(20))) and e.get("verb") != "visual_sample" and e.get("verb") != "seed_frame_present")
    semantic_events = sum(
        1
        for e in events_all
        if e.get("verb") not in {"visual_sample", "seed_frame_present"}
    )

    metrics = {
        "run_id": run_id,
        "factory_version": __version__,
        "extractor_version": EXTRACTOR_VERSION,
        "elapsed_s": round(time.time() - t0, 2),
        "videos_processed": videos_ok,
        "videos_skipped_media": videos_skip,
        "videos_extraction_failed": videos_fail,
        "videos_total_inventory": len(inventory),
        "genre_distribution": dict(genre),
        "n_events_total": len(events_all),
        "n_events_semantic": semantic_events,
        "n_evidence_index": len(evidence_all),
        "n_relations": len(relations),
        "n_qa_drafts": len(drafts),
        "n_independent_evidence_families": fam_indep,
        "n_family_duplicates_flagged": fam_dup,
        "duplicate_rate": round(fam_dup / max(1, len(drafts)), 3),
        "auto_grade_counts": dict(grade_counts),
        "mechanism_coverage_independent": dict(mech_counts),
        "n_human_packet_items": packet["n_items"],
        "human_packet_status": "PENDING_HUMAN",
        "candidate_yield_per_video": round(fam_indep / max(1, videos_ok), 3),
        "auto_high_rate": round(grade_counts.get("AUTO_HIGH", 0) / max(1, len(screened)), 3),
        "data_partition_status": "UNASSIGNED",
        "formal_supported": False,
        "ok_for_expensive_rsi": False,
        "sealed_accessed": False,
    }
    _write_json(output / "pipeline_metrics.json", metrics)

    report = _render_report(metrics, extract_status, screened, prioritized, drafts)
    (output / "PRODUCTION_AND_QUALITY_REPORT.md").write_text(report, encoding="utf-8")

    return {
        "metrics": metrics,
        "output": str(output),
        "packet_id": packet["packet_id"],
        "n_human_items": packet["n_items"],
    }


def _render_report(
    metrics: dict[str, Any],
    extract_status: list[dict[str, Any]],
    screened: list[dict[str, Any]],
    prioritized: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Track B Production & Quality Report — `{metrics['run_id']}`",
        "",
        f"Factory `{metrics['factory_version']}` / extractor `{metrics['extractor_version']}`",
        f"Elapsed: {metrics['elapsed_s']}s | partition: **UNASSIGNED** | formal_supported: **false** | ok_for_expensive_rsi: **false**",
        "",
        "## Throughput",
        f"- Videos inventory: {metrics['videos_total_inventory']}",
        f"- Processed OK/PARTIAL: {metrics['videos_processed']}",
        f"- MEDIA_UNAVAILABLE: {metrics['videos_skipped_media']}",
        f"- EXTRACTION_FAILED: {metrics['videos_extraction_failed']}",
        f"- Genre: `{metrics['genre_distribution']}`",
        "",
        "## Funnel (not SUPPORTED)",
        f"- Events total / semantic: {metrics['n_events_total']} / {metrics['n_events_semantic']}",
        f"- Relations: {metrics['n_relations']}",
        f"- QA drafts: {metrics['n_qa_drafts']} (independent families {metrics['n_independent_evidence_families']}, dup-flagged {metrics['n_family_duplicates_flagged']}, dup rate {metrics['duplicate_rate']})",
        f"- Auto grades: `{metrics['auto_grade_counts']}`",
        f"- Mechanism coverage (independent): `{metrics['mechanism_coverage_independent']}`",
        f"- Candidate yield / processed video: {metrics['candidate_yield_per_video']}",
        f"- AUTO_HIGH rate: {metrics['auto_high_rate']}",
        "",
        "## Human review packet",
        f"- Items prepared: {metrics['n_human_packet_items']} (status `{metrics['human_packet_status']}`)",
        f"- Priority queue does not block further production batches.",
        "",
        "### Priority sample",
    ]
    for p in prioritized[:12]:
        lines.append(
            f"- [{p['priority']}] `{p['qa_id']}` {p['video_id']} `{p['mechanism']}` grade={p['grade']} score={p['score']} — {p['reason']}"
        )
    lines.extend(
        [
            "",
            "## Per-video extract status",
        ]
    )
    for s in extract_status:
        lines.append(f"- `{s['video_id']}`: {s['status']} n_events={s.get('n_events')} flags={s.get('flags')}")
    lines.extend(
        [
            "",
            "## Failure / risk notes (do not block batch)",
            "- Uncertain / ANSWER_PENDING QAs remain in pool with explicit flags.",
            "- Shortcut controls (e.g. heat-boundary text contrast) graded SHORTCUT_CONTROL.",
            "- Audio-required drafts stay UNCERTAIN until audio audited.",
            "- No auto-SUPPORTED; sealed set not accessed; expensive RSI not run.",
            "",
            "## Cost proxy (this run)",
            "- Coarse ffmpeg frame samples ≤12/video (not full 1fps).",
            "- No paid vision/API calls.",
            f"- Human review cost deferred: {metrics['n_human_packet_items']} items PENDING_HUMAN.",
            "",
        ]
    )
    # Failure reason tally from risks
    risk_c: Counter[str] = Counter()
    for s in screened:
        for r in s.get("risks") or []:
            risk_c[r.split(":")[0]] += 1
        for e in s.get("hard_errors") or []:
            risk_c["HARD:" + e.split(":")[0]] += 1
    lines.append(f"Risk/error tallies: `{dict(risk_c)}`")
    lines.append("")
    return "\n".join(lines)
