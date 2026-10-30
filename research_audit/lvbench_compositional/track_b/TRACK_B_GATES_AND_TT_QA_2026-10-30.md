# Track B — Overlay corrections, TT QA, accept/stop gates

Date: 2026-10-30  
Audit: `CHATGPT_AUDIT_68E3160_AND_DUAL_TRACK_HANDOFF_2026-10-30.md`  
Imported: `CHATGPT_VIDEO_EVIDENCE_ADJUDICATION_2026-10-30.jsonl`

## 1. Overlay semantics corrections (recorded)
See `OVERLAY_SEMANTICS_CORRECTIONS.jsonl` (filenames preserved):
- **Z86** `t_5_27` region: **START LIST – ROUND 1 HEAT 2**, not results.
- **VTCD** `later_t_4_30`: **PREVIOUS RESULTS / FAN ZHENDONG**, not live score.

## 2. Priority QA — TT reverse garment (`QA-TT-REVERSE-001`)
Question preserved (ChatGPT): later PREVIOUS-RESULTS blue/yellow athlete → earlier jacket color?  
Provisional answer **red**; **not SUPPORTED**.

| Evidence | Path | Watched? |
|---|---|---|
| A stills/sheet 02:43–03:06 | `tt_qa_adjudication/contact_A.jpg` + local `tt_garment_0243_0306.mp4` | Clips extracted; continuous human identity confirmation still required |
| B stills/sheet 04:25–04:35 | `tt_qa_adjudication/contact_B.jpg` + local `tt_previous_results_0425_0435.mp4` | Same |

Necessity protocol (pending blind human): A-only / B-only / A+B on exact wording; role-swap shortcut check.  
Legal status: `PROPOSED_REVIEW_REQUIRED` / `UNASSIGNED`. Funnel: `COMPOSITION_QA_CANDIDATE`.

## 3. Football stop gate
`CG-SPORT-DESIGN-001-REFINED` → funnel **`REJECTED_OR_UNRESOLVED`** for strong composition.  
Score trajectory remains `SOURCE_VISUAL_FACT` only.  
**No further attack-origin JPEG grids.** Next step if resumed: one human watch of `liv_live_attack_2955_3015.mp4` + `bha_live_attack_3848_3915.mp4` with timestamped ball actions — not more sampling.

## 4. Athletics revise gate
Finish-rank hypothesis demoted. Heat-boundary control `QA-ATH-HEAT-BOUNDARY-CONTROL-001` kept as **DEVELOPMENT_CONTROL**.  
Bounded finish-results search (05:30–15:00 every 15s, bright-panel filter) saved under `chatgpt_review_assets/Z86xysw5Ncc/finish_results_search/` — **not auto-labeled as finish board**. Stop open-ended re-extraction of the start-list window.

## 5. CG-NEW
- CG-NEW-002 table push: **REJECTED_OR_UNRESOLVED** / `TABLE_PUSH_UNCONFIRMED` (stop same-range grids).
- CG-NEW-001 hug / CG-NEW-003 audio: still pending one continuous adjudication each; no new dense JPEG spam this round.

## 6. New construction discovery (benchmark line)
Added seed frames for previously unexposed DEV_CONSTRUCTION videos (not sealed):
- `S8vPx-u9p_A`, `iA_69g87Ilw`, `hROKtPqktO8` under `construction_discovery_assets/*/seed_frame_*.jpg`  
Registered in `construction_video_pool.jsonl` append + `construction_discovery_batch_2026-10-30.jsonl`. No QA minted.

## 7. Parallel funnel
`CANDIDATE_FUNNEL_PARALLEL.jsonl` — does not alter legal TB/CG-NEW status strings.
