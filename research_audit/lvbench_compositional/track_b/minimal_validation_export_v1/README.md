# Track B → Track A minimal validation export v1.1

Read-only packaging of the fixed **5 Seen + 2 Unseen** pilot for Track A *loading/plumbing* checks.

**Not** a formal Gold set. **Not** a launch of Track A experiments.

## Layout

| Path | Role |
|------|------|
| `qa_items.json` / `program_graphs.json` / `video_manifest.json` / `split_manifest.json` | Full scientific audit pack |
| `projections/inference_safe/` | Ordinary Track A inference projection |
| `projections/scorer_private/` | Scorer-only answers (not for inference) |
| `NECESSITY_DIFF_REPORT.json` | Inventory vs authoritative necessity |
| `WINDOW_AVAILABILITY_REPORT.json` | Fixed A/B window eval availability |
| `LANGUAGE_AND_STRUCTURE_LIMITS_REPORT.json` | en/zh split + C2 abbreviation constraint |
| `CHANGE_LIST_WP1_1.md` | Patch change list |
| `schemas/*.json` | Strict JSON Schemas |
| `VALIDATION_REPORT.json` | Schema + join + uniqueness + leak scan |

## Join keys

- `item_id` joins QA ↔ graphs ↔ split
- `video_id` joins QA ↔ video_manifest

## Necessity authority

Track A must use `necessity.necessity_authoritative` only. Provenance records are retained under `necessity.provenance_records`.

## Limits

- Answers: `HUMAN_REFERENCE_OR_HISTORICAL_NOT_FORMAL_GOLD`
- Unseen graphs omitted from inference-safe projection
- P7 windows UNKNOWN ⇒ `fixed_ab_window_eval=BLOCKED`
- C2 abbreviation-matching constraint reported; annotations not rewritten
- Local video SHA is engineering-only

## Validate

```bash
python3 eng/build_minimal_validation_export_v1.py
python3 tests/test_minimal_validation_export_v1.py -v
```

Built by `minimal_validation_export_v1.1.0`.
