# E2 — Valid Initial vs Direct VQA (frozen diagnostic 24)

**Run:** `research_audit/arch_self_evolution_pilot/runs/valid_infoflow_retest_e1`  
**Health:** VALID · Protocol PASS · ranking usable  
**Code:** `fd45beb` · config_fp `7a1ad42dbec4b683` · harness_sha `afcedacceee8480d`  
**Caveat:** Same previously audited 24 IDs — diagnostic only, not a fresh held-out paper test set.

## Headline (architecture-comparable)

| Arm | Correct | Accuracy | Mean Qwen frames |
|-----|---------|----------|------------------|
| **Initial Harness** | **19 / 24** | **79.2%** | 51.9 |
| Direct VQA (fixed 32) | 13 / 24 | 54.2% | 32.0 |

### Pairwise (Direct relative to Initial)

| Metric | Value |
|--------|-------|
| Fix (Direct✓ Initial✗) | 1 |
| Harm (Direct✗ Initial✓) | 7 |
| Net | −6 |
| McNemar discordant (b=7, c=1) | exact two-sided **p ≈ 0.070** |

p < 0.05 is **not** met on n=24; direction favors Initial, not Direct.

### Oracle path selector

| Policy | Correct |
|--------|---------|
| Always Direct | 13 |
| Always Initial | 19 |
| Perfect choose-per-item (I∨D) | 20 |
| Extra vs always Direct | **+7** |
| Extra vs always Initial | **+1** |

Most of the “routing upside” vs Direct is already captured by Initial; little headroom above Initial.

## Resources

| | Initial | Direct |
|--|---------|--------|
| DeepSeek calls (sum) | 139 | 0 |
| Qwen calls (approx) | 89 | 24 |
| Direct estimated CNY (ledger) | — | ≈ 1.11 |
| Visual success rate (Guard, Initial) | ≈ 0.91 | n/a (fixed extract) |
| Infra INVALID_RUN | 0 | 0 |
| Same-run Direct reuse | 4 (E1) + 20 fresh | |

## By question type (I / D correct of n)

| Type | n | Initial | Direct |
|------|---|:-------:|:------:|
| entity recognition | 4 | 4 | 4 |
| temporal grounding | 4 | 3 | 3 |
| key information retrieval | 4 | 4 | 2 |
| summarization | 4 | 3 | 2 |
| reasoning | 4 | 2 | 2 |
| **event understanding** | 4 | **3** | **0** |

Largest type gap: event understanding.

## Video-level

18 videos; Initial ≥ Direct on all but one video (`vaL_vSdZKZo`: I0 D1 = the single Direct-only item `lvbench_1634`). Full table in `analysis_raw.json`.

## Engineering integrity

- Preflight PASS; no fingerprint drift  
- `--no-legacy-direct-reuse` (E1); E2 reused only same-run E1 Direct records with full timestamps  
- Did **not** write `phase_d_eval_v1` or overwrite `out/phase_d_eval.safe.json`
