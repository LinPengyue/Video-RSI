# User Annotation Rubric — P7 HIL

**Purpose:** Accumulate *your* review standards over time.  
**Owner:** USER (human reviewer). Cursor only records what you state or confirm.  
**Last update:** 2026-11-01 (after VTCD A/B continuous review)

## Rule classes (strict)

| Class | Meaning |
|-------|---------|
| `USER_EXPLICIT_RULE` | You explicitly stated this as a standing rule. |
| `USER_CASE_JUDGMENT` | Case-level ACCEPT/REJECT for a specific event/clip — not automatically a general rule. |
| `INFERRED_RULE_PENDING_CONFIRMATION` | Pattern suggested by ≥2 of your decisions; **not** confirmed until you say so. |
| `ASSISTANT_SUGGESTION` | Cursor/ChatGPT suggestion only — **not** your standard. |
| `ASSISTANT_ERROR_CORRECTED` | Assistant claim you rejected; retained so it is not reused. |

Model guesses must never be written as confirmed rules.

---

## Layer distinction (USER_EXPLICIT_RULE)

User explicitly required separating these layers (2026-11-01):

| id | class | rule | source_event | date |
|----|-------|------|--------------|------|
| UR-001 | `USER_EXPLICIT_RULE` | **`EVENT_VERIFICATION`**: whether a stated action/state truly occurs in a clip (e.g., A remove-jacket). | VTCD A continuous review | 2026-11-01 |
| UR-002 | `USER_EXPLICIT_RULE` | **`CROSS_CLIP_IDENTITY_BINDING`**: whether person in clip A and person in clip B are the same; requires inspecting identity evidence **in both** clips for that task. | VTCD A↔B identity review | 2026-11-01 |
| UR-003 | `USER_EXPLICIT_RULE` | **`QA_COMPOSITIONAL_NECESSITY`**: whether a **specific** composed question requires A+B; must be judged per question; **not** implied by identity ACCEPT; **not** implied by rejecting an assistant shortcut argument about identity. | User correction of ChatGPT logic | 2026-11-01 |
| UR-004 | `USER_EXPLICIT_RULE` | Completing layers 1–2 must **not** auto-set `COMPOSITION_NECESSITY_VERIFIED`. | Same | 2026-11-01 |

---

## Case-level judgments (not general rules)

| id | class | case | accepted | rejected / superseded | uncertainty | reusable_across_qa | source | date |
|----|-------|------|----------|----------------------|-------------|-------------------|--------|------|
| CJ-001 | `USER_CASE_JUDGMENT` | VTCD A context 158–191 | Action **REMOVE_JACKET** (脱下外套); playback ~10–12s → source ≈**168–170s**; Fan Zhendong text playback ~26s → source ≈**184s** | Prior assistant “possible put-on” polarity suspicion for this event | None reported | Action+name-in-A facts may be reused; still subject to per-QA necessity | `user_reviews/VTCD_USER_REVIEW_2026-11-01.json` | 2026-11-01 |
| CJ-002 | `USER_CASE_JUDGMENT` | VTCD B context 260–285 | Fan Zhendong text playback ~9s → source ≈**269s** | — | None reported | Name-in-B reusable as identity evidence | same | 2026-11-01 |
| CJ-003 | `USER_CASE_JUDGMENT` | VTCD A↔B identity | **SAME_PERSON**; basis: Fan Zhendong identity text in **both** A and B | Assistant claim that Fan-in-A alone completes A↔B identity task | None; no more footage needed | Identity bind reusable; **≠** QA necessity | same | 2026-11-01 |

---

## Assistant errors corrected

| id | class | wrong_claim | user_correction | date |
|----|-------|-------------|-----------------|------|
| AE-001 | `ASSISTANT_ERROR_CORRECTED` | “A already shows Fan Zhendong ⇒ A/B identity match does not need both videos” | Identity task was “is A’s person the same as B’s person?” — must observe identity cues in **both** clips | 2026-11-01 |
| AE-002 | `ASSISTANT_ERROR_CORRECTED` | (Implied) Treating identity bind or Fan-in-A as deciding compositional necessity / disqualifying identity | Necessity is **per QA**; identity ACCEPT stands; Fan-in-A is a **shortcut risk for some QAs**, not a void of CROSS_CLIP_IDENTITY_BINDING | 2026-11-01 |

---

## Assistant suggestions (still not user rules)

| id | class | suggestion | date |
|----|-------|------------|------|
| AS-001 | `ASSISTANT_SUGGESTION` | Prefer continuous video over stills for action polarity | 2026-11-01 |
| AS-002 | `ASSISTANT_SUGGESTION` | Do not treat PREVIOUS RESULTS alone as live identity without cross-check — **partially superseded**: user completed cross-check via Fan text in A **and** B | 2026-11-01 |
| AS-003 | `ASSISTANT_SUGGESTION` | Mark UNCERTAIN when occlusion prevents polarity | 2026-11-01 |
| AS-004 | `ASSISTANT_SUGGESTION` | Among VTCD QA drafts, temporal-order vs PREVIOUS RESULTS (C4) is the most promising necessity candidate; C1/C3 likely A-only | 2026-11-01 |

---

## Inferred rules pending confirmation

_None promoted. Do not treat AS-004 as USER_EXPLICIT_RULE unless you confirm._

---

## Non-goals

- No auto-reviewer model training  
- No Cursor/ChatGPT final semantic certification in place of you  
- No auto `COMPOSITION_NECESSITY_VERIFIED` after event/identity ACCEPT  
