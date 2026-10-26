# Historical harness comparison (R1–R3)

**Source of truth:** `evolution/run-seed42/rounds/round_00{1,2,3}/` (`phase.json`, `round_result.json`, `private_gate/*/results.json`, `candidate_snapshot/`, `workspace/analysis/edit_{plan,summary}.md`).  
**Recomputed offline:** `out/audit_summary.safe.json` via `analyze_fix_paths_offline.py`.

---

## 1. Gate table — verified

| Round | Parent→Cand correct | Fix / Harm / Net | Gate | `phase.json` parent |
|---|---|---|---|---|
| R1 | 41→41 | 6 / 6 / 0 | REJECTED | `initial_harness` |
| R2 | 42→40 | 8 / 10 / −2 | REJECTED | `initial_harness` |
| R3 | 43→47 | 10 / 6 / +4 | ACCEPTED → `H_S1` | `initial_harness` |

Logged counts match recomputation from oracle + results JSON (**OBSERVED**).

### Why parent correct moves 41→42→43 if R1/R2 rejected?

**OBSERVED:** Every round’s parent is still `initial_harness` (never promoted).  
**OBSERVED:** Same parent harness, three independent Gate evals; answer disagreements:

| Pair | #samples with different parent answers (n=72) |
|---|---:|
| R1 vs R2 | 19 |
| R2 vs R3 | 19 |
| R1 vs R3 | 20 |

Always-correct across 3 evals / always-wrong: see `audit_summary.safe.json` → `parent_reeval_stability`.

**SUPPORTED HYPOTHESIS:** Parent score drift is **Solver stochastic re-evaluation**, not harness lineage progress.  
**UNKNOWN:** Temperature/seeds of those three runs (not re-derived here beyond effective_config defaults).  
**Implication:** Do **not** treat “parent got better” as evidence of transfer from rejected candidates.

Also **OBSERVED:** R1 candidate **harmed** `lvbench_4195` and `lvbench_5093` (parent right → cand wrong), while R3 later “fixed” them under a **different parent draw** where parent was wrong. That is compatible with noise + different candidates, not a clean recovered skill narrative.

---

## 2. Fix / Harm set overlap

| Metric | Value |
|---|---:|
| Jaccard Fix(R1,R2) | **0.00** |
| Jaccard Fix(R1,R3) | **0.067** (1 shared) |
| Jaccard Fix(R2,R3) | **0.125** (2 shared) |
| Fix ∩ all three rounds | **∅** |
| Fix in R1∪R2 but not R3 | **11** samples |
| Fix only R1 | 5 |
| Fix only R2 | 6 |

**OBSERVED:** Rejected rounds’ successful flips barely overlap R3’s flips.  
**OBSERVED (type-1 only):** There exist samples that a rejected candidate got right (relative to that round’s parent) which R3 did not flip.  

**Not allowed leap:** unique fix IDs ⇒ portable mechanisms (needs shared behavior + code attribution under controlled parent).

Shared Fix(R1,R3) includes `lvbench_2480` (overview-only failure → deeper inspect path under different candidates).

---

## 3. What each rejected/accepted candidate actually changed

Compared to `versions/initial_harness` (file SHA):

| Round | Changed files | Gate | Dominant intended mechanisms (from plan/summary) |
|---|---|---|---|
| R1 | `tools.py`, `skill_policy.py`, `prompt.md` | Reject | denser short-window inspect; OCR skill; ASR unavailable cache; failure-retry prompt |
| R2 | `tools.py`, `skill_policy.py`, `prompt.md`, `time_utils.py`, `agent.py` | Reject | ordinal/attribute occurrence localization skill; overview enumeration prompt; ordinal refs in agent payload |
| R3 | `tools.py`, `prompt.md` | Accept | **remove** `read_transcript` from tool list; exact-window visual cache + prompt note |

### Mechanism taxonomy (primary)

| Round | Tool/Perception | Evidence repr. | Memory | Reasoning/Control | Model role / info flow | Prompt-only | Eng/Cache |
|---|---|---|---|---|---|---|---|
| R1 | Yes (inspect density, ASR cache) | Minor | No | Prompt failure policy | OCR conditional skill | Yes | ASR cache |
| R2 | Yes (overview prompt when ordinal) | Yes (enumerate occurrences) | No | Skill + agent payload | **Yes** (`agent.py` exposes ordinal refs) | Yes | Kept some R1 ideas optionally |
| R3 | Yes (drop ASR tool) | Cache returns prior obs | No | Prompt reused-window note | No | Yes | Visual cache |

**OBSERVED:** R2 is the **most architecture-adjacent** of the three (new detector, agent payload field, overview prompt branching). It still **failed Gate** (−2 net, +frames).  
**OBSERVED:** Accepted R3 is a **narrow tool-menu + cache** change, not a new cognitive module.

**UNKNOWN:** Whether R1’s denser inspect or R2’s occurrence skill would help under paired ablations with fixed seeds. Gate reject ≠ proof of zero local value.

---

## 4. Potential value of rejected harnesses

| Claim level | Statement |
|---|---|
| **OBSERVED** | R1/R2 snapshots exist; they fix different sample sets than R3; R2 edits `agent.py`/`time_utils.py`. |
| **SUPPORTED HYPOTHESIS** | R1 OCR routing and R2 occurrence enumeration target failure modes R3 did not implement. |
| **UNKNOWN** | Net positive transfer if composed with H_S1; interaction with frame budget. |
| **COUNTEREVIDENCE (to “R2 architecture necessarily helps”)** | On this Gate draw, R2 reduced accuracy and raised frames. |

**Historical Mechanism Library — readiness**

| Needed evidence | Status |
|---|---|
| Stable mechanism IDs with code diffs | Partial (plans/summaries exist) |
| Paired ablations isolating each mechanism | Missing |
| Parent-fixed multi-seed Gate | Missing (parent already unstable) |
| Cross-round complementary wins beyond noise | Weak (low Jaccard; parent noise high) |

**Verdict:** Logs **motivate** a library research program but **do not yet support** claiming reusable mechanisms with measured uplift.

---

## 5. Practical boundaries for reuse claims

1. Treat each Gate parent eval as a **noisy baseline**, not a fixed oracle trajectory.  
2. A sample in `fix_only_r2` is **not** a license to merge R2 patches into H_S1 without new controlled eval.  
3. Architecture-adjacent edits (R2) can fail Gate; local tool edits (R3) can pass—**selection ≠ capability taxonomy**.
