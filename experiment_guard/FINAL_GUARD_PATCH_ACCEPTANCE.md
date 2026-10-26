# Final Guard Patch Acceptance

**Base:** `engineering/experiment-guard` @ `427bb19`  
**Scope:** Direct VQA into multi-arm Guard + protect frozen Phase D artifacts. Offline only.

## Fixes

### 1. Direct VQA is Guard-auditable

- New module: `experiment_guard/direct_vqa_audit.py`
  - `normalize_direct_vqa_record` — maps real provider/frame fields into `classify_item_run` shape (never fabricates `qwen_frames`)
  - `assess_direct_vqa_reuse` — resume only when prompt_sha / version / model / frame count / timestamps (or proven legacy inference) match
- `eval_independent.run_direct_vqa` now returns `(summary, guard_results, reuse_stats)` and feeds **`results_by_arm["direct_vqa"]`** into `guard.finalize(multi_arms=...)`
- Provider / extract failures abort remaining Direct VQA IDs via RuntimeGuard

### 2. Historical data protection

- Default `--run-dir` → `runs/phase_d_eval_guarded_v1` (not `phase_d_eval_v1`)
- `assert_run_dir_safe` refuses writes under frozen `phase_d_eval_v1`
- Safe summary written to **`run_dir/phase_d_eval.safe.json`** + dated `out/phase_d_eval_guarded_*.safe.json`
- **Never** overwrites `out/phase_d_eval.safe.json`
- Legacy Direct calls may be reused only after `assess_direct_vqa_reuse` proves compatibility (not `status=ok` alone; not hard-coded `cache_compatible=True`)

## Offline tests (`test_direct_vqa_guard_patch.py`)

| # | Case | Result |
|---|------|--------|
| 1 | Initial valid, Direct invalid → ranking blocked | PASS |
| 2 | Direct valid, Initial invalid → ranking blocked | PASS |
| 3 | Both valid → multi-arm VALID | PASS |
| 4 | Direct provider failure stops remaining IDs | PASS (1/4 completed) |
| 5 | Resume rejects incompatible prompt_sha | PASS |
| 6 | New retest does not touch frozen Phase D files | PASS |
| 7 | `--limit 4` both arms enter Guard multi_arm | PASS |
| + | Normalize rejects ok+0 frames; dry-run shows new defaults | PASS |

Full suite: `PYTHONPATH=. python3 experiment_guard/tests/run_all.py` — all suites PASS.

## Remaining risks

1. Other runners (`run_batch*.py`, AutoResearch, `cli.py run`) still unwired.
2. Legacy Direct reuse without stored timestamps relies on prompt_sha + n_frames proof — stricter than `status=ok`, but not bit-identical frame hashes.
3. In-flight concurrent harness tasks may finish after abort (recorded as `completed_after_abort`).
4. Baseline/Treatment candidate dirs may be missing — arms skipped; ranking requires declared arms present in `results_by_arm`.

## Formal paid command (not executed here)

```bash
cd /path/to/Video-RSI
set -a && source providers.env && set +a
export ARCH_AB_ALLOW_PAID=1 PYTHONPATH=.
PY="$(python3 -c 'import json;print(json.load(open("evolution/run-seed42/effective_config.json"))["execution"]["python"])')"
"$PY" research_audit/arch_self_evolution_pilot/eval_independent.py \
  --execute --concurrency 2 \
  --run-dir research_audit/arch_self_evolution_pilot/runs/phase_d_eval_guarded_v1 \
  --arms initial,direct_vqa \
  --limit 4
```

Guard runs inside the runner. Frozen `phase_d_eval_v1` remains read-only for optional proven Direct reuse.

**Stopped — no paid API.**
