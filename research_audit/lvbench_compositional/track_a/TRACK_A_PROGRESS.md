# TRACK A PROGRESS — Typed Evidence Contract Evolution

Expensive RSI: **not run** (`ok_for_expensive_rsi=false`).

## Method interface

Ops: `locate_event` → `resolve_reference` → `track_identity` → `query_property` → `verify_answer`  
Credit via `EvidenceDependencyGraph` (A → binding → B → answer).

Code: `tools/lvbench_comp/typed_evidence_contract/`.

## This round

- Real evidence-contract verify (no flag/timestamp shortcuts)
- Non-identical recovery with rebind + logging
- Closed evolver loop + Fixed/Random/Vanilla/TECE synthetic ablation
- Report: `TRACK_A_EVOLUTION_REPORT.md`

Synthetic TECE Seen/Unseen: 1.00 / 1.00 vs Fixed 0.67 / 0.00 (mechanism only).

## Status

**Runnable TECE mechanism prototype. NOT a real-video RSI claim.**
