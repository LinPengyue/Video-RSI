# 13 — MLVU-Test GO/NO-GO checklist

Updated: 2026-10-23 (GT + MaaS billing prep; see `17_mlvu_gt_billing_smoke_prep.md`).

| # | Item | Status now |
|---:|---|---|
| 1 | Annotations present & hashed | **GO** |
| 2 | Confirmed MLVU-Test (6-opt, SQA/TQA) | **GO** |
| 3 | Official Test GT published upstream | **GO** (policy fact) |
| 4 | Local `test_mcq_gt.json` present | **GO** |
| 5 | GT matched 502/502 → A–F labels built | **GO** (gitignored labels; 1-based ints) |
| 6 | Video archive on disk | **GO** (`video/`, ~71 GB, 396 files; tar deleted) |
| 7 | Paths resolve; header+decode smoke | **GO** (502/502 paths; 349/349 MC; 17/17 decode) |
| 8 | Filename/ID overlap vs LVBench | **GO** (0); content overlap **UNKNOWN** |
| 9 | Public items conversion (MC, A–F) | **GO** (paths fixed to `video/`) |
| 10 | Six-option ABI on Initial & H_S1 | **GO** (`14_`) |
| 11 | Answers isolated (items clean; labels gitignored) | **GO** |
| 12 | Harness pins unchanged | **GO** |
| 13 | OCR + config dependencies on disk | **GO** (local) |
| 14 | Token-based paired cost estimate | **GO** (estimate only; `14_`) |
| 15 | MaaS unit rates (DeepSeek 9/27, Qwen 4/24) | **GO** (Excel「常规模型」; see `17_`) |
| 16 | Checkpoint runner + per-model billing tests | **GO** (`batch_billing.py`, 16 offline tests) |
| 17 | Smoke/Primary IDs frozen (video-disjoint) | **GO** (`sample_ids_n{10,200}.json`) |
| 18 | Cost estimate reviewed / spend approved | **PENDING** (paired Smoke ≈¥8.31 no-cache) |

**Overall: GO for paid n=10 paired Smoke pending explicit researcher approval.** Formal Primary200 still needs spend approval at ≈¥166 paired (no-cache planning).
