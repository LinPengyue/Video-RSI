# User Annotation Rubric — P7 HIL

**Purpose:** Accumulate *your* review standards over time.  
**Owner:** USER (human reviewer). Cursor only records what you state or confirm.  
**Status:** Framework seeded Round 002 — **no confirmed user rules yet**.

## Rule classes (strict)

| Class | Meaning |
|-------|---------|
| `USER_EXPLICIT_RULE` | You explicitly stated this as a standing rule. |
| `INFERRED_RULE_PENDING_CONFIRMATION` | Pattern suggested by ≥2 of your decisions; **not** confirmed until you say so. |
| `ASSISTANT_SUGGESTION` | Cursor/ChatGPT suggestion only — **not** your standard. |

Model guesses must never be written as confirmed rules.

## Seeded assistant suggestions (not user rules)

| id | class | suggestion | source | date |
|----|-------|------------|--------|------|
| AS-001 | `ASSISTANT_SUGGESTION` | Prefer continuous video over stills for action polarity (put on vs take off). | Round 2 pack design | 2026-11-01 |
| AS-002 | `ASSISTANT_SUGGESTION` | Do not treat PREVIOUS RESULTS overlay alone as live identity proof without A↔B visual continuity. | Round 2 pack design | 2026-11-01 |
| AS-003 | `ASSISTANT_SUGGESTION` | Mark UNCERTAIN when occlusion / cut / ambiguous motion prevents polarity call. | Round 2 pack design | 2026-11-01 |

## User explicit rules

_None yet. Append rows after you return decisions._

| id | class | rule | accepted_facts | rejected_phrases | why_reject | extra_evidence_needed | when_uncertain | reusable_across_qa | source_event | date |
|----|-------|------|----------------|------------------|------------|----------------------|-----------------|---------------------|--------------|------|
| — | — | — | — | — | — | — | — | — | — | — |

## Inferred rules pending confirmation

_None yet._

## Log protocol (when you reply)

For each reviewed item, Cursor will append:

1. What you **accepted**
2. What phrasing you **rejected** and why
3. Extra evidence you required
4. Cases you marked **UNCERTAIN**
5. Which facts you allow to **reuse** across QA

Then ask you whether any new line should be promoted to `USER_EXPLICIT_RULE`.

## Non-goals this phase

- No auto-reviewer model training
- No Cursor/ChatGPT final semantic certification
- Completing event review does **not** auto-set `COMPOSITION_NECESSITY_VERIFIED`
