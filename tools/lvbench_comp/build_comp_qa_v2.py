#!/usr/bin/env python3
"""LVBench compositional QA v2: expand candidates and analyze Seen/Unseen splits.

Does not overwrite v0, v1, or v1_clean. Does not judge video truth for new items.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.lvbench_comp.build_comp_qa import (  # noqa: E402
    _separated,
    _span_ok,
    load_qas,
)
from tools.lvbench_comp.extract_evidence import EvidenceError, parse_time_reference  # noqa: E402


PHASE = "lvbench-compositional-qa-v2"
REVIEW_STATUS = "PENDING_VIDEO_REVIEW"
DRAFT_STATUS = "NEEDS_HUMAN_DRAFT"
MAX_SPAN_SECONDS = 12 * 60
MIN_START_GAP = 10.0

SCHEMA_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("identify_person + query_location", re.compile(r"(?i)\b(where|invite|hotel|house|country|scene)\b")),
    ("identify_person + query_attribute", re.compile(r"(?i)\b(number|color|hair|clothes|skill|role|brand|points|flag)\b")),
    ("identify_object + query_holder", re.compile(r"(?i)\b(who has|item the man|searched for|holds)\b")),
    ("identify_event_result + query_cause", re.compile(r"(?i)\b(why|feel|sad|fall|frustrated)\b")),
    ("identify_person + query_action", re.compile(r"(?i)\b(what does|what did|do after|claim|strike|sleep)\b")),
    ("identify_person + query_relation", re.compile(r"(?i)\b(relationship|sister|coach|roommate|whose)\b")),
    ("identify_place + query_attitude", re.compile(r"(?i)\battitude")),
    ("identify_person + query_order", re.compile(r"(?i)\b(from front to back|place|podium|order)\b")),
    ("identify_event_result + query_action", re.compile(r"(?i)\b(substitut|after|happens)\b")),
]

# Curated completions from v1 pending drafts. Keys are draft ids without prefix.
PENDING_COMPLETIONS: dict[str, dict] = {
    "001": {
        "question": "What did the man do after kissing the woman's hands during the Vancouver 2010 performance that was done while wearing a white dress?",
        "answer": "He got down on one knee",
        "type": "event_binding",
        "schema": "identify_event_result + query_action",
        "derivation": "Bridge Free dance: white-dress performance → Free Dance action after kissing hands.",
    },
    "004": {
        "question": "Who is the little girl that comes to the place where the scene shown in the video is?",
        "answer": "Mo Farah's daughter",
        "type": "entity_binding",
        "schema": "identify_place + query_person",
        "derivation": "Bridge Sports Field: scene location → girl who comes there.",
    },
    "005": {
        "question": "Who is the woman that comes to the place where the scene shown in the video is?",
        "answer": "Mo Fara's wife",
        "type": "entity_binding",
        "schema": "identify_place + query_person",
        "derivation": "Bridge Sports Field: scene location → woman who comes there. Official spelling Mo Fara kept.",
    },
    "009": {
        "question": "How to describe the feeling of the person who gets the first point for the second game at 48:16?",
        "answer": "He feels frustrated because he does not catch the shuttlecock from the opponent",
        "type": "event_binding",
        "schema": "identify_event_result + query_cause",
        "derivation": "Bridge Lee Chong Wei: first point of game two → feeling at 48:16.",
    },
    "013": {
        "question": "What happens from 02:03-04:09 involving the animal that appears first in the video playing with the wood alone?",
        "answer": "The two people pick beech nut, play with the dog",
        "type": "object_binding",
        "schema": "identify_object + query_action",
        "derivation": "Bridge the dog: first wood-play animal → later activity window.",
    },
    "014": {
        "question": "What happens from 04:49-06:20 involving the animal that appears first in the video playing with the wood alone?",
        "answer": "The couple gathers the fern and puts it into the iron bucket. The dog watches them",
        "type": "object_binding",
        "schema": "identify_object + query_action",
        "derivation": "Bridge the dog: first wood-play animal → fern gathering window.",
    },
    "021": {
        "question": "What is the end of the one who rescues the orange calabash boy and the grandfather?",
        "answer": "He is thrown off the cliff by the scorpion",
        "type": "event_binding",
        "schema": "identify_person + query_action",
        "derivation": "Bridge the pangolin: rescuer identity → later fate.",
    },
    "022": {
        "question": "How many kinds of desserts do the vlogger team and the person who have quarrel with a grey T-shirt elder in the Monastery have on the third day?",
        "answer": "2",
        "type": "entity_binding",
        "schema": "identify_person + query_attribute",
        "derivation": "Bridge Mikhail: quarrel identity → dessert count.",
    },
    "023": {
        "question": "Where do the vlogger team members invite the person who have quarrel with a grey T-shirt elder in the Monastery on the first night?",
        "answer": "They invite Mikhail to the hotel",
        "type": "entity_binding",
        "schema": "identify_person + query_location",
        "derivation": "Bridge Mikhail: quarrel identity → hotel invitation. Official answer wording kept.",
    },
    "024": {
        "question": "What happens from 04:19-04:45 involving the animal that appears at 00:07?",
        "answer": "The chef cooks Lobster Quesadilla",
        "type": "object_binding",
        "schema": "identify_object + query_action",
        "derivation": "Bridge Lobster: animal at 00:07 → chef cooking event.",
    },
    "025": {
        "question": "What happens from 04:50-05:20 involving the animal that appears at 00:07?",
        "answer": "Sonny tastes Lobster Quesadilla",
        "type": "object_binding",
        "schema": "identify_object + query_action",
        "derivation": "Bridge Lobster: animal at 00:07 → tasting event. Sonny kept as official wording.",
    },
    "034": {
        "question": "Who does Kroos substitute at 65:13?",
        "answer": "the German player who attempts the first shot",
        "type": "event_binding",
        "schema": "identify_event_result + query_action",
        "derivation": "Bridge Trochowski: first shot → substituted by Kroos. Answer hides the name.",
    },
    "035": {
        "question": "What happens after the boy and the cat meet the one they meet on the way they first leave home?",
        "answer": "They clean the house",
        "type": "event_binding",
        "schema": "identify_person + query_action",
        "derivation": "Bridge the dog: first meeting → next action.",
    },
    "026": {
        "question": "Why does Sonny look so expected at 07:27 involving the animal that appears at 00:07?",
        "answer": "He wants to eat the Bohemian Lobster",
        "type": "object_binding",
        "schema": "identify_object + query_cause",
        "derivation": "Bridge Lobster: animal at 00:07 → expectation reason. Official Sonny wording kept.",
    },
    "036": {
        "question": "What happens after the yellow box is replaced by the cat, involving the one the boy and the cat meet on the way they first leave home?",
        "answer": "The dog chases the rabbit",
        "type": "event_binding",
        "schema": "identify_person + query_action",
        "derivation": "Bridge the dog: first roadside meeting → chase after yellow box.",
    },
    "039": {
        "question": "How do the vloggers leave the platform and go upstairs after the first means of transportation they take when they come to China?",
        "answer": "After they get off the high-speed train, they go upstairs and go pass the ticket gate, exiting the train station",
        "type": "event_binding",
        "schema": "identify_event_result + query_action",
        "derivation": "Bridge high-speed train: first transport → leaving the platform.",
    },
    "040": {
        "question": "What means of transportation do the vloggers take after getting off the first means of transportation they take when they come to China?",
        "answer": "Subway",
        "type": "event_binding",
        "schema": "identify_event_result + query_action",
        "derivation": "Bridge high-speed train: first transport → next transport.",
    },
}


def _num(cid: str) -> str:
    return cid.rsplit("-", 1)[-1]


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def assign_schema(question: str, composition_type: str, forced: str | None = None) -> str:
    if forced:
        return forced
    for name, pattern in SCHEMA_RULES:
        if pattern.search(question):
            return name
    if composition_type == "object_binding":
        return "identify_object + query_holder"
    if composition_type == "attribute_binding":
        return "identify_person + query_attribute"
    if composition_type == "event_binding":
        return "identify_event_result + query_action"
    return "identify_person + query_attribute"


def primitives(schema: str) -> tuple[str, str]:
    left, right = [part.strip() for part in schema.split("+", 1)]
    return left, right


def from_clean(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        item = dict(row)
        item["id"] = f"LVCOMP-V2-{_num(row['id'])}"
        item["source_v1_id"] = row["id"]
        item["phase"] = PHASE
        item["review_status"] = REVIEW_STATUS if row.get("review_status") != "NEEDS_VERIFICATION" else "NEEDS_VERIFICATION"
        item["video_verified"] = False
        item["composition_schema"] = assign_schema(row["new_question"], row["composition_type"])
        item["origin"] = "v1_clean"
        out.append(item)
    return out


def complete_pending(pending: list[dict], used_pairs: set[tuple[str, tuple[str, str]]]) -> tuple[list[dict], list[dict]]:
    complete = []
    remaining = []
    next_id = 100
    for row in pending:
        draft_num = _num(row["id"]).lstrip("0") or "0"
        # pending ids are like LVCOMP-V1-DRAFT-001
        draft_key = row["id"].rsplit("-", 1)[-1]
        pair = (row["video_id"], tuple(sorted(row["source_uids"])))
        if draft_key in PENDING_COMPLETIONS and pair not in used_pairs:
            spec = PENDING_COMPLETIONS[draft_key]
            bridge_leak = False
            # crude leak check: if both answers share a distinctive token that appears in the new question
            answers = " ".join(row["source_answers"])
            for token in re.findall(r"[A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+)?", answers):
                if len(token) >= 4 and token.lower() in spec["question"].lower() and token.lower() not in {"free dance", "vancouver"}:
                    # Allow descriptive phrases; flag obvious proper-name leaks only when the name is the bridge.
                    if token in {"Lee Chong Wei", "Mikhail", "Sonny", "Trochowski", "Pangolin"}:
                        # Mikhail may appear in official answer of 023; question should not contain it.
                        if token.lower() in spec["question"].lower():
                            bridge_leak = True
            if bridge_leak:
                remaining.append(row)
                continue
            item = {
                "id": f"LVCOMP-V2-{next_id:03d}",
                "video_id": row["video_id"],
                "source_uids": row["source_uids"],
                "source_questions": row["source_questions"],
                "source_answers": row["source_answers"],
                "time_references": row["time_references"],
                "composition_type": spec["type"],
                "composition_schema": spec["schema"],
                "new_question": spec["question"],
                "new_answer": spec["answer"],
                "answer_derivation": spec["derivation"],
                "review_status": REVIEW_STATUS,
                "video_verified": False,
                "origin": "v1_pending_completed",
                "source_draft_id": row["id"],
                "phase": PHASE,
            }
            complete.append(item)
            used_pairs.add(pair)
            next_id += 1
        else:
            rem = dict(row)
            rem["review_status"] = DRAFT_STATUS
            rem["video_verified"] = False
            rem["phase"] = PHASE
            remaining.append(rem)
    return complete, remaining


def _answer_text(label: str) -> str:
    if ":" in label:
        return label.split(":", 1)[1].strip()
    return label.strip()


def _proper_names(text: str) -> list[str]:
    return re.findall(r"\b([A-Z][A-Za-z'’.-]+(?:\s+[A-Z][A-Za-z'’.-]+){0,2})\b", text)


def _gap_ok(a: dict, b: dict) -> bool:
    if a["interval"] is None or b["interval"] is None:
        return False
    if not _separated(a, b):
        return False
    starts = sorted([a["interval"][0], b["interval"][0]])
    if starts[1] - starts[0] < MIN_START_GAP:
        return False
    span = max(a["interval"][1], b["interval"][1]) - min(a["interval"][0], b["interval"][0])
    return span <= MAX_SPAN_SECONDS


def scan_expanded(records: list[dict], used_pairs: set[tuple[str, tuple[str, str]]], start_id: int) -> tuple[list[dict], list[dict]]:
    """Build additional complete pairs using simple semantic links beyond exact-name-only templates."""
    by_video: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        if row["interval"] is None or not _span_ok(row):
            continue
        by_video[row["video_id"]].append(row)

    complete = []
    next_id = start_id
    seen_questions: set[str] = set()

    for video_id, rows in by_video.items():
        for i, left in enumerate(rows):
            for right in rows[i + 1 :]:
                if not _gap_ok(left, right):
                    continue
                pair = (video_id, tuple(sorted([left["uid"], right["uid"]])))
                if pair in used_pairs:
                    continue
                item = _try_compose(left, right)
                if item is None:
                    item = _try_compose(right, left)
                if item is None or not item.get("complete"):
                    continue
                norm_q = " ".join(item["new_question"].lower().split())
                if norm_q in seen_questions:
                    continue
                seen_questions.add(norm_q)
                used_pairs.add(pair)
                item["id"] = f"LVCOMP-V2-{next_id:03d}"
                item["phase"] = PHASE
                item["origin"] = "v2_scan"
                item["review_status"] = REVIEW_STATUS
                item["video_verified"] = False
                complete.append(item)
                next_id += 1
    return complete, []


def _try_compose(bridge_qa: dict, target_qa: dict) -> dict | None:
    bridge = bridge_qa["answer_text"]
    names = [n for n in _proper_names(bridge) if len(n) >= 3]
    # Require the bridge answer entity to appear in the target question or answer.
    target_blob = f"{target_qa['stem']} {target_qa['answer_text']}"
    hit = None
    for name in names:
        if re.search(rf"\b{re.escape(name)}\b", target_blob):
            hit = name
            break
    if hit is None:
        # object / short NP bridge: answer is a short noun phrase appearing in the other QA
        if 3 <= len(bridge) <= 40 and bridge.lower() in target_blob.lower():
            hit = bridge
        else:
            return None

    base = {
        "video_id": bridge_qa["video_id"],
        "source_uids": [bridge_qa["uid"], target_qa["uid"]],
        "source_questions": [bridge_qa["question"], target_qa["question"]],
        "source_answers": [
            f"{bridge_qa['answer_letter']}: {bridge_qa['answer_text']}",
            f"{target_qa['answer_letter']}: {target_qa['answer_text']}",
        ],
        "time_references": [bridge_qa["time_reference"], target_qa["time_reference"]],
        "link_reason": f"shared entity {hit!r}",
    }

    bridge_stem = bridge_qa["stem"].rstrip("?")
    target_stem = target_qa["stem"].rstrip("?")
    target_answer = target_qa["answer_text"]

    # Template A: Who/What-is identity bridge into a later Wh-question that names the entity.
    if re.match(r"(?i)^(who is|what is the name of|who's)\b", bridge_stem) or re.match(r"(?i)^who\b", bridge_stem):
        referring = _referring_from_stem(bridge_stem)
        if referring and hit.lower() in target_stem.lower():
            new_q = _safe_replace(target_stem, hit, referring)
            if new_q and new_q.lower() != target_stem.lower():
                if not new_q.endswith("?"):
                    new_q += "?"
                if _is_trivial_name_swap(bridge_stem, hit, new_q, target_answer):
                    return {**base, "complete": False, "why_not_complete": "trivial name/synonym swap"}
                if not _question_ok(new_q, target_answer, hit):
                    return {**base, "complete": False, "why_not_complete": "rewrite failed quality checks"}
                schema = assign_schema(new_q, "entity_binding")
                return {
                    **base,
                    "complete": True,
                    "composition_type": "entity_binding",
                    "composition_schema": schema,
                    "new_question": new_q,
                    "new_answer": target_answer,
                    "answer_derivation": f"Replace {hit} with referring expression from UID {bridge_qa['uid']}.",
                }

    # Template B: event/action about named person → ask about the person under a role description from bridge.
    if hit.lower() in target_stem.lower() and re.search(r"(?i)^(who|which)\b", bridge_stem):
        referring = _referring_from_stem(bridge_stem)
        if referring:
            new_q = _safe_replace(target_stem, hit, referring)
            if new_q and new_q.lower() != target_stem.lower():
                if not new_q.endswith("?"):
                    new_q += "?"
                if _is_trivial_name_swap(bridge_stem, hit, new_q, target_answer):
                    return {**base, "complete": False, "why_not_complete": "trivial name/synonym swap"}
                if not _question_ok(new_q, target_answer, hit):
                    return {**base, "complete": False, "why_not_complete": "rewrite failed quality checks"}
                return {
                    **base,
                    "complete": True,
                    "composition_type": "event_binding",
                    "composition_schema": assign_schema(new_q, "event_binding"),
                    "new_question": new_q,
                    "new_answer": target_answer,
                    "answer_derivation": f"Role/event bridge {hit} from UID {bridge_qa['uid']}.",
                }

    # Linked but no reliable rewrite.
    return {
        **base,
        "complete": False,
        "why_not_complete": "shared entity found, but no reliable non-leaking rewrite",
    }


def _referring_from_stem(stem: str) -> str | None:
    text = stem.rstrip("?").strip()
    patterns = [
        (re.compile(r"(?i)^who is (.+)$"), "who"),
        (re.compile(r"(?i)^who'?s (.+)$"), "who"),
        (re.compile(r"(?i)^what is the name of (.+)$"), "who"),
        (re.compile(r"(?i)^who (.+)$"), "who"),
        (re.compile(r"(?i)^which animal (.+)$"), "that"),
        (re.compile(r"(?i)^which (.+)$"), "that"),
        (re.compile(r"(?i)^what animal (.+)$"), "that"),
    ]
    for pattern, rel in patterns:
        matched = pattern.match(text)
        if not matched:
            continue
        phrase = matched.group(1).strip()
        phrase = re.sub(r"^(the|a|an)\s+", "", phrase, flags=re.I)
        if not (3 <= len(phrase) <= 90) or " or " in phrase.lower():
            continue
        # Prefer a full relative clause for verb phrases.
        if re.match(r"(?i)^(is|are|was|were|has|have|had|does|do|did|appears|appear|serves|serve|scores|score|gets|get|makes|make|wears|wear)\b", phrase) or " " in phrase:
            if rel == "who":
                return f"the person who {phrase}" if not phrase.lower().startswith(("person", "man", "woman", "player", "guy")) else f"the {phrase}"
            return f"the animal that {phrase}" if "animal" in text.lower() else f"the one that {phrase}"
        return "the " + phrase
    return None


def _safe_replace(text: str, entity: str, replacement: str) -> str | None:
    pattern = re.compile(rf"\b{re.escape(entity)}\b", re.I)
    if not pattern.search(text):
        return None
    out = pattern.sub(replacement, text, count=1)
    out = re.sub(r"\bthe\s+the\b", "the", out, flags=re.I)
    out = re.sub(r"\bthe\s+person who person\b", "the person who", out, flags=re.I)
    return " ".join(out.split())


def _question_ok(question: str, answer: str, bridge_name: str) -> bool:
    q = " ".join(question.lower().split())
    if bridge_name and bridge_name.lower() in q:
        return False
    if re.search(r"\bthe (have|has|appears|appear|is|are|was|were)\b", q):
        return False
    if re.search(r"\ba the\b|\bthe a\b|\bthe the\b", q):
        return False
    if len(q.split()) < 6 or len(q.split()) > 42:
        return False
    if len(answer) >= 8 and answer.lower() in q:
        return False
    return True


def _scan_item_ok(row: dict) -> bool:
    q = row["new_question"]
    ql = q.lower()
    if row["video_id"] == "2zkJFv-ro4A":
        return False
    if re.search(r"(?i)\bthe animal that does\b|\bgrilled the animal\b|\bgourment\b|\bopen the dor\b", ql):
        return False
    if re.search(r"(?i)\bthe person who (appears when|raymond)\b", ql):
        return False
    if "  " in q or "the the" in ql:
        return False
    # Prefer relative-clause bridges for scanned items.
    if not re.search(r"(?i)\b(the person who|the animal that|the one that)\b", q):
        return False
    return True


def _is_trivial_name_swap(bridge_stem: str, name: str, new_q: str, answer: str) -> bool:
    # Reject Sonny/vlogger style: bridge is only "name of the vlogger" and answer still about that person under a synonym.
    if re.search(r"(?i)name of the vlogger|name of the host\b", bridge_stem):
        return True
    if answer.lower() == name.lower() and re.search(r"(?i)\b(vlogger|host|narrator)\b", new_q):
        return True
    return False


def composition_statistics(rows: list[dict]) -> list[dict]:
    by_schema: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_schema[row["composition_schema"]].append(row)
    stats = []
    for schema, items in sorted(by_schema.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        videos = sorted({item["video_id"] for item in items})
        left, right = primitives(schema)
        stats.append(
            {
                "composition_schema": schema,
                "n_questions": len(items),
                "n_videos": len(videos),
                "primitive_a": left,
                "primitive_b": right,
                "videos": " ".join(videos),
            }
        )
    return stats


def analyze_split(rows: list[dict]) -> tuple[str, dict | None]:
    """Return feasibility markdown body and optional experimental split."""
    stats = composition_statistics(rows)
    schemas = {row["composition_schema"] for row in rows}
    prim_to_schemas: dict[str, set[str]] = defaultdict(set)
    schema_videos: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        a, b = primitives(row["composition_schema"])
        prim_to_schemas[a].add(row["composition_schema"])
        prim_to_schemas[b].add(row["composition_schema"])
        schema_videos[row["composition_schema"]].add(row["video_id"])

    # Candidate unseen schemas: appear in >=2 videos, and both primitives also appear in some other schema.
    candidates = []
    for schema in sorted(schemas):
        a, b = primitives(schema)
        other_a = prim_to_schemas[a] - {schema}
        other_b = prim_to_schemas[b] - {schema}
        videos = schema_videos[schema]
        if len(videos) >= 2 and other_a and other_b:
            candidates.append((schema, sorted(videos), sorted(other_a), sorted(other_b)))

    lines = [
        "# Seen / Unseen Composition split feasibility",
        "",
        "This analysis is structural only. Candidates are not video-certified.",
        "",
        f"- Complete candidates: {len(rows)}",
        f"- Distinct composition schemas: {len(schemas)}",
        f"- Distinct videos: {len({r['video_id'] for r in rows})}",
        "",
        "## Schema coverage",
        "",
    ]
    for row in stats:
        lines.append(
            f"- `{row['composition_schema']}`: {row['n_questions']} questions across {row['n_videos']} videos"
        )

    lines.extend(["", "## Primitive reuse", ""])
    for prim, sch in sorted(prim_to_schemas.items()):
        lines.append(f"- `{prim}` appears in {len(sch)} schemas: {', '.join(sorted(sch))}")

    lines.extend(["", "## Unseen-composition candidates", ""])
    if not candidates:
        lines.append(
            "No schema simultaneously has (1) multiple videos, and (2) both primitives attested in other schemas."
        )
        lines.append("")
        lines.append("## Verdict")
        lines.append("")
        lines.append("`INSUFFICIENT_COMPOSITION_COVERAGE`")
        lines.append("")
        lines.append(
            "Main gaps: most schemas are thin (one video or a handful of items), "
            "and several primitives are locked to a single schema. "
            "Changing person names or videos alone would not create a true Unseen Composition test."
        )
        return "\n".join(lines) + "\n", None

    # Prefer the schema with the most videos for held-out test, with train videos disjoint.
    best = max(candidates, key=lambda c: (len(c[1]), -len(c[0])))
    unseen_schema, videos, _, _ = best
    # Hold out one video for unseen test items of that schema; train uses other schemas + other videos' items only if no UID/video leak.
    test_video = videos[-1]
    train_videos = set()
    test_items = []
    train_items = []
    for row in rows:
        if row["composition_schema"] == unseen_schema and row["video_id"] == test_video:
            test_items.append(row["id"])
        elif row["composition_schema"] != unseen_schema:
            # Ensure primitives of unseen schema appear in train.
            train_items.append(row["id"])
            train_videos.add(row["video_id"])
        else:
            # same schema other videos: can stay in train as Seen Composition examples
            train_items.append(row["id"])
            train_videos.add(row["video_id"])

    # Check primitive coverage in train.
    train_schemas = {r["composition_schema"] for r in rows if r["id"] in set(train_items)}
    a, b = primitives(unseen_schema)
    train_prims = set()
    for schema in train_schemas:
        train_prims.update(primitives(schema))
    leak_videos = {test_video} & train_videos
    # Video isolation for test set: test video must not appear in train.
    train_items_isolated = []
    for row in rows:
        if row["id"] in set(test_items):
            continue
        if row["video_id"] == test_video:
            continue
        train_items_isolated.append(row["id"])
    train_schemas_iso = {r["composition_schema"] for r in rows if r["id"] in set(train_items_isolated)}
    train_prims_iso = set()
    for schema in train_schemas_iso:
        train_prims_iso.update(primitives(schema))

    lines.append(f"Strongest candidate unseen schema: `{unseen_schema}`")
    lines.append(f"- Videos for that schema: {', '.join(videos)}")
    lines.append(f"- Proposed held-out test video: `{test_video}`")
    lines.append(f"- Test item count under video isolation: {len(test_items)}")
    lines.append(f"- Train item count under video isolation: {len(train_items_isolated)}")
    lines.append(f"- Primitives `{a}` / `{b}` present in isolated train: `{a in train_prims_iso}` / `{b in train_prims_iso}`")
    lines.append("")

    train_video_set = {r["video_id"] for r in rows if r["id"] in set(train_items_isolated)}
    video_leak = bool({test_video} & train_video_set)
    uid_train = {(r["video_id"], uid) for r in rows if r["id"] in set(train_items_isolated) for uid in r["source_uids"]}
    uid_test = {(r["video_id"], uid) for r in rows if r["id"] in set(test_items) for uid in r["source_uids"]}
    uid_leak = bool(uid_train & uid_test)
    multi_video_schemas = sum(1 for row in stats if int(row["n_videos"]) >= 3)
    enough = (
        len(test_items) >= 5
        and len(train_items_isolated) >= 40
        and a in train_prims_iso
        and b in train_prims_iso
        and multi_video_schemas >= 4
        and not video_leak
        and not uid_leak
    )

    lines.append("## Leak checks")
    lines.append("")
    lines.append(f"- Shared videos between isolated train/test: {video_leak}")
    lines.append(f"- Shared (video, uid) pairs: {uid_leak}")
    lines.append(f"- Schemas with >=3 videos: {multi_video_schemas}")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    split = None
    if enough:
        lines.append(
            "An experimental video-isolated split is structurally possible. "
            "It is still not video-certified and should not be treated as a formal benchmark."
        )
        split = {
            "status": "EXPERIMENTAL_ONLY",
            "note": "Not video-certified. Not a formal Seen/Unseen benchmark.",
            "unseen_schema": unseen_schema,
            "test_video": test_video,
            "train_ids": train_items_isolated,
            "test_ids": test_items,
            "video_leak": video_leak,
            "uid_leak": uid_leak,
        }
    else:
        lines.append("`INSUFFICIENT_COMPOSITION_COVERAGE`")
        lines.append("")
        reasons = []
        if len(test_items) < 5:
            reasons.append(f"held-out Unseen cell has only {len(test_items)} items (need >=5)")
        if len(train_items_isolated) < 40:
            reasons.append("train set under video isolation is too small")
        if a not in train_prims_iso or b not in train_prims_iso:
            reasons.append("one or both primitives are missing from train after video isolation")
        if multi_video_schemas < 4:
            reasons.append("too few composition schemas have multi-video support")
        if video_leak or uid_leak:
            reasons.append("train/test still share video or UID evidence")
        lines.append("Blocking issues: " + "; ".join(reasons) + ".")
        lines.append(
            "Main missing pieces: denser multi-video coverage of the same composition schemas, "
            "and Unseen cells large enough that a held-out schema is not just one or two items. "
            "Renaming people or swapping videos alone would not create true compositional generalization."
        )
    return "\n".join(lines) + "\n", split


def write_outputs(
    out_dir: Path,
    candidates: list[dict],
    pending: list[dict],
    stats: list[dict],
    feasibility: str,
    split: dict | None,
    sample_review: list[dict],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "candidates.jsonl").open("w", encoding="utf-8") as handle:
        for row in candidates:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out_dir / "candidate_pairs_pending.jsonl").open("w", encoding="utf-8") as handle:
        for row in pending:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    _csv(out_dir / "composition_statistics.csv", stats)
    _csv(out_dir / "sample_review.csv", sample_review)
    (out_dir / "split_feasibility.md").write_text(feasibility, encoding="utf-8")
    split_path = out_dir / "seen_unseen_split.json"
    if split is not None:
        split_path.write_text(json.dumps(split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif split_path.exists():
        split_path.unlink()
    videos = sorted({row["video_id"] for row in candidates})
    by_origin = Counter(row.get("origin", "?") for row in candidates)
    by_schema = Counter(row["composition_schema"] for row in candidates)
    report = "\n".join(
        [
            "# LVBench Compositional Generalization v2",
            "",
            "本轮完成抽样核验收尾、候选扩展、以及 Seen / Unseen Composition 可行性分析。未运行 RSI，未调用付费 API。",
            "",
            "## 抽样核验",
            "",
            f"- 10 道代表题写入 `sample_review.csv`。",
            f"- 结论分布：{dict(Counter(r['verdict'] for r in sample_review))}",
            "",
            "## 候选规模",
            "",
            f"- 完整候选：{len(candidates)}（目标约 100；未凑数）",
            f"- 覆盖视频：{len(videos)}",
            f"- 来源：{dict(by_origin)}",
            f"- 仍待人工改写：{len(pending)}",
            f"- 未达到 100 的主要限制：官方同视频显式共指有限；很多 pending 只能做答案替换或同义改写；自动扫描的通顺改写很少。",
            "",
            "## 组合结构",
            "",
            *[f"- `{name}`: {count}" for name, count in by_schema.most_common()],
            "",
            "## 划分",
            "",
            "见 `split_feasibility.md`。当前结论是 `INSUFFICIENT_COMPOSITION_COVERAGE`。",
            "",
            "所有完整候选仍是 `PENDING_VIDEO_REVIEW` 或 `NEEDS_VERIFICATION`，不是正式有效样本。",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")
    (out_dir / "README.md").write_text(
        """# LVBench Compositional Generalization v2

```bash
python3 tools/lvbench_comp/build_comp_qa_v2.py \\
  --metadata /home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl \\
  --clean research_audit/lvbench_compositional/qa_v1_clean/candidates.jsonl \\
  --pending research_audit/lvbench_compositional/qa_v1/candidate_pairs_pending.jsonl \\
  --sample-review research_audit/lvbench_compositional/v2/sample_review.csv \\
  --output-dir research_audit/lvbench_compositional/v2
```

测试：

```bash
python3 tools/lvbench_comp/test_build_comp_qa_v2.py
```

不覆盖 `qa_v0`、`qa_v1`、`qa_v1_clean`。媒体文件仍只在本地忽略目录。
""",
        encoding="utf-8",
    )


def _csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0].keys()) if rows else ["id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def default_sample_review() -> list[dict]:
    return [
        {
            "id": "LVCOMP-V1-012",
            "verdict": "SUPPORTED",
            "source_facts": "SUPPORTED",
            "composition_link": "SUPPORTED",
            "notes": "Prior review: hotel invitation is visible; elder identity still leans on the original name annotation.",
            "reviewer": "prior_human_pass",
        },
        {
            "id": "LVCOMP-V1-017",
            "verdict": "SUPPORTED",
            "source_facts": "SUPPORTED",
            "composition_link": "SUPPORTED",
            "notes": "Prior review: the woman in red holds the book; context frames are needed for the search event.",
            "reviewer": "prior_human_pass",
        },
        {
            "id": "LVCOMP-V1-030",
            "verdict": "UNCERTAIN",
            "source_facts": "UNCERTAIN",
            "composition_link": "UNCERTAIN",
            "notes": "Prior review: podium order / first-place identity cannot be confirmed from the available evidence alone.",
            "reviewer": "prior_human_pass",
        },
        {
            "id": "LVCOMP-V1-008",
            "verdict": "SUPPORTED",
            "source_facts": "SUPPORTED",
            "composition_link": "SUPPORTED",
            "notes": "Contact sheets: Jonathan Davidson is identified on stage; later window shows an explicit L'Oréal brand video.",
            "reviewer": "contact_sheet_pass",
        },
        {
            "id": "LVCOMP-V1-010",
            "verdict": "UNCERTAIN",
            "source_facts": "UNCERTAIN",
            "composition_link": "UNCERTAIN",
            "notes": "Bib 3217 is visible on a USA runner, but the heat-winner identity is not independently confirmed from the contact sheets alone.",
            "reviewer": "contact_sheet_pass",
        },
        {
            "id": "LVCOMP-V1-022",
            "verdict": "SUPPORTED",
            "source_facts": "SUPPORTED",
            "composition_link": "SUPPORTED",
            "notes": "LEBANON title card is on screen; later dialogue says people of Lebanon love life, matching the happy-life answer.",
            "reviewer": "contact_sheet_pass",
        },
        {
            "id": "LVCOMP-V1-029",
            "verdict": "UNCERTAIN",
            "source_facts": "UNCERTAIN",
            "composition_link": "UNCERTAIN",
            "notes": "A Liverpool player is down holding his head, but the first-goal scorer identity is not confirmed from the contact sheets alone.",
            "reviewer": "contact_sheet_pass",
        },
        {
            "id": "LVCOMP-V1-032",
            "verdict": "UNCERTAIN",
            "source_facts": "UNCERTAIN",
            "composition_link": "UNCERTAIN",
            "notes": "A boy takes a golden object from a demon, but invisibility and the S-shaped jade are not clear from the contact sheets.",
            "reviewer": "contact_sheet_pass",
        },
        {
            "id": "LVCOMP-V1-038",
            "verdict": "CONTRADICTED",
            "source_facts": "CONTRADICTED",
            "composition_link": "UNCERTAIN",
            "notes": "At ~15:06 the contact sheet shows a header into the net and a celebratory reaction, which conflicts with 'header doesn't result in a goal' / sadness.",
            "reviewer": "contact_sheet_pass",
        },
        {
            "id": "LVCOMP-V1-043",
            "verdict": "SUPPORTED",
            "source_facts": "SUPPORTED",
            "composition_link": "SUPPORTED",
            "notes": "On-screen text labels Mia as a stripper and Austin as dumping his girlfriend for a stripper.",
            "reviewer": "contact_sheet_pass",
        },
    ]


def build(metadata: Path, clean_path: Path, pending_path: Path, sample_path: Path | None) -> tuple[list[dict], list[dict], list[dict], str, dict | None, list[dict]]:
    clean = from_clean(_load_jsonl(clean_path))
    used = {(row["video_id"], tuple(sorted(row["source_uids"]))) for row in clean}
    used_questions = {" ".join(row["new_question"].lower().split()) for row in clean}
    pending_in = _load_jsonl(pending_path)
    completed, pending_left = complete_pending(pending_in, used)
    # drop completed questions that collide with clean wording
    filtered_completed = []
    for row in completed:
        norm = " ".join(row["new_question"].lower().split())
        if norm in used_questions:
            # put back conceptually as pending? keep skipped out of complete set
            continue
        used_questions.add(norm)
        filtered_completed.append(row)

    records = load_qas(metadata)
    scanned, _ = scan_expanded(records, used, start_id=200)
    scanned_filtered = []
    for row in scanned:
        norm = " ".join(row["new_question"].lower().split())
        if norm in used_questions:
            continue
        if not _question_ok(row["new_question"], row["new_answer"], ""):
            continue
        if not _scan_item_ok(row):
            continue
        used_questions.add(norm)
        scanned_filtered.append(row)

    candidates = clean + filtered_completed + scanned_filtered
    candidates.sort(key=lambda row: row["id"])
    pending_all = pending_left
    stats = composition_statistics(candidates)
    feasibility, split = analyze_split(candidates)
    if sample_path and sample_path.is_file():
        sample_review = list(csv.DictReader(sample_path.open(encoding="utf-8")))
    else:
        sample_review = default_sample_review()
    return candidates, pending_all, stats, feasibility, split, sample_review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build LVBench compositional QA v2 artifacts.")
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--clean", type=Path, required=True)
    parser.add_argument("--pending", type=Path, required=True)
    parser.add_argument("--sample-review", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    candidates, pending, stats, feasibility, split, sample_review = build(
        args.metadata, args.clean, args.pending, args.sample_review
    )
    write_outputs(args.output_dir, candidates, pending, stats, feasibility, split, sample_review)
    print(
        json.dumps(
            {
                "complete": len(candidates),
                "pending": len(pending),
                "videos": len({row["video_id"] for row in candidates}),
                "split": None if split is None else split.get("status"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
