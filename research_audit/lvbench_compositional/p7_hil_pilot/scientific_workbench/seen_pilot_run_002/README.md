# Seen Human Annotation Pilot · run_002

Necessity-aware **pre-screen** packets after run_001 scientific feedback.

- Status: `PENDING_HUMAN_VIDEO_REVIEW`
- Auto-approved structured graphs: **0**
- Does **not** overwrite run_001 records
- Formal Seen / Gold / train_exposed / pool freeze / expensive RSI: **all false**

## Workbench

1. `python3 serve_workbench.py --host 127.0.0.1 --port 8770`
2. Open http://127.0.0.1:8770/
3. Tab **Seen Pilot run_002**

## Key artifacts

| File | Role |
|------|------|
| `CANDIDATE_SUPPLY_AUDIT.md` / `.json` | Honest inventory |
| `screening/SCREENING_RESULTS.json` | Heuristic necessity pre-screen |
| `review_packs/` | Priority human packets (≤6) |
| `diagnostic_negatives/` | Shortcut/unresolved diagnostics (not approvals) |
| `ISOLATION_CHECK.json` / `MANIFEST.json` | Isolation + SHA |

Rebuild: `python3 eng/build_seen_pilot_run_002.py`
