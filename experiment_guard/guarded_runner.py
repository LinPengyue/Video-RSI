"""Public Guarded Runner — wrap outer experiment scripts without touching Gate/Harness algo."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from experiment_guard.fingerprints import config_fingerprint, git_sha, harness_fingerprint
from experiment_guard.health_report import build_health_report, write_health_report
from experiment_guard.preflight import (
    PreflightCapabilities,
    load_config,
    require_preflight,
    run_preflight,
    write_preflight_report,
)
from experiment_guard.protocol_validator import validate_protocol
from experiment_guard.result_validator import validate_arm, validate_multi_arm
from experiment_guard.runtime_guard import BatchAbortPolicy, RuntimeGuard

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class GuardedExperiment:
    """Lifecycle: preflight → observe results → validate → health report.

    Example:
        guard = GuardedExperiment(
            experiment_id="phase_d_retest_v1",
            out_dir=Path("runs/my_exp/guard"),
            capabilities=PreflightCapabilities(visual_sample_frames=True),
        )
        guard.start(reexec=True)  # SystemExit if FAIL
        for result in results:
            if guard.observe(result):
                break  # aborted
        report = guard.finalize(results, gold=gold)
    """

    experiment_id: str
    out_dir: Path
    capabilities: PreflightCapabilities = field(default_factory=PreflightCapabilities)
    config_path: Path | None = None
    harness_dir: Path | None = None
    policy: BatchAbortPolicy = field(default_factory=BatchAbortPolicy)
    require_provider_env: bool = False
    allow_degraded: bool = False

    preflight_report: dict | None = None
    runtime: RuntimeGuard | None = None
    config: dict | None = None
    cfg_fp: str | None = None

    def start(self, *, reexec: bool = True) -> dict:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.config = load_config(self.config_path)
        self.cfg_fp = config_fingerprint(self.config)
        self.preflight_report = require_preflight(
            config=self.config,
            capabilities=self.capabilities,
            reexec=reexec,
            harness_dir=self.harness_dir,
            require_provider_env=self.require_provider_env,
        )
        write_preflight_report(self.preflight_report, self.out_dir / "preflight_report.json")
        self.runtime = RuntimeGuard(policy=self.policy, start_fingerprint=self.cfg_fp)
        return self.preflight_report

    def start_soft(self, *, reexec: bool = False) -> dict:
        """Run preflight without SystemExit (for tests / dry-run reporting)."""
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.config = load_config(self.config_path)
        self.cfg_fp = config_fingerprint(self.config)
        self.preflight_report = run_preflight(
            config=self.config,
            capabilities=self.capabilities,
            reexec=reexec,
            harness_dir=self.harness_dir,
            require_provider_env=self.require_provider_env,
        )
        write_preflight_report(self.preflight_report, self.out_dir / "preflight_report.json")
        self.runtime = RuntimeGuard(policy=self.policy, start_fingerprint=self.cfg_fp)
        return self.preflight_report

    def observe(self, result: dict) -> bool:
        """Record one sample result. Returns True if batch should abort."""
        if self.runtime is None:
            self.runtime = RuntimeGuard(policy=self.policy, start_fingerprint=self.cfg_fp)
        self.runtime.observe_result(result, current_fingerprint=self.cfg_fp)
        return self.runtime.aborted

    def finalize(
        self,
        results: list[dict],
        *,
        gold: dict[str, str] | None = None,
        expected_ids: Iterable[str] | None = None,
        multi_arms: dict[str, list[dict]] | None = None,
        protocol_kwargs: dict | None = None,
        cost: dict | None = None,
    ) -> dict:
        arm_val = validate_arm(
            results,
            gold=gold,
            expected_ids=expected_ids,
            arm_name=self.experiment_id,
            allow_degraded=self.allow_degraded,
            expected_config_fingerprint=self.cfg_fp,
            observed_config_fingerprint=self.cfg_fp,
        )
        (self.out_dir / "arm_validation.json").write_text(
            json.dumps(arm_val, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )

        multi = None
        if multi_arms:
            multi = validate_multi_arm(
                multi_arms,
                gold=gold,
                expected_ids=expected_ids,
                allow_degraded=self.allow_degraded,
            )
            (self.out_dir / "multi_arm_validation.json").write_text(
                json.dumps(multi, indent=2, ensure_ascii=False, default=str) + "\n",
                encoding="utf-8",
            )

        protocol = validate_protocol(**(protocol_kwargs or {}))
        (self.out_dir / "protocol_validation.json").write_text(
            json.dumps(protocol, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        runtime_summary = self.runtime.summary() if self.runtime else None
        if runtime_summary:
            (self.out_dir / "runtime_summary.json").write_text(
                json.dumps(runtime_summary, indent=2, ensure_ascii=False, default=str) + "\n",
                encoding="utf-8",
            )

        health = build_health_report(
            experiment_id=self.experiment_id,
            preflight=self.preflight_report,
            arm_validation=arm_val,
            multi_arm=multi,
            protocol=protocol,
            runtime_summary=runtime_summary,
            code_sha=git_sha(ROOT),
            harness_sha=(harness_fingerprint(self.harness_dir).get("sha16") if self.harness_dir else None),
            config_fingerprint=self.cfg_fp,
            cost=cost,
            diagnostic_paths=[
                str(self.out_dir / "preflight_report.json"),
                str(self.out_dir / "arm_validation.json"),
                str(self.out_dir / "runtime_summary.json"),
            ],
        )
        paths = write_health_report(health, self.out_dir)
        health["_paths"] = {k: str(v) for k, v in paths.items()}

        # Fail-closed: refuse unmarked ranking export
        ranking_path = self.out_dir / "architecture_ranking.json"
        if health.get("usable_for_architecture_ranking"):
            ranking = {
                "usable": True,
                "arm": arm_val.get("architecture_comparable"),
                "multi_arm": (multi or {}).get("arms") if multi else None,
            }
        else:
            ranking = {
                "usable": False,
                "overall_validity": health.get("overall_validity"),
                "reason_codes": health.get("reason_codes"),
                "naive_audit_only": arm_val.get("naive_including_invalid"),
                "warning": "Do not publish as architecture ranking",
            }
        ranking_path.write_text(json.dumps(ranking, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return health


def wrap_main(
    experiment_id: str,
    out_dir: Path,
    main_fn: Callable[[GuardedExperiment], int],
    **guard_kwargs,
) -> int:
    """Convenience: construct guard, call user main, always attempt finalize artifacts if started."""
    guard = GuardedExperiment(experiment_id=experiment_id, out_dir=out_dir, **guard_kwargs)
    return main_fn(guard)


def cli_preflight() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Experiment Guard preflight")
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=ROOT / "experiment_guard" / "out" / "preflight_report.json")
    ap.add_argument("--no-reexec", action="store_true")
    ap.add_argument("--editor", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--require-provider-env", action="store_true")
    ap.add_argument("--soft", action="store_true", help="do not SystemExit on FAIL")
    args = ap.parse_args()
    caps = PreflightCapabilities(
        visual_sample_frames=True,
        editor_investigation=args.editor or args.probe,
        infoflow_probe=args.probe,
    )
    if args.soft:
        report = run_preflight(
            config_path=args.config,
            capabilities=caps,
            reexec=not args.no_reexec,
            require_provider_env=args.require_provider_env,
        )
    else:
        try:
            report = require_preflight(
                config_path=args.config,
                capabilities=caps,
                reexec=not args.no_reexec,
                require_provider_env=args.require_provider_env,
            )
        except SystemExit as exc:
            # still write fail report if possible
            report = run_preflight(
                config_path=args.config,
                capabilities=caps,
                reexec=False,
                require_provider_env=args.require_provider_env,
            )
            write_preflight_report(report, args.out)
            print(str(exc) or "PREFLIGHT_FAIL")
            return 2
    write_preflight_report(report, args.out)
    print(json.dumps({"status": report["status"], "reason_codes": report.get("reason_codes"), "out": str(args.out)}, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(cli_preflight())
