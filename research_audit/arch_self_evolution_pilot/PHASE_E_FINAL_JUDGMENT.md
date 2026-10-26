# Phase E — Final Research Judgment

**Pilot branch:** `research/arch-self-evolution-pilot`  
**Baseline preflight:** `fa96c0e`  
**Conclusion (exploratory):** **INSUFFICIENT**

---

## Phase D results (n=24 independent, OBSERVED)

| Arm | Correct | Acc |
|---|---|---|
| Initial harness | 8/24 | 0.333 |
| Baseline Editor | 9/24 | 0.375 |
| Treatment Editor | 10/24 | 0.417 |
| Fixed Direct VQA | **14/24** | **0.583** |

| Contrast | Fix | Harm | Net |
|---|---|---|---|
| Baseline vs Initial | 1 | 0 | +1 |
| Treatment vs Initial | 3 | 1 | +2 |
| Treatment vs Baseline | 2 | 1 | **+1** |
| Direct VQA vs Initial | 9 | 3 | +6 |
| Treatment vs Direct VQA | 3 | 7 | **−4** |

Editor train subset / exploratory-20 / Gate excluded from this eval.  
Mean Qwen frames for harness arms often ~0 on this slice (many trajectories answered without vision calls); Direct VQA used 32 frames by construction.

---

## Answers to the five questions

1. **Can the stock Video-RSI Editor autonomously discover these architecture issues?**  
   **No evidence in this pilot.** Baseline never saw infoflow probes; its plan focused on decision-layer qualifiers / prompt / tool-cache — not vision-vs-text info-flow.

2. **Does adding counterfactual mechanism diagnosis improve discovery and editing?**  
   **Not observed.** Treatment had `infoflow_probe` available and was told it was optional; **0 probe calls**. Edit was again prompt / interval-dedup / counting `skill_policy` — not an info-flow architecture change. Independent net vs Baseline = **+1/24** (not a reliable gain).

3. **Was a new Video Agent mechanism produced, or mainly prompt rewriting?**  
   **Mostly prompt / local tool policy.** Neither arm implemented Direct VQA, answerer routing, or caption-vs-vision branching in the solver loop.

4. **Does independent video eval support a benefit?**  
   **Weak for Treatment vs Baseline; strong for fixed Direct VQA vs all Editor arms.** Mechanism-level RSI as tested did not approach the fixed-architecture ceiling on this set.

5. **Difference vs MetaVideoAgent / VideoHarness-SRSI?**  
   This pilot tested **optional, executable info-flow counterfactuals inside the existing Editor**, not MetaVideoAgent’s modular (S,L,P,W,R) rewrite loop with Teacher gold, nor SRSI’s content-free search governance. The negative result is about **whether such probes get used and yield architecture edits under matched budget** — not a refutation of those full systems.

---

## Why INSUFFICIENT (not PROMISING / PIVOT)

| Criterion | Evidence |
|---|---|
| PROMISING needs repeatable mechanism **and** diagnosis-driven effective architecture mods | Phase B mechanisms replicate, but Phase C produced **no probe use** and **no info-flow architecture edit** |
| PIVOT if fixed architecture already solves / RSI adds no value | Direct VQA clearly best here — **supports pivoting product attention** — but mechanism hypotheses remain real; the **method** (Editor+probes) failed to capitalize |
| **INSUFFICIENT** | Mechanism signal exists; **new method shows no reliable autonomous architecture gain** |

Oracle Router on the earlier n=20 was only **12 vs Direct 11** (+1), consistent with limited headroom for learned routing on that freeze.

---

## Recommended next path (if continuing research)

1. **Do not** expand mechanism-RSI rounds on Caption-bottleneck mythology without forcing/instrumenting probe use.  
2. Prefer either: (a) **fixed Direct VQA / hybrid harness** ablations with cost controls, or (b) a **mandatory warm-up probe stage** (SRSI-like) before free Editor search — only if a new protocol is explicitly scoped.  
3. Keep Placebo-Gate calibration from preflight when any Gate-based RSI resumes.

---

## Artifact map (local vs publishable)

| Publish | Local only |
|---|---|
| `PHASE_*.md`, scripts, `out/*.safe.json` | `runs/**` frames, raw calls, editor workspaces, gold-linked full reports |
