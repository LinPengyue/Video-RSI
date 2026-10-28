# LVBench Compositional QA v1

从官方 `video_info.meta.jsonl` 构造组合题候选。v0 的 30 道题保留在 `qa_v0/`，这里不覆盖。

完整候选必须改写问句，并且不能把需要组合才能得到的中间实体直接写进题干。做不到可靠改写的配对记为 `NEEDS_HUMAN_DRAFT`，不计入完整数量。

## 复现

在仓库根目录执行：

```bash
python3 tools/lvbench_comp/build_comp_qa_v1.py \
  --metadata /home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl \
  --v0 research_audit/lvbench_compositional/qa_v0/candidates.jsonl \
  --output-dir research_audit/lvbench_compositional/qa_v1
```

解析复用 `prepare_lvbench.split_question` 和 v0 的时间窗过滤。不调用模型，不划分 Seen/Unseen。

测试：

```bash
python3 tools/lvbench_comp/test_build_comp_qa_v1.py
```
