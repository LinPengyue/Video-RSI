# 04 — Self-evolution capability evaluation readiness

Audit date: 2026-10-22  
Question: Can the **existing** codebase and logs support Diagnosis / Modification / Selection / Generalization evaluation **without** rebuilding a full system?

No new benchmark was implemented in this audit.

---

## Capability matrix

| Capability | Already supported | Missing interfaces | Need instrumentation? | Need API/GPU? | Minimal verification | Risks |
|---|---|---|---|---|---|---|
| **Diagnosis** | Train trajectories in `training_cache/*/results.json` and per-item dumps; Editor `analysis.md`, `notes.md`, investigation `request_*.json` under each round; Gate parent/candidate item JSON with tool traces | No standardized “diagnosis correctness” label schema; no automatic map from analysis claims → failure causal class | Light: export schema linking `sample_id` → trajectory → analysis citations | Offline scoring possible; paid only if new investigations | Sample 20 failures: human/LLM-judge whether analysis cites actual trajectory evidence | Analysis text may be post-hoc; investigation optional |
| **Modification** | Per-round `candidate_snapshot/` vs parent version; `edit_plan.md` / `edit_summary.md`; edit protocol jsonl; committed `versions/H_S*` | No structured patch AST / file-diff index committed; hard to auto-classify edit type | Light: `diff -u` initial↔candidate per round into JSONL | Offline | Diff round_003 `prompt.md`/`tools.py` vs `initial_harness` | Editor may rewrite beyond plan; plan≠edit |
| **Selection** | `gate_decision` outputs in `round_result.json` / `gate_aggregate.json`; accept/reject + help/harm/net/frames; lineage feedback JSON | No oracle of “beneficial vs harmful” beyond Gate aggregate; Gate sees **only** Gate-set metrics (`gate_feedback` aggregate-only policy) | Optional: store paired item-level flips CSV | Uses existing Gate dumps first (offline). New accepts need full Gate eval (paid) | Replay Gate predicate on saved parent/candidate `results.json` | Gate gaming; stochastic Solver variance; incomplete rounds |
| **Generalization** | `run_batch.py` + any saved version under `versions/`; video-disjoint Gate set; UID screens in patch_validation | No frozen held-out **video-disjoint** suite beyond Gate; Gate used for selection ⇒ not pure generalization if selected on it | Medium: define eval-only split never used for Gate/accept | Paid Solver runs on frozen candidates | Score `initial_harness` vs `H_S1` on a **new** video-disjoint slice never used in `run-seed42` Gate | Same-video leakage (SR audits); selecting then testing on Gate |

---

## Fixed Evolver × varying Initial Harness

| Question | Status | Evidence |
|---|---|---|
| Can Editor start from a chosen seed harness directory? | **VERIFIED yes** | `cli init --seed <dir>` copies seed into `versions/initial_harness` (`evolve.py` initialize) |
| Can the same Editor/Gate protocol evaluate multiple seeds? | **LIKELY yes** with separate run roots | Engine is seed-agnostic; needs separate `evolution/run-*` trees |
| Existing multi-seed experiment? | **UNKNOWN / not found as completed matrix** | Multipatch varies **candidates** from one lineage more than independent initial harnesses |
| Gap | Need a registry of seed harness SHAs + identical split/budgets | Without pins, seed×evolver interactions confound |

**Minimum interface gap:** a manifest listing `{seed_id, harness_tree_sha256, evolver_config_sha, split_sha, run_root}` — not present as a first-class object today.

---

## What can be evaluated offline today (0 new API)

1. **Selection predicate fidelity:** recompute `gate_decision` from saved round parent/candidate results (large JSON already on disk).
2. **Modification extractability:** unified diffs for accepted/rejected candidates in rounds 1–3.
3. **Diagnosis extractability:** parse `analysis.md` + investigation requests for round 3 (and 1–2).
4. **IG ReObserve degeneracy:** already offline-complete (`action_space_audit/`).

## What requires paid / GPU

1. New Solver evals of frozen harnesses on a fresh video-disjoint set.
2. New Editor rounds from alternate initial harnesses.
3. Any live Investigation re-probe beyond existing pilot caches.

---

## Readiness verdict

| Capability | Ready for offline metric scaffolding? | Ready for scientific claim without new runs? |
|---|---|---|
| Diagnosis | **Yes** (extract) | **No** (no gold diagnoses) |
| Modification | **Yes** (diff) | **Partial** (can describe what changed; not whether change was “right”) |
| Selection | **Yes** (Gate logs) | **Partial** (can audit Gate behavior; not general beneficial selection) |
| Generalization | **Partial** (runner exists) | **No** without a held-out video-disjoint protocol |
| Fixed Evolver × many seeds | **Partial** (CLI supports) | **No** (matrix not run) |

Overall: the repository **can support capability-level instrumentation** with mostly offline parsers plus carefully scoped paid evals. It does **not** already contain a finished capability benchmark.
