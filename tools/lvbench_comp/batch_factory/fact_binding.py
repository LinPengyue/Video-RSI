"""Validate that QA subjects derive from cited event fields (V2)."""

from __future__ import annotations

import re
from typing import Any


_NAME_HINTS = re.compile(
    r"\b(Gay|Gatlin|Ndure|Fan|Zhendong|Tyson|Justin|Jaysuma)\b",
    re.I,
)
_COUNTRY = re.compile(r"\b(USA|NOR|CHN|BRI|LIV)\b", re.I)


def _event_text_bag(ev: dict[str, Any]) -> str:
    parts = [
        str(ev.get("object") or ""),
        str(ev.get("verb") or ""),
        str(ev.get("notes") or ""),
        str(ev.get("actor_local_track") or ""),
        str(ev.get("state_before") or ""),
        str(ev.get("state_after") or ""),
        str(ev.get("summary_zh") or ""),
    ]
    return " ".join(parts)


def validate_fact_binding(qa: dict[str, Any], events_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Return binding report; set reject/quarantine flags on contradictions."""
    errors: list[str] = []
    warnings: list[str] = []
    q = (qa.get("question_zh") or "") + " " + (qa.get("provisional_answer_zh") or "")
    cited = [events_by_id[i] for i in (qa.get("fact_ids") or []) if i in events_by_id]
    if not cited:
        errors.append("no_cited_events")
        return {"ok": False, "errors": errors, "warnings": warnings}

    bags = [_event_text_bag(e) for e in cited]
    joined = " | ".join(bags)

    # Named entities in question/answer must appear in at least one cited event
    for m in _NAME_HINTS.finditer(q):
        name = m.group(1)
        if name.lower() not in joined.lower():
            # Allow if only in answer template about a different intro — hard error if first fact contradicts
            errors.append(f"name_not_in_cited_events:{name}")

    for m in _COUNTRY.finditer(q):
        c = m.group(1)
        if c.upper() not in joined.upper() and c.upper() not in {"USA"}:  # USA may be inferred from Gay/Gatlin
            warnings.append(f"country_weak:{c}")

    # Special: first fact intro Ndure but Q claims USA Gay
    first = cited[0]
    first_bag = _event_text_bag(first).lower()
    if "ndure" in first_bag or "nor" in first_bag:
        if re.search(r"美国|USA|Gay", q, re.I) and "gay" not in first_bag:
            errors.append("subject_fact_mismatch:cited_Ndure_but_question_USA_Gay")

    # Internal track tokens must not leak into user-facing question
    if re.search(r"`?[a-z]+_local(_[A-Za-z0-9]+)?`?", qa.get("question_zh") or "") or "presenter_local" in (
        qa.get("question_zh") or ""
    ):
        errors.append("internal_track_token_in_question")

    # Color answers should match garment event object/state
    if qa.get("mechanism") == "reverse_name_to_early_garment":
        ans = (qa.get("provisional_answer_zh") or "") + (qa.get("normalized_answer") or "")
        garment_evs = [e for e in cited if e.get("verb") in {"remove_outer_garment", "wipe_face_wear_jacket"}]
        if garment_evs and "红" in ans:
            gbag = _event_text_bag(garment_evs[0]).lower()
            if "red" not in gbag and "红" not in gbag:
                errors.append("color_answer_not_in_garment_event")

    ok = len(errors) == 0
    return {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "binding_status": "OK" if ok else "QUARANTINE_BINDING_ERROR",
    }


def apply_binding_gate(drafts: list[dict[str, Any]], events_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for d in drafts:
        d = dict(d)
        rep = validate_fact_binding(d, events_by_id)
        d["fact_binding"] = rep
        if not rep["ok"]:
            d["funnel_level"] = "REJECTED_OR_QUARANTINE"
            d["retained_as_independent_sample"] = False
            d["answer_status"] = "ANSWER_PENDING"
            # Do not leave contradictory filled answers
            if any("mismatch" in e or "name_not_in" in e for e in rep["errors"]):
                d["provisional_answer_zh"] = None
                d["normalized_answer"] = None
                d["generation_error"] = True
        out.append(d)
    return out
