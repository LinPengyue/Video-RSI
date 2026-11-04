# Dataset Card — LongVideoCompBench (DEV v0.1.0)

## Summary

Long-video compositional QA with program-graph structure, human necessity/review records, and strict provenance.

## Video sources and license

- Primary source pool: **LVBench** videos referenced by ID.
- Videos are **not** copied into this git tree.
- License status per row: `UNKNOWN_NOT_DECLARED_OPEN` until counsel/dataset owners confirm.
- **No open license is claimed by this card.**

## Annotation workflow

1. Human / GPT / Cursor produce candidates into `staging/`.
2. `import_annotation_batch.py` validates schema, FKs, duplicates, graph integrity, split rules.
3. Accepted rows append to DEV JSONL with `formal_gold=false`.
4. Releases under `releases/` are immutable snapshots; edits require a new version + changelog reason.

## QA and program graph formats

- JSONL + JSON Schema in `schemas/`.
- Stable IDs: `lvcb:qa:{source_item_id}`, `lvcb:pg:{source_item_id}`, `lvcb:ev:{source_item_id}:{role}`.
- Original question/answer preserved when present; never inferred from graph outputs.

## Seen / Unseen meaning

- **Frozen 5+2**: Track A minimal-validation pilot roles; immutable.
- **Proposed 7+4 DEV**: construction target (Seen += A, P7_R4_F1; Unseen += B, P7_R4_F2). Status **`PROPOSED`** until human approval is recorded. Not a formal promotion.

## Scientific limits

- Sidecar / chat-approved graphs ≠ frame certification.
- `SOURCE_WINDOW_ONLY` is not `FRAME_CERTIFIED`.
- Necessity tests are not auto-passed from program graphs.
- A/B seeds currently lack original QA text in authoritative sources → `GRAPH_ONLY`.

## Known biases

- Language: frozen Seen mostly English; several Unseen Chinese.
- Video reuse (e.g., SP201/SP202 share a video).
- Operator Layer2 may collapse fine-grained constraints (e.g., name abbreviation matching).

## Reproduction / citation

TBD until a public release is approved.
