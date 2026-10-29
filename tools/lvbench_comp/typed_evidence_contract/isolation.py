"""Experiment isolation checks for Track A."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IsolationPolicy:
    evolution_primitives: set[str]
    held_out_composition_signatures: set[str]
    train_videos: set[str]
    eval_videos: set[str]
    train_uids: set[str]
    eval_uids: set[str]
    initial_harness_id: str = "INITIAL_HARNESS_DECLARED"
    forbid_hs1_as_final_judge: bool = True
    forbid_track_b_sealed_access: bool = True
    notes: list[str] = field(default_factory=list)


def assert_isolation(policy: IsolationPolicy, runtime: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime = runtime or {}
    violations: list[str] = []
    if policy.train_videos & policy.eval_videos:
        violations.append(f"video_overlap:{sorted(policy.train_videos & policy.eval_videos)}")
    if policy.train_uids & policy.eval_uids:
        violations.append(f"uid_overlap:{sorted(policy.train_uids & policy.eval_uids)}")
    leaked = policy.held_out_composition_signatures & set(runtime.get("evolution_seen_signatures", []))
    if leaked:
        violations.append(f"schema_leak:{sorted(leaked)}")
    if runtime.get("using_hs1_as_final_judge") and policy.forbid_hs1_as_final_judge:
        violations.append("hs1_used_as_final_judge")
    if runtime.get("accessed_track_b_sealed") and policy.forbid_track_b_sealed_access:
        violations.append("accessed_track_b_sealed")
    if runtime.get("harness_id") and runtime["harness_id"] != policy.initial_harness_id:
        # Allow only if explicitly declared alternative initial snapshot
        if not runtime.get("harness_explicitly_declared"):
            violations.append("undeclared_harness")
    return {
        "ok": not violations,
        "violations": violations,
        "policy": {
            "initial_harness_id": policy.initial_harness_id,
            "held_out": sorted(policy.held_out_composition_signatures),
            "forbid_hs1": policy.forbid_hs1_as_final_judge,
        },
    }
