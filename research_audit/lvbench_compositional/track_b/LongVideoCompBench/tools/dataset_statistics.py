#!/usr/bin/env python3
"""Dataset statistics — distinguish confirmed counts from UNKNOWN (never coerce missing→0)."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DS_ROOT, read_jsonl, utc_now, write_json  # noqa: E402


def _unk(counter_key: str, known: int, unknown: int) -> dict:
    return {"confirmed": known, "unknown": unknown, "note": "unknown_not_treated_as_zero"}


def directed_subgraphs(graph: dict, size: int) -> set[tuple]:
    """Label-preserving weakly-connected induced subgraph signatures (simple)."""
    nodes = {n["node_id"]: n for n in graph["nodes"]}
    edges = [(e["source"], e["target"]) for e in graph["edges"]]
    ids = list(nodes)
    sigs = set()
    from itertools import combinations

    for combo in combinations(ids, size):
        subset = set(combo)
        # induced edges
        ind = [(a, b) for a, b in edges if a in subset and b in subset]
        # weakly connected?
        und: dict[str, set[str]] = {n: set() for n in subset}
        for a, b in ind:
            und[a].add(b)
            und[b].add(a)
        seen = set()
        stack = [next(iter(subset))]
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            stack.extend(und[u] - seen)
        if seen != subset:
            continue
        labels = tuple(
            sorted(
                (
                    nodes[n].get("layer2") or nodes[n].get("raw_operator") or "UNK",
                    nodes[n].get("layer1") or "UNK",
                )
                for n in combo
            )
        )
        edge_labs = tuple(sorted(ind))
        sigs.add((labels, edge_labs))
    return sigs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.parse_args()
    videos = read_jsonl(DS_ROOT / "data" / "videos.jsonl")
    qas = read_jsonl(DS_ROOT / "data" / "qa_items.jsonl")
    graphs = read_jsonl(DS_ROOT / "data" / "program_graphs.jsonl")
    reviews = read_jsonl(DS_ROOT / "annotations" / "human_reviews.jsonl")
    splits = json.loads((DS_ROOT / "data" / "splits.json").read_text())

    # video dedup
    vid_freq = Counter()
    for q in qas:
        if q.get("video_id"):
            vid_freq[q["video_id"]] += 1
        else:
            vid_freq["__UNKNOWN_VIDEO__"] += 1

    duration_known = sum(1 for v in videos if v.get("duration_seconds") is not None)
    duration_unknown = len(videos) - duration_known

    split_counts = Counter(q.get("split_assignment") for q in qas)
    gold_counts = Counter()
    for q in qas:
        if q.get("formal_gold") is True:
            gold_counts["Gold"] += 1
        elif q.get("answer_status") == "REJECTED":
            gold_counts["Rejected"] += 1
        else:
            gold_counts["Pending"] += 1

    layer1, layer2 = Counter(), Counter()
    layer1_unk = layer2_unk = 0
    for g in graphs:
        for n in g["nodes"]:
            if n.get("layer1"):
                layer1[n["layer1"]] += 1
            else:
                layer1_unk += 1
            if n.get("layer2"):
                layer2[n["layer2"]] += 1
            else:
                layer2_unk += 1

    sub2, sub3 = set(), set()
    for g in graphs:
        sub2 |= directed_subgraphs(g, 2)
        sub3 |= directed_subgraphs(g, 3)

    # novelty placeholders from stage4 if present — do not invent
    novelty = {
        "atomic_covered": {"confirmed": None, "unknown": True, "source": "not_recomputed_here"},
        "atomic_novel": {"confirmed": None, "unknown": True, "source": "not_recomputed_here"},
        "mixed_ood": {"confirmed": None, "unknown": True, "source": "not_recomputed_here"},
        "note": "Use normalized_programs_v1 Stage4 for novelty; missing ≠ 0.",
    }

    nec_known = nec_pass = nec_unk = 0
    for r in reviews:
        v = r.get("necessity_test_passed")
        if v in ("TRUE", True):
            nec_pass += 1
            nec_known += 1
        elif v in ("FALSE", False):
            nec_known += 1
        else:
            nec_unk += 1

    report = {
        "schema": "longvideocompbenc_coverage_stats_v0_1",
        "built_utc": utc_now(),
        "videos": {
            "unique_video_rows": len(videos),
            "qa_video_frequency": dict(vid_freq),
            "dedup_note": "Multiple QAs may share one video (e.g., SP201/SP202).",
            "duration_seconds": _unk("duration", duration_known, duration_unknown),
        },
        "qa": {
            "n_records": len(qas),
            "n_complete": sum(1 for q in qas if q["record_completeness"] == "COMPLETE"),
            "n_partial": sum(1 for q in qas if q["record_completeness"] == "PARTIAL"),
            "n_graph_only": sum(1 for q in qas if q["record_completeness"] == "GRAPH_ONLY"),
            "independent_source_item_ids": sorted(
                {q.get("source_item_id") for q in qas if q.get("source_item_id")}
            ),
            "split_assignment_counts": dict(split_counts),
            "gold_pending_rejected": dict(gold_counts),
        },
        "splits_declared": {
            "frozen_5_2": splits.get("frozen_5_2"),
            "proposed_7_4_dev": {
                "status": splits["proposed_7_4_dev"]["status"],
                "n_seen": len(splits["proposed_7_4_dev"]["seen"]),
                "n_unseen": len(splits["proposed_7_4_dev"]["unseen"]),
            },
        },
        "layer_coverage": {
            "layer1": dict(layer1),
            "layer1_missing_node_fields": layer1_unk,
            "layer2": dict(layer2),
            "layer2_missing_node_fields": layer2_unk,
        },
        "directed_subgraph_coverage": {
            "unique_2node_signatures": len(sub2),
            "unique_3node_signatures": len(sub3),
        },
        "novelty_distribution": novelty,
        "necessity_audit": {
            "records_with_explicit_pass_fail": nec_known,
            "passed": nec_pass,
            "unknown_or_not_auto_inferred": nec_unk,
            "pass_rate_among_known": (nec_pass / nec_known) if nec_known else None,
        },
        "human_review_workload": {
            "n_review_records": len(reviews),
            "note": "Count of imported review rows only; not hours.",
        },
    }
    write_json(DS_ROOT / "reports" / "coverage_report.json", report)
    print(
        json.dumps(
            {
                "n_videos": len(videos),
                "n_qa": len(qas),
                "n_complete": report["qa"]["n_complete"],
                "n_graph_only": report["qa"]["n_graph_only"],
                "sub2": len(sub2),
                "sub3": len(sub3),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
