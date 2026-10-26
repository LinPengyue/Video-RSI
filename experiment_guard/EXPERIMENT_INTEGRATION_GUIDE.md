# Experiment Guard — Integration Guide

## Install / import

Package lives at repo root `experiment_guard/`. Set `PYTHONPATH=.` (or install editable later). Prefer launching with the production interpreter:

```bash
export PYTHONPATH=.
/path/to/envs/videorsi/bin/python -m experiment_guard --soft --no-reexec
```

## Minimum paid-experiment preamble

```python
from experiment_guard import require_preflight
from experiment_guard.preflight import PreflightCapabilities

require_preflight(
    capabilities=PreflightCapabilities(
        visual_sample_frames=True,
        editor_investigation=False,  # True for Editor arms
        infoflow_probe=False,        # True for Treatment probe
        host_must_match_config_python=True,
    ),
    reexec=True,
    require_provider_env=True,  # when about to call paid APIs
)
```

On FAIL → `SystemExit` with `EXPERIMENT_GUARD_PREFLIGHT_FAIL:...`. **No silent no-vision downgrade.**

## Full lifecycle (recommended)

```python
from pathlib import Path
from experiment_guard.guarded_runner import GuardedExperiment
from experiment_guard.preflight import PreflightCapabilities

guard = GuardedExperiment(
    experiment_id="my_eval_v1",
    out_dir=Path("runs/my_eval_v1/guard"),
    capabilities=PreflightCapabilities(visual_sample_frames=True),
    require_provider_env=True,
)
guard.start(reexec=True)

results = []
for item in items:
    row = run_one(item)  # existing runner; unchanged agent logic
    results.append(row)
    if guard.observe(row):
        break  # infrastructure abort

health = guard.finalize(results, gold=gold, expected_ids=ids)
assert health["usable_for_architecture_ranking"], health["reason_codes"]
```

## CLI

```bash
# Visual smoke only (0 API)
python -m experiment_guard --soft --no-reexec \
  --out experiment_guard/out/preflight_report.json

# + Editor observe + infoflow_probe mocks
python -m experiment_guard --soft --no-reexec --editor --probe

# Hard fail (exit 2) for CI / paid gates
python -m experiment_guard --no-reexec
```

## Offline tests

```bash
PYTHONPATH=. python3 experiment_guard/tests/run_all.py
```

## Next formal experiment command (template)

```bash
set -a && source providers.env && set +a
export ARCH_AB_ALLOW_PAID=1 PYTHONPATH=.
# 1) Guard must PASS
$(jq -r '.execution.python' evolution/run-seed42/effective_config.json) \
  -m experiment_guard --no-reexec --require-provider-env
# 2) Then launch your existing runner (after adding require_preflight at top)
# Example (after wiring):
# $(...)/python research_audit/arch_self_evolution_pilot/eval_independent.py --execute ...
```

Do **not** start Editor RSI rounds from Guard. Guard only certifies infrastructure.

## Entry-point coverage

| Status | Meaning |
|--------|---------|
| **wired** | Guard APIs usable as-is (post-hoc validators) |
| **documented** | Add `require_preflight` / `GuardedExperiment` at outer `main()` |
| **gap** | Needs extra engineering |

See `adapters.py` (`ENTRY_POINTS`). Summary:

| Category | Path | Status |
|----------|------|--------|
| Phase D-style eval | `eval_independent.py` | documented — **highest priority** |
| Editor arms | `run_editor_arms.py` | documented |
| Info-flow A/B | `ab_infoflow_runner.py` | documented |
| Batch / MLVU | `run_batch*.py` | documented |
| Train/Gate CLI | `solver_full_workspace/cli.py` `run` | documented |
| AutoResearch paid | `exp1_glm53/run_*.py` | documented |
| Offline analyze/score | `score.py`, audit analyzers | wired |
| DSH `investigate.py` | remote broker | **gap** |

## What Guard does **not** cover yet

1. Remote DSH investigation server health.
2. Automatic one-line patches inside every historical runner (callers must wire).
3. Claiming statistical significance from small-N gaps.
4. Matched-frame equality unless the experiment protocol asserts it.

## Potential silent failures that remain without wiring

If an outer script never calls Guard, Phase D can recur. Wiring is mandatory for scientific claims — Guard cannot protect uninstrumented entry points.
