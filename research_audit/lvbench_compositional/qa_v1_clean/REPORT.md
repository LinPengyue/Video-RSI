# LVBench Compositional QA v1.1 clean

这一版只整理 v1 的 45 道候选，没有新增来源配对。任何题目都还不是正式有效题。

## 数量

- 原始候选：45。
- KEEP：15。
- REVISE：27。
- DROP：3。排除记录见 `excluded.csv`。
- 文本已按标注改完并进入审查集：19。
- `NEEDS_VERIFICATION`：3。016 的答案指向双人组合中的单人表演；026 和 028 的官方选项只有数字 5，没有写明是球衣号码。
- `HOLD_LABEL_BALANCE`：5。五道 Yes/No 题答案全是 Yes，未进入审查集，也没有伪造 No。
- 清洗后审查集：37。状态是 `PENDING_VIDEO_REVIEW` 或 `NEEDS_VERIFICATION`。
- 排除：3。
- 问法修订记录：23。

035 从 `event_binding` 改为 `attribute_binding`，因为它绑定的是第一天的衣着和后来的邀请地点。

视频事实没有在这里判断。
