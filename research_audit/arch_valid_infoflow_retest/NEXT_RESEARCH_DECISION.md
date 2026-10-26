# Next research decision (after valid retest)

## Answers to the five questions

### 1. After env repair, is there still a clear Initial vs Direct gap?

**Yes, but reversed from the broken Phase D story.**  
On the diagnostic 24: Initial **79.2%** vs Direct **54.2%**; Direct fix/harm vs Initial = **1 / 7** (McNemar exact p≈**0.07**).  
Label: **ARCHITECTURAL GAP OBSERVED** (direction: Initial > Direct), with **INSUFFICIENT EVIDENCE** for p<0.05 significance and for generalization beyond this audited set.

### 2. What observable info-flow failure pattern?

- Not “Initial cannot see video” (that was engineering).  
- Main pattern: **fixed 32-frame Direct loses where adaptive Initial search + DeepSeek succeeds** (esp. event understanding).  
- Minor: one case Initial gathers vision but answers wrong while Direct is right (answerer / decision error).  
- Shared hard misses: 4 both-wrong.

### 3. Worth mechanism-level self-evolution Editor?

**Not toward “evolve into Direct VQA.”** That target is **weaker** than Initial here.  

Possible remaining Editor motivations (weaker / different):

- Reduce both-wrong (4/24) via better temporal localization or verification.  
- Fix rare answerer misuse when evidence exists (1/24).  
- Cost control (Initial uses more frames/calls than Direct) — engineering/econ, not accuracy vs Direct.

### 4. Re-open Mechanism-Aware Editor Pilot?

**No — not as previously framed (Treatment ≈ push toward Direct / infoflow swap).**  
Prior Phase D ranking was **INVALID**; refreshed evidence **does not** support that research bet.

If Editor work resumes, re-freeze a **new video-disjoint** eval, redefine the mechanism hypothesis **away from Direct-superiority**, and keep Guard mandatory.

### 5. Is fixed Direct “good enough” so we should pivot the research question?

Direct is **competitive on some types** (entity, temporal) but **not** overall stronger here.  
**Pivot recommendation:** treat “RSI to recover Direct-like answering” as a **dead end on this diagnostic evidence**. Prefer either:

- **PIVOT** research question toward failures Initial still shares with Direct (both-wrong / grounding), or  
- Study **efficiency** (when few-frame Direct matches Initial) without claiming Direct accuracy dominance.

## Decision code

| Code | Apply? |
|------|--------|
| ENGINEERING PASS | Yes (Guard VALID, vision healthy) |
| ARCHITECTURAL GAP OBSERVED | Yes (Initial > Direct on this set) |
| INSUFFICIENT EVIDENCE | Yes (n=24 audited set; McNemar p≈0.07) |
| PIVOT | **Yes** away from Editor→Direct-VQA RSI thesis |

## Do not

- Restart Editor Round 4–20 on the old Treatment hypothesis  
- Use Private Gate to tune on this 24  
- Overwrite Phase D archives  
- Publish these 24 as untouched generalization
