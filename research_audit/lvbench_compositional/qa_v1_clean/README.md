# LVBench Compositional QA v1.1 clean

整理 `qa_v1/candidates.jsonl` 的 45 道题。不覆盖 v0 或 v1，不新增组合配对。

```bash
python3 tools/lvbench_comp/clean_comp_qa_v1.py \
  --input research_audit/lvbench_compositional/qa_v1/candidates.jsonl \
  --output-dir research_audit/lvbench_compositional/qa_v1_clean
```

测试：

```bash
python3 tools/lvbench_comp/test_clean_comp_qa_v1.py
```

视频片段写在 `qa_v1_clean/local_media/`，该目录被 git 忽略。索引 `video_evidence_index.json` 只记录路径、哈希和时间，不判断视频事实。

```bash
python3 tools/lvbench_comp/extract_v1_clean_evidence.py \
  --candidates research_audit/lvbench_compositional/qa_v1_clean/candidates.jsonl \
  --media-root research_audit/lvbench_compositional/qa_v1_clean/local_media \
  --index research_audit/lvbench_compositional/qa_v1_clean/video_evidence_index.json
```

本轮抽了 10 道、10 个视频。012 和 017 复用 Phase 1 里哈希一致的片段。另外加上 008，避免和 043 重复使用同一个视频。
