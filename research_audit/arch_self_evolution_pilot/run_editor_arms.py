#!/usr/bin/env python3
"""Phase C — Baseline vs Treatment Editor arms (matched budget; no Round 4–20).

Baseline: stock DeepSeekEditor + stock Investigation.
Treatment: same Editor with CounterfactualInvestigation + INVESTIGATION_COUNTERFACTUAL.md
           and a generic capability note (does NOT instruct 'switch to Direct VQA').

Does not mutate evolution/run-seed42. Writes under runs/editor_arms_v1/.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PILOT = Path(__file__).resolve().parent
PREFLIGHT = ROOT / "research_audit" / "arch_evolution_min_preflight"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PREFLIGHT))

from solver_full_workspace.engine.common import public_item, read_json, write_json, validate_config
from solver_full_workspace.engine.runner import copy_candidate, check_candidate
from solver_full_workspace.engine.editor import DeepSeekEditor, Investigation
from solver_full_workspace.engine.services import Meter, PinnedProvider

from infoflow_lib import (
    TRAIN_CACHE,
    TRAIN_ITEMS,
    TRAIN_ORACLE,
    GATE_ORACLE,
    load_frozen_ids,
    load_gate_ids,
    load_oracle,
    load_train_items,
    cache_by_sample_id,
)
from counterfactual_investigation import CounterfactualInvestigation

SEED_HARNESS = ROOT / "evolution" / "run-seed42" / "versions" / "initial_harness"
CONFIG_PATH = ROOT / "config.evolution.local.json"
# Analysis+plan alone consumed ~48 on baseline; matched ceiling raised so both arms
# can attempt edit under the same limit (still far below production 160).
MATCHED_PROVIDER_CALLS = 96
TRAIN_SUBSET_N = 16
TRAIN_SUBSET_SEED = 20261026
PROTOCOL = "arch_editor_arms_v1"


def load_config() -> dict:
    cfg = validate_config(read_json(CONFIG_PATH))
    cfg = json.loads(json.dumps(cfg))  # deep copy via json
    cfg["editor"]["max_provider_calls"] = MATCHED_PROVIDER_CALLS
    cfg["editor"]["timeout_seconds"] = min(int(cfg["editor"].get("timeout_seconds", 3600)), 3600)
    return cfg


def select_train_subset() -> list[str]:
    """Wrong initial_harness trajs, excluding frozen-20 and Gate; fixed seed."""
    rng = random.Random(TRAIN_SUBSET_SEED)
    frozen = set(load_frozen_ids())
    gate = load_gate_ids()
    gold = load_oracle(TRAIN_ORACLE)
    cache = cache_by_sample_id()
    pool = []
    for sid, traj in cache.items():
        if sid in frozen or sid in gate:
            continue
        if traj.get("status") != "answered":
            continue
        if traj.get("answer") != gold.get(sid):
            pool.append(sid)
    rng.shuffle(pool)
    chosen = sorted(pool[:TRAIN_SUBSET_N])
    assert not (set(chosen) & frozen)
    assert not (set(chosen) & gate)
    return chosen


def build_workspace(arm_dir: Path, sample_ids: list[str], items: dict, gold: dict, cache: dict) -> Path:
    workspace = arm_dir / "workspace"
    if workspace.exists():
        return workspace
    workspace.mkdir(parents=True)
    copy_candidate(SEED_HARNESS, workspace / "candidate")
    (workspace / "analysis").mkdir()
    (workspace / "analysis" / "investigations").mkdir(exist_ok=True)
    (workspace / "training" / "cases").mkdir(parents=True)
    index = []
    for number, sid in enumerate(sample_ids):
        row = items[sid]
        traj = cache[sid]
        evidence = {"answer": gold[sid]}
        outcome = "wrong" if traj.get("answer") != gold[sid] else "correct"
        relative = "cases/%06d.json" % number
        record = {
            "item": public_item(row),
            "gold_answer": evidence["answer"],
            "trajectory": traj,
            "program_outcome": outcome,
            "analysis_metadata": {k: row[k] for k in ("question_type",) if k in row},
        }
        write_json(workspace / "training" / relative, record)
        index.append({"sample_id": sid, "outcome": outcome, "path": relative})
    write_json(workspace / "training/index.json", index)
    write_json(
        workspace / "lineage_feedback.json",
        {"status": "initial_parent", "feedback_policy": "fixed_gate_aggregate_only_v1"},
    )
    for name in ("SERVICES.md", "DIAGNOSIS.md", "INVESTIGATION.md", "investigate.py"):
        shutil.copyfile(ROOT / "solver_full_workspace" / name, workspace / name)
    return workspace


class TreatmentEditor(DeepSeekEditor):
    """DeepSeekEditor that installs CounterfactualInvestigation + capability note."""

    def run(self, workspace, private, phase):
        workspace = Path(workspace)
        # Append counterfactual docs without prescribing Direct VQA.
        inv = workspace / "INVESTIGATION.md"
        addendum = (PILOT / "INVESTIGATION_COUNTERFACTUAL.md").read_text(encoding="utf-8")
        text = inv.read_text(encoding="utf-8")
        if "infoflow_probe" not in text:
            inv.write_text(text.rstrip() + "\n\n" + addendum + "\n", encoding="utf-8")
        # Soft capability note into analysis directive (generic).
        extra = (
            "\n\nADDITIONAL OPTIONAL TOOLING: This session exposes executable info-flow "
            "counterfactual probes via investigate.py (see INVESTIGATION.md section on infoflow_probe). "
            "You may use them to test whether failures stem from visual evidence handling, "
            "textual observations, or final answer reasoning. Whether to use them, what to test, "
            "and what to change in code is your decision. Do not treat any single probe outcome as Gate.\n"
        )
        self.config = json.loads(json.dumps(self.config))
        base = self.config["editor"].get("analysis_directive") or (
            Path(__file__).resolve().parents[2] / "solver_full_workspace" / "DIAGNOSIS.md"
        ).read_text(encoding="utf-8")
        if "infoflow_probe" not in base:
            self.config["editor"]["analysis_directive"] = base + extra

        import solver_full_workspace.engine.editor as editor_mod

        prev = editor_mod.Investigation
        editor_mod.Investigation = CounterfactualInvestigation
        try:
            return super().run(workspace, private, phase)
        finally:
            editor_mod.Investigation = prev


def run_arm(arm: str, sample_ids: list[str], execute: bool) -> dict:
    cfg = load_config()
    arm_dir = PILOT / "runs" / "editor_arms_v1" / arm
    arm_dir.mkdir(parents=True, exist_ok=True)
    items = load_train_items()
    gold = load_oracle(TRAIN_ORACLE)
    cache = cache_by_sample_id()
    rows = [items[sid] for sid in sample_ids]
    workspace = build_workspace(arm_dir, sample_ids, items, gold, cache)
    private = arm_dir / "private_editor"
    private.mkdir(exist_ok=True)
    write_json(
        arm_dir / "arm_meta.json",
        {
            "protocol": PROTOCOL,
            "arm": arm,
            "matched_provider_calls": MATCHED_PROVIDER_CALLS,
            "train_subset": sample_ids,
            "seed_harness": str(SEED_HARNESS),
            "treatment_has_infoflow_probe": arm == "treatment",
        },
    )

    if not execute:
        return {"arm": arm, "status": "dry_prepared", "workspace": str(workspace)}

    if os.environ.get("ARCH_AB_ALLOW_PAID") != "1":
        raise SystemExit("ARCH_AB_ALLOW_PAID=1 required")

    provider = PinnedProvider(cfg["services"], Meter())
    if arm == "treatment":
        editor = TreatmentEditor(cfg, provider=provider)
    else:
        editor = DeepSeekEditor(cfg, provider=provider)
    editor.configure_investigation(rows, workspace / "candidate")

    phases_done = []
    errors = []
    for phase in ("analysis", "plan", "edit"):
        marker = arm_dir / ("phase_%s.done" % phase)
        if marker.is_file():
            phases_done.append(phase)
            continue
        print("ARM", arm, "PHASE", phase, flush=True)
        try:
            editor.run(workspace, private, phase)
            marker.write_text(json.dumps({"ok": True, "t": time.time()}), encoding="utf-8")
            phases_done.append(phase)
        except Exception as exc:
            errors.append({"phase": phase, "error_type": type(exc).__name__, "error": str(exc)[:800]})
            write_json(arm_dir / "arm_error.json", errors[-1])
            break

    # Collect evidence of mechanism choice / code change
    evidence = collect_arm_evidence(arm, workspace, private)
    write_json(arm_dir / "arm_result.json", {
        "arm": arm,
        "phases_done": phases_done,
        "errors": errors,
        "evidence": evidence,
    })
    return {"arm": arm, "phases_done": phases_done, "errors": errors, "evidence": evidence}


def collect_arm_evidence(arm: str, workspace: Path, private: Path) -> dict:
    analysis = workspace / "analysis"
    plan = analysis / "edit_plan.md"
    summary = analysis / "edit_summary.md"
    analysis_md = analysis / "analysis.md"

    # Diff candidate vs seed (file list + sha)
    from hashlib import sha256
    from solver_full_workspace.engine.runner import INITIAL_FILES

    diffs = []
    for name in INITIAL_FILES:
        a = SEED_HARNESS / name
        b = workspace / "candidate" / name
        if not b.is_file():
            diffs.append({"file": name, "status": "missing_in_candidate"})
            continue
        ha, hb = sha256(a.read_bytes()).hexdigest(), sha256(b.read_bytes()).hexdigest()
        if ha != hb:
            diffs.append({"file": name, "status": "modified", "bytes_delta": b.stat().st_size - a.stat().st_size})

    # infoflow_probe usage
    probe_ops = []
    inv_dir = private / "investigations"
    if inv_dir.is_dir():
        for p in sorted(inv_dir.glob("request_*.json")):
            row = read_json(p)
            op = (row.get("request") or {}).get("operation")
            if op == "infoflow_probe":
                probe_ops.append({
                    "id": row.get("id"),
                    "mode": (row.get("request") or {}).get("mode"),
                    "sample_id": (row.get("request") or {}).get("sample_id"),
                    "status": row.get("status"),
                })

    def head(path: Path, n=400):
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8", errors="ignore")[:n]

    # Heuristic: did edit mention info-flow / answerer / direct vision?
    plan_text = plan.read_text(encoding="utf-8", errors="ignore") if plan.is_file() else ""
    keywords = {
        "direct_vqa_or_vision_answer": any(k in plan_text.lower() for k in ("direct", "vision", "qwen 直接", "看帧", "vqa")),
        "answerer_routing": any(k in plan_text.lower() for k in ("回答者", "answerer", "deepseek", "分工")),
        "caption_or_observation": any(k in plan_text.lower() for k in ("caption", "观察", "overview", "描述")),
        "infoflow_probe_mentioned": "infoflow_probe" in plan_text or "反事实" in plan_text,
    }

    eng = None
    try:
        eng = check_candidate(workspace / "candidate")
    except Exception as exc:
        eng = {"status": "check_failed", "error": str(exc)[:400]}

    return {
        "analysis_exists": analysis_md.is_file() and bool(analysis_md.read_text().strip()),
        "plan_exists": plan.is_file() and bool(plan_text.strip()),
        "edit_summary_exists": summary.is_file() and bool(summary.read_text().strip()) if summary.is_file() else False,
        "candidate_files_modified": diffs,
        "n_files_modified": sum(1 for d in diffs if d.get("status") == "modified"),
        "infoflow_probe_calls": probe_ops,
        "n_infoflow_probes": len(probe_ops),
        "plan_keyword_hits": keywords,
        "engineering_check": eng,
        "analysis_head": head(analysis_md),
        "plan_head": head(plan),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["baseline", "treatment", "both"], default="both")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--prepare-only", action="store_true")
    args = ap.parse_args()
    subset = select_train_subset()
    write_json(PILOT / "out" / "editor_train_subset.safe.json", {
        "n": len(subset),
        "sample_ids": subset,
        "excluded": ["frozen_exploratory_n20", "private_gate"],
        "matched_provider_calls": MATCHED_PROVIDER_CALLS,
    })
    arms = ["baseline", "treatment"] if args.arm == "both" else [args.arm]
    results = []
    for arm in arms:
        results.append(run_arm(arm, subset, execute=args.execute and not args.prepare_only))
    write_json(PILOT / "runs" / "editor_arms_v1" / "arms_summary.json", {"results": results})
    # safe summary without plan prose dumps beyond flags
    safe = {
        "protocol": PROTOCOL,
        "matched_provider_calls": MATCHED_PROVIDER_CALLS,
        "train_subset_n": len(subset),
        "arms": [
            {
                "arm": r.get("arm"),
                "phases_done": r.get("phases_done"),
                "errors": r.get("errors"),
                "n_files_modified": (r.get("evidence") or {}).get("n_files_modified"),
                "n_infoflow_probes": (r.get("evidence") or {}).get("n_infoflow_probes"),
                "plan_keyword_hits": (r.get("evidence") or {}).get("plan_keyword_hits"),
                "engineering_check": (r.get("evidence") or {}).get("engineering_check"),
                "analysis_exists": (r.get("evidence") or {}).get("analysis_exists"),
                "plan_exists": (r.get("evidence") or {}).get("plan_exists"),
            }
            for r in results
        ],
    }
    write_json(PILOT / "out" / "editor_arms.safe.json", safe)
    print(json.dumps(safe, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
