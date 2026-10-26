# 附加能力：信息流反事实探针（可选）

在原有 observe / ocr / transcript / run_solver 之外，本会话额外提供**通用、可执行**的信息流反事实测试。
是否使用、用于哪些训练失败、如何解释结果，由你自主决定。

这些测试只比较**同一训练样本、同一时间戳集合**上的不同信息传递与回答方式，
帮助区分：失败更可能来自视觉证据获取、文字转写观察，还是最终选项推理。
它们**不是** Gate，也不是强制改架构的指令。

不要把探针结果写成“必须改成某种固定架构”；用证据说明可复用机制是否成立。

## 操作：`infoflow_probe`

```json
{
  "operation": "infoflow_probe",
  "sample_id": "TRAIN_ID",
  "question": "同一视觉证据下，换一种回答者是否改变选项？文字观察是否丢掉了关键线索？",
  "mode": "answerer_swap | vision_vs_text | observation_regen",
  "timestamps": [12.5, 40.0],
  "basis": "trajectory_review"
}
```

- `timestamps`：与原有 overview/inspect 对齐的秒级时间戳列表（必填）。
- `mode`：
  - `answerer_swap`：先得到一份文字观察，再分别用不同回答者在**相同文字**上作答，比较选项。
  - `vision_vs_text`：同一帧集合上比较「直接看帧回答」与「先文字观察再回答」。
  - `observation_regen`：比较缓存/既有文字观察与**重新生成**的文字观察（及随后回答是否变化）。

`prompt` 可选，仅影响文字观察生成，不得要求模型证明标准答案。

返回中会包含各分支的解析选项、是否可解析、帧数与用量；请写入 notes，并在综合报告中说明机制含义与不确定性。
