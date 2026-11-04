## v0.1.1 — WP2.1 A/B recovery audit (no Gold / no invented QA)

- Added `reports/AB_SOURCE_RECOVERY_AUDIT.json` with per-field recovery evidence.
- Added `reports/WINDOW_RECOVERY_C2_R3_F1_F2_AUDIT.json` (filename candidates only; not promoted).
- A/B remain `GRAPH_ONLY` — question/answer/video_id/windows unresolved under binding rules.
- `releases/v0.1.0` left immutable; this snapshot is `releases/v0.1.1`.
- No Track A / sealed / 5+2 / 7+4 / Gold changes.

# Changelog

## v0.1.0-dev / releases/v0.1.0 — WP2 bootstrap

- Initialize LongVideoCompBench directory, schemas, tools, and internal release snapshot.
- Import 11 Stage-2 normalized program graphs.
- Import complete QA for seeds with authoritative question/answer (WP1 5+2 + P7_R4_F1/F2).
- Record A/B as `GRAPH_ONLY` (missing original QA in approved sources) — PARTIAL bootstrap.
- Freeze 5+2 reference; record 7+4 DEV split as `PROPOSED`.
- No Gold promotion; no Track A launch; no public license claim.
