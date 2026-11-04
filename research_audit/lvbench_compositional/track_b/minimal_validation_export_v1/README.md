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
| `CHANGE_LIST_WP1_2.md` | Isolation patch change list |
| `projections/inference_safe/INFERENCE_ACCESS_WHITELIST.json` | Machine-enforced inference file whitelist |
| `schemas/*.json` | Strict JSON Schemas |
| `VALIDATION_REPORT.json` | Schema + join + uniqueness + leak scan |

## Join keys

- `item_id` joins QA ↔ graphs ↔ split
- `video_id` joins QA ↔ video_manifest

## Necessity authority

Scientific audit / scorer-private: use `necessity.necessity_authoritative`.  
Ordinary inference projection: necessity labels are **withheld** (`WITHHELD_SCORER_PRIVATE`).

## Inference access

```python
from eng.inference_access import resolve_allowed_path, open_text
root = Path('.../projections/inference_safe')
text = open_text(root, 'qa_items.json')  # parent escapes raise InferenceAccessError
```

## Limits

- Answers: `HUMAN_REFERENCE_OR_HISTORICAL_NOT_FORMAL_GOLD`
- Unseen graphs omitted; Unseen structure labels withheld from inference split
- Human A-only/B-only necessity is scorer-private only
- P7 windows UNKNOWN ⇒ `fixed_ab_window_eval=BLOCKED`
- C2 abbreviation-matching constraint reported; annotations not rewritten
- Local video SHA is engineering-only

## Validate

```bash
python3 eng/build_minimal_validation_export_v1.py
python3 tests/test_minimal_validation_export_v1.py -v
```

Built by `minimal_validation_export_v1.2.0`.
