# Experiment Health Report

| Metric | Value |
|---|---|
| Experiment ID | `fault_injection_phase_d_sim` |
| Code SHA | `aa79e869a0fe7b3d120e0902b16aacfd97500e3e` |
| Harness SHA | `None` |
| Config Fingerprint | `7a1ad42dbec4b683` |
| Environment | `{"sys_executable": ".../envs/videorsi/bin/python", "python_version": "3.12.15"}` |
| Preflight | **FAIL** |
| Samples (T/V/I/D) | 3 / 0 / 3 / 0 |
| Visual Success Rate | 0.0 |
| Qwen Frames (mean/min/max) | 0.0 / 0 / 0 |
| Tool Errors | `{"INVALID_RUN": 1}` |
| Provider Errors | `{}` |
| Cost | `{}` |
| Protocol Validation | **PASS** |
| Overall Validity | **INVALID** |

## Reason codes

- `imageio_ffmpeg_missing`
- `has_invalid_runs`
- `systematic_vision_infra_failure`

## Diagnostic paths

- `~/lpy/Video-RSI/experiment_guard/out/fault_injection/sim_run/preflight_report.json`
- `~/lpy/Video-RSI/experiment_guard/out/fault_injection/sim_run/arm_validation.json`
- `~/lpy/Video-RSI/experiment_guard/out/fault_injection/sim_run/runtime_summary.json`

## Ranking usability

usable_for_architecture_ranking = **False**

> Answers produced under INVALID_RUN must not be treated as healthy Video Agent architecture evidence.
