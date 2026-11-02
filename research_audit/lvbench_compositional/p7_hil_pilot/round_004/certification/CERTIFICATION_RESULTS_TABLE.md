# P7 Certification Results Table (first structure+necessity pass)

**Leave-out definition frozen:** `STRUCTURE_LEAVEOUT_DEFINITION_V1.json` (before necessity outcomes).  
**Necessity blind adjudication:** **NOT_EXECUTED** — Cursor/GPT already saw answers; recorded as `PENDING_INDEPENDENT_REVIEW`. Heuristic shortcut notes are **not** passes.  
**Formal Gold / qualified families:** **0**.

## Composition & structure candidates

| qa_id | video_id | directed_program | isomorphic_to_sierra_seen_unseen_target | temporary_structure_role | meets_first_study_unseen_signature | a_only | b_only | a_plus_b | evidence_answer_reliable | final_conclusion |
|---|---|---|---|---|---|---|---|---|---|---|
| P7_VTCD_C4 | VTCDQYYKA9o | ORDER_TWO_INTERVAL_EVENTS | False | RELATED_STRUCTURE_NOT_FIRST_STUDY_UNSEEN_TARGET | False | NOT_EXECUTED | NOT_EXECUTED | NOT_EXECUTED | USER_EVENT+IDENTITY_ACCEPTED; QA candidate accepted; answer from candidate sketch+user facts | 待证_相关结构_非本轮Unseen目标签名 |
| P7_VTCD_C2 | VTCDQYYKA9o | IDENTIFY_PERSON → BIND_SAME_ENTITY_CROSS_INTERVAL → QUERY_ACTION_OTHER_INTERVAL | True | UNSEEN_TARGET_STRUCTURE_CANDIDATE | True | NOT_EXECUTED | NOT_EXECUTED | NOT_EXECUTED | USER_EVENT+IDENTITY; candidate accepted; A also has Fan text → A-only risk | 待证_结构符合Unseen目标_必要性未独立执行 |
| P7_TJR_R3 | TJR1oYDDTwg | IDENTIFY_PERSON → BIND_SAME_ENTITY_CROSS_INTERVAL → QUERY_ATTRIBUTE_OTHER_INTERVAL | False | RELATED_STRUCTURE_NOT_FIRST_STUDY_UNSEEN_TARGET | False | NOT_EXECUTED | NOT_EXECUTED | NOT_EXECUTED | USER_CONFIRMED_REVISED_QA | 待证_相关结构_非本轮Unseen目标签名 |
| P7_R4_F1 | Cm73ma6Ibcs | IDENTIFY_PERSON → BIND_SAME_ENTITY_CROSS_INTERVAL → QUERY_ACTION_OTHER_INTERVAL | True | UNSEEN_TARGET_STRUCTURE_CANDIDATE | True | NOT_EXECUTED | NOT_EXECUTED | NOT_EXECUTED | USER_CONFIRMED_REVISED_QA | 待证_结构符合Unseen目标_必要性未独立执行 |
| P7_R4_F2 | LLSJrEgOOtw | IDENTIFY_ANIMAL → BIND_SAME_ENTITY_CROSS_INTERVAL → QUERY_ACTION_OTHER_INTERVAL | False | RELATED_STRUCTURE_NOT_FIRST_STUDY_UNSEEN_TARGET | False | NOT_EXECUTED | NOT_EXECUTED | NOT_EXECUTED | USER_CONFIRMED_REVISED_QA | 待证_相关结构_非本轮Unseen目标签名 |
| P7_R4_F3 | Z86xysw5Ncc | IDENTIFY_PERSON → BIND_SAME_ENTITY_CROSS_INTERVAL → QUERY_ATTRIBUTE_OTHER_INTERVAL | False | RELATED_STRUCTURE_NOT_FIRST_STUDY_UNSEEN_TARGET | False | NOT_EXECUTED | NOT_EXECUTED | NOT_EXECUTED | USER_CONFIRMED; literal Q incomplete; B may show winner directly | 待证_相关结构_非本轮Unseen目标签名 |
| P7_R4_F4 | xi6r3hZe5Tg | IDENTIFY_OBJECT_OR_ATTRIBUTE → RELATE_TWO_SCENES_NONCAUSAL | False | HOLD_NO_GOLD_PATH | False | NOT_APPLICABLE_HELD | NOT_APPLICABLE_HELD | NOT_APPLICABLE_HELD | USER_ACCEPT but EDIT_JUXTAPOSITION vs causal/reference conflict unresolved | 失败_暂缓Gold路径 |

## Calibration + Seen primitive rows (leakage)

| qa_id | video_id | directed_program | isomorphic_to_sierra_seen_unseen_target | temporary_structure_role | meets_first_study_unseen_signature | a_only | b_only | a_plus_b | evidence_answer_reliable | final_conclusion |
|---|---|---|---|---|---|---|---|---|---|---|
| TA_LVCOMP-V2-002 | JTa_Ue2MSwc | IDENTIFY_PERSON → BIND_SAME_ENTITY_CROSS_INTERVAL → QUERY_ACTION_OTHER_INTERVAL | True | UNSEEN_TARGET_STRUCTURE_CANDIDATE | True | NOT_REQUIRED_FOR_THIS_ROW | NOT_REQUIRED_FOR_THIS_ROW | NOT_REQUIRED_FOR_THIS_ROW | USER/TrackA_SUPPORTED | 待证_结构符合Unseen目标_必要性未独立执行 |
| TA_LVCOMP-V2-003 | JTa_Ue2MSwc | IDENTIFY_PERSON → BIND_SAME_ENTITY_CROSS_INTERVAL → QUERY_ACTION_OTHER_INTERVAL | True | UNSEEN_TARGET_STRUCTURE_CANDIDATE | True | NOT_REQUIRED_FOR_THIS_ROW | NOT_REQUIRED_FOR_THIS_ROW | NOT_REQUIRED_FOR_THIS_ROW | USER/TrackA_SUPPORTED | 待证_结构符合Unseen目标_必要性未独立执行 |
| P7_R4_S1 | JTa_Ue2MSwc | IDENTIFY_PERSON | False | SEEN_PRIMITIVE_OK_BUT_VIDEO_ALSO_HAS_SIERRA_COMPOSITION_CALIBRATION | False | NOT_REQUIRED_FOR_THIS_ROW | NOT_REQUIRED_FOR_THIS_ROW | NOT_REQUIRED_FOR_THIS_ROW | USER_ACCEPT | 待证_Seen原语候选_未冻结分割 |
| P7_R4_S2 | JTa_Ue2MSwc | QUERY_ACTION_OTHER_INTERVAL | False | SEEN_PRIMITIVE_OK_BUT_VIDEO_ALSO_HAS_SIERRA_COMPOSITION_CALIBRATION | False | NOT_REQUIRED_FOR_THIS_ROW | NOT_REQUIRED_FOR_THIS_ROW | NOT_REQUIRED_FOR_THIS_ROW | USER_ACCEPT | 待证_Seen原语候选_未冻结分割 |
| P7_R4_S3 | T1yhBv1ytzw | IDENTIFY_OBJECT_OR_ATTRIBUTE | False | SEEN_PRIMITIVE_CANDIDATE | False | NOT_REQUIRED_FOR_THIS_ROW | NOT_REQUIRED_FOR_THIS_ROW | NOT_REQUIRED_FOR_THIS_ROW | USER_ACCEPT | 待证_Seen原语候选_未冻结分割 |
| P7_R4_S4 | VTCDQYYKA9o | IDENTIFY_PERSON | False | SEEN_PRIMITIVE_BLOCKED_SAME_VIDEO_AS_UNSEEN_TARGET_CANDIDATE | False | NOT_REQUIRED_FOR_THIS_ROW | NOT_REQUIRED_FOR_THIS_ROW | NOT_REQUIRED_FOR_THIS_ROW | USER_ACCEPT | 失败_视频泄漏_不可作Train原语 |

## Stats

```json
{
  "formal_qualified_families": 0,
  "formal_gold": 0,
  "formal_seen_split_frozen_count": 0,
  "formal_unseen_necessity_passed_count": 0,
  "temporary_unseen_target_structure_candidates": 4,
  "independent_videos_touching_unseen_target_candidates": [
    "Cm73ma6Ibcs",
    "JTa_Ue2MSwc",
    "VTCDQYYKA9o"
  ],
  "necessity_blind_executed": false,
  "necessity_reason": "Adjudicator contamination (Cursor/GPT know answers). Packets prepared for independent reviewer.",
  "track_a_restart_gate": {
    "need_unseen_items": 6,
    "have_formal_unseen": 0,
    "need_unseen_videos": 3,
    "have_formal_unseen_videos": 0,
    "need_seen_query_action_items_videos": "4 items / 3 videos",
    "need_seen_identify_person_items_videos": "8 items / 4 videos",
    "status": "BLOCKED",
    "gap": "0 formal Unseen after this round because necessity NOT_EXECUTED; structure leave-out V1 frozen; S4 blocked from train if VTCD compositions are test; TJR lacks Seen attribute primitive; F2 not first-study Unseen signature; F3/C4 related not target signature"
  }
}
```

## Independent packets

Under `independent_review_packets/` — question + clip paths only; answers only in `ANSWER_KEYS_DO_NOT_SERVE_TO_REVIEWER.json`.
