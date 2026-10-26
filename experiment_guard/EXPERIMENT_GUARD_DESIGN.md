# Experiment Guard — Design

## Problem

Phase D of the Architectural Self-Evolution Pilot completed and produced accuracy tables, but the Initial / Baseline / Treatment harness arms all had `qwen_frames=0` because the **host** Python lacked `imageio_ffmpeg`. Agents still requested overview/scan/inspect; DeepSeek still answered; results were marked `answered`. Direct VQA used a separate working ffmpeg path — an unfair comparison. Research conclusions were drawn from **invalid** runs.

**Experiment completion ≠ scientific validity.**

## Goals

1. Block paid / batch experiments when the visual stack is broken (**fail-closed**).
2. Distinguish intentional no-vision (Case A) from infrastructure vision failure (Case B) and partial failure (Case C).
3. Prevent INVALID runs from entering unmarked architecture rankings.
4. Stay outside Gate acceptance rules, Harness agent logic, and model prompts.
5. Stay lightweight: Python modules + JSON/Markdown — no Prometheus/DB.

## Non-goals

- Changing Gate thresholds or RSI round logic
- Auto-starting Editor evolution or paid evals
- Requiring every question to call Qwen
- Forcing identical frame counts across architectures (unless the protocol claims matched frames)

## Architecture (3 layers)

```
┌─────────────────────────────────────────────────────────┐
│  GuardedExperiment / require_preflight (outer runner)   │
├──────────────┬──────────────────┬───────────────────────┤
│ Layer 1      │ Layer 2          │ Layer 3               │
│ Preflight    │ Runtime Guard    │ Result + Protocol     │
│              │                  │ Validation            │
│ interpreter  │ Case A/B/C       │ arm / multi-arm       │
│ dual-env     │ batch abort      │ leakage / resume      │
│ sample_frames│ ENGINEERING vs   │ health report         │
│ smoke+meter  │ MODEL vs TASK    │ ranking gate          │
└──────────────┴──────────────────┴───────────────────────┘
```

### Layer 1 — Preflight (`preflight.py`)

Before any formal API batch:

- Compare `sys.executable` vs `config.execution.python` (re-exec or FAIL).
- Probe **both** interpreters for `imageio_ffmpeg` + ffmpeg binary (Phase D lesson: Solver worker ≠ Editor host).
- Run **production** `Services.sample_frames` (4 frames) + Mock Qwen + Meter checks.
- Optional: Editor `observe` + `infoflow_probe` mock modes.
- Optional: OCR root, provider env presence (never print secrets).
- Status: `PASS` | `FAIL` | `NOT_APPLICABLE` per check. Any required FAIL → refuse start.

### Layer 2 — Runtime (`runtime_guard.py`)

Per sample:

| Case | Condition | Validity |
|------|-----------|----------|
| A | No visual tools, no infra errors | `VALID_RUN` (intentional no-vision OK) |
| B | Visual tools requested; all fail via infra | `INVALID_RUN` |
| C | Some visual OK, some fail | `DEGRADED_RUN` |

Batch abort (fail-closed): first systematic `sample_frames` infra error; repeated infra; meter vs trace contradiction; config/harness fingerprint change mid-run.

Error kinds: `ENGINEERING_ERROR` | `MODEL_ERROR` | `TASK_FAILURE`.

### Layer 3 — Result & Protocol (`result_validator.py`, `protocol_validator.py`)

- Single-arm and multi-arm validity: `VALID` | `PARTIALLY_VALID` | `INVALID` + `reason_codes`.
- Train/Gate/Editor vs eval isolation; arm ID equality; resume fingerprint; cache reuse rules.
- Architecture ranking export only when `usable_for_architecture_ranking=True`. Naive accuracy including INVALID is retained for audit contrast only.

### Health report (`health_report.py`)

Writes `experiment_health.json` + `.md` with fingerprints, preflight, sample counts, frames, costs, protocol status, overall validity, diagnostic paths. Paths/secrets redacted.

## Dual interpreter rule

| Surface | Who runs `sample_frames` | Guard requirement |
|---------|--------------------------|-------------------|
| Harness `run_item` → worker | `config.execution.python` | Probe that binary |
| Editor / Investigation / in-process eval | Host `sys.executable` | Host must match production env (re-exec) |
| Direct VQA / `infoflow_lib.extract_frames` | Side ffmpeg path | Healthy, but **not** a substitute for Services smoke |

## Public API

```python
from experiment_guard import require_preflight, classify_item_run, validate_arm, write_health_report
from experiment_guard.guarded_runner import GuardedExperiment
from experiment_guard.preflight import PreflightCapabilities
```

## Package layout

```
experiment_guard/
  __init__.py
  preflight.py
  runtime_guard.py
  result_validator.py
  protocol_validator.py
  health_report.py
  guarded_runner.py
  fingerprints.py
  redact.py
  adapters.py          # coverage matrix
  tests/
  examples/            # fault-injection health report
  EXPERIMENT_*.md
```
