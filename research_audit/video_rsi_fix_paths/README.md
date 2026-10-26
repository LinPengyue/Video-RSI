# Video-RSI Fix Path & Historical Harness Audit

Offline-only audit of `evolution/run-seed42` (no paid API).

## Reports

- `fix_path_audit.md` — deep dive on `lvbench_2480`, `4195`, `5093`
- `historical_harness_comparison.md` — R1–R3 fix/harm + rejected harness value
- `architecture_evolution_implications.md` — mapping to architectural self-evolution Qs

## Reproduce

```bash
cd /path/to/Video-RSI
PYTHONPATH=. python3 research_audit/video_rsi_fix_paths/analyze_fix_paths_offline.py
```

Writes `out/audit_summary.safe.json` (desensitized).

## Not committed

- `local_untracked/` (gitignored) — optional full perception dumps
- Raw `private_gate` JSON, gold answers, API keys, videos
