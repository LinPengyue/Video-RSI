#!/usr/bin/env python3
"""S7/S9: independent status layers + trusted-registry release gate.

Human relation ≠ QA Gold. Staging self-fill cannot mint formal_gold.
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


def independent_status_bundle(
    *,
    human_relation: str,
    qa_draft: str,
    necessity: str,
    program_execution: str = "NOT_RUN",
    formal_gold: bool = False,
) -> dict[str, Any]:
    return {
        "schema": "s7_independent_status_v1",
        "human_relation": human_relation,
        "qa_draft": qa_draft,
        "necessity": necessity,
        "program_execution": program_execution,
        "formal_gold": formal_gold,
        "rules": {
            "human_SAME_does_not_set_formal_gold": True,
            "necessity_FAIL_blocks_gold_review_entry": True,
            "staging_review_status_alone_insufficient": True,
        },
    }


def load_trusted_claim_ids(records_jsonl: Path) -> set[str]:
    if not records_jsonl.exists():
        return set()
    out = set()
    for ln in records_jsonl.read_text().splitlines():
        if not ln.strip():
            continue
        r = json.loads(ln)
        if r.get("claim_id"):
            out.add(r["claim_id"])
    return out


def release_gate_check(
    item: dict[str, Any],
    *,
    trusted_records_jsonl: Path,
) -> dict[str, Any]:
    """Validate trusted review ↔ release gap before any Gold/import promotion."""
    codes: list[str] = []
    claims = set(item.get("bind_claim_ids") or [])
    trusted = load_trusted_claim_ids(trusted_records_jsonl)
    missing = sorted(claims - trusted)
    if missing:
        codes.append("MISSING_TRUSTED_REGISTRY_CLAIMS:" + ",".join(missing))
    if item.get("staging_review_status") == "HUMAN_APPROVED" and not claims:
        codes.append("STAGING_HUMAN_APPROVED_WITHOUT_TRUSTED_CLAIMS")
    if item.get("formal_gold") is True:
        codes.append("FORMAL_GOLD_TRUE_BLOCKED_IN_WP3_CONFORMANCE")
    if item.get("necessity_overall") not in {"PASS"}:
        codes.append("NECESSITY_NOT_PASS")
    if item.get("necessity_overall") == "PASS" and item.get("model_necessity_status") == "NOT_RUN":
        codes.append("CANNOT_FULL_PASS_WITHOUT_MODEL_OR_INDEPENDENT_REVIEW")

    ok = len(codes) == 0
    return {
        "schema": "s9_release_gate_v1",
        "allowed": ok,
        "codes": codes,
        "trusted_claims_present": sorted(claims & trusted),
        "formal_gold": False,
        "import_ready": False,
    }
