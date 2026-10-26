# E1 Smoke — 4-item Initial vs Direct VQA connectivity

**Run dir:** `research_audit/arch_self_evolution_pilot/runs/valid_infoflow_retest_e1`  
**Branch:** `research/arch-valid-infoflow-retest`  
**Flags:** `--arms initial,direct_vqa --limit 4 --concurrency 2 --no-legacy-direct-reuse`  
**Interpreter:** videorsi (`config.execution.python`)

## Forced checks

| Check | Result |
|-------|--------|
| Preflight PASS | Yes |
| Initial visual extract / Qwen frames > 0 | Yes (8–96 frames/item) |
| Direct VQA 32 frames each | Yes |
| Both arms in Guard | `initial`, `direct_vqa` |
| Infra errors | 0 / 0 |
| Protocol PASS | Yes |
| Health VALID | Yes |
| Ranking usable | Yes |
| Frozen Phase D untouched | Yes (`out/phase_d_eval.safe.json` unchanged) |
| Legacy Direct reuse | `reused=0`, `fresh=4` |

## Engineering note (not a research claim)

On these 4 IDs both arms scored 2/4 (50%). Fix/harm vs Initial for Direct: fix=1, harm=1. **No scientific conclusion from n=4.**

## Cost / usage (desensitized)

- Direct: 4×32 frames, fresh Qwen calls, reuse aborted=false  
- Initial: mean qwen_frames=46.0 (adaptive)  
- See `runs/valid_infoflow_retest_e1/phase_d_eval.safe.json` and `experiment_guard/`

**Proceed to E2 (full 24) under identical protocol.**
