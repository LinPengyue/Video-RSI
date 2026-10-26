#!/usr/bin/env python3
"""Offline Phase D validity auditor (0 API). Recomputes zero-frame / tool-fail stats."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "research_audit" / "arch_self_evolution_pilot" / "runs" / "phase_d_eval_v1"
IDS = ROOT / "research_audit" / "arch_self_evolution_pilot" / "out" / "independent_eval_ids.safe.json"
OUT = Path(__file__).resolve().parent / "out"


def analyze_arm(arm: str, ids: list[str]) -> dict:
    path = RUN / arm / "results.json"
    if not path.is_file():
        return {"arm": arm, "error": "missing_results", "path": str(path)}
    rows = {r["sample_id"]: r for r in json.loads(path.read_text())}
    per = []
    visual_attempts = visual_ok = sf_err = qwen_trace = 0
    err_msgs = Counter()
    for sid in ids:
        r = rows[sid]
        mem = r.get("memory") or []
        n_vis = n_err = n_ok = n_stub = 0
        for m in mem:
            if m.get("tool") not in ("overview", "scan_interval", "inspect_interval", "read_text"):
                continue
            n_vis += 1
            visual_attempts += 1
            obs = m.get("observation") or {}
            if isinstance(obs, dict) and obs.get("error"):
                n_err += 1
            elif isinstance(obs, dict) and obs.get("already_observed"):
                n_stub += 1
                n_ok += 1
                visual_ok += 1
            elif isinstance(obs, dict) and (obs.get("frames") or obs.get("perception")):
                n_ok += 1
                visual_ok += 1
        for e in r.get("service_trace") or []:
            if e.get("service") == "sample_frames" and e.get("error"):
                sf_err += 1
                err_msgs[str(e.get("error"))[:120]] += 1
            if e.get("service") == "qwen":
                qwen_trace += 1
        usage = r.get("usage") or {}
        per.append(
            {
                "sample_id": sid,
                "status": r.get("status"),
                "n_memory": len(mem),
                "n_visual_calls": n_vis,
                "n_visual_errors": n_err,
                "n_visual_ok_or_stub": n_ok,
                "n_already_observed_stubs": n_stub,
                "qwen_frames": usage.get("qwen_frames"),
                "qwen_calls": usage.get("qwen_calls"),
                "deepseek_calls": usage.get("deepseek_calls"),
                "frames_extracted": usage.get("frames_extracted"),
                "tool_execution_errors": (r.get("diagnostics") or {}).get("tool_execution_errors"),
            }
        )
    return {
        "arm": arm,
        "n": len(per),
        "status_counts": dict(Counter(x["status"] for x in per)),
        "items_all_visual_failed_or_absent": sum(1 for x in per if x["n_visual_ok_or_stub"] == 0 or x["n_visual_ok_or_stub"] == x["n_already_observed_stubs"] and x["n_visual_errors"] > 0 and x["qwen_frames"] == 0),
        "items_qwen_frames_zero": sum(1 for x in per if x["qwen_frames"] == 0),
        "items_qwen_calls_zero": sum(1 for x in per if x["qwen_calls"] == 0),
        "total_visual_calls": visual_attempts,
        "total_visual_ok_including_stubs": visual_ok,
        "total_sample_frames_errors": sf_err,
        "qwen_in_service_trace": qwen_trace,
        "service_error_messages": dict(err_msgs),
        "mean_deepseek_calls": sum(x["deepseek_calls"] or 0 for x in per) / len(per),
        "classification": "CASE_A_visual_tools_attempted_but_sample_frames_failed_before_qwen",
        "per_item": per,
    }


def main() -> int:
    if not RUN.is_dir():
        print("missing run dir", RUN, file=sys.stderr)
        return 2
    ids = json.loads(IDS.read_text())["sample_ids"]
    report = {
        "protocol": "phase_d_validity_audit_v1",
        "run_dir": str(RUN),
        "eval_python_note": (
            "eval_independent.py runs in-process under the invoking interpreter; "
            "ff1d383 Phase D used system python without imageio_ffmpeg while config.execution.python points at videorsi."
        ),
        "arms": {arm: analyze_arm(arm, ids) for arm in ("initial", "baseline", "treatment")},
    }
    # Direct VQA
    dv = RUN / "direct_vqa" / "calls"
    if dv.is_dir():
        calls = [json.loads(p.read_text()) for p in dv.glob("*.json")]
        report["direct_vqa"] = {
            "n_calls": len(calls),
            "n_ok": sum(1 for c in calls if c.get("status") == "ok"),
            "n_frames_counter": dict(Counter(c.get("n_frames") for c in calls)),
            "note": "Direct VQA used infoflow_lib.ffmpeg_bin fallback to videorsi-packaged ffmpeg binary; succeeded under same system python",
        }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "phase_d_frame_audit.safe.json"
    # strip nothing sensitive beyond sample_ids already public in freeze list
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({a: {k: v for k, v in report["arms"][a].items() if k != "per_item"} for a in report["arms"]}, indent=2))
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
