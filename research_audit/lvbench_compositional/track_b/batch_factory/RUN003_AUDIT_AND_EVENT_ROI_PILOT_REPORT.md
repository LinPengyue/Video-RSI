# run_003 audit acceptance + event-centric ROI pilot (2026-10-31)

Parent HEAD: `ccff4f3310fc7e7175781fa6a9202d0e2b5acd2a`  
Audit: `CHATGPT_AUDIT_BCD1A0F_RUN003_COMPOSITION_GATE_2026-10-31.md`  
Invariants: `UNASSIGNED` · no auto-`SUPPORTED` · sealed untouched · `ok_for_expensive_rsi=false`  
Track A: **frozen** (choice 0.833 / exec 0.333 / gold-feed 0).

## Accept run_003 engineering; do not upgrade science

Historical `run_003` artifacts **unchanged**:

- 12 ChatGPT single-still observations
- 10 relations / 10 QA drafts — all `SHORTCUT_CONTROL` / `development_control`
- 2 question stems / 2 program signatures
- `n_independent_evidence_families=10` = fact-id combinations, **not** 10 novel composition skills
- formal_blind_ready = 0

**Not** reworded or regenerated. No second still-order-contrast factory pass.

## P1 — bounded ROI dense sampling

Videos (registered nonsealed DEV only): `Mcggugol2ts`, `xi6r3hZe5Tg`  
Cap: ≤2 ROI/video · ~10 s · 1.5 fps · ≤16 frames/ROI · no full-length dense decode.

| roi_id | video | window_s | n_frames | selection rationale |
|--------|-------|-----------|---------:|---------------------|
| `Mcgg_ROI_vending_hand_1060_1070` | Mcggugol2ts | 1060–1070 | 16 | Scout: wide facade → hand pointing at priced drinks → street pullback (interaction candidate) |
| `Mcgg_ROI_cardshop_approach_2128_2138` | Mcggugol2ts | 2128–2138 | 16 | Scout: aisle approach → closer priced card case (weak; camera/focus) |
| `xi6_ROI_aerial_to_speaker_528_538` | xi6r3hZe5Tg | 528–538 | 16 | Scout: aerial cityscape cut to indoor gesturing speaker (ordered cut; identity UNRESOLVED) |
| `xi6_ROI_bioprint_deposit_1060_1070` | xi6r3hZe5Tg | 1060–1070 | 16 | Scout: printer nozzle depositing purple lattice (strongest within-window state-change candidate) |

**Totals:** 4 ROIs · **64** timestamped GitHub frames · extract wall ≈ **2.6 s** (ffmpeg seeks; excludes prior ChatGPT time).

Optional local continuous clips (~10 s each) under gitignored `track_b/local_media/roi_clips_2026-10-31/` — playable for a continuous auditor later; **not** committed; ChatGPT GitHub still review **cannot** set `CONTINUOUS_VIDEO_VERIFIED`.

## P2 — ChatGPT multi-frame production batch

Path: `track_b/batch_factory/chatgpt_multiframe_roi_pilot_2026-10-31/`

- `batch_manifest.json` — ROI metadata, frame paths, sha256, rationales, continuous accessibility
- `frames/<video_id>/<roi_id>/*.jpg`
- `events_CHATGPT_MULTIFRAME_OBSERVATION.jsonl` — **placeholder only**
- Status: **`PENDING_CHATGPT_MULTIFRAME_SEMANTIC_REVIEW`**
- **0 fabricated ChatGPT multiframe events**

Required next-pass labels: `STATIC_VISIBLE` | `ORDERED_MULTIFRAME_SUGGESTS` | `CONTINUOUS_VIDEO_VERIFIED` | `UNRESOLVED`.

## P3 — relation feasibility (pre-QA)

Cursor scout seeds (provisional; **not** certified; **not** factory relations):

| hypothesis | provisional modality | two-witness idea | shortcut risk |
|------------|----------------------|------------------|---------------|
| Vending hand selection | ORDERED_MULTIFRAME_SUGGESTS | wide vs hand-close vs pullback | middle still may suffice |
| Cardshop approach | ORDERED_MULTIFRAME_SUGGESTS | weak | late case still alone |
| Aerial→speaker cut | ORDERED_MULTIFRAME_SUGGESTS | both ends for joint Q | either end alone |
| Printer deposit progress | ORDERED_MULTIFRAME_SUGGESTS | early sparse vs late filled lattice | late lattice alone |

**No nontrivial directed composition certified this turn.**  
**run_004 = NOT_STARTED** → `BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE` until ChatGPT multiframe events exist **and** pass relation-feasibility (non-scene-contrast) gate.

No QA Draft / Auto Screen for this pilot (by design).

## Input integrity regression

`validate_chatgpt_events(..., manifest_frames=...)` now defaults to trusted production:

- evidence path **must** be in manifest
- `source_frame_sha256` **required** and must match file (and manifest sha when present)

No-manifest callers remain lenient. Tests in `test_chatgpt_ingest.py`.

## Track A

Unchanged frozen negative baseline; no selector / RSI work.

## Cost & blockers

| item | value |
|------|------:|
| ROI extract wall | ~2.6 s |
| GitHub frames | 64 (~5.6 MB batch dir) |
| Paid VLM | 0 |
| ChatGPT multiframe events | 0 (pending) |
| Continuous certification | blocked (no remote continuous auditor on GitHub stills) |
| Independent A/B blind | blocked (producer ≠ adjudicator) |
| run_004 | blocked pending compositional event evidence |

## Next concrete action

ChatGPT reviews the multiframe ROI sheets on GitHub and writes real `CHATGPT_MULTIFRAME_OBSERVATION` events. Cursor then runs relation feasibility only; start run_004 **iff** a nontrivial evidence-grounded directed dependency survives.
