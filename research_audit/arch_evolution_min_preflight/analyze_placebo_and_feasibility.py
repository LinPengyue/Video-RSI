#!/usr/bin/env python3
"""Offline preflight for architectural-evolution mini-experiment.

1) Same-code Placebo Gate on R1/R2/R3 parent (initial_harness) results
2) Train-side exploratory sample freeze (no Gate IDs)
3) Info-flow feasibility stats from training_cache

No paid API. Does not modify evolution artifacts. Writes desensitized JSON only.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from solver_full_workspace.engine.common import read_json, validate_config
from solver_full_workspace.engine.evolve import gate_decision
from solver_full_workspace.engine.runner import INITIAL_FILES

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "evolution" / "run-seed42"
OUT = Path(__file__).resolve().parent / "out"
GATE_ORACLE = ROOT / "data" / "lvbench-split" / "gate_oracle.jsonl"
TRAIN_ITEMS = ROOT / "data" / "lvbench-split" / "train_items.jsonl"
TRAIN_ORACLE = ROOT / "data" / "lvbench-split" / "train_oracle.jsonl"
TRAIN_CACHE = RUN / "training_cache" / "initial_harness"
SEED = 20261026
N_TARGET = 20  # within 16–24


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def harness_tree_sha(root: Path) -> str:
    lines = []
    for name in sorted(INITIAL_FILES):
        p = Path(root) / name
        lines.append("%s %s" % (name, sha256_file(p)))
    return hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()


def load_oracle(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["sample_id"]] = row["answer"]
    return out


def load_results_list(path: Path) -> list:
    return read_json(path)


def results_by_id(rows: list) -> dict:
    return {r["sample_id"]: r for r in rows}


def config_fingerprint(config: dict) -> str:
    slim = {
        "protocol": config.get("protocol"),
        "solver": config.get("solver"),
        "execution": {
            "concurrency": config.get("execution", {}).get("concurrency"),
            "linux_isolation": config.get("execution", {}).get("linux_isolation"),
        },
        "services": {
            "deepseek": config.get("services", {}).get("deepseek"),
            "qwen": config.get("services", {}).get("qwen"),
            "temperature": config.get("services", {}).get("temperature"),
            "provider_retries": config.get("services", {}).get("provider_retries"),
        },
        "gate": config.get("gate"),
    }
    blob = json.dumps(slim, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


def placebo_gate() -> dict:
    config = validate_config(read_json(RUN / "effective_config.json"))
    labels = load_oracle(GATE_ORACLE)  # sample_id -> answer (gate_decision expects this dict)
    parents = {}
    for r in (1, 2, 3):
        rows = load_results_list(
            RUN / "rounds" / ("round_%03d" % r) / "private_gate" / "parent" / "results.json"
        )
        parents[r] = rows
        ids = [row["sample_id"] for row in rows]
        assert set(ids) == set(labels), "parent coverage mismatch round %s" % r

    init_sha = harness_tree_sha(RUN / "versions" / "initial_harness")
    phase_parents = {
        r: read_json(RUN / "rounds" / ("round_%03d" % r) / "phase.json").get("parent")
        for r in (1, 2, 3)
    }
    cfg_fp = config_fingerprint(config)

    pairs = []
    # six directed comparisons: a=parent, b=candidate (same initial_harness, eval noise only)
    for a in (1, 2, 3):
        for b in (1, 2, 3):
            if a == b:
                continue
            decision = gate_decision(parents[a], parents[b], labels, config)
            # treat a as parent, b as candidate (same code, different eval noise)
            pairs.append(
                {
                    "parent_round": a,
                    "candidate_round": b,
                    "accepted": decision["accepted"],
                    "status": decision["status"],
                    "accuracy_branch_passed": decision["accuracy_branch_passed"],
                    "efficiency_branch_passed": decision["efficiency_branch_passed"],
                    "parent_correct": decision["parent_correct"],
                    "candidate_correct": decision["candidate_correct"],
                    "fix": decision["fix"],
                    "harm": decision["harm"],
                    "net": decision["net"],
                    "parent_mean_frames": decision["parent_mean_frames"],
                    "candidate_mean_frames": decision["candidate_mean_frames"],
                    "frame_ratio_cand_over_parent": (
                        decision["candidate_mean_frames"] / decision["parent_mean_frames"]
                        if decision["parent_mean_frames"]
                        else None
                    ),
                }
            )

    # answer disagreement matrix
    by = {r: results_by_id(parents[r]) for r in (1, 2, 3)}
    disagree = {}
    for a, b in ((1, 2), (1, 3), (2, 3)):
        n = 0
        both_wrong_diff = 0
        flip_rw = 0
        flip_wr = 0
        for sid, gold in labels.items():
            aa, bb = by[a][sid].get("answer"), by[b][sid].get("answer")
            if aa != bb:
                n += 1
                ca, cb = aa == gold, bb == gold
                if ca and not cb:
                    flip_rw += 1
                elif (not ca) and cb:
                    flip_wr += 1
                elif (not ca) and (not cb):
                    both_wrong_diff += 1
        disagree["r%s_vs_r%s" % (a, b)] = {
            "answer_mismatch": n,
            "right_to_wrong": flip_rw,
            "wrong_to_right": flip_wr,
            "both_wrong_different_letters": both_wrong_diff,
        }

    # invalid / engineering
    status_counts = {
        r: dict(Counter(row.get("status") for row in parents[r])) for r in (1, 2, 3)
    }

    false_accepts = [p for p in pairs if p["accepted"]]
    return {
        "protocol": "same_code_placebo_gate_v1",
        "harness": "initial_harness",
        "harness_tree_sha256": init_sha,
        "phase_parent_fields": phase_parents,
        "effective_config_fingerprint": cfg_fp,
        "models": {
            "deepseek": config["services"]["deepseek"]["request_model"],
            "qwen": config["services"]["qwen"]["request_model"],
            "temperature": config["services"].get("temperature"),
            "concurrency": config["execution"]["concurrency"],
        },
        "n_gate": len(labels),
        "parent_correct": {str(r): sum(1 for sid, g in labels.items() if by[r][sid].get("answer") == g) for r in (1, 2, 3)},
        "directed_pairs": pairs,
        "n_directed_pairs": len(pairs),
        "n_false_accepts_if_treated_as_independent": len(false_accepts),
        "false_accept_pairs": false_accepts,
        "note_on_dependence": (
            "The six directed pairs share the same three noisy evals; "
            "do not treat false-accept count as six i.i.d. Bernoulli trials."
        ),
        "answer_disagreement": disagree,
        "status_counts": status_counts,
        "placebo_gate_exists": len(false_accepts) > 0,
    }


def train_cache_index() -> dict[str, dict]:
    """Index training_cache trajectories by sample_id (desensitized features)."""
    out = {}
    for path in sorted(TRAIN_CACHE.glob("item_*.json")):
        row = read_json(path)
        sid = row.get("sample_id")
        if not sid:
            continue
        mem = row.get("memory") or []
        visual_steps = []
        for m in mem:
            tool = m.get("tool")
            if tool not in ("overview", "scan_interval", "inspect_interval"):
                continue
            obs = m.get("observation") or {}
            frames = obs.get("frames") or []
            ts = [float(f["timestamp"]) for f in frames if isinstance(f, dict) and "timestamp" in f]
            perc = obs.get("perception") or {}
            text = perc.get("text") if isinstance(perc, dict) else ""
            visual_steps.append(
                {
                    "tool": tool,
                    "n_frames": len(frames),
                    "t_min": min(ts) if ts else None,
                    "t_max": max(ts) if ts else None,
                    "perception_chars": len(text or ""),
                    "perception_empty": not bool((text or "").strip()),
                    "frame_ids_only": True,  # no JPEG bytes in cache
                }
            )
        usage = row.get("usage") or {}
        out[sid] = {
            "status": row.get("status"),
            "answered": row.get("status") == "answered",
            "n_memory": len(mem),
            "n_visual_steps": len(visual_steps),
            "n_visual_frames_sum": sum(s["n_frames"] for s in visual_steps),
            "n_nonempty_perceptions": sum(1 for s in visual_steps if not s["perception_empty"]),
            "has_overview": any(s["tool"] == "overview" for s in visual_steps),
            "qwen_calls": usage.get("qwen_calls"),
            "deepseek_calls": usage.get("deepseek_calls"),
            "qwen_frames": usage.get("qwen_frames") or usage.get("frames"),
            "visual_steps": visual_steps,
        }
    return out


def freeze_exploratory_samples() -> dict:
    """Select 16–24 train IDs before any new API; exclude all Gate IDs."""
    rng = random.Random(SEED)
    gate_ids = set(load_oracle(GATE_ORACLE))
    train_oracle = load_oracle(TRAIN_ORACLE)
    cache = train_cache_index()

    items = []
    for line in TRAIN_ITEMS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sid = row["sample_id"]
        if sid in gate_ids:
            continue  # hard exclude reviewed private Gate set
        vp = Path(row["video_path"])
        video_ok = vp.is_file() and vp.stat().st_size > 0
        meta = cache.get(sid) or {}
        items.append(
            {
                "sample_id": sid,
                "question_type": row.get("question_type") or row.get("task_type"),
                "duration": float(row["duration"]),
                "video_stem": vp.stem if video_ok else None,
                "video_ok": video_ok,
                "in_train_cache": sid in cache,
                "cache_correct": (
                    meta.get("answered") and (sid in train_oracle)
                    # correctness checked below without storing gold in output selection logic
                ),
                "n_nonempty_perceptions": meta.get("n_nonempty_perceptions", 0),
                "n_visual_frames_sum": meta.get("n_visual_frames_sum", 0),
                "qwen_frames": meta.get("qwen_frames"),
                "has_overview": meta.get("has_overview", False),
            }
        )

    # attach correctness without writing gold letters into frozen list file later
    for it in items:
        sid = it["sample_id"]
        meta = cache.get(sid)
        if not meta:
            it["traj_correct"] = None
            continue
        # need answer from cache vs oracle — read answer only ephemerally
        # (reload minimal)
        it["traj_correct"] = None

    # reload answers from cache files for correctness flag only
    ans = {}
    for path in TRAIN_CACHE.glob("item_*.json"):
        row = read_json(path)
        ans[row["sample_id"]] = row.get("answer")
    for it in items:
        sid = it["sample_id"]
        if sid in ans and sid in train_oracle:
            it["traj_correct"] = ans[sid] == train_oracle[sid]

    # eligibility: video ok, in cache, has nonempty perception, frames not huge
    eligible = [
        it
        for it in items
        if it["video_ok"]
        and it["in_train_cache"]
        and it["n_nonempty_perceptions"] >= 1
        and it["has_overview"]
        and (it["qwen_frames"] is None or it["qwen_frames"] <= 160)
    ]

    # strata: wrong traj / right traj × question_type; also mix frame budgets
    by_bucket = defaultdict(list)
    for it in eligible:
        key = (
            "correct" if it["traj_correct"] else "wrong" if it["traj_correct"] is False else "unk",
            it["question_type"],
        )
        by_bucket[key].append(it)
    for key in by_bucket:
        rng.shuffle(by_bucket[key])

    # target mix: ~half wrong, half correct; cover all 6 types if possible
    types = sorted({it["question_type"] for it in eligible})
    selected = []
    used_videos = set()
    # first pass: one wrong + one correct per type (12)
    for t in types:
        for label in ("wrong", "correct"):
            pool = [x for x in by_bucket[(label, t)] if x["video_stem"] not in used_videos]
            if not pool:
                pool = list(by_bucket[(label, t)])
            if not pool:
                continue
            pick = pool[0]
            selected.append(pick)
            if pick["video_stem"]:
                used_videos.add(pick["video_stem"])
    # fill to N_TARGET preferring unused videos and diverse frames
    rest = [it for it in eligible if it["sample_id"] not in {s["sample_id"] for s in selected}]
    rng.shuffle(rest)
    rest.sort(key=lambda x: (x["video_stem"] in used_videos, x["n_visual_frames_sum"]))
    for it in rest:
        if len(selected) >= N_TARGET:
            break
        if it["video_stem"] in used_videos and len(selected) >= 16:
            # allow video reuse only if needed near end
            continue
        selected.append(it)
        if it["video_stem"]:
            used_videos.add(it["video_stem"])
    # if still short, allow video reuse
    if len(selected) < 16:
        for it in rest:
            if len(selected) >= 16:
                break
            if it["sample_id"] in {s["sample_id"] for s in selected}:
                continue
            selected.append(it)

    selected = selected[:N_TARGET]
    selected.sort(key=lambda x: x["sample_id"])

    frozen = {
        "seed": SEED,
        "n": len(selected),
        "source": "data/lvbench-split/train_items.jsonl",
        "excluded_sets": ["gate_items / private Gate cohort"],
        "selection_rule": (
            "stratified by (traj_correct, question_type), prefer video-disjoint, "
            "require train_cache nonempty overview perception, qwen_frames<=160; "
            "frozen before any new API"
        ),
        "sample_ids": [s["sample_id"] for s in selected],
        "by_question_type": dict(Counter(s["question_type"] for s in selected)),
        "n_traj_correct": sum(1 for s in selected if s["traj_correct"] is True),
        "n_traj_wrong": sum(1 for s in selected if s["traj_correct"] is False),
        "n_unique_videos": len({s["video_stem"] for s in selected if s["video_stem"]}),
        "items_safe": [
            {
                "sample_id": s["sample_id"],
                "question_type": s["question_type"],
                "duration": s["duration"],
                "video_stem": s["video_stem"],
                "traj_correct_on_initial_cache": s["traj_correct"],
                "n_nonempty_perceptions": s["n_nonempty_perceptions"],
                "qwen_frames_cache": s["qwen_frames"],
                "n_visual_frames_sum": s["n_visual_frames_sum"],
            }
            for s in selected
        ],
        "blocked_examples_not_selected_reasons": {
            "missing_video": sum(1 for it in items if not it["video_ok"]),
            "not_in_cache": sum(1 for it in items if not it["in_train_cache"]),
            "no_nonempty_perception": sum(
                1 for it in items if it["in_train_cache"] and it["n_nonempty_perceptions"] < 1
            ),
            "qwen_frames_gt_160": sum(
                1
                for it in items
                if it.get("qwen_frames") is not None and it["qwen_frames"] > 160
            ),
        },
        "gate_id_leakage_check": {
            "n_selected_in_gate": sum(1 for s in selected if s["sample_id"] in gate_ids),
            "ok": all(s["sample_id"] not in gate_ids for s in selected),
        },
    }
    return frozen, cache


def infoflow_feasibility(cache: dict) -> dict:
    n = len(cache)
    with_overview = sum(1 for v in cache.values() if v.get("has_overview"))
    nonempty = sum(1 for v in cache.values() if v.get("n_nonempty_perceptions", 0) > 0)
    # Can we reconstruct identical frames? timestamps+ids yes; JPEG bytes no — need ffmpeg
    return {
        "path_A": {
            "name": "frames -> Qwen describe -> DeepSeek answer",
            "feasible_without_changing_Services_ABI": True,
            "note": (
                "Services.call('qwen', {frames, prompt}) already takes arbitrary prompt; "
                "DeepSeek path is separate provider.chat. External wrapper can orchestrate A "
                "without editing frozen harness Services signature."
            ),
        },
        "path_B": {
            "name": "frames -> Qwen direct VQA letter",
            "feasible_without_changing_Services_ABI": True,
            "qwen_can_take_answer_prompt": True,
            "note": (
                "Same qwen endpoint; prompt can request single option letter. "
                "No harness edit required if run as offline/external script calling Services/provider."
            ),
            "caveat": "Need parse/validate letter; model may refuse or free-form — fail closed.",
        },
        "identical_frames": {
            "cached_jpeg_bytes_in_training_cache": False,
            "cached_frame_ids_and_timestamps": True,
            "reextract_via_ffmpeg_from_video_path_plus_timestamps": True,
            "fair_A_B_requires": "shared timestamp list (or shared overview 32-frame grid) extracted once, then both prompts on same frame bundle",
        },
        "reusable_observations": {
            "train_cache_items": n,
            "with_overview": with_overview,
            "with_nonempty_perception": nonempty,
            "can_reuse_text_as_path_A_without_new_qwen": True,
            "reusing_text_breaks_fair_frame_identity_for_path_B": (
                "If B needs new Qwen-on-frames while A reuses old text, A/B are not matched on "
                "the same Qwen call — only on timestamps. For strict A/B, either both reuse "
                "nothing (new calls) or B is text-only (invalid for vision direct)."
            ),
        },
        "cost_logging": {
            "meter_events_fields": ["prompt_tokens", "completion_tokens", "role", "frames"],
            "recommend": "external runner wrapping provider.chat with MaaS rates from batch_billing.py",
        },
        "cannot_fairly_compare_from_logs_alone": [
            "Path B (Qwen direct VQA) never appears in historical Solver traces",
            "JPEG bytes absent — must re-extract frames for any new Qwen call",
            "DeepSeek answers in cache conditioned on multi-step tool memory, not single overview text",
            "Stochasticity: single historical DeepSeek answer ≠ fixed Path A replicate",
        ],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    placebo = placebo_gate()
    frozen, cache = freeze_exploratory_samples()
    info = infoflow_feasibility(cache)

    api_plan = {
        "max_qwen_direct_vqa": min(24, frozen["n"]),
        "max_deepseek_control": min(24, frozen["n"]),
        "editor_calls": 0,
        "optional_extra_qwen_describe_if_not_reusing_cache_text": (
            "If strict matched frames for Path A without reusing cached perception text, "
            "add up to N Qwen describe calls (would exceed 24 unless N reduced)."
        ),
        "recommended_first_batch": {
            "n": frozen["n"],
            "mode": (
                "Path B: new Qwen direct VQA on re-extracted overview timestamps; "
                "Path A-control: DeepSeek answers from cached nonempty overview perception text "
                "(no new Qwen) OR DeepSeek on freshly described frames if budget allows"
            ),
            "estimated_calls": {
                "qwen": frozen["n"],
                "deepseek": frozen["n"],
                "editor": 0,
            },
            "stop_do_not_auto_run": True,
        },
    }

    summary = {
        "protocol": "arch_evolution_min_preflight_v1",
        "paid_api_calls": 0,
        "placebo": placebo,
        "infoflow": info,
        "frozen_samples_ref": "exploratory_samples_n20.json",
        "api_plan": api_plan,
        "answers_to_key_questions": {
            "placebo_gate_real": placebo["placebo_gate_exists"],
            "infoflow_ab_reliable": (
                "Feasible via external wrapper + ffmpeg re-extract; "
                "not fair from logs alone for Path B; Path A can partially reuse cache text."
            ),
        },
    }
    (OUT / "preflight_summary.safe.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "placebo_gate.safe.json").write_text(
        json.dumps(placebo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    samples_path = Path(__file__).resolve().parent / "exploratory_samples_n20.json"
    samples_path.write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "infoflow_feasibility.safe.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "api_call_plan.safe.json").write_text(
        json.dumps(api_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "placebo_false_accepts": placebo["n_false_accepts_if_treated_as_independent"],
                "placebo_exists": placebo["placebo_gate_exists"],
                "parent_correct": placebo["parent_correct"],
                "n_frozen": frozen["n"],
                "gate_leak": frozen["gate_id_leakage_check"],
                "types": frozen["by_question_type"],
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
