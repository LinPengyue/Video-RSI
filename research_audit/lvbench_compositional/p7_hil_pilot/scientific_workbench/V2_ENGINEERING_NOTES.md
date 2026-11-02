# Scientific Workbench v2 — engineering notes

## What shipped
- Form upgrade: expandable reference templates (not exported), insert blank template, localStorage + draft history, import/export compatible with v1 key `p7_scientific_judgments_v1`.
- Single-window form mode for S1–S4.
- Window A: program graph library + compare (full digraph / subgraph-edge / operator-only). Distinguishes `USER_APPROVED_STRUCTURED_GRAPH` / pending / DEMO.
- Window B: operator library with 尚不可计算 coverage layers (unchanged while Seen train pool unfrozen).
- Four USER-approved structured graphs v0.2 under `data/approved_graphs_v0.2/` (F2, C2, TJR, F1). Not formal Unseen/Gold.
- Node-id-independent typed digraph isomorphism in `eng/structure_checks.py` (type/IO/clip_role/time/edges); no unapproved alias merge.
- JSON import/export fidelity via `v2/judgment_io.js` + browser HTTP roundtrip test.
- Deterministic checks: `eng/structure_checks.py` + `eng/tests` (22 OK).
- DEMO graphs marked and excluded from scientific equivalence.

## Unchanged scientific archives
- `SCIENTIFIC_JUDGMENTS_DIRECTED_PROGRAMS_CORRECTED_F1_F3.json` left as user/GPT text (no rewrite this release).
- No formal Unseen/Seen/Gold promotion.
- No sealed / Track A / new QA.
- Precise timing and operator vocabulary remain `PENDING_SCIENTIFIC_APPROVAL`.

## Seen Pilot run_001 (engineering prep)
- Path: `seen_pilot_run_001/` (catalog, exclusion, isolation, packs, media, blank judgments).
- Workbench tab: **Seen Pilot run_001** — status `PENDING_HUMAN_VIDEO_REVIEW` only.
- Separate localStorage key; does not overwrite scientific judgments or approved graphs.
- Hard isolation blocks Unseen/approved-graph/test video IDs; historical train label ≠ formal Seen.

## Still needed from USER/GPT
1. Freeze approved operator vocabulary version + definitions (replace provisional labels).
2. Approve precise timing / time_condition fields currently marked pending.
3. Structured program graphs for remaining pending raw-text items.
4. Frozen Seen training pool (explicit graph/UID list), separate from candidate bucket labels.
5. Controlled train-exposure evidence if coverage should become computable.
6. Confirm whether DEMO sandbox comparisons should remain visible in production UI.
7. Whether any of the four approved graphs should later be independently reviewed for formal Unseen/Gold (engineering will not auto-promote).
8. Human review of Seen Pilot run_001 packs (events/bind/program draft) — engineering will not auto-certify.
