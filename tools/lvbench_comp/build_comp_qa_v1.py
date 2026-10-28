#!/usr/bin/env python3
"""LVBench compositional QA v1.

v0 kept a pair whenever a proper name occurred in another official string.
Many of those items only rewrote the answer. v1 keeps a pair only when the
annotations support a new question: the bridge entity is hidden, and the
question is not the original wording.

Pairs with an explicit annotation link but no reliable question template go
to candidate_pairs_pending.jsonl as NEEDS_HUMAN_DRAFT. They are not counted
as complete compositional questions.
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

from tools.lvbench_comp.build_comp_qa import (  # noqa: E402
    _answer_label,
    _contains_name,
    _is_name,
    _polish,
    _separated,
    _span_ok,
    is_identifier,
    load_qas,
    referring_expression,
)
from tools.lvbench_comp.build_comp_qa import (  # noqa: E402
    AFTER,
    COLOR,
    HOLDS,
    SEARCH,
    SEEKER,
)


PHASE = "lvbench-compositional-qa-v1"
REVIEW_STATUS = "PENDING_REVIEW"
DRAFT_STATUS = "NEEDS_HUMAN_DRAFT"
COMPOSITION_TYPES = (
    "entity_binding",
    "object_binding",
    "event_binding",
    "attribute_binding",
)
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
    "video_verified",
    "derived_from_v0",
)
COLORS = {
    "red", "blue", "green", "black", "white", "yellow", "orange", "purple",
    "pink", "brown", "grey", "gray", "gold", "silver", "golden",
}
NUMBERS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "none", "both", "yes", "no", "left", "right",
}
GENERIC = {
    "the man", "the woman", "the person", "the vlogger", "the host", "the narrator",
    "a man", "a woman", "the girl", "the boy", "he", "she", "they",
}
RELATIONS = (
    "sister", "brother", "coach", "girlfriend", "boyfriend", "roommate",
    "wife", "husband", "friend", "father", "mother", "daughter", "son",
)
BARE_VERBS = (
    "go", "come", "choose", "score", "hold", "wear", "take", "win", "leave",
    "save", "make", "pick", "see", "get", "serve",
)
IRREGULAR = {
    "see": "sees", "do": "does", "go": "goes", "have": "has", "get": "gets",
    "take": "takes", "leave": "leaves", "make": "makes", "choose": "chooses",
    "save": "saves", "win": "wins", "come": "comes", "hold": "holds",
    "wear": "wears", "score": "scores", "pick": "picks", "serve": "serves",
}
WHO_DOES = re.compile(r"(?i)^who does (.+?) (\w+)(.*)$")
WHOS_THAT = re.compile(r"(?i)^who'?s that (.+)$")
WHO_IS = re.compile(r"(?i)^who is (.+)$")
WHICH_DOES = re.compile(r"(?i)^which (\w+) does (.+)$")
WHICH_DO = re.compile(r"(?i)^which (\w+) do (.+)$")
WHICH_BE = re.compile(r"(?i)^which (\w+) (was|is|were|are) (.+)$")
WHICH_COUNTRY = re.compile(r"(?i)^which country's (.+)$")
WHICH_VERB = re.compile(r"(?i)^which (\w+) ([a-z]+s) (.+)$")
WHO_REST = re.compile(r"(?i)^who (?!is\b|are\b|was\b|were\b)(.+)$")
WHAT_DOES = re.compile(r"(?i)^what does (.+?) (do|claim|say|wear|want)\b(.*)$")
WHAT_HAPPENS = re.compile(r"(?i)^what happens (.+)$")
POSSESSIVE_ANSWER = re.compile(
    r"(?i)^(?:she|he|they)(?:'s| is) ([A-Z][\w'’. -]+?)'s (" + "|".join(RELATIONS) + r")$"
)
POSSESSIVE_ONLY = re.compile(
    r"^([A-Z][\w'’. -]+?)'s (" + "|".join(RELATIONS) + r")$"
)
ORDINALS = ("First", "Second", "Third", "Fourth", "Fifth")


def _clean(stem: str) -> str:
    return " ".join(stem.strip().rstrip("?").split())


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _verb3(verb: str) -> str:
    base = verb.lower()
    if base in IRREGULAR:
        return IRREGULAR[base]
    if re.search(r"(?:s|x|ch|sh)$", base):
        return base + "es"
    if base.endswith("y") and len(base) > 2 and base[-2] not in "aeiou":
        return base[:-1] + "ies"
    if base.endswith("e"):
        return base + "s"
    return base + "s"


def _conjugate_once(text: str) -> str:
    pattern = r"\b(" + "|".join(BARE_VERBS) + r")\b"

    def replace(match: re.Match[str]) -> str:
        return _verb3(match.group(1))

    return re.sub(pattern, replace, text, count=1, flags=re.I)


def _distinctive(answer: str) -> bool:
    text = " ".join(answer.split()).rstrip(".")
    lowered = text.lower()
    if lowered in COLORS or lowered in NUMBERS or lowered in GENERIC:
        return False
    if re.fullmatch(r"\d+", text) or len(text) < 3 or len(text.split()) > 6:
        return False
    if " because " in lowered or " and then " in lowered:
        return False
    if lowered.startswith(("he ", "she ", "they ", "it ", "his ", "her ", "he's ", "she's ")):
        return False
    if _is_name(text):
        return True
    return len(text.split()) >= 2 and (
        text[0].isupper() or lowered.startswith(("the ", "a ", "an "))
    )


def _trivial(phrase: str) -> bool:
    return phrase.lower().strip() in GENERIC


def _visual_description(phrase: str) -> bool:
    lowered = phrase.lower()
    return any(token in lowered for token in ("appearing", "on the screen", "at 0", "in the video wearing"))


def bridge_np(stem: str) -> str | None:
    text = _clean(stem)
    if is_identifier(text):
        phrase = referring_expression(text)
        if phrase and not _trivial(phrase):
            return phrase
    if WHOS_THAT.match(text) or WHO_IS.match(text):
        return None
    matched = WHO_DOES.match(text)
    if matched:
        return f"the person {matched.group(1)} {_verb3(matched.group(2))}{matched.group(3)}".strip()
    matched = WHICH_COUNTRY.match(text)
    if matched:
        return f"the country whose {matched.group(1)}".strip()
    matched = WHICH_DOES.match(text)
    if matched:
        return f"the {matched.group(1).lower()} {_conjugate_once(matched.group(2))}".strip()
    matched = WHICH_DO.match(text)
    if matched:
        return f"the {matched.group(1).lower()} {matched.group(2)}".strip()
    matched = WHICH_BE.match(text)
    if matched:
        return f"the {matched.group(1).lower()} that {matched.group(2)} {matched.group(3)}".strip()
    matched = WHICH_VERB.match(text)
    if matched and matched.group(2).lower() not in {"is", "was", "has"}:
        return f"the {matched.group(1).lower()} that {matched.group(2).lower()} {matched.group(3)}".strip()
    matched = WHO_REST.match(text)
    if (
        matched
        and matched.group(1)[:1].islower()
        and " and " not in matched.group(1).lower()
        and len(matched.group(1).split()) <= 12
    ):
        return f"the person who {matched.group(1)}".strip()
    return None


def event_np(stem: str) -> str | None:
    phrase = bridge_np(stem)
    if phrase:
        return phrase
    text = _clean(stem)
    matched = re.match(r"(?i)^who (?!is\b|are\b|was\b|were\b|'s\b)(.+)$", text)
    if matched and len(matched.group(1).split()) <= 12:
        return "the person who " + matched.group(1)
    return None


def _gap_ok(left: dict, right: dict) -> bool:
    if not _span_ok(left) or not _span_ok(right) or not _separated(left, right):
        return False
    return abs(left["interval"][0] - right["interval"][0]) >= 10


def _find_span(text: str, entity: str) -> re.Match[str] | None:
    flags = re.I if len(entity.split()) > 1 else 0
    return re.search(r"\b" + re.escape(entity) + r"\b", text, flags)


def _compound_break(text: str, entity: str) -> bool:
    matched = _find_span(text, entity)
    if matched is None:
        return True
    before = text[: matched.start()]
    after = text[matched.end() :]
    if re.match(r"\s+[A-Z]", after):
        return True
    if re.search(r"[A-Z][\w'’.-]+\s+$", before):
        return True
    return False


def _substitute(text: str, entity: str, phrase: str) -> str | None:
    matched = _find_span(text, entity)
    if matched is None:
        return _scrub_tokens(" ".join(text.split()), entity, phrase)
    if _compound_break(text, entity):
        return None
    start = matched.start()
    determiner = re.search(r"(?i)\b(?:the|a|an)\s+$", text[:start])
    if determiner and phrase.lower().startswith(("the ", "a ", "an ")):
        start = determiner.start()
    replaced = " ".join((text[:start] + phrase + text[matched.end() :]).split())
    replaced = _scrub_tokens(replaced, entity, phrase)
    if replaced is None or _find_span(replaced, entity):
        return None
    return replaced


def _scrub_tokens(text: str, entity: str, phrase: str) -> str | None:
    for token in entity.split():
        if len(token) < 4 or not token[0].isupper():
            continue
        if not _find_span(text, token):
            continue
        text = re.sub(
            r"\b" + re.escape(token) + r"\b",
            phrase,
            text,
            count=1,
        )
        if _find_span(text, token):
            return None
    return " ".join(text.split())


def _changed(question: str, *stems: str) -> bool:
    current = _norm(question)
    return bool(current) and all(current != _norm(stem) for stem in stems)


def _circular(answer: str, phrase: str, question: str) -> bool:
    if phrase.lower() not in question.lower():
        return False
    simplified = re.sub(r"^(he|she|they|it)\s+", "", answer.lower()).strip(" .")
    return bool(simplified) and simplified in phrase.lower()


def _usable(question: str, answer: str, hidden: str, phrase: str, *stems: str) -> bool:
    if not question or not answer or _trivial(phrase):
        return False
    if len(phrase.split()) > 24 or len(question) > 280:
        return False
    if "?" in question[:-1] or not _changed(question, *stems):
        return False
    if re.search(r"\bthe the\b", question, re.I):
        return False
    if re.search(r"\b(?:two|three|four|five)\s+the\s+", question, re.I):
        return False
    if _find_span(question, hidden) or _find_span(answer, hidden):
        return False
    if phrase.lower() not in question.lower() and phrase.lower() not in answer.lower():
        return False
    if _circular(answer, phrase, question):
        return False
    return True


def _pack(
    kind: str,
    bridge: dict,
    other: dict,
    question: str,
    answer: str,
    derivation: str,
    score: int,
) -> dict:
    ordered = sorted((bridge, other), key=lambda item: (item["interval"][0], item["uid"]))
    return {
        "video_id": bridge["video_id"],
        "source_uids": [item["uid"] for item in ordered],
        "source_questions": [item["question"] for item in ordered],
        "source_answers": [_answer_label(item) for item in ordered],
        "time_references": [item["time_reference"] for item in ordered],
        "composition_type": kind,
        "new_question": _polish(question.strip().rstrip(".")),
        "new_answer": " ".join(answer.split()),
        "answer_derivation": derivation,
        "review_status": REVIEW_STATUS,
        "video_verified": False,
        "derived_from_v0": None,
        "_score": score,
        "_gap": abs(bridge["interval"][0] - other["interval"][0]),
        "_pair": (bridge["video_id"], tuple(sorted((bridge["uid"], other["uid"])))),
    }


def _note(bridge: dict, other: dict, detail: str) -> str:
    return (
        f"UID {bridge['uid']} ({bridge['time_reference']}) official option "
        f"{bridge['answer_letter']} is {bridge['answer_text']!r}. "
        f"UID {other['uid']} ({other['time_reference']}) official option "
        f"{other['answer_letter']} is {other['answer_text']!r}. "
        f"{detail} The wording uses those annotation strings only. "
        "It does not verify the video, and it is not a certified benchmark item."
    )


def _entity_key(text: str) -> str:
    return " ".join(text.split()).rstrip(".")


def _scanned_pairs(grouped: dict[str, list[dict]]) -> int:
    total = 0
    for items in grouped.values():
        total += len(items) * (len(items) - 1) // 2
    return total


def _preliminary(grouped: dict[str, list[dict]]) -> dict[tuple, str]:
    found: dict[tuple, str] = {}
    for items in grouped.values():
        for left in items:
            entity = _entity_key(left["answer_text"])
            if not _distinctive(entity):
                continue
            for right in items:
                if left["uid"] >= right["uid"] or not _gap_ok(left, right):
                    continue
                key = (left["video_id"], tuple(sorted((left["uid"], right["uid"]))))
                other = _entity_key(right["answer_text"])
                if _distinctive(other) and other.lower() == entity.lower():
                    found[key] = "both official answers are the same distinctive entity"
                    continue
                if _find_span(right["stem"], entity) or _find_span(right["answer_text"], entity):
                    found[key] = "one official answer is a distinctive entity named in the other QA"
        for left in items:
            searched = SEARCH.search(left["answer_text"])
            if not searched:
                continue
            for right in items:
                held = HOLDS.search(right["answer_text"])
                if not held or left["uid"] == right["uid"] or not _gap_ok(left, right):
                    continue
                if held.group(3).lower() == searched.group(2).lower() and held.group(2).lower() == searched.group(1).lower():
                    key = (left["video_id"], tuple(sorted((left["uid"], right["uid"]))))
                    found[key] = "one answer searches for a possessed object and the other says who has it"
    return found


def _object_candidates(grouped: dict[str, list[dict]]) -> list[dict]:
    found = []
    for items in grouped.values():
        for seek in items:
            searched = SEARCH.search(seek["answer_text"])
            seeker = SEEKER.match(_clean(seek["stem"]))
            event = AFTER.search(_clean(seek["stem"]))
            if not searched or not seeker or not event:
                continue
            for holder in items:
                held = HOLDS.search(holder["answer_text"])
                meeting = AFTER.search(_clean(holder["stem"]))
                if not held or not meeting or not _gap_ok(seek, holder):
                    continue
                if held.group(3).lower() != searched.group(2).lower():
                    continue
                if held.group(2).lower() != searched.group(1).lower():
                    continue
                if holder["interval"][0] + 1 < seek["interval"][0]:
                    continue
                noun = searched.group(2)
                specific = re.search(r"\bthe woman in red\b", holder["stem"], re.I)
                answer = specific.group(0).lower() if specific else held.group(1).lower()
                clause = meeting.group(0)
                question = (
                    f"{clause[0].upper()}{clause[1:]}, who has the item "
                    f"{seeker.group(1)} searched for {event.group(0)}?"
                )
                if re.search(r"\b" + re.escape(noun) + r"\b", question, re.I):
                    continue
                if re.search(r"\bpick", question, re.I) or re.search(r"\bpick", answer, re.I):
                    continue
                found.append(
                    _pack(
                        "object_binding",
                        seek,
                        holder,
                        question,
                        answer,
                        _note(
                            seek,
                            holder,
                            f"Both answers use the possessed object {noun!r}, but the new question "
                            "hides that noun. The holder wording is copied from the official "
                            "question or answer. The annotation supports possession only.",
                        ),
                        100,
                    )
                )
    return found


def _role_candidates(grouped: dict[str, list[dict]]) -> list[dict]:
    found = []
    for items in grouped.values():
        groups: dict[str, list[dict]] = defaultdict(list)
        for item in items:
            entity = _entity_key(item["answer_text"])
            if _span_ok(item) and _is_name(entity) and entity.lower() not in COLORS:
                groups[entity].append(item)
        for entity, members in groups.items():
            identities = [item for item in members if is_identifier(_clean(item["stem"])) and bridge_np(item["stem"])]
            events = [item for item in members if event_np(item["stem"]) and not is_identifier(_clean(item["stem"]))]
            for identity in identities:
                role = bridge_np(identity["stem"])
                if not role:
                    continue
                for event in events:
                    if not _gap_ok(identity, event):
                        continue
                    event_phrase = event_np(event["stem"])
                    if not event_phrase:
                        continue
                    if _visual_description(role):
                        question = f"Who is {event_phrase}?"
                    else:
                        question = f"What is the role of {event_phrase}?"
                    if not _usable(question, role, entity, event_phrase, identity["stem"], event["stem"]):
                        continue
                    found.append(
                        _pack(
                            "attribute_binding",
                            identity,
                            event,
                            question,
                            role,
                            _note(
                                identity,
                                event,
                                "The two official answers are the same name. "
                                "The new question asks for the identity description instead of repeating that name.",
                            ),
                            90,
                        )
                    )
    return found


def _whose_candidates(grouped: dict[str, list[dict]]) -> list[dict]:
    found = []
    names: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for items in grouped.values():
        for item in items:
            entity = _entity_key(item["answer_text"])
            if _span_ok(item) and _is_name(entity) and entity.lower() not in COLORS and bridge_np(item["stem"]):
                names[(item["video_id"], entity)].append(item)
    for items in grouped.values():
        for other in items:
            relation = _relation_in_answer(other["answer_text"])
            if relation is None or not _span_ok(other):
                continue
            person, role = relation
            bridges = names.get((other["video_id"], person), [])
            subject = _whose_subject(other["stem"])
            if subject is None:
                continue
            for bridge in bridges:
                if not _gap_ok(bridge, other):
                    continue
                phrase = bridge_np(bridge["stem"])
                if not phrase:
                    continue
                question = f"Whose {role} is {subject}?"
                if not _usable(question, phrase, person, phrase, bridge["stem"], other["stem"]):
                    continue
                found.append(
                    _pack(
                        "attribute_binding",
                        bridge,
                        other,
                        question,
                        phrase,
                        _note(
                            bridge,
                            other,
                            f"The official answer states the {role} relation. "
                            "The new question asks whose relation it is, using the other QA's description.",
                        ),
                        88 if is_identifier(_clean(bridge["stem"])) else 85,
                    )
                )
    return found


def _relation_in_answer(answer: str) -> tuple[str, str] | None:
    text = " ".join(answer.split())
    matched = POSSESSIVE_ANSWER.match(text) or POSSESSIVE_ONLY.match(text)
    if not matched:
        return None
    return matched.group(1).strip(), matched.group(2).lower()


def _whose_subject(stem: str) -> str | None:
    text = _clean(stem)
    matched = WHOS_THAT.match(text)
    if matched:
        return "that " + matched.group(1)
    matched = re.match(r"(?i)^what can we know about (.+)$", text)
    if matched:
        return matched.group(1)
    return None


def _stem_candidates(grouped: dict[str, list[dict]]) -> list[dict]:
    found = []
    for items in grouped.values():
        for bridge in items:
            entity = _entity_key(bridge["answer_text"])
            phrase = bridge_np(bridge["stem"]) if _distinctive(entity) else None
            if not phrase or entity.lower() in COLORS:
                continue
            for other in items:
                if not _gap_ok(bridge, other) or not _find_span(other["stem"], entity):
                    continue
                if _compound_break(other["stem"], entity):
                    continue
                if re.match(r"(?i)^the person who (have|get|save|do|did)\b", phrase):
                    continue
                question = _substitute(other["stem"], entity, phrase)
                answer = _substitute(other["answer_text"], entity, phrase)
                if question is None or answer is None or not _usable(
                    question, answer, entity, phrase, bridge["stem"], other["stem"]
                ):
                    continue
                kind = "entity_binding" if is_identifier(_clean(bridge["stem"])) else "event_binding"
                found.append(
                    _pack(
                        kind,
                        bridge,
                        other,
                        question,
                        answer,
                        _note(
                            bridge,
                            other,
                            f"The new question replaces {entity!r} with {phrase!r} from the other official QA.",
                        ),
                        80 if kind == "entity_binding" else 70,
                    )
                )
    return found


def _subject_rewrite_candidates(grouped: dict[str, list[dict]]) -> list[dict]:
    found = []
    for items in grouped.values():
        for bridge in items:
            entity = _entity_key(bridge["answer_text"])
            phrase = bridge_np(bridge["stem"]) if _is_name(entity) and entity.lower() not in COLORS else None
            if not phrase:
                continue
            for other in items:
                if not _gap_ok(bridge, other) or _find_span(other["stem"], entity):
                    continue
                if not other["answer_text"].startswith(entity + " "):
                    continue
                question = _rewrite_subject(other["stem"], phrase)
                if question is None:
                    continue
                answer = other["answer_text"][len(entity) :].strip()
                if answer and answer[0].islower():
                    answer = "She " + answer if answer.split()[0] in {"says", "quarrels", "fights"} else answer
                answer = _substitute(other["answer_text"], entity, "She") or answer
                if not _usable(question, answer, entity, phrase, bridge["stem"], other["stem"]):
                    continue
                found.append(
                    _pack(
                        "event_binding",
                        bridge,
                        other,
                        question,
                        answer,
                        _note(
                            bridge,
                            other,
                            "The later answer begins with the earlier name, so the new question "
                            "asks what that described person does.",
                        ),
                        65,
                    )
                )
    return found


def _rewrite_subject(stem: str, phrase: str) -> str | None:
    text = _clean(stem)
    matched = WHAT_DOES.match(text)
    if matched:
        return f"What does {phrase} {matched.group(2)}{matched.group(3)}?"
    matched = WHAT_HAPPENS.match(text)
    if matched:
        return f"What does {phrase} do {matched.group(1)}?"
    return None


def _podium_candidates(grouped: dict[str, list[dict]]) -> list[dict]:
    found = []
    for items in grouped.values():
        for bridge in items:
            entity = _entity_key(bridge["answer_text"])
            phrase = bridge_np(bridge["stem"]) if _is_name(entity) and entity.lower() not in COLORS else None
            if not phrase:
                continue
            for other in items:
                if not _gap_ok(bridge, other):
                    continue
                if not re.match(r"(?i)^in what order", _clean(other["stem"])):
                    continue
                names = [part.strip() for part in other["answer_text"].split(",")]
                if entity not in names or len(names) < 2 or len(names) > len(ORDINALS):
                    continue
                place = ORDINALS[names.index(entity)]
                question = (
                    f"From front to back, which place does {phrase} occupy "
                    "when the three athletes walk to the podium?"
                )
                if not _usable(question, place, entity, phrase, bridge["stem"], other["stem"]):
                    continue
                found.append(
                    _pack(
                        "event_binding",
                        bridge,
                        other,
                        question,
                        place,
                        _note(
                            bridge,
                            other,
                            "The place word is the position of that name in the official ordered answer.",
                        ),
                        60,
                    )
                )
    return found


def _color_event_candidates(grouped: dict[str, list[dict]]) -> list[dict]:
    found = []
    for items in grouped.values():
        for earlier in items:
            matched = COLOR.match(_clean(earlier["stem"]))
            if not matched or not _span_ok(earlier):
                continue
            name = matched.group(1).strip()
            if not _is_name(name) or name.lower() in COLORS:
                continue
            if _contains_name(earlier["answer_text"], name) or len(earlier["answer_text"].split()) > 3:
                continue
            best = None
            for later in items:
                if later["uid"] == earlier["uid"] or not _span_ok(later):
                    continue
                if not _contains_name(later["stem"], name):
                    continue
                if later["interval"][0] < earlier["interval"][1] + 30:
                    continue
                phrase = f"the person wearing {earlier['answer_text']} {matched.group(2)}".strip()
                question = _substitute(later["stem"], name, phrase)
                answer = _substitute(later["answer_text"], name, phrase) or later["answer_text"]
                if question is None or not _usable(
                    question, answer, name, phrase, earlier["stem"], later["stem"]
                ):
                    continue
                candidate = _pack(
                    "event_binding",
                    earlier,
                    later,
                    question,
                    answer,
                    _note(
                        earlier,
                        later,
                        "The earlier official answer is the clothing color. "
                        "The later question is rewritten so it no longer names the person.",
                    ),
                    55,
                )
                gap = later["interval"][0] - earlier["interval"][1]
                if best is None or gap > best["_gap"]:
                    candidate["_gap"] = gap
                    best = candidate
            if best:
                found.append(best)
    return found


def _same_event_candidates(grouped: dict[str, list[dict]]) -> list[dict]:
    found = []
    for items in grouped.values():
        groups: dict[str, list[dict]] = defaultdict(list)
        for item in items:
            entity = _entity_key(item["answer_text"])
            if (
                _span_ok(item)
                and _is_name(entity)
                and entity.lower() not in COLORS
                and bridge_np(item["stem"])
                and not is_identifier(_clean(item["stem"]))
            ):
                groups[entity].append(item)
        for entity, members in groups.items():
            for index, left in enumerate(members):
                for right in members[index + 1 :]:
                    if not _gap_ok(left, right):
                        continue
                    if _find_span(left["stem"], entity) or _find_span(right["stem"], entity):
                        continue
                    left_phrase = bridge_np(left["stem"])
                    right_phrase = bridge_np(right["stem"])
                    if not left_phrase or not right_phrase:
                        continue
                    earlier, later = sorted((left, right), key=lambda item: item["interval"][0])
                    earlier_phrase = bridge_np(earlier["stem"])
                    later_phrase = bridge_np(later["stem"])
                    question = f"Is {earlier_phrase} the same as {later_phrase}?"
                    if not _usable(question, "Yes", entity, earlier_phrase, left["stem"], right["stem"]):
                        continue
                    if later_phrase.lower() not in question.lower():
                        continue
                    found.append(
                        _pack(
                            "event_binding",
                            earlier,
                            later,
                            question,
                            "Yes",
                            _note(
                                earlier,
                                later,
                                "Both official answers are this name, and neither question already states it. "
                                "The new question asks whether the two described events are the same person.",
                            ),
                            40,
                        )
                    )
    return found


def _select(candidates: list[dict]) -> list[dict]:
    best: dict[tuple, dict] = {}
    for candidate in candidates:
        key = candidate["_pair"]
        current = best.get(key)
        rank = (candidate["_score"], -len(candidate["new_question"]), candidate["_gap"])
        if current is None or rank > (
            current["_score"],
            -len(current["new_question"]),
            current["_gap"],
        ):
            best[key] = candidate
    by_question: dict[tuple, dict] = {}
    for candidate in best.values():
        key = (candidate["video_id"], _norm(candidate["new_question"]))
        current = by_question.get(key)
        if current is None or candidate["_score"] > current["_score"]:
            by_question[key] = candidate
    chosen = list(by_question.values())
    chosen.sort(
        key=lambda item: (
            COMPOSITION_TYPES.index(item["composition_type"]),
            item["video_id"],
            item["source_uids"],
        )
    )
    for index, candidate in enumerate(chosen, 1):
        candidate["id"] = f"LVCOMP-V1-{index:03d}"
        candidate.pop("_score", None)
        candidate.pop("_gap", None)
        candidate.pop("_pair", None)
    return chosen


def _pending_records(
    records: list[dict],
    preliminary: dict[tuple, str],
    chosen: list[dict],
) -> list[dict]:
    index = {(item["video_id"], item["uid"]): item for item in records}
    done = {(item["video_id"], tuple(sorted(item["source_uids"]))) for item in chosen}
    rows = []
    for key, reason in sorted(preliminary.items()):
        if key in done:
            continue
        video_id, uids = key
        pair = [index[(video_id, uid)] for uid in uids]
        rows.append(
            {
                "id": f"LVCOMP-V1-DRAFT-{len(rows) + 1:03d}",
                "video_id": video_id,
                "source_uids": [item["uid"] for item in pair],
                "source_questions": [item["question"] for item in pair],
                "source_answers": [_answer_label(item) for item in pair],
                "time_references": [item["time_reference"] for item in pair],
                "link_reason": reason,
                "why_not_complete": (
                    "The annotations share an entity, but no template produced a new question "
                    "that hides that entity and stays inside the official wording."
                ),
                "review_status": DRAFT_STATUS,
                "video_verified": False,
            }
        )
    return rows


def _attach_v0(chosen: list[dict], v0_rows: list[dict]) -> None:
    by_pair = {
        (item["video_id"], tuple(sorted(str(uid) for uid in item["source_uids"]))): item["id"]
        for item in v0_rows
    }
    for candidate in chosen:
        candidate["derived_from_v0"] = by_pair.get(
            (candidate["video_id"], tuple(sorted(candidate["source_uids"])))
        )


def review_v0(v0_rows: list[dict], chosen: list[dict]) -> list[dict]:
    by_pair = {
        (item["video_id"], tuple(item["source_uids"])): item
        for item in chosen
    }
    reviews = []
    for old in v0_rows:
        current = None
        for candidate in chosen:
            if candidate["video_id"] == old["video_id"] and set(candidate["source_uids"]) == set(map(str, old["source_uids"])):
                current = candidate
                break
        stems = []
        for question in old["source_questions"]:
            stems.append(_norm(question.split("(A)")[0]))
        same_question = current is not None and _norm(old["new_question"]) == _norm(current["new_question"])
        same_answer = current is not None and _norm(old["new_answer"]) == _norm(current["new_answer"])
        answer_only = old.get("substitution_site") == "answer" or _norm(old["new_question"]) in stems
        trivial = "the vlogger" in old["new_question"].lower() or "the vlogger" in old["new_answer"].lower()
        if current is None and trivial:
            decision, reason = (
                "deleted",
                "Sonny and the vlogger are an obvious synonym, and the item does not add an event or attribute.",
            )
        elif current is None and answer_only:
            decision, reason = (
                "deleted",
                "v0 only changed the answer. No reverse wording stayed inside the annotations.",
            )
        elif current is None:
            decision, reason = (
                "deleted",
                "The pair repeats another bridge or the generated wording was not reliable.",
            )
        elif same_question and same_answer:
            decision, reason = (
                "kept",
                "The v0 question already hides the bridge entity and remains supported.",
            )
        elif answer_only:
            decision, reason = (
                "regenerated",
                "v0 left the original question in place. v1 asks the relation in the other direction.",
            )
        else:
            decision, reason = (
                "modified",
                "The same source pair is kept, with the question or answer rewritten so the bridge is not given away.",
            )
        reviews.append(
            {
                "v0_id": old["id"],
                "video_id": old["video_id"],
                "source_uids": " ".join(str(uid) for uid in old["source_uids"]),
                "v0_question": old["new_question"],
                "v0_answer": old["new_answer"],
                "decision": decision,
                "v1_id": "" if current is None else current["id"],
                "v1_question": "" if current is None else current["new_question"],
                "v1_answer": "" if current is None else current["new_answer"],
                "reason": reason,
            }
        )
    return reviews


def build_v1(records: list[dict], v0_rows: list[dict] | None = None) -> tuple[list[dict], list[dict], dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["video_id"]].append(record)
    preliminary = _preliminary(grouped)
    pool: list[dict] = []
    pool.extend(_object_candidates(grouped))
    pool.extend(_role_candidates(grouped))
    pool.extend(_whose_candidates(grouped))
    pool.extend(_stem_candidates(grouped))
    pool.extend(_subject_rewrite_candidates(grouped))
    pool.extend(_podium_candidates(grouped))
    pool.extend(_color_event_candidates(grouped))
    pool.extend(_same_event_candidates(grouped))
    chosen = _select(pool)
    if v0_rows:
        _attach_v0(chosen, v0_rows)
    pending = _pending_records(records, preliminary, chosen)
    v0_pairs = set()
    if v0_rows:
        v0_pairs = {
            (item["video_id"], tuple(sorted(str(uid) for uid in item["source_uids"])))
            for item in v0_rows
        }
    new_pairs = [
        item
        for item in chosen
        if (item["video_id"], tuple(sorted(item["source_uids"]))) not in v0_pairs
    ]
    stats = {
        "phase": PHASE,
        "official_qa": len(records),
        "official_videos": len(grouped),
        "scanned_same_video_pairs": _scanned_pairs(grouped),
        "preliminary_pairs": len(preliminary),
        "complete_candidates": len(chosen),
        "needs_human_draft": len(pending),
        "videos": len({item["video_id"] for item in chosen}),
        "by_type": {kind: sum(item["composition_type"] == kind for item in chosen) for kind in COMPOSITION_TYPES},
        "new_source_pairs_vs_v0": len(new_pairs),
        "review_status": REVIEW_STATUS,
        "video_verified": False,
    }
    return chosen, pending, stats


def validate_candidate(candidate: dict, records: list[dict] | None = None) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in candidate:
            errors.append(f"missing {field}")
        elif field != "derived_from_v0" and candidate[field] in ("", None, [], {}):
            errors.append(f"missing {field}")
    if candidate.get("review_status") != REVIEW_STATUS:
        errors.append("review_status")
    if candidate.get("video_verified") is not False:
        errors.append("video_verified")
    if candidate.get("composition_type") not in COMPOSITION_TYPES:
        errors.append("composition_type")
    uids = candidate.get("source_uids") or []
    if len(uids) < 2 or len(set(uids)) != len(uids):
        errors.append("source_uids")
    for key in ("source_questions", "source_answers", "time_references"):
        if len(candidate.get(key) or []) != len(uids):
            errors.append(key)
    if records is not None and not errors:
        index = {(item["video_id"], item["uid"]): item for item in records}
        stems = []
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
            stems.append(item["stem"])
            if item["question"] != question or item["time_reference"] != reference:
                errors.append(f"source mismatch {uid}")
            if not label.startswith(item["answer_letter"] + ":"):
                errors.append(f"answer letter {uid}")
            if item["answer_text"] not in label:
                errors.append(f"answer text {uid}")
        if stems and not _changed(candidate.get("new_question", ""), *stems):
            errors.append("question unchanged")
    return errors


def _load_v0(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_outputs(
    chosen: list[dict],
    pending: list[dict],
    stats: dict,
    reviews: list[dict],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "candidates.jsonl").open("w", encoding="utf-8") as handle:
        for candidate in chosen:
            handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
    with (output_dir / "candidate_pairs_pending.jsonl").open("w", encoding="utf-8") as handle:
        for row in pending:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    fields = list(REQUIRED_FIELDS)
    with (output_dir / "candidates.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for candidate in chosen:
            row = dict(candidate)
            for key in ("source_uids", "source_questions", "source_answers", "time_references"):
                row[key] = " || ".join(row[key])
            writer.writerow(row)
    review_fields = [
        "v0_id", "video_id", "source_uids", "v0_question", "v0_answer",
        "decision", "v1_id", "v1_question", "v1_answer", "reason",
    ]
    with (output_dir / "v0_to_v1_review.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=review_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(reviews)
    (output_dir / "stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    (output_dir / "REPORT.md").write_text(_report(stats, chosen, reviews), encoding="utf-8")
    (output_dir / "README.md").write_text(README, encoding="utf-8")


def _report(stats: dict, chosen: list[dict], reviews: list[dict]) -> str:
    decisions: dict[str, int] = defaultdict(int)
    for review in reviews:
        decisions[review["decision"]] += 1
    lines = [
        "# LVBench Compositional QA v1",
        "",
        "这些是可人工审查的候选，不是已经通过视频核验的 Benchmark 测试题。每道题的 `video_verified` 都是 false，`review_status` 都是 `PENDING_REVIEW`。",
        "",
        "## 漏斗",
        "",
        f"- 扫描的同视频 QA 对：{stats['scanned_same_video_pairs']}。",
        f"- 初步语义关联配对：{stats['preliminary_pairs']}。判定标准是官方答案里的同一个专名或名词短语，或“寻找某物 / 某人持有该物”。普通词共现没有算进来。",
        f"- 完整生成的新组合 QA：{stats['complete_candidates']}。",
        f"- 仍需人工编写：{stats['needs_human_draft']}。这些配对在 `candidate_pairs_pending.jsonl`，状态是 `NEEDS_HUMAN_DRAFT`，不计入完整候选。",
        f"- 完整候选覆盖视频：{stats['videos']}。",
        f"- 相对 v0 新增的来源配对：{stats['new_source_pairs_vs_v0']}。",
        "",
        "## 四种类型",
        "",
        f"- `entity_binding` 人物：{stats['by_type']['entity_binding']}。",
        f"- `object_binding` 物体：{stats['by_type']['object_binding']}。",
        f"- `event_binding` 动作／事件：{stats['by_type']['event_binding']}。",
        f"- `attribute_binding` 属性／关系：{stats['by_type']['attribute_binding']}。",
        "",
        "## 为什么不是大约 100 道",
        "",
        "v0 只有 30 道，主要是因为脚本要求一道题的正确答案必须是人名，并且优先做字符串替换。放宽到“答案实体出现在另一道题里”之后，全库 1,549 道题里能这样连起来的同视频配对仍然只有上面的初步筛选数量。其中一部分问法不能在不虚构动作的前提下自动改写，所以完整候选少于 100。没有用 and 拼接无关题目来补数量。",
        "",
        "## 相对 v0 的处理",
        "",
        f"- 保留：{decisions['kept']}。",
        f"- 修改：{decisions['modified']}。",
        f"- 反向改写后重新生成：{decisions['regenerated']}。",
        f"- 删除：{decisions['deleted']}。",
        "",
        "只改答案、没有新问题的 v0 题，能反向提问的改成了属性题，例如脱衣舞者。只把 Sonny 换成 the vlogger 的题已删除。物体题不再把被寻找的物品写进题干。",
        "",
        "同一道官方 UID 仍可能出现在多道候选里。审查时按题独立看。",
        "",
        "## 样例",
        "",
    ]
    shown = []
    for kind in COMPOSITION_TYPES:
        for candidate in chosen:
            if candidate["composition_type"] == kind and candidate not in shown:
                shown.append(candidate)
                break
    for candidate in chosen:
        if len(shown) >= 8:
            break
        if candidate not in shown:
            shown.append(candidate)
    for candidate in shown[:8]:
        lines.extend(
            [
                f"### {candidate['id']} `{candidate['composition_type']}` `{candidate['video_id']}`",
                "",
                f"- UIDs: {', '.join(candidate['source_uids'])}",
                f"- 新问题: {candidate['new_question']}",
                f"- 新答案: {candidate['new_answer']}",
                "",
            ]
        )
    lines.append("逐题来源见 `candidates.jsonl`。v0 的去留见 `v0_to_v1_review.csv`。")
    lines.append("")
    return "\n".join(lines)


README = """# LVBench Compositional QA v1

从官方 `video_info.meta.jsonl` 构造组合题候选。v0 的 30 道题保留在 `qa_v0/`，这里不覆盖。

完整候选必须改写问句，并且不能把需要组合才能得到的中间实体直接写进题干。做不到可靠改写的配对记为 `NEEDS_HUMAN_DRAFT`，不计入完整数量。

## 复现

在仓库根目录执行：

```bash
python3 tools/lvbench_comp/build_comp_qa_v1.py \\
  --metadata /home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl \\
  --v0 research_audit/lvbench_compositional/qa_v0/candidates.jsonl \\
  --output-dir research_audit/lvbench_compositional/qa_v1
```

解析复用 `prepare_lvbench.split_question` 和 v0 的时间窗过滤。不调用模型，不划分 Seen/Unseen。

测试：

```bash
python3 tools/lvbench_comp/test_build_comp_qa_v1.py
```
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build LVBench compositional QA v1 candidates.")
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--v0", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    records = load_qas(args.metadata)
    v0_rows = _load_v0(args.v0)
    chosen, pending, stats = build_v1(records, v0_rows)
    problems = []
    for candidate in chosen:
        problems.extend(f"{candidate['id']}: {item}" for item in validate_candidate(candidate, records))
    if problems:
        raise SystemExit("invalid candidates:\n" + "\n".join(problems))
    reviews = review_v0(v0_rows, chosen)
    write_outputs(chosen, pending, stats, reviews, args.output_dir)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
