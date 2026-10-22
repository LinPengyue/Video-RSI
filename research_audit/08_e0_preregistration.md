# 08 — E0 preregistration (blocked + contingent alternatives)

Date: 2026-10-22  
Status: **ORIGINAL E0 NOT AUTHORIZED TO RUN** (no LVBench held-out videos; see `07_heldout_feasibility.md`).  
This file freezes what *would* have been required, and registers contingent follow-ons that must not be confused with the original claim.

Frozen harnesses (do not edit):

| Arm | Path | tree_sha256 |
|---|---|---|
| Control | `evolution/run-seed42/versions/initial_harness` | `0805cf0e…744fe3` |
| Treatment | `evolution/run-seed42/versions/H_S1` | `6733c480…25518f` |

Upstream baseline commit: `5ad014499a5e009b75e3ef05ac83595b78adda09`.  
Public env template: `config.example.json`; local run used `effective_config.json` (`DeepSeek-V4-Pro-0813`, `Qwen3.6-Plus`, concurrency 4).

---

## A. Original E0 (LVBench video-disjoint) — BLOCKED

### Intended hypothesis (now moot on LVBench)

H1: `H_S1` raises accuracy vs `initial_harness` on a video set **disjoint from train∪gate**, with frames not exceeding the Gate accuracy-branch frame cap spirit (≤110% of control).

### Why blocked

`|train ∪ gate| = |LVBench| = 103` (**VERIFIED** in `07_`). No eligible videos.

### Explicit prohibitions

- Do not build “held-out” items on train or gate videos and call them independent-video generalization.
- Do not tune `H_S1` or pick another candidate using any new eval set.
- Do not merge research branch to `main` for this workstream.

---

## B. Contingent protocol E0-CD — cross-dataset smoke (NOT same-distribution)

Only if researchers later obtain a **public** VideoQA set with videos, questions, and labels, and complete an overlap audit vs LVBench IDs.

### Claim language (mandatory)

> Cross-dataset transfer of one locally accepted harness revision under frozen models/budgets.  
> **Not** proof of LVBench unseen-video generalization.  
> **Not** proof that the Evolver generally improves arbitrary initial harnesses.

### Design

| Item | Rule |
|---|---|
| Arms | Control `initial_harness` vs Treatment `H_S1` only |
| Models / budgets | Freeze to `effective_config.json` solver budgets; same `API_BASE` route; temperature 0 |
| Samples | Identical item list for both arms |
| Primary metric | Accuracy (answered==label) |
| Secondary | Fix/Harm/Net vs control; mean successful Qwen frames; Qwen/DeepSeek calls; tokens if metered |
| n | Pre-declare before any scored run; exploratory if n&lt;48 |
| Analysis | Paired Acc delta; report CI only if pre-declared bootstrap; no post-hoc harness picking |
| Stop | Budget cap; provider errors; discovery of LVBench video-ID overlap ⇒ abort claim |
| Small-n caveat | Feasibility / smoke only; not population inference |

### Still does **not** measure

General Evolver skill, multi-seed improvement, diagnosis quality, or selection policy quality beyond this one artifact.

---

## C. Contingent protocol E0-SV — same-video stress (optional, weaker)

Evaluate both harnesses on **held-out questions** whose videos appear in train or gate, with UID disjoint from items used in Editor analysis dumps **if** such UIDs can be listed.

### Claim language (mandatory)

> Same-video / different-question robustness. **Not** independent-video generalization.

Prior PV/SR work already shows this setting is contaminated for video-level claims (`pv0_video_exposure_audit.md`). Use only as engineering smoke, grade ≤ B.

---

## D. What this experiment can and cannot say about “self-evolution”

| Can say (if a valid protocol runs) | Cannot say |
|---|---|
| Whether **this** accepted patch transfers to a stated eval distribution | That Video-RSI Evolver is generally capable |
| Whether Gate accept on 72 Q predicted the eval outcome | That Selection policy is optimal |
| | That Diagnosis/Modification modules are correct |

### Suggested later Evolver-capability design (separate program)

1. **Fixed eval suite** with true unseen videos (cross-dataset or a larger long-video corpus).  
2. **Multiple initial harness seeds** (ablated tools/prompts), same Editor/Gate config.  
3. **Process metrics:** diagnosis citation precision; patch–plan alignment; Gate help/harm calibration.  
4. **Pre-registered stop rules** against one-off accepts (see SR instability in `03_`).

---

## Prereg decision

| Protocol | Run now? |
|---|---|
| E0 LVBench held-out | **No — impossible** |
| E0-CD | **Not now** — needs external data + overlap audit + cost approval |
| E0-SV | **Not recommended** as generalization evidence |

No paid experiment is started by this commit.
