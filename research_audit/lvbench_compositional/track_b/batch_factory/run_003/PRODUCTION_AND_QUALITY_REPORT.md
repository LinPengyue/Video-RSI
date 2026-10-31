# Track B Production & Quality Report — `run_003`

Factory `0.2.2` / extractor `batch_factory_v2_2_chatgpt_intake_2026-10-31`
Elapsed: 0.1s | partition: **UNASSIGNED** | formal_supported: **false** | ok_for_expensive_rsi: **false**

## Throughput
- Videos inventory: 3
- Processed OK/PARTIAL: 3
- MEDIA_UNAVAILABLE: 0
- EXTRACTION_FAILED: 0
- Genre: `{'documentary_travel': 1, 'unknown': 2}`

## Funnel (not SUPPORTED) — honest provenance
- Coarse frames: 0
- Curated semantic (fixtures): 0
- Cursor still observations: 0 | ChatGPT still: 12 | **model_inferred**: 0
- Relations: 10
- QA drafts: 10 | distinct question texts: 2 | distinct Q+A pairs: 10 | program structures: 2 | independent families: 10 | dup: 0 | quarantine: 0 | leakage: 0
- provisional_answer_present: 10 | independently_answer_verified: 0
- New relation families (from new obs): 10
- Grades (heuristic, not video-tested): `{'SHORTCUT_CONTROL': 10}`
- Mechanism coverage (independent): `{'still_ordered_setting_contrast': 9, 'still_commerce_price_display_pair': 1}`
- New-candidate yield / video: 3.333
- cost_per_new_candidate_decode_only_s: 0.0 (decode_only: ffmpeg/coarse extract wall time / new families; excludes Cursor/ChatGPT still interpretation and QA validation time (not instrumented))

## Human review packet
- packet_serialized: 10 | answerable_candidate: 10 | asset_verified: 0 | continuous_media: 0 | formal_blind_ready: 0 | true_blind_evaluated: 0
- status: `SERIALIZED_NOT_FORMAL_USER_BATCH` — not a formal user batch while formal_blind_ready=0

### Priority sample
- [1] `QA_DRAFT_0001` JPPMz8fEml0 `still_ordered_setting_contrast` grade=SHORTCUT_CONTROL score=0.65 new=True — new_frame_observation_candidate
- [2] `QA_DRAFT_0002` JPPMz8fEml0 `still_ordered_setting_contrast` grade=SHORTCUT_CONTROL score=0.65 new=True — new_frame_observation_candidate
- [3] `QA_DRAFT_0003` JPPMz8fEml0 `still_ordered_setting_contrast` grade=SHORTCUT_CONTROL score=0.65 new=True — new_frame_observation_candidate
- [4] `QA_DRAFT_0004` Mcggugol2ts `still_ordered_setting_contrast` grade=SHORTCUT_CONTROL score=0.65 new=True — new_frame_observation_candidate
- [5] `QA_DRAFT_0005` Mcggugol2ts `still_ordered_setting_contrast` grade=SHORTCUT_CONTROL score=0.65 new=True — new_frame_observation_candidate
- [6] `QA_DRAFT_0006` Mcggugol2ts `still_ordered_setting_contrast` grade=SHORTCUT_CONTROL score=0.65 new=True — new_frame_observation_candidate
- [7] `QA_DRAFT_0007` Mcggugol2ts `still_commerce_price_display_pair` grade=SHORTCUT_CONTROL score=0.65 new=True — new_frame_observation_candidate
- [8] `QA_DRAFT_0008` xi6r3hZe5Tg `still_ordered_setting_contrast` grade=SHORTCUT_CONTROL score=0.65 new=True — new_frame_observation_candidate
- [9] `QA_DRAFT_0009` xi6r3hZe5Tg `still_ordered_setting_contrast` grade=SHORTCUT_CONTROL score=0.65 new=True — new_frame_observation_candidate
- [10] `QA_DRAFT_0010` xi6r3hZe5Tg `still_ordered_setting_contrast` grade=SHORTCUT_CONTROL score=0.65 new=True — new_frame_observation_candidate

## Per-video extract status
- `JPPMz8fEml0`: OK n_events=4 flags=['CHATGPT_STILL_INTAKE_ONLY', 'NO_CONTINUOUS_VIDEO_EVENTS']
- `Mcggugol2ts`: OK n_events=4 flags=['CHATGPT_STILL_INTAKE_ONLY', 'NO_CONTINUOUS_VIDEO_EVENTS']
- `xi6r3hZe5Tg`: OK n_events=4 flags=['CHATGPT_STILL_INTAKE_ONLY', 'NO_CONTINUOUS_VIDEO_EVENTS']

## Failure / risk notes (do not block batch)
- Uncertain / ANSWER_PENDING QAs remain in pool with explicit flags.
- Shortcut controls (e.g. heat-boundary text contrast) graded SHORTCUT_CONTROL.
- Audio-required drafts stay UNCERTAIN until audio audited.
- No auto-SUPPORTED; sealed set not accessed; expensive RSI not run.

## Cost proxy (this run)
- Coarse ffmpeg frame samples ≤12/video (not full 1fps).
- No paid vision/API calls.
- Human review cost deferred: 10 items PENDING_HUMAN.

Risk/error tallies: `{'from_new_frame_observation_unverified_video': 10}`
