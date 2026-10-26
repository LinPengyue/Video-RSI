# Experiment Guard — Offline Test Report

**Scope:** Engineering only. 0 paid API. No Phase D re-run. No Editor RSI. No mutation of frozen research results.

**Branch:** `engineering/experiment-guard`

## How to reproduce

```bash
cd /path/to/Video-RSI
PYTHONPATH=. python3 experiment_guard/tests/run_all.py
```

## Results (this commit)

| Suite | Result | PASS count |
|-------|--------|------------|
| `test_runtime_guard.py` | PASS | 5 |
| `test_result_validator.py` | PASS | 4 |
| `test_protocol_validator.py` | PASS | 5 |
| `test_fault_injection.py` | PASS | 12 |
| `test_preflight.py` | PASS | 4 |
| **Total** | **all suites PASS** | **≈30** |

## Critical regressions

### Phase D `imageio_ffmpeg` missing

- **Preflight:** system Python with `--no-reexec` → `FAIL` / `EXPERIMENT_GUARD_PREFLIGHT_FAIL` **before** any batch.
- **Runtime:** Phase-D-shaped result → `INVALID_RUN` + batch abort on first infra `sample_frames` error.
- **Result validation:** all-invalid vision arm → `overall_validity=INVALID`, `usable_for_architecture_ranking=False`, while naive accuracy may still look high (audit contrast).

### Intentional no-vision

Agent with no visual tools and no infra errors → `VALID_RUN` / Case A. Not flagged as failure.

### Meter inconsistency

Qwen events with `qwen_frames=0` → `INVALID_RUN`.

## Fault injection checklist

| # | Fault | Caught |
|---|-------|--------|
| 1 | Missing `imageio_ffmpeg` | Yes |
| 2 | Invalid ffmpeg path (injected) | Yes |
| 3 | Missing video | Yes |
| 4 | Corrupt / undecodable video | Yes |
| 5 | `sample_frames` exception | Yes |
| 6–7 | Qwen/meter under-report | Yes |
| 8 | Answer after all vision failed | Yes (INVALID; ranking blocked) |
| 9 | Intentional no-vision | Yes (VALID) |
| 10 | Arm sample-set mismatch | Yes |
| 11 | Resume old config fingerprint | Yes |
| 12 | Editor investigation infra fail | Yes |

Example artifacts: `examples/fault_injection_health.{json,md}`.

## Editor / probe mock

Under videorsi: `--editor --probe` preflight PASS (observe + three `infoflow_probe` modes).

## Historical files

No modifications to `research_audit/arch_self_evolution_pilot/runs/phase_d_eval_v1/` or other frozen result trees.
