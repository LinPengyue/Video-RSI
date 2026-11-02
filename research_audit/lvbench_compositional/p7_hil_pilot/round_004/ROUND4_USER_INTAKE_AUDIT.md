# P7 Round 4 — USER human-first intake and minimal audit

**Source of truth for user's words:** `user_reviews/ROUND4_USER_REVIEW_2026-11-02_RAW.json` (user-pasted JSON copied verbatim, not user-local file bytes). User personally watched continuous video, reported `15min`. **No independent verification or Gold/Seen/Unseen promotion.**

**Round:** P7 human-review 004, **not** P0 factory `run_004` (still `NOT_STARTED`). **Pool:** exposed DEV only; sealed untouched.

## Counts — no conflation

| Item | Count | What it means |
|---|---:|---|
| User-reviewed candidate items | 8 | 4 Seen-primitives + 4 structure candidates |
| Seen primitive observations marked ACCEPT | 4 | *Observations*, not four unique new training videos or certified Seen tasks |
| Structure candidate QA marked ACCEPT | 2 (F1, F4) | Original user decisions remain; **does not imply answer-complete or composition-valid** |
| Structure candidate QA marked REVISE | 2 (F2, F3) | Proposed replacement wording is stored in the `answer` field |
| New user-reviewed structure families | 4 | Unique candidate video/evidence spines; no necessity pass |
| New qualified independent composition families | **0** | Neither necessity nor structural split certified |
| New Gold QA | **0** | No certification |
| Seen/Unseen assignment | **UNASSIGNED** | Registry / training coverage not frozen |

## Seen primitive facts — USER_CASE_JUDGMENT

- `R4_S1`: USER ACCEPT, visible text `SIERRA`; from historical JTa source, not independent new video.
- `R4_S2`: USER ACCEPT, `脱下鞋子`; historical JTa action reused.
- `R4_S3`: USER ACCEPT, scoreboard `BRI 0-0 LIV`; this is a ReadScoreboardState primitive **not** a replacement for Seen `query_action` or `identify_person`.
- `R4_S4`: USER ACCEPT, visible text **`Fan Z.D.`** (as written). Do **not** silently expand to `Fan Zhendong` in this clip's literal transcription. Existing VTCD other-window user observations may support broader identity separately.

## Four new structure candidates — original USER decisions preserved

| ID | What user established | User QA | Non-overwriting audit note |
|---|---|---|---|
| F1 | Earlier: armed villain threatens cook; **different-looking rescuer** wears blue, white neck scarf, sword and hat. Later: blue/scarf/sword person falls in snow and wipes face. Identity `SAME_PERSON` based on clothing and accessories. | `ACCEPT`, **answer empty** | Original prompt “对峙/持械的那个人” can refer to the *villain* rather than the rescuer. QA is not answer-complete. Suggest refer explicitly to **the person in blue who intervenes**, not gunman. Do not silently rewrite user-approved raw text. |
| F2 | Early black-white dog barks/plays with wood/digs; later dog plays with woman/bucket, pants; early humans too small to identify. | `REVISE` | `answer` field contains the user's **revised animal question**, not an answer. Original checkbox `SAME_PERSON` is ambiguous because the reviewer justifies the **dog** rather than validating a same-*person* bind. Preserve raw; treat dog cross-window identity as user-suggested, human identity unresolved. |
| F3 | A: multiple athletes (Ndure, Thompson, Gay); B: user identifies Tyson Gay as lane-7 winner, deep-red uniform; partial back number “217”. | `REVISE` | `answer` field is user's **revised American-athlete question**, not an answer. Name/lane/kit grounds a proposed Gay bind, but full number `3217` in later view is **not fully visible**; only `217` observed and “3” inferred. Never invent a fully readable number. |
| F4 | User describes purple mesh printing and a plated-food cut; user believes **reference / referenced** relation. `relation=EDIT_JUXTAPOSITION`. User proposes trimming A to its first 10 local seconds to eliminate overlap. | `ACCEPT`; answer `参考与被参考关系` | **Conflict within source**: selected label means edit juxtaposition, free text asserts causal reference relationship. Preserve both. Existing A `1055–1070`, B `1065–1075` overlap 5s; ending A at source 1065 makes intervals abut, but this must **not** be used to manufacture necessity or prove causality. Visual adjacency alone does not verify which scene is a reference or whether the printer used the plated item. Flag `CAUSALITY_UNRESOLVED`. |

**Do not upgrade** F1/F4 to formal QA on account of `ACCEPT`: F1 lacks answer and has wrong-person referent risk; F4 has causal interpretation conflict. F2/F3 are promising **revision-needed** candidates, not completed QAs.

## GPT Skill v1 — observed learning opportunities

- **USER_CASE_JUDGMENT:** Event/actor reference may require distinguishing villain from rescuer (F1); animal referent can replace an unidentifiable human target (F2); multi-athlete identity must use visible lane, clothing, partial bib and named entity jointly (F3); user may judge semantic montage/reference relation (F4).
- **INFERRED_RULE_PENDING_CONFIRMATION / GPT_SUGGESTION:** A QA must name the correct target entity; revision text is not an answer; an edited juxtaposition is not automatically causal; clip non-overlap is not evidence of a directed causal link.
- These are not new `USER_EXPLICIT_RULE` until user clearly states them as general review rules.

## Next minimal steps (do NOT start now as an automatic experiment)

1. Keep all eight user observations and four family candidates, with uncertainty as above. No extra user video viewing unless a specific missing referent is impossible to resolve from the recorded observations.
2. Create one **short repair sheet** for F1–F4: corrected proposed Q wording and provisional answer *only where directly supplied by user observations*. User approves any semantic change; do not fill missing answers by inference.
3. **Before formal labels**, freeze a small, explicit Seen-primitive/Seen-composition vs held-out-composition structural split, with no video/UID leakage, and check necessary primitive coverage. Existing Track A variants disagree on held-out schema: cannot silently inherit a label.
4. Then batch-check question-specific evidence necessity (A-only, B-only, A+B) and answer grounding, with genuinely separate review for a formal claim. Eligible entries only then become qualified families / Gold. Development examples never enter sealed final.
5. Track user minute cost per **accepted-and-qualified evidence family**; 15 minutes for 8 reviewed items is *not* 15 minutes for 8 new benchmark samples.

**Status:** `USER_REVIEW_INTAKEN`; `UNASSIGNED` · `NOT_TESTED` · `Gold=0` · `run_004=NOT_STARTED` · Track A frozen.
