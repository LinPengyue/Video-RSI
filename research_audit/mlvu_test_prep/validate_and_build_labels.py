#!/usr/bin/env python3
"""Validate official MLVU-Test MCQ GT and build a local score.py labels JSONL.

Does not call paid APIs. Does not modify harnesses.
Writes answers ONLY to an explicitly local path (gitignored).
Never writes answers into mlvu_test_mc_items.jsonl.
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
        by_id[qid] = cands
    return by_id


def normalize_gt(raw):
    """Accept list[{question_id, answer}] or dict[question_id -> answer/text]."""
    out = {}
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
    elif isinstance(raw, dict):
        # either {question_id: answer} or {data: [...]} 
        if all(isinstance(v, (str, int)) for v in raw.values()):
            out = {str(k): v for k, v in raw.items()}
        elif "data" in raw and isinstance(raw["data"], list):
            return normalize_gt(raw["data"])
        else:
            raise SystemExit("unsupported GT dict schema")
    else:
        raise SystemExit(f"unsupported GT type: {type(raw)}")
    return out


def map_answer(qid: str, ans, candidates: list[str]) -> str:
    """Map GT to A-F. No guessing."""
    if isinstance(ans, int):
        if 0 <= ans < 6:
            return LETTER[ans]
        if 1 <= ans <= 6:
            return LETTER[ans - 1]
        raise SystemExit(f"{qid}: int answer out of range: {ans}")
    if not isinstance(ans, str):
        raise SystemExit(f"{qid}: answer type unsupported: {type(ans)}")
    text = ans.strip()
    if len(text) == 1 and text.upper() in LETTER[:6]:
        return text.upper()
    # exact candidate text match
    matches = [i for i, c in enumerate(candidates) if c == text]
    if len(matches) == 1:
        return LETTER[matches[0]]
    # casefold unique match
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
    raw = json.loads(gt_path.read_text())
    gt = normalize_gt(raw)

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

    labels = []
    for qid in sorted(mc_ids):
        letter = map_answer(qid, gt[qid], by_id[qid])
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
        "n_mc": len(mc_ids),
        "n_gt": len(gt_ids),
        "matched": len(labels),
        "match_rate": 1.0,
        "missing_in_gt": 0,
        "extra_in_gt": 0,
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
