# Track B Human-First Flow v1 (suggested)

Lightweight production loop — not a new status ontology.

## Return path (confirmed)

```text
User watches locally (Remote SSH OK)
  → local review JSON
  → ChatGPT organizes + pushes GitHub
  → Cursor syncs SHA and indexes
```

Do not require uploading the local JSON to the remote machine each time.

## Four-step loop

1. **Prepare one item** — continuous clips + human-first HTML; hide machine hypothesis until after watch.  
2. **User judges once** — event facts → A↔B identity → accept / revise / reject QA.  
3. **Record with provenance** — keep original Q/A history; tag `USER_*` vs GPT suggestion; necessity/`Gold`/`Seen·Unseen` stay off until separately tested.  
4. **Skill update** — append case + assistant errors to `GPT_REVIEW_SKILL_v1.md`; reuse verified events; no re-watch.

## After a candidate is accepted (optional later)

- Only if pursuing formal quality: same frozen question × A-only / B-only / A+B with real isolation.  
- Pass ⇒ consider Gold path; fail ⇒ keep as negative/control.  
- Never auto-pass necessity from identity alone.

## Guardrails

- P0 frozen; `run_004=NOT_STARTED` until ready.  
- Track A frozen unless user restarts.  
- Sealed untouched; partition `UNASSIGNED` until structural split exists.  
- One item (or tiny batch) per round; scale only after the loop is stable.

## Round 3 lesson

Process works. Main QA construction bug to avoid: answering from the **referent** interval (B hug) when the question claims an **earlier** (A) fact — fix by revising wording so the answer is A-anchored (green dragon).
