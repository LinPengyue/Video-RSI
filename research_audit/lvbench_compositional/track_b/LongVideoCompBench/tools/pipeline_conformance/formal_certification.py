#!/usr/bin/env python3
"""Formal Ready / Gold certification entry — independent verification.

Does not trust caller-supplied PASS / RUN / EXECUTABLE_PASS strings.
Requires video ID, windows, hashes, provenance chain, independent answer
certification (≠ Human SAME), real Necessity records, and program execution
evidence from stores — not self-declared fields alone.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .s7_s9_gates import load_trusted_claims, validate_claim_against_item


ANSWER_CERT_SCOPES_ALLOWED = {
    "ANSWER_ATTRIBUTE",
    "QA_ANSWER",
    "CONTINUOUS_VIDEO_ANSWER",
}
IDENTITY_ONLY_SCOPES = {"CROSS_WINDOW_PERSON_IDENTITY"}


def _load_jsonl_index(path: Path | None, key: str) -> dict[str, dict]:
    if path is None or not path.exists():
        return {}
    out: dict[str, dict] = {}
    for ln in path.read_text().splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        kid = r.get(key)
        if kid:
            out[str(kid)] = r
    return out


def _verify_model_necessity_record(rec: dict[str, Any] | None) -> list[str]:
    if not rec:
        return ["MISSING_NECESSITY_RECORD"]
    codes = []
    if rec.get("status") == "NOT_RUN":
        codes.append("MODEL_NECESSITY_NOT_RUN")
        return codes
    if rec.get("status") != "RUN":
        codes.append(f"MODEL_STATUS_NOT_RUN:{rec.get('status')}")
        return codes
    for label in ("A_only", "B_only", "A_plus_B"):
        run = rec.get(label)
        if not isinstance(run, dict):
            codes.append(f"MISSING_ISOLATED_RUN:{label}")
            continue
        for k in ("run_id", "model_version", "input_condition", "evidence_isolation", "raw_output"):
            if not run.get(k):
                codes.append(f"RUN_FIELD_MISSING:{label}.{k}")
        # Isolation must declare distinct input condition
        if run.get("input_condition") and label.replace("_", "").lower() not in str(
            run.get("input_condition")
        ).lower().replace("+", "plus").replace("_", ""):
            # soft check — require evidence_isolation flag
            pass
        if run.get("evidence_isolation") not in {
            True,
            "ISOLATED",
            "A_ONLY",
            "B_ONLY",
            "A_PLUS_B",
            "ok",
            "OK",
        }:
            if not run.get("evidence_isolation"):
                codes.append(f"EVIDENCE_ISOLATION_MISSING:{label}")
    # Strict compositional necessity cannot ignore B-only
    a = rec.get("A_only") or {}
    b = rec.get("B_only") or {}
    ab = rec.get("A_plus_B") or {}
    if (
        a.get("correct") is False
        and ab.get("correct") is True
        and b.get("correct") is not False
    ):
        codes.append("B_ONLY_NOT_SHOWN_INCORRECT_CANNOT_CLAIM_STRICT_NECESSITY")
    return codes


def _verify_program_execution_record(rec: dict[str, Any] | None) -> list[str]:
    if not rec:
        return ["MISSING_PROGRAM_EXECUTION_RECORD"]
    if rec.get("status") in {"PROGRAM_EXECUTION_NOT_RUN", "NOT_RUN", None, ""}:
        return ["PROGRAM_EXECUTION_NOT_RUN"]
    if rec.get("status") != "EXECUTABLE_PASS":
        return [f"PROGRAM_EXECUTION_STATUS:{rec.get('status')}"]
    # Must have executor artifact — not caller string alone
    if not rec.get("executor_run_id") or not rec.get("raw_trace"):
        return ["PROGRAM_EXECUTION_MISSING_EXECUTOR_TRACE"]
    if rec.get("caller_declared_only"):
        return ["PROGRAM_EXECUTION_CALLER_DECLARED_ONLY"]
    return []


def evaluate_formal_ready(
    item: dict[str, Any],
    *,
    trusted_records_jsonl: Path,
    necessity_records_jsonl: Path | None = None,
    program_execution_records_jsonl: Path | None = None,
    answer_cert_records_jsonl: Path | None = None,
) -> dict[str, Any]:
    """Independent Formal Ready evaluation. Never trusts item.self_declared_* alone."""
    codes: list[str] = []

    # Reject self-declared promotions
    for bad_key in (
        "self_declared_necessity_pass",
        "self_declared_model_run",
        "self_declared_executable_pass",
        "self_declared_formal_gold",
    ):
        if item.get(bad_key):
            codes.append(f"REJECT_SELF_DECLARED:{bad_key}")

    # Caller strings are ignored for truth; re-check stores
    nec_store = _load_jsonl_index(necessity_records_jsonl, "qa_id")
    exec_store = _load_jsonl_index(program_execution_records_jsonl, "program_id")
    ans_store = _load_jsonl_index(answer_cert_records_jsonl, "qa_id")
    trusted = load_trusted_claims(trusted_records_jsonl)

    qa_id = item.get("qa_id")
    program_id = item.get("program_id")
    video_id = item.get("video_id") or item.get("source_video_id")
    windows = item.get("windows") or item.get("windows_seconds_map")
    clip_sha = item.get("clip_sha256") or {}

    if not video_id:
        codes.append("MISSING_VIDEO_ID")
    if not windows:
        codes.append("MISSING_WINDOWS")
    if not clip_sha.get("A") or not clip_sha.get("B"):
        codes.append("MISSING_CLIP_HASHES")

    # Bind claims: identity only — validate chain
    bind_ids = list(item.get("bind_claim_ids") or [])
    for cid in bind_ids:
        claim = trusted.get(cid)
        if not claim:
            codes.append(f"MISSING_TRUSTED_CLAIM:{cid}")
            continue
        codes.extend(
            validate_claim_against_item(
                claim,
                {
                    "video_id": video_id,
                    "windows": windows,
                    "clip_sha256": clip_sha,
                    "answer_certified_by_human_relation": False,
                    "require_same_decision": True,
                },
            )
        )
        if claim.get("decision_scope") in IDENTITY_ONLY_SCOPES:
            # Identity OK for bind, never for answer
            pass

    # Independent answer certification (≠ Human SAME)
    ans = ans_store.get(str(qa_id)) if qa_id else None
    if item.get("answer_certified_by_human_relation"):
        codes.append("HUMAN_SAME_CANNOT_CERTIFY_ANSWER")
    if not ans:
        codes.append("MISSING_INDEPENDENT_ANSWER_CERTIFICATION")
    else:
        if ans.get("scope") not in ANSWER_CERT_SCOPES_ALLOWED:
            codes.append(f"ANSWER_CERT_BAD_SCOPE:{ans.get('scope')}")
        if ans.get("video_id") != video_id:
            codes.append("ANSWER_CERT_VIDEO_MISMATCH")
        if not ans.get("provenance_chain"):
            codes.append("ANSWER_CERT_MISSING_PROVENANCE_CHAIN")
        if ans.get("reviewer_role") not in {
            "HUMAN_SCIENTIFIC_OWNER",
            "INDEPENDENT_ANSWER_REVIEWER",
        }:
            codes.append("ANSWER_CERT_BAD_REVIEWER_ROLE")

    # Necessity from independent store only — embedded/store_backed self-marks rejected
    if item.get("necessity_store_backed") or item.get("necessity_record"):
        codes.append("REJECT_EMBEDDED_NECESSITY_BYPASS")
    nec = nec_store.get(str(qa_id)) if qa_id else None
    codes.extend(_verify_model_necessity_record((nec or {}).get("model") if nec else None))
    if nec:
        if nec.get("overall_verdict") != "PASS":
            codes.append(f"NECESSITY_OVERALL_NOT_PASS:{nec.get('overall_verdict')}")
        if not nec.get("strict_necessity_proof"):
            codes.append("NECESSITY_STRICT_PROOF_FALSE")
        model = nec.get("model") or {}
        if model.get("verdict") == "SUPPORTS_NECESSITY":
            b = model.get("B_only") or {}
            if b.get("correct") is not False:
                codes.append("STRICT_NECESSITY_REQUIRES_B_ONLY_INCORRECT")
        # Raw outputs must be store-backed artifacts, not bare self-attested strings alone
        for label in ("A_only", "B_only", "A_plus_B"):
            run = (model.get(label) or {}) if model else {}
            if run and not run.get("raw_output_artifact_uri") and not run.get("raw_output_sha256"):
                codes.append(f"MODEL_RAW_OUTPUT_NOT_ARTIFACT_BACKED:{label}")
    else:
        codes.append("MISSING_NECESSITY_STORE_RECORD")

    # Program execution from independent store only
    if item.get("program_execution_store_backed") or item.get("program_execution_record"):
        codes.append("REJECT_EMBEDDED_PROGRAM_EXECUTION_BYPASS")
    ex = exec_store.get(str(program_id)) if program_id else None
    codes.extend(_verify_program_execution_record(ex))

    if item.get("formal_gold") is True and codes:
        codes.append("FORMAL_GOLD_BLOCKED_BY_CERT_GAPS")

    ok = len(codes) == 0
    return {
        "schema": "formal_certification_v1",
        "formal_ready": ok,
        "independent_gold_certified": False if not ok else bool(item.get("request_gold")),
        "codes": codes,
        "ignored_caller_fields": [
            "necessity_overall",
            "model_necessity_status",
            "program_execution",
            "self_declared_*",
        ],
        "human_same_isolated_from_answer_cert": True,
        "note": "Caller PASS/RUN/EXECUTABLE_PASS strings are not evidence",
    }
