"""B6 — concentrated human/ChatGPT review packets (8–12 QAs)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_packet(
    *,
    run_id: str,
    prioritized: list[dict[str, Any]],
    drafts_by_id: dict[str, dict[str, Any]],
    screened_by_id: dict[str, dict[str, Any]],
    events_by_id: dict[str, dict[str, Any]],
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for p in prioritized:
        qa = drafts_by_id[p["qa_id"]]
        sc = screened_by_id[p["qa_id"]]
        facts = []
        for fid in qa.get("fact_ids") or []:
            ev = events_by_id.get(fid)
            if not ev:
                continue
            facts.append(
                {
                    "event_id": fid,
                    "time_start_s": ev["time_start_s"],
                    "time_end_s": ev["time_end_s"],
                    "event_type": ev.get("event_type"),
                    "summary_zh": ev.get("summary_zh"),
                    "evidence_paths": ev.get("evidence_paths"),
                    "source": ev.get("source"),
                }
            )
        items.append(
            {
                "priority": p["priority"],
                "qa_id": qa["qa_id"],
                "video_id": qa["video_id"],
                "mechanism": qa.get("mechanism"),
                "auto_grade": sc["grade"],
                "auto_score": sc["score"],
                "risks": sc.get("risks"),
                "question_zh": qa.get("question_zh"),
                "question_en": qa.get("question_en"),
                "answer_status": qa.get("answer_status"),
                "provisional_answer_zh": qa.get("provisional_answer_zh"),
                "provisional_answer_note": "Hidden during blind review if following blind protocol",
                "required_windows": qa.get("required_windows"),
                "facts": facts,
                "proxy_necessity": sc.get("necessity_proxy"),
                "data_partition_status": "UNASSIGNED",
                "formal_supported": False,
                "reviewer_fields": {
                    "verdict": None,
                    "answer_ok": None,
                    "necessity_ok": None,
                    "notes": None,
                },
            }
        )

    packet = {
        "packet_id": f"{run_id}_human_batch_01",
        "run_id": run_id,
        "n_items": len(items),
        "protocol": [
            "Blind: do not reveal provisional_answer until after attempting QA from clips",
            "Judge: answer correctness, evidence sufficiency, A/B necessity (proxy then human)",
            "Do not mark SUPPORTED; only funnel progress toward HUMAN_VERIFIED / CANDIDATE_POOL",
            "Uncertain QAs stay UNCERTAIN — do not block the batch",
        ],
        "items": items,
        "data_partition_status": "UNASSIGNED",
        "formal_supported": False,
    }

    (out_dir / "human_review_packet.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Markdown for ChatGPT / human batch review
    lines = [
        f"# Human Review Packet — {packet['packet_id']}",
        "",
        f"Items: {len(items)} | partition: UNASSIGNED | formal_supported: false",
        "",
        "## Protocol",
        "- Blind answer attempt before reading provisional_answer_zh",
        "- Do not promote to SUPPORTED",
        "- Uncertain QAs may remain UNCERTAIN without blocking the batch",
        "",
    ]
    for it in items:
        lines.extend(
            [
                f"## [{it['priority']}] {it['qa_id']} — {it['video_id']}",
                f"- mechanism: `{it['mechanism']}`",
                f"- auto: `{it['auto_grade']}` score={it['auto_score']}",
                f"- risks: {it.get('risks')}",
                f"- Q(zh): {it['question_zh']}",
                f"- windows: {it.get('required_windows')}",
                f"- facts: {', '.join(f['event_id'] for f in it['facts'])}",
                f"- provisional_answer_zh: ||{it.get('provisional_answer_zh')}||",
                "- reviewer: verdict= / answer_ok= / necessity_ok= / notes=",
                "",
            ]
        )
    (out_dir / "human_review_packet.md").write_text("\n".join(lines), encoding="utf-8")
    return packet
