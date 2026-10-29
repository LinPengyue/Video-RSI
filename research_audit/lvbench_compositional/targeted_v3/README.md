# Targeted Compositional QA v3

```bash
python3 tools/lvbench_comp/build_targeted_comp_v3.py \
  --v2-candidates research_audit/lvbench_compositional/v2/candidates.jsonl \
  --v22-test-review research_audit/lvbench_compositional/pilot_v2_2/test_video_review.csv \
  --output-dir research_audit/lvbench_compositional/targeted_v3

python3 tools/lvbench_comp/extract_targeted_v3_sample_media.py
python3 -m unittest tools.lvbench_comp.test_build_targeted_comp_v3 -v
```

媒体目录 `local_media/` 被 git 忽略。
