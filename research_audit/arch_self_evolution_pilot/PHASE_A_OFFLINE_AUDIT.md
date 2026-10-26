# Phase A — Offline Audit (0 API)

**Branch:** `research/arch-self-evolution-pilot`  
**Baseline commit:** `fa96c0e` (`research/arch-evolution-min-preflight`)  
**Paid API this phase:** 0  

---

## 1. `decide_go_stop()` fixes (OBSERVED)

| Bug | Fix |
|---|---|
| `or True` short-circuit forced GO whenever complement+diff | Removed; GO requires `strict_support` |
| `vision_retention` true whenever both caption paths fail | Now requires **B-direct correct** on the same `sample_id` |
| Empty loop / ignored AB rows | Uses `ab["per_item"]` lookup |
| Mechanism labels treated as conclusions | Emits `hypothesis_status: HYPOTHESIS_TO_VERIFY` for all three |

Re-evaluated local `infoflow_v1` with fixed logic: still **GO**, with explicit IDs:

- vision_retention: `2886`, `3523`
- answerer_identity: `2984`, `38`, `4799`, `531`

## 2. Counterexample unit tests

Added in `test_ab_infoflow_offline.py` (14 tests, all PASS):

- complement without mechanism link → STOP (`or True` regression)
- both text fail but B wrong → no vision retention → STOP
- B correct + both text fail → vision retention → GO
- answerer letter disagree → GO
- B dominates, a_only=0 → PIVOT
- diag missing → PENDING_DIAG
- oracle router = 12/20

## 3. Oracle Router upper bound (OBSERVED)

On frozen n=20 A/B:

| Policy | Correct / 20 |
|---|---|
| A-reuse | 8 |
| B-direct | 11 |
| **Oracle Router** (A∨B) | **12** |
| Oracle − B | **+1** |

Routing between Caption→DeepSeek and Direct VQA adds only **one** additional correct item beyond always choosing Direct VQA. Ceiling for “learn a router” on this set is thin.

## 4. Mechanism status (reframed)

| Claim | Status |
|---|---|
| Visual information loss in captioning | **HYPOTHESIS_TO_VERIFY** (candidates 2886, 3523) |
| Model division of labor (answerer identity) | **HYPOTHESIS_TO_VERIFY** (candidates include 531) |
| Caption refresh / quality | **HYPOTHESIS_TO_VERIFY** (candidate 3472) |

Not causal conclusions until Phase B stability.

## 5. Private Gate leakage

Frozen exploratory IDs ∩ Gate oracle IDs = **∅**.  
No Gate items used as develop set in A/B/diag.

## Gate to Phase B

Engineering + science checks pass. Proceed to **stability repeats** on `2886`, `3523`, `531`, `3472` without overwriting `runs/infoflow_v1/`.
