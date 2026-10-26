#!/usr/bin/env python3
"""Phase D — freeze video-disjoint independent eval IDs (0 API).

Excludes: exploratory n20, editor train subset, Private Gate.
Prefer videos unused by those sets.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PILOT = Path(__file__).resolve().parent
PREFLIGHT = ROOT / "research_audit" / "arch_evolution_min_preflight"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PREFLIGHT))

from infoflow_lib import load_frozen_ids, load_gate_ids, load_train_items, write_json

SEED = 20261029
N = 24


def main() -> int:
    items = load_train_items()
    frozen = set(load_frozen_ids())
    gate = load_gate_ids()
    subset_path = PILOT / "out" / "editor_train_subset.safe.json"
    editor_ids = set(json.loads(subset_path.read_text())["sample_ids"]) if subset_path.is_file() else set()

    blocked_ids = frozen | gate | editor_ids
    blocked_videos = set()
    for sid in blocked_ids:
        if sid in items:
            blocked_videos.add(Path(items[sid]["video_path"]).stem)

    pool = []
    for sid, row in items.items():
        if sid in blocked_ids:
            continue
        stem = Path(row["video_path"]).stem
        if stem in blocked_videos:
            continue
        if not Path(row["video_path"]).is_file():
            continue
        pool.append(sid)

    rng = random.Random(SEED)
    rng.shuffle(pool)
    # diversify types
    by_type = {}
    for sid in pool:
        t = items[sid].get("question_type") or "unk"
        by_type.setdefault(t, []).append(sid)
    selected = []
    types = sorted(by_type)
    while len(selected) < N and any(by_type.values()):
        for t in types:
            if len(selected) >= N:
                break
            if by_type[t]:
                selected.append(by_type[t].pop(0))
    selected = sorted(selected[:N])
    videos = {Path(items[s]["video_path"]).stem for s in selected}
    out = {
        "seed": SEED,
        "n": len(selected),
        "sample_ids": selected,
        "n_unique_videos": len(videos),
        "by_question_type": {
            t: sum(1 for s in selected if items[s].get("question_type") == t) for t in types
        },
        "excluded_sets": ["exploratory_n20", "editor_train_subset", "private_gate"],
        "video_disjoint_from_blocked": True,
        "note": "Frozen before Phase D eval; not for Editor develop or tuning",
    }
    write_json(PILOT / "out" / "independent_eval_ids.safe.json", out)
    print(json.dumps({"n": out["n"], "videos": out["n_unique_videos"], "types": out["by_question_type"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
