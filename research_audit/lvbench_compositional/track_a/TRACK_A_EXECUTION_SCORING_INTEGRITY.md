# Track A — Execution Scoring Integrity

Date: 2026-10-31 · post-`ad42987` gold-feed closure · `ok_for_expensive_rsi=false` · sealed untouched

## Integrity fixes applied

1. **ABSTAIN credit** requires an *explicit* missing-evidence decision (`explicit_abstain=true`), not mere `pred is None`.
2. **Compare path** may use tool-visible locate/query outputs only; **forbidden** to scrape `world.facts` in the agent/scorer fallback (`oracle_world_scraped=false` on all rows).
3. Per-operation success rates recorded in each trace under `per_op_success`.
4. Selection weight search remains label-based on train — **not** claimed as trace-optimized TECE; frozen 4-task binding negative control untuned.
5. **VERIFY gold-feed closed (audit `4e8872f` P0):** `schema_to_program` no longer sets `verify_answer.inputs["answer"]=task.answer`. VERIFY binds `answer=None` / `answer_source=agent_prediction_runtime` at compile time; `run_program_with_agent_pred` fills VERIFY from the prior `query_property` prediction only. Scorer alone sees gold. Instrumented `executor_saw_gold_answer` / suite rate. Negative tests: `test_verify_answer_never_receives_task_answer`, `test_sentinel_gold_world_mismatch_no_executor_gold_feed` (includes VERIFY).

## Current numbers (after gold-feed closure; matched 6-task control, seed=42)

| | choice_acc | exec_acc | abstain | explicit_abstain | oracle_scrape | executor_saw_gold |
|--|------------|----------|---------|------------------|---------------|-------------------|
| selected policy | 0.833 | 0.333 | 0.333 | 0.333 | 0.000 | 0.000 |
| gold DAG upper | 1.000 | 0.333 | 0.333 | 0.333 | 0.000 | 0.000 |

Semantic-control exec_ok_rate=0.417 (masks/swaps/paraphrase).

**Historical note:** Prior 0.333 exec_acc under latent VERIFY gold feed is retained as a diagnostic only; post-fix matched control remains **0.333 / executor_saw_gold_rate=0** — accepted negative, not leakage-free method evidence.

## Non-claims

- No real-video generalization.
- No expensive RSI.
- Low exec_acc after removing oracle leakage / soft abstain / VERIFY gold feed is an **accepted negative** on this tiny harness, not a method failure to paper over.
