#!/usr/bin/env python3
"""S7/S9 (Word v1.0): scientific approval status layers + version-ingest release gate.

S7 = 答案与程序图科学审批 (independent statuses).
S9 = 版本入库.

Human relation ≠ QA Gold. Claim ID presence alone is insufficient —
gate checks status, scope, video, windows, evidence hashes, provenance chain.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


STATUS_FIELDS = (
    "human_relation",
    "qa_draft",
    "necessity",
    "program_execution",
    "formal_gold",
)

# Production wiring: S3–S9 conformance modules are invoked via Batch Factory
# `s0_s9_production` as the DEV formal entry. Scientific closed-loop/Gold remains false.
INTERFACE_WIRING = {
    "s3_s9_implementation_modules": [
        "tools/pipeline_conformance/s3_s5_relation_qa.py",
        "tools/pipeline_conformance/s6_necessity.py",
        "tools/pipeline_conformance/s8_signature_feedback.py",
        "tools/pipeline_conformance/s7_s9_gates.py",
        "tools/pipeline_conformance/formal_certification.py",
    ],
    "formal_batch_entry": [
        "tools/lvbench_comp/batch_factory/s0_s9_production.py",
        "tools/lvbench_comp/batch_factory/__main__.py::s0s9-dev-smoke",
    ],
    "legacy_parallel_paths": [
        "tools/lvbench_comp/batch_factory/qa_draft.py",
        "tools/wp3_pipeline_conformance_repair.py",
    ],
    "wired_into_formal_batch_entry": True,
    "production_closed_loop_claimed": False,
    "production_closed_loop_scientific": False,
    "note": (
        "Engineering: S3–S9 wired through batch_factory.s0_s9_production for DEV smoke. "
        "Scientific Gold/closed-loop rates are separate and must not be inferred from wiring."
    ),
}


def independent_status_bundle(
    *,
    human_relation: str,
    qa_draft: str,
    necessity: str,
    program_execution: str = "PROGRAM_EXECUTION_NOT_RUN",
    formal_gold: bool = False,
) -> dict[str, Any]:
    return {
        "schema": "s7_independent_status_v2",
        "human_relation": human_relation,
        "qa_draft": qa_draft,
        "necessity": necessity,
        "program_execution": program_execution,
        "formal_gold": formal_gold,
        "rules": {
            "human_SAME_does_not_set_formal_gold": True,
            "human_SAME_scope_is_identity_only": True,
            "human_SAME_does_not_certify_answer_attributes": True,
            "necessity_FAIL_blocks_gold_review_entry": True,
            "staging_review_status_alone_insufficient": True,
            "program_execution_not_run_blocks_executable_pass": True,
        },
        "interface_wiring": INTERFACE_WIRING,
    }


def load_trusted_claims(records_jsonl: Path) -> dict[str, dict]:
    if not records_jsonl.exists():
        return {}
    out: dict[str, dict] = {}
    for ln in records_jsonl.read_text().splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        cid = r.get("claim_id")
        if cid:
            out[cid] = r
    return out


def load_trusted_claim_ids(records_jsonl: Path) -> set[str]:
    return set(load_trusted_claims(records_jsonl).keys())


def _windows_match(expected: dict | list | None, actual: dict | None) -> bool:
    if expected is None or actual is None:
        return False
    if isinstance(expected, dict):
        for k in ("A", "B"):
            if k in expected and list(expected[k]) != list(actual.get(k) or []):
                return False
        return True
    return False


def validate_claim_against_item(
    claim: dict[str, Any],
    item: dict[str, Any],
) -> list[str]:
    """Return gate failure codes for one trusted claim vs release item."""
    codes: list[str] = []
    if claim.get("decision") != "SAME" and item.get("require_same_decision", True):
        codes.append(f"CLAIM_DECISION_NOT_SAME:{claim.get('claim_id')}")
    scope = claim.get("decision_scope")
    if scope != "CROSS_WINDOW_PERSON_IDENTITY":
        codes.append(f"UNEXPECTED_CLAIM_SCOPE:{scope}")

    # Identity claims must not be used to certify answer attributes
    if item.get("answer_certified_by_human_relation"):
        codes.append("HUMAN_RELATION_MUST_NOT_CERTIFY_ANSWER_ATTRIBUTES")
    does_not = set(claim.get("does_not_certify") or [])
    if "QA_GOLD" not in does_not or "FORMAL_GOLD" not in does_not:
        codes.append(f"CLAIM_MISSING_DOES_NOT_CERTIFY_GOLD:{claim.get('claim_id')}")

    vid = item.get("video_id") or item.get("source_video_id")
    if vid and claim.get("source_video_id") != vid:
        codes.append(
            f"CLAIM_VIDEO_MISMATCH:{claim.get('claim_id')}:{claim.get('source_video_id')}!={vid}"
        )

    item_windows = item.get("windows") or item.get("windows_seconds_map")
    if item_windows and not _windows_match(item_windows, claim.get("windows")):
        codes.append(f"CLAIM_WINDOW_MISMATCH:{claim.get('claim_id')}")

    # Evidence hashes: if item supplies expected clip hashes, they must match registry
    expected_hashes = item.get("clip_sha256") or {}
    claim_hashes = claim.get("clip_sha256") or {}
    for side in ("A", "B"):
        if side in expected_hashes and expected_hashes[side] != claim_hashes.get(side):
            codes.append(f"CLAIM_HASH_MISMATCH:{claim.get('claim_id')}:{side}")

    chain = claim.get("provenance_chain") or []
    if not chain:
        codes.append(f"CLAIM_MISSING_PROVENANCE_CHAIN:{claim.get('claim_id')}")

    if not claim.get("record_id"):
        codes.append(f"CLAIM_MISSING_RECORD_ID:{claim.get('claim_id')}")

    return codes


def release_gate_check(
    item: dict[str, Any],
    *,
    trusted_records_jsonl: Path,
) -> dict[str, Any]:
    """Validate trusted review ↔ release gap before any Gold/import promotion."""
    codes: list[str] = []
    claims = list(item.get("bind_claim_ids") or [])
    trusted = load_trusted_claims(trusted_records_jsonl)
    trusted_ids = set(trusted.keys())
    missing = sorted(set(claims) - trusted_ids)
    if missing:
        codes.append("MISSING_TRUSTED_REGISTRY_CLAIMS:" + ",".join(missing))
    if not claims:
        codes.append("NO_BIND_CLAIMS")

    # Claim ID alone insufficient — validate each present claim's chain
    for cid in claims:
        if cid not in trusted:
            continue
        codes.extend(validate_claim_against_item(trusted[cid], item))

    if item.get("staging_review_status") == "HUMAN_APPROVED" and not claims:
        codes.append("STAGING_HUMAN_APPROVED_WITHOUT_TRUSTED_CLAIMS")
    if item.get("formal_gold") is True:
        codes.append("FORMAL_GOLD_TRUE_BLOCKED_IN_WP3_CONFORMANCE")
    if item.get("necessity_overall") not in {"PASS"}:
        codes.append("NECESSITY_NOT_PASS")
    if item.get("necessity_overall") == "PASS" and item.get("model_necessity_status") == "NOT_RUN":
        codes.append("CANNOT_FULL_PASS_WITHOUT_MODEL_OR_INDEPENDENT_REVIEW")
    if item.get("necessity_strict_proof") is False and item.get("necessity_overall") == "PASS":
        codes.append("STRICT_NECESSITY_PROOF_REQUIRED_FOR_GOLD")
    if item.get("program_execution") not in {"EXECUTABLE_PASS", "PASS"}:
        # Default: not run — blocks Gold
        if item.get("require_program_execution", True):
            codes.append("PROGRAM_EXECUTION_NOT_PASS")
    if item.get("answer_certified_by_human_relation"):
        codes.append("HUMAN_RELATION_MUST_NOT_CERTIFY_ANSWER_ATTRIBUTES")
    if item.get("claim_id_only_without_chain"):
        codes.append("CLAIM_ID_ONLY_WITHOUT_SOURCE_CHAIN")

    # Production closed-loop claim guard
    if item.get("claim_production_closed_loop") and not INTERFACE_WIRING["wired_into_formal_batch_entry"]:
        codes.append("PRODUCTION_CLOSED_LOOP_NOT_WIRED")

    ok = len(codes) == 0
    return {
        "schema": "s9_release_gate_v2",
        "allowed": ok,
        "codes": codes,
        "trusted_claims_present": sorted(set(claims) & trusted_ids),
        "trusted_claims_validated": [
            cid for cid in claims if cid in trusted and not validate_claim_against_item(trusted[cid], item)
        ],
        "formal_gold": False,
        "import_ready": False,
        "interface_wiring": INTERFACE_WIRING,
        "production_closed_loop_claimed": False,
    }
