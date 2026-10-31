# Multiframe relation feasibility (2026-10-31)

Parent HEAD: `f2004a00b02711f78aded56d0a9713563a3a0a94`  
Source events: `chatgpt_multiframe_roi_pilot_2026-10-31/events_CHATGPT_MULTIFRAME_OBSERVATION.jsonl` (10)  
ChatGPT review: `CHATGPT_MULTIFRAME_SEMANTIC_REVIEW_REPORT.md`  
Invariants: `UNASSIGNED` · no auto-`SUPPORTED` · sealed untouched · `ok_for_expensive_rsi=false`  
Track A: frozen. **No QA Draft / Auto Screen / run_004.**

## Validation

| check | result |
|-------|--------|
| Accepted / rejected | **10 / 0** |
| Provenance | all `CHATGPT_MULTIFRAME_OBSERVATION` |
| Manifest path membership | OK |
| Per-path `evidence_sha256[]` ↔ file ↔ manifest | OK |
| ROI / time_span containment | OK |
| `CONTINUOUS_VIDEO_VERIFIED` | **0** |
| `video_motion_verified` / cross-shot identity | all false |

Artifacts: `validation_report.json`, `normalized_events.jsonl`.

## Per-candidate decisions

| ID | ROI / claim | decision | run_004? |
|----|-------------|----------|----------|
| 001 | Vending static prices | CONTROL_ONLY | no |
| 002 | Vending pointing gesture | **REJECT** (≠ purchase) | no |
| 003 | Cardshop camera approach | **REJECT** | no |
| 004 | Card pointing | **REJECT** (≠ buy/touch) | no |
| 005 | Cardshop view shift | **REJECT** | no |
| 006 | Aerial PARKROYAL static | CONTROL_ONLY | no |
| 007 | Aerial→speaker edit cut | **REJECT** (≠ causality) | no |
| **008** | **Bioprint local lattice extension** | **DEV_HYPOTHESIS_NOT_QUALIFYING** | **no** |
| 009 | Print↔plated-food cut | **REJECT** (UNRESOLVED; forbid bind) | no |
| 010 | Later nozzle angle ↔ early lattice | **REJECT** (same point unproven) | no |

### Focus: `xi6_ROI_bioprint_deposit_1060_1070` / REL_FEAS_008

- Ordered stills (1060→1065.3) **suggest** local purple lattice extension near nozzle (`ORDERED_MULTIFRAME_SUGGESTS`).
- Cursor spot-check of begin/mid frames is consistent with a partial lattice + nozzle on build plate.
- **Why it fails the composition gate:** basic temporal state-change ≠ held-out multi-step directed composition; late frame alone shortcuts “what is printed”; not continuous-certified; producer ChatGPT ≠ independent A/B verifier; post-1066 plated-food insert must **not** be bound as product of the print (009).

## Gate

```
run_004_status = NOT_STARTED
status = BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE
n_run004_qualifying_relations = 0
qa_drafts_generated = 0
```

No generic ordered-still contrast QA manufactured.

## Resources needed (not user per-Q review)

1. Independent continuous review of gitignored `track_b/local_media/roi_clips_2026-10-31/xi6_ROI_bioprint_deposit_1060_1070.mp4` (and optionally vending ROI) under a non-ChatGPT provenance tier.
2. Or authorized continuous VLM with distinct provenance.
3. Separate blinded adjudicator if any future QA is drafted from continuous-verified events.

## Track A

Unchanged negative baseline.
