# DEV capacity + continuous evidence gate (2026-10-31)

Parent HEAD baseline: `6422d271115b0f9b825104f0aec580b9ad8491d5`  
Audit: `CHATGPT_AUDIT_56D68AE_CONTINUOUS_MEDIA_AND_SPLIT_GATE_2026-10-31.md`  
Invariants: `UNASSIGNED` · no auto-`SUPPORTED` · sealed untouched · `ok_for_expensive_rsi=false`  
Track A scores frozen (choice 0.833 / exec 0.333 / gold-feed 0); not reworked this turn.

## P0 — sealed exclusion reconciliation

`track_b/SEALED_POOL_SPLIT_POLICY.json` `exposed_or_construction` reconciled against:

- prior policy IDs
- `construction_video_pool.jsonl`
- `construction_discovery_assets/` + `chatgpt_review_assets/` video dirs
- `qa_v1_clean` / `pilot_v2_2` / `targeted_v3` / `phase1` `local_media/` dirs
- `run_001` / `run_002` / `run_002_patch_regen` inventories

**Audit-critical adds:** `S8vPx-u9p_A`, `iA_69g87Ilw`, `hROKtPqktO8`  
**Also added** other previously sampled construction/local_media IDs that were missing from the register (see policy `reconciliation.added_ids`).  
**New DEV registered this turn** also appended to exclusion: `Mcggugol2ts`, `xi6r3hZe5Tg`.

`sealed_reservoir.current_ids` remains `[]` (untouched). Exclusion ≠ Seen/Unseen program assignment (`UNASSIGNED`).

Regression: `tools/lvbench_comp/test_sealed_exclusion.py` → `test_all_run001_run002_exposed_IDs_subset_of_sealed_exclusion`.

## P1-A — continuous DEV evidence (≤2 candidates)

Source: four already-decoded local clips (not re-probed as novelty). Artifact: `dev_continuous_evidence_candidates_2026-10-31.json`.

| candidate | video | status | continuous motion watched | formal |
|-----------|-------|--------|---------------------------|--------|
| VTCD cross-clip identity (red jacket ↔ FAN ZHENDONG overlay) | VTCDQYYKA9o | **UNVERIFIED** | no | false |
| T1yh score-state order control (0-0 anchor; no attack-origin reopen) | T1yhBv1ytzw | **SHORTCUT_CONTROL** | no | false |

Global: **`BLOCKED_NO_CONTINUOUS_SEMANTIC_REVIEWER`**. Stills suggest jersey/overlay cues; ffmpeg playability ≠ certified video fact. No user formal blind packets issued.

## P1-B — DEV capacity & semantic path (metadata + presence)

| quantity | value |
|----------|------:|
| LVBench `video_info.meta.jsonl` videos | 103 |
| Local `/dataset/LVBench/videos/*.mp4` | 103 |
| Prior registered DEV_CONSTRUCTION | 8 |
| After this turn | **10** (+`Mcggugol2ts`, `xi6r3hZe5Tg`) |
| Eligible IDs not in exclusion (before new register) | ~79 with local MP4 |
| Eligible local excluding gate-split stems (selection pool) | ~67 |

**Answer to “only 8 DEV?”:** Only 8 were *registered* as `DEV_CONSTRUCTION`. Local LVBench holds many additional non-excluded MP4s that can be pre-registered under the existing split policy **before** content semantics. This turn registered **2** new eligible DEV IDs with seed frames only.

**Semantic extractor:** no `torch`/`transformers`/OpenAI/Anthropic SDKs in env; API key env slots length-8 placeholders; OCR ONNX present but **not** video semantics → `BLOCKED_NO_SEMANTIC_EXTRACTOR_MODEL`. Alternate path: ChatGPT frame production (below). Hardcoded `NEW_FRAME_OBSERVATIONS` are **not** autonomous discovery.

## P1-C — ChatGPT frame production pilot

Batch: `track_b/batch_factory/chatgpt_frame_production_pilot_2026-10-31/`

- 12 timestamped frames (JPPMz8fEml0 unused regions ×4 + 2 new DEV ×4)
- Status: **`PENDING_CHATGPT_FRAME_PRODUCTION`**
- Events file placeholder only — **0 ChatGPT events fabricated**
- Provenance target: `CHATGPT_FRAME_OBSERVATION` (≠ Cursor/curated/VLM)
- Same ChatGPT pass must **not** later count as independent A/B blind review

Pilot metrics until ChatGPT returns: new ChatGPT events **0** · independently verified events **0** · new relations **0** · new QA families **0** · true composition-dependence candidates **0**.

## run_003

**`NOT_STARTED`**. New DEV seeds exist, but real semantic observations are still pending ChatGPT GitHub review; no authorized local VLM.

## Track A

Unchanged negative baseline (not re-tuned).

## Next concrete actions

1. ChatGPT completes `events_CHATGPT_FRAME_OBSERVATION.jsonl` on the pilot batch.  
2. Cursor ingests events → relations/QA factory (distinguish still vs continuous vs independent family).  
3. Only then consider `run_003` with measured yield — not a replay of old 8-pool templates.  
4. Continuous identity/order candidates stay UNVERIFIED/SHORTCUT_CONTROL until a real motion reviewer exists.
