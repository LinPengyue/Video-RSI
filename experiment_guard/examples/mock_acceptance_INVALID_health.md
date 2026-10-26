# Experiment Health Report

| Metric | Value |
|---|---|
| Experiment ID | `mock_acceptance_invalid` |
| Code SHA | `9203555b5772eb2c1d87df96034671168c0eb0b8` |
| Harness SHA | `afcedacceee8480d` |
| Config Fingerprint | `7a1ad42dbec4b683` |
| Environment | `{"sys_executable": ".../envs/videorsi/bin/python", "python_version": "3.12.15"}` |
| Preflight | **PASS** |
| Samples (T/V/I/D) | 2 / 0 / 2 / 0 |
| Visual Success Rate | 0.0 |
| Qwen Frames (mean/min/max) | 0.0 / 0 / 0 |
| Tool Errors | `{"INVALID_RUN": 2}` |
| Provider Errors | `{}` |
| Cost | `{}` |
| Protocol Validation | **PASS** |
| Overall Validity | **INVALID** |

## Reason codes

- `missing_samples`
- `has_invalid_runs`
- `systematic_vision_infra_failure`

## Diagnostic paths

- `~/lpy/Video-RSI/experiment_guard/out/mock_acceptance/invalid/preflight_report.json`
- `~/lpy/Video-RSI/experiment_guard/out/mock_acceptance/invalid/arm_validation.json`
- `~/lpy/Video-RSI/experiment_guard/out/mock_acceptance/invalid/runtime_summary.json`
- `~/lpy/Video-RSI/experiment_guard/out/mock_acceptance/invalid/protocol_validation.json`

## Ranking usability

usable_for_architecture_ranking = **False**

> Answers produced under INVALID_RUN must not be treated as healthy Video Agent architecture evidence.
