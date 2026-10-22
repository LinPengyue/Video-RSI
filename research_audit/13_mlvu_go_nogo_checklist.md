# 13 — MLVU-Test GO/NO-GO checklist

Updated: 2026-10-22 evening (GT official-vs-local correction).

| # | Item | Status now |
|---:|---|---|
| 1 | Annotations present & hashed | **GO** |
| 2 | Confirmed MLVU-Test (6-opt, SQA/TQA) | **GO** |
| 3 | Official Test GT published upstream | **GO** (policy fact) |
| 4 | Local `test_mcq_gt.json` present | **NO-GO** (not downloaded; HF auth/network) |
| 5 | GT matched 502/502 → A–F labels built | **NO-GO** (blocked on #4) |
| 6 | Video archive complete + SHA256 | **NO-GO** (rsync partial ≈32 GB) |
| 7 | Videos extracted; paths resolve; decode smoke | **NO-GO** |
| 8 | Filename/ID overlap vs LVBench | **GO** (0); content overlap **UNKNOWN** |
| 9 | Public items conversion (MC, A–F) | **GO** |
| 10 | Answers isolated (items clean; labels gitignored) | **GO** (policy + ignore rules) |
| 11 | Harness pins unchanged | **GO** |
| 12 | OCR + config dependencies on disk | **GO** (local) |
| 13 | Cost estimate reviewed | **PENDING** |
| 14 | Explicit approval to spend | **PENDING** |

**Overall: NO-GO for paid eval.**

Still missing for formal eval:

1. Authorized local copy of `test_mcq_gt.json` + successful `validate_and_build_labels.py` (match rate 1.0).  
2. Finished video archive, extract, path check, optional decode smoke.  
3. Researcher cost approval.
