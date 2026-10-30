# TRACK A — Gold-conditioned link-score leakage fix

Date: 2026-10-30  
Responds to: `CHATGPT_AUDIT_66B01DB_AND_NEXT_DUAL_TRACK_2026-10-30.md`  
`ok_for_expensive_rsi=false`  
Experiment label: **`binding_policy_evolution_only`** (not autonomous DAG discovery)

## Fixes

| Issue | Change |
|---|---|
| Soft score `+0.5 if correct` from `gold_matches` | Removed. Agent-visible scores = cue-overlap / Jaccard + cue-hash jitter only (`observations_v2._cue_overlap_score`). |
| `person_in_A_{oid[-1]}` / `person_in_B_{oid[-1]}` shared suffix | Replaced with independent nick vocabularies (`cedar`… vs `harbor`…). |
| `bridge_ok` overclaimed pairing | Renamed metric to `local_ids_disjoint`; added `pair_accuracy_top1`, `topk_pair_recall`, `pair_correct_at_bind`, `pair_score_gap`. |
| Forced schema / evolver branding | Results explicitly labeled `binding_policy_evolution_only`; `oracle_program_upper` remains diagnostic. |

## Invariance tests (`test_cross_scene_binding.py`)

1. Gold-label permutation with frozen observations → agent link signature unchanged.
2. Independent A/B local-ID rename → relative scores + semantic outcome preserved.
3. No `is_gold` / `gold_matches` in agent hypothesis payload.
4. No shared oracle name suffix in surfaces.
5. Lookalike hard-negatives expose pair metrics separately from answer accuracy.
6. Dual vs B-only necessity controls retained.

## Fair ablation (15 seeds) — `scene_local_binding_fair_ablation.json`

| Arm | Acc | Pair top1 | Pair@bind | Dual sem | Shortcut B-detect |
|---|---:|---:|---:|---:|---:|
| Fixed | 0.000 | 0.875 | 0.000 | 0.000 | 1.000 |
| Fixed rebind | **0.500** | 0.875 | 0.500 | **1.000** | 1.000 |
| Random | 0.000 | 0.875 | 0.000 | 0.000 | 1.000 |
| Vanilla | 0.000 | 0.875 | 0.000 | 0.000 | 1.000 |
| TECE | **0.000** | 0.875 | 0.000 | 0.000 | 1.000 |
| Oracle-program upper | 1.000 | 0.875 | 1.000 | 1.000 | 1.000 |

### Interpretation
- After removing gold score boost, cue-only pairing still yields mean **pair_accuracy_top1 ≈ 0.875**, but target-query transfer without gold bind is hard.
- **TECE ≤ fixed_rebind** (TECE 0.000 vs fixed_rebind 0.500). **Negative result accepted**; not tuned away.
- `local_ids_disjoint=1.0` everywhere; this is **not** pair accuracy.
- Oracle upper bound still solves with injected gold match (diagnostic only).

## Not claimed
No real-video RSI; no expensive models; no new method brand; no autonomous reverse/AV DAG discovery.
