#!/usr/bin/env python3
"""Phase B — mechanism stability repeats (does not modify infoflow_v1).

For each target sample:
  - reuse frozen frames + frozen A-strict caption from infoflow_v1 when present
  - rep0 = cached infoflow_v1 outcomes (no new API)
  - additional repeats of B-direct / A-strict-answer / C-text on frozen caption
  - one independent fresh caption (+ DeepSeek + C) for caption-quality probe

Requires ARCH_AB_ALLOW_PAID=1 and --execute for paid calls.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = ROOT / "research_audit" / "arch_evolution_min_preflight"
PILOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PREFLIGHT))

from ab_infoflow_runner import (  # noqa: E402
    PATH_A_STRICT,
    PATH_B_DIRECT,
    PATH_C_TEXT,
    apply_usage,
    ensure_frames,
    finalize_answer,
    make_provider,
    record_template,
    summarize_call,
)
from infoflow_lib import (  # noqa: E402
    CAPTION_PROMPT_VERSION,
    PROMPT_VERSION,
    ResultStore,
    TRAIN_ORACLE,
    bundle_sha,
    cache_by_sample_id,
    caption_prompt,
    extract_frames,
    load_frozen_ids,
    load_gate_ids,
    load_json,
    load_oracle,
    load_services_config,
    load_train_items,
    overview_bundle,
    sha256_text,
    text_messages,
    vision_messages,
    vqa_prompt,
    write_json,
)

INFOFLOW_RUN = PREFLIGHT / "runs" / "infoflow_v1"
TARGETS = ["lvbench_2886", "lvbench_3523", "lvbench_531", "lvbench_3472"]
# rep0 = cache; plus EXTRA_REPEATS new paid replicates
EXTRA_REPEATS = 2
PROTOCOL = "mechanism_stability_v1"


def assert_targets_ok():
    frozen = set(load_frozen_ids())
    gate = load_gate_ids()
    for sid in TARGETS:
        if sid not in frozen:
            raise SystemExit("target not in frozen set: %s" % sid)
        if sid in gate:
            raise SystemExit("Gate leak: %s" % sid)


def copy_frames_if_needed(src_dir: Path, dst_dir: Path) -> None:
    if dst_dir.is_dir() and any(dst_dir.glob("*.jpg")):
        return
    if src_dir.is_dir() and any(src_dir.glob("*.jpg")):
        dst_dir.mkdir(parents=True, exist_ok=True)
        for p in src_dir.glob("*.jpg"):
            shutil.copy2(p, dst_dir / p.name)


def load_infoflow_call(sid: str, path: str, stage: str) -> dict | None:
    p = INFOFLOW_RUN / "calls" / ("%s__%s__%s.json" % (sid, path, stage))
    if p.is_file():
        return load_json(p)
    return None


def seed_rep0(store: ResultStore, sid: str) -> dict:
    """Materialize cached infoflow outcomes as stability rep0 (no API)."""
    out = {}
    for path, stage, key in [
        (PATH_B_DIRECT, "answer", "B_direct"),
        (PATH_A_STRICT, "caption", "A_strict_caption"),
        (PATH_A_STRICT, "answer", "A_strict"),
        (PATH_C_TEXT, "answer", "C_text"),
    ]:
        src = load_infoflow_call(sid, path, stage)
        if not src:
            continue
        rec = dict(src)
        rec["stability_rep"] = 0
        rec["stability_source"] = "infoflow_v1_cache"
        # store under stage tagged with rep
        staged = "%s_rep0" % stage
        rec["stage"] = staged
        rec["path"] = path
        # keep original path/stage fields for summarize
        store.save_call({**rec, "stage": staged})
        out[key] = rec
    return out


def run_repeat_answer(
    store: ResultStore,
    provider,
    item,
    gold,
    *,
    path_name: str,
    stage_base: str,
    rep: int,
    messages,
    role: str,
    frames: int,
    extra: dict,
    force: bool = False,
) -> dict:
    stage = "%s_rep%d" % (stage_base, rep)
    existing = store.load_call(item["sample_id"], path_name, stage)
    if existing and existing.get("status") == "ok" and not force:
        return existing
    record = record_template(item["sample_id"], path_name, stage, stability_rep=rep, **extra)
    resp = provider.chat(role, messages, frames=frames)
    apply_usage(record, resp)
    if resp.status == "ok":
        finalize_answer(record, resp.text, item["options"], gold)
    store.save_call(record)
    return record


def per_sample_stability(store, provider, config, items, cache, golds, sid: str) -> dict:
    item = items[sid]
    ov = overview_bundle(cache[sid])
    gold = golds.get(sid)

    # frames: prefer copy from infoflow then ensure
    copy_frames_if_needed(INFOFLOW_RUN / "frames" / sid, store.frames_dir / sid)
    paths, fb_sha = ensure_frames(store, item, ov, config)

    # frozen caption from infoflow A_strict caption
    cap_src = load_infoflow_call(sid, PATH_A_STRICT, "caption")
    if not cap_src or cap_src.get("status") != "ok":
        raise RuntimeError("missing frozen caption for %s" % sid)
    frozen_caption = cap_src["raw_text"]
    frozen_cap_sha = cap_src.get("caption_sha") or sha256_text(frozen_caption)

    seed_rep0(store, sid)

    reps = {"B_direct": [], "A_strict": [], "C_text": []}
    # include rep0 from infoflow
    b0 = load_infoflow_call(sid, PATH_B_DIRECT, "answer")
    a0 = load_infoflow_call(sid, PATH_A_STRICT, "answer")
    c0 = load_infoflow_call(sid, PATH_C_TEXT, "answer")
    reps["B_direct"].append(summarize_call(b0) | {"stability_rep": 0, "source": "cache"})
    reps["A_strict"].append(summarize_call(a0) | {"stability_rep": 0, "source": "cache"})
    reps["C_text"].append(summarize_call(c0) | {"stability_rep": 0, "source": "cache"})

    vqa = vqa_prompt(item["question"], item["options"], caption=None)
    text_prompt = vqa_prompt(item["question"], item["options"], caption=frozen_caption)

    for rep in range(1, EXTRA_REPEATS + 1):
        b = run_repeat_answer(
            store, provider, item, gold,
            path_name=PATH_B_DIRECT, stage_base="answer", rep=rep,
            messages=vision_messages(vqa, paths, ov["timestamps"]),
            role="qwen", frames=len(paths),
            extra={"frame_bundle_sha": fb_sha, "prompt_sha": sha256_text(vqa), "frozen_caption": False},
        )
        a = run_repeat_answer(
            store, provider, item, gold,
            path_name=PATH_A_STRICT, stage_base="answer", rep=rep,
            messages=text_messages(text_prompt),
            role="deepseek", frames=0,
            extra={
                "frame_bundle_sha": fb_sha,
                "caption_sha": frozen_cap_sha,
                "caption_source": "frozen_infoflow_v1",
                "prompt_sha": sha256_text(text_prompt),
            },
        )
        c = run_repeat_answer(
            store, provider, item, gold,
            path_name=PATH_C_TEXT, stage_base="answer", rep=rep,
            messages=text_messages(text_prompt),
            role="qwen", frames=0,
            extra={
                "frame_bundle_sha": fb_sha,
                "caption_sha": frozen_cap_sha,
                "caption_source": "frozen_infoflow_v1",
                "prompt_sha": sha256_text(text_prompt),
            },
        )
        reps["B_direct"].append(summarize_call(b) | {"stability_rep": rep, "source": "new"})
        reps["A_strict"].append(summarize_call(a) | {"stability_rep": rep, "source": "new"})
        reps["C_text"].append(summarize_call(c) | {"stability_rep": rep, "source": "new"})

    # Caption quality: one independent new caption + A_strict + C
    fresh_stage_cap = "caption_fresh1"
    fresh_cap = store.load_call(sid, PATH_A_STRICT, fresh_stage_cap)
    if not (fresh_cap and fresh_cap.get("status") == "ok"):
        c_prompt = caption_prompt()
        fresh_cap = record_template(
            sid, PATH_A_STRICT, fresh_stage_cap,
            caption_prompt_version=CAPTION_PROMPT_VERSION,
            prompt_sha=sha256_text(c_prompt),
            frame_bundle_sha=fb_sha,
            stability_probe="caption_quality",
        )
        resp = provider.chat("qwen", vision_messages(c_prompt, paths, ov["timestamps"]), frames=len(paths))
        apply_usage(fresh_cap, resp)
        if resp.status == "ok":
            fresh_cap["raw_text"] = resp.text
            fresh_cap["status"] = "ok"
            fresh_cap["caption_sha"] = sha256_text(resp.text)
        store.save_call(fresh_cap)

    fresh_text = fresh_cap.get("raw_text") or ""
    fresh_sha = fresh_cap.get("caption_sha") or sha256_text(fresh_text)
    fresh_prompt = vqa_prompt(item["question"], item["options"], caption=fresh_text)
    a_fresh = run_repeat_answer(
        store, provider, item, gold,
        path_name=PATH_A_STRICT, stage_base="answer_fresh1", rep=1,
        messages=text_messages(fresh_prompt), role="deepseek", frames=0,
        extra={"caption_sha": fresh_sha, "caption_source": "fresh1", "frame_bundle_sha": fb_sha},
    )
    c_fresh = run_repeat_answer(
        store, provider, item, gold,
        path_name=PATH_C_TEXT, stage_base="answer_fresh1", rep=1,
        messages=text_messages(fresh_prompt), role="qwen", frames=0,
        extra={"caption_sha": fresh_sha, "caption_source": "fresh1", "frame_bundle_sha": fb_sha},
    )

    def path_stats(rows):
        answers = [r.get("answer") for r in rows]
        corrects = [bool(r.get("correct")) for r in rows]
        ok = [r for r in rows if r.get("status") == "ok"]
        return {
            "n": len(rows),
            "n_ok": len(ok),
            "accuracy": sum(corrects) / len(rows) if rows else None,
            "unique_answers": sorted({a for a in answers if a}),
            "answer_consistency": len(set(answers)) == 1,
            "correct_consistency": len(set(corrects)) == 1,
            "majority_answer": Counter(answers).most_common(1)[0][0] if answers else None,
            "estimated_cny_new": sum(float(r.get("estimated_cny") or 0) for r in rows if r.get("source") == "new"),
            "reps": rows,
        }

    # Hypothesis checks on majority over frozen-caption replicates
    b_stats = path_stats(reps["B_direct"])
    a_stats = path_stats(reps["A_strict"])
    c_stats = path_stats(reps["C_text"])
    b_maj_correct = b_stats["accuracy"] is not None and b_stats["accuracy"] >= 0.5
    a_maj_wrong = a_stats["accuracy"] is not None and a_stats["accuracy"] < 0.5
    c_maj_wrong = c_stats["accuracy"] is not None and c_stats["accuracy"] < 0.5
    vision_retention_holds = bool(b_maj_correct and a_maj_wrong and c_maj_wrong)

    # answerer: frozen caption A vs C majority answers differ
    answerer_holds = (
        a_stats["majority_answer"]
        and c_stats["majority_answer"]
        and a_stats["majority_answer"] != c_stats["majority_answer"]
    )

    # caption quality: fresh caption answers differ from frozen majority
    caption_effect = {
        "frozen_cap_sha": frozen_cap_sha,
        "fresh_cap_sha": fresh_sha,
        "caption_text_changed": frozen_cap_sha != fresh_sha,
        "A_strict_frozen_maj": a_stats["majority_answer"],
        "A_strict_fresh": a_fresh.get("answer"),
        "C_frozen_maj": c_stats["majority_answer"],
        "C_fresh": c_fresh.get("answer"),
        "A_answer_changed": a_stats["majority_answer"] != a_fresh.get("answer"),
        "C_answer_changed": c_stats["majority_answer"] != c_fresh.get("answer"),
        "A_fresh": summarize_call(a_fresh),
        "C_fresh": summarize_call(c_fresh),
        "fresh_caption_status": fresh_cap.get("status"),
        "fresh_caption_cny": fresh_cap.get("estimated_cny"),
    }

    return {
        "sample_id": sid,
        "frame_bundle_sha": fb_sha,
        "frozen_caption_sha": frozen_cap_sha,
        "B_direct": b_stats,
        "A_strict_frozen_caption": a_stats,
        "C_text_frozen_caption": c_stats,
        "caption_quality_probe": caption_effect,
        "hypothesis_checks": {
            "vision_information_loss": {
                "status": "SUPPORTED" if vision_retention_holds else "NOT_REPLICATED",
                "detail": "B majority correct and both frozen-caption paths majority wrong",
            },
            "model_division_of_labor": {
                "status": "SUPPORTED" if answerer_holds else "NOT_REPLICATED",
                "detail": "majority A_strict letter != majority C on frozen caption",
            },
            "caption_refresh": {
                "status": (
                    "SUPPORTED"
                    if caption_effect["caption_text_changed"]
                    and (caption_effect["A_answer_changed"] or caption_effect["C_answer_changed"])
                    else "WEAK_OR_NONE"
                ),
                "detail": "fresh caption changes at least one answerer letter",
            },
        },
    }


def aggregate(results: list[dict]) -> dict:
    hyp = {
        "vision_information_loss": [],
        "model_division_of_labor": [],
        "caption_refresh": [],
    }
    for r in results:
        for k, v in r["hypothesis_checks"].items():
            hyp[k].append({"sample_id": r["sample_id"], "status": v["status"]})

    def score(key, positive="SUPPORTED"):
        rows = hyp[key]
        n_pos = sum(1 for x in rows if x["status"] == positive)
        return {"n_supported": n_pos, "n": len(rows), "per_sample": rows}

    vision = score("vision_information_loss")
    answerer = score("model_division_of_labor")
    caption = score("caption_refresh", positive="SUPPORTED")

    # Gate to Phase C: at least one vision OR answerer hypothesis replicates on ≥1 target
    # and is not explained purely by answer flipping (require answer_consistency on B for vision cases)
    credible = []
    for r in results:
        hc = r["hypothesis_checks"]
        if hc["vision_information_loss"]["status"] == "SUPPORTED" and r["B_direct"].get("answer_consistency"):
            credible.append(("vision_information_loss", r["sample_id"]))
        if hc["model_division_of_labor"]["status"] == "SUPPORTED" and (
            r["A_strict_frozen_caption"].get("answer_consistency")
            or r["C_text_frozen_caption"].get("answer_consistency")
        ):
            credible.append(("model_division_of_labor", r["sample_id"]))

    if len(credible) >= 1:
        gate = "PROCEED_PHASE_C"
        gate_reason = "at least one mechanism hypothesis replicates with answer consistency"
    else:
        gate = "STOP_NO_PHASE_C"
        gate_reason = "core phenomena consistent with random flip / not replicated"

    return {
        "protocol": PROTOCOL,
        "targets": TARGETS,
        "extra_repeats": EXTRA_REPEATS,
        "hypotheses": {
            "vision_information_loss": vision,
            "model_division_of_labor": answerer,
            "caption_refresh": caption,
        },
        "credible_signals": credible,
        "phase_c_gate": gate,
        "phase_c_gate_reason": gate_reason,
        "per_sample": [
            {
                "sample_id": r["sample_id"],
                "hypothesis_checks": r["hypothesis_checks"],
                "B_accuracy": r["B_direct"]["accuracy"],
                "B_answer_consistency": r["B_direct"]["answer_consistency"],
                "A_accuracy": r["A_strict_frozen_caption"]["accuracy"],
                "A_answer_consistency": r["A_strict_frozen_caption"]["answer_consistency"],
                "C_accuracy": r["C_text_frozen_caption"]["accuracy"],
                "C_answer_consistency": r["C_text_frozen_caption"]["answer_consistency"],
                "caption_quality": {
                    "text_changed": r["caption_quality_probe"]["caption_text_changed"],
                    "A_answer_changed": r["caption_quality_probe"]["A_answer_changed"],
                    "C_answer_changed": r["caption_quality_probe"]["C_answer_changed"],
                },
            }
            for r in results
        ],
    }


def safe_aggregate(agg: dict, results: list[dict]) -> dict:
    """Desensitized: no raw text / gold."""
    cost = 0.0
    for r in results:
        for key in ("B_direct", "A_strict_frozen_caption", "C_text_frozen_caption"):
            cost += float(r[key].get("estimated_cny_new") or 0)
        cost += float(r["caption_quality_probe"].get("fresh_caption_cny") or 0)
        cost += float((r["caption_quality_probe"].get("A_fresh") or {}).get("estimated_cny") or 0)
        cost += float((r["caption_quality_probe"].get("C_fresh") or {}).get("estimated_cny") or 0)
    return {
        "protocol": PROTOCOL,
        "phase_c_gate": agg["phase_c_gate"],
        "phase_c_gate_reason": agg["phase_c_gate_reason"],
        "credible_signals": agg["credible_signals"],
        "hypotheses": agg["hypotheses"],
        "per_sample_safe": agg["per_sample"],
        "estimated_cny_new_calls": cost,
        "note": "rep0 from infoflow_v1 cache excluded from new-call cost",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, default=PILOT / "runs" / "stability_v1")
    ap.add_argument("--provider", choices=["mock", "http"], default="mock")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    assert_targets_ok()

    if args.provider == "http":
        if not args.execute or os.environ.get("ARCH_AB_ALLOW_PAID") != "1":
            print("Refusing http without --execute and ARCH_AB_ALLOW_PAID=1", file=sys.stderr)
            return 2

    config = load_services_config()
    store = ResultStore(args.run_dir)
    write_json(store.meta_path, {"protocol": PROTOCOL, "targets": TARGETS, "extra_repeats": EXTRA_REPEATS, "prompt_version": PROMPT_VERSION})
    provider = make_provider(args.provider, config)
    items = load_train_items()
    cache = cache_by_sample_id()
    golds = load_oracle(TRAIN_ORACLE)

    results = []
    for sid in TARGETS:
        print("stability", sid, flush=True)
        results.append(per_sample_stability(store, provider, config, items, cache, golds, sid))
        write_json(args.run_dir / "stability_partial.json", {"done": [r["sample_id"] for r in results]})

    write_json(args.run_dir / "stability_full.json", {"results": results})
    agg = aggregate(results)
    write_json(args.run_dir / "stability_aggregate.json", agg)
    safe = safe_aggregate(agg, results)
    write_json(PILOT / "out" / "stability_summary.safe.json", safe)
    print(json.dumps({"phase_c_gate": agg["phase_c_gate"], "credible": agg["credible_signals"], "safe_cost": safe["estimated_cny_new_calls"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
