"""Question-side semantic leakage checks (V2 patch)."""

from __future__ import annotations

import re
from typing import Any


def _tokens_from_event(ev: dict[str, Any]) -> set[str]:
    bag: set[str] = set()
    for key in ("location", "object", "summary_zh", "state_before", "state_after", "verb"):
        val = ev.get(key)
        if not val:
            continue
        s = str(val).strip()
        if len(s) >= 4:
            bag.add(s.lower())
        # also snake_case parts
        for part in re.split(r"[_\s/;|]+", s):
            if len(part) >= 5:
                bag.add(part.lower())
    return bag


def question_side_leakage(
    qa: dict[str, Any],
    events_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Detect if question text embeds answer-bearing A/B attributes.

    For multi-witness QAs, leaking *both* sides' distinctive location/object tokens
    into the question defeats A-only/B-only necessity even when media is masked.
    """
    q = (qa.get("question_zh") or "") + " " + (qa.get("question_en") or "")
    q_l = q.lower()
    fact_ids = qa.get("fact_ids") or []
    facts = [events_by_id[i] for i in fact_ids if i in events_by_id]
    leaked: list[str] = []
    side_hits = {"A": [], "B": []}
    for i, ev in enumerate(facts):
        side = "A" if i == 0 else "B" if i == len(facts) - 1 else "M"
        for tok in _tokens_from_event(ev):
            if tok in q_l:
                leaked.append(tok)
                if side in side_hits:
                    side_hits[side].append(tok)
    # Critical: both sides' distinctive attrs in the same question
    both_sides = bool(side_hits["A"] and side_hits["B"])
    mech = qa.get("mechanism") or ""
    # Scene-contrast drafts must not name either side's environment/objects in the stem.
    # Name-contrast controls may mention names (that is the question); do not auto-fail those.
    must_block = mech in {"cross_scene_attribute_contrast", "cross_shot_narrative"}
    ok = True
    if must_block and both_sides:
        ok = False
    elif must_block and leaked:
        # even one-side location dump in contrast Q is discouraged
        loc_leaks = [t for t in leaked if "_" in t or len(t) >= 8]
        if loc_leaks:
            ok = False
    return {
        "ok": ok,
        "both_sides_leaked": both_sides,
        "leaked_tokens": sorted(set(leaked)),
        "side_hits": side_hits,
        "note": "Question must not embed both witnesses' answer-bearing attributes",
    }


def apply_leakage_gate(drafts: list[dict[str, Any]], events_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for d in drafts:
        d = dict(d)
        rep = question_side_leakage(d, events_by_id)
        d["question_leakage"] = rep
        if not rep["ok"]:
            d["leakage_error"] = True
            d["retained_as_independent_sample"] = False
            d.setdefault("uncertainty", [])
            if "question_side_semantic_leakage" not in d["uncertainty"]:
                d["uncertainty"] = list(d["uncertainty"]) + ["question_side_semantic_leakage"]
        out.append(d)
    return out
