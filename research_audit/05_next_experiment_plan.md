# 05 — Minimal falsifiable next experiment + executive summary

Audit date: 2026-10-22  
Status: **plan only**. Do not execute until researcher review.

---

## Executive summary (answers to the five questions)

### 1. Is the current Video-RSI reproduction enough for trustworthy science?

**Yes for controlled relative experiments on the local seed-42 split; no for paper-absolute claims.**

Framework loop, Gate predicate, initial harness bytes, and video-disjoint construction are **VERIFIED**. Paper trajectory, exact endpoints, ASR/OCR hashes, and paper `H_S*` identity remain **UNKNOWN / not claimed** (`reproduction/REPRODUCTION_CLAIM.md`).

### 2. Main likely cause of EM+IG frequent ReObserve?

**VERIFIED:** deterministic action-space collapse (legal coverage 0/68) + constant family synthetic IG → cost-only ranking to `reobserve_probe` on the last visual slot. Not an LLM unconditional choice. Logged reobserves re-caption the same timestamps.

### 3. Which prior conclusions need reconsideration?

Paper reproduction / paper `H_S1` identity; local `H_S1` as default improved baseline; single-run Gate/patch proof; multipatch ranking as fair bake-off; IG probe-selection and counterfactual credit as primary novelties; stale `experiment_manifest.json`; GLM scientific Acc outcomes; any untracked-only artifact claims.

### 4. Can existing code support capability-level evaluation?

**Partially.** Diagnosis/Modification/Selection artifacts already exist for completed rounds and can be parsed offline. Generalization and fixed-Evolver×many-seeds need held-out protocols and new runs. No finished capability benchmark exists yet (`04_evolution_capability_readiness.md`).

### 5. What experiment should run next, and why?

**Offline-first Gate replay + same-timestamp ReObserve ablation ranking (0 API), then a tiny paid held-out Solver compare of `initial_harness` vs local `H_S1` only if offline gates pass.**  
Reason: highest information per dollar; falsifies whether local accept transfers beyond the selection set; avoids reopening stopped IG novelty; does not modify baseline code.

---

## Proposed experiment: E0 — “Accept ≠ Generalize” smoke

### Scientific hypothesis

**H0:** Under the frozen seed-42 training split, the locally accepted `H_S1` does **not** improve accuracy over `initial_harness` on a **new video-disjoint** question set that was never used for Gate selection.  
**H1:** `H_S1` improves accuracy by ≥ +Δ on that held-out set with non-increasing mean Qwen frames (or within +10% frames), mirroring Gate’s accuracy branch.

This tests whether Gate acceptance on 72 questions implies transferable harness improvement — a prerequisite for Selection/Generalization claims.

### Groups

| Arm | Harness | Eval set |
|---|---|---|
| Control | `evolution/run-seed42/versions/initial_harness` | Held-out video-disjoint set **E** |
| Treatment | `evolution/run-seed42/versions/H_S1` | Same set **E** |

No Editor / no evolution loop in E0.

### Data & video isolation

1. Start from LVBench metadata already used for seed-42.
2. Build set **E** by sampling videos from the complement of (train videos ∪ gate videos) when enough remain; if pool too small, document **UNKNOWN** and stop rather than reuse Gate videos.
3. Record `sample_id` / `video_id` set SHA256 in a new prereg JSON (do not commit videos).
4. Hard fail if any video ID intersects train or gate.

### Offline prerequisites (must pass before any paid call)

1. Recompute Gate decisions for rounds 1–3 from saved `results.json` → must match `round_result.json` (**Selection instrumentation check**).
2. Emit unified diffs `initial_harness` ↔ `H_S1` (expect `prompt.md` / `tools.py` only per prior notes).
3. Confirm harness tree SHAs and baseline commit `5ad0144…` in the prereg file.

### Resources

- CPU only for offline checks.
- Paid: 2 × |E| Solver runs (DeepSeek + Qwen as in `effective_config.json`), concurrency as local (4), **no** Editor.
- GPU: only if OCR path requires it; prefer configs already validated in prior runs.

### Cost estimate

**Only if |E| is fixed and rate card known.**  
Order-of-magnitude from prior Gate (72 Q): Round3 parent ~299 Qwen calls / candidate ~328 on Gate. Linear scaling suggests ~**(299+328)×(|E|/72)** Qwen calls plus DeepSeek agent calls.  
Exact CNY: **UNKNOWN** without current provider pricing and measured tokens — do not invent a number. Cap with a hard budget (suggested: stop if estimated > prior single Gate eval cost).

### Confounders

- Stochastic decoding despite temperature 0.
- Same provider model string drift (`DeepSeek-V4-Pro-0813` vs example).
- Empty ASR vs paper.
- Small |E| → high variance.
- If E cannot be video-disjoint, experiment is invalid.

### Results that falsify H1 / support H0

- Treatment Acc ≤ Control Acc on E, or frames inflate beyond Gate-like bounds without Acc gain.
- Any video overlap discovered post-hoc → abort, no claim.

### Success / stop rules

| Event | Action |
|---|---|
| Offline Gate replay mismatch | **Stop**; fix provenance before science |
| Cannot build video-disjoint E | **Stop**; report UNKNOWN |
| |E| < 24 questions | **Stop** or pre-declare exploratory-only |
| Paid budget / error storm | **Stop**; keep partial logs |
| Clear Acc↑ with frames OK on E | Proceed to design Selection stress tests |
| No Acc↑ on E | Treat local Gate accept as **selection-set phenomenon**; do not promote `H_S1` as improved baseline |

### Explicit non-goals

- Do not revive IG reobserve novelty.
- Do not modify baseline harness or Gate policy.
- Do not merge research branch to `main`.
- Do not run full 20-round evolution.

---

## Optional follow-on (only after E0)

**E1 (offline):** A1 same-timestamp reobserve ban on the 68-case ranking CSV — confirms expected collapse without API.  
**E2 (paid, larger):** fixed Editor config × 2–3 distinct initial harness seeds on separate run roots — only if E0 shows transferable gains or a new method needs multi-seed stress.

---

## Audit deliverable provenance

| File | Role |
|---|---|
| `research_audit/01_baseline_audit.md` | Task A |
| `research_audit/02_em_ig_reobserve.md` | Task B |
| `research_audit/03_experiment_reliability.md` | Task C |
| `research_audit/04_evolution_capability_readiness.md` | Task D |
| `research_audit/05_next_experiment_plan.md` | Plan + summary |

Baseline commit preserved: `5ad014499a5e009b75e3ef05ac83595b78adda09` on `main`.  
This audit commits reports only on `research/cvpr2027-audit`.
