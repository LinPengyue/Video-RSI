# Architectural Evolution — Minimal Info-Flow Experiment

Preflight + executed mechanism probe: Caption→DeepSeek vs Qwen Direct VQA under matched overview timestamps.

## Docs

- `PREFLIGHT_REPORT.md` — placebo Gate / feasibility / sample freeze  
- `MECHANISM_EXPERIMENT_REPORT.md` — executed A/B + diagnosis + GO/STOP  

## Offline

```bash
PYTHONPATH=. python3 research_audit/arch_evolution_min_preflight/test_ab_infoflow_offline.py
PYTHONPATH=. python3 research_audit/arch_evolution_min_preflight/analyze_placebo_and_feasibility.py
PYTHONPATH=. python3 research_audit/arch_evolution_min_preflight/analyze_ab_results.py
```

## Paid (manual; not auto)

```bash
set -a && source providers.env && set +a
export ARCH_AB_ALLOW_PAID=1 PYTHONPATH=.
python3 research_audit/arch_evolution_min_preflight/ab_infoflow_runner.py --phase connectivity --provider http --execute
python3 research_audit/arch_evolution_min_preflight/ab_infoflow_runner.py --phase full_ab --provider http --execute
python3 research_audit/arch_evolution_min_preflight/ab_infoflow_runner.py --phase diagnose --provider http --execute
```

Local raw run data lives under `runs/` (gitignored).

## Push hygiene

Safe: markdown, scripts, `out/*.safe.json`, frozen sample IDs.  
Never: `runs/` frames/raw, oracles, videos, `providers.env`, keys, private Gate.
