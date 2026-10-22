# 02 — EM+IG forced ReObserve anomaly investigation

Audit date: 2026-10-22  
Baseline for failure pool: initial_harness @ `5ad014499a5e009b75e3ef05ac83595b78adda09`  
No code changes; no new probe API calls in this audit.

---

## Executive finding

**VERIFIED:** Frequent ReObserve under EM+IG is **not** an LLM habit. Probe selection is **deterministic Python ranking**. After the coverage legality gate, the legal action space collapses to `reobserve_probe` for **63/68** clean natural failures. Family-level synthetic IG is constant, so ranking reduces to **cost**. Logged reobserves **re-caption the same timestamps** rather than add new temporal coverage.

Official Video-RSI has **no** `reobserve_probe` tool; the Solver uses `overview` / `scan_interval` / `inspect_interval` / OCR / transcript (`tools.py` L29–38).

---

## Question-by-question

### 1. Forced by code or LLM?

**VERIFIED — code / ranking collapse.**

- Candidates built in `ig_shadow/rank_mvp12.py` `legal_candidates` (L145–153): only `coverage_candidate` and `reobserve_candidate`. Level-2 grounding excluded from the active set.
- `reobserve_candidate` (L99–117) hardcodes the **last stored visual slot**.
- `failure_em.py` documents no IG controller for EM posterior updates.
- Policy evidence: repaired MVP-12 top-1 is **12/12 reobserve** (`natural_pilot/repaired_ranking_report.md`).

### 2. Prompt / tool-description bias?

**VERIFIED** selection is not prompt-driven.  
**LIKELY** frozen reobserve vision prompts that forbid using stored text encourage redescription of the same frames (pilot prediction JSON), but they do not choose the probe.

### 3. Forced state-machine branches?

**VERIFIED — legality gates.**

- Coverage requires geometric expansion **and** task relevance (`coverage_legality` / audit narrative).
- Action-space audit: legal coverage **0/68**; rejection reasons `target_already_covered: 62`, `no_task_relevant_target: 6` (`action_space_audit/viability_report.md` L31–33).
- When coverage fails, reobserve remains legal for already-covered / unknown targets.

### 4. Evidence already sufficient but still reobserves?

**VERIFIED** for executed pilot reobserve trials (same-slot re-look with existing visual memory).  
**LIKELY** for policy top-1 on the 68: no sufficiency stop exists once a visual slot is stored.

Pilot adjudication examples (from prior artifacts / CA notes): trials with 1–4 visual slots still reobserve; outcomes include `EVIDENCE_CONFIRMED` and same-timestamp `CONTENT_REVISED`.

### 5. Can LLM bypass evidence / budget checks?

**VERIFIED for EM+IG:** there is no LLM chooser in ranking.  
**VERIFIED for natural pilot:** budget precheck dropped high-cost items before run (`pre_registered_predictions_v2.json` / `budget_precheck_v2.json` in `natural_pilot/`).  
Official Solver LLM can freely choose tools under soft prompt constraints; that path is separate from EM+IG.

### 6. New visual evidence or repeated content?

**VERIFIED — same timestamps, new caption text.**

Natural pilot v2 (`natural_pilot/v2_cost_summary.json`):

| Probe | Calls | Frames |
|---|---:|---:|
| coverage_probe | 4 | 128 |
| reobserve_probe | 4 | 40 |
| grounding_probe | 3 | 80 |
| **Total** | **11** | **248** |

Reobserve call share of executed schedule: **4/11 ≈ 36%**. Prior CA/cache notes record **7/7** reobserve+grounding evidence pairs with request timestamps == stored timestamps; text exact-match **0/7** (new Qwen text on identical stamps).

### 7. Hidden retry / fallback?

**VERIFIED:**

| Trigger | Effect | Evidence |
|---|---|---|
| Coverage illegal → reobserve legal | Fallback into reobserve family | viability_report rejection mix |
| Constant family IG | Ranking = cost | `ig_ranking_equals_cost` True for **68/68** (`natural68_actions.csv`) |
| Grounding same-slot | Labeled reobserve-like unsupported grounding | calibration eligibility CSVs |
| Budget drop | Schedule rewrite, not IG | v2 prereg |

### 8. Consistent with official Video-RSI?

**VERIFIED — inconsistent as primary novelty on initial harness.**

Recorded stop: `research_decisions/ig_active_investigation_stop.md` (legal coverage 0; 92.6% only-reobserve; stop rule fired).

---

## Log statistics (existing artifacts only)

| Metric | Value | Source |
|---|---:|---|
| Pool size | 68 | `viability_summary.json` `n` |
| Only-reobserve families | **63** (92.6%) | same + `viability_report.md` |
| ≥2 active families | **5** (7.4%) | same |
| Legal coverage candidates | **0** | `coverage_legal` / CSV `coverage_candidate_count` all 0 |
| `ig_ranking_equals_cost` | **68/68** | CSV |
| Family IG (constant) | coverage 0.246080; reobserve 0.291158 bits | `viability_summary.json` |
| OCR candidates | 6 across 5 cases | viability_report |
| API calls in action-space audit | **0** | viability_report L43 |
| Natural pilot v2 provider calls | 11 (248 frames) | `v2_cost_summary.json` |

---

## Root-cause hypotheses (ranked)

1. **VERIFIED primary:** Action-space collapse after coverage legality + synthetic family likelihood → cost-only reobserve.
2. **VERIFIED secondary:** Reobserve target = last visual slot → same-timestamp reperception by construction.
3. **LIKELY tertiary:** Vision prompt forbids adopting stored text → captions change without new frames.
4. **Rejected:** LLM unconditional ReObserve preference in EM+IG ranking (no LLM in chooser).

---

## Minimal fix proposals (do **not** implement in this audit)

1. Ban same-timestamp reobserve unless an explicit revision hypothesis is present.
2. Add a sufficiency stop when visual slots exist and no open contradiction feature.
3. Restore multi-family discrimination (relax coverage for true unobserved task regions **or** give OCR/transcript calibrated likelihoods).

### Proposed ablations (offline / small paid)

| ID | Change | Expected signal |
|---|---|---|
| A1 | Ban same-timestamp reobserve | Top-1 reobserve rate collapses; many “no legal probe” |
| A2 | Add OCR/transcript likelihood rows | Distinct IG > 1 on >0/68 |
| A3 | Geometry-only coverage (disable task-relevance) | Coverage reappears; isolates legality vs IG |
| A4 | IG-only vs IG/cost on fixed candidates | Isolates cost-tie artifact |

Stop condition already documented: do not treat this IG formulation as core novelty (`ig_active_investigation_stop.md`).
