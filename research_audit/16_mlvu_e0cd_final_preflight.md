# 16 — MLVU-Test E0-CD final preflight (zero-API)

Date: 2026-10-23  
Branch: `research/cvpr2027-audit`  
**No paid API. No harness / Solver / Gate edits. No answers in git.**

Video root (actual): `/home/descfly/lpy/dataset/MLVU_Test/MLVU_Test/video/`

---

## GO / NO-GO board

| # | Check | Result |
|---:|---|---|
| 1 | 502/502 item `video_path` valid & non-zero | **GO** |
| 2 | 349/349 unique MC videos present & readable | **GO** |
| 3 | Local Ground Truth (`test_mcq_gt.json`) + 502 match | **NO-GO** (file absent) |
| 4 | Smoke n=10 & Primary n=200 frozen (answer-free IDs) | **GO** |
| 5 | Long-batch runner reliability (external checkpoint) | **GO** (offline tests) |
| 6 | Invoice-grade provider rates known | **NO-GO** (local 2/8 planning card only) |
| 6b | Runner call/CNY hard stop enforceable | **GO** (`run_batch_checkpoint.py`) |
| 7 | Apply to start **accuracy-scored** 10-Q Smoke | **NO-GO** (blocked on GT) |
| 7b | Apply to start **engineering** 10-Q Smoke (paths/runner only) | **CONDITIONAL** — needs spend approval; cannot score |

**Overall for formal paired E0-CD: NO-GO.**  
Videos + items + runner are ready. **Local GT and invoice rates are not.**

---

## Task 1 — Video paths & media

| Metric | Value |
|---|---|
| Items path rewrite | `.../videos/` → `.../video/` for **502/502** |
| Items SHA256 | `c94aac4a632e2281e0aa078e4281915ff3727f98af193be7a1e1598ca3df4524` |
| Paths valid non-zero | **502/502** |
| Unique MC videos | **349/349** on disk |
| Disk files | **396** (= MC∪generation annotation union; 0 missing, 0 extras) |
| Zero-byte / &lt;1KB | **0 / 0** |
| ffmpeg header probe (349 MC) | **0 failures** |
| Duration vs annotation (\|Δ\|&gt;1.5s) | **0** |
| Decode smoke (17 short/long × task types, 8 frames) | **17/17 pass** |

Tooling: conda `imageio_ffmpeg` binary (system `ffprobe`/`ffmpeg` not installed).  
Evidence: `research_audit/mlvu_test_prep/media_validation_report.json`  
Script: `research_audit/mlvu_test_prep/finalize_e0cd_preflight.py`

**No missing/corrupt MC videos found. No questions dropped.**

---

## Task 2 — Ground Truth

Searched:

- `/home/descfly/lpy/dataset/MLVU_Test/test-ground-truth/test_mcq_gt.json` — **missing** (dir empty)
- `/home/descfly/lpy/dataset/MLVU_Test/MLVU_Test/test_mcq_gt.json` — missing
- Broader `*gt*` / `*ground*` / `*label*` under dataset root — **no hits**

**Local GT: ABSENT.** Match rate: N/A.  
Did **not** guess answers or call models.  
`validate_and_build_labels.py` remains ready once an authorized `test_mcq_gt.json` is placed locally; labels stay gitignored (`LABELS_POLICY.md`).

---

## Task 3 — Frozen samples (no answers)

| Split | File | Seed | Unique videos | SHA256 of list file |
|---|---|---:|---:|---|
| Smoke | `sample_ids_n10.json` | 20261024 | **10/10** | `fba0328a30a352702524b6ceb95401ee53b006e3b255b5631445c6eac319d014` |
| Primary | `sample_ids_n200.json` | 20261023 | **188/200** (12 Q share a video already used in-primary) | `8d972fbf14cb54d516fe0b1d9855957e6d164980795fced06285753d5b7f2754` |

- Method: stratified by `task_type`, min-1 when n≥#types, largest remainder; prefer unique videos; **smoke sampled first**, primary avoids smoke videos.
- Smoke ∩ Primary **sample_ids**: ∅  
- Smoke ∩ Primary **videos**: ∅  
- Selection is ID/path/task-type only — **not** conditioned on answers or model scores.
- Prior seed-20261022 lists superseded by this video-disjoint freeze (items SHA also changed after path fix).

Smoke IDs: `AC_19, AO_68, AR_29, ER_20, NQA_35, PQA_44, SQA_30, TQA_29, TR_57, TR_6`

---

## Task 4 — Runner safety

| Requirement | `run_batch.py` | `run_batch_checkpoint.py` |
|---|---|---|
| Resume / no re-bill completed | **No** (`exist_ok=False`) | **Yes** (terminal `answered`/`invalid_decision`) |
| Identical samples/config for two harnesses | Manual discipline | Manifest fingerprints (`items_sha256`, `config_fingerprint`, harness tree SHA) |
| Record model / candidate SHA / items SHA / usage | Partial | Manifest + per-item results + `batch_summary.json` |
| External call/CNY hard stop | **No** | **Yes** (`--max-provider-calls`, `--max-estimated-cny`, reserve-before-submit) |
| Concurrent overshoot bound | N/A | ≤ concurrency × reserve |

Offline: `PYTHONPATH=. python3 -m unittest test_run_batch_checkpoint` → **10/10 OK** (no API).  
Harness / Solver / Gate unchanged.

Paired protocol: same frozen items JSONL + same config; two `--candidate` dirs (`initial_harness`, `H_S1`) → two output dirs.

---

## Task 5 — Rates & Smoke application

| Item | Status |
|---|---|
| Local planning card | `RATE_IN=2.0`, `RATE_OUT=8.0` CNY/1M tok (from audit `14_`) |
| Paired Smoke n=10 est. | ≈ **¥2.5** on that card (**not** an invoice) |
| Official DeepSeek-V4-Pro / Qwen3.6-Plus unit prices | **UNKNOWN** |
| Budget enforcement in runner | **Available** via checkpoint CLI |

### Can we apply to start 10-Q Smoke?

| Mode | Decision |
|---|---|
| Engineering smoke (paths, resume, meters; **no accuracy claim**) | **Ask approval** with hard `--max-estimated-cny` / `--max-provider-calls`; expect ≈¥2.5 paired on local card |
| Accuracy / GO-for-E0 smoke | **NO-GO** until local `test_mcq_gt.json` validates 502/502 → `labels.local.jsonl` |

---

## Explicitly not done

- No paid API calls  
- No formal MLVU paired eval  
- No GT download (auth/network not assumed)  
- No tar.gz re-download / checksum requirement  
- No harness edits  
