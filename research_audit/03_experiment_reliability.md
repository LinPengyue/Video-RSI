# 03 — Historical experiment reliability audit

Audit date: 2026-10-22  
Grades: **A** trustworthy for stated claim · **B** partial / needs controls · **C** insufficient, re-verify · **D** missing logs / cannot judge.

Cross-cutting: almost all experiment trees were **git-untracked** at audit time. Only `research_baseline/`, `research_decisions/`, and (after this audit) `research_audit/` bind conclusions to commits. Until artifacts are selectively committed, scientific claims have **weak code-version provenance**.

This audit did **not** re-run experiments.

---

## Scorecard

| Family | Grade | Completion | Fairness / consistency risks | Provenance | Reconsider |
|---|---|---|---|---|---|
| `experiment_manifest.json` | **C** as live status | Records Phase3 round-1 reject only | Stale vs disk Round2/3 + `H_S1` | Paths only | “Stopped at round-1 reject” |
| `reproduction/` framework claim | **B** | Loop + 1 accept | Concurrency 4 vs 16; model ID strings differ; ASR empty | `runtime_manifest.json` (untracked) | Equating local Acc to paper |
| Paper trajectory / paper `H_S1` | **C/D** | Not claimed | Public setup unknowns | No paper logs | Any paper-revision identity |
| `research_screening/` FR-0 / PR-0B | **A** (negative stop) | Offline complete | Pool = MP-1 only | Untracked | Treating as positive method proof (it is not) |
| `research_autoresearch/evolvability_stage0` | **A** offline contract | 11/11 Keep/Discard, **0 API** | N/A for Acc | Untracked | Using as paid-evolution evidence |
| `research_autoresearch/exp1` GLM stack | **B** eng. / **C** science | Smokes; C0 archived | Stack ≠ DeepSeek/Qwen | Untracked | Scientific Acc claims |
| `exp1_glm53` scientific triplets | **C** | Abort / incomplete patches | Schema failures; stack mismatch | Reports exist, untracked | “Method X works/fails” Acc |
| `credit_assignment/` CA-0…CA-4 | **B** | Program closed stop | Cue confounding; small n; train failures | Prereg + jsonl untracked | Counterfactual credit as core method |
| `controlled_faults/` | **A** construction · **B/C** live efficacy | 14 cases; **0 API** build | Some fault types impossible on Memory API | Untracked | Live Investigation superiority |
| `multipatch/` MP-1 | **B** run · **C** ranking claim | 8 passes finished | Dependent patches; C3 +4→−4; same-video train | Large results untracked | Stable multipatch ranking |
| `patch_validation/` instability (SR) | **A** as instability evidence | Multi-set sign flips | Fresh UIDs but shared videos common | Untracked | Single-run patch proof |
| `patch_validation/` H_S1 win | **C** | PV-1a Pilot-20 net 0 | Not video-disjoint generalization | Untracked | H_S1 as default improved baseline |
| `natural_pilot/` | **B** | v1 infeasible; v2 11 calls; coverage_v3 not calibration-eligible | Mid-stream legality repairs | Untracked | Closed IG calibration |
| `mvp_analysis/` | **A** descriptive | Offline features | Train cache only | Untracked | Causal method claims |
| `action_space_audit/` + IG stop | **A** negative viability | 68/68 offline | Synthetic likelihood | Untracked + decision tracked | IG probe-selection novelty |
| `research_decisions/` | **A** policy | Written stops | N/A | **Tracked** | — |

---

## Local evolution facts (VERIFIED)

From `evolution/run-seed42/`:

| Round | Status | Parent correct | Candidate correct | Notes |
|---|---|---:|---:|---|
| 1 | REJECTED | 41 | 41 | `round_001/round_result.json` |
| 2 | REJECTED | 42 | 40 | |
| 3 | ACCEPTED | 43 | 47 | accuracy branch; net +4; help 10 / harm 6 |
| 4–20 | not run | — | — | `state.next_round=4`; `original_evolution_stop.md` |

`current.json`: `version=H_S1`, `generation=1`, `attempt=3`.

Split: seed 42, train 216 Q / 85 videos, gate 72 Q / 18 videos (`sampling_summary.json`).

---

## Conclusions that must be reconsidered

1. Paper reproduction of retained harness sequence / paper Acc tables.
2. Treating local `H_S1` as the default improved baseline (research baseline is `initial_harness`).
3. Single Gate accept or single paired pilot as proof of a stable patch.
4. Multipatch ranking as a fair method bake-off (dependent lineage + subset sensitivity).
5. Counterfactual credit assignment and IG active investigation as primary novelties (both stopped with evidence).
6. `experiment_manifest.json` as current experiment status (stale).
7. GLM Autoresearch scientific Acc outcomes (no completed fair triplet).
8. Any claim whose only artifacts remain untracked (cannot bind to a research commit yet).

---

## What remains trustworthy enough to build on

- **A / B with clear scope:** framework loop under local seed-42 split; video-disjoint construction; IG action-space **negative** result; patch **instability** evidence; screening stop decisions; Stage0 offline Keep/Discard; MVP descriptive census; controlled-fault construction invariants.
- Prefer **relative** comparisons on frozen `initial_harness` + recorded split hashes (`reproduction/runtime_manifest.json`) over paper-absolute claims.
