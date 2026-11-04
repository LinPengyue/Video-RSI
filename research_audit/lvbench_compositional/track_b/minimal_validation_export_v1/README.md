# Track B → Track A minimal validation export v1

Read-only packaging of the fixed **5 Seen + 2 Unseen** pilot for Track A *loading/plumbing* checks.

**Not** a formal Gold set. **Not** a launch of Track A experiments.

## Files

| File | Contents |
|------|----------|
| `qa_items.json` | QA text, answer + certification status, item/video IDs, A/B windows, necessity |
| `program_graphs.json` | 7 normalized directed graphs (nodes/edges/L1/L2/I/O/time/evidence status) |
| `video_manifest.json` | Video IDs, local path if resolved, time base, hashes |
| `split_manifest.json` | Fixed 5/2 roles, structure labels, training-exposure limits |
| `schemas/*.json` | Lightweight JSON Schemas |
| `VALIDATION_REPORT.json` | Schema/join-key validation result |

## Join keys

- `item_id` joins `qa_items` ↔ `program_graphs` ↔ `split_manifest.items`
- `video_id` joins `qa_items` ↔ `video_manifest`

## Loading example

```python
import json
from pathlib import Path
root = Path('research_audit/lvbench_compositional/track_b/minimal_validation_export_v1')
qa = {x['item_id']: x for x in json.loads((root/'qa_items.json').read_text())['items']}
graphs = {x['item_id']: x for x in json.loads((root/'program_graphs.json').read_text())['graphs']}
videos = {x['video_id']: x for x in json.loads((root/'video_manifest.json').read_text())['videos']}
assert set(qa) == set(graphs)
for item_id, row in qa.items():
    assert row['video_id'] in videos
```

## Limits (mandatory)

- Answers are `HUMAN_REFERENCE_OR_HISTORICAL_NOT_FORMAL_GOLD` — **not** formal Gold.
- Chat-approved program sidecars are **not** frame-level video certification.
- P7 windows may be `UNKNOWN_PENDING_SOURCE_SECOND_MAPPING` — do not invent seconds from graphs.
- Pilot Seen/Unseen ≠ formal Seen/Unseen/train exposure.
- Local video SHA (if present) is an engineering fingerprint only.

## Sources

- Pilot inventory/records: `family_level_minimal_validation_pilot_v0.1/`
- Normalized graphs: `normalized_programs_v1/graphs/{item_id}.json`
- Built by `minimal_validation_export_v1.0.0` at export time.

## Validate

```bash
python3 eng/build_minimal_validation_export_v1.py
python3 tests/test_minimal_validation_export_v1.py -v
```
