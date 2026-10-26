"""Layer 2: Runtime Guard — per-sample validity + batch fail-closed abort."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


VISUAL_TOOLS = ("overview", "scan_interval", "inspect_interval", "read_text")

# Error taxonomy (not model wrong answers)
ENGINEERING_ERROR = "ENGINEERING_ERROR"
MODEL_ERROR = "MODEL_ERROR"
TASK_FAILURE = "TASK_FAILURE"


def classify_error_kind(result: dict) -> str | None:
    """Classify top-level failure mode for a run_item-like result."""
    status = result.get("status")
    usage = result.get("usage") or {}
    mem = result.get("memory") or []
    trace = result.get("service_trace") or []
    diag = result.get("diagnostics") or {}

    infra_markers = (
        "imageio_ffmpeg",
        "ModuleNotFoundError",
        "ffmpeg",
        "No such file",
        "sample_frames",
    )
    blob = json_safe_blob(result)
    if any(m in blob for m in ("imageio_ffmpeg", "ModuleNotFoundError")):
        return ENGINEERING_ERROR
    for e in trace:
        if e.get("service") == "sample_frames" and e.get("error"):
            return ENGINEERING_ERROR
    if int(diag.get("tool_execution_errors") or 0) > 0:
        # May be engineering or model tool misuse — inspect messages
        for m in mem:
            obs = m.get("observation") or {}
            if isinstance(obs, dict) and obs.get("error"):
                msg = str(obs.get("message") or obs.get("error") or "")
                if any(x in msg for x in infra_markers):
                    return ENGINEERING_ERROR
        if status == "engineering_error":
            return ENGINEERING_ERROR
    if status in ("provider_error", "timeout") or "provider" in str(status):
        return MODEL_ERROR  # provider/model path
    if status in ("answered", "ok", "completed"):
        return None
    if status in ("failed", "wrong", "no_answer"):
        return TASK_FAILURE
    return None


def json_safe_blob(obj: Any) -> str:
    try:
        import json

        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


def classify_item_run(result: dict) -> dict[str, Any]:
    """Case A / B / C classification for one harness (or similar) result.

    Case A: intentional no-vision — VALID_RUN
    Case B: vision requested, all failed due to infra — INVALID_RUN
    Case C: partial success — DEGRADED_RUN
    """
    usage = result.get("usage") or {}
    mem = result.get("memory") or []
    trace = result.get("service_trace") or []
    diag = result.get("diagnostics") or {}

    visual_requests = 0
    visual_errors = 0
    visual_ok = 0
    already_observed_stubs = 0
    sample_frames_errors: list[str] = []
    qwen_events = 0

    for m in mem:
        tool = m.get("tool")
        if tool not in VISUAL_TOOLS:
            continue
        visual_requests += 1
        obs = m.get("observation") or {}
        if isinstance(obs, dict) and obs.get("error"):
            visual_errors += 1
        elif isinstance(obs, dict) and obs.get("already_observed"):
            already_observed_stubs += 1
        elif isinstance(obs, dict) and (obs.get("frames") or obs.get("perception") or "text" in obs):
            if obs.get("error"):
                visual_errors += 1
            else:
                visual_ok += 1

    for e in trace:
        if e.get("service") == "sample_frames" and e.get("error"):
            sample_frames_errors.append(str(e.get("error"))[:200])
        if e.get("service") == "qwen":
            qwen_events += 1

    _missing_mod = "No module named 'imageio_ffmpeg'"
    _missing_mod2 = 'No module named "imageio_ffmpeg"'
    blob = json_safe_blob({"memory": mem, "service_trace": trace})
    ffmpeg_missing = any(_missing_mod in err or _missing_mod2 in err for err in sample_frames_errors) or (
        _missing_mod in blob or _missing_mod2 in blob
    )
    tool_exec_errors = int(diag.get("tool_execution_errors") or 0)
    qwen_frames = int(usage.get("qwen_frames") or 0)
    frames_extracted = int(usage.get("frames_extracted") or 0)

    intentional_no_vision = visual_requests == 0 and not sample_frames_errors and qwen_frames == 0
    vision_tooling_failed = bool(sample_frames_errors) or (
        visual_requests > 0 and visual_ok == 0 and visual_errors > 0
    )
    partial_vision = visual_requests > 0 and visual_ok > 0 and (visual_errors > 0 or sample_frames_errors)
    meter_inconsistent = (qwen_events > 0 and qwen_frames == 0) or (
        frames_extracted > 0 and qwen_frames == 0 and qwen_events > 0
    )

    reasons: list[str] = []
    if ffmpeg_missing:
        reasons.append("imageio_ffmpeg_missing")
    if vision_tooling_failed:
        reasons.append("visual_tooling_failed")
    if meter_inconsistent:
        reasons.append("meter_inconsistent_with_trace")
    if tool_exec_errors > 0 and visual_requests > 0 and visual_ok == 0:
        if "visual_tooling_failed" not in reasons:
            reasons.append("tool_execution_errors_without_success")

    if vision_tooling_failed or ffmpeg_missing or meter_inconsistent:
        validity = "INVALID_RUN"
        case = "B"
    elif partial_vision:
        validity = "DEGRADED_RUN"
        case = "C"
        if "partial_vision_failures" not in reasons:
            reasons.append("partial_vision_failures")
    else:
        validity = "VALID_RUN"
        case = "A" if intentional_no_vision else "HEALTHY_VISION"

    error_kind = classify_error_kind(result)
    if validity == "INVALID_RUN" and error_kind is None:
        error_kind = ENGINEERING_ERROR

    return {
        "sample_id": result.get("sample_id"),
        "agent_status": result.get("status"),
        "case": case,
        "run_valid": validity == "VALID_RUN",
        "validity": validity,
        "reasons": reasons,
        "error_kind": error_kind,
        "intentional_no_vision": intentional_no_vision,
        "vision_tooling_failed": vision_tooling_failed,
        "partial_vision": partial_vision,
        "visual_requests": visual_requests,
        "visual_ok": visual_ok,
        "visual_errors": visual_errors,
        "already_observed_stubs": already_observed_stubs,
        "sample_frames_error_count": len(sample_frames_errors),
        "sample_frames_errors_head": sample_frames_errors[:3],
        "qwen_events": qwen_events,
        "qwen_frames": qwen_frames,
        "frames_extracted": frames_extracted,
        "deepseek_calls": usage.get("deepseek_calls"),
        "answered_letter": result.get("answer") if result.get("status") in ("answered", "ok") else None,
        "note": (
            "Answer under INVALID_RUN must not enter architecture accuracy tables."
            if validity == "INVALID_RUN"
            else (
                "DEGRADED_RUN inclusion is protocol-defined; do not change rules after seeing accuracy."
                if validity == "DEGRADED_RUN"
                else "VALID_RUN may still have intentional_no_vision=True."
            )
        ),
    }


@dataclass
class BatchAbortPolicy:
    """Fail-closed batch stopping rules (outer runner only)."""

    abort_on_first_infra_sample_frames_error: bool = True
    abort_on_repeated_infra: int = 2  # same reason_code streak
    abort_on_meter_inconsistency: bool = True
    abort_on_fingerprint_change: bool = True
    max_invalid_fraction: float | None = None  # optional soft stop

    def should_abort(
        self,
        assessments: list[dict],
        *,
        start_fingerprint: str | None = None,
        current_fingerprint: str | None = None,
    ) -> tuple[bool, str | None]:
        if (
            self.abort_on_fingerprint_change
            and start_fingerprint
            and current_fingerprint
            and start_fingerprint != current_fingerprint
        ):
            return True, "config_or_harness_fingerprint_changed"

        infra_streak = 0
        last_reason = None
        for a in assessments:
            reasons = a.get("reasons") or []
            is_infra = any(
                r in reasons
                for r in (
                    "imageio_ffmpeg_missing",
                    "visual_tooling_failed",
                    "meter_inconsistent_with_trace",
                )
            )
            if self.abort_on_meter_inconsistency and "meter_inconsistent_with_trace" in reasons:
                return True, "meter_inconsistent_with_trace"
            if is_infra and self.abort_on_first_infra_sample_frames_error:
                if "imageio_ffmpeg_missing" in reasons or a.get("sample_frames_error_count", 0) > 0:
                    return True, "systematic_sample_frames_infra_error"
            if is_infra:
                key = tuple(sorted(reasons)) or ("infra",)
                if key == last_reason:
                    infra_streak += 1
                else:
                    infra_streak = 1
                    last_reason = key
                if infra_streak >= self.abort_on_repeated_infra:
                    return True, "repeated_infrastructure_failure"
            else:
                infra_streak = 0
                last_reason = None

        if self.max_invalid_fraction is not None and assessments:
            inv = sum(1 for a in assessments if a.get("validity") == "INVALID_RUN")
            if inv / len(assessments) >= self.max_invalid_fraction:
                return True, "invalid_run_fraction_exceeded"
        return False, None


@dataclass
class RuntimeGuard:
    policy: BatchAbortPolicy = field(default_factory=BatchAbortPolicy)
    assessments: list[dict] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str | None = None
    start_fingerprint: str | None = None

    def observe_result(self, result: dict, *, current_fingerprint: str | None = None) -> dict:
        a = classify_item_run(result)
        self.assessments.append(a)
        stop, reason = self.policy.should_abort(
            self.assessments,
            start_fingerprint=self.start_fingerprint,
            current_fingerprint=current_fingerprint,
        )
        if stop:
            self.aborted = True
            self.abort_reason = reason
        return a

    def summary(self) -> dict:
        c = Counter(a["validity"] for a in self.assessments)
        return {
            "n": len(self.assessments),
            "by_validity": dict(c),
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "assessments": self.assessments,
        }
