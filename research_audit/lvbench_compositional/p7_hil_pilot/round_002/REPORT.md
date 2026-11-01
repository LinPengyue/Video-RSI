# P7 Round 2 Report — User Video Review Kickoff

**Branch:** `research/lvbench-comp-p7-hil-pilot`  
**Start HEAD:** `6bdb7e92625f13030fdca3120cec442d98152b18`  
**This commit:** `92ec312e017816a686804d9de002d38fc5fc6012`  
**Data partition:** `UNASSIGNED` · **`run_004`:** `NOT_STARTED` · P0 untouched

## Status (honest)

| Flag | Value |
|------|-------|
| `REVIEW_PACKAGE_READY` | **true** |
| `USER_REVIEW_PENDING` | **true** |
| `USER_VIDEO_REVIEW_COMPLETED` | **false** |
| `RELATION_VERIFIED` | **false** |
| `COMPOSITION_NECESSITY_VERIFIED` | **false** |

Preparing the pack ≠ human verification success.

## Where to review

1. **Primary — VTCD:**  
   `round_002/vtcd_review/REVIEW_START_HERE.html`  
   Continuous A **163–186 s** and B **265–280 s** (context ±5 s available).  
   Full instructions: `ROUND2_REVIEW_START_HERE.md`

2. **Templates (blank):** `templates/review_decisions.template.{json,csv}`

3. **Rubric framework:** `USER_ANNOTATION_RUBRIC.md` (no `USER_EXPLICIT_RULE` yet)

4. **Optional — TJR:** `tjr_relocate/OPTIONAL_REVIEW_START_HERE.html`

## Continuous clips user can play now

| ID | Path (under `round_002/`) | Source times |
|----|---------------------------|--------------|
| VTCD A context | `vtcd_review/media/A_context_158_191.mp4` | 158–191 (core 163–186) |
| VTCD A core | `vtcd_review/media/A_core_browser_163_186.mp4` | 163–186 |
| VTCD B context | `vtcd_review/media/B_context_260_285.mp4` | 260–285 (core 265–280) |
| VTCD B core | `vtcd_review/media/B_core_browser_265_280.mp4` | 265–280 |
| TJR early cand. | `tjr_relocate/media/early_candidate_dragon_ride_1100_1125.mp4` | 1100–1125 |
| TJR late ref. | `tjr_relocate/media/late_dual_performers_1200_1220.mp4` | 1200–1220 |

Media is **gitignored**; rebuild with `scripts/build_round2_review_pack.py` if missing.

## Judgments requested (user only)

- VTCD A: action polarity/type, span, ID cues, uncertainty  
- VTCD B: visible person/clothes/text; same-person as A? 是/否/证据不足  
- Optional TJR: whether 1100–1125 matches 1200–1220 performers  

Cursor will **not** fill `review_decisions` for you.

## TJR relocate

- Original purple-near-king → drums: **`NO_VALID_EARLY_WINDOW_FOUND`**  
- Bounded search logged in `tjr_relocate/TJR_EARLY_WINDOW_RELOCATE_RESULT.json`  
- New optional candidate only (dragon-ride ~1110 vs stage ~1200); **not** relation-verified; do not double-count families

## Evidence still needed

- Your continuous-video decisions for VTCD (blocking)  
- Optional TJR candidate call  
- After events+identity: separate necessity pack (A/B isolation; do not treat public `SEALED_FROM_REVIEWER` filename as true isolation)

## Tests run

```text
python .../round_002/tests/test_round2_review_pack.py
```

Checks: source/clips exist, windows legal, manifest↔paths/sha256, templates stay `PENDING_USER_REVIEW`, status flags honest, no `run_004`, P0 present, TJR original = NO_VALID.

## Stop

No QA batching, no video expansion, no `run_004`, no P0 edits until user returns review feedback.
