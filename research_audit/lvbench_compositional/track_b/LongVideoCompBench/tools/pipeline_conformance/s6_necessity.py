#!/usr/bin/env python3
"""S6 Necessity: three independent result channels.

1. Structural Necessity — evidence uniqueness / answer localization (auditable trail)
2. Model Necessity — real A-only / B-only / A+B runs (NOT_RUN if no blind model)
3. Shortcut Audit — OCR, single-candidate, language prior, answer leakage

Human SAME ≠ Necessity PASS. Structural does not write preset FAIL without evidence fields.
"""
from __future__ import annotations

from typing import Any


def structural_necessity(evidence: dict[str, Any]) -> dict[str, Any]:
    """Derive structural verdict from explicit evidence fields (no hidden presets).

    Expected evidence keys (callers must supply; missing → UNKNOWN):
      - answer_localized_window: "A" | "B" | "BOTH" | "NEITHER"
      - a_unique_answer_bearing_entity: bool | None
      - b_contains_answer_payload: bool | None
      - bind_required_for_answer_payload: bool | None
      - within_b_subject_switch: bool | None
      - notes: str
    """
    required = [
        "answer_localized_window",
        "a_unique_answer_bearing_entity",
        "b_contains_answer_payload",
        "bind_required_for_answer_payload",
    ]
    missing = [k for k in required if k not in evidence or evidence[k] is None]
    trail = {
        "inputs": {k: evidence.get(k) for k in required + ["within_b_subject_switch", "notes"]},
        "missing_fields": missing,
        "rules_fired": [],
    }
    if missing:
        return {
            "channel": "structural",
            "verdict": "UNKNOWN",
            "reason": "missing_evidence_fields:" + ",".join(missing),
            "trail": trail,
        }

    loc = evidence["answer_localized_window"]
    a_unique = bool(evidence["a_unique_answer_bearing_entity"])
    b_has = bool(evidence["b_contains_answer_payload"])
    bind_needed = bool(evidence["bind_required_for_answer_payload"])

    # Rule 1: answer fully in A and unique entity → A-only sufficient → FAIL
    if loc == "A" and a_unique and not bind_needed:
        trail["rules_fired"].append("R1_A_unique_answer_no_bind_needed")
        return {
            "channel": "structural",
            "verdict": "FAIL",
            "reason": "A-only uniquely determines answer; CrossWindow bind not required for payload",
            "trail": trail,
        }
    # Rule 2: answer fully in B without needing A → FAIL
    if loc == "B" and b_has and not bind_needed:
        trail["rules_fired"].append("R2_B_only_answer")
        return {
            "channel": "structural",
            "verdict": "FAIL",
            "reason": "B-only contains answer payload without A dependency",
            "trail": trail,
        }
    # Rule 3: bind required and answer needs both windows → PASS (structural only)
    if bind_needed and loc in {"BOTH", "A"} and not (loc == "A" and a_unique and not bind_needed):
        if bind_needed and not (loc == "A" and a_unique):
            trail["rules_fired"].append("R3_bind_required_compositional")
            return {
                "channel": "structural",
                "verdict": "PASS",
                "reason": "Bind required and answer not uniquely A-local without identity",
                "trail": trail,
            }
    # Ambiguous
    trail["rules_fired"].append("R0_insufficient_to_decide")
    return {
        "channel": "structural",
        "verdict": "UNKNOWN",
        "reason": "evidence present but no decisive structural rule fired",
        "trail": trail,
    }


def shortcut_audit(signals: dict[str, Any]) -> dict[str, Any]:
    """OCR / single-candidate / language-prior / answer-leakage checks."""
    findings = []
    risk = "LOW"
    if signals.get("ocr_answer_in_window_A"):
        findings.append("OCR_OR_SIGNAGE_IN_A_MATCHES_ANSWER")
        risk = "HIGH"
    if signals.get("single_candidate_entity_in_A"):
        findings.append("SINGLE_CANDIDATE_ENTITY_IN_A")
        risk = "HIGH" if risk != "HIGH" else risk
    if signals.get("question_text_leaks_answer"):
        findings.append("QUESTION_TEXT_LEAKS_ANSWER")
        risk = "HIGH"
    if signals.get("language_prior_celebrity_or_brand"):
        findings.append("LANGUAGE_PRIOR_CELEBRITY_OR_BRAND")
        risk = "MEDIUM" if risk == "LOW" else risk
    if signals.get("subtitle_leak"):
        findings.append("SUBTITLE_LEAK")
        risk = "HIGH"
    return {
        "channel": "shortcut_audit",
        "risk": risk,
        "findings": findings,
        "signals": signals,
        "blocks_strict_necessity_pass": risk == "HIGH",
    }


def model_necessity(
    *,
    blind_model_available: bool = False,
    a_only_run: dict[str, Any] | None = None,
    b_only_run: dict[str, Any] | None = None,
    ab_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not blind_model_available:
        return {
            "channel": "model",
            "status": "NOT_RUN",
            "reason": "NO_BLIND_MODEL_OR_INDEPENDENT_REVIEWER",
            "forged": False,
            "A_only": None,
            "B_only": None,
            "A_plus_B": None,
        }
    # Real runs only when provided
    return {
        "channel": "model",
        "status": "RUN",
        "forged": False,
        "A_only": a_only_run,
        "B_only": b_only_run,
        "A_plus_B": ab_run,
    }


def combine_necessity(
    structural: dict[str, Any],
    model: dict[str, Any],
    shortcut: dict[str, Any],
) -> dict[str, Any]:
    """Overall verdict never promotes to PASS if structural FAIL or high shortcut risk.

    Model NOT_RUN does not invent PASS. Human identity is out of scope here.
    """
    overall = "UNKNOWN"
    reasons = []
    if structural.get("verdict") == "FAIL" or shortcut.get("blocks_strict_necessity_pass"):
        overall = "FAIL"
        if structural.get("verdict") == "FAIL":
            reasons.append("structural:" + structural.get("reason", ""))
        if shortcut.get("blocks_strict_necessity_pass"):
            reasons.append("shortcut:" + ",".join(shortcut.get("findings") or []))
    elif structural.get("verdict") == "PASS" and model.get("status") == "RUN":
        # Would require model A-only fail + AB success — not auto without model
        a = model.get("A_only") or {}
        ab = model.get("A_plus_B") or {}
        if a.get("correct") is False and ab.get("correct") is True:
            overall = "PASS"
            reasons.append("structural_PASS_and_model_A_fail_AB_pass")
        else:
            overall = "UNKNOWN"
            reasons.append("model_run_inconclusive_for_pass")
    elif structural.get("verdict") == "PASS" and model.get("status") == "NOT_RUN":
        overall = "UNKNOWN"
        reasons.append("structural_PASS_but_model_NOT_RUN_cannot_claim_full_necessity_pass")
    else:
        overall = structural.get("verdict") or "UNKNOWN"
        reasons.append("defer_to_structural")

    return {
        "schema": "s6_necessity_combined_v1",
        "overall_verdict": overall,
        "reasons": reasons,
        "structural": structural,
        "model": model,
        "shortcut_audit": shortcut,
        "formal_gold": False,
        "human_identity_does_not_imply_pass": True,
    }
