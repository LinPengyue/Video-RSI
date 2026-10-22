# 06 — Gate replay (Rounds 1–3)

Date: 2026-10-22  
Branch: `research/cvpr2027-audit`  
Baseline: `5ad014499a5e009b75e3ef05ac83595b78adda09`  
Method: recompute `gate_decision` from `private_gate/{parent,candidate}/results.json` + `data/lvbench-split/gate_oracle.jsonl` using `solver_full_workspace/engine/evolve.py` and `evolution/run-seed42/effective_config.json`.  
**No Solver/Editor/Gate re-run. No paid API.**

Safe machine-readable summary (no answers): `research_audit/e0_gate_replay_stats.safe.json`.

Metric name note: the Gate JSON field for wrong→right flips is **`fix`** (not `help`). Confirmed by source `evolve.py` L61 and raw `gate_aggregate.json` bytes.

---

## Harness versions (SHA256)

| Tree | tree_sha256 | Diff vs initial |
|---|---|---|
| `versions/initial_harness` | `0805cf0eff40fe55712124f0cc70e228e7e3205e362cca37dc79a9d977744fe3` | — |
| `versions/H_S1` | `6733c4806ba3a352e15e866451292a03144c862c53c65e1691d42a718525518f` | `prompt.md`, `tools.py` only |

Per-file hashes are in `e0_gate_replay_stats.safe.json` → `versions`.

All three rounds used **parent = `initial_harness`** (`phase.json`), because R1/R2 were rejected so `current` never moved until R3 accept.

| Round | Candidate snapshot tree | Equals committed `H_S1`? |
|---|---|---|
| 1 | `7bc6f5229dd2c42606684d1d42248aa09e74a597bef4e0de172eb7adee6a5c9a` | No |
| 2 | `d437314e04863f1e061ff83e79e0556ac5af3ec71f0c0dc75e17fc830743eb5d` | No |
| 3 | `6733c4806ba3a352e15e866451292a03144c862c53c65e1691d42a718525518f` | **Yes** |

---

## Pairing & replay

| Round | Paired on same 72 Gate IDs? | Stored `gate_aggregate` == replay? | Policy decision |
|---|---|---|---|
| 1 | **VERIFIED** yes | **VERIFIED** exact match | REJECTED |
| 2 | **VERIFIED** yes | **VERIFIED** exact match | REJECTED |
| 3 | **VERIFIED** yes | **VERIFIED** exact match | ACCEPTED (accuracy branch) |

Policy (`evolve.py` L47–49): accept if  
`cn > pn` and `100*cf <= 110*pf` **or**  
`pn-1 <= cn <= pn` and `100*cf <= 80*pf`.

---

## Recomputed metrics

| Round | Parent Acc | Cand Acc | Fix | Harm | Net | Parent mean Qwen frames | Cand mean | Frame ratio | Parent Qwen calls | Cand calls | Decision |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 41/72 | 41/72 | 6 | 6 | 0 | 57.39 | 55.56 | 0.968 | 310 | 281 | REJECTED (neither branch) |
| 2 | 42/72 | 40/72 | 8 | 10 | −2 | 55.24 | 60.33 | 1.092 | 304 | 328 | REJECTED |
| 3 | 43/72 | 47/72 | 10 | 6 | **+4** | 55.39 | 59.82 | **1.080** | 299 | 328 | **ACCEPTED** accuracy (`cn>pn` and ratio≤1.10) |

Submitted/failed Qwen frames and OCR frames match stored aggregates (see safe JSON).

---

## Round 3 accept: flip structure

**Fix (10):** types — entity recognition 3, key information retrieval 3, summarization 2, reasoning 1, temporal grounding 1.  
Videos: 9 unique; `vHlSoxg8WHo` appears twice; others once.  
Sample IDs (no answers): see `e0_gate_replay_stats.safe.json` → `round3_flips_aggregate.fix_sample_ids`.

**Harm (6):** types — event understanding 2, summarization 2, entity recognition 1, reasoning 1.  
Videos: 6 unique, one each.

**VERIFIED:** flips are **not** confined to a single video or single question type.  
**UNKNOWN:** whether flips share a latent failure mode beyond type/video counts (would need trajectory coding; not done here).

---

## Patch vs Editor plan (Round 3)

Changed files vs `initial_harness`: **`tools.py`**, **`prompt.md`** only.

Implemented mechanisms (**VERIFIED** by unified diff + `edit_summary.md`):

1. Remove `read_transcript` from `ToolBox.descriptions()` (ASR unavailable on local train evidence cited in plan).
2. Exact-window visual cache in `ToolBox.visual()` keyed by `(purpose, start, end)`; returns `reused=True` without new Qwen call.
3. Short `prompt.md` note describing reused observations.

`edit_plan.md` proposed exactly these two mechanisms (+ optional prompt); `edit_summary.md` states both were implemented in `tools.py` with a small prompt note. **VERIFIED alignment** between plan intent and committed `H_S1` file set.  
**UNKNOWN:** whether runtime Editor transcript fully matches every plan sentence (would require full protocol jsonl audit).

### Testable mechanism hypotheses (not validated)

| ID | Hypothesis | How to falsify later |
|---|---|---|
| M1 | Removing `read_transcript` improves Acc by freeing decision steps when ASR is empty | Compare ablations: cache-only vs transcript-removal-only on a fixed eval |
| M2 | Exact-window cache reduces redundant Qwen frames | Measure repeat identical-window rate / frames with cache on vs off |
| M3 | Gate Acc↑ is partly stochastic Solver variance, not causal patch effect | Repeated paired evals; sign instability already seen in other pilots (`03_`) |

**IMPORTANT:** Round 3 Gate accept measures selection on the **Gate set**, not generalization.

---

## Verdict

Selection logs for R1–R3 are **internally consistent and reproducible from raw predictions**. Local `H_S1` is exactly the Round 3 candidate snapshot. The accept is an **accuracy-branch** win with **+8% frames** (still ≤10% cap), not an efficiency win.
