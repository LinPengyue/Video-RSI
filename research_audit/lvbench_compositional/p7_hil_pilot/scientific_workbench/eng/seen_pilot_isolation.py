#!/usr/bin/env python3
"""Seen pilot isolation checks — engineering only; no scientific adjudication."""
from __future__ import annotations

from typing import Any


FORMAL_FORBIDDEN = {
    "USER_APPROVED_STRUCTURED_GRAPH",
    "FORMAL_SEEN_TRAIN",
    "TRAIN_EXPOSED",
    "GOLD",
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
        if st != PILOT_STATUS:
            issues.append(f"status must be {PILOT_STATUS}, got {st} for {it.get('workbench_id')}")
        for flag in ("formal_seen_train", "formal_gold", "train_exposed", "formal_unseen"):
            if it.get(flag) is True:
                issues.append(f"forbidden formal flag {flag}=true on {it.get('workbench_id')}")
        if it.get("user_confirmation_status") in FORMAL_FORBIDDEN:
            issues.append(f"forbidden status label on {it.get('workbench_id')}")
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
    }


def historical_train_label_does_not_certify(item: dict) -> bool:
    """Old train split membership never implies FORMAL_SEEN_TRAIN."""
    if item.get("historical_train_label_present") or item.get("historical_train_label_status"):
        return item.get("formal_seen_train") is not True and item.get("user_confirmation_status") == PILOT_STATUS
    return True


def media_unavailable_not_reviewed(item: dict) -> bool:
    if item.get("media_status") == "MEDIA_UNAVAILABLE":
        return item.get("human_reviewed") is not True and item.get("review_completed") is not True
    return True
