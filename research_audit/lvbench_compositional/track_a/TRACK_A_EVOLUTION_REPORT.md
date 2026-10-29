# TRACK A — Typed Evidence Contract Evolution (TECE) Report

Date: 2026-10-29  
Branch: `research/lvbench-comp-video-grounded-evidence`  
Expensive RSI: **not run** (`ok_for_expensive_rsi=false`)

## 1. Audit of prior prototype (pre-fix)

Prior 7/7 unit tests mainly proved interface plumbing. Gaps:

| Issue | Finding |
|---|---|
| `verify_answer` | Could treat dual timestamps / `single_clip_sufficient` as composition success |
| Evidence binding | No executable A → binding → B → answer dependency check |
| Recovery | Tendency toward same-op retry without strategy choice or evidence delta |
| Evolver | Mutation acceptance only; no closed evaluate→select→update loop on Seen leave-out |
| Hardcoding | Risk of flag-driven shortcuts rather than evidence-structure decisions |

## 2. Fixes shipped this round

Code under `tools/lvbench_comp/typed_evidence_contract/`:

- `evidence_graph.py` — `EvidenceDependencyGraph` grants `STRONG_COMPOSITION` only when dual-interval evidence + unique binding + bound entity present on both sides + B supports answer. Forged / cross-entity / unsupported / single-interval → denied or control-only.
- `executor.py` — `_verify_answer` uses the graph (flags ignored for credit). `_maybe_recover` chooses different ops (relocate / rebind / investigate), blocks identical cue retries, rebinds entity from located evidence, logs budget and evidence deltas.
- `evolution_loop.py` — closed loop: Initial Harness → mutate (allowed keys only) → evaluate on Seen → select → update; Unseen held out of evolution; freeze video-model weights by construction (sim world only).
- Expanded counterfactuals + 14 TECE unit tests + isolation checks.

## 3. Synthetic ablation (mechanism check only)

Consistent budget/search settings. Seed=11. Results in `tece_evolver_ablation.json`.

| Arm | Seen acc | Unseen held-out acc | Strategy changed | Winning recovery |
|---|---:|---:|---|---|
| Fixed Harness | 0.67 | 0.00 | no | none |
| Random Mutation | 0.67 | 0.00 | no | none |
| Vanilla Evolver (budget-only) | 0.67 | 0.00 | no | none |
| TECE Evolver | **1.00** | **1.00** | **yes** | `rebind_from_a` |

Interpretation:

- Ambiguous referring expressions fail under Fixed/Vanilla because recovery never evolves.
- TECE discovers a non-trivial recovery/disambiguation policy on Seen and the same policy transfers to a held-out signature (`identify_person + describe_action`) in the **synthetic** world.
- This is **not** a claim of real-video RSI compositional generalization.

## 4. Counterfactual anti-examples

All asserted true in `tece_counterfactual_results.json`:

1. Forged B evidence → `DENIED_FORGED_EVIDENCE`
2. Cross-entity A/B → `DENIED_CROSS_ENTITY_INTERVALS`
3. Unsupported answer → `DENIED_ANSWER_UNSUPPORTED`
4. Single-interval support → `CONTROL_ONLY_SINGLE_INTERVAL` (never strong)
5. Subject swap changes bound entity and answer
6. Multi-candidate reference → `AMBIGUOUS_REFERENCE` + recovery investigation

## 5. Isolation

`tece_isolation_check.json`: schema leave-out OK; no H_S1 final judge; no Track B sealed access; Initial Harness declared.

## 6. Still missing for a real Video Agent RSI claim

- Human-verified dual-interval tickets on real LVBench clips (≥6 Unseen compositions / ≥3 videos)
- Declared Initial Harness wired to frozen real video tools (not H_S1 as final)
- Fair-budget runners: no-harness / fixed planner / vanilla RSI / TECE-RSI on real media
- Cost/latency accounting against paid video models (still blocked)
- No Unseen-driven hyperparameter feedback

## Status

**Runnable TECE mechanism prototype with evidence contracts, recovery, and evolver loop on synthetic Seen/Unseen. Not ready for expensive RSI or paper-grade video claims.**
