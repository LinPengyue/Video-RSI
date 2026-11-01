# P7 HIL Pilot Report — Track B Batch Annotation Feasibility

**Branch:** `research/lvbench-comp-p7-hil-pilot`  
**Baseline SHA (start):** `6b98d1de16b8ac7bfa2e40ea1b07e02a447cfb4f`  
**Pilot dir:** `research_audit/lvbench_compositional/p7_hil_pilot/`  
**Data partition:** `UNASSIGNED`  
**`ok_for_expensive_rsi`:** `false`  
**`run_004`:** `NOT_STARTED`  
**P0 runs:** not modified / not regenerated

## Verdict

**Method scaffolding works; new qualified composition families this round: 0.**

Production pipeline (machine clip prep → Event Cards → directed relation candidates → Batch Review Packet with A/B/gold isolation) is in place. Independent continuous-video human review was **not** executed this round, so pending statuses remain `PENDING_INDEPENDENT_REVIEW`. No fabricated `HUMAN_VIDEO_VERIFIED`, no new QA gold, no scale-up.

## Scope

| Item | Value |
|------|-------|
| Videos (≤4 DEV exposed) | `JTa_Ue2MSwc`, `VTCDQYYKA9o`, `TJR1oYDDTwg`, `T1yhBv1ytzw` |
| Media missing / sealed top-up | None — all four MP4s present under local LVBench videos |
| Event cards | 11 (3 calibration `EVENT_VERIFIED`, 8 pending) |
| Relation candidates | 10 (≤12): 2 calibration verified, 5 pending, 3 rejected non-composition |
| New independent qualified families | **0** |
| QA drafts | **None** (truth conditions unmet for new items) |
| Human review minutes | **0** |
| Paid API / GPU / Track A RSI | **Not run** |

## Reuse of Track A pilot_v2_2

Read and reused:

- `pilot_v2_2/REPORT.md`, `judgments.json`, `test_video_review.csv`
- `track_a/TRACK_A_READINESS.md`
- Existing Track B Event / Relation / QA schemas (status tiers; no schema rewrite of P0)

Calibration only (not P7 new discoveries):

- `LVCOMP-V2-002` Sierra ID → remove shoe → `P7_R_CALIB_sierra_id_to_remove_shoe`
- `LVCOMP-V2-003` Sierra ID → slap → `P7_R_CALIB_sierra_id_to_slap`

These demonstrate the **Identify Person → Bind Same Actor → Query Later Action** template end-to-end from prior human SUPPORTED judgments. They do **not** count toward P7 new family tally.

## Event Cards

Path: `event_cards/event_cards.jsonl`

| event_id | video | status | notes |
|----------|-------|--------|-------|
| P7_E_JTa_sierra_lower_third | JTa | EVENT_VERIFIED | pilot_v2_2; calibration |
| P7_E_JTa_remove_shoe | JTa | EVENT_VERIFIED | calibration |
| P7_E_JTa_slap_male_guest | JTa | EVENT_VERIFIED | calibration |
| P7_E_VTCD_red_jacket_towel | VTCD | PENDING_INDEPENDENT_REVIEW | historical still/clip index |
| P7_E_VTCD_remove_red_jacket | VTCD | PENDING_INDEPENDENT_REVIEW | curated; span needs continuous confirm |
| P7_E_VTCD_fan_previous_results_overlay | VTCD | PENDING_INDEPENDENT_REVIEW | PREVIOUS RESULTS overlay |
| P7_E_TJR_purple_child_near_king | TJR | PENDING_INDEPENDENT_REVIEW | embrace verb ambiguous |
| P7_E_TJR_purple_child_drums | TJR | PENDING_INDEPENDENT_REVIEW | cross-scene bind pending |
| P7_E_TJR_pink_child_string | TJR | PENDING_INDEPENDENT_REVIEW | distractor |
| P7_E_T1yh_score_00_anchor | T1yh | PENDING_INDEPENDENT_REVIEW | development control |
| P7_E_T1yh_score_later_state | T1yh | PENDING_INDEPENDENT_REVIEW | digits unread pending review |

Continuous review clips: `local_media/` (gitignored). Contact sheets: `review_assets/` (tracked). Cursor/LLM/still inference was **not** labeled `HUMAN_VIDEO_VERIFIED`.

**Contact-sheet spot-check (still ≠ continuous verify):**

- `TJR` 315–335s: Carmen Sandiego **royal** cast (king / prince reach), **not** later purple stage-costume performers → historical purple-embrace→drums bind likely **wrong early window**.
- `VTCD` garment window: athlete appears to **put on** red jacket over blue/yellow jersey (partial `FAN`/`CHN` lettering visible) → historical **remove** polarity conflict; flagged, not auto-verified.

## Relation Candidates

Path: `relations/relation_candidates.jsonl` · tally: `relations/family_tally.json`

**Kept as composition hypotheses (pending):**

1. VTCD garment actor ↔ Fan overlay bind  
2. VTCD red jacket → later jersey state (necessity risk: same short window)  
3. TJR purple near-king → later drums (**downgraded** — early window cast mismatch on contact sheets)  
4. TJR condition-select purple → instrument (same spine; likely fails with #3)  
5. T1yh score 0–0 → later state (development control; likely necessity fail)

**Rejected (logged, not composition):**

- Same-shot purple/pink co-occurrence  
- Shot-order-as-causality (VTCD)  
- Scene/score still contrast only (T1yh)

## Batch Human Review Packet

Path: `review_packets/`

| File | Role |
|------|------|
| `BATCH_REVIEW_PACKET.json` | Public batch items; status `PENDING_INDEPENDENT_REVIEW` |
| `blind_a_only.json` | A-only necessity probes (no gold) |
| `blind_b_only.json` | B-only necessity probes (no gold) |
| `gold_answer_key.SEALED_FROM_REVIEWER.json` | Answer sketches; sealed from necessity reviewer |

Status tiers (upgrade only after real verification):

`EVENT_VERIFIED` → `RELATION_VERIFIED` → `COMPOSITION_NECESSITY_VERIFIED` → `GOLD_ANSWER_VERIFIED`

**Independent continuous reviewer available this round:** `false` → packet stays pending; no invented pass.

## Failure Layer Diagnosis

Primary blocker: **视频核验** (independent continuous human video verification).  
Secondary signal: **事件发现 / 身份关联** errors exposed by contact-sheet spot-check (TJR wrong cast window; VTCD action polarity).

| Layer | Assessment |
|-------|------------|
| 事件发现 | PARTIAL_WITH_ERRORS — cards prepared; TJR/VTCD label issues flagged |
| 视频核验 | **BLOCKING** — 8 events pending independent continuous review |
| 身份关联 | BLOCKED / likely broken for TJR purple spine |
| 组合枚举 | PARTIAL_OK — 10 candidates, 3 honest rejects |
| 必要性 | NOT_REACHED — blinds prepared, 0 adjudicated |
| QA 真值 | NOT_REACHED — no new drafts |

Detail: `FAILURE_LAYER_DIAGNOSIS.json`

## Costs

| Kind | Value |
|------|-------|
| Human review minutes | 0 |
| Machine | local ffmpeg clips + contact sheets; no GPU / paid API / RSI |

See `COST_LOG.json`.

## Isolation / Safety

- P7 isolated under `p7_hil_pilot/`; branch off baseline `6b98d1d`
- Did not rewrite or regenerate P0 `run_001` / `run_002` / `run_003` artifacts
- `run_004` remains `NOT_STARTED`
- Sealed pool not read for construction fill
- All P7 results `UNASSIGNED`

## Minimal Fix Options (do not auto-scale)

1. Independent continuous review of **VTCD** garment + overlay first (polarity + identity).  
2. **Rediscover** a correct early purple-costume window on TJR before claiming embrace→drums; do not force king-window bind.  
3. Expect early drop of T1yh scoreboard family on necessity.  
4. Keep P0 frozen; open no `run_004` until ≥1 necessity-pass new family.

## Recommended Next Step

**Stop here for round 1.** After commit, report SHA. Next: independent continuous review of VTCD windows + TJR early-window rediscovery — **not** full LVBench scale-up, **not** `run_004`, **not** P0 rewrite.
