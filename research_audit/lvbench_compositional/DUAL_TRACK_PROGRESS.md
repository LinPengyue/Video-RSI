# Dual-track progress update

Baseline: `791d25f9603a6533ef2ce0ee9e275430123ff667`

## Shared
- Registered CG-NEW-001..005 as PROPOSED / UNASSIGNED under `chatgpt_video_driven_qa/`
- Source label: CHATGPT_DESIGN_FROM_UPLOADED_EVIDENCE (official upload file missing → brief fallback; see IMPORT_STATUS.json)
- TB-001..007 preserved; not overwritten
- Contaminated for blind sealed final test

## Track A
- TECE prototype + unit tests
- Counterfactual assertions: {'missing_evidence_reported': True, 'binding_changes_query_target': True, 'single_clip_not_strong_success': True, 'failure_triggers_recovery': True}
- Isolation dry-check ok: True
- Expensive RSI: not run

## Track B
- Evidence pack: research_audit/lvbench_compositional/track_b/local_media/lvbench_cg_new_evidence_round.zip (34.55 MB)
- Extracted clips: 9; adjacent fact windows: 6
- No auto SUPPORTED
