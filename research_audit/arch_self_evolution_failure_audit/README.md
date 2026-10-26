# Arch Self-Evolution Failure Audit

Offline audit of pilot `ff1d383`. **No paid API. Does not overwrite** `runs/phase_d_eval_v1` or `runs/editor_arms_v1`.

## Verdict

**PARTIALLY VALID** pilot overall; Phase D architecture comparison = **INVALID EXPERIMENT** (harness vision broken via missing `imageio_ffmpeg` in eval interpreter).

## Docs

| File | Content |
|---|---|
| `PHASE_D_VALIDITY_AUDIT.md` | Zero-frame root cause; what to withdraw |
| `INFOFLOW_PROBE_AUDIT.md` | Probe wiring / discovery / Editor behavior |
| `ROOT_CAUSE_ANALYSIS.md` | Categorized causes |
| `NEXT_EXPERIMENT_DECISION.md` | E0 design only |

## Reproduce offline

```bash
PYTHONPATH=. python3 research_audit/arch_self_evolution_failure_audit/audit_phase_d_offline.py
PYTHONPATH=. python3 research_audit/arch_self_evolution_failure_audit/test_infoflow_probe_mock.py
```

Requires local gitignored run dirs from the pilot on disk.
