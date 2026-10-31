"""B4 — batch QA drafting from recorded events/relations (V2: attribute-conditioned)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .dedup import apply_semantic_dedup
from .fact_binding import apply_binding_gate


def _family(fact_ids: list[str], sig: str) -> str:
    key = "|".join(sorted(fact_ids)) + "#" + sig
    return "FAM_" + hashlib.sha256(key.encode()).hexdigest()[:10]


def _name_from_obj(obj: str) -> str | None:
    # Prefer last capitalized token sequence resembling a person name
    if not obj:
        return None
    # Patterns: "USA Gay", "USA Justin Gatlin", "NOR Jaysuma Saidy Ndure", "CHN FAN ZHENDONG"
    m = re.search(
        r"(?:USA|NOR|CHN|GBR|JPN)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})",
        obj,
    )
    if m:
        return m.group(1).title() if m.group(1).isupper() else m.group(1)
    m2 = re.search(r"\b(Gay|Gatlin|Ndure|Fan\s*Zhendong)\b", obj, re.I)
    return m2.group(1) if m2 else None


def _country_from_obj(obj: str) -> str | None:
    m = re.search(r"\b(USA|NOR|CHN|GBR|JPN|BRI|LIV)\b", obj or "")
    return m.group(1) if m else None


def draft_qa(
    relations: list[dict[str, Any]],
    events_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    n = 0

    for rel in relations:
        facts = [events_by_id[i] for i in rel["source_fact_ids"] if i in events_by_id]
        if len(facts) < 2:
            continue
        a, b = facts[0], facts[1]
        n += 1
        qid = f"QA_DRAFT_{n:04d}"
        fam = _family(rel["source_fact_ids"], rel["composition_signature"])
        base = {
            "qa_id": qid,
            "video_id": rel["video_id"],
            "relation_id": rel["relation_id"],
            "evidence_family": fam,
            "fact_ids": rel["source_fact_ids"],
            "dependency_program": rel["composition_signature"],
            "witness_set": rel["minimal_witness_set"],
            "time_intervals": rel["source_intervals"],
            "single_clip_shortcut_risk": rel.get("possible_shortcut"),
            "uncertainty": list(rel.get("uncertainty") or []),
            "funnel_level": "QA_DRAFT",
            "data_partition_status": "UNASSIGNED",
            "formal_supported": False,
            "prompt_model_version": "rule_drafter_v2_attr",
            "distractors_with_rationale": [],
            "counterfactual_probe": None,
            "from_new_observation": any(
                events_by_id.get(i, {}).get("is_newly_discovered_semantic") for i in rel["source_fact_ids"]
            ),
        }

        rtype = rel["type"]
        if rtype == "ordered_state_transitions":
            drafts.append(
                {
                    **base,
                    "question_zh": "两次改变比分的事件按文件时间顺序，比分状态如何变化？请只依据两段比分覆盖层作答。",
                    "normalized_answer": f"{a.get('state_before')}→{a.get('state_after')}; then {b.get('state_before')}→{b.get('state_after')}",
                    "gold_answer": None,
                    "answer_status": "ANSWER_PENDING",
                    "answer_derivation": "Derived from recorded overlay state_before/after; attack origins NOT claimed",
                    "mechanism": "ordered_state_transitions",
                    "provisional_answer_zh": f"先 {a.get('state_after')}，后 {b.get('state_after')}",
                    "development_control": True,
                }
            )
        elif rtype == "late_name_condition_early_attribute":
            color = "红色"
            if "red" in (a.get("object") or "") or a.get("state_before") == "red_jacket":
                color = "红色"
            drafts.append(
                {
                    **base,
                    "question_zh": "后来画面用姓名/成绩类字幕介绍的那位蓝黄色比赛服运动员，在较早的场边准备阶段先脱下了什么颜色的外套？",
                    "normalized_answer": "red_outer_jacket",
                    "gold_answer": None,
                    "answer_status": "ANSWER_PENDING",
                    "answer_derivation": "Requires identity hypothesis across late overlay and early garment events",
                    "mechanism": "reverse_name_to_early_garment",
                    "provisional_answer_zh": f"{color}外套",
                    "counterfactual_probe": "若晚段运动员不是早段脱外套者，答案应拒答",
                    "distractors_with_rationale": [
                        {"text": "黑色外套", "why": "另一运动员可能穿深色"},
                        {"text": "未脱外套", "why": "仅擦脸未脱衣的局部片段"},
                    ],
                }
            )
        elif rtype == "event_boundary_identity_contrast":
            # Bind names/countries ONLY from cited event objects
            name_a = _name_from_obj(a.get("object") or "")
            name_b = _name_from_obj(b.get("object") or "")
            c_a = _country_from_obj(a.get("object") or "")
            c_b = _country_from_obj(b.get("object") or "")
            if not name_a or not name_b:
                drafts.append(
                    {
                        **base,
                        "question_zh": "较早介绍字幕中的运动员，与后来 START LIST 中列出的运动员，是否为同一人？请写出两处可见姓名。",
                        "normalized_answer": None,
                        "gold_answer": None,
                        "answer_status": "ANSWER_PENDING",
                        "answer_derivation": "Names not parseable from cited events — leave pending",
                        "mechanism": "heat_boundary_name_contrast",
                        "provisional_answer_zh": None,
                        "development_control": True,
                    }
                )
            else:
                same = name_a.lower() == name_b.lower()
                drafts.append(
                    {
                        **base,
                        "question_zh": (
                            f"较早介绍字幕中的{(c_a or '')}运动员与后来 START LIST 中的{(c_b or '')}运动员是同一人吗？"
                            f"两处姓名分别是什么？"
                        ).replace("  ", " "),
                        "normalized_answer": f"{'yes' if same else 'no'}; {name_a} vs {name_b}",
                        "gold_answer": None,
                        "answer_status": "ANSWER_PENDING",
                        "answer_derivation": f"From cited objects: {a.get('object')} vs {b.get('object')}; START LIST ≠ results",
                        "mechanism": "heat_boundary_name_contrast",
                        "provisional_answer_zh": (
                            f"{'是' if same else '不是'}；早先 {name_a}，名单 {name_b}"
                        ),
                        "development_control": True,
                    }
                )
        elif rtype == "same_local_actor_nonadjacent":
            drafts.append(
                {
                    **base,
                    "question_zh": (
                        f"较早片段中可见动作「{a.get('verb')}」与较晚片段中「{b.get('verb')}」"
                        f"是否由画面中同一可跟踪人物完成？（仅依据已记录事件，勿臆造身份）"
                    ),
                    "normalized_answer": None,
                    "gold_answer": None,
                    "answer_status": "ANSWER_PENDING",
                    "answer_derivation": "Local track reuse; cross-cut identity not proven — no internal tokens in question",
                    "mechanism": "same_local_actor_temporal",
                    "provisional_answer_zh": None,
                }
            )
        elif rtype == "slide_speech_grounding_hypothesis":
            drafts.append(
                {
                    **base,
                    "question_zh": "讲者在展示基础设施/安全相关幻灯后，口头回答是否对应其中某一问题？具体内容是什么？",
                    "normalized_answer": None,
                    "gold_answer": None,
                    "answer_status": "ANSWER_PENDING",
                    "answer_derivation": "Requires audio; currently AUDIO_NOT_AUDITED",
                    "mechanism": "slide_speech_av_grounding",
                    "uncertainty": list(base["uncertainty"]) + ["audio_required"],
                    "provisional_answer_zh": None,
                }
            )
        elif rtype == "cross_shot_narrative_hypothesis":
            drafts.append(
                {
                    **base,
                    "question_zh": "室内人物片段与之后城市航拍之间是否存在可核实的地点/叙事因果关系？",
                    "normalized_answer": None,
                    "gold_answer": None,
                    "answer_status": "ANSWER_PENDING",
                    "answer_derivation": "Place/causality unknown — keep as uncertain draft",
                    "mechanism": "cross_shot_narrative",
                    "provisional_answer_zh": "UNKNOWN",
                }
            )
        elif rtype == "cross_scene_attribute_contrast":
            loc_a = a.get("location") or "场景A"
            loc_b = b.get("location") or "场景B"
            sum_a = a.get("summary_zh") or a.get("object") or a.get("verb")
            sum_b = b.get("summary_zh") or b.get("object") or b.get("verb")
            drafts.append(
                {
                    **base,
                    "question_zh": (
                        f"按文件时间顺序，较早在「{loc_a}」可见的内容与较晚在「{loc_b}」可见的内容有何不同？"
                        f"（请依据两段画面，勿编造因果）"
                    ),
                    "normalized_answer": f"{sum_a} || {sum_b}",
                    "gold_answer": None,
                    "answer_status": "ANSWER_PENDING",
                    "answer_derivation": "Attribute contrast from new frame observations; causality not claimed",
                    "mechanism": "cross_scene_attribute_contrast",
                    "provisional_answer_zh": f"早：{sum_a}；晚：{sum_b}",
                    "distractors_with_rationale": [
                        {"text": "两段为同一地点连续镜头", "why": "locations differ in recorded events"},
                    ],
                }
            )
        else:
            drafts.append(
                {
                    **base,
                    "question_zh": "根据两段已记录事件，二者存在何种跨时间关系？（勿臆造未记录事实）",
                    "normalized_answer": None,
                    "gold_answer": None,
                    "answer_status": "ANSWER_PENDING",
                    "answer_derivation": "Generic relation draft",
                    "mechanism": rtype,
                }
            )

    # Family-level then semantic dedup + binding gate
    seen_fam: set[str] = set()
    unique: list[dict[str, Any]] = []
    for d in drafts:
        fam = d["evidence_family"]
        if fam in seen_fam:
            d = {**d, "duplicate_of_family": True, "retained_as_independent_sample": False, "dedup_reason": "same_fact_id_family"}
        else:
            seen_fam.add(fam)
            d = {**d, "duplicate_of_family": False, "retained_as_independent_sample": True}
        unique.append(d)

    unique = apply_semantic_dedup(unique)
    unique = apply_binding_gate(unique, events_by_id)
    # Quarantined / binding errors cannot be independent samples
    for d in unique:
        if d.get("generation_error") or d.get("funnel_level") == "REJECTED_OR_QUARANTINE":
            d["retained_as_independent_sample"] = False
    return unique
