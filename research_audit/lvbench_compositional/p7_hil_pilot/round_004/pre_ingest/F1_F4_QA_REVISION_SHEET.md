# F1–F4 QA Revision Sheet (pre-ingest)

**Purpose:** Compact repair table for user-confirmed structure QAs.  
**Authority:** Raw + confirmed revision JSON only. Cursor does **not** approve wording.  
**Sources:**  
- `user_reviews/ROUND4_USER_REVIEW_2026-11-02_RAW.json`  
- `user_reviews/ROUND4_USER_CONFIRMED_QA_REVISION_2026-11-02.json`

| ID | Raw decision | Issue | Current candidate Q (user-confirmed where applicable) | Current candidate A | Open for user/ChatGPT | Ready for necessity batch? |
|----|--------------|-------|------------------------------------------------------|---------------------|------------------------|----------------------------|
| **F1** | ACCEPT → later confirmed revised Q/A | Original “对峙/持械的那个人”易指持枪坏人；raw 答案空 | **更早室内片段中穿蓝衣、戴白围巾、佩刀并前来解围的人，在后来的雪地中发生了什么？** | **被打倒在雪地上，并用雪擦脸。** | 是否冻结该措辞为唯一题面 | **Yes**（题面/答案已用户确认） |
| **F2** | REVISE | 原题指“穿蓝外套的人”；人太小；用户改动物目标；raw `answer` 实为修订题 | **更早雾林空地中出现的那只狗，在后来落叶林中做了什么？** | **与提着桶的女人打闹。** | 狗个体身份是否足够；`SAME_PERSON` 标签与狗目标并存需记录 | **Yes**（待必要性；身份风险保留） |
| **F3** | REVISE | 原题“姓名条那名运动员”指代不清；用户改美国运动员/第一名；字面 **「几名运动」** 不完整 | **更早片段中的几名运动，在后来的片段中哪个取得第一名？**（字面保留） | **美国运动员 Tyson Gay，深红色。背部号码可见 217。** | 是否批准润色「几名运动员」；B-only 捷径（后期直接见第一名） | **Conditional** — 建议先确认题面润色；否则可带字面题进必要性并记录 B-only 风险 |
| **F4** | ACCEPT（维持原判） | `EDIT_JUXTAPOSITION` vs 书面「参考/被参考」/因果叙述冲突；A/B 源窗重叠约 5s | **打印紫色网格的设备，与紧随其后的摆盘画面是什么关系？** | **参考与被参考关系** | 是否仍作组合题、负例或搁置；重叠剪辑建议未执行 | **No** — 因果未解，**不得**因 ACCEPT 升 Gold |

### History preserved (do not overwrite)

- F1 original Q + empty answer  
- F2 original human-target Q + animal revised-question-in-answer-field  
- F3 original name-bar Q + American-athlete revised-question-in-answer-field  
- F4 original relation label + answer + user note to keep original judgment  

### Not done by Cursor

- No silent polish of F3「几名运动」  
- No inventing F1/F2/F3 facts beyond user text  
- No `COMPOSITION_NECESSITY_VERIFIED` / Gold / Seen·Unseen assignment  
