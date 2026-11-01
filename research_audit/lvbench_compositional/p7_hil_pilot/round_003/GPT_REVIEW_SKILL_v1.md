# GPT Review Skill v1 — Track B P7 (in-context only)

**Purpose:** Reusable judgment reference for GPT/Cursor when preparing candidates and recording reviews.  
**Not:** weight training, auto-certification, or replacement of the human reviewer.  
**Sources:** Track A pilot_v2_2; VTCD Round 2 user review; TJR Round 3 revision record.

---

## A. USER explicit / case judgments (authoritative)

### Ownership labels
- `USER_CASE_JUDGMENT` — one video/clip decision; not a global rule.  
- `USER_EXPLICIT_RULE` — only when the user states a standing rule.  
- GPT inference ≠ user rule until confirmed.

### Layer split (USER_EXPLICIT — VTCD Round 2)
1. **EVENT_VERIFICATION** — did the action/state happen in the clip?  
2. **CROSS_CLIP_IDENTITY_BINDING** — same person across A and B? Inspect **both** clips’ identity evidence.  
3. **QA_COMPOSITIONAL_NECESSITY** — for a **specific** question, is A+B required? Per-question; **not** implied by identity ACCEPT.

### Positive cases
| Case | User fact |
|------|-----------|
| Track A `LVCOMP-V2-002/003` | Named person → later action (shoe remove / slap); calibration only, not P7 new family |
| VTCD A | `REMOVE_JACKET` ≈168–170s; Fan text ≈184s |
| VTCD B | Fan text ≈269s; A↔B `SAME_PERSON` via Fan text in **both** |
| VTCD QA framing | User accepted C2/C4 as **candidates**; overlay may be explained as PREVIOUS RESULTS（过往成绩）; necessity still untested |
| TJR A | Green dragon carries prince toward palace (1100–1125) |
| TJR B | Prince drums on stage (1200–1220); `SAME_PERSON` via appearance |
| TJR QA (final) | Q: 打鼓的王子更早乘坐什么前往王宫？ A: **绿色的龙** |

### Negative / rejected binds
- TJR 315–335 royal cast ↛ later stage performers → `NO_VALID_EARLY_WINDOW_FOUND`. Do not silently repair.

---

## B. GPT / assistant mistakes (do not repeat)

| Error | Correction |
|-------|------------|
| Fan text in A ⇒ identity bind does not need B | Identity **task** still requires both clips |
| Identity ACCEPT ⇒ composition necessity pass/fail | Necessity is **per QA wording** |
| Contact-sheet “put on” vs user “remove” | Prefer continuous-video **user** polarity |
| Force purple-near-king → drums | Wrong early window / cast |
| Original TJR Q “更早做了什么？” with answer “拥抱了国王” | Hug is **visible in B**; does not cleanly ask an A-anchored fact — user **revised** Q/A to dragon transport in A |
| Treat ChatGPT-organized GitHub JSON as missing review because local file isn’t on remote | Review **happened**; record is organized copy with provenance |

---

## C. GPT suggestions (pending user confirmation — not rules)

- When drafting cross-interval QA, put the **answer fact** in the intended evidence interval; use the other interval mainly for identity/referent.  
- Prefer temporal-order or B-referent→A-fact forms when name/action co-occur in one clip (VTCD Fan-in-A shortcut risk).  
- Preserve original Q/A in history when revising; never silent overwrite.  
- Human-first page: watch → facts/identity → then reveal candidate question.

---

## D. What GPT may / may not do

| May | Must not |
|-----|----------|
| Prepare clips/HTML; propose candidates; log user text | Invent watch minutes, facts, or ACCEPT |
| Sync GitHub-organized user records | Claim Gold / Seen·Unseen / necessity verified |
| Cite this skill in-context | Auto-upgrade status stacks |
