# Round 2 — Start Review Here

**Status:** `REVIEW_PACKAGE_READY` · `USER_REVIEW_PENDING`  
**Not claimed:** `USER_VIDEO_REVIEW_COMPLETED` / `RELATION_VERIFIED` / `COMPOSITION_NECESSITY_VERIFIED`

## 1. Open the VTCD review UI (primary)

Absolute path:

```text
/home/descfly/lpy/Video-RSI/research_audit/lvbench_compositional/p7_hil_pilot/round_002/vtcd_review/REVIEW_START_HERE.html
```

From repo root:

```bash
xdg-open research_audit/lvbench_compositional/p7_hil_pilot/round_002/vtcd_review/REVIEW_START_HERE.html
# or: google-chrome / firefox with the same path
```

You will play continuous clips for:

| Clip | Source window | Default file |
|------|---------------|--------------|
| A garment | **163–186 s** (context 158–191) | `vtcd_review/media/A_context_158_191.mp4` |
| B overlay | **265–280 s** (context 260–285) | `vtcd_review/media/B_context_260_285.mp4` |

Use pause / ±1s / 0.25×–0.5× in the page. Keyframes are assist-only.

## 2. What to judge (VTCD)

**A:** action (put on / take off / hold / other), approximate span, identity cues, uncertainty.  
**B:** people/clothes/text; whether B’s on-screen person matches A (**是 / 否 / 证据不足**).

Watch first; expand “机器假设” only afterward. Historical “脱外套” is **not** default truth.

## 3. Record answers

- Fill fields in the HTML → **导出审核 JSON**, or  
- Edit blank templates:  
  - `templates/review_decisions.template.json`  
  - `templates/review_decisions.template.csv`  

Paste the filled JSON back in chat, or save under gitignored  
`private_user_reviews/` (do not commit filled private files).

## 4. Optional TJR (after VTCD)

Original purple-near-king → drums: **`NO_VALID_EARLY_WINDOW_FOUND`**.

Optional candidate UI:

```text
.../round_002/tjr_relocate/OPTIONAL_REVIEW_START_HERE.html
```

Windows: early **1100–1125 s** vs late **1200–1220 s**. Identity bind stays unverified until you say so.

## 5. If media missing

```bash
python research_audit/lvbench_compositional/p7_hil_pilot/round_002/scripts/build_round2_review_pack.py
python research_audit/lvbench_compositional/p7_hil_pilot/round_002/tests/test_round2_review_pack.py
```

## 6. Stop line

After this pack is openable, **stop**. No QA minting, no `run_004`, no P0 edits until you return review feedback.
