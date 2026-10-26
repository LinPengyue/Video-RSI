# CVPR2027 Preflight: Video Agent Architectural Evolution (Offline)

**Protocol:** `arch_evolution_min_preflight_v1`  
**Run artifact:** `evolution/run-seed42` (read-only)  
**Paid API calls this preflight:** **0**  
**Rounds 4–20:** not started  
**Evolution artifacts:** not modified  

Epistemic tags: **OBSERVED** / **SUPPORTED HYPOTHESIS** / **UNKNOWN** / **COUNTEREVIDENCE**.

---

## Executive answers (five questions)

| # | Question | Verdict |
|---|---|---|
| 1 | Same-Code Placebo Gate real? | **Yes (OBSERVED).** 3/6 directed parent-vs-parent pairs would be `ACCEPTED` by original `gate_decision()`. |
| 2 | Minimal info-flow A/B reliably implementable? | **Yes with external runner + ffmpeg** (OBSERVED ABI). Fair A/B **not** recoverable from logs alone for Path B. |
| 3 | What historical observation reuse cuts API? | Train-cache overview **timestamps + nonempty perception text** (216 items); reuse text for Path-A DeepSeek without new Qwen. |
| 4 | After 16–24 samples, continue or stop? | See go/stop criteria below. |
| 5 | If experiment holds, novelty vs prior work? | Info-flow **answerer identity** ablation under identical frames + placebo-Gate methodology; not full RSI search. |

---

## Task 1 — Same-Code Placebo Gate

### Setup consistency (OBSERVED)

| Check | Result |
|---|---|
| Phase `parent` R1–R3 | all `initial_harness` |
| Harness tree SHA256 | `0805cf0e…744fe3` (versions/initial_harness) |
| vs `solver_full_workspace` INITIAL_FILES | identical hashes |
| Config fingerprint | `51b499c9…2d2eaa3` |
| Models | DeepSeek-V4-Pro-0813 / Qwen3.6-Plus, `temperature=0`, concurrency=4 |
| Gate n | 72; all three parents `status=answered` for all items |
| Sample ID set | identical across R1–R3 parents and `gate_oracle` |

### Parent accuracy (OBSERVED)

| Round | Correct / 72 |
|---|---|
| 1 | 41 |
| 2 | 42 |
| 3 | 43 |

Same code → +2 absolute points across re-evals.

### Six directed `gate_decision()` outcomes (OBSERVED)

Using original `solver_full_workspace.engine.evolve.gate_decision` (accuracy: `cn>pn` and frames ≤110%; efficiency not triggered here).

| Parent → Candidate | Accept? | Branch | Net | Frame ratio |
|---|---|---|---|---|
| R1 → R2 | **ACCEPT** | accuracy | +1 | 0.962 |
| R1 → R3 | **ACCEPT** | accuracy | +2 | 0.965 |
| R2 → R1 | reject | — | −1 | 1.039 |
| R2 → R3 | **ACCEPT** | accuracy | +1 | 1.003 |
| R3 → R1 | reject | — | −2 | 1.036 |
| R3 → R2 | reject | — | −1 | 0.997 |

**False accepts if treated as “code change”:** 3/6 directed pairs.  
**Do not** treat 3/6 as i.i.d. Bernoulli (shared three noisy evals).

**Interpretation:** Any Gate accept with `|Δacc|≤2/72` and frames within ~10% is **indistinguishable from same-code re-eval** on this run. R3’s parent climb 41→43 alone would accept R2→R3 and R1→R3 without any harness edit.

### Answer / frame / error sources (OBSERVED)

| Signal | Value |
|---|---|
| Items with answer disagreement across ≥2 of 3 parents | **28 / 72 (38.9%)** |
| Pairwise answer mismatches | R1–R2: 19; R1–R3: 20; R2–R3: 19 |
| Typical flip structure | ~8–9 right↔wrong each direction; 2–4 both-wrong letter changes |
| Mean per-item qwen_frames spread (max−min over 3) | **16.8** frames |
| Max per-item frame spread | 64 |
| Provider error event sums | R1:12, R2:13, R3:10 |
| Engineering / invalid answers | **0** (all answered) |

**SUPPORTED HYPOTHESIS** for noise: provider nondeterminism at T=0 + tool-path branching when perception text differs + retry-induced trajectory divergence (frame counts move with tool sequences).

**Not claimed:** that Gate is useless—only that **raw accuracy_gain with soft frame bound is placebo-vulnerable** at this noise scale.

Artifacts: `out/placebo_gate.safe.json`, `out/placebo_noise_detail.safe.json`.

---

## Task 2 — Info-flow replacement feasibility

### Frozen service ABI (OBSERVED)

`Services.call` allows:

- `qwen`: `{frames, prompt}` only  
- `deepseek`: `{messages}`  
- `sample_frames` / `ocr` as today  

No ABI change required for either path. An **external** A/B runner can call the same providers (or wrap `Services`) without editing harness `Services` signature.

### Path A — frames → Qwen describe → DeepSeek answer

| Aspect | Status |
|---|---|
| Feasible without ABI change | **Yes** |
| Reuse cached overview perception text | **Yes** (216/216 train cache items; frozen 20 all nonempty overview) |
| Identical frames vs Path B | Timestamps+ids in cache; **JPEG bytes absent** → re-extract via ffmpeg from `video_path` + timestamps |
| Caveat | Historical DeepSeek answers used **multi-step memory**, not single overview text; log DeepSeek ≠ Path A replicate |

### Path B — same frames → Qwen direct VQA

| Aspect | Status |
|---|---|
| Feasible without ABI change | **Yes** (prompt can request option letter) |
| In historical Solver traces | **No** — never run; must new-call |
| Parse risk | Free-form / refuse → fail closed as invalid |

### Fairness requirements

1. Extract overview timestamps **once** per sample; build one frame bundle.  
2. Path B: Qwen(VQA prompt, frames).  
3. Path A options:  
   - **A-reuse (cheap):** DeepSeek(question + cached overview text) — matched on timestamps conceptually but **not** on a fresh Qwen describe call.  
   - **A-strict:** new Qwen(describe) on same frames + DeepSeek — doubles Qwen budget (would exceed 24 unless N reduced).  

**Recommended first batch:** Path B new Qwen + Path A-reuse DeepSeek (≤20+20 calls), optionally note A-strict as follow-up requiring extra Qwen.

### Cannot fairly compare from logs alone

- Path B never logged.  
- No JPEG bytes.  
- Cached DeepSeek conditioned on full tool memory.  
- Stochastic one-shot history ≠ fixed replicate.

Artifact: `out/infoflow_feasibility.safe.json`.

---

## Task 3 — Frozen exploratory samples (n=20)

**File:** `exploratory_samples_n20.json`  
**Seed:** `20261026` (fixed before any new API)  
**Source:** train_items only  
**Gate leakage:** 0 selected IDs in gate_oracle  

| Property | Value |
|---|---|
| n | 20 (within 16–24) |
| traj correct / wrong on initial cache | 10 / 10 |
| unique videos | **20** (video-disjoint) |
| All videos present on disk | yes |
| Overview timestamps + nonempty perception | 20/20 |
| Types | event 4, KIR 5, summarization 3, reasoning 3, entity 3, temporal 2 |

Selection does **not** use expected A/B winners—only cache recoverability, strata, video de-dup.

**Blocked pool reasons (population):** missing video 0; not in cache 0; no nonempty perception counted in script; qwen_frames>160 filtered from eligibility.

**Hard rule:** private Gate cohort is **not** a development set for new methods.

---

## Task 4 — Minimal A/B protocol (design only; do not auto-run)

### Budget ceiling (first batch)

| Call type | Max | Planned for n=20 |
|---|---|---|
| Qwen Direct VQA | ≤24 | 20 |
| DeepSeek control (Path A-reuse) | ≤24 | 20 |
| Editor / RSI | **0** | 0 |
| Extra Qwen describe (A-strict) | not auto | would need +20 → reduce N or defer |

Artifact: `out/api_call_plan.safe.json`  
Script skeleton: `ab_infoflow_runner.py` (`--dry-run` default; refuses paid calls unless `--execute` **and** explicit env flag).

### Protocol steps

1. **Input consistency:** for each frozen ID, load overview timestamps from train cache; ffmpeg-extract; hash frame paths; assert identical bundle fed to A and B.  
2. **Randomness:** provider T=0; still run **2 repeats** on a 4-sample subset if first batch is ambiguous (counts against budget → reduce N). Primary analysis uses first replicate.  
3. **Logging:** answer letter, parse_ok, error_type, n_frames, prompt/completion tokens, CNY via existing MaaS rates, path id, frame_bundle_sha.  
4. **Complementarity:** McNemar / contingency of (A correct, B correct); list A∧¬B vs B∧¬A with question_type; do **not** pool with Gate.  
5. **Pass / stop:** see below.  
6. **No Editor.**

### Go / stop after 16–24 samples

**Continue** mechanism-level self-evolution research if **≥2** of:

- **G1:** Path B accuracy − Path A ≥ +3 absolute on n=20 **and** McNemar two-sided p&lt;0.1 (exploratory; not publication claim).  
- **G2:** Nonempty complementarity: ≥3 samples where exactly one of A/B correct, spanning ≥2 question_types.  
- **G3:** Path B does not systematically explode frames (same overview 32-frame bundle by construction).

**Stop / pivot** if **any**:

- **S1:** |Δacc| ≤ 1 and complementarity &lt; 2 (no actionable info-flow signal).  
- **S2:** Path B invalid/parse rate &gt; 25%.  
- **S3:** Re-extract or video IO failure rate &gt; 10% (infra, not science).  
- **S4:** Any accidental Gate-ID contamination in runner (hard abort).

**Placebo implication for future RSI:** treat Gate accepts with net ≤2 as **non-evidence** of architectural progress unless multi-seed parent-fixed or placebo-calibrated threshold.

---

## Related work — most direct overlaps

| System | Overlap | Distinct claim if our A/B holds |
|---|---|---|
| **MetaVideoAgent** ([arXiv:2608.04587](https://arxiv.org/abs/2608.04587)) | Modular video-agent evolution; Teacher/Diagnosis/Evolution; perception tools as **observation providers**, reasoning module answers. | We **challenge the observation-only perception assumption** with matched-frame Qwen-direct VQA vs describe→LLM, without Teacher gold/evidence intervals or full module rewrite loop. |
| **VideoHarness-SRSI** ([arXiv:2610.19424](https://arxiv.org/abs/2610.19424)) | Documents validation overfitting / noisy feedback; content-free proposer; warm-up mechanism ablations. | Our **Same-Code Placebo Gate** is concrete evidence of accept-on-noise for accuracy gates; our experiment is a **single info-flow mechanism probe**, not SRSI’s multi-stage search governance. Complementary, not a reimplementation. |
| **VidHarness** ([arXiv:2609.38413](https://arxiv.org/html/2609.38413)) | Evolves harnesses under frame budgets via MCTS + multi-fidelity validation; mixture-of-harness by budget. | We do **not** propose MCTS evolution or budget routing; we isolate **who answers** (VLM vs LLM-on-captions) under **identical** frames and **zero Editor** calls. |

**Minimal realizable method (only if go criteria met):**  
*Mechanism-tagged info-flow swap* — frozen frames, replace “Qwen→text→DeepSeek” with “Qwen→letter”, log cost/frames, use placebo-calibrated gates for any later RSI. Novelty is the **diagnosed architectural bottleneck** (answerer identity / evidence-use vs acquisition), not another full self-evolution stack.

---

## Deliverables map

| Path | Role |
|---|---|
| `PREFLIGHT_REPORT.md` | This report |
| `analyze_placebo_and_feasibility.py` | Offline placebo + sample freeze + feasibility |
| `exploratory_samples_n20.json` | Fixed sample list |
| `ab_infoflow_runner.py` | A/B design + dry-run harness (no auto paid) |
| `out/*.safe.json` | Desensitized numeric artifacts |
| `README.md` | Push / hygiene notes |

---

## Stop line

Preflight complete. **Do not** start paid A/B, Editor, or Round 4–20 from this document alone.
