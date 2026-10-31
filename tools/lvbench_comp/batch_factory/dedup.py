"""Multi-layer semantic / evidence-family dedup (V2)."""

from __future__ import annotations

import hashlib
import re
from typing import Any


def _norm_text(s: str | None) -> str:
    if not s:
        return ""
    t = s.lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[，。？！、；：\"'（）()[\]{}]", "", t)
    return t


def question_answer_key(qa: dict[str, Any]) -> str:
    q = _norm_text(qa.get("question_zh") or qa.get("question_en"))
    a = _norm_text(qa.get("provisional_answer_zh") or qa.get("normalized_answer") or "")
    return hashlib.sha256(f"{q}||{a}".encode()).hexdigest()[:16]


def windows_overlap(a: list[list[float]] | None, b: list[list[float]] | None, *, iou_min: float = 0.3) -> bool:
    if not a or not b:
        return False
    for wa in a:
        for wb in b:
            if len(wa) < 2 or len(wb) < 2:
                continue
            lo = max(float(wa[0]), float(wb[0]))
            hi = min(float(wa[1]), float(wb[1]))
            inter = max(0.0, hi - lo)
            union = max(float(wa[1]), float(wb[1])) - min(float(wa[0]), float(wb[0]))
            if union > 0 and inter / union >= iou_min:
                return True
            # also treat nested / near-identical spans
            if inter > 0 and abs(float(wa[0]) - float(wb[0])) < 5 and abs(float(wa[1]) - float(wb[1])) < 15:
                return True
    return False


def evidence_overlap_key(qa: dict[str, Any]) -> str:
    vid = qa.get("video_id") or ""
    mech = qa.get("mechanism") or ""
    # Round windows to reduce aliasing
    spans = []
    for w in qa.get("time_intervals") or qa.get("required_windows") or []:
        if len(w) >= 2:
            spans.append(f"{int(float(w[0]) // 10)}-{int(float(w[1]) // 10)}")
    return f"{vid}|{mech}|{'/'.join(spans)}"


def apply_semantic_dedup(drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse duplicate questions / overlapping evidence; keep alias provenance."""
    # First pass: exact question+answer
    seen_qa: dict[str, str] = {}
    # Second: overlapping windows same video+mechanism
    kept_by_overlap: list[dict[str, Any]] = []

    out: list[dict[str, Any]] = []
    for d in drafts:
        d = dict(d)
        aliases = list(d.get("duplicate_aliases") or [])
        qk = question_answer_key(d)
        collapsed = False
        reason = None

        if qk in seen_qa:
            d["duplicate_of_family"] = True
            d["retained_as_independent_sample"] = False
            d["duplicate_of_qa_id"] = seen_qa[qk]
            d["dedup_reason"] = "identical_normalized_question_answer"
            aliases.append(seen_qa[qk])
            collapsed = True
            reason = "identical_normalized_question_answer"
        else:
            # overlap with retained
            for prev in kept_by_overlap:
                if prev["video_id"] != d["video_id"]:
                    continue
                if (prev.get("mechanism") or "") != (d.get("mechanism") or ""):
                    continue
                if windows_overlap(prev.get("time_intervals"), d.get("time_intervals")):
                    d["duplicate_of_family"] = True
                    d["retained_as_independent_sample"] = False
                    d["duplicate_of_qa_id"] = prev["qa_id"]
                    d["dedup_reason"] = "overlapping_windows_same_mechanism"
                    aliases.append(prev["qa_id"])
                    collapsed = True
                    reason = "overlapping_windows_same_mechanism"
                    # mark prev as having alias
                    prev.setdefault("duplicate_aliases", []).append(d["qa_id"])
                    break

        d["duplicate_aliases"] = aliases
        if not collapsed:
            d["duplicate_of_family"] = bool(d.get("duplicate_of_family", False))
            if "retained_as_independent_sample" not in d or d.get("dedup_reason"):
                d["retained_as_independent_sample"] = not d["duplicate_of_family"]
            if not d.get("duplicate_of_family"):
                seen_qa[qk] = d["qa_id"]
                kept_by_overlap.append(d)
        else:
            d["retained_as_independent_sample"] = False
            # attach alias on canonical
            can_id = d.get("duplicate_of_qa_id")
            for prev in out:
                if prev["qa_id"] == can_id:
                    prev.setdefault("duplicate_aliases", []).append(d["qa_id"])
                    break
        if reason and not d.get("dedup_reason"):
            d["dedup_reason"] = reason
        out.append(d)
    return out


def n_distinct_questions(drafts: list[dict[str, Any]]) -> int:
    return len({question_answer_key(d) for d in drafts})
