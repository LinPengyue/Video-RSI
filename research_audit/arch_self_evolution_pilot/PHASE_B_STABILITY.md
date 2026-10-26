# Phase B — Mechanism Stability

**Paid API:** yes (new run dir `runs/stability_v1/`; `infoflow_v1` untouched)  
**Targets:** `2886`, `3523`, `531`, `3472`  
**Design:** rep0 = cached infoflow_v1; +2 paid replicates on frozen frames/caption; +1 fresh caption probe  

---

## Per-sample (OBSERVED)

| ID | B acc/cons | A-strict acc/cons | C acc/cons | Vision loss | Answerer split | Caption refresh |
|---|---|---|---|---|---|---|
| 2886 | 1.0 / yes | 0.0 / yes | 0.0 / yes | **SUPPORTED** | no | weak |
| 3523 | 1.0 / yes | 0.0 / yes | 0.0 / yes | **SUPPORTED** | no | **SUPPORTED** |
| 531 | 1.0 / yes | 0.0 / yes | 1.0 / yes | no | **SUPPORTED** | weak |
| 3472 | 1.0 / yes | 1.0 / yes | 1.0 / yes | no | no | weak |

Estimated new-call cost ≈ **1.19 CNY**.

## Hypothesis verdicts after repeats

| Hypothesis | Verdict |
|---|---|
| Visual information loss | **Replicates** on 2886 & 3523 with full answer consistency |
| Model division of labor | **Replicates** on 531 (DeepSeek vs Qwen-text on frozen caption) |
| Caption refresh | **Weak** — only 3523 shows answer shift; 3472’s earlier “fresh caption recovers DeepSeek” did **not** remain a distinctive instability signal (all paths correct/stable) |

## Gate to Phase C

**PROCEED_PHASE_C** — credible, consistent signals for vision-loss and answerer-identity; not explained by single-shot random flips.

Safe artifact: `out/stability_summary.safe.json`.
