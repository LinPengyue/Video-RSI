# Video-Grounded Evidence Pilot

`SHARED_INFRASTRUCTURE` evidence preparation for `identify_person + query_action`.

```bash
python3 tools/lvbench_comp/prepare_video_grounded_evidence.py
```

- Indexes: `evidence_candidates.jsonl`, `video_selection.csv`, `review_manifest.json`, `REPORT.md`
- Dual-track fields: `applicable_track`, `composition_signature`, `primitive_operations`, `evidence_dependency`, `single_clip_shortcut_risk`, `annotation_scalability_notes`, `data_partition_status=UNASSIGNED`
- Media (gitignored): `local_media/`
- ChatGPT upload pack: `local_media/lvbench_video_grounded_3videos.zip`

Track tags are potential-use labels only. Do not treat candidates as SUPPORTED or as formal A/B splits without human review.
