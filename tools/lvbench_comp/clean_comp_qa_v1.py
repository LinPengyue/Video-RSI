#!/usr/bin/env python3
"""Clean the 45 LVBench compositional QA v1 candidates.

This does not create new source pairs. It applies the text-review decisions:
KEEP, DROP, REVISE, HOLD_LABEL_BALANCE, and NEEDS_VERIFICATION.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


KEEP = {
    "001", "006", "007", "010", "011", "012", "013", "017",
    "021", "022", "029", "030", "032", "038", "043",
}
DROP = {
    "018": "Daesung and Kang Dae-sung may be aliases of one person, so the relation answer is not reliable.",
    "039": "The new question and answer do not form a usable identity reference for this composition.",
    "044": "The question asks for a role, but the answer is not a job or role attribute.",
}
HOLD = {"019", "020", "027", "033", "034"}
NEEDS_VERIFICATION = {"016", "026", "028"}
PENDING = "PENDING_VIDEO_REVIEW"

# Wording that stays inside the official annotations. Keys are the three-digit ids.
REVISIONS: dict[str, dict[str, str]] = {
    "002": {
        "question": "What does the first interviewee do after her former roommate comes to the stage?",
        "answer": "She takes off her shoes",
        "reason": "Replace 'first interview' with 'first interviewee'. The answer is unchanged.",
    },
    "003": {
        "question": "What does the first interviewee do after the first male guest shows up on the stage?",
        "answer": "She slaps the man",
        "reason": "Replace 'first interview' with 'first interviewee' and correct 'show' to 'shows'.",
    },
    "004": {
        "question": "Who cheats on the first interviewee with Kindall?",
        "answer": "David",
        "reason": "Replace 'first interview' with 'first interviewee'. The answer is unchanged.",
    },
    "005": {
        "question": "What is the name of the first interviewee's former roommate?",
        "answer": "Kindall",
        "reason": "Replace 'first interview' with 'first interviewee'. The answer is unchanged.",
    },
    "008": {
        "question": "What brand does the second person to speak on stage show a video about during his talk?",
        "answer": "L'Oreal",
        "reason": "Turn the official statement-question into a direct question. The brand answer is unchanged.",
    },
    "009": {
        "question": "How many points does the player who takes off red clothes to reveal blue clothes underneath score in the fourth game?",
        "answer": "9",
        "reason": "Shorten the official clothing description without dropping the red-to-blue reveal.",
    },
    "014": {
        "question": "What is the hair color of the person on the right side of the screen after the ground move in the third round?",
        "answer": "All white",
        "reason": "Replace the ungrammatical 'one who is' with 'person'. The hair-color answer is unchanged.",
    },
    "015": {
        "question": "At 11:14 in the video, how does the person on the right side of the screen after the ground move in the third round strike the opponent's head?",
        "answer": "An uppercut punch",
        "reason": "Use 'person' for the official on-screen description. The strike answer is unchanged.",
    },
    "016": {
        "question": "Why do the four judges stand up for the third group?",
        "answer": "Because they are so excited about Nymeria's performance",
        "reason": "The official answer names Nymeria's performance, while the question refers to the pair Amber and Nymeria. The pair-wide rewrite is withdrawn.",
    },
    "022": {
        "question": "What are the attitudes of people living in the country the travelers choose towards life?",
        "answer": "They are happy about their life",
        "reason": "Correct 'is the attitudes' to 'are the attitudes'. The answer is unchanged.",
    },
    "023": {
        "question": "Whose house does the person who goes to a party at night sleep in?",
        "answer": "A stranger's friend's",
        "reason": "Replace the fill-in-the-blank with a whose-question. The official option text is unchanged.",
    },
    "024": {
        "question": "What does the first interviewee do after Kindall comes to the stage?",
        "answer": "She quarrels and fights with her",
        "reason": "Replace 'first interview' with 'first interviewee'. The answer is unchanged.",
    },
    "025": {
        "question": "What does the last person to appear during the second interview claim?",
        "answer": "She says she's Brain's first love",
        "reason": "Repair the official 'last one appear' wording. The name Brain is left as annotated.",
    },
    "031": {
        "question": "What does the person who steals the S-shaped jade use to scratch the scorpion's nose, causing the scorpion to sneeze?",
        "answer": "The leave on his head",
        "reason": "The question already matches the official event. The option spelling 'leave' is not changed.",
    },
    "035": {
        "question": "Where do the vlogger team members invite the person wearing green on the first day, on the first night?",
        "answer": "They invite the person wearing Green on the first day to the hotel",
        "type": "attribute_binding",
        "reason": "This binds a clothing attribute to a later place. It is not an independent temporal-reasoning item.",
    },
    "036": {
        "question": "How many flags of the country whose flag is on the flagpole atop the building with the gold clock are on the stage when Putin delivers the first speech?",
        "answer": "5",
        "reason": "Keep both official facts and remove the stacked 'of the ... are there' wording.",
    },
    "037": {
        "question": "Which company does the presenter mention before the company that claims to first to provide AI-powered business insights from secondary data?",
        "answer": "Servicenow",
        "reason": "Correct 'does ... mentions' to 'does ... mention'. The official claim clause is otherwise unchanged.",
    },
    "040": {
        "question": "What competition result does the person who serves first have?",
        "answer": "the final winner",
        "reason": "The final winner is a match result, not an occupation. The answer string is unchanged.",
    },
    "041": {
        "question": "What competition result does the person who gets the first point for the second game have?",
        "answer": "the final winner",
        "reason": "Ask for the match result, and correct the official 'who get' to 'who gets'.",
    },
    "042": {
        "question": "Whose coach is the guy in orange who is always coughing?",
        "answer": "the final winner",
        "reason": "The coughing man is annotated as Lee Chong Wei's coach, and Lee Chong Wei is the final winner.",
    },
    "045": {
        "question": "What is Brittany's relationship to the person shown at 00:02?",
        "answer": "sister",
        "reason": "The official answer says Brittany is Tacara's sister, and Tacara is the person at 00:02.",
    },
}


def _num(candidate_id: str) -> str:
    return candidate_id.rsplit("-", 1)[-1]


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def clean_candidates(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    if len(rows) != 45:
        raise SystemExit(f"expected 45 v1 candidates, found {len(rows)}")
    seen = {_num(row["id"]) for row in rows}
    expected = {f"{index:03d}" for index in range(1, 46)}
    if seen != expected:
        raise SystemExit(f"candidate ids do not cover 001-045: {sorted(expected - seen)}")
    cleaned = []
    decisions = []
    excluded = []
    revisions = []
    for row in rows:
        number = _num(row["id"])
        decision = "KEEP" if number in KEEP else "DROP" if number in DROP else "REVISE"
        status = PENDING
        if number in HOLD:
            status = "HOLD_LABEL_BALANCE"
        elif number in NEEDS_VERIFICATION:
            status = "NEEDS_VERIFICATION"
        elif number in DROP:
            status = "DROPPED"
        reason = ""
        new_question = row["new_question"]
        new_answer = row["new_answer"]
        composition_type = row["composition_type"]
        if number in DROP:
            reason = DROP[number]
            excluded.append(
                {
                    "id": row["id"],
                    "video_id": row["video_id"],
                    "source_uids": " ".join(row["source_uids"]),
                    "old_question": row["new_question"],
                    "old_answer": row["new_answer"],
                    "reason": reason,
                }
            )
        elif number in REVISIONS:
            spec = REVISIONS[number]
            new_question = spec["question"]
            new_answer = spec["answer"]
            composition_type = spec.get("type", composition_type)
            reason = spec["reason"]
            revisions.append(
                {
                    "id": row["id"],
                    "decision": decision,
                    "review_status": status,
                    "old_question": row["new_question"],
                    "new_question": new_question,
                    "old_answer": row["new_answer"],
                    "new_answer": new_answer,
                    "old_type": row["composition_type"],
                    "new_type": composition_type,
                    "reason": reason,
                }
            )
        elif number in HOLD:
            reason = "All current answers in this Yes/No group are Yes. Held out of the review set. No No answer was invented."
        elif number in NEEDS_VERIFICATION:
            reason = (
                "The official answer options are the numbers 13, 20, 5, and 15. "
                "They do not say that 5 is a jersey number, so the question was not rewritten."
            )
            revisions.append(
                {
                    "id": row["id"],
                    "decision": decision,
                    "review_status": status,
                    "old_question": row["new_question"],
                    "new_question": row["new_question"],
                    "old_answer": row["new_answer"],
                    "new_answer": row["new_answer"],
                    "old_type": row["composition_type"],
                    "new_type": composition_type,
                    "reason": reason,
                }
            )
        else:
            reason = "Kept. The wording already matches the official annotations."
        decisions.append(
            {
                "id": row["id"],
                "video_id": row["video_id"],
                "source_uids": " ".join(row["source_uids"]),
                "decision": decision,
                "review_status": status,
                "included_in_clean_set": "yes" if status in {PENDING, "NEEDS_VERIFICATION"} else "no",
                "reason": reason,
            }
        )
        if status not in {PENDING, "NEEDS_VERIFICATION"}:
            continue
        item = dict(row)
        item["source_v1_id"] = row["id"]
        item["composition_type"] = composition_type
        item["new_question"] = new_question
        item["new_answer"] = new_answer
        item["review_status"] = status
        item["video_verified"] = False
        item["clean_decision"] = decision
        item["clean_reason"] = reason
        cleaned.append(item)
    return cleaned, decisions, excluded, revisions


def write_outputs(output_dir: Path, cleaned: list[dict], decisions: list[dict], excluded: list[dict], revisions: list[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "candidates.jsonl").open("w", encoding="utf-8") as handle:
        for item in cleaned:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    _write_csv(output_dir / "review_decisions.csv", decisions)
    _write_csv(output_dir / "excluded.csv", excluded)
    _write_csv(output_dir / "revision_log.csv", revisions)
    (output_dir / "REPORT.md").write_text(_report(cleaned, decisions, excluded, revisions), encoding="utf-8")
    (output_dir / "README.md").write_text(README, encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0]) if rows else ["id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _report(cleaned: list[dict], decisions: list[dict], excluded: list[dict], revisions: list[dict]) -> str:
    by_status: dict[str, int] = {}
    by_decision: dict[str, int] = {}
    for row in decisions:
        by_decision[row["decision"]] = by_decision.get(row["decision"], 0) + 1
        by_status[row["review_status"]] = by_status.get(row["review_status"], 0) + 1
    text_fixed = sum(
        1
        for row in revisions
        if row["review_status"] == PENDING
        and (
            row["old_question"] != row["new_question"]
            or row["old_answer"] != row["new_answer"]
            or row["old_type"] != row["new_type"]
        )
    )
    return "\n".join(
        [
            "# LVBench Compositional QA v1.1 clean",
            "",
            "这一版只整理 v1 的 45 道候选，没有新增来源配对。任何题目都还不是正式有效题。",
            "",
            "## 数量",
            "",
            f"- 原始候选：45。",
            f"- KEEP：{by_decision.get('KEEP', 0)}。",
            f"- REVISE：{by_decision.get('REVISE', 0)}。",
            f"- DROP：{by_decision.get('DROP', 0)}。排除记录见 `excluded.csv`。",
            f"- 文本已按标注改完并进入审查集：{text_fixed}。",
            f"- `NEEDS_VERIFICATION`：{by_status.get('NEEDS_VERIFICATION', 0)}。016 的答案指向双人组合中的单人表演；026 和 028 的官方选项只有数字 5，没有写明是球衣号码。",
            f"- `HOLD_LABEL_BALANCE`：{by_status.get('HOLD_LABEL_BALANCE', 0)}。五道 Yes/No 题答案全是 Yes，未进入审查集，也没有伪造 No。",
            f"- 清洗后审查集：{len(cleaned)}。状态是 `PENDING_VIDEO_REVIEW` 或 `NEEDS_VERIFICATION`。",
            f"- 排除：{len(excluded)}。",
            f"- 问法修订记录：{len(revisions)}。",
            "",
            "035 从 `event_binding` 改为 `attribute_binding`，因为它绑定的是第一天的衣着和后来的邀请地点。",
            "",
            "视频事实没有在这里判断。",
            "",
        ]
    )


README = """# LVBench Compositional QA v1.1 clean

整理 `qa_v1/candidates.jsonl` 的 45 道题。不覆盖 v0 或 v1，不新增组合配对。

```bash
python3 tools/lvbench_comp/clean_comp_qa_v1.py \\
  --input research_audit/lvbench_compositional/qa_v1/candidates.jsonl \\
  --output-dir research_audit/lvbench_compositional/qa_v1_clean
```

测试：

```bash
python3 tools/lvbench_comp/test_clean_comp_qa_v1.py
```

视频片段写在 `qa_v1_clean/local_media/`，该目录被 git 忽略。索引 `video_evidence_index.json` 只记录路径、哈希和时间，不判断视频事实。

```bash
python3 tools/lvbench_comp/extract_v1_clean_evidence.py \\
  --candidates research_audit/lvbench_compositional/qa_v1_clean/candidates.jsonl \\
  --media-root research_audit/lvbench_compositional/qa_v1_clean/local_media \\
  --index research_audit/lvbench_compositional/qa_v1_clean/video_evidence_index.json
```

本轮抽了 10 道、10 个视频。012 和 017 复用 Phase 1 里哈希一致的片段。另外加上 008，避免和 043 重复使用同一个视频。
"""


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Clean LVBench compositional QA v1 candidates.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    cleaned, decisions, excluded, revisions = clean_candidates(_load(args.input))
    write_outputs(args.output_dir, cleaned, decisions, excluded, revisions)
    print(json.dumps({
        "clean": len(cleaned),
        "decisions": len(decisions),
        "excluded": len(excluded),
        "revisions": len(revisions),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
