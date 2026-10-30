# Track B Production & Quality Report — `run_001`

Factory `0.1.0` / extractor `batch_factory_v1_2026-10-30`
Elapsed: 0.23s | partition: **UNASSIGNED** | formal_supported: **false** | ok_for_expensive_rsi: **false**

## Throughput
- Videos inventory: 8
- Processed OK/PARTIAL: 8
- MEDIA_UNAVAILABLE: 0
- EXTRACTION_FAILED: 0
- Genre: `{'documentary_travel': 1, 'tech_talk': 1, 'athletics': 1, 'table_tennis': 1, 'football_broadcast': 1, 'unlabeled_lvbench': 3}`

## Funnel (not SUPPORTED)
- Events total / semantic: 110 / 13
- Relations: 8
- QA drafts: 8 (independent families 8, dup-flagged 0, dup rate 0.0)
- Auto grades: `{'AUTO_MEDIUM': 4, 'AUTO_LOW': 1, 'AUTO_HIGH': 3}`
- Mechanism coverage (independent): `{'cross_shot_narrative': 1, 'same_local_actor_temporal': 1, 'slide_speech_av_grounding': 1, 'heat_boundary_name_contrast': 2, 'reverse_name_to_early_garment': 2, 'ordered_state_transitions': 1}`
- Candidate yield / processed video: 1.0
- AUTO_HIGH rate: 0.375

## Human review packet
- Items prepared: 8 (status `PENDING_HUMAN`)
- Priority queue does not block further production batches.

### Priority sample
- [1] `QA_DRAFT_0006` VTCDQYYKA9o `reverse_name_to_early_garment` grade=AUTO_HIGH score=0.8 — high_auto_or_calibration
- [2] `QA_DRAFT_0008` T1yhBv1ytzw `ordered_state_transitions` grade=AUTO_HIGH score=0.8 — high_auto_or_calibration
- [3] `QA_DRAFT_0001` JPPMz8fEml0 `cross_shot_narrative` grade=AUTO_MEDIUM score=0.5 — coverage_or_uncertain
- [4] `QA_DRAFT_0002` QWXlvx1GoTY `same_local_actor_temporal` grade=AUTO_MEDIUM score=0.65 — risk_sample:no_provisional_answer
- [5] `QA_DRAFT_0004` Z86xysw5Ncc `heat_boundary_name_contrast` grade=AUTO_MEDIUM score=0.6 — risk_sample:text_overlay_low_complexity_control
- [6] `QA_DRAFT_0003` QWXlvx1GoTY `slide_speech_av_grounding` grade=AUTO_LOW score=0.45 — risk_sample:audio_required_unresolved,no_provisional_answer
- [7] `QA_DRAFT_0007` VTCDQYYKA9o `reverse_name_to_early_garment` grade=AUTO_HIGH score=0.8 — high_auto_or_calibration
- [8] `QA_DRAFT_0005` Z86xysw5Ncc `heat_boundary_name_contrast` grade=AUTO_MEDIUM score=0.6 — risk_sample:text_overlay_low_complexity_control

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

Risk/error tallies: `{'no_provisional_answer': 2, 'audio_required_unresolved': 1, 'text_overlay_low_complexity_control': 2, 'possible_B_only_order_leak': 1}`
