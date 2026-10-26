#!/usr/bin/env python3
"""Offline Video-RSI fix-path & historical-harness audit (no paid API).

Reads evolution/run-seed42 Gate dumps + harness trees. Writes ONLY desensitized
JSON under research_audit/video_rsi_fix_paths/out/.

Never writes gold answers, full perception dumps, absolute video paths, or keys.
Does not modify evolution artifacts.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "evolution" / "run-seed42"
OUT = Path(__file__).resolve().parent / "out"
ORACLE = ROOT / "data" / "lvbench-split" / "gate_oracle.jsonl"
ITEMS = ROOT / "data" / "lvbench-split" / "gate_items.jsonl"

FOCUS = ("lvbench_2480", "lvbench_4195", "lvbench_5093")
HARNESS_FILES = (
    "candidate.json",
    "main.py",
    "agent.py",
    "answers.py",
    "memory.py",
    "prompt.md",
    "skill_policy.py",
    "time_utils.py",
    "tools.py",
)
VISUAL = {"overview", "scan_interval", "inspect_interval"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def harness_tree_sha(root: Path) -> str:
    lines = []
    for name in sorted(HARNESS_FILES):
        p = root / name
        if not p.is_file():
            raise FileNotFoundError(p)
        lines.append("%s %s" % (name, sha256_file(p)))
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_oracle() -> dict[str, str]:
    out = {}
    for line in ORACLE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["sample_id"]] = row["answer"]
    return out


def load_items_meta() -> dict[str, dict]:
    out = {}
    for line in ITEMS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["sample_id"]] = {
            "sample_id": row["sample_id"],
            "question_type": row.get("question_type") or row.get("task_type"),
            "duration": row.get("duration"),
            "n_options": len(row.get("options") or {}),
            # question text kept only as length (desensitized)
            "question_chars": len(row.get("question") or ""),
        }
    return out


def load_results(path: Path) -> dict[str, dict]:
    rows = load_json(path)
    return {r["sample_id"]: r for r in rows}


def tool_seq(result: dict) -> list[str]:
    return [m.get("tool") for m in (result.get("memory") or []) if m.get("tool")]


def interval_from_args(args: dict | None) -> dict | None:
    if not isinstance(args, dict):
        return None
    if "start" in args and "end" in args:
        try:
            return {"start": float(args["start"]), "end": float(args["end"])}
        except (TypeError, ValueError):
            return None
    return None


def frames_meta(obs: dict | None) -> dict:
    obs = obs or {}
    frames = obs.get("frames") or []
    ts = []
    for f in frames:
        if isinstance(f, dict) and "timestamp" in f:
            try:
                ts.append(float(f["timestamp"]))
            except (TypeError, ValueError):
                pass
    return {
        "n_frames": len(frames),
        "t_min": min(ts) if ts else None,
        "t_max": max(ts) if ts else None,
        "reused": bool(obs.get("reused")),
    }


def perception_digest(obs: dict | None) -> dict:
    """Desensitized perception features — no free text."""
    obs = obs or {}
    perc = obs.get("perception") or {}
    text = ""
    if isinstance(perc, dict):
        text = str(perc.get("text") or "")
    elif isinstance(perc, str):
        text = perc
    # For ASR / OCR shaped observations
    if not text and "status" in obs:
        text = json.dumps({"status": obs.get("status"), "n_segments": len(obs.get("segments") or [])})
    lower = text.lower()
    return {
        "chars": len(text),
        "empty": len(text.strip()) == 0,
        "mentions_color": bool(re.search(r"\b(color|colour|black|white|blue|red|green|gray|grey|suit|jacket|blazer)\b", lower)),
        "mentions_count": bool(re.search(r"\b(how many|number of|\d+\s+(children|athletes|people|dancers))\b", lower)),
        "mentions_start_list": "start list" in lower or "start-list" in lower or "heat" in lower,
        "unavailable_asr": "unavailable" in lower and "segment" in lower,
        "sha256_12": hashlib.sha256(text.encode()).hexdigest()[:12] if text else None,
    }


def step_timeline(result: dict) -> list[dict]:
    """Build per-memory-step timeline (tool executions). Answer step appended from trace."""
    steps = []
    for i, mem in enumerate(result.get("memory") or []):
        tool = mem.get("tool")
        args = mem.get("arguments") or {}
        obs = mem.get("observation") or {}
        steps.append(
            {
                "step": i,
                "decision": "tool",
                "tool": tool,
                "interval": interval_from_args(args),
                "frames": frames_meta(obs),
                "perception": perception_digest(obs),
                "new_evidence_heuristic": None,  # filled later
            }
        )
    # final answer from last trace decision if present
    answer = result.get("answer")
    steps.append(
        {
            "step": len(steps),
            "decision": "answer",
            "tool": None,
            "answer_letter": answer,
            "status": result.get("status"),
            "usage": {
                "deepseek_calls": (result.get("usage") or {}).get("deepseek_calls"),
                "qwen_calls": (result.get("usage") or {}).get("qwen_calls"),
                "qwen_frames": (result.get("usage") or {}).get("qwen_frames")
                or (result.get("usage") or {}).get("frames"),
            },
        }
    )
    # mark new evidence: non-empty perception not seen by sha before
    seen = set()
    for s in steps:
        if s.get("decision") != "tool":
            continue
        dig = s["perception"]
        sha = dig.get("sha256_12")
        if dig.get("empty"):
            s["new_evidence_heuristic"] = False
        elif sha and sha not in seen:
            s["new_evidence_heuristic"] = True
            seen.add(sha)
        else:
            s["new_evidence_heuristic"] = False
    return steps


def flips(parent: dict, cand: dict, oracle: dict) -> tuple[list[str], list[str]]:
    fix, harm = [], []
    for sid in sorted(set(parent) & set(cand) & set(oracle)):
        gold = oracle[sid]
        pok = parent[sid].get("answer") == gold
        cok = cand[sid].get("answer") == gold
        if not pok and cok:
            fix.append(sid)
        if pok and not cok:
            harm.append(sid)
    return fix, harm


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def changed_files(parent_dir: Path, cand_dir: Path) -> list[str]:
    out = []
    for name in HARNESS_FILES:
        pb, cb = parent_dir / name, cand_dir / name
        if not pb.is_file() or not cb.is_file():
            continue
        if sha256_file(pb) != sha256_file(cb):
            out.append(name)
    return out


def classify_edit(changed: list[str], plan_text: str, summary_text: str) -> list[dict]:
    blob = (plan_text + "\n" + summary_text).lower()
    cats = []

    def add(cat, primary, note):
        cats.append({"category": cat, "primary": primary, "note": note})

    if "tools.py" in changed:
        if "transcript" in blob or "read_transcript" in blob:
            add("Tool / Perception", True, "tools.py: transcript tool surface")
        if "cache" in blob or "reused" in blob:
            add("Engineering / Cache / Error Handling", True, "tools.py: visual cache")
            add("Evidence Representation", False, "cache returns prior observation object")
        if "tools.py" in changed and not cats:
            add("Tool / Perception", True, "tools.py changed")
    if "prompt.md" in changed:
        add("Prompt-only", True, "prompt.md changed")
        add("Reasoning / Control Flow", False, "prompt may steer stop/reuse behavior")
    if "agent.py" in changed or "main.py" in changed:
        add("Reasoning / Control Flow", True, "agent/main loop files changed")
        add("Model Role / Information Flow", False, "possible role/routing change")
    if "memory.py" in changed:
        add("Memory", True, "memory.py changed")
    if not cats and changed:
        add("Engineering / Cache / Error Handling", True, "other harness files: " + ",".join(changed))
    return cats


def focus_case_report(sid: str, parent: dict, cand: dict, meta: dict, gold: str) -> dict:
    pr, cr = parent[sid], cand[sid]
    p_steps = step_timeline(pr)
    c_steps = step_timeline(cr)
    p_tools = tool_seq(pr)
    c_tools = tool_seq(cr)
    return {
        "sample_id": sid,
        "question_type": meta.get("question_type"),
        "duration": meta.get("duration"),
        "gold_omitted": True,
        "parent_correct": pr.get("answer") == gold,
        "candidate_correct": cr.get("answer") == gold,
        "parent_answer_letter": pr.get("answer"),
        "candidate_answer_letter": cr.get("answer"),
        "parent_tool_seq": p_tools,
        "candidate_tool_seq": c_tools,
        "parent_has_transcript": "read_transcript" in p_tools,
        "candidate_has_transcript": "read_transcript" in c_tools,
        "parent_n_visual": sum(t in VISUAL for t in p_tools),
        "candidate_n_visual": sum(t in VISUAL for t in c_tools),
        "parent_timeline": p_steps,
        "candidate_timeline": c_steps,
        "parent_usage": (pr.get("usage") or {}),
        "candidate_usage": (cr.get("usage") or {}),
        "notes_desensitized": True,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    oracle = load_oracle()
    items = load_items_meta()
    init = RUN / "versions" / "initial_harness"
    hs1 = RUN / "versions" / "H_S1"
    init_sha = harness_tree_sha(init)
    hs1_sha = harness_tree_sha(hs1)

    rounds = {}
    fix_sets = {}
    harm_sets = {}
    for r in (1, 2, 3):
        base = RUN / "rounds" / ("round_%03d" % r)
        phase = load_json(base / "phase.json")
        rr = load_json(base / "round_result.json")
        parent = load_results(base / "private_gate" / "parent" / "results.json")
        cand = load_results(base / "private_gate" / "candidate" / "results.json")
        fix, harm = flips(parent, cand, oracle)
        # recompute correctness counts
        p_ok = sum(1 for sid in oracle if parent.get(sid, {}).get("answer") == oracle[sid])
        c_ok = sum(1 for sid in oracle if cand.get(sid, {}).get("answer") == oracle[sid])
        snap = base / "candidate_snapshot"
        snap_sha = harness_tree_sha(snap) if snap.is_dir() else None
        plan = base / "workspace" / "analysis" / "edit_plan.md"
        summary = base / "workspace" / "analysis" / "edit_summary.md"
        plan_text = plan.read_text(encoding="utf-8") if plan.is_file() else ""
        summary_text = summary.read_text(encoding="utf-8") if summary.is_file() else ""
        changed = changed_files(init, snap) if snap.is_dir() else []
        rounds[str(r)] = {
            "phase_parent": phase.get("parent"),
            "phase_accepted": phase.get("accepted"),
            "phase_target_version": phase.get("target_version"),
            "gate_accepted": rr.get("accepted"),
            "n": rr.get("n"),
            "parent_correct_logged": rr.get("parent_correct"),
            "candidate_correct_logged": rr.get("candidate_correct"),
            "parent_correct_recomputed": p_ok,
            "candidate_correct_recomputed": c_ok,
            "fix_logged": rr.get("fix"),
            "harm_logged": rr.get("harm"),
            "net_logged": rr.get("net"),
            "fix_recomputed_n": len(fix),
            "harm_recomputed_n": len(harm),
            "fix_sample_ids": fix,
            "harm_sample_ids": harm,
            "candidate_snapshot_sha256": snap_sha,
            "matches_initial_harness": snap_sha == init_sha,
            "matches_H_S1": snap_sha == hs1_sha,
            "changed_files_vs_initial": changed,
            "edit_categories": classify_edit(changed, plan_text, summary_text),
            "edit_plan_sha256": sha256_file(plan) if plan.is_file() else None,
            "edit_summary_sha256": sha256_file(summary) if summary.is_file() else None,
            "parent_mean_frames": rr.get("parent_mean_frames"),
            "candidate_mean_frames": rr.get("candidate_mean_frames"),
        }
        fix_sets[r] = set(fix)
        harm_sets[r] = set(harm)

    # Parent stability across rounds (same harness, three Gate evals)
    parent_answers = {}
    for r in (1, 2, 3):
        parent = load_results(
            RUN / "rounds" / ("round_%03d" % r) / "private_gate" / "parent" / "results.json"
        )
        parent_answers[r] = {sid: parent[sid].get("answer") for sid in oracle if sid in parent}

    disagree_12 = sum(1 for sid in oracle if parent_answers[1].get(sid) != parent_answers[2].get(sid))
    disagree_23 = sum(1 for sid in oracle if parent_answers[2].get(sid) != parent_answers[3].get(sid))
    disagree_13 = sum(1 for sid in oracle if parent_answers[1].get(sid) != parent_answers[3].get(sid))
    always_right = sum(
        1
        for sid in oracle
        if parent_answers[1].get(sid) == oracle[sid]
        and parent_answers[2].get(sid) == oracle[sid]
        and parent_answers[3].get(sid) == oracle[sid]
    )
    always_wrong = sum(
        1
        for sid in oracle
        if parent_answers[1].get(sid) != oracle[sid]
        and parent_answers[2].get(sid) != oracle[sid]
        and parent_answers[3].get(sid) != oracle[sid]
    )

    # Cross-round fix/harm
    cross = {
        "fix_jaccard": {
            "r1_r2": jaccard(fix_sets[1], fix_sets[2]),
            "r1_r3": jaccard(fix_sets[1], fix_sets[3]),
            "r2_r3": jaccard(fix_sets[2], fix_sets[3]),
        },
        "harm_jaccard": {
            "r1_r2": jaccard(harm_sets[1], harm_sets[2]),
            "r1_r3": jaccard(harm_sets[1], harm_sets[3]),
            "r2_r3": jaccard(harm_sets[2], harm_sets[3]),
        },
        "fix_intersection_all3": sorted(fix_sets[1] & fix_sets[2] & fix_sets[3]),
        "fix_only_r1": sorted(fix_sets[1] - fix_sets[2] - fix_sets[3]),
        "fix_only_r2": sorted(fix_sets[2] - fix_sets[1] - fix_sets[3]),
        "fix_only_r3": sorted(fix_sets[3] - fix_sets[1] - fix_sets[2]),
        "fix_r1_or_r2_not_r3": sorted((fix_sets[1] | fix_sets[2]) - fix_sets[3]),
        "harm_only_r3": sorted(harm_sets[3] - harm_sets[1] - harm_sets[2]),
        # samples fixed in earlier rejected round then harmed in later?
        "fixed_r1_harmed_r2": sorted(fix_sets[1] & harm_sets[2]),
        "fixed_r1_harmed_r3": sorted(fix_sets[1] & harm_sets[3]),
        "fixed_r2_harmed_r3": sorted(fix_sets[2] & harm_sets[3]),
    }

    # Focus cases from R3
    p3 = load_results(RUN / "rounds" / "round_003" / "private_gate" / "parent" / "results.json")
    c3 = load_results(RUN / "rounds" / "round_003" / "private_gate" / "candidate" / "results.json")
    focus = {
        sid: focus_case_report(sid, p3, c3, items.get(sid, {}), oracle[sid]) for sid in FOCUS
    }

    # Mechanism pattern stats on R3 fixes (desensitized)
    r3_fix = rounds["3"]["fix_sample_ids"]
    patterns = Counter()
    for sid in r3_fix:
        pt, ct = tool_seq(p3[sid]), tool_seq(c3[sid])
        if "read_transcript" in pt and "read_transcript" not in ct:
            patterns["parent_transcript_cand_none"] += 1
        if sum(t in VISUAL for t in ct) > sum(t in VISUAL for t in pt):
            patterns["cand_more_visual_calls"] += 1
        if sum(t in VISUAL for t in ct) < sum(t in VISUAL for t in pt):
            patterns["cand_fewer_visual_calls"] += 1
        if pt == ["overview"]:
            patterns["parent_overview_only"] += 1
        if any((m.get("observation") or {}).get("reused") for m in (c3[sid].get("memory") or [])):
            patterns["cand_visual_cache_hit"] += 1

    summary = {
        "protocol": "video_rsi_fix_path_audit_v1",
        "paid_api_calls": 0,
        "run_root": "evolution/run-seed42",
        "initial_harness_tree_sha256": init_sha,
        "H_S1_tree_sha256": hs1_sha,
        "rounds": rounds,
        "parent_reeval_stability": {
            "note": "phase.json parent is initial_harness for R1/R2/R3; parent_correct drift is same-harness re-eval",
            "parent_correct_sequence": [
                rounds["1"]["parent_correct_recomputed"],
                rounds["2"]["parent_correct_recomputed"],
                rounds["3"]["parent_correct_recomputed"],
            ],
            "answer_disagreements": {"r1_vs_r2": disagree_12, "r2_vs_r3": disagree_23, "r1_vs_r3": disagree_13},
            "always_correct_across_3_evals": always_right,
            "always_wrong_across_3_evals": always_wrong,
            "n": len(oracle),
        },
        "cross_round": cross,
        "r3_fix_behavior_patterns": dict(patterns),
        "focus_cases": focus,
        "omissions": {
            "gold_answers": True,
            "full_perception_text": True,
            "absolute_video_paths": True,
            "api_keys": True,
        },
    }

    (OUT / "audit_summary.safe.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Compact printable stats
    print(json.dumps({
        "rounds_ok": {
            r: {
                "accepted": rounds[r]["gate_accepted"],
                "parent": rounds[r]["parent_correct_recomputed"],
                "cand": rounds[r]["candidate_correct_recomputed"],
                "fix": rounds[r]["fix_recomputed_n"],
                "harm": rounds[r]["harm_recomputed_n"],
                "parent_phase": rounds[r]["phase_parent"],
                "snap_is_H_S1": rounds[r]["matches_H_S1"],
                "changed": rounds[r]["changed_files_vs_initial"],
            }
            for r in rounds
        },
        "parent_disagreements": summary["parent_reeval_stability"]["answer_disagreements"],
        "fix_jaccard": cross["fix_jaccard"],
        "fix_r1_or_r2_not_r3_n": len(cross["fix_r1_or_r2_not_r3"]),
        "r3_patterns": dict(patterns),
        "out": str(OUT / "audit_summary.safe.json"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
