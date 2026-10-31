# Dual-track progress update

Latest: run_002 **P0 patch** + run_003 **blocked** · `track_b/batch_factory/RUN002_PATCH_AND_RUN003_REPORT.md`  
Audits: `CHATGPT_AUDIT_68AB45C_RUN002_FOLLOWUP_2026-10-31.md`, `CHATGPT_RUN002_FRAME_AUDIT.jsonl`

## Shared
- **UNASSIGNED**; no auto-**SUPPORTED**; sealed untouched; `ok_for_expensive_rsi=false`
- run_001 / run_002 immutable

## Track A
- Scoring integrity: wrong-schema abstain blocked; compare exact match; oracle boundary tests
- choice≈0.833 / exec≈0.333 retained negative
- `track_a/TRACK_A_EXECUTION_SCORING_INTEGRITY.md`

## Track B
- Factory v0.2.1: question leakage gate, metric split, review readiness gates
- `run_002_patch_regen/`: leakage_error=0; formal_blind_ready=0; model_inferred=0
- run_003: **BLOCKED_NO_NEW_DEV_VIDEO_AND_NO_SEMANTIC_EXTRACTOR**
