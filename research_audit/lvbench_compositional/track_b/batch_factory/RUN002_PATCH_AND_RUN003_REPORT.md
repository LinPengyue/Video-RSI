# RUN002 Patch + RUN003 Status (2026-10-31)

Baseline audited: `68ab45c` · Follow-up audit: `CHATGPT_AUDIT_68AB45C_RUN002_FOLLOWUP_2026-10-31.md`  
Synced HEAD at start: `f5413c62c69e763325a443fdee39725a1f6e3ac3`  
Constraints: **UNASSIGNED** · no auto-**SUPPORTED** · sealed untouched · `ok_for_expensive_rsi=false`

`run_001` / `run_002` artifacts are **immutable**. This round only patches factory/scoring code and regenerates drafts from stored run_002 events.

## P0 patches delivered

| Item | Fix |
|------|-----|
| Question-side leakage | Cross-scene Qs no longer embed A/B `location` tokens; `leakage.py` gate + regression test |
| Metric semantics | Split `n_provisional_answer_present` vs `n_independently_answer_verified`; Cursor/ChatGPT/model counters separated; `cost_per_new_candidate_decode_only_s` labeled decode-only |
| Review readiness | `reviewer_asset_verified` stays false for stills; `n_formal_blind_ready=0`; still vs continuous media states; no user formal batch authorized |
| Track A scoring | Wrong-schema abstain not credited; compare requires exact/canonical answer (not `evidence_path_valid` / substring); oracle scrape boundary tests |

Tests: `test_batch_factory_v2` + `test_program_execution` = **13/13 OK**

## Patch regen (`run_002_patch_regen/`)

Re-drafted from immutable run_002 event graphs with fixed generators (not new video discovery):

| Metric | Value |
|--------|-------|
| leakage_error | **0** |
| provisional_answer_present | 13 |
| independently_answer_verified | **0** |
| packet_serialized | 8 |
| answerable_candidate | 6 |
| reviewer_asset_verified | **0** |
| continuous_media_reviewable | **0** |
| formal_blind_ready | **0** |
| true_blind_evaluated | **0** |
| model_inferred_semantic_events | **0** |
| cursor_frame_observations (from run_002 events) | 9 |

ChatGPT’s nine-still audit (`CHATGPT_RUN002_FRAME_AUDIT.jsonl`) remains a **separate unblinded static review**; not counted as A-only/B-only, not upgraded to `HUMAN_VIDEO_VERIFIED`.

## RUN003 — blocked (honest)

**Status:** `NOT_STARTED_BLOCKED_NO_NEW_DEV_VIDEO_AND_NO_SEMANTIC_EXTRACTOR`

Reasons:
1. DEV_CONSTRUCTION pool still has only the same 8 videos already used in run_001/002; no additional unlabeled construction IDs registered without sealed-set risk.
2. `model_inferred_events=0` — no authorized affordable continuous-video semantic extractor.
3. Pre-authored `NEW_FRAME_OBSERVATIONS` must not be reported as automatic discovery success on arbitrary new videos.

**Do not fabricate run_003.** Recovery: add new DEV_CONSTRUCTION IDs with local media + still/ChatGPT observation path, or enable a budgeted local VLM; then open a uniquely named batch.

## Track A (after integrity patch)

choice≈**0.833** · exec≈**0.333** · explicit_abstain≈**0.333** · oracle_scrape=**0.0**  
Negative result retained; frozen binding control untuned; no RSI.

## Claims

**Supported:** leakage regression closed on regen; metrics no longer equate provisional text with verified answers; formal user blind batch correctly gated off.

**Not supported:** autonomous semantic discovery; continuous-video-verified QA; A/B necessity; run_003 yield.
