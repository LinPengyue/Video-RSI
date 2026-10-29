# TRACK A — Cross-scene binding audit (no oracle ID bridge)

Date: 2026-10-30  
Responds to: `CHATGPT_AUDIT_DD2AFDF_AND_NEXT_DUAL_TRACK_2026-10-29.md`  
`ok_for_expensive_rsi=false`

## Fixes

| Issue | Change |
|---|---|
| Shared `track_id` across A/B | `observations_v2.project_scene_local`: **a_*** vs **b_*** disjoint IDs; gold matches scorer-only |
| B-only via global aliases / first-entity fallback | Scene-local entity lists in masks; removed privileged first-entity resolve fallback |
| Forced test schema as “transfer” | Split modes: `oracle_program` (upper bound) vs `program_selection` / evolver policy |
| Necessity undistinguished | ≥2 `dual_necessary` + ≥2 `b_only_shortcut` by generation; agreement metric |

Code: `observations_v2.py`, `binding_executor.py`, `binding_loop.py`.

## Results (15 seeds) — `tece_cross_scene_binding_ablation.json`

| Arm | Test acc | Dual semantic | Necessity | Shortcut B-detect | Gen. agree |
|---|---:|---:|---:|---:|---:|
| Fixed | 0.000 | 0.000 | 0.000 | 1.000 | 0.500 |
| Fixed rebind | **0.500** | **1.000** | 0.500 | 1.000 | **1.000** |
| Random | 0.333 | 0.667 | 0.333 | 1.000 | 0.833 |
| Vanilla | 0.333 | 0.667 | 0.333 | 1.000 | 0.833 |
| TECE | **0.267** | 0.533 | 0.267 | 1.000 | 0.767 |
| Oracle-program upper | 1.000 | 1.000 | 0.500 | 1.000 | 1.000 |

Notes:
- Bridge intersection empty (A/B track IDs disjoint) on all evaluated tasks.
- Shortcut controls: B-only solves; dual-necessary: A-only and B-only fail when protocol works.
- **TECE ≤ fixed_rebind** on this oracle-bridge-free suite — **negative result accepted**, not tuned away.
- `oracle_program_upper` uses gold A↔B match (diagnostic only); not a transfer claim.

## Failure modes

1. Without recovery / low bind threshold, cross-scene match hypotheses often miss.
2. Shortcut tasks: AB pipeline that insists on A-first resolve can fail semantically while B-only correctly answers — necessity flag still detects shortcut.
3. Evolver search does not beat a strong static rebind threshold policy here.

## Not claimed

No real-video RSI; no expensive models; no new method brand.
