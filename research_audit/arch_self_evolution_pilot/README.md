# Architectural Self-Evolution Pilot

Counterfactual info-flow diagnosis for Video-RSI Editor. Does **not** run Round 4–20 or mutate `evolution/run-seed42`.

## Verdict

**INSUFFICIENT** — see `PHASE_E_FINAL_JUDGMENT.md`.

## Phase docs

- `PHASE_A_OFFLINE_AUDIT.md`
- `PHASE_B_STABILITY.md`
- `PHASE_E_FINAL_JUDGMENT.md`
- Editor/eval details also in `out/*.safe.json`

## Offline

```bash
PYTHONPATH=. python3 research_audit/arch_evolution_min_preflight/test_ab_infoflow_offline.py
PYTHONPATH=. python3 research_audit/arch_self_evolution_pilot/select_independent_eval.py
```

## Push hygiene

Safe: markdown, scripts, `out/*.safe.json`.  
Never: `runs/`, videos, oracles, `providers.env`, keys.
