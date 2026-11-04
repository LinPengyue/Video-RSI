# Track B — `normalized_programs_v1`

Stage 2 lossless normalization + Stage 3 overlap gate.

## Run

```bash
python3 eng/run_stage2_stage3.py --stage all
python3 tests/test_normalized_programs_v1.py -v
```

## Current gate

Stage 2 is **BLOCKED** until:

1. Standalone approved graphs `A` and `B` exist (or the 11-set is scientifically revised).
2. SP001/SP002/SP005 have authoritative node I/O + edge lists (not only `graph_as_reviewed` macros).
3. SP201/SP202 have an approved 4-node/3-edge expansion (macros must not be auto-split).
4. Layer-1/2 operator vocab is scientifically frozen (currently provisional engineering map).

Stage 3 M1–M4 remain **null** while Stage 2 is BLOCKED (no fabricated overlap).
