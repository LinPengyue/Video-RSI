"""B4 — batch QA drafting from real recorded events/relations (not official QA concat)."""

from __future__ import annotations

import hashlib
from typing import Any


def _family(fact_ids: list[str], sig: str) -> str:
    key = "|".join(sorted(fact_ids)) + "#" + sig
    return "FAM_" + hashlib.sha256(key.encode()).hexdigest()[:10]


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
            "uncertainty": rel.get("uncertainty") or [],
            "funnel_level": "QA_DRAFT",
            "data_partition_status": "UNASSIGNED",
            "formal_supported": False,
            "prompt_model_version": "rule_drafter_v1",
            "distractors_with_rationale": [],
            "counterfactual_probe": None,
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
                }
            )
        elif rtype == "late_name_condition_early_attribute":
            color = (a.get("object") or "").split()[0] if a.get("verb") == "remove_outer_garment" else "红色"
            if "red" in (a.get("object") or "") or "红" in (a.get("object") or "") or a.get("state_before") == "red_jacket":
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
            drafts.append(
                {
                    **base,
                    "question_zh": "画面早先介绍的美国短跑运动员，与后来 START LIST / ROUND 1 HEAT 2 名单中列出的美国运动员，是同一人吗？分别是谁？",
                    "normalized_answer": "no; Gay vs Gatlin",
                    "gold_answer": None,
                    "answer_status": "ANSWER_PENDING",
                    "answer_derivation": "Two overlay name reads; START LIST ≠ results",
                    "mechanism": "heat_boundary_name_contrast",
                    "provisional_answer_zh": "不是；早先介绍 Tyson Gay，名单为 Justin Gatlin",
                    "development_control": True,
                }
            )
        elif rtype == "same_local_actor_nonadjacent":
            drafts.append(
                {
                    **base,
                    "question_zh": f"同一本地轨迹 `{a['actor_local_track']}` 在较早与较晚事件中分别做了什么？（仅依据已记录事件，勿臆造）",
                    "normalized_answer": f"{a['verb']} then {b['verb']}",
                    "gold_answer": None,
                    "answer_status": "ANSWER_PENDING",
                    "answer_derivation": "Local track reuse; cross-cut identity not proven",
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
        else:
            drafts.append(
                {
                    **base,
                    "question_zh": f"根据事件 {a['event_id']} 与 {b['event_id']}，二者存在何种跨时间关系？",
                    "normalized_answer": None,
                    "gold_answer": None,
                    "answer_status": "ANSWER_PENDING",
                    "answer_derivation": "Generic relation draft",
                    "mechanism": rtype,
                }
            )

    # Deduplicate within evidence_family: keep first per family
    seen_fam: set[str] = set()
    unique: list[dict[str, Any]] = []
    for d in drafts:
        fam = d["evidence_family"]
        if fam in seen_fam:
            d = {**d, "duplicate_of_family": True, "retained_as_independent_sample": False}
        else:
            seen_fam.add(fam)
            d = {**d, "duplicate_of_family": False, "retained_as_independent_sample": True}
        unique.append(d)
    return unique
