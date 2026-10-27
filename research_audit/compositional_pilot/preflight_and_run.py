#!/usr/bin/env python3
"""Compositional smoke pilot: preflight + paired Initial vs H_S1 under CNY budget.

External experiment tool only. Does not modify harnesses.
Requires videorsi Python and API_BASE/API_KEY in the environment.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from batch_billing import DEFAULT_MODEL_RATES, role_cost  # noqa: E402
from run_batch import load_items  # noqa: E402
from run_batch_checkpoint import (  # noqa: E402
    harness_tree_sha256,
    run_batch_checkpoint,
)
from solver_full_workspace.engine.common import read_json, validate_config, write_json  # noqa: E402
from solver_full_workspace.engine.frame_cost import cost_usage  # noqa: E402

PILOT = Path(__file__).resolve().parent
VIDEORSI = "/home/descfly/miniconda3/envs/videorsi/bin/python"
TOTAL_BUDGET_CNY = 8.0


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:]
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def extract_one_frame(video: Path, t_sec: float, out: Path) -> dict:
    ff = ffmpeg_exe()
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ff,
        "-y",
        "-ss",
        str(t_sec),
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    ok = out.is_file() and out.stat().st_size > 2000
    return {
        "ok": ok,
        "bytes": out.stat().st_size if out.is_file() else 0,
        "returncode": proc.returncode,
        "stderr_tail": (proc.stderr or "")[-200:],
    }


def preflight(items_path: Path, config: dict, out_dir: Path) -> dict:
    report = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "python": sys.executable,
        "videorsi_required": VIDEORSI,
        "checks": {},
        "pass": False,
    }
    report["checks"]["python_is_videorsi"] = {
        "ok": Path(sys.executable).resolve() == Path(VIDEORSI).resolve(),
        "executable": sys.executable,
    }
    try:
        ff = ffmpeg_exe()
        report["checks"]["imageio_ffmpeg"] = {"ok": True, "path": ff}
    except Exception as exc:
        report["checks"]["imageio_ffmpeg"] = {"ok": False, "error": type(exc).__name__ + ": " + str(exc)}

    report["checks"]["api_env"] = {
        "ok": bool(os.environ.get(config["services"]["key_env"]))
        and bool(os.environ.get(config["services"]["endpoint_env"])),
        "key_env": config["services"]["key_env"],
        "endpoint_env": config["services"]["endpoint_env"],
        "endpoint_set": bool(os.environ.get(config["services"]["endpoint_env"])),
        "key_set": bool(os.environ.get(config["services"]["key_env"])),
        # never record secret values
    }

    rows = load_items(str(items_path), check_media=True)
    report["checks"]["load_items"] = {"ok": True, "n": len(rows), "sample_ids": [r["sample_id"] for r in rows]}

    init = ROOT / "evolution/run-seed42/versions/initial_harness"
    hs1 = ROOT / "evolution/run-seed42/versions/H_S1"
    report["checks"]["harnesses"] = {
        "ok": True,
        "initial_sha": harness_tree_sha256(init),
        "hs1_sha": harness_tree_sha256(hs1),
        "initial_path": str(init),
        "hs1_path": str(hs1),
    }

    # Seek one frame from each unique video used by items
    seek = []
    seen = set()
    scratch = out_dir / "preflight_frames"
    for row in rows:
        vp = Path(row["video_path"])
        if str(vp) in seen:
            continue
        seen.add(str(vp))
        dest = scratch / (vp.stem + "_t60.jpg")
        res = extract_one_frame(vp, 60.0, dest)
        seek.append({"video": vp.name, **res})
    report["checks"]["ffmpeg_seek"] = {"ok": all(x["ok"] for x in seek), "videos": seek}

    # Minimal paid ping: one DeepSeek completion (~tiny) to confirm billing path
    ping = {"ok": False}
    try:
        from solver_full_workspace.engine.services import Meter, PinnedProvider, perception_content

        meter = Meter()
        provider = PinnedProvider(config["services"], meter)
        t0 = time.time()
        value = provider.chat(
            role="deepseek",
            messages=[{"role": "user", "content": "Reply with exactly: PONG"}],
        )
        text = perception_content(value).get("text", "")[:40]
        usage = value.get("usage") or {}
        pt = int(usage.get("prompt_tokens") or 0)
        ct = int(usage.get("completion_tokens") or 0)
        cached = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
        cny, _ = role_cost(pt, ct, cached, DEFAULT_MODEL_RATES["deepseek"], apply_cache=True)
        ping = {
            "ok": True,
            "latency_s": round(time.time() - t0, 3),
            "reply_prefix": text,
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "estimated_cny": round(cny, 6),
        }
    except Exception as exc:
        ping = {"ok": False, "error": type(exc).__name__ + ": " + str(exc)[:400]}
    report["checks"]["api_ping_deepseek"] = ping

    report["pass"] = all(
        report["checks"][k].get("ok")
        for k in (
            "python_is_videorsi",
            "imageio_ffmpeg",
            "api_env",
            "load_items",
            "harnesses",
            "ffmpeg_seek",
            "api_ping_deepseek",
        )
    )
    write_json(out_dir / "preflight_report.json", report)
    return report


def result_validity(result: dict) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "not_dict"
    if result.get("status") == "engineering_error":
        return False, "engineering_error:" + str(result.get("error_type"))
    usage = cost_usage(result)
    frames = int(usage.get("qwen_frames") or usage.get("frames") or 0)
    if frames <= 0:
        # Compositional/atomic video QA must observe frames; zero frames = INVALID
        return False, "zero_qwen_frames"
    if result.get("status") not in ("answered", "invalid_decision"):
        return False, "bad_status:" + str(result.get("status"))
    return True, "ok"


def summarize_arm(results: list, labels: dict) -> dict:
    rows = []
    total_cny = 0.0
    total_frames = 0
    total_ds = 0
    total_qw = 0
    total_in = 0
    total_out = 0
    n_valid = 0
    n_correct = 0
    for r in results:
        sid = r.get("sample_id")
        ok, reason = result_validity(r)
        usage = cost_usage(r) if isinstance(r, dict) else {}
        bill = (r or {}).get("billing_estimate") or {}
        cny = float(bill.get("estimated_cny") or 0.0)
        pred = r.get("answer")
        gold = labels.get(sid)
        correct = bool(ok and pred == gold)
        if ok:
            n_valid += 1
        if correct:
            n_correct += 1
        total_cny += cny
        total_frames += int(usage.get("qwen_frames") or 0)
        total_ds += int(usage.get("deepseek_calls") or 0)
        total_qw += int(usage.get("qwen_calls") or 0)
        total_in += int(usage.get("input_tokens") or 0)
        total_out += int(usage.get("output_tokens") or 0)
        rows.append(
            {
                "sample_id": sid,
                "pred": pred,
                "gold": gold,
                "correct": correct,
                "valid": ok,
                "invalid_reason": None if ok else reason,
                "status": r.get("status"),
                "qwen_frames": int(usage.get("qwen_frames") or 0),
                "deepseek_calls": int(usage.get("deepseek_calls") or 0),
                "qwen_calls": int(usage.get("qwen_calls") or 0),
                "estimated_cny": cny,
            }
        )
    return {
        "n": len(results),
        "n_valid": n_valid,
        "n_correct": n_correct,
        "total_estimated_cny": round(total_cny, 6),
        "total_qwen_frames": total_frames,
        "total_deepseek_calls": total_ds,
        "total_qwen_calls": total_qw,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="run paid paired eval after preflight")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--max-total-cny", type=float, default=TOTAL_BUDGET_CNY)
    args = parser.parse_args()

    load_dotenv(ROOT / "providers.env")
    load_dotenv(ROOT / "paratera.env")

    run_dir = PILOT / "runs" / "v0_initial_vs_hs1"
    run_dir.mkdir(parents=True, exist_ok=True)
    items_path = PILOT / "eval_items.jsonl"
    labels_path = PILOT / "labels.local.jsonl"
    config_path = PILOT / "effective_config.concurrency1.json"
    config = validate_config(read_json(config_path))

    if Path(sys.executable).resolve() != Path(VIDEORSI).resolve():
        print("FATAL: must run with videorsi python:", VIDEORSI, file=sys.stderr)
        print("current:", sys.executable, file=sys.stderr)
        return 2

    report = preflight(items_path, config, run_dir)
    print(json.dumps({"preflight_pass": report["pass"], "checks": {k: v.get("ok") for k, v in report["checks"].items()}}, indent=2))
    if not report["pass"]:
        print("PREFLIGHT FAILED — refusing paid run", file=sys.stderr)
        return 3
    if args.preflight_only or not args.execute:
        print("Preflight OK. Pass --execute to start paid paired run.")
        return 0

    labels = {row["sample_id"]: row["answer"] for row in (json.loads(l) for l in labels_path.read_text().splitlines() if l.strip())}
    rows = load_items(str(items_path), check_media=True)

    ping_cny = float(report["checks"]["api_ping_deepseek"].get("estimated_cny") or 0.0)
    remaining = args.max_total_cny - ping_cny
    if remaining < 1.0:
        print("FATAL: remaining budget after ping too small:", remaining, file=sys.stderr)
        return 4

    # Split remaining budget across arms; Initial first, then H_S1 gets residual.
    # concurrency=1; reserve one item ~0.5 CNY
    init_cap = min(remaining * 0.55, remaining - 0.8)
    arms = [
        ("initial", ROOT / "evolution/run-seed42/versions/initial_harness", init_cap),
        ("hs1", ROOT / "evolution/run-seed42/versions/H_S1", None),  # filled after initial
    ]

    spent = ping_cny
    arm_summaries = {}
    abort = None

    for name, cand, cap in arms:
        if name == "hs1":
            cap = max(0.0, args.max_total_cny - spent)
            if cap < 0.5:
                abort = "insufficient_budget_for_hs1"
                break
        out = run_dir / name
        print(f"\n=== ARM {name} candidate={cand} max_estimated_cny={cap:.4f} ===", flush=True)
        summary = run_batch_checkpoint(
            config,
            cand,
            rows,
            out,
            resume=True,
            max_provider_calls=200,
            max_estimated_cny=cap,
            reserve_calls=20,
            reserve_cny=0.55,
            apply_cache=True,
        )
        write_json(out / "batch_summary.json", summary)
        results = read_json(out / "results.json")
        # Fail-closed on zero frames / engineering errors
        invalid = []
        for r in results:
            ok, reason = result_validity(r)
            if not ok and r.get("status") != "missing":
                invalid.append({"sample_id": r.get("sample_id"), "reason": reason, "status": r.get("status")})
        arm_sum = summarize_arm(results, labels)
        arm_sum["batch_status"] = summary.get("status")
        arm_sum["budget_snapshot"] = summary.get("budget")
        arm_sum["invalid_runs"] = invalid
        arm_summaries[name] = arm_sum
        spent += arm_sum["total_estimated_cny"]
        print(
            json.dumps(
                {
                    "arm": name,
                    "batch_status": summary.get("status"),
                    "spent_arm_cny": arm_sum["total_estimated_cny"],
                    "spent_total_cny": round(spent, 4),
                    "invalid": invalid,
                },
                indent=2,
            ),
            flush=True,
        )
        if invalid:
            abort = "invalid_run_detected"
            break
        if summary.get("status") == "stopped_budget":
            abort = "stopped_budget:" + name
            break
        if spent >= args.max_total_cny:
            abort = "total_budget_reached"
            break

    final = {
        "protocol": "compositional_pilot_v0",
        "tag": "Exploratory / Non-Held-Out / Smoke Test",
        "max_total_cny": args.max_total_cny,
        "ping_cny": ping_cny,
        "spent_total_cny": round(spent, 6),
        "abort": abort,
        "arms": arm_summaries,
        "preflight_pass": True,
    }
    write_json(run_dir / "paired_summary.json", final)
    print(json.dumps({"done": True, "abort": abort, "spent_total_cny": final["spent_total_cny"]}, indent=2))
    return 0 if abort is None else 5


if __name__ == "__main__":
    raise SystemExit(main())
