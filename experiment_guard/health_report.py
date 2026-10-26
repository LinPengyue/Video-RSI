"""Unified Experiment Health Report (JSON + Markdown, desensitized)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment_guard.redact import redact_obj


def build_health_report(
    *,
    experiment_id: str,
    preflight: dict | None = None,
    arm_validation: dict | None = None,
    multi_arm: dict | None = None,
    protocol: dict | None = None,
    runtime_summary: dict | None = None,
    code_sha: str | None = None,
    harness_sha: str | None = None,
    config_fingerprint: str | None = None,
    environment: dict | None = None,
    cost: dict | None = None,
    diagnostic_paths: list[str] | None = None,
    extra: dict | None = None,
) -> dict[str, Any]:
    samples = {"total": 0, "valid": 0, "invalid": 0, "degraded": 0}
    qwen = {"mean": None, "min": None, "max": None, "total": 0}
    visual_success_rate = None
    tool_errors: dict = {}
    provider_errors: dict = {}

    src = arm_validation or (multi_arm or {}).get("arms", {})
    if isinstance(src, dict) and "n" in src:
        samples = {
            "total": src.get("n", 0),
            "valid": src.get("n_valid_run", 0),
            "invalid": src.get("n_invalid_run", 0),
            "degraded": src.get("n_degraded_run", 0),
        }
        qwen = src.get("qwen_frames") or qwen
        visual_success_rate = src.get("visual_success_rate")
    elif isinstance(src, dict) and src and "n" not in src:
        # multi-arm map
        totals = {"total": 0, "valid": 0, "invalid": 0, "degraded": 0}
        frames = []
        for arm in src.values():
            if not isinstance(arm, dict):
                continue
            totals["total"] += arm.get("n", 0)
            totals["valid"] += arm.get("n_valid_run", 0)
            totals["invalid"] += arm.get("n_invalid_run", 0)
            totals["degraded"] += arm.get("n_degraded_run", 0)
            qf = arm.get("qwen_frames") or {}
            if qf.get("mean") is not None:
                frames.append(qf)
        samples = totals
        if frames:
            qwen = {
                "mean": sum(f["mean"] for f in frames) / len(frames),
                "min": min(f["min"] for f in frames if f.get("min") is not None),
                "max": max(f["max"] for f in frames if f.get("max") is not None),
                "total": sum(f.get("total") or 0 for f in frames),
            }

    if runtime_summary:
        tool_errors = dict(runtime_summary.get("by_validity") or {})

    overall = "VALID"
    reason_codes: list[str] = []
    if preflight and preflight.get("status") == "FAIL":
        overall = "INVALID"
        reason_codes.extend(preflight.get("reason_codes") or ["preflight_fail"])
    if protocol and protocol.get("status") in ("FAIL", "INCOMPLETE"):
        if protocol.get("status") == "FAIL":
            overall = "INVALID"
        elif overall != "INVALID":
            overall = "PARTIALLY_VALID"
        reason_codes.extend(protocol.get("reason_codes") or ["protocol_fail"])
    if arm_validation:
        ov = arm_validation.get("overall_validity")
        if ov == "INVALID":
            overall = "INVALID"
        elif ov == "PARTIALLY_VALID" and overall != "INVALID":
            overall = "PARTIALLY_VALID"
        reason_codes.extend(arm_validation.get("reason_codes") or [])
    if multi_arm:
        ov = multi_arm.get("overall_validity")
        if ov == "INVALID":
            overall = "INVALID"
        elif ov == "PARTIALLY_VALID" and overall != "INVALID":
            overall = "PARTIALLY_VALID"
        reason_codes.extend(multi_arm.get("reason_codes") or [])

    # de-dupe reason codes preserving order
    seen = set()
    uniq = []
    for r in reason_codes:
        if r not in seen:
            seen.add(r)
            uniq.append(r)

    report = {
        "experiment_id": experiment_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_sha": code_sha or (preflight or {}).get("code_sha"),
        "harness_sha": harness_sha or ((preflight or {}).get("harness") or {}).get("sha16"),
        "config_fingerprint": config_fingerprint or (preflight or {}).get("config_fingerprint"),
        "environment": environment or (preflight or {}).get("host"),
        "preflight": (preflight or {}).get("status", "NOT_APPLICABLE"),
        "samples": samples,
        "visual_success_rate": visual_success_rate,
        "qwen_frames": qwen,
        "tool_errors": tool_errors,
        "provider_errors": provider_errors,
        "cost": cost or {},
        "protocol_validation": (protocol or {}).get("status", "NOT_APPLICABLE"),
        "overall_validity": overall,
        "reason_codes": uniq,
        "usable_for_architecture_ranking": overall == "VALID",
        "diagnostic_paths": diagnostic_paths or [],
        "runtime_aborted": (runtime_summary or {}).get("aborted"),
        "runtime_abort_reason": (runtime_summary or {}).get("abort_reason"),
        "extra": extra or {},
    }
    return redact_obj(report)


def render_markdown(report: dict) -> str:
    lines = [
        "# Experiment Health Report",
        "",
        "| Metric | Value |",
        "|---|---|",
        "| Experiment ID | `%s` |" % report.get("experiment_id"),
        "| Code SHA | `%s` |" % report.get("code_sha"),
        "| Harness SHA | `%s` |" % report.get("harness_sha"),
        "| Config Fingerprint | `%s` |" % report.get("config_fingerprint"),
        "| Environment | `%s` |" % json.dumps(report.get("environment") or {}, ensure_ascii=False),
        "| Preflight | **%s** |" % report.get("preflight"),
        "| Samples (T/V/I/D) | %s / %s / %s / %s |"
        % (
            (report.get("samples") or {}).get("total"),
            (report.get("samples") or {}).get("valid"),
            (report.get("samples") or {}).get("invalid"),
            (report.get("samples") or {}).get("degraded"),
        ),
        "| Visual Success Rate | %s |" % report.get("visual_success_rate"),
        "| Qwen Frames (mean/min/max) | %s / %s / %s |"
        % (
            (report.get("qwen_frames") or {}).get("mean"),
            (report.get("qwen_frames") or {}).get("min"),
            (report.get("qwen_frames") or {}).get("max"),
        ),
        "| Tool Errors | `%s` |" % json.dumps(report.get("tool_errors") or {}),
        "| Provider Errors | `%s` |" % json.dumps(report.get("provider_errors") or {}),
        "| Cost | `%s` |" % json.dumps(report.get("cost") or {}),
        "| Protocol Validation | **%s** |" % report.get("protocol_validation"),
        "| Overall Validity | **%s** |" % report.get("overall_validity"),
        "",
        "## Reason codes",
        "",
    ]
    codes = report.get("reason_codes") or []
    if codes:
        for c in codes:
            lines.append("- `%s`" % c)
    else:
        lines.append("- (none)")
    lines.extend(["", "## Diagnostic paths", ""])
    for p in report.get("diagnostic_paths") or []:
        lines.append("- `%s`" % p)
    if not report.get("diagnostic_paths"):
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "## Ranking usability",
            "",
            "usable_for_architecture_ranking = **%s**" % report.get("usable_for_architecture_ranking"),
            "",
            "> Answers produced under INVALID_RUN must not be treated as healthy Video Agent architecture evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def write_health_report(report: dict, out_dir: Path, stem: str = "experiment_health") -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / ("%s.json" % stem)
    md_path = out_dir / ("%s.md" % stem)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "md": md_path}
