"""Experiment Guard — infrastructure validity for Video-RSI experiments.

Experiment completion ≠ scientific validity. Use this package before/during/after
paid or batch runs without modifying Gate, Harness, or model logic.

Public API:
  from experiment_guard import require_preflight, classify_item_run, validate_batch, write_health_report
  from experiment_guard.guarded_runner import GuardedExperiment
"""
from __future__ import annotations

from experiment_guard.preflight import require_preflight, run_preflight
from experiment_guard.runtime_guard import (
    BatchAbortPolicy,
    classify_item_run,
    classify_error_kind,
    RuntimeGuard,
)
from experiment_guard.result_validator import validate_arm, validate_multi_arm
from experiment_guard.protocol_validator import validate_protocol
from experiment_guard.health_report import write_health_report, build_health_report

__all__ = [
    "require_preflight",
    "run_preflight",
    "classify_item_run",
    "classify_error_kind",
    "BatchAbortPolicy",
    "RuntimeGuard",
    "validate_arm",
    "validate_multi_arm",
    "validate_protocol",
    "write_health_report",
    "build_health_report",
]

__version__ = "1.0.0"
