# 17 — MLVU GT validation, MaaS billing fix, Smoke prep (zero paid API)

Date: 2026-10-23  
Branch: `research/cvpr2027-audit`  
Base reviewed: `aa1b2e1`  
**No paid API this round. Waiting for explicit Smoke approval.**

---

## Final GO / NO-GO

| Item | Status |
|---|---|
| GT 502/502 match → local A–F labels | **GO** |
| MaaS DeepSeek/Qwen unit rates verified from Excel | **GO** |
| R3 Gate cost recalc (no-cache) matches researcher table | **GO** |
| Per-model billing runner + offline tests | **GO** (16 tests) |
| Smoke n=10 items / harness pins / shared config | **GO** |
| Provider account hard spend limit configured | **UNKNOWN** (not modified) |
| **Start paid paired Smoke now?** | **GO pending researcher approval** |

Engineering + billing ready. Do **not** retune harnesses or Primary200 from Smoke outcomes.

---

## 1. Ground Truth

| Field | Value |
|---|---|
| Path | `/home/descfly/lpy/dataset/MLVU_Test/test-ground-truth/test_mcq_gt.json` |
| SHA256 | `569ee2a8e45329e6eef83a4c81072ce646cb99718f74be1f3603d267d3c22bdd` |
| Schema | `list[object]` with `question_id`, `candidates`, `answer`, … |
| Match | **502/502** IDs; candidates identical to `test_multi_choice_tasks.json` |
| Answer types | 442× string (exact candidate text); 60× int (`count` only) |
| Int index base | **1-based** (values ∈ {1..6}, includes **6**, never **0**). 0-based would fail 10 rows. Ambiguous 1..5-only sets are **refused** by validator. |
| Labels | gitignored `research_audit/mlvu_test_prep/labels.local.jsonl` (SHA256 `d880db71…`) |
| Safe report | `gt_match_report.safe.json` (no answers) |

Offline score tests: `test_score_labels_offline.py` — perfect 502 → 100%; smoke flip → 90%.  
Answers are **not** in Solver inputs, harnesses, or git.

---

## 2. MaaS rates (Excel「常规模型」)

Source file (local upload, **not committed**): `MaaS平台模型列表及报价.xlsx`  
`effective_config.json` models unchanged: `DeepSeek-V4-Pro-0813`, `Qwen3.6-Plus`.

| Model | 常规输入 | 输出 | 缓存命中输入 |
|---|---:|---:|---:|
| DeepSeek-V4-Pro-0813 | **¥9** | **¥27** | **¥0.30** |
| Qwen3.6-Plus | **¥4** | **¥24** | **¥0.40** |

Units: CNY / 百万 tokens. Safe copy: `mlvu_test_prep/maas_rates.safe.json`.

---

## 3. Gate R3 cost recalc (independent)

From `round_003/private_gate/{parent,candidate}/results.json` **meter_events only** (matches aggregate `usage` token totals; no double count).

| Scale (paired Initial+H_S1) | No-cache (常规输入) | With logged cache hits |
|---:|---:|---:|
| 10 | **¥8.31** | ¥5.07 |
| 50 | **¥41.57** | ¥25.36 |
| 200 | **¥166.28** | ¥101.44 |
| 502 | **¥417.37** | ¥254.61 |

Researcher no-cache table: **exact match**.  
Cache discount applied **only** where `prompt_tokens_details.cached_tokens` logged (DeepSeek had hits; Qwen cached=0 in R3).

**n=10 call estimate (paired):** ≈ **124.4** DeepSeek + **87.1** Qwen calls.

Undercount risks: Qwen R3 had 10/13 non-ok events with **empty usage** (parent/cand) — those calls not in token/CNY sums.  
Multimodal image billing vs text tokens: **UNKNOWN** from logs (cannot separate); treat as extra cost uncertainty.  
MLVU vs LVBench mix may shift spend.

Artifact: `mlvu_test_prep/gate_r3_cost_recalc.safe.json`.

---

## 4. Runner billing fix

New: `batch_billing.py` + updated `run_batch_checkpoint.py`.

- Per-role prompt/completion/cached + CNY  
- Prefer `meter_events`; **never** add aggregate `usage` on top  
- Aggregate-only fallback bills at **max** role rates + `undercount_risk`  
- Missing usage / non-ok flagged  
- Resume credits prior per-model spend into fuse  
- Fuse = local estimate only — **≠ provider hard limit**

Offline: `PYTHONPATH=. python3 -m unittest test_run_batch_checkpoint test_score_labels_offline` → **16 OK**.

Breaker guarantee: new submits stop when `spent+reserved` would exceed caps; in-flight ≤ `concurrency × reserve_*` overshoot. Single item can still exceed one `reserve_cny` if actual > reserve.

Provider account caps: **not inspected / not changed**. If MaaS console offers project budget alerts, set them manually outside this repo.

---

## 5. Smoke prep (n=10 paired)

| Asset | Value |
|---|---|
| IDs | frozen `sample_ids_n10.json` |
| Items | `smoke_n10_items.jsonl` (SHA256 `960f4bd9…`); videos under `…/video/` all present |
| Config | `evolution/run-seed42/effective_config.json` (same models/budgets/API env for both arms) |
| Initial SHA | `0805cf0eff40fe55712124f0cc70e228e7e3205e362cca37dc79a9d977744fe3` |
| H_S1 SHA | `6733c4806ba3a352e15e866451292a03144c862c53c65e1691d42a718525518f` |

### Metrics to record after run

Accuracy, Fix, Harm, Net (Initial vs H_S1 item flips), Qwen frames, DeepSeek/Qwen calls, tokens, estimated CNY (`batch_summary.json`), error rate.  
Smoke validates engineering/billing — **do not** change harness or Primary200 from results.

### Recommended budget caps (planning)

| | Estimate | Recommended fuse |
|---|---:|---:|
| One arm (no-cache scale) | ≈ ¥4.2 | `--max-estimated-cny 12` |
| Paired | ≈ ¥8.31 | stop if either arm trips; optional project cap **¥20** |
| Reserve / item | — | `--reserve-cny 1.0 --reserve-calls 20` |
| Conservative | use `--no-cache-rates` | ignores cache discounts |

### Commands (do **not** run until approved)

```bash
cd /home/descfly/lpy/Video-RSI
export PYTHONPATH=.
CFG=evolution/run-seed42/effective_config.json
ITEMS=research_audit/mlvu_test_prep/smoke_n10_items.jsonl

# Arm A — Initial
python3 run_batch_checkpoint.py \
  --config "$CFG" --candidate evolution/run-seed42/versions/initial_harness \
  --items "$ITEMS" --output-dir outputs/mlvu_smoke_n10_initial \
  --allow-provider-calls --no-cache-rates \
  --max-estimated-cny 12 --reserve-cny 1.0 --reserve-calls 20

# Arm B — H_S1 (same items/config)
python3 run_batch_checkpoint.py \
  --config "$CFG" --candidate evolution/run-seed42/versions/H_S1 \
  --items "$ITEMS" --output-dir outputs/mlvu_smoke_n10_hs1 \
  --allow-provider-calls --no-cache-rates \
  --max-estimated-cny 12 --reserve-cny 1.0 --reserve-calls 20

# Score (labels stay local / gitignored)
python3 score.py --items "$ITEMS" \
  --predictions outputs/mlvu_smoke_n10_initial/results.json \
  --labels research_audit/mlvu_test_prep/labels.local.jsonl \
  --output outputs/mlvu_smoke_n10_initial/score.json
python3 score.py --items "$ITEMS" \
  --predictions outputs/mlvu_smoke_n10_hs1/results.json \
  --labels research_audit/mlvu_test_prep/labels.local.jsonl \
  --output outputs/mlvu_smoke_n10_hs1/score.json
```

Resume: re-run the same command (fingerprint-checked).

---

## 6. Residual risks

1. Estimate fuse ≠ invoice / account hard stop.  
2. Missing usage & retries undercount CNY.  
3. Vision token surcharge unknown.  
4. MLVU duration/tool mix ≠ LVBench Gate.  
5. Concurrency overshoot up to `4 × reserve_cny` with current config concurrency=4.

---

## Git hygiene

Committed: code, safe stats/reports, smoke items (answer-free).  
**Not** committed: `labels.local.jsonl`, `test_mcq_gt.json`, videos, API keys, MaaS xlsx.
