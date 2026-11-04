#!/usr/bin/env python3
"""Shared paths and IDs for LongVideoCompBench."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

DS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]
WP1 = (
    REPO_ROOT
    / "research_audit/lvbench_compositional/track_b/minimal_validation_export_v1"
)
NORM = (
    REPO_ROOT
    / "research_audit/lvbench_compositional/track_b/normalized_programs_v1"
)
PILOT = (
    REPO_ROOT
    / "research_audit/lvbench_compositional/track_b/family_level_minimal_validation_pilot_v0.1"
)

# Immutable Track A minimal-validation seed (WP1)
FROZEN_5_2_SEEN = ["SP001", "SP002", "SP005", "SP201", "SP202"]
FROZEN_5_2_UNSEEN = ["P7_VTCD_C2", "P7_TJR_R3"]
FROZEN_5_2 = FROZEN_5_2_SEEN + FROZEN_5_2_UNSEEN

# 11 Stage-2 normalized program graphs
SEED_11 = FROZEN_5_2 + ["A", "B", "P7_R4_F1", "P7_R4_F2"]

# Proposed DEV 7+4 (NOT frozen unless human records say otherwise)
PROPOSED_7_4_SEEN = FROZEN_5_2_SEEN + ["A", "P7_R4_F1"]
PROPOSED_7_4_UNSEEN = FROZEN_5_2_UNSEEN + ["B", "P7_R4_F2"]

DATASET_VERSION = "0.1.0-dev"
ALGO = "longvideocompbenc_bootstrap_v0.1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def qa_id(source_item_id: str) -> str:
    return f"lvcb:qa:{source_item_id}"


def pg_id(source_item_id: str) -> str:
    return f"lvcb:pg:{source_item_id}"


def evidence_id(source_item_id: str, role: str) -> str:
    return f"lvcb:ev:{source_item_id}:{role}"


def review_id(source_item_id: str, kind: str) -> str:
    return f"lvcb:rev:{source_item_id}:{kind}"


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows
