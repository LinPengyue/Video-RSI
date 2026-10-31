# Track A — Execution Scoring Integrity

Date: 2026-10-31 · `ok_for_expensive_rsi=false` · sealed untouched

## Integrity fixes applied

1. **ABSTAIN credit** requires an *explicit* missing-evidence decision (`explicit_abstain=true`), not mere `pred is None`. Wrong-schema abstain on non-ABSTAIN gold is **not** credited (`wrong_schema_abstain_not_credited`).
2. **Compare path** requires exact/canonical answer match; `evidence_path_valid` alone never credits; substring match removed.
3. Per-operation success rates recorded in each trace under `per_op_success`.
4. Oracle boundary: scoring section must not scrape executor world state; tests assert denied patterns + `executor_saw_gold_answer=false`.
5. Selection weight search remains label-based on train — **not** claimed as trace-optimized TECE; frozen 4-task binding negative control untuned.

Regression tests: `test_wrong_schema_abstain_not_credited`, `test_compare_evidence_path_valid_alone_not_enough`, `test_oracle_boundary_no_world_facts_in_scorer`.

## Current numbers (after integrity fix)

| | choice_acc | exec_acc | abstain | explicit_abstain | oracle_scrape |
|--|------------|----------|---------|------------------|---------------|
| selected policy | 0.833 | 0.333 | 0.333 | 0.333 | 0.000 |
| gold DAG upper | 1.000 | 0.333 | 0.333 | 0.333 | 0.000 |

Semantic-control exec_ok_rate=0.417 (masks/swaps/paraphrase).

## Non-claims

- No real-video generalization.
- No expensive RSI.
- Low exec_acc after removing oracle leakage / soft abstain is an **accepted negative** on this tiny harness, not a method failure to paper over.
