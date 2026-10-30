# Dual-track progress update

Latest factory baseline: see `DUAL_TRACK_ROUND_REPORT_BATCH_FACTORY_2026-10-30.md`  
Plan executed: `TRACK_B_BATCH_FACTORY_AND_DUAL_TRACK_RESET_2026-10-30.md`

## Shared
- All candidates remain **UNASSIGNED**; no auto-**SUPPORTED**
- Sealed final not accessed; `ok_for_expensive_rsi=false`
- Contaminated construction videos are DEV only

## Track A
- Selection-only metrics frozen as incomplete: choice ≠ execution
- New: `program_execution.py` compiles selected DAGs → `TypedEvidenceExecutor` traces
- Result: choice_acc≈0.833 vs **exec_acc≈0.333** (gold DAG also 0.333 on this harness)
- Frozen 4-task matched binding parity: do not retune
- Report: `track_a/TRACK_A_EXECUTION_OVER_SELECTION.md`

## Track B
- Batch factory CLI: `python -m tools.lvbench_comp.batch_factory run ...`
- Real run_001 on 8 DEV_CONSTRUCTION videos with local MP4s
- Funnel: 110 events → 8 relations → 8 QA drafts → auto grades → **8-item human packet PENDING_HUMAN**
- Uncertain QAs do not block production
- Report: `track_b/batch_factory/run_001/PRODUCTION_AND_QUALITY_REPORT.md`
