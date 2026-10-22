# 10 — MLVU-Test upload integrity & compatibility (zero-API)

Date: 2026-10-22 (updated evening: GT status correction)  
Branch: `research/cvpr2027-audit`  
Upload root: `/home/descfly/lpy/dataset/MLVU_Test`  
**No paid API. No formal Solver run. No harness edits.**

Companion: `research_audit/mlvu_test_prep_stats.safe.json`  
Conversion: `research_audit/mlvu_test_prep/`

---

## 1. Split identity: Test vs Dev

| Evidence | Observation |
|---|---|
| Path / HF naming | Directory `MLVU_Test`; README links `MLVU/MLVU_Test` |
| MC option count | **502/502** questions have **exactly 6** candidates |
| New task types | `sportsQA` (36), `tutorialQA` (43) present (Test additions) |
| Dev contrast | Dev is separate HF `MLVU/MVLU`; not this tree |

**VERIFIED:** annotations match **MLVU-Test**, not Dev.

### Ground truth: official vs local (correction)

| Layer | Status |
|---|---|
| **Official upstream** | Test MCQ GT **published** (researcher: 2025-03-18). File: `test-ground-truth/test_mcq_gt.json` on `MLVU/MLVU_Test` |
| **Local disk** | `test-ground-truth/` still **empty** as of this update |
| **Fetch from this host** | Failed: HF timeout / **401** without token; mirror **403**. No bypass attempted |
| Bundled README line “GT remain undisclosed” | Historical README text; **do not** treat as current upstream policy |

**Prior wording error:** earlier prep equated empty local folder + old README with “officially still secret.” Correct split: **officially released; locally not yet obtained.**

---

## 2. File integrity (annotations)

| File | Size | SHA256 |
|---|---:|---|
| `test_multi_choice_tasks.json` | 252403 | `fc042268e17fae2313698cb7dd180a3c191949a9a6e1a3a6478861b6e6c93b01` |
| `MLVU_Test/test_question.json` | 252403 | **identical** to multi-choice file |
| `test_generation_tasks.json` | 20059 | `02e79cfa33f40e5419d8164543891859ccc481e24c0f8bd30803326674f32824` |
| `README.md` | 13450 | `a8bbbb77df3b007c62aef363e3485f5dc0c93be01f9bcf7d1187bc9e9f4432ee` |
| `test_mcq_gt.json` (local) | — | **ABSENT** → match rate **N/A** |

MC: **502** unique `question_id`s; generation: **86** (excluded from round-1).  
Unique videos referenced by MC+gen annotations: **396** (MC alone **349**).

Label builder (runs when GT arrives; answers gitignored):  
`research_audit/mlvu_test_prep/validate_and_build_labels.py`

### Videos

| Check | Status (2026-10-22 ~19:58 +08) |
|---|---|
| `*.mp4` present | **0** |
| Archive | Partial `MLVU_Test/.test_video.tar.gz.vtOWhI` ≈ **32 GB**, still growing under **rsync** |
| Extract / decode | **Not started** (no complete archive) |
| Full archive SHA256 / video count | **UNKNOWN** |

**VERIFIED incomplete.** Path/decode checks deferred until rsync finishes.

---

## 3. Overlap with LVBench Train/Gate

| Comparison | Result |
|---|---|
| Exact `video` stem ∩ LVBench meta `key` (103) | **0** |
| Exact stem ∩ train (85) / gate (18) | **0 / 0** |
| Normalized-name overlap | **0** |
| YouTube-like 11-char ID overlap | **0** |

**VERIFIED:** no **filename / ID** collision with local LVBench splits → supports **cross-dataset** labeling.

**Caveat (required):** filename non-overlap **does not** prove content-level uniqueness (shared source footage, re-encodes, clips). Perceptual/content duplicate checks remain **UNKNOWN** without decoded-frame audit (not run).

---

## 4. Compatibility with `run_batch.py` / `score.py`

| Requirement | Support |
|---|---|
| Public fields only in items | `run_batch.load_items` rejects non-public keys |
| Six options → A–F | `public_item` list→letters, 2..26 options |
| Labels separate | `score.py --labels`; answers only in gitignored `labels.local.jsonl` after GT arrives |
| Open generation | Excluded from round-1 |

Converted answer-free manifest: `mlvu_test_prep/mlvu_test_mc_items.jsonl` (502 rows).  
Expected video root: `/home/descfly/lpy/dataset/MLVU_Test/MLVU_Test/videos/` — **502/502 missing** until extract.

---

## 5. Ground-truth isolation

| Rule | Status |
|---|---|
| Items JSONL has no `answer` | **VERIFIED** |
| GT/labels gitignored | `.gitignore` updated |
| Solver never receives labels file | Architecture of `run_batch` vs `score.py` |
| Local GT obtained | **NO** |

---

## 6. Frozen harness & hash discrepancy

Unchanged: freeze tree `5fc0db9a…` = sorted `name hash` lines **without** trailing newline; E0 `0805cf0e…` = **with** trailing newline. Nine files byte-identical to baseline `5ad0144…`. `H_S1` still differs only `prompt.md` / `tools.py`. See `harness_pins.json`.

---

## 7. Zero-API preflight

| Check | Result |
|---|---|
| Annotation parse / 6-opt map | OK |
| Video files | **FAIL** (upload incomplete) |
| Official GT on disk + 502 match A–F | **FAIL** (not fetched) |
| OCR models | OK |
| Paid eval | **NO-GO** |

---

## 8. Commit hygiene

Committed: corrected reports, safe stats, answer-free items, validator script, policy.  
**Not** committed: videos, partial tar, GT JSON, labels, tokens, `config.local.json`.
