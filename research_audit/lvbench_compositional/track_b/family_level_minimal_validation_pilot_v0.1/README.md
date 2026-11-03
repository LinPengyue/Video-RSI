# FAMILY_LEVEL_MINIMAL_VALIDATION_PILOT_v0.1

Independent Track B pilot config on `research/lvbench-comp-video-grounded-evidence`.

Approved graphs are snapshotted from `research/lvbench-comp-p7-hil-pilot` with original versions retained under `provenance_snapshots/`.

| Role | IDs |
|------|-----|
| Seen | SP001, SP002, SP005, SP201, SP202 |
| Unseen | P7_VTCD_C2, P7_TJR_R3 |
| Hold | P7_R4_F1, P7_R4_F2, SP205 |

`pilot_role` ≠ `formal_seen_train` / `formal_unseen`. Open-ended QA only.

## Artifacts

- `PILOT_CONFIG.json` / `PILOT_INVENTORY.json` — P0
- `reports/ENGINEERING_INTEGRITY_REPORT.*` — P1
- `p2_multiframe_link/` — P2 digest of existing multiframe ROI pilot (run_003 untouched)
- `p3_new_video_discovery/` — P3 source register + ≤16-frame ROIs pending GPT observation
- `p4_scientific_review_pack/` — P4 joint review pack
- `RUN_004_GATE.json` — **NOT_STARTED**

Rebuild: `python3 eng/build_pilot_v0_1.py`  
Tests: `python3 -m unittest discover -s tests -p 'test_*.py'`
