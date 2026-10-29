# Video-Grounded Evidence Pilot

Evidence preparation only for `identify_person + query_action`.

```bash
python3 tools/lvbench_comp/prepare_video_grounded_evidence.py
```

- Indexes: `evidence_candidates.jsonl`, `video_selection.csv`, `review_manifest.json`, `REPORT.md`
- Media (gitignored): `local_media/`
- ChatGPT upload pack: `local_media/lvbench_video_grounded_3videos.zip`

Do not treat candidates as SUPPORTED without human video review.
