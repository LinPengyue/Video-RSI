# Track B Production & Quality Report — `run_002`

Factory `0.2.0` / extractor `batch_factory_v2_2026-10-31`
Elapsed: 5.29s | partition: **UNASSIGNED** | formal_supported: **false** | ok_for_expensive_rsi: **false**

## Throughput
- Videos inventory: 8
- Processed OK/PARTIAL: 8
- MEDIA_UNAVAILABLE: 0
- EXTRACTION_FAILED: 0
- Genre: `{'documentary_travel': 1, 'tech_talk': 1, 'athletics': 1, 'table_tennis': 1, 'football_broadcast': 1, 'unlabeled_lvbench': 3}`

## Funnel (not SUPPORTED) — honest provenance
- Coarse frames: 88
- Curated semantic (fixtures): 13
- **New** agent/machine semantic: 9
- Relations: 17
- QA drafts: 17 | distinct Q: 16 | independent families: 9 | dup: 8 | quarantine: 1
- New relation families (from new obs): 3
- Grades (heuristic, not video-tested): `{'HEURISTIC_MEDIUM_NOT_VIDEO_TESTED': 2, 'HEURISTIC_LOW_NOT_VIDEO_TESTED': 1, 'SHORTCUT_CONTROL': 2, 'REJECT_HARD': 1, 'HEURISTIC_HIGH_NOT_VIDEO_TESTED': 11}`
- Mechanism coverage (independent): `{'cross_shot_narrative': 1, 'same_local_actor_temporal': 1, 'slide_speech_av_grounding': 1, 'heat_boundary_name_contrast': 1, 'reverse_name_to_early_garment': 1, 'ordered_state_transitions': 1, 'cross_scene_attribute_contrast': 3}`
- New-candidate yield / video: 0.375
- cost_per_new_candidate_s: 1.688

## Human review packet (true-blind)
- Reviewable items: 8 (status `PENDING_HUMAN`)
- Do not pad with duplicates/UNKNOWN; production continues without waiting for human.

### Priority sample
- [1] `QA_DRAFT_0009` S8vPx-u9p_A `cross_scene_attribute_contrast` grade=HEURISTIC_HIGH_NOT_VIDEO_TESTED score=0.85 new=True — new_frame_observation_candidate
- [2] `QA_DRAFT_0012` iA_69g87Ilw `cross_scene_attribute_contrast` grade=HEURISTIC_HIGH_NOT_VIDEO_TESTED score=0.85 new=True — new_frame_observation_candidate
- [3] `QA_DRAFT_0015` hROKtPqktO8 `cross_scene_attribute_contrast` grade=HEURISTIC_HIGH_NOT_VIDEO_TESTED score=0.85 new=True — new_frame_observation_candidate
- [4] `QA_DRAFT_0006` VTCDQYYKA9o `reverse_name_to_early_garment` grade=HEURISTIC_HIGH_NOT_VIDEO_TESTED score=0.8 new=False — heuristic_high_calibration_not_video_tested
- [5] `QA_DRAFT_0001` JPPMz8fEml0 `cross_shot_narrative` grade=HEURISTIC_MEDIUM_NOT_VIDEO_TESTED score=0.5 new=False — coverage_or_uncertain
- [6] `QA_DRAFT_0002` QWXlvx1GoTY `same_local_actor_temporal` grade=HEURISTIC_MEDIUM_NOT_VIDEO_TESTED score=0.65 new=False — risk_sample:no_provisional_answer
- [7] `QA_DRAFT_0004` Z86xysw5Ncc `heat_boundary_name_contrast` grade=SHORTCUT_CONTROL score=0.6 new=False — development_control_or_shortcut
- [8] `QA_DRAFT_0008` T1yhBv1ytzw `ordered_state_transitions` grade=SHORTCUT_CONTROL score=0.6 new=False — development_control_or_shortcut
- [9] `QA_DRAFT_0003` QWXlvx1GoTY `slide_speech_av_grounding` grade=HEURISTIC_LOW_NOT_VIDEO_TESTED score=0.45 new=False — risk_sample:audio_required_unresolved,no_provisional_answer

## Per-video extract status
- `JPPMz8fEml0`: OK n_events=13 flags=[]
- `QWXlvx1GoTY`: OK n_events=13 flags=[]
- `Z86xysw5Ncc`: OK n_events=14 flags=[]
- `VTCDQYYKA9o`: OK n_events=14 flags=[]
- `T1yhBv1ytzw`: OK n_events=14 flags=[]
- `S8vPx-u9p_A`: OK n_events=14 flags=[]
- `iA_69g87Ilw`: OK n_events=14 flags=[]
- `hROKtPqktO8`: OK n_events=14 flags=[]

## Failure / risk notes (do not block batch)
- Uncertain / ANSWER_PENDING QAs remain in pool with explicit flags.
- Shortcut controls (e.g. heat-boundary text contrast) graded SHORTCUT_CONTROL.
- Audio-required drafts stay UNCERTAIN until audio audited.
- No auto-SUPPORTED; sealed set not accessed; expensive RSI not run.

## Cost proxy (this run)
- Coarse ffmpeg frame samples ≤12/video (not full 1fps).
- No paid vision/API calls.
- Human review cost deferred: 8 items PENDING_HUMAN.

Risk/error tallies: `{'no_provisional_answer': 3, 'audio_required_unresolved': 1, 'text_overlay_low_complexity_control': 2, 'duplicate_evidence_family': 8, 'HARD:generation_error': 1, 'HARD:fact_binding_quarantine': 1, 'possible_B_only_order_leak': 1, 'from_new_frame_observation_unverified_video': 9}`
