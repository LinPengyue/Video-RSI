# Track B — Video-driven QA evidence round (post-35ebad3 audit)

Responds to `CHATGPT_AUDIT_35EBAD3_AND_NEXT_DUAL_TRACK_2026-10-30.md`.  
No auto-`SUPPORTED`. Sealed pool untouched. No answers from single stills.

## 1. Football T1yh — attack-origin verification package

### New review assets
| Asset | Window | Role |
|---|---|---|
| `liv_attack_origin_2955_3010.jpg` | 29:55–30:10 | Live attack lead-in → celebration |
| `bha_attack_origin_3848_3912.jpg` | 38:48–39:12 | Live equalizer window |
| `attack_stills/*` | selected | Per-second stills for ball-state annotation |
| local MP4 (gitignored) | `liv_live_attack_2955_3015.mp4`, `bha_live_attack_3848_3915.mp4` | Continuous review required |

### Structured annotations (provisional; not gold)
See `T1yh_ATTACK_ORIGIN_ANNOTATION.jsonl`:
- Score order (overlays): LIV 0–1 then BRI 1–1 — previously anchored.
- Live vs replay: replay blocks are **same goals**, not new events.
- **Kick origin / set-piece vs open play / last touch / scorer**: still `UNKNOWN_PENDING_CONTINUOUS_CLIP_REVIEW`.
- Human/ChatGPT should watch the two live MP4s; do not invent technique from stills.

### Refined hypothesis (NOT accepted item)
Stored in `CHATGPT_REFINED_SPORT_QA_HYPOTHESIS.jsonl`:
> 比分先被改写、随后又被扳平的两次进球中，哪一方的进攻首先由定位球发起？该次进球改变的是领先还是扳平状态？  
`gold=null`, `HYPOTHESIS_NOT_SUPPORTED`, `UNASSIGNED`.  
Necessity: A-only/B-only/A+B on **exact** wording after origins verified; risk of conjunction / single-window shortcut documented.

Canonical `CG-SPORT-DESIGN-001` unchanged: not SUPPORTED.

## 2. Athletics Z86 — intro → finish → board

| Asset | Note |
|---|---|
| `result_board_0450_0549_1fps.jpg` | 1fps finish/board window |
| `board_stills/` + crops | Candidate result-panel frames ~05:24–05:30 |
| local `finish_board_0450_0550.mp4` | Continuous |

**Placements / times not claimed.** OCR unavailable in this environment; board text legibility = `PENDING_HUMAN_OR_CHATGPT_BOARD_READ`.  
Candidate mechanism (intro name/country → lane → board place) remains hypothesis only (`CG-ATHLETICS-QA-HYPOTHESIS` in JSONL, gold=null).

## 3. Table tennis VTCD — garment + later event

| Asset | Note |
|---|---|
| prior `garment_0240_0320_1fps.jpg` | Red jacket → blue/yellow sequence (still-level) |
| `event_stills/garment_*` | Key stills 02:46–03:10 |
| `later_rally_0330_0555.jpg` + `later_*` stills | Later window probe |
| local `later_0330_0500.mp4` | Continuous later segment |

Weak diagnostic QA prototype (shortcut-prone) kept as `DEV_DIAGNOSTIC_WEAK_COMPOSITION` candidate only — **not formal**, gold pending continuous review. Prefer cross-event same-athlete later rally link once later play identity confirmed; currently later segment status = `PENDING_CONTINUOUS_IDENTITY_MATCH`.

## 4. CG-NEW

| ID | Action | Status |
|---|---|---|
| CG-NEW-002 | New hunt `05:05–07:30` sheet `hunt_0505_0730_5s.jpg` + local window MP4 | If push still absent → `TABLE_PUSH_UNCONFIRMED` (do not re-extract 04:19–05:05) |
| CG-NEW-001 | Prior embrace clip | `ACTION_AMBIGUOUS_PENDING_VIDEO` |
| CG-NEW-003 | WAV present | `AUDIO_NOT_AUDITED` |

## 5. Isolation
Exposed DEV_CONSTRUCTION videos only. No sealed assignment. Manifest updated for new GitHub JPEGs.
