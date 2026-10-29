# CG-NEW 原始设计与 Cursor 回填校准（2026-10-29）

来源：ChatGPT 当前会话生成的 `canonical_qa_proposals.jsonl`（五条，`id` 为主键）。

## 优先级和映射（不应被简报回退值覆盖）

| ID | 原始 seed | 机制 | 原始题目（中文精确文本） |
|---|---|---|---|
| CG-NEW-001 | TB-003 | contrastive_role_alignment | 后来的舞台表演中，一个孩子打鼓、另一个孩子弹吉他。此前国王与绿龙交谈后拥抱国王的是哪一位演奏者？请同时说明其乐器。 |
| CG-NEW-002 | TB-007 | reverse_temporal_role_binding | 在雪地决斗中倒地并用雪擦脸的那名人物，先前在餐馆面对持枪者威胁厨师时，首先采取了哪种反应？ |
| CG-NEW-003 | TB-006 | audio_visual_reidentification_and_reverse_event_query | 后段在两个人采集坚果附近活动的黑白动物，先前独自出现在树林时在玩什么？其早期片段中还可听到什么动物声音？ |
| CG-NEW-004 | TB-005 | category_grounding_plus_process_sequence | 开场在海边展示的那类有大钳的甲壳动物，在后续料理镜头中经历了哪些可见的处理步骤，并最终被装入什么类型的食物？ |
| CG-NEW-005 | TB-004 | role_to_safety_sequence_with_identity_uncertainty | 此前在船舶操纵台操作的那名女船员离开舱内后，在甲板上先做了什么防护准备？ |

## 与 commit 85138431 的回填区别

- 当前 Cursor 回填把 CG-NEW-004 指向 TB-004（船员）；正确原始设计是 TB-005（龙虾料理）。
- 当前 Cursor 回填把 CG-NEW-005 指向 TB-001（老人去酒吧）；正确原始设计是 TB-004（船员防护准备）。
- CG-NEW-003 原始题目还需要狗叫声的独立音轨核验，不能把用户报告写成独立查验事实。
- CG-NEW-001 原始答案要求角色和乐器，不能只保留“鼓”的单实体答案。
- CG-NEW-004 原始文件标记 `PROPOSED_CONTROL_CANDIDATE`，CG-NEW-005 标记 `PROPOSED_EVIDENCE_REQUEST`，其余三项标记 `PROPOSED_REVIEW_REQUIRED`；不要把各种状态都无区别地变成事实确认。

## 导入要求

1. 不要覆盖此前 `candidate_id` 的回退记录：先保存为 `fallback_snapshot_85138431.jsonl` 或 Git 历史可追溯的版本，然后将原始 source 的五条作为 `canonical_chatgpt_proposals.jsonl` 导入。
2. 原始源数据字段 `id` 与已有 schema `candidate_id` 对应；`seed` 与 `linked_tb_id` 对应；`question_zh` 和 `provisional_answer_zh` 分别对应规范中的 `question` 与 `answer`，同时保留原文以避免误差。
3. `official_uids` 是来源线索，不代表画面已核验。 `risks` / `checks` / `evidence` / `composition_program` 必须完整保留。
4. 旧题全部 `data_partition_status=UNASSIGNED`；不能进入未来盲封终测。不要把 `PROPOSED` 自动升级为 `SUPPORTED`。
5. 导入后自动断言五条 `id -> seed` 一一对应，问题、答案、风险、状态完整，且来源哈希一致。
6. 文件只校准此前 ChatGPT 源设计；并不意味着本轮已独立审查 34.6 MB 新媒体。
