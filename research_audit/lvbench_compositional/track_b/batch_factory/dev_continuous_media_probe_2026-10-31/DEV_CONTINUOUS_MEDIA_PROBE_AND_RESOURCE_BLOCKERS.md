# DEV continuous-media probe + resource blockers (2026-10-31)

Scope: bounded playability check of **existing** gitignored DEV continuous clips; **not** new video discovery; **not** run_003; no scene-contrast QA template churn.

## Cap

- Max 4 clips, ≤3 contact frames each (20%/50%/80%).
- ffmpeg/ffprobe only; no VLM / no new event extraction.
- Artifact: `probe_report.json` + `contact_sheets/*.jpg`.

## Result

| video_id | clip role | duration_s | playable | new semantic events |
|----------|-----------|------------|----------|---------------------|
| VTCDQYYKA9o | A_window_garment | 23.0 | yes | 0 |
| VTCDQYYKA9o | B_window_overlay | 10.0 | yes | 0 |
| T1yhBv1ytzw | score_anchor | 25.0 | yes | 0 |
| T1yhBv1ytzw | goal_window_dev_only | 90.0 | yes | 0 |

- **n_playable_continuous_clips = 4** (local MP4 under `track_b/local_media` / `construction_discovery_assets/.../local_clips`, gitignored).
- **n_new_model_inferred_semantic_events = 0**
- **n_new_cursor_frame_observations = 0** (contact stills are decode proofs, not NEW_FRAME_OBSERVATIONS)
- **semantic_extractor_status = BLOCKED_NO_SEMANTIC_EXTRACTOR**
- **run_003_status = NOT_STARTED** (honest; not fabricated)

## Distinct-question recount (history immutable)

Recount only of `run_002_patch_regen/qa_drafts.jsonl` (17 drafts):

| metric | value |
|--------|------:|
| n_distinct_question_texts | **8** |
| n_distinct_question_answer_pairs | 16 |
| n_distinct_program_structures | 7 |
| prior overstated `n_distinct_questions` (Q+A hash) | 16 |

Code now exposes `n_distinct_question_texts` vs `n_distinct_question_answer_pairs`; alias `n_distinct_questions` = stems only. Historical run_001/002 JSONL untouched.

## Resource dependencies (why no run_003 / no new semantics)

1. No additional unlabeled `DEV_CONSTRUCTION` video IDs beyond the existing 8-pool.
2. No approved low-cost continuous-video semantic extractor (local VLM / API) available in this environment.
3. Continuous MP4 clips **are** available for future human continuous review — they do **not** auto-yield new formal events.
4. Sealed reservoir untouched (`SEALED_POOL_SPLIT_POLICY.json`); partition remains `UNASSIGNED`; `formal_supported=false`; `ok_for_expensive_rsi=false`.

## Real new capability this turn

- Confirmed playable continuous DEV media + contact-sheet evidence path.
- **No** autonomous new-semantic discovery; **no** formal blind readiness change.
