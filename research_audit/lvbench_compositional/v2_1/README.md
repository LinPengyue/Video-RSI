# LVBench Compositional Generalization v2.1

严格 Novel Composition Pilot。不新增候选，不重抽视频。

```bash
python3 tools/lvbench_comp/build_comp_qa_v2_1.py \
  --candidates research_audit/lvbench_compositional/v2/candidates.jsonl \
  --sample-review research_audit/lvbench_compositional/v2/sample_review.csv \
  --output-dir research_audit/lvbench_compositional/v2_1
```

测试：

```bash
python3 tools/lvbench_comp/test_build_comp_qa_v2_1.py
```
