# TRACK B PROGRESS — video-driven evidence + canonical import

Baseline prior Cursor: `8513843`  
ChatGPT canonical docs: `1b44fc7` (synced via raw download when fetch timed out)

## Method

Primary path: **video evidence → fact discovery → mechanism → ChatGPT original QA → independent verification**.  
Official-QA name-swap is not the main constructor.

## Canonical mapping (authoritative)

| ID | seed | video | status |
|---|---|---|---|
| CG-NEW-001 | TB-003 | TJR1oYDDTwg | PROPOSED_REVIEW_REQUIRED |
| CG-NEW-002 | TB-007 | Cm73ma6Ibcs | PROPOSED_REVIEW_REQUIRED |
| CG-NEW-003 | TB-006 | LLSJrEgOOtw | PROPOSED_REVIEW_REQUIRED |
| CG-NEW-004 | TB-005 | evYm0cELO3I | PROPOSED_CONTROL_CANDIDATE |
| CG-NEW-005 | TB-004 | vaL_vSdZKZo | PROPOSED_EVIDENCE_REQUEST |

Fallback snapshot of incorrect 004/005 fill retained: `../chatgpt_video_driven_qa/fallback_snapshot_85138431.jsonl`.

## Evidence

Indexed in `CG_NEW_EVIDENCE_INDEX.jsonl` (no re-extract this round).  
Pack: `local_media/lvbench_cg_new_evidence_round.zip` (~34.6 MB, gitignored).

Adjacent windows remain `verified_as_new_fact=false`.

## Necessity

Scaffold: `NECESSITY_REVIEW_PREP.md` + `cg_new_second_round_status.jsonl`. All pending independent review.

## Full benchmark

See `TRACK_B_NEXT_STAGE.md` and `BENCHMARK_EXPANSION_PLAN.md`. Contaminated CG-NEW videos ≠ sealed final test.

## Status

**Track B: canonical five calibrated; evidence indexed; necessity prep ready; expansion plan maintained. Not a formal freeze.**
