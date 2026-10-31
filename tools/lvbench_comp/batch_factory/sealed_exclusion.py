"""Sealed-exclusion registry helpers (no sealed-reservoir access)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
TRACK_B = REPO_ROOT / "research_audit" / "lvbench_compositional" / "track_b"
POLICY_PATH = TRACK_B / "SEALED_POOL_SPLIT_POLICY.json"
BATCH = TRACK_B / "batch_factory"


def load_sealed_exclusion_ids(path: Path | None = None) -> set[str]:
    data = json.loads((path or POLICY_PATH).read_text())
    return set(data.get("exposed_or_construction") or [])


def collect_run_inventory_video_ids(*run_names: str) -> set[str]:
    """Video IDs appearing in batch_factory run_*/video_inventory.jsonl."""
    ids: set[str] = set()
    names = run_names or ("run_001", "run_002", "run_002_patch_regen")
    for name in names:
        inv = BATCH / name / "video_inventory.jsonl"
        if not inv.exists():
            continue
        for line in inv.read_text().splitlines():
            if not line.strip():
                continue
            row: dict[str, Any] = json.loads(line)
            vid = row.get("video_id")
            if vid:
                ids.add(str(vid))
    return ids


def assert_run_inventories_subset_of_exclusion(
    *,
    policy_path: Path | None = None,
    runs: tuple[str, ...] = ("run_001", "run_002", "run_002_patch_regen"),
) -> None:
    exposed = load_sealed_exclusion_ids(policy_path)
    run_ids = collect_run_inventory_video_ids(*runs)
    missing = sorted(run_ids - exposed)
    if missing:
        raise AssertionError(
            "run inventory video IDs missing from sealed exclusion exposed_or_construction: "
            + ", ".join(missing)
        )
