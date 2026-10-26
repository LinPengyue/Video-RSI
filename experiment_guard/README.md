# Experiment Guard

Fail-closed infrastructure validity for Video-RSI experiments.

- Design: [`EXPERIMENT_GUARD_DESIGN.md`](EXPERIMENT_GUARD_DESIGN.md)
- Integration: [`EXPERIMENT_INTEGRATION_GUIDE.md`](EXPERIMENT_INTEGRATION_GUIDE.md)
- **Acceptance (wired runners):** [`GUARD_INTEGRATION_ACCEPTANCE.md`](GUARD_INTEGRATION_ACCEPTANCE.md)
- Test report: [`EXPERIMENT_GUARD_TEST_REPORT.md`](EXPERIMENT_GUARD_TEST_REPORT.md)
- Example VALID/INVALID health reports: [`examples/`](examples/)

```bash
PYTHONPATH=. python3 experiment_guard/tests/run_all.py
PYTHONPATH=. python3 experiment_guard/mock_acceptance_runner.py --mode both
PYTHONPATH=. python -m experiment_guard --soft --no-reexec
```

Wired into `--execute` of:

- `research_audit/arch_self_evolution_pilot/eval_independent.py`
- `research_audit/arch_self_evolution_pilot/run_editor_arms.py`
