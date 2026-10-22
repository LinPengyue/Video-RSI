# 10 — MLVU-Test upload integrity & compatibility (zero-API)

Date: 2026-10-22  
Branch: `research/cvpr2027-audit`  
Upload root: `/home/descfly/lpy/dataset/MLVU_Test`  
**No paid API. No formal Solver run.**

Companion stats: `research_audit/mlvu_test_prep_stats.safe.json`  
Conversion: `research_audit/mlvu_test_prep/`

---

## 1. Split identity: Test vs Dev

| Evidence | Observation |
|---|---|
| Path / HF naming | Directory `MLVU_Test`; README links `MLVU/MLVU_Test` |
| README news | “MLVU-Test set… expanded … options … to **six**”; GT “remain undisclosed” |
| MC option count | **502/502** questions have **exactly 6** candidates |
| New task types | `sportsQA` (36), `tutorialQA` (43) present (Test additions) |
| `test-ground-truth/` | **Empty** (matches undisclosed GT) |
| Dev contrast | Dev is separate HF `MLVU/MVLU`; not this tree |

**VERIFIED:** annotations match **MLVU-Test**, not Dev.

---

## 2. File integrity (annotations)

| File | Size | SHA256 |
|---|---:|---|
| `test_multi_choice_tasks.json` | 252403 | `fc042268e17fae2313698cb7dd180a3c191949a9a6e1a3a6478861b6e6c93b01` |
| `MLVU_Test/test_question.json` | 252403 | **identical** to multi-choice file |
| `test_generation_tasks.json` | 20059 | `02e79cfa33f40e5419d8164543891859ccc481e24c0f8bd30803326674f32824` |
| `README.md` | 13450 | `a8bbbb77df3b007c62aef363e3485f5dc0c93be01f9bcf7d1187bc9e9f4432ee` |

MC: **502** unique `question_id`s; generation: **86** (excluded from round-1).  
Unique videos referenced by MC+gen annotations: **396** (MC alone **349**).

### Videos

| Check | Status |
|---|---|
| `*.mp4` present | **0** |
| Archive | Partial rsync file `MLVU_Test/.test_video.tar.gz.vtOWhI` (growing; ~3.2GB+ at prep time) |
| rsync processes | **Observed** writing into `MLVU_Test/` |

**VERIFIED incomplete:** video payload still uploading. Full archive SHA256 and per-video hashes are **UNKNOWN** until transfer finishes and extract completes.

### Answers / GT

`test-ground-truth/` has **no files**. Offline `score.py` Accuracy is **blocked** until an authorized separate labels JSONL exists. Do not invent labels.

---

## 3. Overlap with LVBench Train/Gate

| Comparison | Result |
|---|---|
| Exact `video` stem ∩ LVBench meta `key` (103) | **0** |
| Exact stem ∩ train (85) / gate (18) | **0 / 0** |
| Normalized-name overlap | **0** |
| YouTube-like 11-char ID overlap | **0** (MLVU naming is mostly `test_*`; LVBench is YouTube IDs) |

**VERIFIED:** no ID-level video collision with local LVBench splits.  
**UNKNOWN:** perceptual/content duplicate without decoded frames (not attempted).

This supports treating MLVU-Test as **cross-dataset**, not LVBench held-out.

---

## 4. Compatibility with `run_batch.py` / `score.py`

| Requirement | Support |
|---|---|
| Public fields only in items | `run_batch.load_items` rejects non-public keys (`run_batch.py` L27–29) |
| Options as list → A.. | `public_item` maps list→`chr(65+i)` and allows 2..26 options (`common.py` L34–37) |
| Six options | **VERIFIED** maps to A–F |
| Labels separate | `score.py` takes `--labels` JSONL with `sample_id`+`answer`; answers must be option keys |
| Open generation (SSC/VS) | **Out of scope** for round-1; 86 gen tasks excluded |

Converted answer-free manifest:  
`research_audit/mlvu_test_prep/mlvu_test_mc_items.jsonl` (502 rows; `load_items(..., check_media=False)` OK).  
Expected video root after extract:  
`/home/descfly/lpy/dataset/MLVU_Test/MLVU_Test/videos/<file.mp4>`  
Currently **502/502 paths missing** (videos not extracted).

---

## 5. Ground-truth isolation

Policy file: `research_audit/mlvu_test_prep/LABELS_POLICY.md`.

| Rule | Status |
|---|---|
| Items JSONL contains no `answer` | **VERIFIED** |
| Solver/Harness never receive labels file | Enforced by separate `score.py` entrypoint |
| Empty GT dir on disk | **VERIFIED** |

---

## 6. Frozen harness & hash discrepancy

| Artifact | tree_sha256 |
|---|---|
| `BASELINE_FREEZE.md` | `5fc0db9a33358a1de7bdd3fedccd9a56261c099ae6005c1b38fd2adb6b6fbea9` |
| E0 `06` / safe JSON (newline variant) | `0805cf0eff40fe55712124f0cc70e228e7e3205e362cca37dc79a9d977744fe3` |
| Recompute **without** trailing `\n` | **= freeze** |
| Recompute **with** trailing `\n` | **= E0** |

**Cause (VERIFIED):** same nine file SHA256 lines; freeze omitted the final newline in the tree digest; E0 included it. **Not** harness drift. All nine files remain byte-identical to `HEAD:solver_full_workspace/*` at baseline commit `5ad0144…`.

`H_S1` differs only in `prompt.md` and `tools.py` (tree with newline `6733c480…`). Pins: `research_audit/mlvu_test_prep/harness_pins.json`.

Models (from `evolution/run-seed42/effective_config.json`, not committed secrets): `DeepSeek-V4-Pro-0813`, `Qwen3.6-Plus`; solver budgets 11/64/256; concurrency 4; OCR root `/home/descfly/lpy/ocr-models` (onnx files present).

---

## 7. Zero-API preflight checklist

| Check | Result |
|---|---|
| Annotation parse | OK |
| Unique sample IDs | OK |
| Six-option mapping | OK |
| `load_items` public validation | OK |
| Video files exist | **FAIL** (upload incomplete) |
| Duration present & finite | OK (MC mean ≈933.6 s; max ≈8205.8 s) |
| OCR model files on disk | OK (det/rec/cls onnx) |
| Labels for scoring | **FAIL / unavailable** |
| Node/DSH needed for Solver-only batch | Not required for `run_batch` Solver path |

**Go/No-Go for paid eval:** **NO-GO** until (a) video archive completes + extracts with checksum, (b) researcher approves cost, (c) scoring path decided (authorized labels **or** online-only).

---

## 8. What was committed vs excluded

Committed: reports, safe stats, answer-free items JSONL, harness pins, labels policy.  
**Not** committed: videos, partial tar, `config.local.json`, API keys, any answers.
