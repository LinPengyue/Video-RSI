"""Public Guarded Runner — wrap outer experiment scripts without touching Gate/Harness algo."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from experiment_guard.concurrent_batch import BatchExecutionReport, run_guarded_batch
from experiment_guard.fingerprint_snapshot import FingerprintSnapshot, capture_snapshot, reread_fingerprint
from experiment_guard.fingerprints import git_sha, harness_fingerprint
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
    """Lifecycle: preflight → observe results → validate → health report."""

    experiment_id: str
    out_dir: Path
    capabilities: PreflightCapabilities = field(default_factory=PreflightCapabilities)
    config_path: Path | None = None
    harness_dir: Path | None = None
    policy: BatchAbortPolicy = field(default_factory=BatchAbortPolicy)
    require_provider_env: bool = False
    allow_degraded: bool = False
    formal_protocol: bool = True

    preflight_report: dict | None = None
    runtime: RuntimeGuard | None = None
    config: dict | None = None
    cfg_fp: str | None = None
    start_snapshot: FingerprintSnapshot | None = None
    batch_report: BatchExecutionReport | None = None

    def start(self, *, reexec: bool = True, config: dict | None = None) -> dict:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        if config is not None:
            self.config = config
        else:
            self.config = load_config(self.config_path)
        self.start_snapshot = capture_snapshot(
            config_path=self.config_path,
            config=self.config if not (self.config_path and Path(self.config_path).is_file()) else None,
            harness_dir=self.harness_dir,
        )
        self.cfg_fp = self.start_snapshot.config_fp
        self.preflight_report = require_preflight(
            config=self.config,
            capabilities=self.capabilities,
            reexec=reexec,
            harness_dir=self.harness_dir,
            require_provider_env=self.require_provider_env,
        )
        # Attach snapshot to preflight artifact
        self.preflight_report = dict(self.preflight_report)
        self.preflight_report["fingerprint_snapshot"] = self.start_snapshot.as_dict()
        write_preflight_report(self.preflight_report, self.out_dir / "preflight_report.json")
        self.runtime = RuntimeGuard(policy=self.policy, start_fingerprint=self.cfg_fp)
        return self.preflight_report

    def start_soft(self, *, reexec: bool = False, config: dict | None = None) -> dict:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        if config is not None:
            self.config = config
        else:
            self.config = load_config(self.config_path)
        self.start_snapshot = capture_snapshot(
            config_path=self.config_path,
            config=self.config if not (self.config_path and Path(self.config_path).is_file()) else None,
            harness_dir=self.harness_dir,
        )
        self.cfg_fp = self.start_snapshot.config_fp
        self.preflight_report = run_preflight(
            config=self.config,
            capabilities=self.capabilities,
            reexec=reexec,
            harness_dir=self.harness_dir,
            require_provider_env=self.require_provider_env,
        )
        self.preflight_report = dict(self.preflight_report)
        self.preflight_report["fingerprint_snapshot"] = self.start_snapshot.as_dict()
        write_preflight_report(self.preflight_report, self.out_dir / "preflight_report.json")
        self.runtime = RuntimeGuard(policy=self.policy, start_fingerprint=self.cfg_fp)
        return self.preflight_report

    def live_fingerprint(self) -> tuple[str | None, str | None]:
        """Re-read config/harness from disk (not the cached start string)."""
        if self.config_path and Path(self.config_path).is_file():
            return reread_fingerprint(
                config_path=self.config_path,
                harness_dir=self.harness_dir,
                fallback_config=self.config,
            )
        # No path — re-hash provided config dict AND re-hash harness from disk
        from experiment_guard.fingerprints import config_fingerprint

        cfg_fp = config_fingerprint(self.config or {})
        harness_sha = harness_fingerprint(self.harness_dir).get("sha16") if self.harness_dir else None
        # If harness_dir set, always re-read harness files from disk
        return cfg_fp, harness_sha

    def observe(self, result: dict) -> bool:
        """Record one sample result. Re-reads fingerprints from disk. Returns True if abort."""
        if self.runtime is None:
            self.runtime = RuntimeGuard(policy=self.policy, start_fingerprint=self.cfg_fp)
        cfg_fp, _ = self.live_fingerprint()
        self.runtime.observe_result(result, current_fingerprint=cfg_fp)
        return self.runtime.aborted

    def run_batch(
        self,
        item_ids: Iterable[str],
        worker: Callable[[str], dict],
        *,
        max_workers: int = 2,
    ) -> BatchExecutionReport:
        if self.runtime is None:
            raise RuntimeError("call start()/start_soft() before run_batch")
        self.batch_report = run_guarded_batch(
            item_ids,
            worker,
            self.runtime,
            max_workers=max_workers,
            fingerprint_fn=self.live_fingerprint,
        )
        (self.out_dir / "batch_execution.json").write_text(
            json.dumps(self.batch_report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self.batch_report

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
        # Re-read fingerprints at finalize for arm validation
        live_cfg, live_harness = self.live_fingerprint()
        arm_val = validate_arm(
            results,
            gold=gold,
            expected_ids=expected_ids,
            arm_name=self.experiment_id,
            allow_degraded=self.allow_degraded,
            expected_config_fingerprint=self.cfg_fp,
            observed_config_fingerprint=live_cfg,
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

        pk = dict(protocol_kwargs or {})
        pk.setdefault("formal", self.formal_protocol)
        protocol = validate_protocol(**pk)
        (self.out_dir / "protocol_validation.json").write_text(
            json.dumps(protocol, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        runtime_summary = self.runtime.summary() if self.runtime else None
        if runtime_summary:
            if self.batch_report:
                runtime_summary = dict(runtime_summary)
                runtime_summary["batch_execution"] = self.batch_report.to_dict()
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
            harness_sha=live_harness or (
                harness_fingerprint(self.harness_dir).get("sha16") if self.harness_dir else None
            ),
            config_fingerprint=live_cfg or self.cfg_fp,
            cost=cost,
            diagnostic_paths=[
                str(self.out_dir / "preflight_report.json"),
                str(self.out_dir / "arm_validation.json"),
                str(self.out_dir / "runtime_summary.json"),
                str(self.out_dir / "protocol_validation.json"),
            ],
            extra={
                "start_snapshot": self.start_snapshot.as_dict() if self.start_snapshot else None,
                "live_config_fp": live_cfg,
                "live_harness_sha": live_harness,
                "fingerprint_drift": bool(self.cfg_fp and live_cfg and self.cfg_fp != live_cfg),
            },
        )
        # Protocol INCOMPLETE/FAIL blocks ranking
        if protocol.get("status") in ("FAIL", "INCOMPLETE"):
            health["usable_for_architecture_ranking"] = False
            if health.get("overall_validity") == "VALID":
                health["overall_validity"] = "PARTIALLY_VALID" if protocol["status"] == "INCOMPLETE" else "INVALID"
            codes = list(health.get("reason_codes") or [])
            for c in protocol.get("reason_codes") or []:
                if c not in codes:
                    codes.append(c)
            health["reason_codes"] = codes

        paths = write_health_report(health, self.out_dir)
        health["_paths"] = {k: str(v) for k, v in paths.items()}

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
                "protocol_status": protocol.get("status"),
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
