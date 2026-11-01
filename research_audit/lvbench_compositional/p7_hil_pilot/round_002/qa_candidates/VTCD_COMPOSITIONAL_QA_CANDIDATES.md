# VTCD Compositional QA Candidates (analysis only — not Gold)

**Facts usable (USER-verified):**  
- A ≈168–170s: REMOVE_JACKET  
- A ≈184s: Fan Zhendong text  
- B ≈269s: Fan Zhendong text  
- A↔B: SAME_PERSON (user; both-clip identity inspection)

**Not claimed:** `COMPOSITION_NECESSITY_VERIFIED` · no formal Gold QA

Necessity is judged **per question wording**, not from identity ACCEPT alone.

---

## C1 — Name → earlier jacket action

**Question (draft):**  
“What does Fan Zhendong do with the (red) jacket in the earlier segment of this video?”

| Field | Content |
|-------|---------|
| Evidence A | REMOVE_JACKET (~168–170s) + Fan text (~184s) |
| Evidence B | Fan text (~269s) — optional for this wording |
| Directed program | Identify named athlete → query earlier jacket action |
| Expected answer | Removes / takes off the jacket |
| A-only | **Likely YES** — A contains both name text and remove action |
| B-only | **No** — name only, no jacket remove |
| A+B unique? | Not required; A already sufficient under this wording |
| Duplicate? | Same family pattern as Sierra ID→action calibration; new video |
| Necessity risk | **HIGH A-only shortcut** |
| Verdict | Poor composition candidate unless question **forbids** using A’s name text (hard to enforce) |

---

## C2 — PREVIOUS RESULTS referent → earlier jacket action

**Question (draft):**  
“What jacket-related action did the athlete who appears with the PREVIOUS RESULTS name graphic perform earlier?”

| Field | Content |
|-------|---------|
| Evidence A | REMOVE_JACKET |
| Evidence B | PREVIOUS RESULTS + Fan Zhendong text |
| Directed program | Select person via B graphic → bind SAME_PERSON → query A action |
| Expected answer | Removes / takes off jacket |
| A-only | **Risk remains** — A also shows Fan text near same person; model may answer without B |
| B-only | **No** — no remove action |
| A+B | Supports bind + action; may not be *necessary* if A name≈B name |
| Duplicate? | Related to C1; not independent family if both reduce to name→remove |
| Necessity risk | **MEDIUM–HIGH** (A contains same name cue) |
| Verdict | Better *framing* than C1, but Fan-in-A still threatens necessity |

---

## C3 — Remover → later on-screen identity text (B-only text target)

**Question (draft):**  
“What name appears on the later PREVIOUS RESULTS graphic for the athlete who removed a jacket earlier?”

| Field | Content |
|-------|---------|
| Evidence A | REMOVE_JACKET (+ Fan text in A at ~184s) |
| Evidence B | Fan Zhendong on PREVIOUS RESULTS (~269s) |
| Directed program | Observe remove in A → bind → read B graphic name |
| Expected answer | Fan Zhendong |
| A-only | **Likely YES** — Fan text already appears in A (~184s) |
| B-only | Name without confirming who removed jacket |
| A+B | Redundant for name if A already shows it |
| Necessity risk | **HIGH A-only** (same name string in A) |
| Verdict | Weak composition; do not mint as necessity-pass without blind test proving A-only fails |

---

## C4 — Cross-window temporal order

**Question (draft):**  
“Does Fan Zhendong remove the jacket before or after the PREVIOUS RESULTS identity graphic appears?”

| Field | Content |
|-------|---------|
| Evidence A | Remove ~168–170s; Fan text ~184s |
| Evidence B | PREVIOUS RESULTS Fan text ~269s |
| Directed program | Localize remove time → localize PREVIOUS RESULTS time → order |
| Expected answer | **Before** (approx. remove ≪ PREVIOUS RESULTS window) |
| A-only | Sees remove; **does not** see PREVIOUS RESULTS graphic (unless confused with A’s later Fan text — **wording hazard**) |
| B-only | Sees PREVIOUS RESULTS; no remove |
| A+B | Can order remove vs PREVIOUS RESULTS board |
| Duplicate? | No prior P7 VTCD gold |
| Necessity risk | **MEDIUM** — if “PREVIOUS RESULTS” is explicit, A-only should fail; if model equates any Fan lower-third in A with that graphic, shortcut |
| Verdict | **Most promising** among this set; still needs formal A-only/B-only/A+B with fixed wording |

---

## C5 — Identity match as the QA itself (not recommended as composition gold)

**Question (draft):**  
“Is the person who removes the jacket the same person named on the later PREVIOUS RESULTS graphic?”

| Field | Content |
|-------|---------|
| Maps to | User’s CROSS_CLIP_IDENTITY_BINDING task (already ACCEPT) |
| A-only | May answer yes via Fan text in A + remove |
| B-only | Incomplete without remove |
| A+B | Matches user review path |
| Necessity risk | **HIGH A-only** once Fan∈A |
| Verdict | Valid **identity** item; **not** automatic composition-necessity gold |

---

## Summary table

| ID | Necessity outlook | Next step |
|----|-------------------|-----------|
| C1 | Fail likely (A-only) | Drop or keep as negative control |
| C2 | Weak–medium | Optional if C4 fails |
| C3 | Fail likely (A-only) | Drop / negative control |
| C4 | Best candidate | Formal necessity pack if approved |
| C5 | Identity≠necessity | Do not auto-promote |

## Review plan (if proceeding)

1. Freeze **one** question string (prefer C4).  
2. A-only / B-only / A+B packets with **same** question; no gold in reviewer materials.  
3. True access isolation (not GitHub `SEALED_*` filename).  
4. User or independent reviewer; Cursor does not adjudicate necessity alone.  
5. Record pass/fail; only then consider Gold.

**No formal Gold QA generated this round.**
