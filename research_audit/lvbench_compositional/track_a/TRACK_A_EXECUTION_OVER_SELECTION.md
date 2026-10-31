# Track A — Execution Over Selection

Date: 2026-10-30 · `ok_for_expensive_rsi=false` · sealed: not accessed · partition: N/A (synthetic)

## Verdict

Selector **program_choice_accuracy=0.833** is **not** the same as
**execution_answer_accuracy=0.333** after running the chosen DAG.
Gold-DAG upper bound execution_answer_accuracy=0.333.

n_test_questions=6, n_held_out_examples=4,
n_independent_test_worlds=6.

## Budget-matched arms (select → execute)

| Arm | choice_acc | exec_acc | both | abstain | mean_tools | held_exec |
|-----|------------|----------|------|---------|------------|-----------|
| strong_static_selector | 0.833 | 0.333 | 0.333 | 0.333 | 4.50 | 0.500 |
| random | 0.333 | 0.333 | 0.167 | 0.500 | 4.17 | 0.500 |
| evolver_weights | 0.833 | 0.333 | 0.333 | 0.333 | 4.33 | 0.500 |
| oracle_gold_dag | 1.000 | 0.333 | 0.333 | 0.333 | 4.17 | 0.500 |

## Semantic controls

n=24 (paraphrase / force-forward / drop_A / drop_B / swap_roles / swap_order).
exec_ok_rate=0.417.

## What this is / is not

- **Is**: compiling selected `ProgramSchema` nodes into `TypedEvidenceExecutor` ops; recording trace, tool cost, abstention, answer check.
- **Is not**: video RSI, expensive search, or proof of unseen-graph composition beyond this synthetic harness.
- Frozen 4-task matched binding parity remains **FROZEN_NEGATIVE_CONTROL_DO_NOT_TUNE**.

## Hashes

```
{
  "forward_person_action": "eebe6b9bf1b690a3",
  "reverse_event_to_prior_action": "0586bcbfab3f704b",
  "compare_two_state_transitions": "3b7b93286889d065",
  "missing_evidence_abstain": "2755edda56579c3c"
}
```
