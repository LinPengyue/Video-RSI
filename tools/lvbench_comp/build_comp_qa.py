#!/usr/bin/env python3
"""Build LVBench Compositional QA candidates from official annotations.

Pairs are kept only when a name or a possessed object is explicitly shared by
the official wording. Shared ordinary keywords do not qualify. Every candidate
stays PENDING_REVIEW: the annotations support the wording, the video does not.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from prepare_lvbench import split_question

from tools.lvbench_comp.extract_evidence import EvidenceError, parse_time_reference


PHASE = "lvbench-compositional-qa-v0"
REVIEW_STATUS = "PENDING_REVIEW"
REQUIRED_FIELDS = (
    "id",
    "video_id",
    "source_uids",
    "source_questions",
    "source_answers",
    "time_references",
    "composition_type",
    "new_question",
    "new_answer",
    "answer_derivation",
    "review_status",
)
COMPOSITION_TYPES = ("entity_binding", "object_binding", "temporal_event")
MAX_SPAN_SECONDS = 12 * 60
MAX_PER_IDENTIFIER = 4
MIN_START_GAP_SECONDS = 10
AMBIGUOUS_NAMES = {"Will", "May", "Hope", "Art", "Bo", "Ed", "Al", "Jo", "Don"}
NAME_SHAPE = re.compile(r"^[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,3}$")
IDENT_STEM = re.compile(r"(?i)^(?:what is the name of|what's the name of|who is)\b")
BARE_NAME = re.compile(r"(?i)^what is the (.+?) name\??$")
OF_NAME = re.compile(r"(?i)^what(?:'s| is) the name of (.+?)\??$")
WHO_IS = re.compile(r"(?i)^who is (.+?)\??$")
SEARCH = re.compile(
    r"\b(?:looks for|looking for|searches for) (his|her|their) ([a-z]{3,})\b",
    re.I,
)
HOLDS = re.compile(
    r"\b((?:[Tt]he|[Aa]n?) (?:woman in red|woman|man|girl|boy)) has (his|her|their) ([a-z]{3,})\b"
)
SEEKER = re.compile(r"(?i)^what does (.+?) do\b")
AFTER = re.compile(r"\bafter\b.+", re.I)
COLOR = re.compile(r"(?i)^what color of clothes does (.+?) wear (.+?)\??$")
WH_QUESTION = re.compile(r"(?i)^(what|where|why|how|who)\b")


def load_qas(metadata_path: Path) -> list[dict]:
    records = []
    with Path(metadata_path).open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            video_id = str(raw["key"])
            for qa in raw["qa"]:
                stem, options = split_question(qa["question"])
                letter = str(qa["answer"])
                if letter not in options:
                    raise ValueError(f"{metadata_path}:{lineno} UID {qa['uid']} answer {letter} missing")
                interval = _interval(qa.get("time_reference"))
                records.append(
                    {
                        "video_id": video_id,
                        "uid": str(qa["uid"]),
                        "question": qa["question"],
                        "stem": " ".join(stem.split()),
                        "options": options,
                        "answer_letter": letter,
                        "answer_text": " ".join(options[letter].split()),
                        "time_reference": qa.get("time_reference"),
                        "question_type": qa.get("question_type"),
                        "interval": interval,
                    }
                )
    return records


def _interval(reference) -> tuple[float, float] | None:
    if not isinstance(reference, str):
        return None
    try:
        start, end = parse_time_reference(reference)
    except EvidenceError:
        return None
    return (start, end)


def _separated(left: dict, right: dict) -> bool:
    left_start, left_end = left["interval"]
    right_start, right_end = right["interval"]
    return left_end <= right_start or right_end <= left_start


def _span_ok(item: dict) -> bool:
    interval = item["interval"]
    if interval is None:
        return False
    start, end = interval
    return 0 <= end - start <= MAX_SPAN_SECONDS


def _is_name(text: str) -> bool:
    cleaned = text.strip().rstrip(".")
    if cleaned in AMBIGUOUS_NAMES or len(cleaned) < 3:
        return False
    return NAME_SHAPE.fullmatch(cleaned) is not None


def _contains_name(text: str, name: str) -> bool:
    return re.search(r"\b" + re.escape(name) + r"\b", text) is not None


def _replace_name(text: str, name: str, replacement: str) -> str:
    return re.sub(r"\b" + re.escape(name) + r"\b", replacement, text)


def is_identifier(stem: str) -> bool:
    return bool(IDENT_STEM.search(stem) or BARE_NAME.match(stem))


def _polish(question: str) -> str:
    question = " ".join(question.split()).strip()
    if question and question[0].islower():
        question = question[0].upper() + question[1:]
    if not question.endswith("?"):
        question += "?"
    return question


def referring_expression(stem: str) -> str | None:
    text = " ".join(stem.strip().split())
    matched = OF_NAME.match(text)
    if matched:
        rest = matched.group(1).strip()
        if re.match(r"(?i)^(the|a|an)\b", rest) or re.match(r"^[A-Z]\w+'s\b", rest):
            return rest[0].lower() + rest[1:] if rest.startswith(("The ", "A ", "An ")) else rest
        return "the " + rest
    matched = BARE_NAME.match(text)
    if matched and not OF_NAME.match(text):
        rest = re.sub(r"'s$", "", matched.group(1).strip())
        return "the " + rest
    matched = WHO_IS.match(text)
    if matched:
        rest = matched.group(1).strip()
        if rest.lower() in {"he", "she", "it", "they", "this", "that"}:
            return None
        if re.match(r"(?i)^(the|a|an)\b", rest):
            return rest[0].lower() + rest[1:]
        if re.match(r"^[A-Z]\w+'s\b", rest):
            return rest
        return "the one who is " + rest
    return None


def _answer_label(item: dict) -> str:
    return f"{item['answer_letter']}: {item['answer_text']}"


def _base_candidate(kind: str, first: dict, second: dict, question: str, answer: str, derivation: str) -> dict:
    ordered = sorted((first, second), key=lambda item: (item["interval"][0], item["uid"]))
    gap = abs(first["interval"][0] - second["interval"][0])
    return {
        "video_id": first["video_id"],
        "source_uids": [item["uid"] for item in ordered],
        "source_questions": [item["question"] for item in ordered],
        "source_answers": [_answer_label(item) for item in ordered],
        "time_references": [item["time_reference"] for item in ordered],
        "composition_type": kind,
        "new_question": _polish(question),
        "new_answer": " ".join(answer.split()),
        "answer_derivation": derivation,
        "review_status": REVIEW_STATUS,
        "time_gap_seconds": round(gap, 3),
        "video_verified": False,
    }


def _entity_candidates(grouped: dict[str, list[dict]]) -> list[dict]:
    found = []
    for video_id, items in grouped.items():
        identifiers = []
        for item in items:
            if not is_identifier(item["stem"]):
                continue
            name = item["answer_text"].strip().rstrip(".")
            phrase = referring_expression(item["stem"])
            if phrase and _is_name(name):
                identifiers.append((item, name, phrase))
        for ident, name, phrase in identifiers:
            linked = []
            for other in items:
                if other["uid"] == ident["uid"] or not _span_ok(ident) or not _span_ok(other):
                    continue
                if not _separated(ident, other):
                    continue
                if abs(ident["interval"][0] - other["interval"][0]) < MIN_START_GAP_SECONDS:
                    continue
                in_stem = _contains_name(other["stem"], name)
                in_answer = _contains_name(other["answer_text"], name)
                if not in_stem and not in_answer:
                    continue
                if not in_stem and len(other["answer_text"].split()) > 14:
                    continue
                if in_stem:
                    question = _replace_name(other["stem"], name, phrase)
                    answer = _replace_name(other["answer_text"], name, phrase)
                    link = "the later question uses the official name"
                else:
                    question = other["stem"]
                    answer = _replace_name(other["answer_text"], name, phrase)
                    link = "the later official answer is or names this person, while its question does not"
                if question.strip(" ?") == other["stem"].strip(" ?") and answer == other["answer_text"]:
                    continue
                if name in question or name in answer:
                    # A second copy of the name survived, so the substitution is incomplete.
                    if _contains_name(question, name) or (
                        _contains_name(answer, name) and answer.strip().rstrip(".") != phrase
                    ):
                        continue
                gap = abs(ident["interval"][0] - other["interval"][0])
                derivation = (
                    f"UID {ident['uid']} ({ident['time_reference']}) asks for a name and the "
                    f"official option {ident['answer_letter']} is {name!r}. "
                    f"UID {other['uid']} ({other['time_reference']}) {link}. "
                    f"Official option {other['answer_letter']} is {other['answer_text']!r}. "
                    f"The new wording replaces {name!r} with {phrase!r}. "
                    "This uses the annotation string only. It does not verify that the "
                    "picture shows the same person, and it is not a certified composition item."
                )
                candidate = _base_candidate("entity_binding", ident, other, question, answer, derivation)
                candidate["substitution_site"] = "question" if in_stem else "answer"
                candidate["_gap"] = gap
                candidate["_in_stem"] = in_stem
                candidate["_name_q"] = is_identifier(other["stem"])
                linked.append(candidate)
            linked.sort(
                key=lambda item: (
                    not item["_in_stem"],
                    item["_name_q"],
                    -item["_gap"],
                    item["source_uids"],
                )
            )
            found.extend(linked[:MAX_PER_IDENTIFIER])
    return found


def _object_candidates(grouped: dict[str, list[dict]]) -> list[dict]:
    found = []
    for items in grouped.values():
        for seek in items:
            if not _span_ok(seek):
                continue
            searched = SEARCH.search(seek["answer_text"])
            seeker = SEEKER.match(seek["stem"])
            if not searched or not seeker:
                continue
            possessive, obj = searched.group(1).lower(), searched.group(2).lower()
            event = AFTER.search(seek["stem"])
            event_text = event.group(0).rstrip(" ?") if event else ""
            for holder_item in items:
                if holder_item["uid"] == seek["uid"] or not _span_ok(holder_item):
                    continue
                held = HOLDS.search(holder_item["answer_text"])
                if not held:
                    continue
                if held.group(3).lower() != obj or held.group(2).lower() != possessive:
                    continue
                if holder_item["interval"][0] + 1 < seek["interval"][0]:
                    continue
                specific = re.search(r"\bthe woman in red\b", holder_item["stem"], re.I)
                holder = specific.group(0) if specific else held.group(1)
                holder = holder[0].lower() + holder[1:]
                question = (
                    f"Who has the {obj} that {seeker.group(1)} looks for {event_text}?"
                ).replace("  ", " ")
                if not event_text:
                    continue
                meeting = AFTER.search(holder_item["stem"])
                if meeting:
                    question = question.rstrip("?") + ", " + meeting.group(0).rstrip(" ?") + "?"
                derivation = (
                    f"UID {seek['uid']} ({seek['time_reference']}) option {seek['answer_letter']} "
                    f"is {seek['answer_text']!r}. UID {holder_item['uid']} ({holder_item['time_reference']}) "
                    f"option {holder_item['answer_letter']} is {holder_item['answer_text']!r}. "
                    f"The shared object is {obj!r} with the same possessive {possessive!r}. "
                    f"The holder wording {holder!r} is taken from the official question or answer. "
                    "The annotation supports possession only. It does not support a more specific "
                    "action such as picking the object up. Video identity is not verified."
                )
                candidate = _base_candidate(
                    "object_binding", seek, holder_item, question, holder, derivation
                )
                candidate["substitution_site"] = "question"
                found.append(candidate)
    return found


def _temporal_candidates(grouped: dict[str, list[dict]]) -> list[dict]:
    found = []
    for items in grouped.values():
        names = []
        ident_uids = set()
        for item in items:
            if is_identifier(item["stem"]) and _is_name(item["answer_text"].strip().rstrip(".")):
                names.append(item["answer_text"].strip().rstrip("."))
                ident_uids.add(item["uid"])
        for name in sorted(set(names)):
            events = [
                item
                for item in items
                if item["uid"] not in ident_uids
                and _span_ok(item)
                and _contains_name(item["stem"], name)
                and WH_QUESTION.match(item["stem"])
            ]
            best = None
            for earlier in events:
                color = COLOR.match(earlier["stem"])
                if not color or color.group(1) != name:
                    continue
                if _contains_name(earlier["answer_text"], name):
                    continue
                if len(earlier["answer_text"].split()) > 3:
                    continue
                for later in events:
                    if later["uid"] == earlier["uid"]:
                        continue
                    if later["interval"][0] < earlier["interval"][1] + 30:
                        continue
                    gap = later["interval"][0] - earlier["interval"][1]
                    descriptor = f"the person wearing {earlier['answer_text']} {color.group(2)}"
                    question = _polish(_replace_name(later["stem"], name, descriptor))
                    answer = _replace_name(later["answer_text"], name, descriptor)
                    if _contains_name(question, name):
                        continue
                    derivation = (
                        f"UID {earlier['uid']} ({earlier['time_reference']}) says the clothes "
                        f"{name} wears {color.group(2)} are {earlier['answer_text']!r}. "
                        f"UID {later['uid']} ({later['time_reference']}) is a later official question "
                        f"about the same annotated name. Option {later['answer_letter']} is "
                        f"{later['answer_text']!r}. The time order comes from the official "
                        "time references. The shared name is not video-verified identity."
                    )
                    candidate = _base_candidate("temporal_event", earlier, later, question, answer, derivation)
                    candidate["substitution_site"] = "question"
                    candidate["_gap"] = gap
                    if best is None or gap > best["_gap"]:
                        best = candidate
            if best:
                found.append(best)
    return found


def _dedupe(candidates: list[dict]) -> list[dict]:
    seen_pairs = set()
    seen_questions = set()
    kept = []
    for candidate in candidates:
        pair = (
            candidate["video_id"],
            tuple(candidate["source_uids"]),
            candidate["composition_type"],
        )
        question_key = (
            candidate["video_id"],
            re.sub(r"\s+", " ", candidate["new_question"].strip().lower()),
        )
        if pair in seen_pairs or question_key in seen_questions:
            continue
        if not candidate["new_question"] or not candidate["new_answer"]:
            continue
        seen_pairs.add(pair)
        seen_questions.add(question_key)
        kept.append(candidate)
    kept.sort(
        key=lambda item: (
            COMPOSITION_TYPES.index(item["composition_type"]),
            item["video_id"],
            item["source_uids"],
        )
    )
    for index, candidate in enumerate(kept, 1):
        candidate["id"] = f"LVCOMP-V0-{index:03d}"
        candidate.pop("_gap", None)
        candidate.pop("_in_stem", None)
        candidate.pop("_name_q", None)
    return kept


def build_candidates(records: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for record in records:
        grouped[record["video_id"]].append(record)
    candidates = []
    candidates.extend(_entity_candidates(grouped))
    candidates.extend(_object_candidates(grouped))
    candidates.extend(_temporal_candidates(grouped))
    return _dedupe(candidates)


def validate_candidate(candidate: dict, records: list[dict] | None = None) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in candidate or candidate[field] in ("", None, [], {}):
            errors.append(f"missing {field}")
    if candidate.get("review_status") != REVIEW_STATUS:
        errors.append("review_status")
    if candidate.get("composition_type") not in COMPOSITION_TYPES:
        errors.append("composition_type")
    uids = candidate.get("source_uids") or []
    if len(uids) < 2 or len(set(uids)) != len(uids):
        errors.append("source_uids")
    if len(candidate.get("source_questions") or []) != len(uids):
        errors.append("source_questions")
    if len(candidate.get("source_answers") or []) != len(uids):
        errors.append("source_answers")
    if len(candidate.get("time_references") or []) != len(uids):
        errors.append("time_references")
    if records is not None and not errors:
        index = {(item["video_id"], item["uid"]): item for item in records}
        for uid, label, question, reference in zip(
            candidate["source_uids"],
            candidate["source_answers"],
            candidate["source_questions"],
            candidate["time_references"],
        ):
            item = index.get((candidate["video_id"], uid))
            if item is None:
                errors.append(f"unknown uid {uid}")
                continue
            if item["question"] != question or item["time_reference"] != reference:
                errors.append(f"source mismatch {uid}")
            if not label.startswith(item["answer_letter"] + ":"):
                errors.append(f"answer letter {uid}")
            if item["answer_text"] not in label:
                errors.append(f"answer text {uid}")
    return errors


def write_outputs(candidates: list[dict], output_dir: Path, qa_count: int, video_count: int) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "candidates.jsonl"
    csv_path = output_dir / "candidates.csv"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
    fields = list(REQUIRED_FIELDS) + ["substitution_site", "time_gap_seconds", "video_verified"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for candidate in candidates:
            row = dict(candidate)
            for key in ("source_uids", "source_questions", "source_answers", "time_references"):
                row[key] = " || ".join(row[key])
            writer.writerow(row)
    counts = {kind: sum(item["composition_type"] == kind for item in candidates) for kind in COMPOSITION_TYPES}
    stats = {
        "phase": PHASE,
        "official_qa": qa_count,
        "official_videos": video_count,
        "candidates": len(candidates),
        "videos": len({item["video_id"] for item in candidates}),
        "by_type": counts,
        "review_status": REVIEW_STATUS,
        "video_verified": False,
    }
    (output_dir / "stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    return stats


def render_report(stats: dict, candidates: list[dict]) -> str:
    lines = [
        "# LVBench Compositional QA Dataset v0",
        "",
        "这些题目全部是 `PENDING_REVIEW`。它们由官方标注里的名字或所属物对应关系推出，没有看片核实，也没有 Seen/Unseen 划分。",
        "",
        "## 规模",
        "",
        f"- 官方 QA：{stats['official_qa']}，视频 {stats['official_videos']} 个。",
        f"- 候选题：{stats['candidates']}。",
        f"- 覆盖视频：{stats['videos']}。",
        f"- `entity_binding`：{stats['by_type']['entity_binding']}。",
        f"- `object_binding`：{stats['by_type']['object_binding']}。",
        f"- `temporal_event`：{stats['by_type']['temporal_event']}。",
        "",
        "## 为什么不是把关键词撞在一起",
        "",
        "- 人物题：一道题的正确答案是人名，另一道题的题干或正确答案按整词用了这个名字。问法把名字换成前一道题里的指称。",
        "- 物体题：一道正确答案是 “looks/searches for his/her X”，另一道正确答案是同一所有格的 “has his/her X”。只写成持有，不写成捡起。",
        "- 时间题：同名人物先有一条衣服颜色标注，后有一条间隔至少 30 秒的事件题。颜色用来回指这个人，后题提供答案。",
        "- 同一标识最多保留 4 道人物题。题干里出现名字的配对优先；另一道题本身又是人名题的配对靠后。时间窗互相重叠、起点相距不足 10 秒、超过 12 分钟、无法解析，以及 Will/May 这类兼类词，都丢掉。",
        "- “What is the first interview's name?” 这类以 name 结尾的人名题，和 “What is the name of …” / “Who is …” 一样作为人物标识。",
        "- 只共享 video、the、man 这类普通词的题目不会进入候选。",
        "",
        "## 需要人工确认",
        "",
        "- 同名是否真是同一个人，尤其是后题已经写出名字时，前一段画面是否还必要。",
        "- 物体题里的持有人是否能只靠后一个片段看出来。",
        "- 自动替换后人名问法可能生硬，审查时可以改写，但不能改到来源标注支持不了的动作。原始问法里的语法错误会保留。",
        "- 时间题只证明官方时间戳的先后和名字字符串相同。",
        "- 物体题和衣服颜色时间题在全库里各只有一对满足规则，所以这两类数量少。",
        "- 同一道官方 UID 可以出现在多道候选里。例如酒店邀请同时连到“加入旅途的老人”和“第一天穿绿色衣服的人”，作弊事件同时连到 Sierra 和 Kindall。审查时按题独立看，不要把共享来源当成两份独立证据。",
        "",
        "目标区间是 30–50。能同时满足“两个官方 QA、同一视频、答案可由标注推出、而且不是用并且把两题拼起来”的配对，经过去重和每名最多 4 题之后，就是规模一节里的数量。共享普通词、时间窗重叠、超长时间窗的配对没有补进去。",
        "",
        "## 题干没有改写的题",
        "",
        "下面这些题的问句仍是后一道官方题的题干，只把正确答案里的人名换成了前一道题的指称。审查时要确认：用指称作答是否不会和人名答案混淆。",
        "",
    ]
    answer_site = [item["id"] for item in candidates if item.get("substitution_site") == "answer"]
    if answer_site:
        lines.append(", ".join(answer_site))
    else:
        lines.append("无。")
    lines.extend(["", "## 样例", ""])
    picked: list[dict] = []

    def take(predicate) -> None:
        for candidate in candidates:
            if candidate in picked or not predicate(candidate):
                continue
            picked.append(candidate)
            return

    take(lambda item: item["composition_type"] == "entity_binding" and set(item["source_uids"]) == {"2873", "2890"})
    take(lambda item: set(item["source_uids"]) == {"120", "121"})
    take(lambda item: item["composition_type"] == "temporal_event")
    seen_videos = {item["video_id"] for item in picked}
    for candidate in candidates:
        if len(picked) >= 10:
            break
        if candidate["composition_type"] == "entity_binding" and candidate["video_id"] not in seen_videos:
            picked.append(candidate)
            seen_videos.add(candidate["video_id"])
    for candidate in picked:
        lines.append(
            f"### {candidate['id']} `{candidate['composition_type']}` `{candidate['video_id']}`"
        )
        lines.append("")
        lines.append(f"- UIDs: {', '.join(candidate['source_uids'])}")
        lines.append(f"- 时间: {' || '.join(candidate['time_references'])}")
        lines.append(f"- 新问题: {candidate['new_question']}")
        lines.append(f"- 新答案: {candidate['new_answer']}")
        lines.append("")
    lines.append("完整列表见 `candidates.jsonl`。")
    lines.append("")
    return "\n".join(lines)


README = """# LVBench Compositional QA v0

从 LVBench 官方 `video_info.meta.jsonl` 构造组合题候选，供人工审查。不修改 Video-RSI，不调用模型，不划分 Seen/Unseen。

## 复现

在仓库根目录执行：

```bash
python3 tools/lvbench_comp/build_comp_qa.py \\
  --metadata /home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl \\
  --output-dir research_audit/lvbench_compositional/qa_v0
```

选项解析复用 `prepare_lvbench.split_question`。时间解析复用 `tools/lvbench_comp/extract_evidence.parse_time_reference`。

测试：

```bash
python3 tools/lvbench_comp/test_build_comp_qa.py
```

## 规则

同一视频内，只有下面三类配对会出题：

1. `entity_binding`：人名题的正确选项整词出现在另一题的题干或正确答案里。
2. `object_binding`：一题答案是寻找 his/her/their X，另一题答案是同一 X 被某人 has。
3. `temporal_event`：同名人物的衣服颜色题，和至少 30 秒之后的另一道事件题。

所有 `review_status` 都是 `PENDING_REVIEW`。`video_verified` 固定为 false。
"""


def write_docs(output_dir: Path, stats: dict, candidates: list[dict]) -> None:
    (output_dir / "REPORT.md").write_text(render_report(stats, candidates), encoding="utf-8")
    (output_dir / "README.md").write_text(README, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build LVBench compositional QA candidates.")
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    records = load_qas(args.metadata)
    candidates = build_candidates(records)
    problems = []
    for candidate in candidates:
        problems.extend(f"{candidate['id']}: {item}" for item in validate_candidate(candidate, records))
    if problems:
        raise SystemExit("invalid candidates:\n" + "\n".join(problems))
    stats = write_outputs(
        candidates,
        args.output_dir,
        qa_count=len(records),
        video_count=len({item["video_id"] for item in records}),
    )
    write_docs(args.output_dir, stats, candidates)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
