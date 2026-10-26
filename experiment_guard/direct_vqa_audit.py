"""Normalize Direct VQA call records into Guard-auditable per-item results.

Does not invent qwen_frames or success status — only maps real provider/frame evidence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from experiment_guard.fingerprint_snapshot import frame_bundle_hash
from experiment_guard.fingerprints import sha256_file


def expected_direct_meta(
    *,
    sample_id: str,
    prompt_sha: str,
    prompt_version: str,
    request_model: str,
    timestamps: list[float],
    config_fingerprint: str,
    harness_sha: str | None = None,
) -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "prompt_sha": prompt_sha,
        "prompt_version": prompt_version,
        "request_model": request_model,
        "timestamps": [float(t) for t in timestamps],
        "n_frames_expected": len(timestamps),
        "config_fingerprint": config_fingerprint,
        "harness_sha": harness_sha,
        "frame_sample_protocol": "uniform_32_or_overview_bundle",
    }


def assess_direct_vqa_reuse(existing: dict | None, expected: dict) -> dict[str, Any]:
    """Prove cache compatibility. status=ok alone is never sufficient."""
    if not existing:
        return {"compatible": False, "reasons": ["no_existing_record"]}
    reasons: list[str] = []
    if existing.get("status") != "ok":
        return {"compatible": False, "reasons": ["status_not_ok:%s" % existing.get("status")]}
    if existing.get("prompt_version") != expected.get("prompt_version"):
        return {"compatible": False, "reasons": ["prompt_version_mismatch"]}
    if existing.get("prompt_sha") != expected.get("prompt_sha"):
        return {"compatible": False, "reasons": ["prompt_sha_mismatch"]}
    if expected.get("request_model") and existing.get("request_model") != expected.get("request_model"):
        return {"compatible": False, "reasons": ["request_model_mismatch"]}

    n = int(existing.get("n_frames") or 0)
    if n <= 0:
        return {"compatible": False, "reasons": ["n_frames_nonpositive"]}
    if n != int(expected.get("n_frames_expected") or 0):
        return {"compatible": False, "reasons": ["frame_count_mismatch"]}

    if existing.get("config_fingerprint") and expected.get("config_fingerprint"):
        if existing["config_fingerprint"] != expected["config_fingerprint"]:
            return {"compatible": False, "reasons": ["config_fingerprint_mismatch"]}

    if existing.get("harness_sha") and expected.get("harness_sha"):
        if existing["harness_sha"] != expected["harness_sha"]:
            return {"compatible": False, "reasons": ["harness_sha_mismatch"]}

    existing_ts = existing.get("timestamps")
    if existing_ts is not None:
        exp_ts = [float(t) for t in expected.get("timestamps") or []]
        got_ts = [float(t) for t in existing_ts]
        if got_ts != exp_ts:
            return {"compatible": False, "reasons": ["timestamp_mismatch"]}
    else:
        # Legacy Phase D records omit timestamps — only accept if prompt_sha + n_frames
        # already matched expected protocol (proven above). Record the inference.
        reasons.append("legacy_timestamps_inferred_from_prompt_sha_and_n_frames")

    if existing.get("frame_bundle_sha") and expected.get("frame_bundle_sha"):
        if existing["frame_bundle_sha"] != expected["frame_bundle_sha"]:
            return {"compatible": False, "reasons": ["frame_bundle_sha_mismatch"]}

    return {"compatible": True, "reasons": reasons or ["full_meta_match"]}


def hash_frame_paths(paths: list[Path]) -> list[str]:
    out = []
    for p in paths:
        digest = sha256_file(Path(p))
        out.append(digest[:16] if digest else "missing")
    return out


def normalize_direct_vqa_record(rec: dict) -> dict[str, Any]:
    """Convert a Direct VQA store record into a classify_item_run-compatible result.

    Never fabricates successful vision evidence. Uses only fields present on `rec`.
    """
    sid = rec.get("sample_id")
    status_raw = rec.get("status")
    n_frames = int(rec.get("n_frames") or 0)
    timestamps = rec.get("timestamps")
    frame_hashes = rec.get("frame_path_hashes") or []
    error = rec.get("error") or ""
    answer = rec.get("answer")

    usage = {
        "qwen_frames": n_frames if status_raw == "ok" and n_frames > 0 else 0,
        "frames_extracted": n_frames if n_frames > 0 and status_raw in ("ok", "parse_error") else 0,
        "qwen_calls": 1 if status_raw in ("ok", "parse_error", "provider_error") else 0,
        "deepseek_calls": 0,
        "prompt_tokens": (rec.get("usage") or {}).get("prompt_tokens"),
        "completion_tokens": (rec.get("usage") or {}).get("completion_tokens"),
        "estimated_cny": rec.get("estimated_cny"),
    }

    memory: list[dict] = []
    service_trace: list[dict] = []
    diagnostics: dict[str, Any] = {}

    extract_error = rec.get("extract_error")
    if extract_error:
        memory.append(
            {
                "tool": "overview",
                "observation": {"error": "extract_frames", "message": str(extract_error)[:400]},
            }
        )
        service_trace.append({"service": "sample_frames", "error": str(extract_error)[:200]})
        diagnostics["tool_execution_errors"] = 1
        agent_status = "engineering_error"
    elif status_raw == "provider_error":
        # Vision was attempted; provider failed after/during frame send
        if n_frames > 0 or timestamps:
            memory.append(
                {
                    "tool": "overview",
                    "observation": {
                        "error": "provider_error",
                        "message": error or "qwen_provider_error",
                        "frames": ["f%d" % i for i in range(max(n_frames, 1))],
                    },
                }
            )
            service_trace.append({"service": "sample_frames", "n_frames": n_frames, "timestamps": timestamps})
            service_trace.append({"service": "qwen", "error": error or "provider_error", "frames": n_frames})
            # Meter inconsistency if frames claimed but qwen failed with 0 recorded success
            usage["qwen_frames"] = 0
            diagnostics["tool_execution_errors"] = 1
        else:
            memory.append(
                {
                    "tool": "overview",
                    "observation": {"error": "provider_error", "message": error or "provider_error"},
                }
            )
            service_trace.append({"service": "qwen", "error": error or "provider_error"})
            diagnostics["tool_execution_errors"] = 1
        agent_status = "provider_error"
    elif status_raw == "ok" and n_frames > 0:
        memory.append(
            {
                "tool": "overview",
                "observation": {
                    "text": "direct_vqa",
                    "frames": ["f%d" % i for i in range(n_frames)],
                    "timestamps": timestamps,
                    "frame_path_hashes": frame_hashes,
                },
            }
        )
        service_trace.append(
            {
                "service": "sample_frames",
                "n_frames": n_frames,
                "timestamps": timestamps,
                "frame_bundle_sha": rec.get("frame_bundle_sha"),
            }
        )
        service_trace.append({"service": "qwen", "frames": n_frames, "status": "ok"})
        agent_status = "answered"
    elif status_raw == "ok" and n_frames <= 0:
        # Claimed ok without frames — invalid evidence
        memory.append(
            {
                "tool": "overview",
                "observation": {"error": "meter", "message": "status_ok_but_n_frames_zero"},
            }
        )
        service_trace.append({"service": "qwen", "frames": 0, "status": "ok"})
        diagnostics["tool_execution_errors"] = 1
        agent_status = "answered"
        usage["qwen_frames"] = 0
    elif status_raw == "parse_error":
        # Provider returned text; frames were real if n_frames>0
        if n_frames > 0:
            memory.append(
                {
                    "tool": "overview",
                    "observation": {
                        "text": "direct_vqa_parse_error",
                        "frames": ["f%d" % i for i in range(n_frames)],
                        "timestamps": timestamps,
                    },
                }
            )
            service_trace.append({"service": "sample_frames", "n_frames": n_frames})
            service_trace.append({"service": "qwen", "frames": n_frames, "status": "ok"})
            usage["qwen_frames"] = n_frames
        agent_status = "answered"
    else:
        agent_status = status_raw or "unknown"
        if error:
            service_trace.append({"service": "qwen", "error": error[:200]})

    return {
        "sample_id": sid,
        "status": agent_status,
        "answer": answer if agent_status == "answered" else None,
        "usage": usage,
        "memory": memory,
        "service_trace": service_trace,
        "diagnostics": diagnostics,
        "arm": "direct_vqa",
        "direct_vqa_record": {
            "status": status_raw,
            "n_frames": n_frames,
            "timestamps": timestamps,
            "frame_bundle_sha": rec.get("frame_bundle_sha"),
            "frame_path_hashes": frame_hashes,
            "prompt_sha": rec.get("prompt_sha"),
            "prompt_version": rec.get("prompt_version"),
            "request_model": rec.get("request_model"),
            "config_fingerprint": rec.get("config_fingerprint"),
            "harness_sha": rec.get("harness_sha"),
            "reused": bool(rec.get("reused")),
            "reuse_reasons": rec.get("reuse_reasons"),
            "error": error,
            "estimated_cny": rec.get("estimated_cny"),
        },
    }


def enrich_record_with_frames(
    record: dict,
    *,
    timestamps: list[float],
    paths: list[Path],
    config_fingerprint: str,
    harness_sha: str | None,
) -> dict:
    """Attach provenance fields required for Guard + future resume."""
    hashes = hash_frame_paths(paths)
    record = dict(record)
    record["timestamps"] = [float(t) for t in timestamps]
    record["frame_path_hashes"] = hashes
    record["frame_bundle_sha"] = frame_bundle_hash(timestamps, paths)
    record["config_fingerprint"] = config_fingerprint
    record["harness_sha"] = harness_sha
    record["n_frames"] = len(paths) if paths else int(record.get("n_frames") or 0)
    return record
