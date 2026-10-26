"""Protocol checks: frozen IDs, leakage, resume contamination, cache reuse rules."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def validate_protocol(
    *,
    eval_ids: Iterable[str] | None = None,
    train_ids: Iterable[str] | None = None,
    gate_ids: Iterable[str] | None = None,
    editor_subset_ids: Iterable[str] | None = None,
    arm_ids: dict[str, Iterable[str]] | None = None,
    resume_results_path: Path | None = None,
    expected_config_fingerprint: str | None = None,
    observed_config_fingerprint: str | None = None,
    cache_reuse_allowed: bool = False,
    cache_source: str | None = None,
    cache_compatible: bool | None = None,
    harness_sha_expected: str | None = None,
    harness_sha_observed: str | None = None,
) -> dict[str, Any]:
    reason_codes: list[str] = []
    checks: list[dict] = []

    eval_set = set(eval_ids or [])
    train_set = set(train_ids or [])
    gate_set = set(gate_ids or [])
    editor_set = set(editor_subset_ids or [])

    if eval_set and train_set:
        leak = sorted(eval_set & train_set)
        checks.append({"name": "train_eval_isolation", "status": "FAIL" if leak else "PASS", "n_leak": len(leak)})
        if leak:
            reason_codes.append("train_eval_leak")
    else:
        checks.append({"name": "train_eval_isolation", "status": "NOT_APPLICABLE"})

    if eval_set and gate_set:
        leak = sorted(eval_set & gate_set)
        checks.append({"name": "gate_eval_isolation", "status": "FAIL" if leak else "PASS", "n_leak": len(leak)})
        if leak:
            reason_codes.append("gate_eval_leak")
    else:
        checks.append({"name": "gate_eval_isolation", "status": "NOT_APPLICABLE"})

    if eval_set and editor_set:
        leak = sorted(eval_set & editor_set)
        checks.append({"name": "editor_eval_isolation", "status": "FAIL" if leak else "PASS", "n_leak": len(leak)})
        if leak:
            reason_codes.append("editor_eval_leak")
    else:
        checks.append({"name": "editor_eval_isolation", "status": "NOT_APPLICABLE"})

    if arm_ids:
        sets = {k: set(v) for k, v in arm_ids.items()}
        ref_name, ref = next(iter(sets.items()))
        mismatch = False
        for name, s in sets.items():
            if s != ref:
                mismatch = True
                reason_codes.append("arm_id_mismatch:%s_vs_%s" % (name, ref_name))
        checks.append({"name": "arm_same_eval_ids", "status": "FAIL" if mismatch else "PASS"})

    if resume_results_path is not None:
        if resume_results_path.is_file():
            if expected_config_fingerprint and observed_config_fingerprint:
                if expected_config_fingerprint != observed_config_fingerprint:
                    reason_codes.append("resume_config_fingerprint_mismatch")
                    checks.append({"name": "resume_fingerprint", "status": "FAIL"})
                else:
                    checks.append({"name": "resume_fingerprint", "status": "PASS"})
            else:
                checks.append(
                    {
                        "name": "resume_fingerprint",
                        "status": "FAIL" if expected_config_fingerprint else "NOT_APPLICABLE",
                        "note": "Resume path present but fingerprints incomplete",
                    }
                )
                if expected_config_fingerprint and not observed_config_fingerprint:
                    reason_codes.append("resume_without_observed_fingerprint")
        else:
            checks.append({"name": "resume_fingerprint", "status": "NOT_APPLICABLE"})

    if cache_reuse_allowed:
        if cache_compatible is False:
            reason_codes.append("incompatible_cache_reuse")
            checks.append({"name": "cache_reuse", "status": "FAIL", "source": cache_source})
        elif cache_compatible is True:
            checks.append({"name": "cache_reuse", "status": "PASS", "source": cache_source})
        else:
            reason_codes.append("cache_reuse_unverified")
            checks.append({"name": "cache_reuse", "status": "FAIL", "source": cache_source})
    else:
        if cache_source:
            reason_codes.append("cache_reuse_not_allowed_but_source_present")
            checks.append({"name": "cache_reuse", "status": "FAIL", "source": cache_source})
        else:
            checks.append({"name": "cache_reuse", "status": "NOT_APPLICABLE"})

    if harness_sha_expected and harness_sha_observed:
        if harness_sha_expected != harness_sha_observed:
            reason_codes.append("harness_sha_mismatch")
            checks.append({"name": "harness_version", "status": "FAIL"})
        else:
            checks.append({"name": "harness_version", "status": "PASS"})
    else:
        checks.append({"name": "harness_version", "status": "NOT_APPLICABLE"})

    status = "FAIL" if reason_codes else "PASS"
    return {
        "status": status,
        "reason_codes": reason_codes,
        "checks": checks,
        "usable_for_architecture_ranking": status == "PASS",
    }


def load_id_list(path: Path, key: str = "sample_ids") -> list[str]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return list(data)
    return list(data[key])
