# Info-Flow Mechanism Experiment Report (Exploratory)

**Protocol:** `infoflow_mechanism_ab_v1`  
**Branch:** `research/arch-evolution-min-preflight`  
**Frozen samples:** `exploratory_samples_n20.json` (unchanged; Gate leakage = 0)  
**Local run:** `runs/infoflow_v1/` (not pushed: frames, raw text, gold-linked correctness files)  
**Editor / RSI / Gate / Round 4–20:** not run  

Epistemic tags: **OBSERVED** / **SUPPORTED HYPOTHESIS** / **UNKNOWN** / **COUNTEREVIDENCE**.

---

## Setup (OBSERVED)

| Item | Value |
|---|---|
| Models | DeepSeek-V4-Pro-0813 / Qwen3.6-Plus, temperature=0 |
| Prompt | `infoflow_vqa_letter_json_v1` (JSON `{"type":"answer","answer":LETTER}`) |
| Frames | Overview timestamps from train cache; ffmpeg re-extract; shared `frame_bundle_sha` |
| Paths | A-reuse (cache text→DeepSeek); B-direct (frames→Qwen VQA); diag: A-strict (fresh caption→DeepSeek), C (same caption→Qwen text) |
| Connectivity IDs (seed 20261027) | `lvbench_1344`, `3097`, `3523`, `3629` — all parse/save OK |
| First-batch calls | 20 Qwen Direct + 20 DeepSeek A-reuse + 0 Editor |
| Diag calls (separate budget) | 8 caption + 8 DeepSeek A-strict + 8 Qwen C-text |

Offline gates before paid calls: mock provider, answer parse, billing, resume, Gate leak — all PASS.

**Caveat:** A-reuse is a **cheap exploratory** control (historical caption text), **not** byte-matched to the new frame bundle.

---

## First-batch A/B results (n=20, exploratory)

| Metric | A-reuse | B-direct |
|---|---|---|
| Correct | **8 / 20** | **11 / 20** |
| Accuracy | 0.40 | 0.55 |
| Wilson 95% CI | see `out/ab_summary.safe.json` | |

| Contingency | Count |
|---|---|
| Both correct | 7 |
| A-only correct | **1** |
| B-only correct | **4** |
| Both wrong | 8 |

McNemar (exact, exploratory): discordant=5 (a_only=1, b_only=4), **p≈0.375** — **not** statistically significant. Do not claim a proven architecture win from n=20.

Estimated first-batch API cost ≈ **1.08 CNY** (A≈0.15, B≈0.93).

Background only (not mixed into A/B): original multi-step Solver traj on these IDs was stratified 10/10 correct/wrong in the freeze — different protocol (multi-tool), not comparable as a third arm.

---

## Diagnosis on disagreements (≤8; OBSERVED)

Selected (priority: correctness disagree, then letter disagree; fixed seed fill):  
`1567, 2886, 2984, 3472, 3523, 38, 4799, 531`.

Mechanism-linked cases:

| Sample | Pattern | Mechanism reading |
|---|---|---|
| `2886`, `3523` | B✓; A-reuse✗; A-strict✗ & C✗ (same fresh caption) | **SUPPORTED HYPOTHESIS:** visual evidence retained by Direct VQA is lost in captioning (vision→text bottleneck). |
| `531` | B✓; A-reuse✗; A-strict✗; **C✓** on same fresh caption | **SUPPORTED HYPOTHESIS:** answerer identity / option mapping (Qwen text succeeds where DeepSeek fails on identical caption). |
| `3472` | B✓; A-reuse✗; **A-strict✓ & C✓** | Cached overview text was the weak link; fresh caption recovers DeepSeek — **caption quality / staleness**, not “must use Direct VQA”. |
| `2984` | A-reuse✓; B✗ (only A-only case); C✓ A-strict✗ | Complement exists; DeepSeek vs Qwen on fresh caption diverge — mixed evidence. |
| `38` | AB both✗; A-strict✓ C✗ | Answerer difference on same caption without B win. |

Diag cost (separate) ≈ **1.27 CNY** (dominated by 8×32-frame caption calls).

No further video expansion; stability repeats not run (mechanism cases already identifiable; still **exploratory**).

---

## Go / Stop (updated rules)

**Decision: GO (exploratory)** — worth further Architectural Self-Evolution research focused on **info-flow / answerer routing**, not a paper claim.

Reasons:

- Meaningful A/B gap and complement (Δ=+3; 4 B-only vs 1 A-only).  
- Strict controls still support **at least two** distinct mechanisms: caption information loss vs answerer-on-text.  
- Differences link to concrete pipeline stages (perception compression vs final reasoning), which an Evolver could target.

Not PIVOT: Direct VQA is better on average but **not** uniformly dominant (A-only + caption-recoverable cases remain).  
Not STOP: advantage does not vanish under A-strict/C on the critical B-only vision-loss cases.

---

## Answers to the six research questions

### 1. Is Direct VQA really better than Caption→DeepSeek?

**OBSERVED (exploratory):** On this frozen 20, B-direct 11/20 vs A-reuse 8/20. Direction favors Direct VQA; McNemar non-significant. A-reuse is not a strict matched-bytes baseline.

### 2. Is the gain from visual retention or different answerer?

**Both appear (OBSERVED in diag):**

- Vision retention: `2886`, `3523` — neither DeepSeek nor Qwen-text recovers after captioning.  
- Answerer identity: `531` (and partly `2984`/`38`) — same caption, Qwen vs DeepSeek disagree.  
- Caption refresh: `3472` — fresh caption restores DeepSeek.

### 3. Do different mechanisms specialize by question?

**Weak / UNKNOWN at n=20.** B-only hits KIR, entity, summarization, temporal; the sole A-only is event understanding. Too few discords to claim type-level specialization.

### 4. Which limitations could a Video Agent autonomously recognize?

**SUPPORTED HYPOTHESIS (from prior audit + this experiment):**

- Empty/weak ASR and sparse overview (prior fix-path audit).  
- **Caption bottleneck** when Direct VQA succeeds but text paths fail on the same timestamps.  
- **Answerer mismatch** when Qwen-text and DeepSeek diverge on identical captions.

**UNKNOWN:** whether the current Editor, given only content-free Gate scores, would surface these without mechanism-tagged probes.

### 5. If we introduce an Evolver, what should it change?

Minimal, evidence-tied targets (not a full new stack):

1. **Info-flow policy:** allow/route **Direct VQA** (or late fusion) when caption-conditioned answers are low-confidence / unstable.  
2. **Caption objective:** train/edit overview prompts toward **VQA-usable** descriptions (timestamped, option-relevant), not generic scene dumps.  
3. **Answerer routing:** optional Qwen-text vs DeepSeek adjudication on the **same** caption when they disagree.  
4. **Gate hygiene:** placebo-calibrate accepts (net≤2 on same code is non-evidence).

Do **not** start with a Historical Mechanism Library or Round 4–20 expansion from this alone.

### 6. If results had not supported Architectural Self-Evolution?

Fallback path (for completeness; **not** selected here): treat Direct VQA / stronger fixed harness as the primary research object (VidHarness-style budgeted harness design) and use self-evolution only for cost/search governance (SRSI-style), not caption-bottleneck mythology.

---

## Overlap reminder (method, not score chase)

| Work | Relation |
|---|---|
| MetaVideoAgent | Assumes perception tools as observation providers; we stress-tested that assumption with matched-frame Direct VQA. |
| VideoHarness-SRSI | Addresses noisy validation; our Placebo Gate + small-n caution align, but this run is a **mechanism probe**, not SRSI search. |
| VidHarness | Budgeted harness evolution; we did not MCTS-evolve — we isolated **who answers** under identical frames. |

---

## Reproducibility

```bash
# Offline tests (no API)
PYTHONPATH=. python3 research_audit/arch_evolution_min_preflight/test_ab_infoflow_offline.py

# Paid (requires providers.env + ARCH_AB_ALLOW_PAID=1)
set -a && source providers.env && set +a
export ARCH_AB_ALLOW_PAID=1 PYTHONPATH=.
python3 research_audit/arch_evolution_min_preflight/ab_infoflow_runner.py --phase connectivity --provider http --execute
python3 research_audit/arch_evolution_min_preflight/ab_infoflow_runner.py --phase full_ab --provider http --execute
python3 research_audit/arch_evolution_min_preflight/ab_infoflow_runner.py --phase diagnose --provider http --execute

# Regenerate safe stats from local run
python3 research_audit/arch_evolution_min_preflight/analyze_ab_results.py
```

Resume is default: successful calls are not repeated.

---

## Stop line

Experiment complete for this scope. **Do not** auto-start RSI rounds, Editor evolution, or larger video expansions from this report alone.
