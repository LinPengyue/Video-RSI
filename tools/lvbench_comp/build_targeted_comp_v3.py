#!/usr/bin/env python3
"""Targeted Novel Composition construction for LVBench v3.

Does not overwrite v0–v2.2 artifacts. New items are curated from official QA
pairs and optional verified video observations; unverified observations stay
NEEDS_HUMAN_VERIFICATION.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


UNSEEN_SCHEMA = "identify_person + query_action"
META = Path("/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl")

# Locked after light screening. TEST videos are isolated from TRAIN.
TEST_VIDEOS = [
    "JTa_Ue2MSwc",
    "cWEnogdsW78",
    "XNtNNplAwiI",
    "sk00epALZps",
    "t-RtDI2RWQs",
    "JlrzSvCsIjE",
    "HfEVEGf1A8Q",
    "RjDrZkBwzho",
]

# Curated NEW unseen candidates (official QA + official QA). Seeds from v2 are added separately.
NEW_UNSEEN: list[dict] = [
    {
        "video_id": "sk00epALZps",
        "related_official_uids": ["4753", "4748"],
        "new_question": "At 14:23, what does the person who assists Fisher's three-pointer do with reporters?",
        "new_answer": "The reporter shakes hands with Kobe",
        "bridge_entity": "Kobe Bryant",
        "fact_A": "The person who assists Fisher's three-pointer is Kobe Bryant.",
        "fact_B": "At 14:23, Kobe shakes hands with a reporter.",
        "evidence_A_time": "17:50-18:00",
        "evidence_B_time": "14:05-14:30",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "Replaces the name Kobe with the assist-event identifier; answering requires binding that identity to the handshake clip.",
        "shortcut_risk": "SINGLE_CLIP_SHORTCUT_RISK: the handshake clip alone may visually identify Kobe without the assist fact.",
    },
    {
        "video_id": "sk00epALZps",
        "related_official_uids": ["4753", "4760"],
        "new_question": "What does the person who assists Fisher's three-pointer take out of his pants pocket while wearing a black suit?",
        "new_answer": "Medal",
        "bridge_entity": "Kobe Bryant",
        "fact_A": "The person who assists Fisher's three-pointer is Kobe Bryant.",
        "fact_B": "Kobe in a black suit takes a medal out of his pants pocket.",
        "evidence_A_time": "17:50-18:00",
        "evidence_B_time": "29:15-29:20",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "Binds the assist identity to a later pocket action rather than asking the assist question again.",
        "shortcut_risk": "SINGLE_CLIP_SHORTCUT_RISK: a black-suit pocket clip may still show Kobe recognizably.",
    },
    {
        "video_id": "sk00epALZps",
        "related_official_uids": ["4753", "4762"],
        "new_question": "What does the person who assists Fisher's three-pointer do from 40:39-40:45?",
        "new_answer": "Kobe blows a kiss",
        "bridge_entity": "Kobe Bryant",
        "fact_A": "The person who assists Fisher's three-pointer is Kobe Bryant.",
        "fact_B": "From 40:39-40:45, Kobe blows a kiss.",
        "evidence_A_time": "17:50-18:00",
        "evidence_B_time": "40:30-40:35",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "Uses the assist identifier to query a later celebratory action.",
        "shortcut_risk": "SINGLE_CLIP_SHORTCUT_RISK: the kiss clip may identify Kobe without the assist fact.",
    },
    {
        "video_id": "t-RtDI2RWQs",
        "related_official_uids": ["1697", "1671"],
        "new_question": "What happens when the Best Lead Actress comes on stage?",
        "new_answer": "Her dress gets torn",
        "bridge_entity": "Emma Stone",
        "fact_A": "The Best Lead Actress is Emma Stone.",
        "fact_B": "When the Best Actress comes on stage, her dress gets torn.",
        "evidence_A_time": "68:42-76:21",
        "evidence_B_time": "69:20-74:13",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "Hides Emma Stone behind the award title and asks for the on-stage dress event.",
        "shortcut_risk": "LOW: the torn-dress clip may still be answerable if the award title is spoken on screen.",
    },
    {
        "video_id": "JlrzSvCsIjE",
        "related_official_uids": ["4028", "4029"],
        "new_question": "What are the people interviewed after the game doing afterward?",
        "new_answer": "Willians takes photos with Federer",
        "bridge_entity": "Willians and Federer",
        "fact_A": "The people interviewed after the game are Willians and Federer.",
        "fact_B": "After the interview, Willians takes photos with Federer.",
        "evidence_A_time": "42:25-45:00",
        "evidence_B_time": "45:00-46:31",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "Replaces named interviewees with the post-game interview referring expression before asking the photo action.",
        "shortcut_risk": "LOW-MEDIUM: the photo clip alone shows the action, but the question still depends on knowing who the post-game interviewees are.",
    },
    {
        "video_id": "HfEVEGf1A8Q",
        "related_official_uids": ["419", "402"],
        "new_question": "What does the one who stops the ghost hunter at last do when the girl first finds him?",
        "new_answer": "Clean the desk",
        "bridge_entity": "Vampire",
        "fact_A": "The one who stops the ghost hunter at last is the vampire.",
        "fact_B": "When the girl first finds the vampire, he cleans the desk.",
        "evidence_A_time": "73:01-74:21",
        "evidence_B_time": "14:00-14:15",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "Binds the later stopper identity to an earlier desk-cleaning action.",
        "shortcut_risk": "SINGLE_CLIP_SHORTCUT_RISK: the desk-cleaning clip may already make the vampire identity obvious.",
    },
    {
        "video_id": "HfEVEGf1A8Q",
        "related_official_uids": ["419", "412"],
        "new_question": "Where does the girl take the one who stops the ghost hunter at last after the exam?",
        "new_answer": "A park",
        "bridge_entity": "Vampire",
        "fact_A": "The one who stops the ghost hunter at last is the vampire.",
        "fact_B": "After the exam, the girl takes the vampire to a park.",
        "evidence_A_time": "73:01-74:21",
        "evidence_B_time": "46:00-47:20",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "Same stopper bridge, but the queried content is a later location/action involving that person.",
        "shortcut_risk": "NOTE: this item is closer to identify_person + query_location than pure query_action; kept as borderline and flagged.",
        "composition_schema": "identify_person + query_location",
        "exclude_from_unseen_action": True,
    },
    {
        "video_id": "CgvJqGxzRfE",
        "related_official_uids": ["4472", "4471"],
        "new_question": "What does the blonde woman do during Joao Duarte's performance, relative to the turning event for the curly-haired contestant?",
        "new_answer": "She crys",
        "bridge_entity": None,
        "fact_A": "Mantas turns first for the curly-haired contestant.",
        "fact_B": "During Joao Duarte's performance, the blonde woman cries.",
        "evidence_A_time": "44:43-44:43",
        "evidence_B_time": "34:45-35:00",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "REJECT_CANDIDATE: facts do not share a person bridge.",
        "shortcut_risk": "N/A",
        "reject": True,
        "reject_reason": "No shared bridge entity between Mantas turn and blonde woman crying.",
    },
    {
        "video_id": "CgvJqGxzRfE",
        "related_official_uids": ["4470", "4469"],
        "new_question": "What does the second girl on the right do between 32:00-32:05, around when VANNA turns for the 17th contestant?",
        "new_answer": "She crys",
        "bridge_entity": None,
        "fact_A": "VANNA turns around first when the 17th contestant performs.",
        "fact_B": "The second girl on the right cries between 32:00-32:05.",
        "evidence_A_time": "32:10-32:30",
        "evidence_B_time": "32:00-32:05",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "REJECT_CANDIDATE: adjacent times but no proven same-person binding.",
        "shortcut_risk": "N/A",
        "reject": True,
        "reject_reason": "No annotation proves the crying girl is VANNA.",
    },
    {
        "video_id": "uusf1qG_uZ4",
        "related_official_uids": ["3174", "3166"],
        "new_question": "What is the first exercise the substitute daycare teacher does with these infants, before the third kid slides into the pool?",
        "new_answer": "Jumping jacks",
        "bridge_entity": None,
        "reject": True,
        "reject_reason": "Not identify_person + query_action; no shared person bridge.",
        "fact_A": "",
        "fact_B": "",
        "evidence_A_time": "",
        "evidence_B_time": "",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "",
        "shortcut_risk": "",
    },
    {
        "video_id": "-WnyRMZqV1U",
        "related_official_uids": ["1734", "1736"],
        "new_question": "What does the presenter do to Brad Pitt when he wins the award, after the first man in red appears?",
        "new_answer": "She hugs him",
        "bridge_entity": None,
        "reject": True,
        "reject_reason": "Tom Hanks (first man in red) is not the hugging presenter; no valid bridge.",
        "fact_A": "",
        "fact_B": "",
        "evidence_A_time": "",
        "evidence_B_time": "",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "",
        "shortcut_risk": "",
    },
    {
        "video_id": "RjDrZkBwzho",
        "related_official_uids": ["766", "767"],
        "new_question": "After finding a row of switches, which switch does the one who fires shots after finding the black mice press?",
        "new_answer": "Yellow switch",
        "bridge_entity": "Sheriff Black Cat",
        "fact_A": "Sheriff Black Cat fires shots after finding the black mice.",
        "fact_B": "After finding switches, Sheriff Black Cat presses the yellow switch.",
        "evidence_A_time": "10:52-11:00",
        "evidence_B_time": "11:59-12:03",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "Identifies the sheriff via the shooting event, then queries a later switch-press action without repeating the name.",
        "shortcut_risk": "MEDIUM: both clips may visually identify the same cat character.",
        "composition_schema": "identify_person + query_action",
        "entity_note": "Anthropomorphic character treated like person-agent for this pilot schema.",
    },
    {
        "video_id": "RjDrZkBwzho",
        "related_official_uids": ["758"],
        "new_question": "What does the black and pink shrew do after climbing the window?",
        "new_answer": "It rings the alarm",
        "bridge_entity": "black and pink shrew",
        "fact_A": "The black and pink shrew is the agent in the window-climbing event.",
        "fact_B": "After climbing the window, it rings the alarm.",
        "evidence_A_time": "06:40-06:55",
        "evidence_B_time": "06:40-06:55",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "REJECT_CANDIDATE: identify and action are the same official QA, not a two-fact composition.",
        "shortcut_risk": "N/A",
        "reject": True,
        "reject_reason": "Single official QA; not a two-interval composition.",
    },
    # Same as v2 seed 003 — keep as documented reject so it is not double-counted as new.
    {
        "video_id": "JTa_Ue2MSwc",
        "related_official_uids": ["5130", "5134"],
        "new_question": "What does the first interviewee do after the first male guest shows up on the stage?",
        "new_answer": "She slaps the man",
        "bridge_entity": "Sierra",
        "fact_A": "The first interviewee's name is Sierra.",
        "fact_B": "After the first male guest shows up, Sierra slaps the man.",
        "evidence_A_time": "00:29-01:36",
        "evidence_B_time": "05:28-05:59",
        "fact_A_source": "OFFICIAL_QA",
        "fact_B_source": "OFFICIAL_QA",
        "novelty_rationale": "REJECT_CANDIDATE: identical structure already retained as v2 seed LVCOMP-V2-003.",
        "shortcut_risk": "MEDIUM",
        "seed_link": "LVCOMP-V2-003",
        "reject": True,
        "reject_reason": "Duplicate of SUPPORTED seed; not a new invention.",
    },
]

# Seen-B true action queries on TRAIN videos only (not in TEST_VIDEOS).
NEW_SEEN_B: list[dict] = [
    {
        "video_id": "evYm0cELO3I",
        "schema": "identify_object + query_action",
        "related_official_uids": ["2754", "2763"],
        "new_question": "What happens from 04:19-04:45 involving the animal that appears at 00:07?",
        "new_answer": "The chef cooks Lobster Quesadilla",
        "primitive_focus": "query_action",
        "rationale": "Queries a cooking action bound to an identified object/animal.",
        "action_status": "ACTION_PRIMITIVE_VALID",
    },
    {
        "video_id": "evYm0cELO3I",
        "schema": "identify_object + query_action",
        "related_official_uids": ["2754", "2764"],
        "new_question": "What happens from 04:50-05:20 involving the animal that appears at 00:07?",
        "new_answer": "Sonny tastes Lobster Quesadilla",
        "primitive_focus": "query_action",
        "rationale": "Queries a tasting action bound to the same animal bridge.",
        "action_status": "ACTION_PRIMITIVE_VALID",
    },
    {
        "video_id": "oZEVgDXJwCc",
        "schema": "identify_event_result + query_action",
        "related_official_uids": ["3534", "3542"],
        "new_question": "Who does Kroos substitute at 65:13?",
        "new_answer": "the German player who attempts the first shot",
        "primitive_focus": "query_action",
        "rationale": "Substitution patient query; marked weak vs test-side agent action queries.",
        "action_status": "ACTION_PRIMITIVE_WEAK",
        "seed_link": "LVCOMP-V2-112",
    },
    {
        "video_id": "2LH3JCGkEBU",
        "schema": "identify_event_result + query_action",
        "related_official_uids": ["4304", "4305"],
        "new_question": "What did the man do after kissing the woman's hands during the Vancouver 2010 performance that was done while wearing a white dress?",
        "new_answer": "He got down on one knee",
        "primitive_focus": "query_action",
        "rationale": "Clear agent action query after an event bridge.",
        "action_status": "ACTION_PRIMITIVE_VALID",
        "seed_link": "LVCOMP-V2-100",
    },
    {
        "video_id": "pXD3txG2bVQ",
        "schema": "identify_event_result + query_action",
        "related_official_uids": ["727"],
        "new_question": "What happens after the boy looks very down in the middle of the man and the woman?",
        "new_answer": "The boy writes and the cat packs the luggage",
        "primitive_focus": "query_action",
        "rationale": "Official post-event action sequence; no identify_person+query_action pairing.",
        "action_status": "ACTION_PRIMITIVE_VALID",
        "from_official_direct": True,
    },
    {
        "video_id": "XNtNNplAwiI",
        "schema": "identify_event_result + query_action",
        "related_official_uids": ["799"],
        "new_question": "What happens after the orange calabash boy come to save grandpa?",
        "new_answer": "He gets blind",
        "primitive_focus": "query_action",
        "rationale": "Post-event consequence/action on the boy; not person+action unseen schema.",
        "action_status": "ACTION_PRIMITIVE_WEAK",
        "from_official_direct": True,
    },
    {
        "video_id": "_T2Avd3tFHc",
        "schema": "identify_person + query_location",
        "related_official_uids": ["2873", "2890"],
        "new_question": "Where do the vlogger team members invite the elder who joins the vlogger on their travel on the first night?",
        "new_answer": "They invite the elder who joins the vlogger on their travel to the hotel",
        "primitive_focus": "identify_person",
        "rationale": "Seen-A style person identification to location, not action.",
        "action_status": "N/A",
        "seed_link": "LVCOMP-V2-012",
        "bucket": "seen_a",
    },
    {
        "video_id": "wgBlACG927Y",
        "schema": "identify_event_result + query_action",
        "related_official_uids": ["3080", "3082"],
        "new_question": "How do the vloggers leave the platform and go upstairs after the first means of transportation they take when they come to China?",
        "new_answer": "After they get off the high-speed train, they go upstairs and go pass the ticket gate, exiting the train station",
        "primitive_focus": "query_action",
        "rationale": "Manner/process query; weak alignment to agent what-does-X-do.",
        "action_status": "ACTION_PRIMITIVE_WEAK",
        "seed_link": "LVCOMP-V2-115",
    },
    {
        "video_id": "T1yhBv1ytzw",
        "schema": "identify_event_result + query_action",
        "related_official_uids": ["3785", "3789"],
        "new_question": "Why does the person who scores the first goal fall at 42:37?",
        "new_answer": "His head hurts",
        "primitive_focus": "query_cause",
        "rationale": "Cause query, not action; excluded from Seen-B action counts.",
        "action_status": "ACTION_PRIMITIVE_MISMATCH",
        "seed_link": "LVCOMP-V2-029",
        "exclude_from_seen_b": True,
    },
]


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _csv(path: Path, rows: list[dict]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_meta_index() -> dict[str, dict]:
    out = {}
    for line in META.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        out[rec["key"]] = rec
    return out


def video_pool_rows(meta: dict[str, dict], v2_videos: set[str]) -> list[dict]:
    screened = [
        "JTa_Ue2MSwc",
        "sk00epALZps",
        "t-RtDI2RWQs",
        "JlrzSvCsIjE",
        "HfEVEGf1A8Q",
        "CgvJqGxzRfE",
        "uusf1qG_uZ4",
        "-WnyRMZqV1U",
        "RjDrZkBwzho",
        "cWEnogdsW78",
        "Aiem1w_TvaA",
        "xECIRjlxM3U",
        "Xjf5N9S3jAA",
        "evYm0cELO3I",
        "2LH3JCGkEBU",
        "oZEVgDXJwCc",
        "_T2Avd3tFHc",
        "T1yhBv1ytzw",
        "pXD3txG2bVQ",
        "wgBlACG927Y",
        "XNtNNplAwiI",
    ]
    rows = []
    for vid in screened:
        rec = meta[vid]
        n = len(rec["qa"])
        split = "TEST" if vid in TEST_VIDEOS else "TRAIN"
        reason = {
            "JTa_Ue2MSwc": "Seed SUPPORTED person-action items from v2.2; multi-event interview.",
            "sk00epALZps": "Kobe appears across interview and highlight actions with official name bridges.",
            "t-RtDI2RWQs": "Award-title person ID plus on-stage dress event.",
            "JlrzSvCsIjE": "Post-game interview identity then photo action.",
            "HfEVEGf1A8Q": "Vampire identity via later event then earlier desk action.",
            "CgvJqGxzRfE": "Many turn/cry events but few proven same-person bridges; kept for screening.",
            "uusf1qG_uZ4": "Multiple named kids/adults; limited reliable action bridges.",
            "-WnyRMZqV1U": "Oscar ceremony; few valid person-action bridges after checks.",
            "RjDrZkBwzho": "Anthropomorphic sheriff action chain usable with caveats.",
            "cWEnogdsW78": "v2.2 reviewed person-strike item; kept in TEST for seed coverage.",
            "Aiem1w_TvaA": "Basketball; person names present but few clean action queries.",
            "xECIRjlxM3U": "Story video; limited dual-interval person-action pairs.",
            "Xjf5N9S3jAA": "Tennis IDs mostly same-person recognition, weak action queries.",
            "XNtNNplAwiI": "v2 seed person/character action item; TEST for seed coverage.",
        }.get(vid, "Prior v2 coverage / Seen-side reuse.")
        if vid in TEST_VIDEOS:
            split = "TEST"
        elif vid in {"CgvJqGxzRfE", "uusf1qG_uZ4", "-WnyRMZqV1U", "Aiem1w_TvaA", "xECIRjlxM3U", "Xjf5N9S3jAA"}:
            split = "UNSUITABLE"
        elif vid in {
            "evYm0cELO3I",
            "2LH3JCGkEBU",
            "oZEVgDXJwCc",
            "_T2Avd3tFHc",
            "T1yhBv1ytzw",
            "pXD3txG2bVQ",
            "wgBlACG927Y",
        }:
            split = "TRAIN"
        rows.append(
            {
                "video_id": vid,
                "n_official_qa": n,
                "used_in_v2": vid in v2_videos,
                "has_identifiable_person": "yes" if n >= 8 else "maybe",
                "has_cross_time_action": "yes" if vid in TEST_VIDEOS or vid in {"evYm0cELO3I", "2LH3JCGkEBU", "RjDrZkBwzho"} else "maybe",
                "candidate_event_times": "see candidates",
                "planned_split": split,
                "selection_reason": reason,
            }
        )
    return rows


EXCLUDE_SEED_IDS = {
    "LVCOMP-V2-106",  # pangolin animal mismatch
    "LVCOMP-V2-113",  # dog mismatch
    "LVCOMP-V2-114",  # dog mismatch
    "LVCOMP-V2-038",  # contradicted
}


def seed_unseen_from_v2(v2_rows: list[dict], reviews: dict[str, dict]) -> list[dict]:
    out = []
    for row in v2_rows:
        if row["composition_schema"] != UNSEEN_SCHEMA:
            continue
        if row["video_id"] not in TEST_VIDEOS:
            continue
        if row["id"] in EXCLUDE_SEED_IDS:
            continue
        v1 = row.get("source_v1_id")
        review = reviews.get(v1, {}) if v1 else {}
        # map v2 review file which uses v2 ids in pilot_v2_2
        rev2 = reviews.get(row["id"], review)
        status = rev2.get("review_status", row.get("review_status", "UNVERIFIED"))
        out.append(
            {
                "question_id": f"LVCOMP-V3-SEED-{row['id'].rsplit('-', 1)[-1]}",
                "video_id": row["video_id"],
                "new_question": row["new_question"],
                "new_answer": row["new_answer"],
                "composition_schema": UNSEEN_SCHEMA,
                "primitive_A": "identify_person",
                "primitive_B": "query_action",
                "bridge_entity": "from_v2",
                "fact_A": "See related official UIDs / v2 source questions.",
                "fact_B": row["new_answer"],
                "evidence_A_time": row["time_references"][0],
                "evidence_B_time": row["time_references"][1],
                "fact_A_source": "OFFICIAL_QA",
                "fact_B_source": "OFFICIAL_QA",
                "related_official_uids": row["source_uids"],
                "novelty_rationale": "Seed retained from v2; not counted as a newly invented sample.",
                "shortcut_risk": "recorded_in_v2_review",
                "review_status": status if status in {"SUPPORTED", "UNCERTAIN", "CONTRADICTED", "PENDING_HUMAN_REVIEW"} else "UNVERIFIED",
                "origin": "v2_seed",
                "source_v2_id": row["id"],
                "video_verified": status == "SUPPORTED",
            }
        )
    return out


def materialize_new_unseen(specs: list[dict]) -> list[dict]:
    out = []
    idx = 1
    for spec in specs:
        if spec.get("reject"):
            continue
        if spec.get("exclude_from_unseen_action"):
            continue
        schema = spec.get("composition_schema", UNSEEN_SCHEMA)
        if schema != UNSEEN_SCHEMA:
            continue
        item = {
            "question_id": f"LVCOMP-V3-U-{idx:03d}",
            "video_id": spec["video_id"],
            "new_question": spec["new_question"],
            "new_answer": spec["new_answer"],
            "composition_schema": schema,
            "primitive_A": "identify_person",
            "primitive_B": "query_action",
            "bridge_entity": spec.get("bridge_entity"),
            "fact_A": spec["fact_A"],
            "fact_B": spec["fact_B"],
            "evidence_A_time": spec["evidence_A_time"],
            "evidence_B_time": spec["evidence_B_time"],
            "fact_A_source": spec["fact_A_source"],
            "fact_B_source": spec["fact_B_source"],
            "related_official_uids": spec["related_official_uids"],
            "novelty_rationale": spec["novelty_rationale"],
            "shortcut_risk": spec["shortcut_risk"],
            "review_status": "UNVERIFIED",
            "origin": "v3_targeted_official",
            "entity_note": spec.get("entity_note", ""),
            "seed_link": spec.get("seed_link"),
            "video_verified": False,
        }
        out.append(item)
        idx += 1
    return out


def seen_from_v2(v2_rows: list[dict], train_videos: set[str]) -> tuple[list[dict], list[dict]]:
    seen_a, seen_b = [], []
    for row in v2_rows:
        if row["video_id"] not in train_videos:
            continue
        if row["id"] == "LVCOMP-V2-038":
            continue
        schema = row["composition_schema"]
        if schema == UNSEEN_SCHEMA:
            continue
        item = {
            "question_id": f"LVCOMP-V3-SEEN-{row['id'].rsplit('-', 1)[-1]}",
            "video_id": row["video_id"],
            "new_question": row["new_question"],
            "new_answer": row["new_answer"],
            "composition_schema": schema,
            "related_official_uids": row["source_uids"],
            "time_references": row["time_references"],
            "origin": "v2_reuse",
            "source_v2_id": row["id"],
            "review_status": row.get("review_status", "UNVERIFIED"),
            "video_verified": False,
        }
        a, b = [p.strip() for p in schema.split("+", 1)]
        if a == "identify_person" and b != "query_action":
            item["bucket"] = "seen_a"
            item["primitive_focus"] = "identify_person"
            seen_a.append(item)
        elif b == "query_action" or schema.endswith("query_action"):
            item["bucket"] = "seen_b"
            item["primitive_focus"] = "query_action"
            # reuse v2.2 audit if known
            item["action_status"] = "PENDING_SEMANTIC_CHECK"
            seen_b.append(item)
    return seen_a, seen_b


def materialize_new_seen(specs: list[dict], train_videos: set[str]) -> tuple[list[dict], list[dict]]:
    seen_a, seen_b = [], []
    ia = ib = 1
    for spec in specs:
        if spec["video_id"] not in train_videos:
            continue
        if spec.get("exclude_from_seen_b") and spec.get("bucket") != "seen_a":
            continue
        item = {
            "video_id": spec["video_id"],
            "new_question": spec["new_question"],
            "new_answer": spec["new_answer"],
            "composition_schema": spec["schema"],
            "related_official_uids": spec["related_official_uids"],
            "origin": "v3_targeted_official" if not spec.get("seed_link") else "v2_seed_linked",
            "seed_link": spec.get("seed_link"),
            "rationale": spec.get("rationale", ""),
            "action_status": spec.get("action_status", "N/A"),
            "review_status": "UNVERIFIED",
            "video_verified": False,
            "primitive_focus": spec.get("primitive_focus"),
        }
        if spec.get("bucket") == "seen_a" or spec.get("primitive_focus") == "identify_person" and "query_action" not in spec["schema"]:
            item["question_id"] = f"LVCOMP-V3-SA-{ia:03d}"
            item["bucket"] = "seen_a"
            seen_a.append(item)
            ia += 1
        else:
            if spec.get("action_status") == "ACTION_PRIMITIVE_MISMATCH":
                continue
            item["question_id"] = f"LVCOMP-V3-SB-{ib:03d}"
            item["bucket"] = "seen_b"
            seen_b.append(item)
            ib += 1
    return seen_a, seen_b


def near_duplicate_clusters(items: list[dict]) -> list[dict]:
    by_video = defaultdict(list)
    for item in items:
        by_video[item["video_id"]].append(item)
    clusters = []
    for vid, rows in by_video.items():
        # cluster by shared bridge / similar question prefix
        groups = defaultdict(list)
        for row in rows:
            key = (row.get("bridge_entity") or row.get("source_v2_id") or row["new_question"][:40]).lower()
            groups[str(key)].append(row["question_id"])
        for key, ids in groups.items():
            if len(ids) >= 2:
                clusters.append({"video_id": vid, "cluster_key": key, "n": len(ids), "ids": " ".join(ids)})
    return clusters


def build_split(unseen: list[dict], seen_a: list[dict], seen_b: list[dict]) -> dict:
    # Structural unseen: schema correct, not contradicted
    structural_test = [
        row
        for row in unseen
        if row["composition_schema"] == UNSEEN_SCHEMA and row["review_status"] != "CONTRADICTED"
    ]
    evidence_test = [row for row in structural_test if row["review_status"] == "SUPPORTED"]
    unverified_test = [row for row in structural_test if row["review_status"] in {"UNVERIFIED", "UNCERTAIN", "PENDING_HUMAN_REVIEW", "NEEDS_HUMAN_VERIFICATION"}]

    # Seen train: no unseen schema, no test videos, no contradicted
    train = []
    for row in seen_a + seen_b:
        if row["video_id"] in TEST_VIDEOS:
            continue
        if row["composition_schema"] == UNSEEN_SCHEMA:
            continue
        if row.get("review_status") == "CONTRADICTED":
            continue
        train.append(row)

    train_ids = [row["question_id"] for row in train]
    test_ids = [row["question_id"] for row in structural_test]
    train_videos = sorted({row["video_id"] for row in train})
    test_videos = sorted({row["video_id"] for row in structural_test})
    train_uids = {(row["video_id"], uid) for row in train for uid in row.get("related_official_uids", [])}
    test_uids = {(row["video_id"], uid) for row in structural_test for uid in row.get("related_official_uids", [])}

    seen_a_valid = [row for row in train if row.get("bucket") == "seen_a"]
    seen_b_valid = [
        row
        for row in train
        if row.get("bucket") == "seen_b" and row.get("action_status") in {None, "PENDING_SEMANTIC_CHECK", "ACTION_PRIMITIVE_VALID", "ACTION_PRIMITIVE_WEAK"}
    ]
    seen_b_strict = [row for row in train if row.get("bucket") == "seen_b" and row.get("action_status") == "ACTION_PRIMITIVE_VALID"]

    validation = {
        "unseen_schema_in_train": sum(1 for row in train if row["composition_schema"] == UNSEEN_SCHEMA),
        "video_overlap": sorted(set(train_videos) & set(test_videos)),
        "uid_overlap": sorted(f"{v}:{u}" for v, u in (train_uids & test_uids)),
        "ok": True,
    }
    validation["ok"] = (
        validation["unseen_schema_in_train"] == 0
        and not validation["video_overlap"]
        and not validation["uid_overlap"]
    )

    return {
        "status": "PILOT_ONLY_NOT_VIDEO_CERTIFIED",
        "unseen_schema": UNSEEN_SCHEMA,
        "train_ids": train_ids,
        "test_ids": test_ids,
        "train_videos": train_videos,
        "test_videos": test_videos,
        "counts": {
            "STRUCTURAL_CANDIDATES_TEST": len(structural_test),
            "EVIDENCE_SUPPORTED_TEST": len(evidence_test),
            "UNVERIFIED_TEST": len(unverified_test),
            "SEEN_A_TRAIN": len(seen_a_valid),
            "SEEN_B_TRAIN": len(seen_b_valid),
            "SEEN_B_ACTION_VALID": len(seen_b_strict),
            "SEEN_A_VIDEOS": len({row["video_id"] for row in seen_a_valid}),
            "SEEN_B_VIDEOS": len({row["video_id"] for row in seen_b_valid}),
            "SEEN_B_VALID_VIDEOS": len({row["video_id"] for row in seen_b_strict}),
        },
        "validation": validation,
        "near_duplicate_note": "See composition_statistics / clusters in REPORT.",
        "note": "Experimental targeted split. Most new items remain UNVERIFIED. Not a formal benchmark.",
    }


def default_sample_review(unseen_all: list[dict], unseen_new: list[dict]) -> list[dict]:
    # Prefer one item per video across new + seeds; do not auto-SUPPORT unverified clips.
    picked: list[dict] = []
    seen_v: set[str] = set()
    # Prefer new first, then seeds, diversify videos.
    for pool in (unseen_new, unseen_all):
        for row in pool:
            if row["video_id"] in seen_v:
                continue
            picked.append(row)
            seen_v.add(row["video_id"])
            if len(picked) >= 10:
                break
        if len(picked) >= 10:
            break
    # If still short, allow a second item from dense videos.
    if len(picked) < 8:
        for row in unseen_new:
            if row in picked:
                continue
            picked.append(row)
            if len(picked) >= 10:
                break
    out = []
    for row in picked:
        if row.get("review_status") == "SUPPORTED" and row.get("origin") == "v2_seed":
            status = "SUPPORTED"
            notes = "Retained v2.2 video-supported seed; not re-audited in v3."
            fact_status = "SUPPORTED"
        else:
            status = "PENDING_HUMAN_REVIEW"
            notes = "Official QA supports the wording. Contact-sheet/video judgment not asserted as SUPPORTED."
            fact_status = "PENDING_HUMAN_REVIEW"
        out.append(
            {
                "question_id": row["question_id"],
                "video_id": row["video_id"],
                "fact_A_status": fact_status,
                "fact_B_status": fact_status,
                "same_person_status": fact_status,
                "ambiguity_status": fact_status if status == "SUPPORTED" else "PENDING_HUMAN_REVIEW",
                "shortcut_status": row.get("shortcut_risk", ""),
                "review_status": status,
                "notes": notes,
            }
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2-candidates", type=Path, required=True)
    parser.add_argument("--v22-test-review", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    meta = load_meta_index()
    v2_rows = _load_jsonl(args.v2_candidates)
    v2_videos = {row["video_id"] for row in v2_rows}

    # reviews keyed by v2 id from pilot_v2_2
    reviews = {}
    with args.v22_test_review.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            reviews[row["id"]] = row

    pool = video_pool_rows(meta, v2_videos)
    train_videos = {row["video_id"] for row in pool if row["planned_split"] == "TRAIN"}
    # ensure all non-test used train videos included
    train_videos |= {row["video_id"] for row in v2_rows if row["video_id"] not in TEST_VIDEOS}

    seeds = seed_unseen_from_v2(v2_rows, reviews)
    # keep only SCHEMA-compatible seeds on test videos; drop animal mismatches already filtered by schema label
    seeds = [row for row in seeds if row["video_id"] in TEST_VIDEOS]
    new_unseen = materialize_new_unseen(NEW_UNSEEN)
    # dedupe questions against seeds
    seed_q = {" ".join(row["new_question"].lower().split()) for row in seeds}
    new_unseen = [row for row in new_unseen if " ".join(row["new_question"].lower().split()) not in seed_q]
    unseen = seeds + new_unseen

    seen_a_v2, seen_b_v2 = seen_from_v2(v2_rows, train_videos)
    # apply v2.2 action audit onto overlapping seed links
    action_audit = {
        "LVCOMP-V2-100": "ACTION_PRIMITIVE_VALID",
        "LVCOMP-V2-109": "ACTION_PRIMITIVE_VALID",
        "LVCOMP-V2-110": "ACTION_PRIMITIVE_VALID",
        "LVCOMP-V2-111": "ACTION_PRIMITIVE_VALID",
        "LVCOMP-V2-104": "ACTION_PRIMITIVE_VALID",
        "LVCOMP-V2-105": "ACTION_PRIMITIVE_VALID",
        "LVCOMP-V2-112": "ACTION_PRIMITIVE_MISMATCH",  # substitution patient, not agent action
        "LVCOMP-V2-115": "ACTION_PRIMITIVE_WEAK",
        "LVCOMP-V2-116": "ACTION_PRIMITIVE_MISMATCH",
        "LVCOMP-V2-203": "ACTION_PRIMITIVE_VALID",
    }
    mismatch_re = re.compile(
        r"\b(feeling|feel|why|company|transport|replace|score|point|name|sad)\b",
        re.I,
    )
    for row in seen_b_v2:
        sid = row.get("source_v2_id")
        q = row["new_question"]
        if sid in action_audit:
            row["action_status"] = action_audit[sid]
        elif mismatch_re.search(q) or q.lower().startswith("who does") or "which company" in q.lower():
            row["action_status"] = "ACTION_PRIMITIVE_MISMATCH"
        elif re.search(r"\bwhat (happens|did|does)\b|\bhow (does|do)\b", q, re.I):
            row["action_status"] = "ACTION_PRIMITIVE_WEAK"
        else:
            row["action_status"] = "ACTION_PRIMITIVE_MISMATCH"
    seen_b_v2 = [row for row in seen_b_v2 if row.get("action_status") != "ACTION_PRIMITIVE_MISMATCH"]

    seen_a_new, seen_b_new = materialize_new_seen(NEW_SEEN_B, train_videos)
    # avoid duplicating v2 seed-linked questions
    existing_q = {" ".join(row["new_question"].lower().split()) for row in seen_a_v2 + seen_b_v2}
    seen_a_new = [row for row in seen_a_new if " ".join(row["new_question"].lower().split()) not in existing_q]
    seen_b_new = [row for row in seen_b_new if " ".join(row["new_question"].lower().split()) not in existing_q]
    seen_a = seen_a_v2 + seen_a_new
    seen_b = seen_b_v2 + seen_b_new

    sample = default_sample_review(unseen, new_unseen)
    split = build_split(unseen, seen_a, seen_b)
    clusters = near_duplicate_clusters(unseen)

    # write jsonl
    with (out / "unseen_candidates.jsonl").open("w", encoding="utf-8") as handle:
        for row in unseen:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (out / "seen_candidates.jsonl").open("w", encoding="utf-8") as handle:
        for row in seen_a + seen_b:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    index_rows = []
    for row in unseen:
        index_rows.append(
            {
                "question_id": row["question_id"],
                "bucket": "unseen",
                "video_id": row["video_id"],
                "schema": row["composition_schema"],
                "origin": row.get("origin"),
                "review_status": row.get("review_status"),
                "related_official_uids": " ".join(row.get("related_official_uids") or []),
            }
        )
    for row in seen_a + seen_b:
        index_rows.append(
            {
                "question_id": row["question_id"],
                "bucket": row.get("bucket"),
                "video_id": row["video_id"],
                "schema": row["composition_schema"],
                "origin": row.get("origin"),
                "review_status": row.get("review_status"),
                "related_official_uids": " ".join(row.get("related_official_uids") or []),
                "action_status": row.get("action_status", ""),
            }
        )

    stats = [
        {
            "metric": "screened_videos",
            "value": len(pool),
        },
        {
            "metric": "test_videos_locked",
            "value": len(TEST_VIDEOS),
        },
        {
            "metric": "new_unseen_candidates",
            "value": len(new_unseen),
        },
        {
            "metric": "seed_unseen_candidates",
            "value": len(seeds),
        },
        {
            "metric": "unseen_videos",
            "value": len({row["video_id"] for row in unseen}),
        },
        {
            "metric": "seen_a",
            "value": len(seen_a),
            "videos": len({row["video_id"] for row in seen_a}),
        },
        {
            "metric": "seen_b",
            "value": len(seen_b),
            "videos": len({row["video_id"] for row in seen_b}),
        },
        {
            "metric": "seen_b_action_valid",
            "value": sum(1 for row in seen_b if row.get("action_status") == "ACTION_PRIMITIVE_VALID"),
            "videos": len({row["video_id"] for row in seen_b if row.get("action_status") == "ACTION_PRIMITIVE_VALID"}),
        },
        {
            "metric": "near_duplicate_clusters",
            "value": len(clusters),
        },
    ]

    _csv(out / "video_pool_selection.csv", pool)
    _csv(out / "all_candidate_index.csv", index_rows)
    _csv(out / "composition_statistics.csv", stats)
    _csv(out / "sample_quality_review.csv", sample)
    (out / "strict_split_pilot.json").write_text(json.dumps(split, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if clusters:
        _csv(out / "near_duplicate_clusters.csv", clusters)

    report = f"""# LVBench Compositional Generalization targeted v3

定向构造 Unseen `{UNSEEN_SCHEMA}`，并补 Seen-A / Seen-B。不覆盖 v0–v2.2。

## 视频池

- 轻量筛选视频：{len(pool)}
- 锁定 TEST：{', '.join(TEST_VIDEOS)}（{len(TEST_VIDEOS)}）
- TRAIN / UNSUITABLE 见 `video_pool_selection.csv`

## Unseen 候选

- 新增官方可追溯候选：{len(new_unseen)}（目标 20–30；未凑数）
- v2 seed 保留：{len(seeds)}（不计入新增发明）
- 覆盖视频：{len({row['video_id'] for row in unseen})}
- 已视频 SUPPORTED：{sum(1 for row in unseen if row.get('review_status')=='SUPPORTED')}（主要来自 v2.2 seed）
- 新增题默认 `UNVERIFIED`；抽样为 `PENDING_HUMAN_REVIEW`（可抽关键帧，不自动升格）

达不到 20–30 的原因：同视频、可独立核验、且真正需要 person→action 绑定的官方共指很少；不能用视频观察臆造动作。

## Seen 能力

- Seen-A：{len(seen_a)} 道 / {len({row['video_id'] for row in seen_a})} 视频
- Seen-B：{len(seen_b)} 道 / {len({row['video_id'] for row in seen_b})} 视频
- Seen-B 中 `ACTION_PRIMITIVE_VALID`：{sum(1 for row in seen_b if row.get('action_status')=='ACTION_PRIMITIVE_VALID')} 道 / {len({row['video_id'] for row in seen_b if row.get('action_status')=='ACTION_PRIMITIVE_VALID'})} 视频

## 捷径与重复

- 多数 Kobe 题标了 `SINGLE_CLIP_SHORTCUT_RISK`
- 近重复簇：{len(clusters)}（同视频同 bridge）

## Strict split

- validation.ok = {split['validation']['ok']}
- STRUCTURAL test = {split['counts']['STRUCTURAL_CANDIDATES_TEST']}
- EVIDENCE_SUPPORTED test = {split['counts']['EVIDENCE_SUPPORTED_TEST']}
- UNVERIFIED test = {split['counts']['UNVERIFIED_TEST']}
- SEEN_A / SEEN_B = {split['counts']['SEEN_A_TRAIN']} / {split['counts']['SEEN_B_TRAIN']}
- 已知 CONTRADICTED 未进入划分

## 主要瓶颈

1. 官方 QA 中可靠的跨区间人物→动作共指仍然稀缺。
2. 新题大多尚未人工看片，不能升格为 SUPPORTED。
3. 测试仍依赖少量高密度视频（尤其 sk00epALZps / JTa）。
4. Seen-B 真正与测试同型的 agent action 仍然偏少。

这不是正式 Benchmark，也未运行 RSI。
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")
    (out / "README.md").write_text(
        """# Targeted Compositional QA v3

```bash
python3 tools/lvbench_comp/build_targeted_comp_v3.py \\
  --v2-candidates research_audit/lvbench_compositional/v2/candidates.jsonl \\
  --v22-test-review research_audit/lvbench_compositional/pilot_v2_2/test_video_review.csv \\
  --output-dir research_audit/lvbench_compositional/targeted_v3

python3 tools/lvbench_comp/extract_targeted_v3_sample_media.py
python3 -m unittest tools.lvbench_comp.test_build_targeted_comp_v3 -v
```

媒体目录 `local_media/` 被 git 忽略。
""",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "new_unseen": len(new_unseen),
                "seed_unseen": len(seeds),
                "unseen_videos": len({row["video_id"] for row in unseen}),
                "seen_a": len(seen_a),
                "seen_b": len(seen_b),
                "seen_b_valid": sum(1 for row in seen_b if row.get("action_status") == "ACTION_PRIMITIVE_VALID"),
                "split_ok": split["validation"]["ok"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
