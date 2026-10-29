# TRACK A — Oracle-free causal audit

Date: 2026-10-29  
Responds to: `CHATGPT_AUDIT_6FE9181_VISUAL_REVIEW_AND_NEXT_DUAL_TRACK.md`  
`ok_for_expensive_rsi=false`

## Fixes

| Defect | Fix |
|---|---|
| A1 Declared schema ≠ runtime | Tasks force `schema.compile_program()`; log `declared_schema_hash`, `compiled_program_hash`, `executed_trace_hash`; `runtime_fidelity_to_schema` |
| A2 Biased A/B masking | `necessity.py` only masks evidence **groups**; no alias/lexicon rewrite |
| A3 Oracle entity_id leak | `observations.py` + `OracleFreeExecutor`: ephemeral `track_id` only; recovery cannot bind oracle ids; leak rate asserted 0 |
| A4 Fair compare | Matched mutation pool; fixed / fixed_rebind / random / vanilla / tece; select on dev; test once |

Code: `observations.py`, `oracle_free_executor.py`, `oracle_free_loop.py`, rewritten `necessity.py`.

## Results (20 seeds, `tece_oracle_free_multiseed.json`)

| Arm | Test semantic mean | Strict | Necessity | Oracle leak | Schema fidelity |
|---|---:|---:|---:|---:|---:|
| Fixed | 0.667 | 0.000 | (see JSON) | **0.000** | **1.000** |
| Fixed rebind | **1.000** | 0.000 | | **0.000** | **1.000** |
| Random | 0.333 | 0.000 | | **0.000** | **1.000** |
| Vanilla | 0.333 | 0.000 | | **0.000** | **1.000** |
| TECE | **0.300** | 0.000 | | **0.000** | **1.000** |

**Scientific readout:** Under oracle-free observations and matched controls, **TECE shows no unique advantage** vs strong fixed-rebind (TECE worse on mean semantic). Strict compositional necessity remains 0. **Negative/equal result accepted — not tuned to invent a win.**

## Failure cases

1. Evolved recovery policies underperform a static `rebind_from_a` baseline on this suite.
2. Reverse tasks often A-only answerable when querying early `role_event` → `composition_necessary=false` (protocol honesty).
3. AV schema still uses text cues over simulated facts — **not** claimed as true audio grounding.
4. Random/Vanilla with matched mutations do not recover fixed-rebind performance here (search noise / objective).

## Not claimed

No real-video RSI; no expensive models; no new method name without incremental mechanism on video.
