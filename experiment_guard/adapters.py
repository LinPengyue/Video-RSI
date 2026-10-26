"""Integration coverage matrix and thin adapter helpers.

Does NOT monkey-patch Gate / Harness / evolve. Outer runners import require_preflight
or GuardedExperiment. Entries marked wired=False need a one-line call at main().
"""
from __future__ import annotations

from typing import Any


# Status: wired = Guard ships a drop-in wrapper in this package
#          documented = integration steps exist; caller must add one-liner
#          gap = needs extra engineering beyond Guard

ENTRY_POINTS: list[dict[str, Any]] = [
    {
        "category": "Initial / Harness eval",
        "path": "research_audit/arch_env_repair_e0/eval_initial_vs_direct.py",
        "status": "documented",
        "note": "Has local env_preflight; migrate to experiment_guard.require_preflight",
    },
    {
        "category": "Initial / Harness eval",
        "path": "research_audit/arch_self_evolution_pilot/eval_independent.py",
        "status": "wired",
        "note": "GuardedExperiment.start before paid arms; guarded concurrent batch; health report",
    },
    {
        "category": "Editor Investigation",
        "path": "research_audit/arch_self_evolution_pilot/run_editor_arms.py",
        "status": "wired",
        "note": "GuardedExperiment.start before Editor; observe infra scan; health report",
    },
    {
        "category": "Architectural Pilot",
        "path": "research_audit/arch_evolution_min_preflight/ab_infoflow_runner.py",
        "status": "documented",
        "note": "Direct path uses infoflow_lib.ffmpeg; still require host/config consistency",
    },
    {
        "category": "Architectural Pilot",
        "path": "research_audit/arch_self_evolution_pilot/stability_runner.py",
        "status": "documented",
        "note": "Wrap paid phases only",
    },
    {
        "category": "Benchmark",
        "path": "run_batch.py",
        "status": "documented",
        "note": "Worker uses config.execution.python; Guard must probe that interpreter",
    },
    {
        "category": "Benchmark",
        "path": "run_batch_checkpoint.py",
        "status": "documented",
        "note": "Add preflight before --allow-provider-calls path; keep existing fingerprint fuse",
    },
    {
        "category": "Train / Gate",
        "path": "solver_full_workspace/cli.py",
        "status": "documented",
        "note": "Hook `run` subcommand only; do not change gate_decision",
    },
    {
        "category": "AutoResearch",
        "path": "research_autoresearch/exp1_glm53/run_*.py",
        "status": "documented",
        "note": "Existing protocol preflight ≠ visual env; compose both",
    },
    {
        "category": "AutoResearch Editor",
        "path": "research_autoresearch/exp1/editor_smoke*.py",
        "status": "documented",
        "note": "Host Investigation; require interpreter match",
    },
    {
        "category": "DSH investigate client",
        "path": "solver_full_workspace/investigate.py",
        "status": "gap",
        "note": "HTTP client to broker; vision runs server-side — needs remote health endpoint",
    },
    {
        "category": "Offline audit / scoring",
        "path": "score.py / research_audit/*/analyze_*.py",
        "status": "wired",
        "note": "Use validate_arm / validate_multi_arm post-hoc; no preflight required",
    },
]


def coverage_summary() -> dict[str, int]:
    from collections import Counter

    return dict(Counter(e["status"] for e in ENTRY_POINTS))


def print_coverage() -> None:
    print("Experiment Guard entry-point coverage")
    for e in ENTRY_POINTS:
        print("- [%s] %s — %s" % (e["status"], e["path"], e["note"]))
    print("summary:", coverage_summary())
