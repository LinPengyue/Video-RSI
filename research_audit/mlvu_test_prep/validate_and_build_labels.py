#!/usr/bin/env python3
"""Validate official MLVU-Test MCQ GT and build a local score.py labels JSONL.

Does not call paid APIs. Does not modify harnesses.
Writes answers ONLY to an explicitly local path (gitignored).
Never writes answers into mlvu_test_mc_items.jsonl.

Integer answers: refuses 0-based/1-based ambiguity. Detects base from the
full GT set (presence of 0 vs 6) before mapping any row.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

LETTER = "ABCDEF"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_mc(path: Path) -> dict:
    rows = json.loads(path.read_text())
    by_id = {}
    for row in rows:
        qid = row["question_id"]
        if qid in by_id:
            raise SystemExit(f"duplicate question_id in MC file: {qid}")
        cands = list(row["candidates"])
        if len(cands) != 6:
            raise SystemExit(f"{qid}: expected 6 candidates, got {len(cands)}")
        by_id[qid] = {"candidates": cands, "row": row}
    return by_id


def normalize_gt(raw):
    """Accept list[{question_id, answer, ...}] or dict[question_id -> answer]."""
    out = {}
    meta = {}
    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                raise SystemExit("GT list entries must be objects")
            qid = row.get("question_id") or row.get("id") or row.get("sample_id")
            if qid is None:
                raise SystemExit(f"GT row missing question_id: {row!r}")
            if "answer" in row:
                ans = row["answer"]
            elif "label" in row:
                ans = row["label"]
            elif "gt" in row:
                ans = row["gt"]
            else:
                raise SystemExit(f"GT row missing answer for {qid}")
            out[str(qid)] = ans
            meta[str(qid)] = row
    elif isinstance(raw, dict):
        if all(isinstance(v, (str, int)) for v in raw.values()):
            out = {str(k): v for k, v in raw.items()}
            meta = {}
        elif "data" in raw and isinstance(raw["data"], list):
            return normalize_gt(raw["data"])
        else:
            raise SystemExit("unsupported GT dict schema")
    else:
        raise SystemExit(f"unsupported GT type: {type(raw)}")
    return out, meta


def detect_int_index_base(answers: dict, forced: str | None) -> str:
    """Return '0' or '1'. Refuse ambiguity unless forced."""
    ints = [v for v in answers.values() if isinstance(v, int)]
    if not ints:
        return "none"
    if forced in ("0", "1"):
        return forced
    if forced is not None:
        raise SystemExit(f"invalid --int-index-base {forced!r}; use 0 or 1")

    has0 = any(v == 0 for v in ints)
    has6 = any(v == 6 for v in ints)
    oob = [v for v in ints if v < 0 or v > 6]
    if oob:
        raise SystemExit(f"int answers out of 0..6 range: {oob[:10]}")
    if has0 and has6:
        raise SystemExit(
            "ambiguous int index base: GT contains both 0 and 6; "
            "refuse to guess. Pass --int-index-base 0|1 only with human confirmation."
        )
    if has6 and not has0:
        # 6 is only valid as 1-based option F.
        if any(v < 1 for v in ints):
            raise SystemExit("int answers contain values <1 while also containing 6")
        return "1"
    if has0 and not has6:
        if any(v > 5 for v in ints):
            raise SystemExit("int answers contain values >5 while also containing 0")
        return "0"
    # All ints in 1..5 inclusive — both bases would map into A–F with different letters.
    raise SystemExit(
        "ambiguous int index base: all int answers are in 1..5 with no 0 or 6 to disambiguate. "
        "Refuse to guess. Pass --int-index-base 0|1 only with human confirmation."
    )


def map_answer(qid: str, ans, candidates: list[str], int_base: str) -> str:
    """Map GT to A–F. No guessing on ambiguous ints."""
    if isinstance(ans, bool):
        raise SystemExit(f"{qid}: bool answer unsupported")
    if isinstance(ans, int):
        if int_base == "1":
            if not 1 <= ans <= 6:
                raise SystemExit(f"{qid}: 1-based int out of range: {ans}")
            return LETTER[ans - 1]
        if int_base == "0":
            if not 0 <= ans <= 5:
                raise SystemExit(f"{qid}: 0-based int out of range: {ans}")
            return LETTER[ans]
        raise SystemExit(f"{qid}: int answer but no int_base resolved")
    if not isinstance(ans, str):
        raise SystemExit(f"{qid}: answer type unsupported: {type(ans)}")
    text = ans.strip()
    if len(text) == 1 and text.upper() in LETTER[:6]:
        return text.upper()
    matches = [i for i, c in enumerate(candidates) if c == text]
    if len(matches) == 1:
        return LETTER[matches[0]]
    matches = [i for i, c in enumerate(candidates) if c.casefold() == text.casefold()]
    if len(matches) == 1:
        return LETTER[matches[0]]
    raise SystemExit(f"{qid}: cannot map answer {ans!r} onto candidates {candidates!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--mc",
        default="/home/descfly/lpy/dataset/MLVU_Test/test_multi_choice_tasks.json",
    )
    ap.add_argument(
        "--gt",
        default="/home/descfly/lpy/dataset/MLVU_Test/test-ground-truth/test_mcq_gt.json",
        help="official GT JSON (local path; not committed)",
    )
    ap.add_argument(
        "--labels-out",
        default="research_audit/mlvu_test_prep/labels.local.jsonl",
        help="gitignored score.py labels JSONL",
    )
    ap.add_argument(
        "--report-out",
        default="research_audit/mlvu_test_prep/gt_match_report.safe.json",
        help="safe summary without answers",
    )
    ap.add_argument(
        "--int-index-base",
        default=None,
        choices=["0", "1"],
        help="force int answer index base; default auto-detect or refuse if ambiguous",
    )
    args = ap.parse_args()

    mc_path = Path(args.mc)
    gt_path = Path(args.gt)
    if not gt_path.is_file():
        print(f"GT missing: {gt_path}", file=sys.stderr)
        print(
            "Place the official test_mcq_gt.json after authorized HF download.",
            file=sys.stderr,
        )
        return 2

    by_id = load_mc(mc_path)
    raw = json.loads(gt_path.read_text(encoding="utf-8"))
    gt, gt_meta = normalize_gt(raw)

    mc_ids = set(by_id)
    gt_ids = set(gt)
    missing = sorted(mc_ids - gt_ids)
    extra = sorted(gt_ids - mc_ids)
    if missing or extra:
        print(
            f"ID mismatch: missing_in_gt={len(missing)} extra_in_gt={len(extra)}",
            file=sys.stderr,
        )
        if missing[:10]:
            print("missing sample", missing[:10], file=sys.stderr)
        if extra[:10]:
            print("extra sample", extra[:10], file=sys.stderr)
        return 3

    # Candidate consistency when GT embeds candidates
    cand_mismatch = []
    for qid, meta in gt_meta.items():
        if isinstance(meta, dict) and "candidates" in meta:
            if list(meta["candidates"]) != by_id[qid]["candidates"]:
                cand_mismatch.append(qid)
    if cand_mismatch:
        print(f"candidates mismatch vs MC annotation: {len(cand_mismatch)}", file=sys.stderr)
        print(cand_mismatch[:10], file=sys.stderr)
        return 4

    n_str = sum(1 for v in gt.values() if isinstance(v, str))
    n_int = sum(1 for v in gt.values() if isinstance(v, int))
    int_base = detect_int_index_base(gt, args.int_index_base)

    labels = []
    for qid in sorted(mc_ids):
        letter = map_answer(qid, gt[qid], by_id[qid]["candidates"], int_base)
        labels.append({"sample_id": qid, "answer": letter})

    out = Path(args.labels_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in labels:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    report = {
        "mc_path": str(mc_path),
        "mc_sha256": sha256(mc_path),
        "gt_path": str(gt_path),
        "gt_sha256": sha256(gt_path),
        "gt_schema": "list[object]" if isinstance(raw, list) else type(raw).__name__,
        "n_mc": len(mc_ids),
        "n_gt": len(gt_ids),
        "matched": len(labels),
        "match_rate": 1.0,
        "missing_in_gt": 0,
        "extra_in_gt": 0,
        "candidates_mismatch": 0,
        "answer_value_types": {"str": n_str, "int": n_int},
        "int_index_base": int_base,
        "int_index_base_forced": args.int_index_base is not None,
        "all_answers_in_A_to_F": all(r["answer"] in set(LETTER[:6]) for r in labels),
        "labels_out": str(out),
        "labels_sha256": sha256(out),
        "answers_omitted_from_this_report": True,
    }
    report_path = Path(args.report_out)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Wrote local labels (gitignored):", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
