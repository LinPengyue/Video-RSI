#!/usr/bin/env python3
"""Necessity-aware pre-screener for Seen Pilot candidates (engineering aid only).

Does NOT certify video facts, formal Seen, Gold, or composition necessity.
Encodes run_001 scientific feedback as diagnostic heuristics.
"""
from __future__ import annotations

import re
from typing import Any


# Lessons from run_001 scientific review (do not auto-promote)
MECHANISM_A_CROSS_WINDOW_TARGET_BIND = "CROSS_WINDOW_TARGET_BIND"
MECHANISM_B_TEMPORAL_PERSON_THEN_RELATION = "TEMPORAL_PERSON_BIND_THEN_CROSS_WINDOW_RELATION"
MECHANISM_C_SHORTCUT_OR_UNRESOLVED = "SINGLE_WINDOW_SHORTCUT_OR_UNRESOLVED_REFERENT"

SUFF_A_ONLY = "A_ONLY_SUFFICIENT_SUSPECTED"
SUFF_B_ONLY = "B_ONLY_SUFFICIENT_SUSPECTED"
SUFF_AB = "A_PLUS_B_NECESSARY_SUSPECTED"
SUFF_REF_UNRESOLVED = "REFERENCE_UNRESOLVED"
SUFF_INSUFFICIENT = "EVIDENCE_INSUFFICIENT_FOR_AUTO_CALL"

PRIORITY = "PRIORITY_FOR_HUMAN_REVIEW"
DIAGNOSTIC = "DIAGNOSTIC_NEGATIVE_OR_UNRESOLVED"
DEFER = "DEFER_INSUFFICIENT_STRUCTURE"


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def infer_bind_variable(question: str, schema: str) -> dict[str, Any]:
    q = _norm(question)
    schema = _norm(schema)
    bind = {
        "bind_variable": None,
        "mechanism_hypothesis": None,
        "target_referent_ambiguous_if_B_names_entity": False,
        "notes": [],
    }
    # SP005 / SP001 style: descriptive target in question needing A to select, B to query
    if any(k in q for k in ["final winner", "country whose", "whose flag", "person who", "the elder who", "animal that", "first means", "place where the scene"]):
        bind["bind_variable"] = "target_entity_selected_in_one_window"
        bind["mechanism_hypothesis"] = MECHANISM_A_CROSS_WINDOW_TARGET_BIND
        bind["target_referent_ambiguous_if_B_names_entity"] = True
        bind["notes"].append(
            "SP005 lesson: B recognizing an entity ≠ B resolving which entity the question selects."
        )
    if "relation" in schema or "whose" in q or "sister" in q or "coach" in q:
        if bind["mechanism_hypothesis"] is None:
            bind["mechanism_hypothesis"] = MECHANISM_B_TEMPORAL_PERSON_THEN_RELATION
        bind["notes"].append("May involve within-A temporal person bind and/or cross-window relation join (SP002-like).")
        if bind["bind_variable"] is None:
            bind["bind_variable"] = "person_or_relation_referent"
    if bind["mechanism_hypothesis"] is None:
        if "identify_" in schema and "query_" in schema:
            bind["mechanism_hypothesis"] = MECHANISM_A_CROSS_WINDOW_TARGET_BIND
            bind["bind_variable"] = "schema_identify_then_query"
        else:
            bind["mechanism_hypothesis"] = MECHANISM_C_SHORTCUT_OR_UNRESOLVED
            bind["bind_variable"] = "unknown"
    return bind


def counterfactual_target_swap(question: str) -> dict[str, Any]:
    """Screening aid only — not video proof."""
    q = _norm(question)
    useful = any(
        k in q
        for k in [
            "final winner",
            "person who",
            "country whose",
            "animal that",
            "elder who",
            "first means",
            "place where",
            "whose coach",
            "whose flag",
        ]
    )
    return {
        "applicable": useful,
        "prompt": (
            "If window A selected a different plausible target entity, would the query executed in B change?"
            if useful
            else "NOT_APPLICABLE_LOW_STRUCTURE"
        ),
        "interpretation_if_yes": "Supports A-required target selection hypothesis (SP005-class); still needs human video review.",
        "interpretation_if_no": "Weakens composition necessity; check A-only/B-only shortcut on FULL original question.",
        "not_video_proof": True,
    }


def diagnose_sufficiency_hypothesis(candidate: dict) -> dict[str, Any]:
    """Heuristic only; must not force pass/fail for unresolved cases."""
    q = _norm(candidate.get("new_question") or candidate.get("question"))
    schema = _norm(candidate.get("composition_schema"))
    refs = candidate.get("time_references") or []
    bind = infer_bind_variable(q, schema)
    cf = counterfactual_target_swap(q)

    # Structural red flags for single-window sufficiency (hypothesis)
    a_only = SUFF_INSUFFICIENT
    b_only = SUFF_INSUFFICIENT
    overall = SUFF_REF_UNRESOLVED

    # If question embeds a definite description that typically needs the other window
    if bind["target_referent_ambiguous_if_B_names_entity"]:
        b_only = SUFF_B_ONLY  # suspected risk only if one wrongly equates recognition with selection
        a_only = SUFF_A_ONLY  # similarly if A alone answers without bind
        overall = SUFF_AB
        priority = PRIORITY
    elif "query_action" in schema and "identify_event" in schema:
        # Often B may contain full narrative (SP003-like) — do not auto-fail or auto-pass
        overall = SUFF_REF_UNRESOLVED
        priority = DIAGNOSTIC
        a_only = SUFF_INSUFFICIENT
        b_only = SUFF_B_ONLY  # risk to check
    else:
        overall = SUFF_REF_UNRESOLVED
        priority = DEFER

    if len(refs) < 2:
        overall = SUFF_INSUFFICIENT
        priority = DEFER

    return {
        "a_only_hypothesis": a_only,
        "b_only_hypothesis": b_only,
        "composition_necessity_hypothesis": overall,
        "screen_bucket": priority,
        "bind": bind,
        "counterfactual": cf,
        "full_question_sufficiency_rule": (
            "Judge A-only/B-only against the COMPLETE original question; "
            "do not assume the target entity is pre-resolved (SP004/SP005)."
        ),
        "auto_certified": False,
        "disclaimer": "Heuristic pre-screen only; human video review required. Not formal Seen/Gold.",
    }


def draft_directed_program(candidate: dict, diag: dict) -> dict[str, Any]:
    schema = candidate.get("composition_schema") or ""
    parts = [p.strip() for p in schema.split("+")]
    identify = parts[0] if parts else "Identify"
    query = parts[1] if len(parts) > 1 else "Query"
    bind_var = diag["bind"]["bind_variable"]
    return {
        "draft_only": True,
        "nodes": [
            {"clip_role": "A_or_B_identify", "op": identify, "out": bind_var},
            {"clip_role": "cross", "op": "CrossWindowBind", "in": [bind_var], "out": "bound_target"},
            {"clip_role": "A_or_B_query", "op": query, "in": ["bound_target"], "out": "answer"},
        ],
        "sp005_guard": "Do not treat B entity recognition alone as resolving question target selection.",
        "sp002_note": "If person identity needs within-window temporal bind, label TemporalPersonBind separately from cross-window join.",
        "not_approved": True,
    }


def screen_candidate(candidate: dict, *, meta: dict | None = None) -> dict[str, Any]:
    diag = diagnose_sufficiency_hypothesis(candidate)
    prog = draft_directed_program(candidate, diag)
    return {
        "qa_uid": candidate.get("id"),
        "video_id": candidate.get("video_id"),
        "composition_schema": candidate.get("composition_schema"),
        "question_unverified": candidate.get("new_question"),
        "answer_unverified": candidate.get("new_answer"),
        "time_references": candidate.get("time_references"),
        "source_uids": candidate.get("source_uids"),
        "diagnosis": diag,
        "program_draft": prog,
        "meta": meta or {},
        "status": "PENDING_HUMAN_VIDEO_REVIEW",
        "formal_seen_train": False,
        "formal_gold": False,
        "train_exposed": False,
    }
