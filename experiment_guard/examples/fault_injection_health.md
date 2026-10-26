# Experiment Health Report

| Metric | Value |
|---|---|
| Experiment ID | `fault_injection_phase_d_sim` |
| Code SHA | `427bb19f8292259042dd6a60e7b7f559f36b1b3b` |
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
| Protocol Validation | **INCOMPLETE** |
| Overall Validity | **INVALID** |

## Reason codes

- `imageio_ffmpeg_missing`
- `protocol_incomplete:frozen_eval_ids_declared`
- `protocol_incomplete:train_eval_isolation`
- `protocol_incomplete:gate_eval_isolation`
- `protocol_incomplete:arm_config_fingerprints`
- `protocol_incomplete:arm_harness_fingerprints`
- `protocol_incomplete:resume_cache_protocol`
- `has_invalid_runs`
- `systematic_vision_infra_failure`

## Diagnostic paths

- `~/lpy/Video-RSI/experiment_guard/out/fault_injection/sim_run/preflight_report.json`
- `~/lpy/Video-RSI/experiment_guard/out/fault_injection/sim_run/arm_validation.json`
- `~/lpy/Video-RSI/experiment_guard/out/fault_injection/sim_run/runtime_summary.json`
- `~/lpy/Video-RSI/experiment_guard/out/fault_injection/sim_run/protocol_validation.json`

## Ranking usability

usable_for_architecture_ranking = **False**

> Answers produced under INVALID_RUN must not be treated as healthy Video Agent architecture evidence.
