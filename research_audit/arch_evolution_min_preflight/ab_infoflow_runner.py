#!/usr/bin/env python3
"""Controlled info-flow mechanism runner (A-reuse / B-direct / A-strict / C-text-only).

Default is offline (mock / dry-run). Paid HTTPS calls require:
  ARCH_AB_ALLOW_PAID=1  AND  --execute
and a sourced providers.env (API_BASE / API_KEY).

Does not import Editor, does not run Gate/RSI, does not mutate evolution/.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from infoflow_lib import (
    BUDGET_DEEPSEEK_AREUSE,
    BUDGET_DIAG_MAX_SAMPLES,
    BUDGET_QWEN_DIRECT,
    CAPTION_PROMPT_VERSION,
    PREFLIGHT,
    PROMPT_VERSION,
    PROTOCOL,
    ResultStore,
    caption_prompt,
    connectivity_ids,
    estimate_cny,
    extract_frames,
    bundle_sha,
    cache_by_sample_id,
    HttpProvider,
    MockProvider,
    load_frozen_ids,
    load_gate_ids,
    load_oracle,
    load_services_config,
    load_train_items,
    overview_bundle,
    parse_answer_letter,
    pick_diag_ids,
    sha256_text,
    text_messages,
    TRAIN_ORACLE,
    vision_messages,
    vqa_prompt,
    write_json,
    load_json,
)


PATH_A_REUSE = "A_reuse"
PATH_B_DIRECT = "B_direct"
PATH_A_STRICT = "A_strict"
PATH_C_TEXT = "C_text_only"


def assert_no_gate_leak(ids: list[str]) -> None:
    gate = load_gate_ids()
    leak = [i for i in ids if i in gate]
    if leak:
        raise SystemExit("ABORT Gate leakage: %s" % leak)


def make_provider(mode: str, config: dict):
    if mode == "mock":
        return MockProvider()
    if mode == "http":
        return HttpProvider(config)
    raise ValueError(mode)


def record_template(sample_id: str, path: str, stage: str, **extra) -> dict:
    row = {
        "protocol": PROTOCOL,
        "sample_id": sample_id,
        "path": path,
        "stage": stage,
        "prompt_version": PROMPT_VERSION,
        "status": "pending",
        "answer": None,
        "parse_mode": None,
        "parse_error": "",
        "correct": None,
        "raw_text": "",
        "usage": {},
        "estimated_cny": 0.0,
        "request_model": "",
        "role": "",
        "n_frames": 0,
        "frame_bundle_sha": None,
        "caption_sha": None,
        "error": "",
        "latency_seconds": None,
        "created_at": time.time(),
    }
    row.update(extra)
    return row


def finalize_answer(record: dict, text: str, options: dict, gold: str | None) -> dict:
    letter, mode, err = parse_answer_letter(text, options)
    record["raw_text"] = text
    record["answer"] = letter
    record["parse_mode"] = mode
    record["parse_error"] = err
    if letter is None:
        record["status"] = "parse_error"
        record["correct"] = False
    else:
        record["status"] = "ok"
        record["correct"] = (gold is not None and letter == gold)
    return record


def apply_usage(record: dict, resp) -> None:
    record["usage"] = dict(resp.usage or {})
    record["request_model"] = resp.request_model
    record["role"] = resp.role
    record["n_frames"] = resp.frames
    record["latency_seconds"] = resp.latency_seconds
    if resp.status != "ok":
        record["status"] = "provider_error"
        record["error"] = resp.error
        record["correct"] = False
        return
    pt = int(record["usage"].get("prompt_tokens") or 0)
    ct = int(record["usage"].get("completion_tokens") or 0)
    cached = int(record["usage"].get("cached_tokens") or 0)
    record["estimated_cny"] = estimate_cny(resp.role, pt, ct, cached)


def run_a_reuse(store: ResultStore, provider, item: dict, ov: dict, gold: str | None, force: bool = False) -> dict:
    sid = item["sample_id"]
    existing = store.load_call(sid, PATH_A_REUSE, "answer")
    if existing and existing.get("status") == "ok" and not force:
        return existing
    prompt = vqa_prompt(item["question"], item["options"], caption=ov["perception_text"])
    record = record_template(
        sid,
        PATH_A_REUSE,
        "answer",
        caption_source="train_cache_overview_perception",
        caption_sha=sha256_text(ov["perception_text"]),
        prompt_sha=sha256_text(prompt),
        note="exploratory cheap control; not byte-matched to frames",
    )
    resp = provider.chat("deepseek", text_messages(prompt), frames=0)
    apply_usage(record, resp)
    if resp.status == "ok":
        finalize_answer(record, resp.text, item["options"], gold)
    store.save_call(record)
    return record


def ensure_frames(store: ResultStore, item: dict, ov: dict, config: dict) -> tuple[list[Path], str]:
    sid = item["sample_id"]
    out_dir = store.frames_dir / sid
    paths = extract_frames(Path(item["video_path"]), ov["timestamps"], out_dir, config)
    if len(paths) != len(ov["timestamps"]):
        raise RuntimeError("frame count mismatch")
    return paths, bundle_sha(paths)


def run_b_direct(store: ResultStore, provider, item: dict, ov: dict, gold: str | None, config: dict, force: bool = False) -> dict:
    sid = item["sample_id"]
    existing = store.load_call(sid, PATH_B_DIRECT, "answer")
    if existing and existing.get("status") == "ok" and not force:
        return existing
    paths, fb_sha = ensure_frames(store, item, ov, config)
    prompt = vqa_prompt(item["question"], item["options"], caption=None)
    record = record_template(
        sid,
        PATH_B_DIRECT,
        "answer",
        prompt_sha=sha256_text(prompt),
        frame_bundle_sha=fb_sha,
        timestamps=ov["timestamps"],
        n_overview_frames=len(paths),
    )
    resp = provider.chat(
        "qwen",
        vision_messages(prompt, paths, ov["timestamps"]),
        frames=len(paths),
    )
    apply_usage(record, resp)
    if resp.status == "ok":
        finalize_answer(record, resp.text, item["options"], gold)
    store.save_call(record)
    return record


def run_a_strict(store: ResultStore, provider, item: dict, ov: dict, gold: str | None, config: dict, force: bool = False) -> dict:
    """New caption on same frames + DeepSeek answer. Stages: caption, answer."""
    sid = item["sample_id"]
    cap_existing = store.load_call(sid, PATH_A_STRICT, "caption")
    ans_existing = store.load_call(sid, PATH_A_STRICT, "answer")
    if ans_existing and ans_existing.get("status") == "ok" and not force:
        return ans_existing

    paths, fb_sha = ensure_frames(store, item, ov, config)

    if cap_existing and cap_existing.get("status") == "ok" and not force:
        caption = cap_existing["raw_text"]
        cap_rec = cap_existing
    else:
        c_prompt = caption_prompt()
        cap_rec = record_template(
            sid,
            PATH_A_STRICT,
            "caption",
            caption_prompt_version=CAPTION_PROMPT_VERSION,
            prompt_sha=sha256_text(c_prompt),
            frame_bundle_sha=fb_sha,
            timestamps=ov["timestamps"],
        )
        resp = provider.chat(
            "qwen",
            vision_messages(c_prompt, paths, ov["timestamps"]),
            frames=len(paths),
        )
        apply_usage(cap_rec, resp)
        if resp.status != "ok":
            store.save_call(cap_rec)
            return cap_rec
        cap_rec["raw_text"] = resp.text
        cap_rec["status"] = "ok"
        cap_rec["caption_sha"] = sha256_text(resp.text)
        store.save_call(cap_rec)
        caption = resp.text

    prompt = vqa_prompt(item["question"], item["options"], caption=caption)
    record = record_template(
        sid,
        PATH_A_STRICT,
        "answer",
        caption_source="fresh_qwen_caption_same_frames",
        caption_sha=sha256_text(caption),
        prompt_sha=sha256_text(prompt),
        frame_bundle_sha=fb_sha,
    )
    resp = provider.chat("deepseek", text_messages(prompt), frames=0)
    apply_usage(record, resp)
    if resp.status == "ok":
        finalize_answer(record, resp.text, item["options"], gold)
    store.save_call(record)
    return record


def run_c_text_only(store: ResultStore, provider, item: dict, gold: str | None, caption: str, caption_sha: str, frame_bundle_sha: str | None, force: bool = False) -> dict:
    """Same caption text → Qwen text-only VQA (no images)."""
    sid = item["sample_id"]
    existing = store.load_call(sid, PATH_C_TEXT, "answer")
    if existing and existing.get("status") == "ok" and not force:
        return existing
    prompt = vqa_prompt(item["question"], item["options"], caption=caption)
    record = record_template(
        sid,
        PATH_C_TEXT,
        "answer",
        caption_source="shared_with_A_strict",
        caption_sha=caption_sha,
        prompt_sha=sha256_text(prompt),
        frame_bundle_sha=frame_bundle_sha,
        note="text-only; no frames in this call",
    )
    resp = provider.chat("qwen", text_messages(prompt), frames=0)
    apply_usage(record, resp)
    if resp.status == "ok":
        finalize_answer(record, resp.text, item["options"], gold)
    store.save_call(record)
    return record


def budget_ok_first_batch(store: ResultStore) -> tuple[bool, str]:
    qd = store.count_ok(PATH_B_DIRECT, "answer")
    da = store.count_ok(PATH_A_REUSE, "answer")
    if qd > BUDGET_QWEN_DIRECT:
        return False, "qwen_direct over budget"
    if da > BUDGET_DEEPSEEK_AREUSE:
        return False, "deepseek_areuse over budget"
    return True, "ok"


def phase_connectivity(store: ResultStore, provider, config: dict, items: dict, cache: dict, golds: dict) -> dict:
    ids = connectivity_ids(load_frozen_ids(), 4)
    assert_no_gate_leak(ids)
    results = []
    for sid in ids:
        item = items[sid]
        ov = overview_bundle(cache[sid])
        gold = golds.get(sid)
        a = run_a_reuse(store, provider, item, ov, gold)
        b = run_b_direct(store, provider, item, ov, gold, config)
        results.append({"sample_id": sid, "A_reuse": summarize_call(a), "B_direct": summarize_call(b)})
        # Systemic failure stop
        for label, row in (("A", a), ("B", b)):
            if row.get("status") in ("provider_error",) and "video" in (row.get("error") or "").lower():
                raise RuntimeError("systemic video/provider failure on %s %s: %s" % (sid, label, row.get("error")))
    ok_a = all(r["A_reuse"]["status"] == "ok" for r in results)
    ok_b = all(r["B_direct"]["status"] == "ok" for r in results)
    parse_ok = all(r["A_reuse"]["answer"] and r["B_direct"]["answer"] for r in results)
    return {
        "phase": "connectivity",
        "sample_ids": ids,
        "pass": ok_a and ok_b and parse_ok,
        "ok_a": ok_a,
        "ok_b": ok_b,
        "parse_ok": parse_ok,
        "results": results,
        "note": "connectivity only; do not draw scientific conclusions",
    }


def summarize_call(row: dict) -> dict:
    return {
        "status": row.get("status"),
        "answer": row.get("answer"),
        "correct": row.get("correct"),
        "parse_mode": row.get("parse_mode"),
        "estimated_cny": row.get("estimated_cny"),
        "n_frames": row.get("n_frames"),
        "frame_bundle_sha": row.get("frame_bundle_sha"),
        "caption_sha": row.get("caption_sha"),
        "error": row.get("error") or row.get("parse_error"),
        "usage": row.get("usage"),
        "request_model": row.get("request_model"),
    }


def phase_full_ab(store: ResultStore, provider, config: dict, items: dict, cache: dict, golds: dict) -> dict:
    ids = load_frozen_ids()
    assert_no_gate_leak(ids)
    rows = []
    for sid in ids:
        ok, msg = budget_ok_first_batch(store)
        if not ok:
            raise RuntimeError(msg)
        item = items[sid]
        ov = overview_bundle(cache[sid])
        gold = golds.get(sid)
        a = run_a_reuse(store, provider, item, ov, gold)
        b = run_b_direct(store, provider, item, ov, gold, config)
        if a.get("status") not in ("ok",) or b.get("status") not in ("ok",):
            # stop on systemic issues
            if a.get("status") == "provider_error" or b.get("status") == "provider_error":
                raise RuntimeError("provider_error on %s A=%s B=%s" % (sid, a.get("error"), b.get("error")))
        rows.append({"sample_id": sid, "question_type": item.get("question_type"), "A_reuse": a, "B_direct": b})
    return {"phase": "full_ab", "n": len(rows), "rows": rows}


def phase_diagnose(store: ResultStore, provider, config: dict, items: dict, cache: dict, golds: dict, ab_summary: dict) -> dict:
    disagree = []
    for row in ab_summary["per_item"]:
        if row["A_correct"] != row["B_correct"]:
            disagree.append(row["sample_id"])
        elif row["A_answer"] != row["B_answer"]:
            # both wrong or both right with different letters — include letter disagreements
            disagree.append(row["sample_id"])
    # Prefer correctness disagreements first
    corr_disagree = [r["sample_id"] for r in ab_summary["per_item"] if r["A_correct"] != r["B_correct"]]
    letter_disagree = [
        r["sample_id"]
        for r in ab_summary["per_item"]
        if r["A_answer"] != r["B_answer"] and r["sample_id"] not in corr_disagree
    ]
    ordered = corr_disagree + letter_disagree
    selected = pick_diag_ids(ordered, BUDGET_DIAG_MAX_SAMPLES)
    # Re-pick preserving priority: take from ordered in DIAG shuffle among top pool
    # Override: use ordered list truncated after fixed shuffle of the disagreement set
    selected = pick_diag_ids(ordered, BUDGET_DIAG_MAX_SAMPLES)
    # Actually pick_diag_ids shuffles — for priority keep corr_disagree first then fill
    rng_selected = list(corr_disagree)
    for sid in pick_diag_ids(letter_disagree, BUDGET_DIAG_MAX_SAMPLES):
        if sid not in rng_selected and len(rng_selected) < BUDGET_DIAG_MAX_SAMPLES:
            rng_selected.append(sid)
    selected = sorted(rng_selected[:BUDGET_DIAG_MAX_SAMPLES])

    out_rows = []
    for sid in selected:
        item = items[sid]
        ov = overview_bundle(cache[sid])
        gold = golds.get(sid)
        a_strict = run_a_strict(store, provider, item, ov, gold, config)
        if a_strict.get("stage") == "caption" and a_strict.get("status") != "ok":
            out_rows.append({"sample_id": sid, "error": "caption_failed", "A_strict": summarize_call(a_strict)})
            continue
        # Load caption from store
        cap = store.load_call(sid, PATH_A_STRICT, "caption")
        caption = cap["raw_text"]
        c = run_c_text_only(
            store,
            provider,
            item,
            gold,
            caption=caption,
            caption_sha=cap.get("caption_sha") or sha256_text(caption),
            frame_bundle_sha=cap.get("frame_bundle_sha"),
        )
        out_rows.append(
            {
                "sample_id": sid,
                "question_type": item.get("question_type"),
                "A_strict": summarize_call(store.load_call(sid, PATH_A_STRICT, "answer")),
                "C_text_only": summarize_call(c),
                "shared_caption_sha": cap.get("caption_sha"),
                "shared_frame_bundle_sha": cap.get("frame_bundle_sha"),
            }
        )
    return {
        "phase": "diagnose",
        "disagreement_pool": ordered,
        "selected": selected,
        "rows": out_rows,
        "budget_note": "diagnosis calls are outside first-batch 20+20 budget",
    }


def summarize_ab(store: ResultStore, items: dict, golds: dict) -> dict:
    ids = load_frozen_ids()
    per = []
    for sid in ids:
        a = store.load_call(sid, PATH_A_REUSE, "answer")
        b = store.load_call(sid, PATH_B_DIRECT, "answer")
        if not a or not b:
            continue
        per.append(
            {
                "sample_id": sid,
                "question_type": items[sid].get("question_type"),
                "A_answer": a.get("answer"),
                "B_answer": b.get("answer"),
                "A_correct": bool(a.get("correct")),
                "B_correct": bool(b.get("correct")),
                "A_status": a.get("status"),
                "B_status": b.get("status"),
                "A_cny": a.get("estimated_cny") or 0.0,
                "B_cny": b.get("estimated_cny") or 0.0,
                "B_frames": b.get("n_frames"),
                "frame_bundle_sha": b.get("frame_bundle_sha"),
            }
        )
    n = len(per)
    a_corr = sum(1 for r in per if r["A_correct"])
    b_corr = sum(1 for r in per if r["B_correct"])
    both = sum(1 for r in per if r["A_correct"] and r["B_correct"])
    a_only = sum(1 for r in per if r["A_correct"] and not r["B_correct"])
    b_only = sum(1 for r in per if r["B_correct"] and not r["A_correct"])
    neither = sum(1 for r in per if not r["A_correct"] and not r["B_correct"])
    # McNemar exact (binomial) exploratory
    mcnemar = mcnemar_exact(a_only, b_only)
    # Wilson CI
    from math import sqrt

    def wilson(k, n, z=1.96):
        if n == 0:
            return [None, None]
        p = k / n
        den = 1 + z * z / n
        center = (p + z * z / (2 * n)) / den
        half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
        return [max(0.0, center - half), min(1.0, center + half)]

    cost = {
        "A_reuse_cny": sum(r["A_cny"] for r in per),
        "B_direct_cny": sum(r["B_cny"] for r in per),
        "total_cny": sum(r["A_cny"] + r["B_cny"] for r in per),
    }
    by_type = {}
    for r in per:
        t = r["question_type"] or "unknown"
        slot = by_type.setdefault(t, {"n": 0, "A": 0, "B": 0, "A_only": 0, "B_only": 0})
        slot["n"] += 1
        slot["A"] += int(r["A_correct"])
        slot["B"] += int(r["B_correct"])
        slot["A_only"] += int(r["A_correct"] and not r["B_correct"])
        slot["B_only"] += int(r["B_correct"] and not r["A_correct"])
    return {
        "n": n,
        "A_correct": a_corr,
        "B_correct": b_corr,
        "A_accuracy": a_corr / n if n else None,
        "B_accuracy": b_corr / n if n else None,
        "A_wilson95": wilson(a_corr, n),
        "B_wilson95": wilson(b_corr, n),
        "both_correct": both,
        "A_only_correct": a_only,
        "B_only_correct": b_only,
        "both_wrong": neither,
        "mcnemar_exploratory": mcnemar,
        "cost_cny": cost,
        "by_question_type": by_type,
        "per_item": per,
        "caveat": "n=20 exploratory; do not treat small fixes as significant architecture gains",
    }


def mcnemar_exact(n01: int, n10: int) -> dict:
    """Two-sided exact McNemar via binomial under p=0.5."""
    n = n01 + n10
    if n == 0:
        return {"n_discordant": 0, "b_only": n10, "a_only": n01, "p_two_sided": 1.0}
    # P(X<=min or X>=max) for X~Bin(n,0.5)
    from math import comb

    k = min(n01, n10)
    tail = sum(comb(n, i) for i in range(0, k + 1))
    p = min(1.0, 2 * tail / (2 ** n))
    return {"n_discordant": n, "a_only": n01, "b_only": n10, "p_two_sided": p}


def safe_summary(ab: dict, conn: dict | None, diag: dict | None) -> dict:
    """Desensitized stats (no questions, gold, raw text)."""
    return {
        "protocol": PROTOCOL,
        "prompt_version": PROMPT_VERSION,
        "connectivity": {
            "sample_ids": (conn or {}).get("sample_ids"),
            "pass": (conn or {}).get("pass"),
        }
        if conn
        else None,
        "ab": {
            k: ab[k]
            for k in (
                "n",
                "A_correct",
                "B_correct",
                "A_accuracy",
                "B_accuracy",
                "A_wilson95",
                "B_wilson95",
                "both_correct",
                "A_only_correct",
                "B_only_correct",
                "both_wrong",
                "mcnemar_exploratory",
                "cost_cny",
                "by_question_type",
                "caveat",
            )
            if k in ab
        }
        if ab
        else None,
        "ab_per_item_safe": [
            {
                "sample_id": r["sample_id"],
                "question_type": r["question_type"],
                "A_correct": r["A_correct"],
                "B_correct": r["B_correct"],
                "answers_differ": r["A_answer"] != r["B_answer"],
                "B_frames": r["B_frames"],
            }
            for r in (ab or {}).get("per_item", [])
        ],
        "diagnose": {
            "selected": (diag or {}).get("selected"),
            "n_pool": len((diag or {}).get("disagreement_pool") or []),
            "rows_safe": [
                {
                    "sample_id": r["sample_id"],
                    "question_type": r.get("question_type"),
                    "A_strict_correct": (r.get("A_strict") or {}).get("correct"),
                    "C_correct": (r.get("C_text_only") or {}).get("correct"),
                    "A_strict_status": (r.get("A_strict") or {}).get("status"),
                    "C_status": (r.get("C_text_only") or {}).get("status"),
                    "shared_caption_sha": r.get("shared_caption_sha"),
                    "shared_frame_bundle_sha": r.get("shared_frame_bundle_sha"),
                }
                for r in (diag or {}).get("rows") or []
            ],
        }
        if diag
        else None,
    }


def decide_go_stop(ab: dict, diag: dict | None) -> dict:
    """Exploratory decision per updated rules (not paper claims)."""
    a_only = ab["A_only_correct"]
    b_only = ab["B_only_correct"]
    delta = ab["B_correct"] - ab["A_correct"]
    meaningful_diff = abs(delta) >= 3 or (a_only + b_only) >= 3
    complementary = a_only >= 1 and b_only >= 1

    strict_support = False
    if diag and diag.get("rows"):
        # Support if among diag rows, pattern persists vs answerer identity
        # e.g. B_direct correct & A_strict wrong → vision path helps beyond DeepSeek
        for r in diag["rows"]:
            sid = r["sample_id"]
            # find AB row
            pass
        # Compare A_strict vs C on same caption: if they differ, answerer identity matters
        ans_disagree = 0
        for r in diag["rows"]:
            as_ = r.get("A_strict") or {}
            c_ = r.get("C_text_only") or {}
            if as_.get("answer") and c_.get("answer") and as_.get("answer") != c_.get("answer"):
                ans_disagree += 1
            if as_.get("correct") != c_.get("correct"):
                strict_support = True
        if ans_disagree >= 1:
            strict_support = True

    # Also: if B beats A and A_strict still loses to B on same frames → vision retention
    vision_retention = False
    if diag:
        for r in diag["rows"]:
            sid = r["sample_id"]
            # loaded externally in report; here use correctness vs C/A_strict
            if (r.get("A_strict") or {}).get("correct") is False and (r.get("C_text_only") or {}).get("correct") is False:
                # both text paths fail — suggestive if B was correct
                vision_retention = True

    decision = "STOP"
    reasons = []
    if not meaningful_diff:
        decision = "STOP"
        reasons.append("no reliable A/B difference (|Δacc|<3 and discordant<3)")
    elif meaningful_diff and complementary and (strict_support or vision_retention or True):
        # GO needs meaningful diff/complement AND strict support when diag present
        if diag is None:
            decision = "PENDING_DIAG"
            reasons.append("AB shows signal; await diagnosis")
        elif strict_support or complementary:
            # require at least one linked mechanism case from diag
            if strict_support or vision_retention:
                decision = "GO"
                reasons.append("meaningful A/B difference/complement with diagnosis support")
            elif complementary and abs(delta) >= 3:
                decision = "GO"
                reasons.append("strong complement + accuracy gap; diagnosis weak but exploratory GO")
            else:
                decision = "PIVOT"
                reasons.append("difference without clear mechanism link after strict controls")
        else:
            decision = "PIVOT"
            reasons.append("B may dominate without mechanism complementarity")
    elif meaningful_diff and b_only >= 3 and a_only == 0:
        decision = "PIVOT"
        reasons.append("Direct VQA dominates without meaningful complement")
    elif meaningful_diff and not (strict_support or complementary):
        decision = "STOP"
        reasons.append("apparent advantage disappears or lacks mechanism link")

    # Refine with explicit user rules
    if abs(delta) < 2 and (a_only + b_only) < 2:
        decision = "STOP"
        reasons = ["paths essentially indistinguishable"]
    elif b_only >= 4 and a_only == 0 and not complementary:
        decision = "PIVOT"
        reasons = ["Direct VQA broadly better; little mechanism complement — prefer fixed architecture questions"]
    elif (a_only + b_only) >= 3 and complementary and (diag is None or strict_support or vision_retention or abs(delta) >= 2):
        if diag is not None and not strict_support and not vision_retention and abs(delta) < 3:
            decision = "STOP"
            reasons = ["complement weak under strict controls"]
        else:
            decision = "GO" if diag is not None else "PENDING_DIAG"
            reasons = ["meaningful complement/diff worth architectural follow-up"] if diag else ["await diagnosis"]

    return {
        "decision": decision,
        "delta_B_minus_A": delta,
        "A_only": a_only,
        "B_only": b_only,
        "strict_support": strict_support,
        "vision_retention_signal": vision_retention,
        "reasons": reasons,
        "exploratory_only": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, default=PREFLIGHT / "runs" / "infoflow_v1")
    ap.add_argument("--phase", choices=["selftest", "connectivity", "full_ab", "diagnose", "summarize", "all"], default="selftest")
    ap.add_argument("--provider", choices=["mock", "http"], default="mock")
    ap.add_argument("--execute", action="store_true", help="allow paid http calls")
    ap.add_argument("--force", action="store_true", help="redo calls even if ok")
    args = ap.parse_args()

    if args.provider == "http":
        if not args.execute or os.environ.get("ARCH_AB_ALLOW_PAID") != "1":
            print("Refusing http provider without --execute and ARCH_AB_ALLOW_PAID=1", file=sys.stderr)
            return 2

    config = load_services_config()
    store = ResultStore(args.run_dir)
    items = load_train_items()
    cache = cache_by_sample_id()
    golds = load_oracle(TRAIN_ORACLE)
    provider = make_provider(args.provider, config)

    write_json(
        store.meta_path,
        {
            "protocol": PROTOCOL,
            "prompt_version": PROMPT_VERSION,
            "provider": args.provider,
            "models": {
                "deepseek": config["services"]["deepseek"]["request_model"],
                "qwen": config["services"]["qwen"]["request_model"],
                "temperature": config["services"].get("temperature"),
            },
            "frozen_n": len(load_frozen_ids()),
            "budgets": {
                "qwen_direct": BUDGET_QWEN_DIRECT,
                "deepseek_areuse": BUDGET_DEEPSEEK_AREUSE,
                "editor": 0,
                "diag_max_samples": BUDGET_DIAG_MAX_SAMPLES,
            },
        },
    )

    if args.phase == "selftest":
        # Hand off to test module
        from test_ab_infoflow_offline import run_all_tests

        return run_all_tests()

    conn = None
    ab_sum = None
    diag = None

    if args.phase in ("connectivity", "all"):
        conn = phase_connectivity(store, provider, config, items, cache, golds)
        write_json(args.run_dir / "connectivity_result.json", conn)
        print(json.dumps({"connectivity_pass": conn["pass"], "ids": conn["sample_ids"]}, indent=2))
        if not conn["pass"]:
            print("Connectivity FAILED — stop before full_ab", file=sys.stderr)
            return 1

    if args.phase in ("full_ab", "all"):
        if args.phase == "full_ab":
            # still require connectivity artifacts if present
            cpath = args.run_dir / "connectivity_result.json"
            if cpath.is_file():
                conn = load_json(cpath)
                if not conn.get("pass"):
                    print("Prior connectivity failed", file=sys.stderr)
                    return 1
        raw = phase_full_ab(store, provider, config, items, cache, golds)
        # strip heavy raw for intermediate save but keep on disk via store
        ab_sum = summarize_ab(store, items, golds)
        write_json(args.run_dir / "ab_summary.json", ab_sum)
        write_json(PREFLIGHT / "out" / "ab_summary.safe.json", safe_summary(ab_sum, conn, None))
        print(
            json.dumps(
                {
                    "A": ab_sum["A_correct"],
                    "B": ab_sum["B_correct"],
                    "A_only": ab_sum["A_only_correct"],
                    "B_only": ab_sum["B_only_correct"],
                    "cost": ab_sum["cost_cny"],
                },
                indent=2,
            )
        )

    if args.phase in ("diagnose", "all"):
        if ab_sum is None:
            ab_sum = load_json(args.run_dir / "ab_summary.json")
        diag = phase_diagnose(store, provider, config, items, cache, golds, ab_sum)
        write_json(args.run_dir / "diagnose_result.json", diag)

    if args.phase in ("summarize", "all", "diagnose", "full_ab"):
        if ab_sum is None and (args.run_dir / "ab_summary.json").is_file():
            ab_sum = load_json(args.run_dir / "ab_summary.json")
        if diag is None and (args.run_dir / "diagnose_result.json").is_file():
            diag = load_json(args.run_dir / "diagnose_result.json")
        if conn is None and (args.run_dir / "connectivity_result.json").is_file():
            conn = load_json(args.run_dir / "connectivity_result.json")
        if ab_sum:
            decision = decide_go_stop(ab_sum, diag)
            safe = safe_summary(ab_sum, conn, diag)
            safe["go_stop"] = decision
            write_json(PREFLIGHT / "out" / "ab_summary.safe.json", safe)
            write_json(args.run_dir / "go_stop.json", decision)
            print(json.dumps({"go_stop": decision}, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
