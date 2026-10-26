# Next Experiment Decision (Design Only — Do Not Execute Here)

## Direct answers

| Question | Answer |
|---|---|
| Fix the Runner? | **Yes.** `eval_independent.py` (and Editor arm launcher) must run harness code under `config.execution.python` **or** ensure `imageio_ffmpeg` / ffmpeg resolution matches production. Add a preflight assert: one `sample_frames` smoke before any paid batch. |
| Re-run Phase D? | **Yes, after fix** — otherwise architecture rankings stay invalid. Keep old `runs/phase_d_eval_v1` immutable as a failed-condition artifact. |
| Change Probe wiring/discovery? | **Wiring OK in code; discovery weak.** After env fix: (1) smoke live `infoflow_probe` once; (2) optionally require logging whether `INVESTIGATION.md` probe section was read; (3) do **not** hard-code “must use Direct VQA.” Consider a **mandatory one-probe warm-up** only if a new protocol is explicitly scoped. |
| Worth another Editor Pilot? | **Only after** ffmpeg-healthy investigation + one forced probe smoke. Otherwise another pilot will rediscover prompt edits under blind vision. |
| Enough evidence to continue Architectural Self-Evolution now? | **Not from Phase D.** Phase B still justifies **limited** interest in info-flow mechanisms. Continuing large RSI spend **not** justified until a **valid** eval exists. |
| Smallest experiment that decides go/stop? | **E0 (below).** |

---

## Minimal decisive experiment **E0** (not run in this audit)

**Goal:** Decide whether *healthy* harnesses on the frozen 24 still lose badly to Direct VQA, and whether Treatment-with-working-vision differs from Baseline.

**Budget ceiling (suggested):**

1. Preflight: 1 video × 8 frames sample_frames under the **same** interpreter as eval (must pass).  
2. Re-eval **only Initial + Direct VQA** on frozen 24 (or 12 stratified) with videorsi Python — establish fair gap.  
3. Optional: re-eval Baseline & Treatment candidates **unchanged** under fixed env (no new Editor).  
4. **0** new Editor rounds unless (2) shows harnesses are competitive once vision works **or** gap is mechanism-shaped (B-only errors).

**Stop rules:**

- If Initial with working vision ≈ Direct VQA (±2/24): **PIVOT** away from caption/info-flow RSI.  
- If Initial ≪ Direct and errors match Phase B vision-loss pattern: **keep** mechanism line; then one **ffmpeg-healthy** Treatment vs Baseline Editor pilot with probe smoke.  
- If harnesses still cannot extract frames after “fix”: **engineering stop** — do not interpret scientifically.

**Explicit non-goals:** Round 4–20, Gate tuning on these 24, Gold-in-harness, overwriting `ff1d383` artifacts.

---

## Recommended sequencing

1. Patch eval launcher + CI assert (engineering).  
2. Offline confirm assert catches system python.  
3. E0 re-eval (paid, separate approval).  
4. Only then reconsider Editor+probe pilot or abandon Arch-SE for fixed Direct VQA / SRSI-style search work.
