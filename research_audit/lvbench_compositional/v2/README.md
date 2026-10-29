# LVBench Compositional Generalization v2

```bash
python3 tools/lvbench_comp/build_comp_qa_v2.py \
  --metadata /home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl \
  --clean research_audit/lvbench_compositional/qa_v1_clean/candidates.jsonl \
  --pending research_audit/lvbench_compositional/qa_v1/candidate_pairs_pending.jsonl \
  --sample-review research_audit/lvbench_compositional/v2/sample_review.csv \
  --output-dir research_audit/lvbench_compositional/v2
```

测试：

```bash
python3 tools/lvbench_comp/test_build_comp_qa_v2.py
```

不覆盖 `qa_v0`、`qa_v1`、`qa_v1_clean`。媒体文件仍只在本地忽略目录。
