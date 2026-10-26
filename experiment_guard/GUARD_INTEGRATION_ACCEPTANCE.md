# Experiment Guard — Integration Acceptance

**Base:** `engineering/experiment-guard` @ `9203555`  
**This work:** forced wiring + Guard validity fixes + E2E acceptance (0 paid API).

## Acceptance criteria (definition of done)

> Historical Phase D silent failure cannot recur through the formal execution entry points.

| Criterion | Evidence |
|-----------|----------|
| `--execute` cannot skip Guard | `eval_independent.py` / `run_editor_arms.py` call `GuardedExperiment.start(...)` **before** any `PinnedProvider` / `HttpProvider` |
| Wrong Python / missing `imageio_ffmpeg` blocked | Preflight FAIL under `/usr/bin/python3`; `require_preflight(reexec=False)` exits |
| Runtime abort on infra vision failure | Concurrent batch: 24 IDs → submitted=2, never_submitted=22 after first Phase-D-shaped error |
| Config drift detected via disk re-read | `live_fingerprint()` / `reread_fingerprint()`; observe aborts with `config_or_harness_fingerprint_changed` |
| Formal protocol never silent PASS | Missing declarations → `INCOMPLETE`, `usable_for_architecture_ranking=False` |
| Intentional no-vision allowed | Case A → `VALID_RUN`, no abort |
| Ranking gated | `architecture_ranking.json` usable only when overall VALID + protocol PASS |
| Dry-run / prepare-only | No paid provider; Guard preflight not required |

## Wired entry points

| Entry | Guard behavior |
|-------|----------------|
| `research_audit/arch_self_evolution_pilot/eval_independent.py` | `start(reexec=True)` on `--execute`; `run_batch` per harness arm; health + formal protocol; ranking suppressed if invalid |
| `research_audit/arch_self_evolution_pilot/run_editor_arms.py` | `start` before Editor; post-phase investigation infra scan via `observe`; health report |

## Coverage gaps (not yet wired)

| Entry | Status |
|-------|--------|
| `run_batch.py` / `run_batch_checkpoint.py` | documented — add same `GuardedExperiment` preamble |
| `solver_full_workspace/cli.py` `run` | documented |
| `ab_infoflow_runner.py` / `stability_runner.py` | documented |
| AutoResearch `exp1_glm53/run_*.py` | documented |
| `solver_full_workspace/investigate.py` (DSH) | **gap** — remote server health |

See `adapters.py`.

## Guard self-fixes in this revision

1. **Fingerprint:** `fingerprint_snapshot.py` + `GuardedExperiment.live_fingerprint()` re-reads config/harness from disk; no longer compares a cached string to itself.
2. **Concurrent abort:** `concurrent_batch.run_guarded_batch` incremental submit; cancels not-started futures; records `never_submitted` / `completed_after_abort`.
3. **Protocol:** formal mode → `PASS` \| `FAIL` \| `INCOMPLETE`; matched-frame claims compare per-item timestamps + bundle hashes.

## Tests

```bash
PYTHONPATH=. python3 experiment_guard/tests/run_all.py
PYTHONPATH=. python3 experiment_guard/mock_acceptance_runner.py --mode both
```

**Result:** all suites PASS (~42 PASS lines across 6 suites).

## Example health reports

- VALID: `examples/mock_acceptance_VALID_health.{json,md}`
- INVALID (Phase-D sim + abort): `examples/mock_acceptance_INVALID_health.{json,md}`
- Fault injection: `examples/fault_injection_health.{json,md}`

## Exact next paid-experiment commands

Guard is **inside** the runners — do not rely on a separate manual preflight.

### Independent eval (Initial / …)

```bash
cd /path/to/Video-RSI
set -a && source providers.env && set +a
export ARCH_AB_ALLOW_PAID=1 PYTHONPATH=.
# Must use production interpreter (Guard will re-exec if needed):
"$(python3 -c 'import json;print(json.load(open("evolution/run-seed42/effective_config.json"))["execution"]["python"])')" \
  research_audit/arch_self_evolution_pilot/eval_independent.py \
  --execute --concurrency 2 \
  --run-dir research_audit/arch_self_evolution_pilot/runs/phase_d_eval_guarded_v1 \
  --arms initial,direct_vqa \
  --limit 4
```

If preflight fails (wrong env / ffmpeg), the process exits **before** any arm API calls.

### Editor arms

```bash
export ARCH_AB_ALLOW_PAID=1 PYTHONPATH=.
"$(python3 -c 'import json;print(json.load(open("config.evolution.local.json"))["execution"]["python"])')" \
  research_audit/arch_self_evolution_pilot/run_editor_arms.py --execute --arm both
```

### Dry-run (no Guard paid path; no provider)

```bash
PYTHONPATH=. python3 research_audit/arch_self_evolution_pilot/eval_independent.py
PYTHONPATH=. python3 research_audit/arch_self_evolution_pilot/run_editor_arms.py --prepare-only
```

## Special answers

| Question | Answer |
|----------|--------|
| Can Phase D broken env start formal eval? | **No** — `guard.start` / preflight FAIL-closed before providers |
| Runtime detect real config change? | **Yes** — disk re-read via `live_fingerprint()` |
| Concurrent batch abort effective? | **Yes** — stops new submits; e2e showed 22/24 never submitted |
| Protocol checks PASS without params? | **No** — formal → `INCOMPLETE` |
| Safe to resume Initial vs Direct retest? | **Engineering-safe yes** on wired runner + videorsi; still need scientific protocol (reuse Direct only if fingerprint-compatible). Do not treat old Phase D harness results as valid. |

**Stopped after acceptance. No paid experiment launched.**
