#!/usr/bin/env python3
"""Seen pilot isolation checks — engineering only; no scientific adjudication."""
from __future__ import annotations

from typing import Any


FORMAL_FORBIDDEN_FLAGS = {
    "FORMAL_SEEN_TRAIN",
    "TRAIN_EXPOSED",
    "GOLD",
}
ALLOWED_PILOT_STATUSES = {
    "PENDING_HUMAN_VIDEO_REVIEW",
    "SCIENTIFIC_REVIEW_INGESTED",
}
PILOT_STATUS = "PENDING_HUMAN_VIDEO_REVIEW"


def assert_seen_pilot_isolation(
    *,
    catalog_items: list[dict],
    hard_exclude_videos: set[str] | list[str],
    hard_exclude_uids: set[str] | list[str],
) -> dict[str, Any]:
    hard_v = set(hard_exclude_videos)
    hard_u = set(hard_exclude_uids)
    issues: list[str] = []
    for it in catalog_items:
        vid = it.get("video_id")
        uid = it.get("qa_uid")
        if vid in hard_v:
            issues.append(f"BLOCK: Unseen/Test/protected video_id in Seen pilot: {vid} ({it.get('workbench_id')})")
        if uid in hard_u:
            issues.append(f"BLOCK: excluded qa_uid in Seen pilot: {uid} ({it.get('workbench_id')})")
        st = it.get("user_confirmation_status")
        if st not in ALLOWED_PILOT_STATUSES:
            issues.append(f"status must be one of {sorted(ALLOWED_PILOT_STATUSES)}, got {st} for {it.get('workbench_id')}")
        for flag in ("formal_seen_train", "formal_gold", "train_exposed", "formal_unseen", "seen_pool_frozen", "approve_expensive_track_a_rsi"):
            if it.get(flag) is True:
                issues.append(f"forbidden formal flag {flag}=true on {it.get('workbench_id')}")
        # Graph approval as Seen-pilot compositional candidate must NOT flip formal Seen
        sr = it.get("scientific_review") or {}
        if sr.get("compositional_candidate_graph_approved") and it.get("formal_seen_train") is True:
            issues.append(f"approved compositional candidate wrongly formal_seen_train on {it.get('workbench_id')}")
        if it.get("media_status") == "MEDIA_UNAVAILABLE" and it.get("human_reviewed") is True:
            issues.append(f"MEDIA_UNAVAILABLE must not be marked human_reviewed: {it.get('workbench_id')}")
        # Historical train label must not auto-certify
        if it.get("historical_train_label_present") and it.get("formal_seen_train") is True:
            issues.append(f"historical train label wrongly certified formal Seen: {it.get('workbench_id')}")
    return {
        "check": "seen_pilot_isolation",
        "status": "PASS" if not issues else "BLOCK",
        "issues": issues,
        "n_items": len(catalog_items),
        "formal_forbidden_flags": sorted(FORMAL_FORBIDDEN_FLAGS),
    }


def historical_train_label_does_not_certify(item: dict) -> bool:
    """Old train split membership never implies FORMAL_SEEN_TRAIN."""
    if item.get("historical_train_label_present") or item.get("historical_train_label_status"):
        return item.get("formal_seen_train") is not True and item.get("user_confirmation_status") in ALLOWED_PILOT_STATUSES
    return True


def media_unavailable_not_reviewed(item: dict) -> bool:
    if item.get("media_status") == "MEDIA_UNAVAILABLE":
        return item.get("human_reviewed") is not True and item.get("review_completed") is not True
    return True
