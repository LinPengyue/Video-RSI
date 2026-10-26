# Architectural Evolution — Minimal Experiment Preflight

Offline-only preparation for a mechanism-level info-flow A/B (Qwen describe→DeepSeek vs Qwen direct VQA) and a Same-Code Placebo Gate check on `run-seed42` parents.

## Do / Don't

- **Do:** run `analyze_placebo_and_feasibility.py`, read `PREFLIGHT_REPORT.md`, inspect `exploratory_samples_n20.json`.
- **Don't:** call paid APIs, resume RSI rounds, mutate `evolution/`, use private Gate IDs as a develop set, upload gold/videos/keys.

## Reproduce offline

```bash
cd /path/to/Video-RSI
PYTHONPATH=. python3 research_audit/arch_evolution_min_preflight/analyze_placebo_and_feasibility.py
PYTHONPATH=. python3 research_audit/arch_evolution_min_preflight/ab_infoflow_runner.py --dry-run
```

## Push hygiene

Safe to publish: this directory’s markdown, scripts, `*.safe.json`, frozen sample **IDs** (no questions/answers/gold).

Never push: `private_gate/`, `*_oracle.jsonl`, raw videos, `.env`, API keys, Gate item JSON with questions.
