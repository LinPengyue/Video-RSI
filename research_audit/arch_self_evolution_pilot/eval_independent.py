#!/usr/bin/env python3
"""Phase D — independent eval of Initial / Baseline / Treatment / Direct-VQA.

Uses frozen IDs in out/independent_eval_ids.safe.json (video-disjoint from
exploratory-20, editor subset, Gate). Does not overwrite editor arm artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PILOT = Path(__file__).resolve().parent
PREFLIGHT = ROOT / "research_audit" / "arch_evolution_min_preflight"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PREFLIGHT))

from solver_full_workspace.engine.common import public_item, read_json, write_json, validate_config
from solver_full_workspace.engine.runner import run_item, copy_candidate
from solver_full_workspace.engine.services import Services, Meter, PinnedProvider, LocalOCR

from infoflow_lib import (
    TRAIN_ORACLE,
    load_gate_ids,
    load_frozen_ids,
    load_oracle,
    load_services_config,
    load_train_items,
    overview_bundle,
    cache_by_sample_id,
    extract_frames,
    vqa_prompt,
    vision_messages,
    parse_answer_letter,
    estimate_cny,
    sha256_text,
)
from ab_infoflow_runner import apply_usage, finalize_answer, record_template, make_provider
from infoflow_lib import ResultStore, HttpProvider, EFFECTIVE_CONFIG

from experiment_guard import GuardedExperiment, PreflightCapabilities
from experiment_guard.fingerprints import config_fingerprint, harness_fingerprint

SEED = ROOT / "evolution" / "run-seed42" / "versions" / "initial_harness"
BASELINE = PILOT / "runs" / "editor_arms_v1" / "baseline" / "workspace" / "candidate"
TREATMENT = PILOT / "runs" / "editor_arms_v1" / "treatment" / "workspace" / "candidate"
EVAL_IDS = PILOT / "out" / "independent_eval_ids.safe.json"
EDITOR_SUBSET = PILOT / "out" / "editor_train_subset.safe.json"
CONFIG_PATH = EFFECTIVE_CONFIG


def assert_eval_hygiene(ids: list[str]) -> None:
    frozen = set(load_frozen_ids())
    gate = load_gate_ids()
    editor = set(read_json(EDITOR_SUBSET)["sample_ids"]) if EDITOR_SUBSET.is_file() else set()
    bad = set(ids) & (frozen | gate | editor)
    if bad:
        raise SystemExit("eval ID leakage: %s" % sorted(bad))


def run_harness_on_item(candidate: Path, item: dict, config: dict, provider, ocr, scratch: Path) -> dict:
    scratch.mkdir(parents=True, exist_ok=True)
    services = Services(public_item(item), item, config, scratch, provider=provider, ocr=ocr)
    result = run_item(candidate, item, services, config)
    return result


def summarize_harness_batch(name: str, results: list, gold: dict) -> dict:
    n = len(results)
    correct = 0
    frames = 0
    for row in results:
        sid = row["sample_id"]
        ok = row.get("status") == "answered" and row.get("answer") == gold.get(sid)
        correct += int(ok)
        frames += int((row.get("usage") or {}).get("qwen_frames") or 0)
    return {
        "name": name,
        "n": n,
        "correct": correct,
        "accuracy": correct / n if n else None,
        "mean_qwen_frames": frames / n if n else None,
        "per_item": [
            {
                "sample_id": r["sample_id"],
                "correct": r.get("status") == "answered" and r.get("answer") == gold.get(r["sample_id"]),
                "status": r.get("status"),
                "qwen_frames": (r.get("usage") or {}).get("qwen_frames"),
            }
            for r in results
        ],
    }


def run_direct_vqa(ids: list[str], items: dict, gold: dict, cache: dict, config: dict, provider, run_dir: Path) -> dict:
    store = ResultStore(run_dir / "direct_vqa")
    rows = []
    for sid in ids:
        existing = store.load_call(sid, "DirectVQA", "answer")
        if existing and existing.get("status") == "ok":
            rows.append(existing)
            continue
        item = items[sid]
        # Prefer cached overview timestamps; else uniform 32 midpoints.
        timestamps = None
        if sid in cache:
            try:
                timestamps = overview_bundle(cache[sid])["timestamps"]
            except ValueError:
                timestamps = None
        if not timestamps:
            dur = float(item["duration"])
            timestamps = [dur * (i + 0.5) / 32 for i in range(32)]
        out_dir = store.frames_dir / sid
        paths = extract_frames(Path(item["video_path"]), timestamps, out_dir, config)
        prompt = vqa_prompt(item["question"], item["options"], caption=None)
        record = record_template(sid, "DirectVQA", "answer", prompt_sha=sha256_text(prompt), n_overview_frames=len(paths))
        resp = provider.chat("qwen", vision_messages(prompt, paths, timestamps), frames=len(paths))
        apply_usage(record, resp)
        if resp.status == "ok":
            finalize_answer(record, resp.text, item["options"], gold.get(sid))
        store.save_call(record)
        rows.append(record)
    return summarize_harness_batch(
        "direct_vqa",
        [
            {
                "sample_id": r["sample_id"],
                "status": "answered" if r.get("answer") else r.get("status"),
                "answer": r.get("answer"),
                "usage": {"qwen_frames": r.get("n_frames") or r.get("usage", {}).get("frames")},
            }
            for r in rows
        ],
        gold,
    )


def run_arm_harness(
    name: str,
    candidate: Path,
    ids: list[str],
    items: dict,
    gold: dict,
    config: dict,
    run_dir: Path,
    concurrency: int = 2,
    *,
    guard: GuardedExperiment | None = None,
) -> tuple[dict, list]:
    """Run harness arm. When guard is set, uses guarded concurrent batch (abort on infra fail).

    Returns (summary_dict, ordered_results).
    """
    out = run_dir / name
    out.mkdir(parents=True, exist_ok=True)
    results_path = out / "results.json"
    if results_path.is_file():
        results = read_json(results_path)
        # Resume only VALID answered rows — INVALID_RUN from broken env must redo
        from experiment_guard import classify_item_run

        done = set()
        for r in results:
            if r.get("status") != "answered":
                continue
            if classify_item_run(r)["validity"] == "INVALID_RUN":
                continue
            done.add(r["sample_id"])
    else:
        results = []
        done = set()

    pending = [sid for sid in ids if sid not in done]
    ocr = LocalOCR(config["services"]["ocr_model_root"])

    def one(sid):
        scratch = out / "scratch" / sid
        item = items[sid]
        local_meter = Meter()
        local_provider = PinnedProvider(config["services"], local_meter)
        return run_harness_on_item(candidate, item, config, local_provider, ocr, scratch)

    new_rows = []
    batch_meta = None
    if pending:
        if guard is not None:
            # Fresh runtime per arm so abort state does not leak across arms incorrectly,
            # but share start fingerprint from guard.
            from experiment_guard.runtime_guard import RuntimeGuard, BatchAbortPolicy

            arm_runtime = RuntimeGuard(policy=BatchAbortPolicy(), start_fingerprint=guard.cfg_fp)
            guard.runtime = arm_runtime
            report = guard.run_batch(pending, one, max_workers=concurrency)
            new_rows = report.results
            batch_meta = report.to_dict()
            for row in new_rows:
                print(name, row.get("sample_id"), row.get("status"), row.get("answer"), flush=True)
            if report.aborted:
                print(
                    "GUARD_ABORT",
                    name,
                    report.abort_reason,
                    "never_submitted=%d cancelled=%d after_abort=%d"
                    % (report.never_submitted, report.cancelled_before_start, report.completed_after_abort),
                    flush=True,
                )
        else:
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futs = {pool.submit(one, sid): sid for sid in pending}
                for fut in as_completed(futs):
                    sid = futs[fut]
                    try:
                        row = fut.result()
                    except Exception as exc:
                        row = {
                            "sample_id": sid,
                            "status": "engineering_error",
                            "answer": None,
                            "error": str(exc)[:400],
                            "usage": {},
                            "memory": [],
                            "service_trace": [],
                            "diagnostics": {"tool_execution_errors": 1},
                        }
                    new_rows.append(row)
                    print(name, sid, row.get("status"), row.get("answer"), flush=True)

    by = {r["sample_id"]: r for r in results}
    for r in new_rows:
        by[r["sample_id"]] = r
    ordered = [by[sid] for sid in ids if sid in by]
    write_json(results_path, ordered)
    if batch_meta is not None:
        write_json(out / "guard_batch_execution.json", batch_meta)
    summary = summarize_harness_batch(name, ordered, gold)
    summary["guard_batch"] = batch_meta
    return summary, ordered


def pairwise(parent: dict, cand: dict) -> dict:
    """Fix/harm relative to parent on same IDs."""
    p = {r["sample_id"]: r["correct"] for r in parent["per_item"]}
    c = {r["sample_id"]: r["correct"] for r in cand["per_item"]}
    ids = sorted(set(p) & set(c))
    fix = sum(1 for i in ids if c[i] and not p[i])
    harm = sum(1 for i in ids if p[i] and not c[i])
    return {
        "vs": parent["name"],
        "fix": fix,
        "harm": harm,
        "net": fix - harm,
        "parent_correct": sum(p[i] for i in ids),
        "cand_correct": sum(c[i] for i in ids),
    }


def _protocol_kwargs_for_eval(ids: list[str], config: dict, arm_harness: dict[str, Path]) -> dict:
    gate = load_gate_ids()
    editor = set(read_json(EDITOR_SUBSET)["sample_ids"]) if EDITOR_SUBSET.is_file() else set()
    frozen = set(load_frozen_ids())
    # "train" for isolation = method-selection / editor / exploratory sets (must not overlap eval)
    method_train = sorted(editor | frozen)
    cfg_fp = config_fingerprint(config)
    arm_cfg = {name: cfg_fp for name in arm_harness}
    arm_har = {name: harness_fingerprint(path).get("sha16") for name, path in arm_harness.items()}
    return {
        "formal": True,
        "eval_ids": ids,
        "train_ids": method_train,
        "gate_ids": sorted(gate),
        "editor_subset_ids": sorted(editor),
        "arm_ids": {name: list(ids) for name in arm_harness},
        "arm_config_fingerprints": arm_cfg,
        "arm_harness_fingerprints": arm_har,
        "cache_reuse_allowed": True,
        "cache_source": "phase_d_direct_vqa_optional",
        "cache_compatible": True,
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--run-dir", type=Path, default=PILOT / "runs" / "phase_d_eval_v1")
    ap.add_argument("--arms", default="initial,baseline,treatment,direct_vqa", help="comma list")
    args = ap.parse_args()

    ids = read_json(EVAL_IDS)["sample_ids"]
    if args.limit:
        ids = ids[: args.limit]
    assert_eval_hygiene(ids)
    items = load_train_items()
    gold = load_oracle(TRAIN_ORACLE)
    cache = cache_by_sample_id()
    config = validate_config(load_services_config())
    want_arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    if not args.execute:
        print(
            json.dumps(
                {
                    "n": len(ids),
                    "arms": want_arms,
                    "guard": "require_preflight runs only with --execute; dry-run skips paid provider",
                },
                indent=2,
            )
        )
        return 0
    if os.environ.get("ARCH_AB_ALLOW_PAID") != "1":
        raise SystemExit("need ARCH_AB_ALLOW_PAID=1")

    # --- Experiment Guard: cannot be bypassed by --execute ---
    guard_dir = args.run_dir / "experiment_guard"
    guard = GuardedExperiment(
        experiment_id="phase_d_eval_independent",
        out_dir=guard_dir,
        config_path=CONFIG_PATH,
        harness_dir=SEED,
        capabilities=PreflightCapabilities(
            visual_sample_frames=True,
            editor_investigation=False,
            infoflow_probe=False,
            host_must_match_config_python=True,
            provider_config=True,
        ),
        require_provider_env=True,
        formal_protocol=True,
    )
    # Fail-closed before any provider construction
    guard.start(reexec=True, config=config)

    args.run_dir.mkdir(parents=True, exist_ok=True)
    summaries = {}
    results_by_arm: dict[str, list] = {}
    harness_map = {
        "initial": SEED,
        "baseline": BASELINE,
        "treatment": TREATMENT,
    }
    aborted_early = False
    for name, cand in (("initial", SEED), ("baseline", BASELINE), ("treatment", TREATMENT)):
        if name not in want_arms:
            continue
        if not cand.is_dir():
            print("SKIP missing candidate", name, cand, flush=True)
            continue
        print("EVAL", name, flush=True)
        summary, ordered = run_arm_harness(
            name, cand, ids, items, gold, config, args.run_dir, args.concurrency, guard=guard
        )
        summaries[name] = summary
        results_by_arm[name] = ordered
        if guard.runtime and guard.runtime.aborted:
            aborted_early = True
            print("EVAL aborted after arm", name, "reason", guard.runtime.abort_reason, flush=True)
            break

    if "direct_vqa" in want_arms and not aborted_early:
        print("EVAL direct_vqa", flush=True)
        provider = HttpProvider(config)
        summaries["direct_vqa"] = run_direct_vqa(ids, items, gold, cache, config, provider, args.run_dir)

    # Health + protocol (formal)
    protocol_kw = _protocol_kwargs_for_eval(
        ids,
        config,
        {k: harness_map[k] for k in harness_map if k in results_by_arm},
    )
    primary_results = results_by_arm.get("initial") or next(iter(results_by_arm.values()), [])
    health = guard.finalize(
        primary_results,
        gold=gold,
        expected_ids=ids,
        multi_arms=results_by_arm or None,
        protocol_kwargs=protocol_kw,
    )

    # Accuracy tables: only emit unmarked ranking if Guard says usable
    report = {
        "n": len(ids),
        "summaries": {k: {kk: vv for kk, vv in v.items() if kk not in ("per_item",)} for k, v in summaries.items()},
        "guard_health": {
            "overall_validity": health.get("overall_validity"),
            "usable_for_architecture_ranking": health.get("usable_for_architecture_ranking"),
            "reason_codes": health.get("reason_codes"),
            "aborted_early": aborted_early,
        },
    }
    if health.get("usable_for_architecture_ranking") and "initial" in summaries:
        report["vs_initial"] = {
            k: pairwise(summaries["initial"], summaries[k])
            for k in ("baseline", "treatment", "direct_vqa")
            if k in summaries
        }
        if "baseline" in summaries and "treatment" in summaries:
            report["treatment_vs_baseline"] = pairwise(summaries["baseline"], summaries["treatment"])
        if "direct_vqa" in summaries and "treatment" in summaries:
            report["treatment_vs_direct_vqa"] = pairwise(summaries["direct_vqa"], summaries["treatment"])
    else:
        report["architecture_ranking_suppressed"] = True
        report["naive_summaries_audit_only"] = {
            k: {"accuracy": summaries[k].get("accuracy"), "correct": summaries[k].get("correct")}
            for k in summaries
        }

    write_json(args.run_dir / "eval_report.json", {"full": {k: summaries[k] for k in summaries}, "aggregate": report})
    safe = {
        "n": report["n"],
        "guard": report["guard_health"],
        "architecture_ranking_usable": bool(health.get("usable_for_architecture_ranking")),
        "accuracy_naive_audit_only": {k: summaries[k]["accuracy"] for k in summaries},
        "mean_qwen_frames": {k: summaries[k]["mean_qwen_frames"] for k in summaries},
        "vs_initial": report.get("vs_initial"),
        "note": "Guard-gated independent eval; INVALID runs excluded from architecture ranking",
    }
    write_json(PILOT / "out" / "phase_d_eval.safe.json", safe)
    print(json.dumps(safe, indent=2))
    return 1 if aborted_early or not health.get("usable_for_architecture_ranking") else 0


if __name__ == "__main__":
    raise SystemExit(main())
