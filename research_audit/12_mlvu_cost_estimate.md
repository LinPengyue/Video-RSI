# 12 — MLVU-Test API cost estimate (from LVBench Gate actuals)

Date: 2026-10-22 (unchanged rates; GT status corrected elsewhere)  
**Estimates only.** No MLVU calls were made. Cost figures do not depend on GT availability.

Source actuals: `evolution/run-seed42/rounds/round_00{1,2,3}/gate_aggregate.json` (72 Gate questions each).

---

## Observed LVBench Gate rates (ACTUAL)

| Round | Arm | Qwen calls / Q | Mean Qwen frames / Q |
|---|---|---:|---:|
| 1 | parent (`initial_harness`) | 4.306 | 57.39 |
| 1 | candidate | 3.903 | 55.56 |
| 2 | parent | 4.222 | 55.24 |
| 2 | candidate | 4.556 | 60.33 |
| 3 | parent | 4.153 | 55.39 |
| 3 | candidate | 4.556 | 59.82 |

Conservative planning rates (max of above means):  
**≈4.56 Qwen calls/Q**, **≈60.3 frames/Q** for a single harness pass.

DeepSeek agent calls are **not** broken out as a stable per-question rate in `gate_aggregate` (only Qwen call counts). Treat DeepSeek usage as **UNKNOWN additive** cost; historically on the order of solver steps (≤11/Q) but not quoted as currency here.

---

## Duration caveat

| Corpus | Mean duration (s) |
|---|---:|
| LVBench Gate items | ≈3939 |
| MLVU-Test MC | ≈934 |

MLVU mean duration is **lower**, but the **max** MLVU clip (≈8206 s) exceeds many LVBench items.  
Therefore LVBench Gate rates are a **rough prior**, not a guaranteed bound. Mark all projections **ESTIMATE**.

---

## Paired eval projections (Control + Treatment = ×2 harnesses)

Using 4.56 Qwen calls/Q and 60.3 frames/Q per harness:

| MC sample size n | Qwen calls (one harness) | Qwen calls (paired ×2) | Frames (paired ×2) |
|---:|---:|---:|---:|
| 50 | 228 | 456 | ≈6.0e3 |
| 100 | 456 | 912 | ≈1.2e4 |
| 200 | 912 | 1824 | ≈2.4e4 |
| 502 (full MC) | 2289 | 4578 | ≈6.1e4 |

Formula: `calls ≈ 4.56 * n * n_harnesses`.

---

## Currency / token cost

**UNKNOWN in CNY/USD** without a locked provider rate card and measured DeepSeek+Qwen tokens on MLVU.  
Do **not** invent a dollar total.

Operational controls (pre-register before any paid run):

1. Hard stop if provider errors exceed 5% of items.  
2. Hard stop if mean Qwen frames/Q exceed **2×** the LVBench Gate parent mean (≈110) without researcher override.  
3. Soft budget: researcher sets a wallet cap before launch; abort when estimated spend hits the cap.  
4. First paid slice must be a **smoke** (e.g. n≤10) before scaling.

---

## Distinction

| Kind | Example |
|---|---|
| ACTUAL | R3 parent 299 Qwen calls on 72 Q |
| ESTIMATE | 502×2×4.56 ≈ 4578 Qwen calls |
| UNKNOWN | Dollar cost; DeepSeek tokens on MLVU; effect of longer/shorter videos |
