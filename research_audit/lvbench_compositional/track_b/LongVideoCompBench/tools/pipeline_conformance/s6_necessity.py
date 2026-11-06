#!/usr/bin/env python3
"""S6 Necessity: three independent result channels with provenance classes.

1. Structural Necessity — auditable trail; engineer hypotheses ≠ auto video proof
2. Model Necessity — real A-only / B-only / A+B runs with run IDs (else NOT_RUN)
3. Shortcut Audit — OCR, single-candidate, language prior, answer leakage

Human SAME ≠ Necessity PASS. Preset booleans must declare provenance class.
"""
from __future__ import annotations

from typing import Any


PROVENANCE_CLASSES = (
    "independently_observed_fact",
    "audited_entity_bind",
    "program_computed_candidate_set",
    "engineer_unverified_shortcut_hypothesis",
    "actual_model_run_record",
)


def _classify_field_provenance(evidence: dict[str, Any]) -> dict[str, Any]:
    """Split evidence into provenance classes. Missing class → treat as engineer hypothesis."""
    field_prov = evidence.get("field_provenance") or {}
    classes: dict[str, list[str]] = {c: [] for c in PROVENANCE_CLASSES}
    for key in (
        "answer_localized_window",
        "a_unique_answer_bearing_entity",
        "b_contains_answer_payload",
        "bind_required_for_answer_payload",
        "within_b_subject_switch",
        "candidate_set_size_in_A",
        "multi_signage_uniqueness_verified",
    ):
        if key not in evidence:
            continue
        cls = field_prov.get(key) or "engineer_unverified_shortcut_hypothesis"
        if cls not in classes:
            cls = "engineer_unverified_shortcut_hypothesis"
        classes[cls].append(key)

    # Explicit lists from caller
    for c in PROVENANCE_CLASSES:
        extra = evidence.get(c + "s") or evidence.get(c) or []
        if isinstance(extra, list):
            for item in extra:
                if isinstance(item, str) and item not in classes[c]:
                    classes[c].append(item)

    engineer_keys = set(classes["engineer_unverified_shortcut_hypothesis"])
    decisive_keys = {
        "a_unique_answer_bearing_entity",
        "bind_required_for_answer_payload",
        "multi_signage_uniqueness_verified",
    }
    uniqueness_only_from_engineer = bool(engineer_keys & decisive_keys)
    return {
        "classes": classes,
        "uniqueness_depends_on_unverified_engineer_hypothesis": uniqueness_only_from_engineer,
        "strict_structural_proof_possible": not uniqueness_only_from_engineer
        and bool(classes["independently_observed_fact"] or classes["program_computed_candidate_set"]),
    }


def structural_necessity(evidence: dict[str, Any]) -> dict[str, Any]:
    """Derive structural verdict from explicit evidence + provenance (no hidden presets).

    Expected evidence keys (callers must supply; missing → UNKNOWN):
      - answer_localized_window: "A" | "B" | "BOTH" | "NEITHER"
      - a_unique_answer_bearing_entity: bool | None
      - b_contains_answer_payload: bool | None
      - bind_required_for_answer_payload: bool | None
      - within_b_subject_switch: bool | None
      - field_provenance: dict[field -> provenance_class]
      - notes: str
    """
    required = [
        "answer_localized_window",
        "a_unique_answer_bearing_entity",
        "b_contains_answer_payload",
        "bind_required_for_answer_payload",
    ]
    missing = [k for k in required if k not in evidence or evidence[k] is None]
    prov = _classify_field_provenance(evidence)
    trail = {
        "inputs": {k: evidence.get(k) for k in required + ["within_b_subject_switch", "notes"]},
        "missing_fields": missing,
        "provenance": prov,
        "rules_fired": [],
    }
    if missing:
        return {
            "channel": "structural",
            "verdict": "UNKNOWN",
            "strict_proof": False,
            "reason": "missing_evidence_fields:" + ",".join(missing),
            "trail": trail,
        }

    loc = evidence["answer_localized_window"]
    a_unique = bool(evidence["a_unique_answer_bearing_entity"])
    b_has = bool(evidence["b_contains_answer_payload"])
    bind_needed = bool(evidence["bind_required_for_answer_payload"])
    multi_sign_ok = evidence.get("multi_signage_uniqueness_verified")

    # If uniqueness is engineer-only hypothesis, do not claim strict FAIL proof
    strict = prov["strict_structural_proof_possible"] and not (
        multi_sign_ok is False or multi_sign_ok is None and "location" in str(evidence.get("notes", "")).lower()
    )
    # Explicit: USFV-style multi-signage must be independently verified
    if evidence.get("multi_signage_uniqueness_verified") is False:
        trail["rules_fired"].append("R_MULTISIGN_UNIQUENESS_NOT_VERIFIED")
        return {
            "channel": "structural",
            "verdict": "UNKNOWN",
            "strict_proof": False,
            "control_risk": True,
            "reason": (
                "Answer uniqueness among multiple A-window signage/candidates "
                "is not independently verified; cannot claim strict structural FAIL/PASS"
            ),
            "trail": trail,
        }

    if loc == "A" and a_unique and not bind_needed:
        trail["rules_fired"].append("R1_A_unique_answer_no_bind_needed")
        return {
            "channel": "structural",
            "verdict": "FAIL",
            "strict_proof": strict,
            "control_risk": True,
            "reason": (
                "A-only uniquely determines answer under supplied fields; "
                + (
                    "strict proof from independent/program evidence"
                    if strict
                    else "fields include engineer_unverified_shortcut_hypothesis — "
                    "NOT independently proven video verification"
                )
            ),
            "trail": trail,
        }
    if loc == "B" and b_has and not bind_needed:
        trail["rules_fired"].append("R2_B_only_answer")
        return {
            "channel": "structural",
            "verdict": "FAIL",
            "strict_proof": strict,
            "control_risk": True,
            "reason": "B-only contains answer payload without A dependency",
            "trail": trail,
        }
    if bind_needed and loc in {"BOTH", "A"} and not (loc == "A" and a_unique):
        trail["rules_fired"].append("R3_bind_required_compositional")
        return {
            "channel": "structural",
            "verdict": "PASS",
            "strict_proof": strict,
            "control_risk": False,
            "reason": "Bind required and answer not uniquely A-local without identity",
            "trail": trail,
        }

    trail["rules_fired"].append("R0_insufficient_to_decide")
    return {
        "channel": "structural",
        "verdict": "UNKNOWN",
        "strict_proof": False,
        "control_risk": False,
        "reason": "evidence present but no decisive structural rule fired",
        "trail": trail,
    }


def shortcut_audit(signals: dict[str, Any]) -> dict[str, Any]:
    """OCR / single-candidate / language-prior / answer-leakage checks."""
    findings = []
    risk = "LOW"
    signal_provenance = signals.get("signal_provenance") or {}
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
        "signals": {k: v for k, v in signals.items() if k != "signal_provenance"},
        "signal_provenance": signal_provenance,
        "blocks_strict_necessity_pass": risk == "HIGH",
    }


def _validate_model_run(run: dict[str, Any] | None, label: str) -> list[str]:
    if run is None:
        return [f"MISSING_RUN:{label}"]
    errs = []
    for k in ("run_id", "model_version", "input_condition", "evidence_isolation", "raw_output"):
        if not run.get(k):
            errs.append(f"MISSING_FIELD:{label}.{k}")
    if run.get("forged") is True:
        errs.append(f"FORGED_RUN:{label}")
    return errs


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
            "verdict": None,
        }

    errs = (
        _validate_model_run(a_only_run, "A_only")
        + _validate_model_run(b_only_run, "B_only")
        + _validate_model_run(ab_run, "A_plus_B")
    )
    if errs:
        return {
            "channel": "model",
            "status": "NOT_RUN",
            "reason": "INCOMPLETE_OR_FORGED_RUNS:" + ",".join(errs),
            "forged": any("FORGED" in e for e in errs),
            "A_only": a_only_run,
            "B_only": b_only_run,
            "A_plus_B": ab_run,
            "verdict": None,
            "validation_errors": errs,
        }

    # Real complete runs only
    a_ok = bool((a_only_run or {}).get("correct"))
    ab_ok = bool((ab_run or {}).get("correct"))
    verdict = None
    if a_ok is False and ab_ok is True:
        verdict = "SUPPORTS_NECESSITY"
    elif a_ok is True:
        verdict = "A_ONLY_SUFFICIENT"
    else:
        verdict = "INCONCLUSIVE"

    return {
        "channel": "model",
        "status": "RUN",
        "forged": False,
        "A_only": a_only_run,
        "B_only": b_only_run,
        "A_plus_B": ab_run,
        "verdict": verdict,
    }


def combine_necessity(
    structural: dict[str, Any],
    model: dict[str, Any],
    shortcut: dict[str, Any],
) -> dict[str, Any]:
    """Overall verdict never promotes to PASS without model RUN + structural support.

    CONTROL inventory may follow high shortcut risk even when structural strict_proof
    is false. Model NOT_RUN cannot yield PASS.
    """
    overall = "UNKNOWN"
    reasons = []
    inventory_hint = "PENDING"
    strict_ok = bool(structural.get("strict_proof"))

    if model.get("status") == "RUN" and model.get("forged"):
        overall = "FAIL"
        reasons.append("forged_model_run_rejected")
        inventory_hint = "REJECT"

    if shortcut.get("blocks_strict_necessity_pass"):
        reasons.append("shortcut:" + ",".join(shortcut.get("findings") or []))
        inventory_hint = "CONTROL"
        # High shortcut → cannot be compositional Gold; may be CONTROL without
        # claiming strict structural FAIL proof.
        if structural.get("verdict") == "FAIL" and strict_ok:
            overall = "FAIL"
            reasons.append("structural_strict_FAIL:" + structural.get("reason", ""))
        elif structural.get("verdict") == "FAIL" and not strict_ok:
            overall = "FAIL"
            reasons.append(
                "structural_FAIL_provisional_not_strict_proof:"
                + structural.get("reason", "")
            )
        elif structural.get("verdict") == "UNKNOWN" and structural.get("control_risk"):
            overall = "FAIL"
            reasons.append(
                "shortcut_HIGH_with_structural_UNKNOWN_control_risk:"
                + structural.get("reason", "")
            )
        else:
            overall = "FAIL"
            reasons.append("shortcut_HIGH_blocks_pass")
    elif structural.get("verdict") == "FAIL":
        overall = "FAIL"
        reasons.append(
            ("structural_strict:" if strict_ok else "structural_provisional:")
            + structural.get("reason", "")
        )
        inventory_hint = "CONTROL"
    elif structural.get("verdict") == "PASS" and model.get("status") == "RUN":
        a = model.get("A_only") or {}
        ab = model.get("A_plus_B") or {}
        if a.get("correct") is False and ab.get("correct") is True:
            overall = "PASS"
            reasons.append("structural_PASS_and_model_A_fail_AB_pass")
            inventory_hint = "CANDIDATE"
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
        "schema": "s6_necessity_combined_v2",
        "overall_verdict": overall,
        "strict_necessity_proof": bool(
            overall == "PASS" and strict_ok and model.get("status") == "RUN"
        ),
        "structural_strict_proof": strict_ok,
        "inventory_hint": inventory_hint,
        "reasons": reasons,
        "structural": structural,
        "model": model,
        "shortcut_audit": shortcut,
        "formal_gold": False,
        "human_identity_does_not_imply_pass": True,
    }
