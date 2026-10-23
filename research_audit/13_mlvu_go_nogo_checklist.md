# 13 — MLVU-Test GO/NO-GO checklist

Updated: 2026-10-23 (final preflight after video extract; see `16_mlvu_e0cd_final_preflight.md`).

| # | Item | Status now |
|---:|---|---|
| 1 | Annotations present & hashed | **GO** |
| 2 | Confirmed MLVU-Test (6-opt, SQA/TQA) | **GO** |
| 3 | Official Test GT published upstream | **GO** (policy fact) |
| 4 | Local `test_mcq_gt.json` present | **NO-GO** (`test-ground-truth/` empty) |
| 5 | GT matched 502/502 → A–F labels built | **NO-GO** (blocked on #4) |
| 6 | Video archive on disk | **GO** (`video/`, ~71 GB, 396 files; tar deleted) |
| 7 | Paths resolve; header+decode smoke | **GO** (502/502 paths; 349/349 MC; 17/17 decode) |
| 8 | Filename/ID overlap vs LVBench | **GO** (0); content overlap **UNKNOWN** |
| 9 | Public items conversion (MC, A–F) | **GO** (paths fixed to `video/`) |
| 10 | Six-option ABI on Initial & H_S1 | **GO** (`14_`) |
| 11 | Answers isolated (items clean; labels gitignored) | **GO** |
| 12 | Harness pins unchanged | **GO** |
| 13 | OCR + config dependencies on disk | **GO** (local) |
| 14 | Token-based paired cost estimate | **GO** (estimate only; `14_`) |
| 15 | Invoice-grade provider rates | **NO-GO** / UNKNOWN |
| 16 | Checkpoint runner + offline resume tests | **GO** (`15_`, `test_run_batch_checkpoint`) |
| 17 | Smoke/Primary IDs frozen (video-disjoint) | **GO** (`sample_ids_n{10,200}.json`) |
| 18 | Cost estimate reviewed / spend approved | **PENDING** |

**Overall: NO-GO for formal / accuracy-scored eval** (GT + invoice rates + spend approval).

Videos + public items + runner are ready. Next blockers:

1. Authorized local `test_mcq_gt.json` → `validate_and_build_labels.py` (match rate 1.0).  
2. Researcher spend approval (planning: paired ≈¥2.5 / ¥50 for n=10/200 on local 2/8 card).  
3. Optional engineering-only Smoke under hard CNY/call caps — still cannot score without GT.
