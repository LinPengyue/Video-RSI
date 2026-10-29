#!/usr/bin/env python3
"""Pilot v2.2: evidence packaging, primitive audit, and readiness gate.

Does not invent video judgments. Items stay PENDING_HUMAN_REVIEW unless an
explicit human/contact-sheet judgment is supplied.
"""

from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path


TEST_IDS = [
    "LVCOMP-V2-002",
    "LVCOMP-V2-003",
    "LVCOMP-V2-015",
    "LVCOMP-V2-024",
    "LVCOMP-V2-025",
    "LVCOMP-V2-031",
]
ACTION_TRAIN_IDS = [
    "LVCOMP-V2-100",
    "LVCOMP-V2-112",
    "LVCOMP-V2-115",
    "LVCOMP-V2-116",
]
UNSEEN = "identify_person + query_action"


def _load_jsonl(path: Path) -> dict[str, dict]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["id"]] = row
    return rows


def default_train_audit(rows: dict[str, dict]) -> list[dict]:
    specs = {
        "LVCOMP-V2-100": (
            "ACTION_PRIMITIVE_VALID",
            "Asks what the man did after an event. This matches the test-side what-does-X-do action query.",
        ),
        "LVCOMP-V2-112": (
            "ACTION_PRIMITIVE_WEAK",
            "Asks who Kroos substitutes: the patient/object of a substitution, not the action itself.",
        ),
        "LVCOMP-V2-115": (
            "ACTION_PRIMITIVE_WEAK",
            "Asks how the vloggers leave/go upstairs: a manner/process query, only partly aligned with agent action queries.",
        ),
        "LVCOMP-V2-116": (
            "ACTION_PRIMITIVE_MISMATCH",
            "Asks which transportation mode is taken next. That is a means/attribute query, not query_action.",
        ),
    }
    out = []
    for cid, (status, reason) in specs.items():
        row = rows[cid]
        out.append(
            {
                "id": cid,
                "video_id": row["video_id"],
                "question": row["new_question"],
                "answer": row["new_answer"],
                "v21_role": "query_action_strict_evidence",
                "action_primitive_status": status,
                "reason": reason,
            }
        )
    return out


def default_test_reviews(rows: dict[str, dict], judgments: dict[str, dict] | None = None) -> list[dict]:
    judgments = judgments or {}
    out = []
    for cid in TEST_IDS:
        row = rows[cid]
        j = judgments.get(cid, {})
        out.append(
            {
                "id": cid,
                "video_id": row["video_id"],
                "source_uids": " ".join(row["source_uids"]),
                "time_references": " | ".join(row["time_references"]),
                "question": row["new_question"],
                "answer": row["new_answer"],
                "source_fact_status": j.get("source_fact_status", "PENDING_HUMAN_REVIEW"),
                "composition_status": j.get("composition_status", "PENDING_HUMAN_REVIEW"),
                "answer_status": j.get("answer_status", "PENDING_HUMAN_REVIEW"),
                "review_status": j.get("review_status", "PENDING_HUMAN_REVIEW"),
                "evidence_timestamp": j.get("evidence_timestamp", ""),
                "notes": j.get(
                    "notes",
                    "Contact sheets/clips extracted for human review. No independent video judgment was asserted automatically from official answers.",
                ),
            }
        )
    return out


def default_revisions(rows: dict[str, dict]) -> list[dict]:
    """Grammar/reference fixes that do not change facts or leak bridge names."""
    revisions = {
        "LVCOMP-V2-025": {
            "revised_question": "What does the last person to appear during the second interview claim?",
            "revised_answer": "She says she's Brian's first love",
            "change": "answer_spelling_from_onscreen_graphic",
            "reason": "uid_5145 lower-third spells Brian. Official option Brain is retained in source_answers; revised_answer follows the observed graphic. Last-appear identity remains UNCERTAIN.",
        },
        "LVCOMP-V2-031": {
            "revised_question": "What does the person who steals the S-shaped jade use to scratch the scorpion's nose, causing the scorpion to sneeze?",
            "revised_answer": "The leave on his head",
            "change": "none",
            "reason": "Official option spelling leave is retained; do not invent leaf or a new action.",
        },
        "LVCOMP-V2-015": {
            "revised_question": "At 11:14 in the video, how does the person who is on the right side of the screen after the ground move in the third round strike the opponent's head?",
            "revised_answer": "An uppercut punch",
            "change": "question_grammar",
            "reason": "Insert who is for grammar. The ground-move referring phrase is unchanged and may still be ambiguous pending video review.",
        },
    }
    out = []
    for cid in TEST_IDS:
        row = rows[cid]
        spec = revisions.get(
            cid,
            {
                "revised_question": row["new_question"],
                "revised_answer": row["new_answer"],
                "change": "none",
                "reason": "No text change required for pilot packaging.",
            },
        )
        out.append(
            {
                "id": cid,
                "video_id": row["video_id"],
                "source_uids": row["source_uids"],
                "source_questions": row["source_questions"],
                "source_answers": row["source_answers"],
                "time_references": row["time_references"],
                "original_question": row["new_question"],
                "original_answer": row["new_answer"],
                "revised_question": spec["revised_question"],
                "revised_answer": spec["revised_answer"],
                "change": spec["change"],
                "reason": spec["reason"],
                "composition_schema": row["composition_schema"],
                "review_status": "PENDING_HUMAN_REVIEW",
                "video_verified": False,
            }
        )
    return out


def readiness(
    pilot_split: dict,
    test_reviews: list[dict],
    train_audit: list[dict],
    candidates: dict[str, dict],
) -> dict:
    supported_test = [r for r in test_reviews if r["review_status"] == "SUPPORTED"]
    supported_videos = sorted({r["video_id"] for r in supported_test})
    valid_action = [r for r in train_audit if r["action_primitive_status"] == "ACTION_PRIMITIVE_VALID"]
    valid_action_videos = sorted({r["video_id"] for r in valid_action})

    train_ids = set(pilot_split["train_ids"])
    test_ids = set(pilot_split["test_ids"])
    # isolation re-check
    train_rows = [candidates[i] for i in train_ids]
    test_rows = [candidates[i] for i in test_ids]
    schema_leak = sum(1 for row in train_rows if row["composition_schema"] == UNSEEN)
    video_overlap = sorted({r["video_id"] for r in train_rows} & {r["video_id"] for r in test_rows})
    uid_overlap = sorted(
        {
            f"{r['video_id']}:{u}"
            for r in train_rows
            for u in r["source_uids"]
        }
        & {
            f"{r['video_id']}:{u}"
            for r in test_rows
            for u in r["source_uids"]
        }
    )
    contradicted_in_pilot = [
        cid
        for cid in train_ids | test_ids
        if cid == "LVCOMP-V2-038"
    ]

    gates = {
        "supported_test_n": len(supported_test),
        "supported_test_videos": len(supported_videos),
        "valid_query_action_n": len(valid_action),
        "valid_query_action_videos": len(valid_action_videos),
        "schema_leak": schema_leak,
        "video_overlap": video_overlap,
        "uid_overlap": uid_overlap,
        "contradicted_in_pilot": contradicted_in_pilot,
    }
    missing = []
    if len(supported_test) < 3:
        missing.append(f"need >=3 SUPPORTED test items, have {len(supported_test)}")
    if len(supported_videos) < 2:
        missing.append(f"need >=2 SUPPORTED test videos, have {len(supported_videos)}")
    if len(valid_action) < 2:
        missing.append(f"need >=2 ACTION_PRIMITIVE_VALID train items, have {len(valid_action)}")
    if len(valid_action_videos) < 2:
        missing.append(f"need >=2 videos for valid query_action, have {len(valid_action_videos)}")
    if schema_leak or video_overlap or uid_overlap or contradicted_in_pilot:
        missing.append("isolation or contradicted-item check failed")

    status = "PILOT_READY_FOR_BASELINE" if not missing else "PILOT_NOT_READY"
    return {
        "status": status,
        "note": (
            "Operational readiness for an exploratory baseline only. "
            "Not a formal compositional generalization proof."
            if status == "PILOT_READY_FOR_BASELINE"
            else "Pilot remains blocked until the listed gaps are closed without lowering review standards."
        ),
        "missing": missing,
        "gates": gates,
        "supported_test_ids": [r["id"] for r in supported_test],
        "valid_query_action_ids": [r["id"] for r in valid_action],
        "structural_train_n": len(train_ids),
        "structural_test_n": len(test_ids),
        "unseen_schema": UNSEEN,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def package_zip(media_root: Path, reviews: list[dict], revisions: list[dict], zip_path: Path) -> None:
    rev_by = {row["id"]: row for row in revisions}
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        manifest = []
        for row in reviews:
            item = {
                "id": row["id"],
                "video_id": row["video_id"],
                "question": rev_by[row["id"]]["revised_question"],
                "answer": rev_by[row["id"]]["revised_answer"],
                "time_references": row["time_references"],
                "source_uids": row["source_uids"],
                "review_status": row["review_status"],
                "notes": row["notes"],
                "clips": [],
            }
            for uid in row["source_uids"].split():
                for mode in ("strict", "context"):
                    base = media_root / row["video_id"] / f"uid_{uid}" / mode
                    clip = base / "clip.mp4"
                    sheet = base / "contact_sheet.jpg"
                    if clip.is_file():
                        arc = f"{row['id']}/{row['video_id']}/uid_{uid}/{mode}/clip.mp4"
                        zf.write(clip, arc)
                        item["clips"].append(arc)
                    if sheet.is_file():
                        arc = f"{row['id']}/{row['video_id']}/uid_{uid}/{mode}/contact_sheet.jpg"
                        zf.write(sheet, arc)
                        item["clips"].append(arc)
            manifest.append(item)
        zf.writestr(
            "review_manifest.json",
            json.dumps(
                {
                    "note": "Evidence pack for independent human/video review. Statuses are not auto-certified.",
                    "items": manifest,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Pilot v2.2 readiness artifacts.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--pilot-split", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--judgments", type=Path, help="Optional JSON map of id->review fields")
    parser.add_argument("--media-root", type=Path)
    args = parser.parse_args(argv)

    rows = _load_jsonl(args.candidates)
    pilot_split = json.loads(args.pilot_split.read_text(encoding="utf-8"))
    judgments = {}
    if args.judgments and args.judgments.is_file():
        judgments = json.loads(args.judgments.read_text(encoding="utf-8"))

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    test_reviews = default_test_reviews(rows, judgments)
    train_audit = default_train_audit(rows)
    revisions = default_revisions(rows)
    ready = readiness(pilot_split, test_reviews, train_audit, rows)

    write_csv(out / "test_video_review.csv", test_reviews)
    write_csv(out / "train_primitive_audit.csv", train_audit)
    with (out / "revised_test_questions.jsonl").open("w", encoding="utf-8") as handle:
        for row in revisions:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out / "pilot_readiness.json").write_text(json.dumps(ready, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    media_root = args.media_root or (out / "local_media")
    zip_path = media_root / "lvbench_pilot_v2_2_test_review.zip"
    if media_root.is_dir():
        package_zip(media_root, test_reviews, revisions, zip_path)

    report = "\n".join(
        [
            "# LVBench Compositional Pilot v2.2",
            "",
            "本轮只核验最小 Novel Composition Pilot 的证据与基本能力，不扩大数据、不运行 RSI。",
            "",
            f"## 结论：`{ready['status']}`",
            "",
            ready["note"],
            "",
            "### 缺口" if ready["missing"] else "### 门槛",
            "",
            *(
                [f"- {m}" for m in ready["missing"]]
                if ready["missing"]
                else ["- 操作性门槛已满足。"]
            ),
            "",
            "## 测试题核验",
            "",
            f"- SUPPORTED：{ready['gates']['supported_test_n']}",
            f"- 其余见 `test_video_review.csv`。未独立观察到的项目保持 PENDING_HUMAN_REVIEW。",
            "",
            "## 训练 query_action 语义",
            "",
            *[
                f"- {row['id']}: `{row['action_primitive_status']}` — {row['reason']}"
                for row in train_audit
            ],
            "",
            f"- ACTION_PRIMITIVE_VALID：{ready['gates']['valid_query_action_n']} 道 / {ready['gates']['valid_query_action_videos']} 视频",
            "",
            "## 隔离",
            "",
            f"- unseen schema 训练泄漏：{ready['gates']['schema_leak']}",
            f"- 视频交集：{ready['gates']['video_overlap'] or '[]'}",
            f"- UID 交集：{ready['gates']['uid_overlap'] or '[]'}",
            "",
            "这不是正式 Compositional Generalization Benchmark。",
            "",
        ]
    )
    (out / "REPORT.md").write_text(report, encoding="utf-8")
    (out / "README.md").write_text(
        """# Pilot v2.2

```bash
python3 tools/lvbench_comp/build_pilot_v2_2.py \\
  --candidates research_audit/lvbench_compositional/v2/candidates.jsonl \\
  --pilot-split research_audit/lvbench_compositional/v2_1/pilot_split.json \\
  --output-dir research_audit/lvbench_compositional/pilot_v2_2 \\
  --judgments research_audit/lvbench_compositional/pilot_v2_2/judgments.json
```

可选 `judgments.json` 写入人工看片结论。没有判断时，测试题保持 `PENDING_HUMAN_REVIEW`。
媒体在 `local_media/`，已被 git 忽略。
""",
        encoding="utf-8",
    )
    print(json.dumps({"status": ready["status"], "missing": ready["missing"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
