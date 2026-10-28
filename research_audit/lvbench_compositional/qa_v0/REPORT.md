# LVBench Compositional QA Dataset v0

这些题目全部是 `PENDING_REVIEW`。它们由官方标注里的名字或所属物对应关系推出，没有看片核实，也没有 Seen/Unseen 划分。

## 规模

- 官方 QA：1549，视频 103 个。
- 候选题：30。
- 覆盖视频：11。
- `entity_binding`：28。
- `object_binding`：1。
- `temporal_event`：1。

## 为什么不是把关键词撞在一起

- 人物题：一道题的正确答案是人名，另一道题的题干或正确答案按整词用了这个名字。问法把名字换成前一道题里的指称。
- 物体题：一道正确答案是 “looks/searches for his/her X”，另一道正确答案是同一所有格的 “has his/her X”。只写成持有，不写成捡起。
- 时间题：同名人物先有一条衣服颜色标注，后有一条间隔至少 30 秒的事件题。颜色用来回指这个人，后题提供答案。
- 同一标识最多保留 4 道人物题。题干里出现名字的配对优先；另一道题本身又是人名题的配对靠后。时间窗互相重叠、起点相距不足 10 秒、超过 12 分钟、无法解析，以及 Will/May 这类兼类词，都丢掉。
- “What is the first interview's name?” 这类以 name 结尾的人名题，和 “What is the name of …” / “Who is …” 一样作为人物标识。
- 只共享 video、the、man 这类普通词的题目不会进入候选。

## 需要人工确认

- 同名是否真是同一个人，尤其是后题已经写出名字时，前一段画面是否还必要。
- 物体题里的持有人是否能只靠后一个片段看出来。
- 自动替换后人名问法可能生硬，审查时可以改写，但不能改到来源标注支持不了的动作。原始问法里的语法错误会保留。
- 时间题只证明官方时间戳的先后和名字字符串相同。
- 物体题和衣服颜色时间题在全库里各只有一对满足规则，所以这两类数量少。
- 同一道官方 UID 可以出现在多道候选里。例如酒店邀请同时连到“加入旅途的老人”和“第一天穿绿色衣服的人”，作弊事件同时连到 Sierra 和 Kindall。审查时按题独立看，不要把共享来源当成两份独立证据。

目标区间是 30–50。能同时满足“两个官方 QA、同一视频、答案可由标注推出、而且不是用并且把两题拼起来”的配对，经过去重和每名最多 4 题之后，就是规模一节里的数量。共享普通词、时间窗重叠、超长时间窗的配对没有补进去。

## 题干没有改写的题

下面这些题的问句仍是后一道官方题的题干，只把正确答案里的人名换成了前一道题的指称。审查时要确认：用指称作答是否不会和人名答案混淆。

LVCOMP-V0-001, LVCOMP-V0-002, LVCOMP-V0-003, LVCOMP-V0-005, LVCOMP-V0-012, LVCOMP-V0-013, LVCOMP-V0-016, LVCOMP-V0-018, LVCOMP-V0-024, LVCOMP-V0-027, LVCOMP-V0-028

## 样例

### LVCOMP-V0-020 `entity_binding` `_T2Avd3tFHc`

- UIDs: 2873, 2890
- 时间: 04:44-04:44 || 15:58-16:07
- 新问题: Where do the vlogger team members invite the elder who joins the vlogger on their travel on the first night?
- 新答案: They invite the elder who joins the vlogger on their travel to the hotel

### LVCOMP-V0-029 `object_binding` `q01CUy_gwdU`

- UIDs: 120, 121
- 时间: 04:42-05:00 || 05:15-05:31
- 新问题: Who has the book that the man looks for after the second collision, after they meet for the third time?
- 新答案: the woman in red

### LVCOMP-V0-030 `temporal_event` `_T2Avd3tFHc`

- UIDs: 2877, 2890
- 时间: 04:05-04:25 || 15:58-16:07
- 新问题: Where do the vlogger team members invite the person wearing Green on the first day on the first night?
- 新答案: They invite the person wearing Green on the first day to the hotel

### LVCOMP-V0-001 `entity_binding` `2zkJFv-ro4A`

- UIDs: 3118, 3123
- 时间: 01:38-01:40 || 33:49-34:04
- 新问题: Who does the vlogger see from the BigBang after the concert ends?
- 新答案: the man appearing on the screen from 01:38-01:40

### LVCOMP-V0-002 `entity_binding` `Hf-n1yfd8II`

- UIDs: 3919, 3944
- 时间: 08:30-08:35 || 90:13-90:40
- 新问题: Who serves first?
- 新答案: the final winner

### LVCOMP-V0-006 `entity_binding` `JTa_Ue2MSwc`

- UIDs: 5130, 5131
- 时间: 00:29-01:36 || 02:08-02:11
- 新问题: What does the first interview do after her former roommate comes to the stage?
- 新答案: She takes off her shoes

### LVCOMP-V0-014 `entity_binding` `QWXlvx1GoTY`

- UIDs: 2463, 2465
- 时间: 42:12-42:35 || 51:15-53:23
- 新问题: The second person to speak on stage shows a video about what brand during his talk?
- 新答案: L'Oreal

### LVCOMP-V0-015 `entity_binding` `VTCDQYYKA9o`

- UIDs: 4083, 4092
- 时间: 03:00-03:00 || 41:50-50:50
- 新问题: How many points does the person in the video wearing red clothes and then taking them off to reveal the blue clothes underneath score in the fourth game?
- 新答案: 9

### LVCOMP-V0-017 `entity_binding` `Z86xysw5Ncc`

- UIDs: 4197, 4199
- 时间: 02:18-02:36 || 03:46-04:25
- 新问题: What's the number on the back of the winner for Men's 100M Round 1 Heat 1?
- 新答案: 3217

### LVCOMP-V0-022 `entity_binding` `cWEnogdsW78`

- UIDs: 4062, 4071
- 时间: 03:29-03:59 || 16:56-17:00
- 新问题: What is the hair color of the one who is on the right side of the screen after the ground move in the third round?
- 新答案: All white

完整列表见 `candidates.jsonl`。
