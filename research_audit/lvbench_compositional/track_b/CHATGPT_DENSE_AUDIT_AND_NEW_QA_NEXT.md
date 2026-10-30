# Track B — Dense audit import + next QA evidence (2026-10-30)

Responds to `CHATGPT_AUDIT_66B01DB_AND_NEXT_DUAL_TRACK_2026-10-30.md`.  
Imported: `CHATGPT_VIDEO_DRIVEN_DESIGN_2026-10-30.jsonl` (6 rows; DESIGN-002 = alternate wording of DESIGN-001 events).  
All statuses remain `UNASSIGNED` / `HYPOTHESIS_NOT_SUPPORTED`. Sealed pool untouched. No auto-`SUPPORTED`.

## P0 Football T1yhBv1ytzw — timed witnesses

### Scoreboard anchors (file time / broadcast clock / score)
| File | Broadcast | Score | Asset |
|---|---|---|---|
| 29:45 | ~29:32 | BRI 0–0 LIV | prior `score_state_keyframes/t_29_45.jpg` |
| 31:30 | ~31:17 | BRI 0–1 LIV | `t_31_30.jpg` |
| 38:40 | ~38:27 | BRI 0–1 LIV | `t_38_40.jpg` |
| 39:40 | ~39:27 | BRI 1–1 LIV | `t_39_40.jpg` |
| 42:15 | — | BRI 1–1 LIV | `t_42_15.jpg` |

### Live vs replay windows (new extracts)
| Window | File time | Role | Review sheet / local clip |
|---|---|---|---|
| LIV live pre/aftermath | 29:50–30:14 | Live lead-in + celebration onset (~30:10) | `chatgpt_review_assets/T1yhBv1ytzw/liv_live_pre_2950_3014.jpg` + `local_media/.../liv_live_attack_2955_3015.mp4` |
| LIV replay block | 30:30–31:19 | Replay of first goal attack (not a second event) | `liv_replay_mark_3030_3119.jpg` + `liv_replay_block_3032_3115.mp4` |
| BRI live attack | 38:45–39:19 | Live equalizer window | `bha_live_3845_3919.jpg` + `bha_live_attack_3848_3915.mp4` |
| BRI replay block | 39:10–40:14 | Replay / celebration continuation | `bha_replay_mark_3910_4014.jpg` + `bha_replay_block_3915_4012.mp4` |
| Action stills | selected | Tiny review JPEGs | `tiny_stills/*.jpg` |

### Attack-mechanism status (honest)
- **Order of score changes**: supported by overlays (LIV 0–1 first, then BRI 1–1).
- **Kick origin / set-piece vs open play / final touch / scorer**: still **`UNKNOWN_PENDING_CONTINUOUS_VIDEO_AND_INDEPENDENT_REVIEW`**.
- Celebration of ELLIOTT #19 ≠ proof he scored. Set-piece-like BRI box play is a **candidate**, not confirmed.
- Do not invent striker names or technique.

### CG-SPORT-DESIGN-001 necessity prep
Question preserved with `gold_answer=null`. Structured check in `T1yh_DESIGN001_NECESSITY_CHECK.jsonl`:
- A-only (LIV window) can answer “who led first / 0–1” from boards → **partial shortcut**.
- B-only (BRI window) can answer equalizer 1–1 and may show set-piece candidate → **partial**.
- Full compare-of-two-attack-origins + order needs both windows **if** attack types are video-verified.
- Until kick types verified: keep `HYPOTHESIS_NOT_SUPPORTED`; DESIGN-002 not counted as independent item.

## P1 Table tennis VTCDQYYKA9o
- 1 fps garment window 02:40–03:20: `chatgpt_review_assets/VTCDQYYKA9o/garment_0240_0320_1fps.jpg`
- Local clip: `local_media/VTCDQYYKA9o_garment/garment_0240_0320.mp4`
- Status: appearance-change / re-ID hypothesis advanced; **formal identity & rally score UNKNOWN** (`CG-TT-OBS-001`).

## P1 Athletics Z86xysw5Ncc
- Finish probe 04:05–06:00 every 5s: `chatgpt_review_assets/Z86xysw5Ncc/finish_probe_0405_0600.jpg`
- Status: intros/start previously visible; **placements not claimed** from this probe (`CG-ATHLETICS-OBS-001`). Finish availability = report via sheet for human review; no auto result.

## P1 CG-NEW continuous / audio
| ID | Action | Status |
|---|---|---|
| CG-NEW-001 | Embrace adjudication clip `local_media/.../embrace_adjudication_0520_0532.mp4` + prior dense sheet | Who-embraces-whom still `ACTION_AMBIGUOUS_PENDING_VIDEO` |
| CG-NEW-002 | Precise 1 fps 04:19–05:05 sheet `precise_0419_0505_1fps.jpg` | Table-push still **not confirmed** → `PENDING_PRECISE_ACTION_TIMECODE` |
| CG-NEW-003 | WAV present; `volumedetect` mean −34.5 dB / max −6.4 dB (signal exists) | Semantic audio content **`AUDIO_NOT_AUDITED`** (no auto-transcript as GT) |

## Isolation
`DEV_CONSTRUCTION` / exposed videos only. Sealed pool not accessed. No batch name-swap QA minted.
