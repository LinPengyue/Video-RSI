"""B6 — true-blind human/ChatGPT review packets (V2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Fields forbidden in B_ONLY / A_ONLY blind serializations
BLIND_FORBIDDEN_KEYS = {
    "provisional_answer_zh",
    "normalized_answer",
    "gold_answer",
    "auto_grade",
    "auto_score",
    "proxy_necessity",
    "proxy_A_only",
    "proxy_B_only",
    "proxy_A_plus_B",
    "necessity_proxy",
    "answer_derivation",
    "risks",
    "fact_binding",
    "generation_error",
}


def _window_side(windows: list | None, side: str) -> list:
    wins = windows or []
    if not wins:
        return []
    if side == "B" and len(wins) >= 2:
        return [wins[-1]]
    if side == "A" and len(wins) >= 1:
        return [wins[0]]
    return list(wins)


def _facts_for_side(facts: list[dict[str, Any]], side: str) -> list[dict[str, Any]]:
    if not facts:
        return []
    if side == "B" and len(facts) >= 2:
        chosen = [facts[-1]]
    elif side == "A":
        chosen = [facts[0]]
    else:
        chosen = facts
    # Strip cross-side leakage: only path + time for this side
    out = []
    for f in chosen:
        out.append(
            {
                "time_start_s": f.get("time_start_s"),
                "time_end_s": f.get("time_end_s"),
                "evidence_paths": f.get("evidence_paths") or [],
                "media_access_state": _media_state(f.get("evidence_paths") or []),
            }
        )
    return out


def _resolve_path(p: str) -> Path | None:
    if not p:
        return None
    cand = [Path(p), Path("/home/descfly/lpy/Video-RSI") / p]
    for c in cand:
        if c.exists():
            return c
    return None


def _media_state(paths: list[str]) -> str:
    ok = 0
    kinds: list[str] = []
    for p in paths:
        rp = _resolve_path(p)
        if rp is None:
            continue
        ok += 1
        suf = rp.suffix.lower()
        if suf in {".mp4", ".mkv", ".webm", ".mov", ".wav", ".mp3"}:
            kinds.append("continuous")
        elif suf in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            kinds.append("still")
        else:
            kinds.append("other")
    if not paths:
        return "NO_ASSET_PATH"
    if ok == 0:
        return "ASSETS_MISSING"
    if ok < len(paths):
        return "PARTIAL_ASSETS"
    if kinds and all(k == "still" for k in kinds):
        return "STILL_PATHS_EXIST_NOT_CONTINUOUS_VIDEO"
    if "continuous" in kinds:
        return "CONTINUOUS_MEDIA_PATH_EXISTS"
    return "PATHS_EXIST_STILLS_OR_CLIPS"


def classify_review_readiness(qa: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any]:
    """Strict gates — path presence ≠ human-review-ready Benchmark QA."""
    paths: list[str] = []
    for f in facts:
        paths.extend(f.get("evidence_paths") or [])
    state = _media_state(paths)
    has_prov = bool(qa.get("provisional_answer_zh")) and (qa.get("provisional_answer_zh") or "").upper() != "UNKNOWN"
    answer_verified = qa.get("answer_status") in {"ANSWER_VERIFIED", "HUMAN_VERIFIED"}
    audio_needed = "audio_required" in (qa.get("uncertainty") or [])
    leakage = (qa.get("question_leakage") or {}).get("ok", True)
    continuous = state == "CONTINUOUS_MEDIA_PATH_EXISTS"
    still_only = state == "STILL_PATHS_EXIST_NOT_CONTINUOUS_VIDEO"
    answerable_candidate = (
        has_prov
        and not qa.get("generation_error")
        and not qa.get("leakage_error")
        and leakage
        and qa.get("answer_status") == "ANSWER_PENDING"
        and not audio_needed
    )
    # Asset verified only if continuous media exists and was explicitly checked playable
    # Stills alone never set reviewer_asset_verified=true for formal blind video review
    reviewer_asset_verified = False
    formal_blind_ready = False  # requires continuous + answerable + no leakage
    return {
        "media_access_state": state,
        "still_only": still_only,
        "continuous_media_path": continuous,
        "provisional_answer_present": has_prov,
        "independently_answer_verified": answer_verified,
        "answerable_candidate": answerable_candidate,
        "reviewer_asset_verified": reviewer_asset_verified,
        "formal_blind_ready": formal_blind_ready,
        "review_mode": "STILL_STATIC_ONLY" if still_only else ("CONTINUOUS" if continuous else "NO_MEDIA"),
        "audio_required_unresolved": audio_needed,
    }


def build_true_blind_item(
    *,
    qa: dict[str, Any],
    facts_full: list[dict[str, Any]],
    side: str,
    priority: int,
) -> dict[str, Any]:
    """B_ONLY / A_ONLY: question + that side's media only."""
    wins = _window_side(qa.get("required_windows") or qa.get("time_intervals"), side)
    side_facts = _facts_for_side(facts_full, side)
    readiness = classify_review_readiness(qa, facts_full)
    item = {
        "priority": priority,
        "qa_id": qa["qa_id"],
        "video_id": qa["video_id"],
        "blind_variant": f"{side}_ONLY_BLIND",
        "question_zh": qa.get("question_zh"),
        "visible_windows": wins,
        "visible_media": side_facts,
        "media_access_state": readiness["media_access_state"],
        "review_mode": readiness["review_mode"],
        "reviewer_asset_verified": readiness["reviewer_asset_verified"],
        "formal_blind_ready": readiness["formal_blind_ready"],
        "answerable_candidate": readiness["answerable_candidate"],
        "reviewer_fields": {
            "answer": None,
            "confidence": None,
            "evidence_note": None,
        },
        "data_partition_status": "UNASSIGNED",
        "formal_supported": False,
        # Explicitly absent (tests search for these)
        "answer_hidden": True,
        "grades_hidden": True,
        "other_side_hidden": True,
    }
    # Sanity: no forbidden keys
    for k in BLIND_FORBIDDEN_KEYS:
        assert k not in item
    return item


def build_adjudication_item(
    *,
    qa: dict[str, Any],
    sc: dict[str, Any],
    facts_full: list[dict[str, Any]],
    priority: int,
) -> dict[str, Any]:
    """Unblinded A+B adjudication packet (intentionally full)."""
    return {
        "priority": priority,
        "qa_id": qa["qa_id"],
        "video_id": qa["video_id"],
        "blind_variant": "A_PLUS_B_ADJUDICATION",
        "unblinded": True,
        "mechanism": qa.get("mechanism"),
        "heuristic_grade": sc.get("grade"),
        "heuristic_score": sc.get("score"),
        "evidence_tested": sc.get("evidence_tested", False),
        "masked_qa_executed": sc.get("masked_qa_executed", False),
        "risks": sc.get("risks"),
        "question_zh": qa.get("question_zh"),
        "answer_status": qa.get("answer_status"),
        "provisional_answer_zh": qa.get("provisional_answer_zh"),
        "required_windows": qa.get("required_windows"),
        "facts": facts_full,
        "rule_proxy_necessity": sc.get("necessity_proxy"),
        "fact_binding": qa.get("fact_binding"),
        "data_partition_status": "UNASSIGNED",
        "formal_supported": False,
        "reviewer_fields": {
            "verdict": None,
            "answer_ok": None,
            "necessity_ok": None,
            "notes": None,
        },
    }


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

    # Serialize candidates for inspection; formal user blind batch only if readiness gates pass
    reviewable = []
    for p in prioritized:
        qa = drafts_by_id[p["qa_id"]]
        if qa.get("generation_error") or qa.get("leakage_error"):
            continue
        if qa.get("funnel_level") == "REJECTED_OR_QUARANTINE":
            continue
        if not qa.get("retained_as_independent_sample", True) and qa.get("duplicate_of_family"):
            continue
        if (qa.get("provisional_answer_zh") or "").upper() == "UNKNOWN" and qa.get("mechanism") == "cross_shot_narrative":
            continue
        reviewable.append(p)

    blind_keys_dir = out_dir / "blind_keys"
    blind_keys_dir.mkdir(parents=True, exist_ok=True)
    keys = []

    b_items, a_items, ab_items = [], [], []
    for p in reviewable:
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
                    "event_type": ev.get("event_type") or ev.get("verb"),
                    "summary_zh": ev.get("summary_zh"),
                    "evidence_paths": ev.get("evidence_paths"),
                    "source": ev.get("provenance_tier") or ev.get("source"),
                }
            )
        b_items.append(build_true_blind_item(qa=qa, facts_full=facts, side="B", priority=p["priority"]))
        a_items.append(build_true_blind_item(qa=qa, facts_full=facts, side="A", priority=p["priority"]))
        ab_items.append(build_adjudication_item(qa=qa, sc=sc, facts_full=facts, priority=p["priority"]))
        keys.append(
            {
                "qa_id": qa["qa_id"],
                "provisional_answer_zh": qa.get("provisional_answer_zh"),
                "normalized_answer": qa.get("normalized_answer"),
                "fact_ids": qa.get("fact_ids"),
                "mechanism": qa.get("mechanism"),
            }
        )

    (blind_keys_dir / "answers_key.json").write_text(
        json.dumps(
            {
                "note": "Separate from blind packets; do not mix into B_ONLY/A_ONLY",
                "items": keys,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    def _write_variant(name: str, items: list[dict[str, Any]], protocol: list[str]) -> dict[str, Any]:
        vdir = out_dir / name
        vdir.mkdir(parents=True, exist_ok=True)
        packet = {
            "packet_id": f"{run_id}_{name}",
            "variant": name,
            "n_items": len(items),
            "protocol": protocol,
            "items": items,
            "data_partition_status": "UNASSIGNED",
            "formal_supported": False,
            "human_status": "PENDING_HUMAN",
            "blind_integrity": name.endswith("BLIND"),
        }
        (vdir / "packet.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
        # Markdown without answers for blind
        lines = [f"# {name} — {packet['packet_id']}", "", f"Items: {len(items)}", ""]
        for it in items:
            lines.append(f"## [{it['priority']}] {it['qa_id']} — {it['video_id']}")
            lines.append(f"- Q: {it.get('question_zh')}")
            if name.endswith("BLIND"):
                lines.append(f"- visible_windows: {it.get('visible_windows')}")
                lines.append(f"- media_access_state: {it.get('media_access_state')}")
                for m in it.get("visible_media") or []:
                    for pth in m.get("evidence_paths") or []:
                        lines.append(f"- media: `{pth}`")
                lines.append("- reviewer answer= / confidence= / evidence_note=")
            else:
                lines.append(f"- provisional: {it.get('provisional_answer_zh')}")
                lines.append(f"- heuristic_grade: {it.get('heuristic_grade')} (NOT video-tested)")
            lines.append("")
        (vdir / "packet.md").write_text("\n".join(lines), encoding="utf-8")
        return packet

    b_pkt = _write_variant(
        "B_ONLY_BLIND",
        b_items,
        [
            "TRUE BLIND: only question + B-side media",
            "No A paths, A event IDs, answers, grades, or proxies",
            "Do not claim independent blindness if you already saw A+B",
        ],
    )
    a_pkt = _write_variant(
        "A_ONLY_BLIND",
        a_items,
        [
            "TRUE BLIND: only question + A-side media",
            "No B paths/answers/grades",
            "Prefer a reviewer who has not seen B or A+B",
        ],
    )
    ab_pkt = _write_variant(
        "A_PLUS_B_ADJUDICATION",
        ab_items,
        [
            "UNBLINDED adjudication — full evidence intentional",
            "Heuristic grades are NOT video-tested necessity proofs",
            "Do not mark SUPPORTED",
        ],
    )

    # Readiness tallies from B-side items (same QAs)
    n_answerable = sum(1 for it in b_items if it.get("answerable_candidate"))
    n_asset_verified = sum(1 for it in b_items if it.get("reviewer_asset_verified"))
    n_formal = sum(1 for it in b_items if it.get("formal_blind_ready"))
    n_still = sum(1 for it in b_items if it.get("review_mode") == "STILL_STATIC_ONLY")
    n_continuous = sum(1 for it in b_items if it.get("review_mode") == "CONTINUOUS")

    # Index (no answers)
    index = {
        "packet_id": f"{run_id}_human_batch_01",
        "run_id": run_id,
        "n_packet_serialized": len(reviewable),
        "n_reviewable": len(reviewable),  # legacy alias = serialized, NOT formal-ready
        "n_answerable_candidate": n_answerable,
        "n_reviewer_asset_verified": n_asset_verified,
        "n_continuous_media_reviewable": n_continuous,
        "n_still_only_serialized": n_still,
        "n_formal_blind_ready": n_formal,
        "n_true_blind_evaluated": 0,  # no independent A/B human/model eval completed this run
        "user_formal_blind_batch_authorized": False,
        "variants": {
            "B_ONLY_BLIND": b_pkt["n_items"],
            "A_ONLY_BLIND": a_pkt["n_items"],
            "A_PLUS_B_ADJUDICATION": ab_pkt["n_items"],
        },
        "blind_keys_path": str(blind_keys_dir / "answers_key.json"),
        "data_partition_status": "UNASSIGNED",
        "formal_supported": False,
        "note": (
            "Serialized ≠ formal user blind batch. "
            "Still-only paths do not set reviewer_asset_verified. "
            "Do not request user review until n_formal_blind_ready>0."
        ),
    }
    (out_dir / "human_review_packet.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "human_review_packet.md").write_text(
        f"# Human review index `{index['packet_id']}`\n\n"
        f"Serialized: {index['n_packet_serialized']} | answerable_candidate: {n_answerable} | "
        f"asset_verified: {n_asset_verified} | formal_blind_ready: {n_formal} | "
        f"true_blind_evaluated: 0\n\n"
        f"- Blind B: `B_ONLY_BLIND/packet.md`\n"
        f"- Blind A: `A_ONLY_BLIND/packet.md`\n"
        f"- Adjudication (unblinded): `A_PLUS_B_ADJUDICATION/packet.md`\n"
        f"- Answers key (separate): `blind_keys/answers_key.json`\n"
        f"\n**Do not send as formal user blind batch** while formal_blind_ready=0 "
        f"(stills ≠ continuous video verification).\n",
        encoding="utf-8",
    )
    return index


def assert_blind_packet_integrity(packet: dict[str, Any]) -> list[str]:
    """Return list of integrity violations (empty = ok)."""
    viol = []
    blob = json.dumps(packet, ensure_ascii=False)
    if packet.get("variant") in {"B_ONLY_BLIND", "A_ONLY_BLIND"}:
        for bad in (
            "provisional_answer_zh",
            "auto_grade",
            "auto_score",
            "proxy_necessity",
            "necessity_proxy",
            "gold_answer",
            "normalized_answer",
            "fact_binding",
            "heuristic_grade",
        ):
            if f'"{bad}"' in blob:
                viol.append(f"forbidden_key_present:{bad}")
        # Other side event ids should not appear as event_id fields
        for it in packet.get("items") or []:
            for m in it.get("visible_media") or []:
                if "event_id" in m:
                    viol.append(f"event_id_in_blind_media:{it.get('qa_id')}")
            if "facts" in it:
                viol.append(f"full_facts_in_blind:{it.get('qa_id')}")
            if "required_windows" in it and it.get("required_windows") and len(it.get("required_windows") or []) > 1:
                # Blind should only expose visible_windows
                viol.append(f"required_windows_in_blind:{it.get('qa_id')}")
    return viol
