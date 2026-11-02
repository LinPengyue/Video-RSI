# Minimal Seen / Unseen Split Proposal (draft — UNASSIGNED)

Aligns with Track A readiness gate (`track_a/TRACK_A_READINESS.md` §5).  
**Not frozen.** No item labeled formal Seen/Unseen until user+ChatGPT approve and necessity passes where required.

## Track A target signature (first study)

`identify_person` + `query_action` with **strict leave-out**: evolution/train holds primitives A and B separately; held-out composition needs both; **no video/UID overlap** train↔test.

## Proposed buckets (design only)

### Seen — primitives (train / evolution)

| Primitive type | Candidate observations (user-accepted) | Videos |
|----------------|------------------------------------------|--------|
| `identify_person` / name graphic | S1 `SIERRA` (JTa); S4 `Fan Z.D.` (VTCD); Track A Sierra lower-third | JTa, VTCD (**2** unique so far for strong name-read) |
| `query_action` | S2 脱鞋 (JTa); Track A shoe-remove + slap; F2 dog later action only if promoted as animal-action primitive | Mostly **JTa** → action diversity **thin** across videos |
| `read_scoreboard` | S3 `BRI 0-0 LIV` (T1yh) | Useful control; **not** a substitute for `query_action` |

**Coverage gap vs Track A gate:**  
- Need ≥8 Seen `identify_person` across ≥4 videos → **now ~2–3 strong name/person IDs on ~2 videos** (far below).  
- Need ≥4 Seen `query_action` across ≥3 videos → **now concentrated on JTa**; Round4 structure answers are composition-side, not certified Seen actions on new videos.

### Seen — composition (optional train composition, not held-out)

Track A V2-002/003 (JTa) remain **calibration / Seen-composition seeds**, not P7 new Unseen.

### Unseen — structure candidates (held-out composition pool — **not assigned**)

| ID | Video | Program | Status for pool |
|----|-------|---------|-----------------|
| VTCD C2 / C4 | VTCDQYYKA9o | name/referent → jacket / temporal order | User-accepted candidates; necessity NOT_TESTED |
| TJR revised | TJR1oYDDTwg | later drummer → earlier transport | User-accepted; necessity NOT_TESTED |
| F1 | Cm73ma6Ibcs | rescuer bind → later snow event | User-confirmed Q/A; necessity NOT_TESTED |
| F2 | LLSJrEgOOtw | dog bind → later play | User-confirmed Q/A; identity risk; necessity NOT_TESTED |
| F3 | Z86xysw5Ncc | early athletes → who finishes first | User-confirmed Q/A; B-only risk; necessity NOT_TESTED |
| F4 | xi6r3hZe5Tg | print ↔ plated reference | ACCEPT but causality conflict → **hold / negative**, not Unseen gold path |

Independent videos touching Unseen-structure **candidates**: VTCD, TJR, Cm73, LLS, Z86 (+ xi6 if kept) ≈ **5–6**, but **formal Unseen count = 0** until necessity + split freeze.

## Leakage / split rules (proposed)

1. If a video contributes Unseen composition, its intervals used in that QA cannot also supply the only train instances of the left-out primitives for that item.  
2. JTa stays primarily Seen/calibration; do not also place new Unseen composition on JTa for the first study.  
3. Development examples ≠ sealed final (sealed remains untouched).  
4. Do not inherit conflicting Track A “v3 unverified Unseen” labels into P7.

## Formal counts **today** (honest)

| Metric | Count |
|--------|------:|
| Formal Seen (split-frozen) | **0** |
| Formal Unseen (split-frozen + necessity) | **0** |
| Formal qualified composition families | **0** |
| User-accepted / confirmed QA **candidates** (P7 cumulative) | **7** (3 prior + F1–F3 confirmed + F4 kept) |
| User-accepted Seen **observations** (R4) | **4** |
