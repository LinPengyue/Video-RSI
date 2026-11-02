# Scientific Workbench v2 — engineering notes

## What shipped
- Form upgrade: expandable reference templates (not exported), insert blank template, localStorage + draft history, import/export compatible with v1 key `p7_scientific_judgments_v1`.
- Single-window form mode for S1–S4.
- Window A: program graph library + compare (full digraph / subgraph-edge / operator-only). Pending structured confirmation when no approved graph.
- Window B: operator library with 尚不可计算 coverage layers.
- Deterministic checks: `eng/structure_checks.py` + `eng/tests` (16 OK).
- DEMO graphs marked and excluded from scientific equivalence.

## Unchanged scientific archives
- `SCIENTIFIC_JUDGMENTS_DIRECTED_PROGRAMS_CORRECTED_F1_F3.json` left as user/GPT text (no rewrite this release).
- No formal Unseen/Seen/Gold promotion.
- No sealed / Track A / new QA.

## Still needed from USER/GPT
1. Approved operator vocabulary version + definitions.
2. Structured program graphs (`USER_APPROVED_STRUCTURED_GRAPH`) for items with only raw directed-program text.
3. Frozen Seen training pool (explicit graph/UID list), separate from candidate bucket labels.
4. Controlled train-exposure evidence if coverage should become computable.
5. Confirm whether any DEMO sandbox comparisons should remain visible in production UI.
