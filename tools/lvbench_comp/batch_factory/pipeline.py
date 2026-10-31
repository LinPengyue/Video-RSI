"""End-to-end Track B batch factory: inventory → events → relations → QA → screen → packets."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from . import EXTRACTOR_VERSION, __version__
from .auto_screen import prioritize_for_human, screen_batch
from .dedup import n_distinct_questions
from .extract_events import extract_for_video
from .human_packets import build_packet
from .inventory import build_inventory
from .provenance import annotate_event, count_by_provenance
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
        per = output / "per_video"
        per.mkdir(parents=True, exist_ok=True)
        ev_path = per / f"{vid}_events.jsonl"
        evi_path = per / f"{vid}_evidence.jsonl"
        if resume and status_path.exists() and ev_path.exists() and evi_path.exists():
            st = json.loads(status_path.read_text())
            extract_status.append(st)
            evs = [annotate_event(json.loads(l)) for l in ev_path.read_text().splitlines() if l.strip()]
            evi = [json.loads(l) for l in evi_path.read_text().splitlines() if l.strip()]
            events_by_video[vid] = evs
            events_all.extend(evs)
            evidence_all.extend(evi)
            continue
        decode_t0 = time.time()
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
        decode_s = round(time.time() - decode_t0, 3)
        cached_reuse = sum(
            1
            for e in (result.get("evidence") or [])
            if e.get("kind") == "coarse_scan_frame"
            and Path(str(e.get("path") or "")).exists()
        )
        extract_status.append(
            {
                "video_id": vid,
                "status": result["status"],
                "flags": result.get("flags") or [],
                "n_events": result.get("n_events", len(result.get("events") or [])),
                "n_curated": result.get("n_curated", 0),
                "n_new_semantic": result.get("n_new_semantic", 0),
                "n_coarse": result.get("n_coarse", 0),
                "semantic_extractor_status": result.get("semantic_extractor_status"),
                "decode_or_extract_s": decode_s,
                "n_evidence": len(result.get("evidence") or []),
                "cached_frame_paths_present": cached_reuse,
            }
        )
        status_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(status_path, extract_status[-1])
        evs = [annotate_event(e) for e in (result.get("events") or [])]
        evi = result.get("evidence") or []
        events_by_video[vid] = evs
        events_all.extend(evs)
        evidence_all.extend(evi)
        _write_jsonl(ev_path, evs)
        _write_jsonl(evi_path, evi)

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

    # B6 true-blind human packets (V2 — no A/B leakage in blind variants)
    packet_dir = output / "human_review_packets"
    packet = build_packet(
        run_id=run_id,
        prioritized=prioritized,
        drafts_by_id=drafts_by_id,
        screened_by_id=screened_by_id,
        events_by_id=events_by_id,
        out_dir=packet_dir,
    )

    # B7 metrics (honest provenance split)
    prov = count_by_provenance(events_all)
    grade_counts = Counter(s["grade"] for s in screened)
    mech_counts = Counter(d.get("mechanism") for d in drafts if d.get("retained_as_independent_sample"))
    fam_indep = sum(1 for d in drafts if d.get("retained_as_independent_sample"))
    fam_dup = sum(1 for d in drafts if d.get("duplicate_of_family"))
    n_distinct_q = n_distinct_questions(drafts)
    n_prov_present = sum(
        1 for d in drafts if d.get("provisional_answer_zh") and str(d["provisional_answer_zh"]).upper() != "UNKNOWN"
    )
    n_answer_verified = sum(
        1 for d in drafts if d.get("answer_status") in {"ANSWER_VERIFIED", "HUMAN_VERIFIED"}
    )
    n_new_rel_families = sum(
        1 for d in drafts if d.get("from_new_observation") and d.get("retained_as_independent_sample")
    )
    n_quarantine = sum(1 for d in drafts if d.get("generation_error") or d.get("funnel_level") == "REJECTED_OR_QUARANTINE")
    n_leakage = sum(1 for d in drafts if d.get("leakage_error"))
    videos_ok = sum(1 for s in extract_status if s["status"] in {"OK", "PARTIAL"})
    videos_skip = sum(1 for s in extract_status if s["status"] == "MEDIA_UNAVAILABLE")
    videos_fail = sum(1 for s in extract_status if s["status"] == "EXTRACTION_FAILED")
    genre = Counter(i.get("genre_guess") for i in inventory)
    semantic_events = sum(1 for e in events_all if e.get("verb") not in {"visual_sample", "seed_frame_present"})
    decode_sum = round(sum(float(s.get("decode_or_extract_s") or 0) for s in extract_status), 3)
    tier = prov["by_tier"]
    n_cursor_obs = int(tier.get("CURSOR_FRAME_VISUAL_OBSERVATION", 0))
    n_chatgpt_obs = int(tier.get("CHATGPT_FRAME_OBSERVATION", 0))
    n_model_inf = int(tier.get("AUTOMATIC_SEMANTIC_MODEL_OBSERVATION", 0))
    n_packet = int(packet.get("n_packet_serialized") or packet.get("n_reviewable") or 0)

    metrics = {
        "run_id": run_id,
        "factory_version": __version__,
        "extractor_version": EXTRACTOR_VERSION,
        "elapsed_s": round(time.time() - t0, 2),
        "new_video_decoding_time_s": decode_sum,
        "cost_per_new_candidate_decode_only_s": round(decode_sum / max(1, n_new_rel_families), 3),
        "cost_note": (
            "decode_only: ffmpeg/coarse extract wall time / new families; "
            "excludes Cursor/ChatGPT still interpretation and QA validation time (not instrumented)"
        ),
        "qa_production_time_s": None,
        "review_time_s": None,
        "cached_frame_reuse_note": "coarse frames skipped when file already present in extract_events._extract_frame",
        "videos_processed": videos_ok,
        "videos_skipped_media": videos_skip,
        "videos_extraction_failed": videos_fail,
        "videos_total_inventory": len(inventory),
        "genre_distribution": dict(genre),
        "n_events_total": len(events_all),
        "n_events_semantic": semantic_events,
        "n_total_coarse_frames": prov["n_total_coarse_frames"],
        "n_curated_semantic_events": prov["n_curated_semantic_events"],
        "n_cursor_frame_observations": n_cursor_obs,
        "n_chatgpt_frame_observations": n_chatgpt_obs,
        "n_model_inferred_semantic_events": n_model_inf,
        "n_new_machine_semantic_events": n_model_inf,  # alias: ONLY automatic model, not Cursor stills
        "n_agent_or_human_still_observations": n_cursor_obs + n_chatgpt_obs,
        "human_curated_events_loaded": prov["n_curated_semantic_events"],
        "model_inferred_events": n_model_inf,
        "provenance_by_tier": tier,
        "n_evidence_index": len(evidence_all),
        "n_relations": len(relations),
        "n_qa_drafts": len(drafts),
        "n_distinct_questions": n_distinct_q,
        "n_provisional_answer_present": n_prov_present,
        "n_independently_answer_verified": n_answer_verified,
        "n_answer_known": n_answer_verified,  # corrected: no longer equals provisional text
        "n_independent_evidence_families": fam_indep,
        "n_new_relation_families": n_new_rel_families,
        "n_family_duplicates_flagged": fam_dup,
        "n_quarantine_binding_errors": n_quarantine,
        "n_question_leakage_flagged": n_leakage,
        "duplicate_rate": round(fam_dup / max(1, len(drafts)), 3),
        "auto_grade_counts": dict(grade_counts),
        "mechanism_coverage_independent": dict(mech_counts),
        "n_packet_serialized": n_packet,
        "n_answerable_candidate": int(packet.get("n_answerable_candidate") or 0),
        "n_reviewer_asset_verified": int(packet.get("n_reviewer_asset_verified") or 0),
        "n_continuous_media_reviewable": int(packet.get("n_continuous_media_reviewable") or 0),
        "n_true_blind_evaluated": int(packet.get("n_true_blind_evaluated") or 0),
        "n_formal_blind_ready": int(packet.get("n_formal_blind_ready") or 0),
        "n_human_reviewable": n_packet,  # legacy alias = serialized only
        "n_human_packet_items": n_packet,
        "n_video_verified": 0,
        "human_packet_status": "SERIALIZED_NOT_FORMAL_USER_BATCH",
        "user_formal_blind_batch_authorized": bool(packet.get("user_formal_blind_batch_authorized")),
        "candidate_yield_per_video_independent": round(fam_indep / max(1, videos_ok), 3),
        "new_candidate_yield_per_video": round(n_new_rel_families / max(1, videos_ok), 3),
        "heuristic_high_rate_not_video_tested": round(
            grade_counts.get("HEURISTIC_HIGH_NOT_VIDEO_TESTED", 0) / max(1, len(screened)), 3
        ),
        "data_partition_status": "UNASSIGNED",
        "formal_supported": False,
        "ok_for_expensive_rsi": False,
        "sealed_accessed": False,
        "no_paid_vlm": True,
        "semantic_extractor_status": (
            "BLOCKED_NO_SEMANTIC_EXTRACTOR" if n_model_inf == 0 else "MODEL_AVAILABLE"
        ),
    }
    _write_json(output / "pipeline_metrics.json", metrics)

    report = _render_report(metrics, extract_status, screened, prioritized, drafts)
    (output / "PRODUCTION_AND_QUALITY_REPORT.md").write_text(report, encoding="utf-8")

    return {
        "metrics": metrics,
        "output": str(output),
        "packet_id": packet["packet_id"],
        "n_human_items": n_human,
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
        "## Funnel (not SUPPORTED) — honest provenance",
        f"- Coarse frames: {metrics.get('n_total_coarse_frames')}",
        f"- Curated semantic (fixtures): {metrics.get('n_curated_semantic_events')}",
        f"- Cursor still observations: {metrics.get('n_cursor_frame_observations')} | ChatGPT still: {metrics.get('n_chatgpt_frame_observations')} | **model_inferred**: {metrics.get('n_model_inferred_semantic_events')}",
        f"- Relations: {metrics['n_relations']}",
        f"- QA drafts: {metrics['n_qa_drafts']} | distinct Q: {metrics.get('n_distinct_questions')} | independent families: {metrics['n_independent_evidence_families']} | dup: {metrics['n_family_duplicates_flagged']} | quarantine: {metrics.get('n_quarantine_binding_errors')} | leakage: {metrics.get('n_question_leakage_flagged')}",
        f"- provisional_answer_present: {metrics.get('n_provisional_answer_present')} | independently_answer_verified: {metrics.get('n_independently_answer_verified')}",
        f"- New relation families (from new obs): {metrics.get('n_new_relation_families')}",
        f"- Grades (heuristic, not video-tested): `{metrics['auto_grade_counts']}`",
        f"- Mechanism coverage (independent): `{metrics['mechanism_coverage_independent']}`",
        f"- New-candidate yield / video: {metrics.get('new_candidate_yield_per_video')}",
        f"- cost_per_new_candidate_decode_only_s: {metrics.get('cost_per_new_candidate_decode_only_s')} ({metrics.get('cost_note')})",
        "",
        "## Human review packet",
        f"- packet_serialized: {metrics.get('n_packet_serialized')} | answerable_candidate: {metrics.get('n_answerable_candidate')} | asset_verified: {metrics.get('n_reviewer_asset_verified')} | continuous_media: {metrics.get('n_continuous_media_reviewable')} | formal_blind_ready: {metrics.get('n_formal_blind_ready')} | true_blind_evaluated: {metrics.get('n_true_blind_evaluated')}",
        f"- status: `{metrics['human_packet_status']}` — not a formal user batch while formal_blind_ready=0",
        "",
        "### Priority sample",
    ]
    for p in prioritized[:12]:
        lines.append(
            f"- [{p['priority']}] `{p['qa_id']}` {p['video_id']} `{p['mechanism']}` grade={p['grade']} score={p['score']} new={p.get('from_new_observation')} — {p['reason']}"
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
