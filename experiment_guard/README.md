# Experiment Guard

Fail-closed infrastructure validity for Video-RSI experiments.

- Design: [`EXPERIMENT_GUARD_DESIGN.md`](EXPERIMENT_GUARD_DESIGN.md)
- Integration: [`EXPERIMENT_INTEGRATION_GUIDE.md`](EXPERIMENT_INTEGRATION_GUIDE.md)
- Test report: [`EXPERIMENT_GUARD_TEST_REPORT.md`](EXPERIMENT_GUARD_TEST_REPORT.md)
- Example INVALID health report: [`examples/`](examples/)

```bash
PYTHONPATH=. python3 experiment_guard/tests/run_all.py
PYTHONPATH=. python -m experiment_guard --soft --no-reexec
```
