# Seen Human Annotation Pilot · run_001

Engineering preparation only. **Not** formal Seen certification, train-pool freeze, or Gold.

## Status

After scientific review ingest: packs are `SCIENTIFIC_REVIEW_INGESTED`.

- 3 compositional **candidate** graphs approved (SP001/SP002/SP005) — **not** formal Seen/Gold
- 2 not approved (SP003/SP004)
- Forbidden formal gates remain false: `formal_seen_train`, `train_exposed`, `formal_gold`, pool freeze, expensive Track A RSI

See `SCIENTIFIC_REVIEW_INGEST_REPORT.md` and `scientific_reviews/`.

## Workbench

1. Serve: `python3 serve_workbench.py --host 127.0.0.1 --port 8770`
2. Open: http://127.0.0.1:8770/
3. Tab: **Seen Pilot run_001**

Separate localStorage key; does not overwrite existing scientific judgments or approved Unseen graphs.

## Artifacts

| File | Role |
|------|------|
| `EXCLUSION_LIST.json` | Hard excludes (Unseen / approved graphs / test) + informational construction-exposed |
| `ISOLATION_CHECK.json` | Dual video_id + qa_uid leakage result |
| `SELECTION.json` | Why each pack was chosen |
| `CATALOG.json` | Workbench catalog |
| `JUDGMENTS_BLANK.json` | Blank human form (round-trip preserve unknown fields) |
| `MANIFEST.json` | Clip/pack SHA256 |
| `review_packs/*.json` | Per-video review pack |
| `media/SP00x/*.mp4` | Extracted A/B clips |

Rebuild: `python3 eng/build_seen_pilot_run_001.py`
