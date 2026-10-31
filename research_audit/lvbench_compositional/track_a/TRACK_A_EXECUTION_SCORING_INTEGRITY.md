# Track A — Execution Scoring Integrity

Date: 2026-10-31 · `ok_for_expensive_rsi=false` · sealed untouched

## Integrity fixes applied

1. **ABSTAIN credit** requires an *explicit* missing-evidence decision (`explicit_abstain=true`), not mere `pred is None`.
2. **Compare path** may use tool-visible locate/query outputs only; **forbidden** to scrape `world.facts` in the agent/scorer fallback (`oracle_world_scraped=false` on all rows).
3. Per-operation success rates recorded in each trace under `per_op_success`.
4. Selection weight search remains label-based on train — **not** claimed as trace-optimized TECE; frozen 4-task binding negative control untuned.

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
