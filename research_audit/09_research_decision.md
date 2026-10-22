# 09 — Research decision after Gate replay & held-out check

Date: 2026-10-22  
Inputs: `06_gate_replay.md`, `07_heldout_feasibility.md`, `08_e0_preregistration.md`, prior `01`–`05`.

---

## Decision 1 — Can we run original E0?

**No.**

Reason (**VERIFIED**): LVBench has 103 videos; local seed-42 train (85) ∪ gate (18) already covers all 103. There is no unused LVBench video for an independent-video test of `H_S1`.

**Do not** substitute same-video new questions and call it E0 generalization.

---

## Decision 2 — Are Round 1–3 Gate results trustworthy as local selection logs?

**Yes, as local logs.**

Reason (**VERIFIED**): raw parent/candidate predictions replay to the stored aggregates under the official Gate policy; Round 3 candidate snapshot byte-matches committed `H_S1`; parent remained `initial_harness` until accept.

Limits: Gate Acc↑ on 72 Q does **not** imply unseen-video generalization; frame ratio 1.08 shows accept was accuracy-branch, not efficiency.

---

## Decision 3 — What should be investigated next (priority order)

### P0 — Mechanism ablation design (still offline-first)

`H_S1` changes are small and explicit (`read_transcript` removal + exact-window visual cache + prompt note).  
Next scientific questions should target **causal mechanism**, not another opaque evolution round:

1. Does transcript removal alone change Acc/frames?  
2. Does cache alone change Acc/frames?  
3. Are Gate flips stable under repeated Solver seeds/temps?

These can be scoped later with paid runs **after** choosing a valid eval distribution (cross-dataset), or as **same-set** diagnostics on frozen Gate predictions already on disk (offline re-scoring only where applicable).

### P1 — Cross-dataset transfer protocol (E0-CD)

If and only if a public VideoQA corpus is obtained and video-ID overlap with LVBench is audited: run frozen Control vs `H_S1` once under `08_` rules. Label results **cross-dataset**, not LVBench held-out.

### P2 — Evolver capability program (after P0/P1)

Do **not** equate one accepted local revision with general self-evolution. A real Evolver study needs multiple seeds, held-out videos, and process metrics (`04_evolution_capability_readiness.md`).

### Explicitly deprioritized

- Reviving IG/ReObserve novelty on initial harness (`02_`, stopped).  
- Treating local `H_S1` as default improved baseline without external validation.  
- Continuing LVBench evolution rounds to chase paper trajectory (`original_evolution_stop.md`).

---

## Final recommendation to the researcher

1. **Accept** Gate replay as a verified local selection record.  
2. **Reject** original E0 as currently specified.  
3. **Hold** all paid generalization runs until a non-LVBench (or otherwise truly unused-video) eval set exists.  
4. Prefer the next *design* work to be **H_S1 mechanism ablations + eval-suite acquisition**, not another full Editor loop.

**Stop here. No paid experiment started.**
