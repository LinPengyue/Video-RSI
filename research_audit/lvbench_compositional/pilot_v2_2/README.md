# Pilot v2.2

```bash
python3 tools/lvbench_comp/build_pilot_v2_2.py \
  --candidates research_audit/lvbench_compositional/v2/candidates.jsonl \
  --pilot-split research_audit/lvbench_compositional/v2_1/pilot_split.json \
  --output-dir research_audit/lvbench_compositional/pilot_v2_2 \
  --judgments research_audit/lvbench_compositional/pilot_v2_2/judgments.json
```

可选 `judgments.json` 写入人工看片结论。没有判断时，测试题保持 `PENDING_HUMAN_REVIEW`。
媒体在 `local_media/`，已被 git 忽略。
