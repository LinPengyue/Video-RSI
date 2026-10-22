# 13 — MLVU-Test GO/NO-GO checklist

| # | Item | Status now |
|---:|---|---|
| 1 | Annotations present & hashed | **GO** |
| 2 | Confirmed MLVU-Test (6-opt, SQA/TQA, empty GT dir) | **GO** |
| 3 | Video archive complete + SHA256 | **NO-GO** (rsync partial) |
| 4 | Videos extracted; paths resolve | **NO-GO** |
| 5 | ID overlap vs LVBench train/gate | **GO** (0 overlap) |
| 6 | Public items conversion (MC, A–F) | **GO** |
| 7 | GT isolated from items | **GO** (no answers in items; GT empty) |
| 8 | Offline labels available for score.py | **NO-GO** / TBD |
| 9 | Harness pins verified | **GO** |
| 10 | OCR + config dependencies on disk | **GO** (local) |
| 11 | Cost estimate reviewed by researcher | **PENDING** |
| 12 | Explicit approval to spend | **PENDING** |

**Overall: NO-GO for paid eval.** Continue waiting on upload completion, then re-hash videos and request approval.
