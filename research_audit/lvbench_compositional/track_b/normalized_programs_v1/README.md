# Track B — `normalized_programs_v1`

Stage 2 lossless/chat-approved normalization + Stage 3 overlap metrics.

## Authority

- Chat-approved handoff (7 graphs + 11-graph per-node Layer1/2 map):  
  `chat_approved_handoff/track_b_stage2_chat_approved_handoff_v1.json`  
  SHA-256 `c2b5aa2ae864dcefd1d71fd23cf6176de680a24b3ed463ba853b930bd5c345ed`
- P7 structured graphs: pilot `provenance_snapshots/P7_*.json` (repo approved v0.2)

Handoff graphs are **conversation-approved sidecars**, not GitHub historical structured originals.

## Run

```bash
python3 eng/run_stage2_stage3.py --stage all
python3 tests/test_normalized_programs_v1.py -v
```

## Split

- Formal analysis: 5 Seen / 2 Unseen
- Candidate sensitivity only: A, B, P7_R4_F1, P7_R4_F2

## Stage 4 (split validity)

```bash
python3 eng/build_stage4_split_validity_audit.py
python3 tests/test_stage4_split_validity.py -v
```

Outputs: `stage4_split_validity_audit.json`, `stage4_split_validity_audit.md`.  
Stage-3 metrics preserved under `reports/stage3_historical/`.
