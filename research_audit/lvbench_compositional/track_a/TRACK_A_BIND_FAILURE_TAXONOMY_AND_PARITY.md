# TRACK A — Bind failure taxonomy & matched-budget parity

Date: 2026-10-30  
Responds to: `CHATGPT_AUDIT_35EBAD3_AND_NEXT_DUAL_TRACK_2026-10-30.md`  
`ok_for_expensive_rsi=false` · label: **`binding_policy_evolution_only`**

Frozen 4-task suite = **negative-control regression only**. Not used to tune TECE for a win.

## 1. Why pair Top-1 ≈ 0.875 but TECE `pair_correct_at_bind` ≈ 0

Two axes (instrumented in `bind_diagnostics.py`):

| Axis | Meaning |
|---|---|
| Hypothesis ranking | `pair_accuracy_top1` / `top1_is_gold` from cue-overlap scores |
| Execution acceptance | threshold + recovery decide whether top-1 is **bound** |

### Reproducible traces (frozen suite)

**A. `ranking_ok_but_threshold_reject`** (TECE-like init: thr=0.45, recovery=`none`, budget=4)

| Task | Top-1 score | Top-1 gold? | Raw pass@0.45? | Bind |
|---|---:|:---:|:---:|---|
| te_dual_a | 0.345 | yes | no | IDENTITY_LOST |
| te_dual_b | 0.389 | yes | no | IDENTITY_LOST |

Ranking is correct; **acceptance fails** because gold pair scores sit below the TECE-like threshold and recovery does not lower it.

**B. Strong fixed-rebind** (thr=0.25, recovery=`rebind_from_a`, budget=6)

| Task | Top-1 score | Bind | Outcome |
|---|---:|---|---|
| te_dual_a / te_dual_b | 0.345 / 0.389 | ok (recovery lowers thr once) | answer ok |
| te_short_* | — | resolve_A_failed | expected for B-only cue on AB path |

**C. `resolve_A_failed`** on shortcut tasks: AB pipeline resolves A with `unique_b_cue` → no A match. Ranking metrics still average over dual tasks → high top-1 coexists with low bind rate on TECE init.

Artifacts: `bind_failure_taxonomy.json`.

## 2. Matched-budget vs strong-policy (do not weaken fixed-rebind)

| Arm | Init | Acc | Pair@bind | Dual sem |
|---|---|---:|---:|---:|
| matched_static | thr=0.25, recovery=none, budget=6 | 0.500 | 0.500 | 1.000 |
| matched_tece_evolve | same init, then evolve 5 gens | 0.500 | 0.500 | 1.000 |
| strong_fixed_rebind_ref | thr=0.25, rebind_from_a, budget=6 | 0.500 | 0.500 | 1.000 |

Under **exact parity**, evolving thresholds/recovery does **not** beat matched static or the strong reference on the frozen suite. Prior “TECE 0 vs fixed-rebind 0.5” was largely an **initialization/threshold confound**, not proof that search is worse than a calibrated static policy once budgets match. Strong fixed-rebind remains a legitimate best-practice baseline (not weakened).

Artifact: `matched_budget_parity.json`.

## 3. Independent scenario suite (not the four held-out strings)

24 freshly generated multi-entity tasks (role-reversal, missing-evidence, dual, B-shortcut); answers outside the frozen set.

| Arm | Acc | Dual acc | Pair@bind | Shortcut B-detect | Missing stays unanswered |
|---|---:|---:|---:|---:|---:|
| strong_fixed_rebind | 0.500 | 0.800 | 0.583 | 1.000 | 1.000 |
| matched_static | 0.208 | 0.333 | 0.250 | 1.000 | 1.000 |
| weak_tece_like_init | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 |

Failure mix on independent duals includes `wrong_pair_accepted`, `ranking_ok_but_threshold_reject`, `ranking_miss_and_reject` — ranking and acceptance both matter once worlds vary.

Artifact: `independent_scenario_eval.json`.

## 4. Design note (not a new brand) — adaptive operation sequencing

Threshold/recovery evolution alone cannot transfer to unseen video compositions. A transferable agent would need **question-conditioned operator sequencing**, e.g.:

1. Parse which evidence groups / modalities the question actually requires.
2. Choose among DAG templates (bind-then-query vs single-side; order A/B; missing-evidence abort).
3. Spend budget on disambiguation only when link entropy is high.
4. Emit calibrated abstention when top-1 score margin is thin.

This remains a design note; `ok_for_expensive_rsi=false`. No RSI run.

## 5. Regression stance
Keep current negative / parity results. Do **not** optimize TECE against the frozen four tasks. Further work = independent graphs + causal diagnostics, not score chasing.
