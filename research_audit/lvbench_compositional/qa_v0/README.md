# LVBench Compositional QA v0

从 LVBench 官方 `video_info.meta.jsonl` 构造组合题候选，供人工审查。不修改 Video-RSI，不调用模型，不划分 Seen/Unseen。

## 复现

在仓库根目录执行：

```bash
python3 tools/lvbench_comp/build_comp_qa.py \
  --metadata /home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl \
  --output-dir research_audit/lvbench_compositional/qa_v0
```

选项解析复用 `prepare_lvbench.split_question`。时间解析复用 `tools/lvbench_comp/extract_evidence.parse_time_reference`。

测试：

```bash
python3 tools/lvbench_comp/test_build_comp_qa.py
```

## 规则

同一视频内，只有下面三类配对会出题：

1. `entity_binding`：人名题的正确选项整词出现在另一题的题干或正确答案里。
2. `object_binding`：一题答案是寻找 his/her/their X，另一题答案是同一 X 被某人 has。
3. `temporal_event`：同名人物的衣服颜色题，和至少 30 秒之后的另一道事件题。

所有 `review_status` 都是 `PENDING_REVIEW`。`video_verified` 固定为 false。
