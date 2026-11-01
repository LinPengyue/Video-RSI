# Round 2 — User Review Intake Report

**Date:** 2026-11-01  
**Branch:** `research/lvbench-comp-p7-hil-pilot`  
**Scope:** VTCD continuous A/B only (TJR optional not reviewed)

## 1. How results were recorded

Path: `user_reviews/VTCD_USER_REVIEW_2026-11-01.json`

| Field | Value |
|-------|-------|
| reviewer | `USER` |
| continuous video watched | **yes** |
| A action | `REMOVE_JACKET`（脱下外套） |
| A↔B identity | `SAME_PERSON` |
| identity basis | Fan Zhendong text in **both** A and B (user) |
| review minutes | **null** (not reported; not invented) |
| extra uncertainty | none reported |

**Timestamp conversion (approximate):**

| Observation | Playback on default context | Context start | ≈ Source time |
|-------------|----------------------------|---------------|---------------|
| Remove jacket | ~10–12 s on A | 158 s | **≈168–170 s** |
| Fan text in A | ~26 s on A | 158 s | **≈184 s** |
| Fan text in B | ~9 s on B | 260 s | **≈269 s** |

Precision: playback-offset approximate — **not** frame-accurate.

Layers: `EVENT_VERIFICATION` + `CROSS_CLIP_IDENTITY_BINDING` completed; `QA_COMPOSITIONAL_NECESSITY` **not** tested.

Also updated: `event_cards/event_cards.jsonl` (VTCD), `relations/relation_candidates.jsonl` (VTCD rows), `vtcd_relation_update.json`, `USER_ANNOTATION_RUBRIC.md`, `ROUND2_STATUS.json`.

## 2. Corrected wrong assumptions

| Withdrawn / superseded | Replacement |
|------------------------|-------------|
| Contact-sheet “possible put-on” polarity | USER: **REMOVE_JACKET** |
| “Fan text in A ⇒ identity bind does not need B” | USER: identity task requires inspecting **both** clips |
| Identity ACCEPT ⇒ composition necessity | Necessity stays **`NOT_TESTED`** / per-question |

## 3–4. Potential composed questions & necessity risk

See `qa_candidates/VTCD_COMPOSITIONAL_QA_CANDIDATES.md` (C1–C5).

**Short:** C1/C3 likely **A-only** (Fan text already in A). C4 (remove **before/after** PREVIOUS RESULTS graphic) is the strongest necessity candidate. C5 is identity-shaped, not auto composition gold. **No Gold QA minted.**

## 5. Do you need to watch more video now?

**Not required for VTCD event/identity** — you said no further footage needed.

**Optional next (only if we pursue necessity):**  
- Formal A-only / B-only / A+B on **one frozen question** (prefer C4), with real isolation — not filename `SEALED_*`.  
- TJR optional pack still unread if you want that thread later.

## 6. Status flags

| Flag | Value |
|------|-------|
| `USER_VIDEO_REVIEW_COMPLETED` | true (VTCD scope) |
| `IDENTITY_BINDING_USER_ACCEPTED` | true |
| `COMPOSITION_NECESSITY_VERIFIED` | **false** |
| `run_004` | NOT_STARTED |

Stopped for joint review of QA candidates with you / ChatGPT.
