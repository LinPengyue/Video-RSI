# 14 — MLVU six-option compatibility & paired cost estimate (zero-API)

Date: 2026-10-22  
**No paid API. No video archive validation. No harness edits.**

---

## 1. Converter / 502×6-option support

| Check | Result |
|---|---|
| Source MC rows | 502 (`test_multi_choice_tasks.json`) |
| Converted items | 502 (`mlvu_test_prep/mlvu_test_mc_items.jsonl`) |
| Candidates per item | **6/6** for all 502 |
| `public_item` → A–F | **VERIFIED** (values match source `candidates` order) |
| `load_items(..., check_media=False)` | OK |
| `score.py` schema (fake labels, discarded) | Completes on 502 IDs |

**VERIFIED:** conversion supports all 502 six-option MCQs for `run_batch` / `score`.

---

## 2. Initial Harness & H_S1 six-option execution logic

| Component | Initial | H_S1 | Six-option behavior |
|---|---|---|---|
| `answers.py` | identical | identical | Answer must be a key in `item["options"]`; A–F accepted; G rejected |
| `agent.py` | identical | identical | Lists available option letters dynamically |
| `prompt.md` | base | +reuse note | Says “option letter present in this question’s options” — not hard-coded to 4 |
| `tools.py` | base | −transcript + visual cache | Qwen prompt includes full `options` dict |

LVBench Gate was **4-option**; MLVU-Test is **6-option**. Code path is option-set agnostic (`common.py` allows 2..26).

**VERIFIED:** both frozen harnesses are logically compatible with six options without modification.  
**UNKNOWN until paid smoke:** whether models behave worse with 6 choices (science, not ABI).

---

## 3. Token usage from LVBench Gate (ACTUAL)

Source: `evolution/run-seed42/rounds/round_003/private_gate/{parent,candidate}/results.json`  
Tokens from `meter_events` provider usage (sums match `usage.input_tokens/output_tokens`).

### Round 3 parent = `initial_harness` (n=72)

| Role | Calls | Prompt tok | Completion tok | Calls/Q | Prompt/Q | Completion/Q |
|---|---:|---:|---:|---:|---:|---:|
| DeepSeek | 453 | 1,877,157 | 16,640 | 6.292 | 26,071.6 | 231.1 |
| Qwen | 299 | 1,522,491 | 195,494 | 4.153 | 21,145.7 | 2,715.2 |
| **Total** | | **3,399,648** | **212,134** | | | |

### Round 3 candidate = `H_S1` (n=72)

| Role | Calls | Prompt tok | Completion tok | Calls/Q | Prompt/Q | Completion/Q |
|---|---:|---:|---:|---:|---:|---:|
| DeepSeek | 443 | 2,157,831 | 21,693 | 6.153 | 29,969.9 | 301.3 |
| Qwen | 328 | 1,661,764 | 211,782 | 4.556 | 23,080.1 | 2,941.4 |
| **Total** | | **3,819,595** | **233,475** | | | |

Qwen had 10–13 non-ok meter events with empty usage on R3; those calls count in `calls` but not in token sums.

---

## 4. Paired cost ESTIMATE (local rate card — not invoice)

Local Autoresearch ceiling card (`RATE_IN=2.0`, `RATE_OUT=8.0` CNY / 1M tok; disclaimer: ≠ platform billing):

| Arm | Est. ¥ / question |
|---|---:|
| Initial (from R3 parent) | ≈ **0.118** |
| H_S1 (from R3 cand) | ≈ **0.132** |
| **Paired (both arms)** | ≈ **0.250** |

| Paired n | Est. CNY (2/8 card) | Est. DeepSeek calls | Est. Qwen calls | Est. tokens in / out |
|---:|---:|---:|---:|---:|
| 10 | ≈ **¥2.5** | ≈124 | ≈87 | ≈1.00M / 0.06M |
| 50 | ≈ **¥12.5** | ≈622 | ≈435 | ≈5.01M / 0.31M |
| 200 | ≈ **¥50.0** | ≈2489 | ≈1742 | ≈20.1M / 1.24M |

### Cannot estimate / UNKNOWN

1. **Official invoice unit prices** for `DeepSeek-V4-Pro-0813` and `Qwen3.6-Plus` (vision) on your provider.  
2. Extra **frame / multimodal surcharges** not captured as chat tokens.  
3. **MLVU vs LVBench** tool mix and duration effects (MLVU mean duration lower; max higher).  
4. Whether H_S1’s cache/transcript removal reduces or increases spend on MLVU (R3 Gate had H_S1 slightly **higher** tokens).

Treat ¥ figures as **planning ceilings from a local card**, not a quote.

---

## 5. Fair paired test without modifying frozen harnesses

**Yes.** Existing CLI already supports it:

1. Freeze config (models/budgets/concurrency) identical for both arms.  
2. Same answer-free items JSONL.  
3. `run_batch.py --candidate evolution/run-seed42/versions/initial_harness --output-dir outputs/mlvu_e0cd_initial_<split>`  
4. `run_batch.py --candidate evolution/run-seed42/versions/H_S1 --output-dir outputs/mlvu_e0cd_hs1_<split>`  
5. Score both with the **same** gitignored `labels.local.jsonl` when GT is ready.

No harness file changes required for six-option ABI fairness.

---

## 6. Minimal change proposals (do **not** implement now)

| Need | Minimal proposal |
|---|---|
| Stratified 10/50/200 ID lists | Small offline sampler writing `sample_ids_n{K}.json` (no API) |
| Convenience paired driver | Thin shell/Python wrapper calling `run_batch` twice + asserting identical items SHA |
| Live cost stop | Optional post-item meter aggregation + hard CNY/call abort (outside harness) |
| Harness edits for 6-opt | **Not needed** |

---

## 7–8. Deferred (per instructions)

- Video extract / 349-file integrity / decode: **after upload completes**.  
- GT 502 mapping: **after** authorized `test_mcq_gt.json` is local.

---

## Formal-test readiness (now)

| Gate | Status |
|---|---|
| 502×6-opt conversion | **Ready** |
| Harness six-option ABI | **Ready** |
| Fair paired protocol (no harness edit) | **Ready** |
| Cost planning numbers | **Ready (estimate)** |
| Videos | **Blocked** |
| Local GT + labels | **Blocked** |
| Researcher spend approval | **Pending** |

**Overall: NOT ready to launch paid eval.** Prep for conversion/harness/cost is sufficient to proceed once data+approval land.
