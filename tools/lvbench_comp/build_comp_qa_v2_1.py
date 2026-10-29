#!/usr/bin/env python3
"""Strict Novel Composition Pilot over the fixed v2 candidate set.

Does not create new questions. Fixes the v2 leave-out bug: the unseen schema
is excluded entirely from training.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


TARGET_SCHEMA = "identify_person + query_action"
ALT_SCHEMA = "identify_event_result + query_action"
PRIMARY_TEST_IDS = [
    "LVCOMP-V2-002",
    "LVCOMP-V2-003",
    "LVCOMP-V2-015",
    "LVCOMP-V2-024",
    "LVCOMP-V2-025",
    "LVCOMP-V2-031",
    "LVCOMP-V2-106",
    "LVCOMP-V2-113",
    "LVCOMP-V2-114",
]

# Manual schema audit for the primary leave-out target.
# identify_person does not automatically include animals.
SCHEMA_AUDIT: dict[str, dict[str, str]] = {
    "LVCOMP-V2-002": {
        "audited_schema": TARGET_SCHEMA,
        "verdict": "SCHEMA_VALID",
        "entity_kind": "person",
        "rationale": "Bridge is the first interviewee (Sierra). Query asks what she does after a roommate appears.",
    },
    "LVCOMP-V2-003": {
        "audited_schema": TARGET_SCHEMA,
        "verdict": "SCHEMA_VALID",
        "entity_kind": "person",
        "rationale": "Bridge is the first interviewee (Sierra). Query asks what she does after the first male guest appears.",
    },
    "LVCOMP-V2-015": {
        "audited_schema": TARGET_SCHEMA,
        "verdict": "SCHEMA_VALID",
        "entity_kind": "person",
        "rationale": "Bridge is the on-screen person identified as Old Bruce Lee. Query asks how that person strikes.",
    },
    "LVCOMP-V2-024": {
        "audited_schema": TARGET_SCHEMA,
        "verdict": "SCHEMA_VALID",
        "entity_kind": "person",
        "rationale": "Bridge is the first interviewee (Sierra). Query asks what she does after Kindall appears.",
    },
    "LVCOMP-V2-025": {
        "audited_schema": TARGET_SCHEMA,
        "verdict": "SCHEMA_VALID",
        "entity_kind": "person",
        "rationale": "Bridge is the last person in the second interview (Alexis). Query asks what that person claims.",
    },
    "LVCOMP-V2-031": {
        "audited_schema": TARGET_SCHEMA,
        "verdict": "SCHEMA_VALID",
        "entity_kind": "anthropomorphic_character",
        "rationale": "Bridge is the blue calabash boy, an anthropomorphic character treated as a person-like agent, not a generic object.",
    },
    "LVCOMP-V2-106": {
        "audited_schema": "identify_animal + query_action",
        "verdict": "SCHEMA_MISMATCH",
        "entity_kind": "animal",
        "rationale": "Official bridge answer is the pangolin. identify_person must not absorb animals.",
    },
    "LVCOMP-V2-113": {
        "audited_schema": "identify_animal + query_action",
        "verdict": "SCHEMA_MISMATCH",
        "entity_kind": "animal",
        "rationale": "The bound entity is the dog the boy and cat meet, not a person.",
    },
    "LVCOMP-V2-114": {
        "audited_schema": "identify_animal + query_action",
        "verdict": "SCHEMA_MISMATCH",
        "entity_kind": "animal",
        "rationale": "Same dog bridge as V2-113. The chase event still binds an animal, not a person.",
    },
}

# Train-side primitive evidence: only count items whose wording clearly matches the operation.
# Coarse schema strings alone are not enough.
PERSON_ID_OK = {
    # person referring expression is the bridge or the asked identity
    "LVCOMP-V2-004",  # who cheats on first interviewee
    "LVCOMP-V2-008",  # second person to speak → brand
    "LVCOMP-V2-010",  # winner → bib
    "LVCOMP-V2-011",  # elder who joins → dessert count
    "LVCOMP-V2-012",  # elder who joins → hotel
    "LVCOMP-V2-013",  # elder who joins → clothes color
    "LVCOMP-V2-040",  # person who serves first → result
    "LVCOMP-V2-041",  # person who gets first point → result
    "LVCOMP-V2-042",  # whose coach / final winner
    "LVCOMP-V2-043",  # person Austin chooses → role
    "LVCOMP-V2-045",  # Brittany relationship to person at 00:02
    "LVCOMP-V2-107",  # quarrel person → desserts
    "LVCOMP-V2-201",  # quarrel person → clothes color
}
ACTION_QUERY_OK = {
    # Clear action / post-event queries. Object/animal "what happens" items are NOT treated as
    # equivalent evidence for person-action queries.
    "LVCOMP-V2-100",  # what did the man do after...
    "LVCOMP-V2-112",  # who does Kroos substitute
    "LVCOMP-V2-115",  # how leave platform after first transport
    "LVCOMP-V2-116",  # what transport after getting off first transport
}


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_review(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_v1 = {row["id"]: row for row in rows}
    return by_v1


def attach_evidence(candidates: list[dict], review_by_v1: dict[str, dict]) -> dict[str, dict]:
    evidence = {}
    for row in candidates:
        v1 = row.get("source_v1_id")
        if v1 and v1 in review_by_v1:
            verdict = review_by_v1[v1]["verdict"]
            notes = review_by_v1[v1].get("notes", "")
            source = "sample_review"
        else:
            verdict = "UNREVIEWED"
            notes = "No sample-review contact-sheet pass for this item."
            source = "none"
        if row.get("review_status") == "NEEDS_VERIFICATION":
            evidence_status = "NEEDS_VERIFICATION"
        elif verdict == "CONTRADICTED":
            evidence_status = "CONTRADICTED"
        elif verdict == "SUPPORTED":
            evidence_status = "SUPPORTED"
        elif verdict == "UNCERTAIN":
            evidence_status = "UNCERTAIN"
        else:
            evidence_status = "PENDING_VIDEO_REVIEW"
        evidence[row["id"]] = {
            "sample_verdict": verdict,
            "evidence_status": evidence_status,
            "notes": notes,
            "source": source,
        }
    return evidence


def build_schema_audit_rows(candidates: list[dict], evidence: dict[str, dict]) -> list[dict]:
    by_id = {row["id"]: row for row in candidates}
    rows = []
    for cid in PRIMARY_TEST_IDS:
        item = by_id[cid]
        audit = SCHEMA_AUDIT[cid]
        rows.append(
            {
                "id": cid,
                "video_id": item["video_id"],
                "original_schema": item["composition_schema"],
                "audited_schema": audit["audited_schema"],
                "schema_verdict": audit["verdict"],
                "entity_kind": audit["entity_kind"],
                "evidence_status": evidence[cid]["evidence_status"],
                "rationale": audit["rationale"],
                "question": item["new_question"],
                "answer": item["new_answer"],
            }
        )
    return rows


def primitives(schema: str) -> tuple[str, str]:
    left, right = [part.strip() for part in schema.split("+", 1)]
    return left, right


def strict_split(
    candidates: list[dict],
    evidence: dict[str, dict],
    schema_audit: list[dict],
    unseen_schema: str,
) -> dict:
    by_id = {row["id"]: row for row in candidates}
    audit_by_id = {row["id"]: row for row in schema_audit}

    excluded = []
    test_ids = []
    for row in schema_audit:
        cid = row["id"]
        if row["schema_verdict"] != "SCHEMA_VALID":
            excluded.append({"id": cid, "reason": f"schema_audit={row['schema_verdict']}: {row['rationale']}"})
            continue
        if evidence[cid]["evidence_status"] == "CONTRADICTED":
            excluded.append({"id": cid, "reason": "known contradicted by sample video review"})
            continue
        test_ids.append(cid)

    test_videos = {by_id[cid]["video_id"] for cid in test_ids}
    test_uids = {(by_id[cid]["video_id"], uid) for cid in test_ids for uid in by_id[cid]["source_uids"]}

    train_ids = []
    for row in candidates:
        cid = row["id"]
        reasons = []
        if row["composition_schema"] == unseen_schema:
            reasons.append(f"belongs to unseen schema {unseen_schema}")
        if evidence[cid]["evidence_status"] == "CONTRADICTED":
            reasons.append("known contradicted by sample video review")
        if row["video_id"] in test_videos:
            reasons.append(f"shares test video {row['video_id']}")
        uid_hits = [(row["video_id"], uid) for uid in row["source_uids"] if (row["video_id"], uid) in test_uids]
        if uid_hits:
            reasons.append(f"shares source UID(s) {uid_hits}")
        # labeled with unseen schema but audited mismatch: still excluded above via schema membership
        if cid in audit_by_id and audit_by_id[cid]["schema_verdict"] != "SCHEMA_VALID" and cid not in test_ids:
            # already captured if schema == unseen; ensure exclusion reason recorded once
            pass
        if reasons:
            if cid not in test_ids and not any(e["id"] == cid for e in excluded):
                excluded.append({"id": cid, "reason": "; ".join(reasons)})
            continue
        train_ids.append(cid)

    # Structural train/test: no CONTRADICTED, schema-valid test, no leaks.
    structural_train = [cid for cid in train_ids if evidence[cid]["evidence_status"] != "CONTRADICTED"]
    structural_test = list(test_ids)
    # Verified: only SUPPORTED evidence.
    verified_train = [cid for cid in structural_train if evidence[cid]["evidence_status"] == "SUPPORTED"]
    verified_test = [cid for cid in structural_test if evidence[cid]["evidence_status"] == "SUPPORTED"]

    return {
        "unseen_schema": unseen_schema,
        "test_ids": structural_test,
        "train_ids": structural_train,
        "test_videos": sorted(test_videos),
        "excluded": excluded,
        "structural": {
            "train_n": len(structural_train),
            "test_n": len(structural_test),
            "train_videos": len({by_id[cid]["video_id"] for cid in structural_train}),
            "test_videos": len(test_videos),
        },
        "verified": {
            "train_n": len(verified_train),
            "test_n": len(verified_test),
            "train_ids": verified_train,
            "test_ids": verified_test,
        },
    }


def primitive_coverage(candidates: list[dict], train_ids: list[str], unseen_schema: str) -> tuple[list[dict], str]:
    by_id = {row["id"]: row for row in candidates}
    train = [by_id[cid] for cid in train_ids]
    left, right = primitives(unseen_schema)

    def collect(op: str, allow_ids: set[str]) -> dict:
        matched = [row for row in train if row["id"] in allow_ids]
        schemas = sorted({row["composition_schema"] for row in matched})
        # Also list coarse string hits for transparency, but do not treat them as proof.
        coarse = [
            row
            for row in train
            if op in {primitives(row["composition_schema"])[0], primitives(row["composition_schema"])[1]}
        ]
        return {
            "primitive": op,
            "strict_n": len(matched),
            "strict_videos": len({row["video_id"] for row in matched}),
            "strict_schemas": " | ".join(schemas) if schemas else "",
            "strict_ids": " ".join(row["id"] for row in matched),
            "coarse_string_n": len(coarse),
            "coarse_string_schemas": " | ".join(sorted({row["composition_schema"] for row in coarse})),
        }

    # For identify_person, only PERSON_ID_OK items that remain in train.
    person_rows = collect("identify_person", PERSON_ID_OK)
    # Only count action queries that are already allow-listed as person/event actions.
    # Coarse schema string hits remain visible for comparison but do not prove equivalence.
    action_allow = set(ACTION_QUERY_OK)
    action_rows = collect("query_action", action_allow)

    status = "OK"
    if person_rows["strict_n"] == 0 or action_rows["strict_n"] == 0:
        status = "PRIMITIVE_COVERAGE_MISSING"
    elif person_rows["strict_videos"] < 2 or action_rows["strict_videos"] < 2:
        status = "PRIMITIVE_COVERAGE_UNCERTAIN"
    # If coarse counts are much larger than strict, note uncertainty about label equivalence.
    if person_rows["coarse_string_n"] > person_rows["strict_n"] or action_rows["coarse_string_n"] > action_rows["strict_n"]:
        if status == "OK":
            status = "PRIMITIVE_COVERAGE_UNCERTAIN"

    rows = [
        {**person_rows, "required_for": unseen_schema, "coverage_status": status},
        {**action_rows, "required_for": unseen_schema, "coverage_status": status},
    ]
    return rows, status


def validate_split(candidates: list[dict], split: dict, evidence: dict[str, dict], unseen_schema: str) -> dict:
    by_id = {row["id"]: row for row in candidates}
    train = [by_id[cid] for cid in split["train_ids"]]
    test = [by_id[cid] for cid in split["test_ids"]]
    train_schemas = Counter(row["composition_schema"] for row in train)
    checks = {
        "unseen_schema_in_train_count": train_schemas.get(unseen_schema, 0),
        "train_test_video_overlap": sorted(
            {row["video_id"] for row in train} & {row["video_id"] for row in test}
        ),
        "train_test_uid_overlap": sorted(
            {
                f"{video}:{uid}"
                for row in train
                for video, uid in [(row["video_id"], u) for u in row["source_uids"]]
            }
            & {
                f"{video}:{uid}"
                for row in test
                for video, uid in [(row["video_id"], u) for u in row["source_uids"]]
            }
        ),
        "contradicted_in_train": [
            cid for cid in split["train_ids"] if evidence[cid]["evidence_status"] == "CONTRADICTED"
        ],
        "contradicted_in_test": [
            cid for cid in split["test_ids"] if evidence[cid]["evidence_status"] == "CONTRADICTED"
        ],
        "v2_038_excluded": "LVCOMP-V2-038" not in set(split["train_ids"]) | set(split["test_ids"]),
    }
    checks["ok"] = (
        checks["unseen_schema_in_train_count"] == 0
        and not checks["train_test_video_overlap"]
        and not checks["train_test_uid_overlap"]
        and not checks["contradicted_in_train"]
        and not checks["contradicted_in_test"]
        and checks["v2_038_excluded"]
    )
    return checks


def analyze_alt_schema(candidates: list[dict], evidence: dict[str, dict]) -> dict:
    """Strict leave-out for identify_event_result + query_action without claiming formal validity of each item."""
    items = [row for row in candidates if row["composition_schema"] == ALT_SCHEMA]
    # Conservative validity: drop NEEDS_VERIFICATION and obvious attribute/result mismatches by wording.
    valid = []
    mismatched = []
    for row in items:
        q = row["new_question"].lower()
        if evidence[row["id"]]["evidence_status"] in {"CONTRADICTED", "NEEDS_VERIFICATION"}:
            mismatched.append({"id": row["id"], "reason": evidence[row["id"]]["evidence_status"]})
            continue
        if re.search(r"\b(skill|company|player scored|feeling)\b", q):
            mismatched.append({"id": row["id"], "reason": "likely not query_action / event_result composition"})
            continue
        valid.append(row)
    if not valid:
        return {
            "schema": ALT_SCHEMA,
            "raw_n": len(items),
            "valid_test_n": 0,
            "note": "No conservatively valid test items remain.",
        }
    test_videos = {row["video_id"] for row in valid}
    train = []
    for row in candidates:
        if row["composition_schema"] == ALT_SCHEMA:
            continue
        if evidence[row["id"]]["evidence_status"] == "CONTRADICTED":
            continue
        if row["video_id"] in test_videos:
            continue
        train.append(row)
    # Primitive coverage under coarse+strict caution
    event_prim = [
        row
        for row in train
        if primitives(row["composition_schema"])[0] == "identify_event_result"
        or "after" in row["new_question"].lower()
    ]
    action_prim = [row for row in train if row["id"] in ACTION_QUERY_OK or re.search(r"(?i)^what (did|does|happens)|^how (do|does)|^who does", row["new_question"])]
    return {
        "schema": ALT_SCHEMA,
        "raw_n": len(items),
        "raw_videos": len({row["video_id"] for row in items}),
        "valid_test_n": len(valid),
        "valid_test_videos": len(test_videos),
        "valid_test_ids": [row["id"] for row in valid],
        "train_n_after_leaveout": len(train),
        "identify_event_result_train_n_coarse": len(
            [row for row in train if "identify_event_result" in row["composition_schema"]]
        ),
        "query_action_train_n_coarse": len(action_prim),
        "note": (
            "After excluding the whole schema and isolating its videos, "
            "identify_event_result support in train is sparse under coarse labels; "
            "this candidate is not preferred over identify_person + query_action."
        ),
    }


def verdict_label(split: dict, prim_status: str, validation: dict) -> str:
    if not validation["ok"] or split["structural"]["test_n"] == 0 or split["structural"]["train_n"] == 0:
        return "INSUFFICIENT_COMPOSITION_COVERAGE"
    if prim_status == "PRIMITIVE_COVERAGE_MISSING":
        return "INSUFFICIENT_COMPOSITION_COVERAGE"
    if split["verified"]["test_n"] >= 1 and split["verified"]["train_n"] >= 5 and prim_status == "OK":
        return "STRUCTURAL_PILOT_FEASIBLE"
    # Structural possible but video evidence thin / primitives only uncertain
    return "STRUCTURAL_PILOT_FEASIBLE_BUT_UNVERIFIED"


def write_outputs(
    out_dir: Path,
    schema_audit: list[dict],
    split: dict,
    prim_rows: list[dict],
    prim_status: str,
    validation: dict,
    alt: dict,
    final_verdict: str,
    evidence: dict[str, dict],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _csv(out_dir / "schema_audit.csv", schema_audit)
    _csv(out_dir / "primitive_coverage.csv", prim_rows)
    (out_dir / "split_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    pilot = None
    if final_verdict != "INSUFFICIENT_COMPOSITION_COVERAGE":
        pilot = {
            "status": "PILOT_ONLY_NOT_VIDEO_CERTIFIED",
            "final_verdict": final_verdict,
            "unseen_schema": split["unseen_schema"],
            "train_ids": split["train_ids"],
            "test_ids": split["test_ids"],
            "test_videos": split["test_videos"],
            "excluded": split["excluded"],
            "structural_counts": split["structural"],
            "verified_counts": {
                "train_n": split["verified"]["train_n"],
                "test_n": split["verified"]["test_n"],
                "train_ids": split["verified"]["train_ids"],
                "test_ids": split["verified"]["test_ids"],
            },
            "primitive_coverage_status": prim_status,
            "note": (
                "Experimental structural pilot only. Most items remain PENDING_VIDEO_REVIEW. "
                "This is not a formal Compositional Generalization Benchmark."
            ),
        }
        (out_dir / "pilot_split.json").write_text(
            json.dumps(pilot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    else:
        path = out_dir / "pilot_split.json"
        if path.exists():
            path.unlink()

    valid_n = sum(1 for row in schema_audit if row["schema_verdict"] == "SCHEMA_VALID")
    mismatch_n = sum(1 for row in schema_audit if row["schema_verdict"] == "SCHEMA_MISMATCH")
    report = "\n".join(
        [
            "# LVBench Compositional Generalization v2.1 — Strict Novel Composition Pilot",
            "",
            "本轮不新增题目，只在现有 56 道 v2 候选上做严格 schema 留出。",
            "",
            "## 修复点",
            "",
            "v2 允许同结构不同视频进入训练集。v2.1 要求：`unseen_schema` 的全部题目不得进入训练。",
            "",
            "## 目标结构审计：`identify_person + query_action`",
            "",
            f"- 原始标注 9 道 / 4 视频。",
            f"- SCHEMA_VALID：{valid_n}",
            f"- SCHEMA_MISMATCH：{mismatch_n}（穿山甲、狗等动物桥不能算 identify_person）",
            f"- 严格测试集：{split['structural']['test_n']} 道 / {split['structural']['test_videos']} 视频",
            f"- 测试视频：{', '.join(split['test_videos'])}",
            "",
            "## 训练规模",
            "",
            f"- Structural Pilot 训练题：{split['structural']['train_n']}（视频 {split['structural']['train_videos']}）",
            f"- Verified Pilot 训练题：{split['verified']['train_n']}；测试题：{split['verified']['test_n']}",
            f"- 已排除 V2-038（CONTRADICTED）及其他泄漏 / schema 不匹配项，见 `pilot_split.json` 的 excluded。",
            "",
            "## 基本能力",
            "",
            f"- 覆盖状态：`{prim_status}`",
            *[
                f"- `{row['primitive']}`：严格 {row['strict_n']} 道 / {row['strict_videos']} 视频；来源 schema：{row['strict_schemas'] or '(none)'}"
                for row in prim_rows
            ],
            "",
            "粗粒度 schema 字符串命中数高于严格集合时，不能直接认定操作等价。",
            "",
            "## 备选结构 `identify_event_result + query_action`",
            "",
            f"- 原始 {alt['raw_n']} 道 / {alt.get('raw_videos', '?')} 视频。",
            f"- 保守有效测试题 {alt['valid_test_n']} / 视频 {alt.get('valid_test_videos', 0)}。",
            f"- 留出后训练题 {alt.get('train_n_after_leaveout', 0)}；训练中 coarse `identify_event_result`={alt.get('identify_event_result_train_n_coarse', 0)}。",
            f"- {alt.get('note', '')}",
            "",
            "## 验证",
            "",
            f"- split_validation.ok = {validation['ok']}",
            "",
            "## 结论",
            "",
            f"`{final_verdict}`",
            "",
            "这不是正式 Compositional Generalization Benchmark，也未运行 RSI。",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")
    (out_dir / "README.md").write_text(
        """# LVBench Compositional Generalization v2.1

严格 Novel Composition Pilot。不新增候选，不重抽视频。

```bash
python3 tools/lvbench_comp/build_comp_qa_v2_1.py \\
  --candidates research_audit/lvbench_compositional/v2/candidates.jsonl \\
  --sample-review research_audit/lvbench_compositional/v2/sample_review.csv \\
  --output-dir research_audit/lvbench_compositional/v2_1
```

测试：

```bash
python3 tools/lvbench_comp/test_build_comp_qa_v2_1.py
```
""",
        encoding="utf-8",
    )


def _csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0].keys()) if rows else ["id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build(candidates_path: Path, review_path: Path) -> dict:
    candidates = _load_jsonl(candidates_path)
    review = _load_review(review_path)
    evidence = attach_evidence(candidates, review)
    schema_audit = build_schema_audit_rows(candidates, evidence)
    split = strict_split(candidates, evidence, schema_audit, TARGET_SCHEMA)
    prim_rows, prim_status = primitive_coverage(candidates, split["train_ids"], TARGET_SCHEMA)
    validation = validate_split(candidates, split, evidence, TARGET_SCHEMA)
    alt = analyze_alt_schema(candidates, evidence)
    final_verdict = verdict_label(split, prim_status, validation)
    return {
        "candidates": candidates,
        "evidence": evidence,
        "schema_audit": schema_audit,
        "split": split,
        "prim_rows": prim_rows,
        "prim_status": prim_status,
        "validation": validation,
        "alt": alt,
        "final_verdict": final_verdict,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Strict Novel Composition Pilot over v2 candidates.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--sample-review", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build(args.candidates, args.sample_review)
    write_outputs(
        args.output_dir,
        result["schema_audit"],
        result["split"],
        result["prim_rows"],
        result["prim_status"],
        result["validation"],
        result["alt"],
        result["final_verdict"],
        result["evidence"],
    )
    print(
        json.dumps(
            {
                "final_verdict": result["final_verdict"],
                "test_n": result["split"]["structural"]["test_n"],
                "test_videos": result["split"]["structural"]["test_videos"],
                "train_n": result["split"]["structural"]["train_n"],
                "verified_test_n": result["split"]["verified"]["test_n"],
                "verified_train_n": result["split"]["verified"]["train_n"],
                "primitive_status": result["prim_status"],
                "validation_ok": result["validation"]["ok"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
