# LVBench Compositional QA v1

这些是可人工审查的候选，不是已经通过视频核验的 Benchmark 测试题。每道题的 `video_verified` 都是 false，`review_status` 都是 `PENDING_REVIEW`。

## 漏斗

- 扫描的同视频 QA 对：11470。
- 初步语义关联配对：72。判定标准是官方答案里的同一个专名或名词短语，或“寻找某物 / 某人持有该物”。普通词共现没有算进来。
- 完整生成的新组合 QA：45。
- 仍需人工编写：40。这些配对在 `candidate_pairs_pending.jsonl`，状态是 `NEEDS_HUMAN_DRAFT`，不计入完整候选。
- 完整候选覆盖视频：20。
- 相对 v0 新增的来源配对：19。

## 四种类型

- `entity_binding` 人物：16。
- `object_binding` 物体：1。
- `event_binding` 动作／事件：21。
- `attribute_binding` 属性／关系：7。

## 为什么不是大约 100 道

v0 只有 30 道，主要是因为脚本要求一道题的正确答案必须是人名，并且优先做字符串替换。放宽到“答案实体出现在另一道题里”之后，全库 1,549 道题里能这样连起来的同视频配对仍然只有上面的初步筛选数量。其中一部分问法不能在不虚构动作的前提下自动改写，所以完整候选少于 100。没有用 and 拼接无关题目来补数量。

## 相对 v0 的处理

- 保留：16。
- 修改：1。
- 反向改写后重新生成：9。
- 删除：4。

只改答案、没有新问题的 v0 题，能反向提问的改成了属性题，例如脱衣舞者。只把 Sonny 换成 the vlogger 的题已删除。物体题不再把被寻找的物品写进题干。

同一道官方 UID 仍可能出现在多道候选里。审查时按题独立看。

## 样例

### LVCOMP-V1-001 `entity_binding` `Hf-n1yfd8II`

- UIDs: 3934, 3944
- 新问题: How to describe the feeling of the final winner at 48:16?
- 新答案: He feels frustrated because he does not catch the shuttlecock from the opponent

### LVCOMP-V1-017 `object_binding` `q01CUy_gwdU`

- UIDs: 120, 121
- 新问题: After they meet for the third time, who has the item the man searched for after the second collision?
- 新答案: the woman in red

### LVCOMP-V1-018 `event_binding` `2zkJFv-ro4A`

- UIDs: 3132, 3119
- 新问题: What is the relation beween the person who performs a solo after Seungri does and Kange Dae Sung?
- 新答案: They are team members

### LVCOMP-V1-039 `attribute_binding` `2zkJFv-ro4A`

- UIDs: 3118, 3123
- 新问题: Who is the person the vloggers see from the BigBang after the concert ends?
- 新答案: the man appearing on the screen from 01:38-01:40

### LVCOMP-V1-002 `entity_binding` `JTa_Ue2MSwc`

- UIDs: 5130, 5131
- 新问题: What does the first interview do after her former roommate comes to the stage?
- 新答案: She takes off her shoes

### LVCOMP-V1-003 `entity_binding` `JTa_Ue2MSwc`

- UIDs: 5130, 5134
- 新问题: What does the first interview do after the first male guest show up on the stage?
- 新答案: She slaps the man

### LVCOMP-V1-004 `entity_binding` `JTa_Ue2MSwc`

- UIDs: 5130, 5135
- 新问题: Who cheats on the first interview with Kindall?
- 新答案: David

### LVCOMP-V1-005 `entity_binding` `JTa_Ue2MSwc`

- UIDs: 5130, 5137
- 新问题: What is the name of the first interview's former roommate?
- 新答案: Kindall

逐题来源见 `candidates.jsonl`。v0 的去留见 `v0_to_v1_review.csv`。
