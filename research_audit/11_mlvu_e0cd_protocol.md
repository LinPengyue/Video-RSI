# 11 — E0-CD preregistration: Initial Harness vs H_S1 on MLVU-Test (MC only)

Date: 2026-10-22  
Status: **PREPARED / NOT STARTED**. Awaiting: complete video upload+checksum, researcher cost approval, scoring-path decision.  
Claim type: **cross-dataset transfer of one accepted local revision** — not LVBench held-out, not general Evolver proof.

---

## Frozen arms

| Arm | Path | tree_sha256 (with trailing newline) |
|---|---|---|
| Control | `evolution/run-seed42/versions/initial_harness` | `0805cf0e…744fe3` |
| Treatment | `evolution/run-seed42/versions/H_S1` | `6733c480…25518f` |

Baseline commit: `5ad014499a5e009b75e3ef05ac83595b78adda09`.  
Config freeze: copy `evolution/run-seed42/effective_config.json` fields for models/budgets/concurrency into the run config **without** committing secrets. Same `API_BASE` route for both arms.

Items (answer-free): `research_audit/mlvu_test_prep/mlvu_test_mc_items.jsonl`  
SHA256: see `conversion_manifest.json`.

---

## Round-1 sample plan (preregistered)

| Stage | n | Rule |
|---|---:|---|
| Smoke | ≤10 | Stratified by `task_type` if possible; paid only after GO |
| Primary (if smoke OK) | **200** | Fixed RNG seed `20261022`; stratified by the 9 MC `question_type`s; freeze sample_id list in a future commit **before** scoring |
| Full MC (optional later) | 502 | Only if primary completes and budget allows |

**Generation tasks (86):** excluded from round-1.  
**Harness selection:** forbidden. Do not edit `H_S1` / initial harness based on MLVU scores. Do not pick other evolution candidates using MLVU.

Until the 200-id list is committed post-video-ready, treat primary n=200 as the **intent**; do not draw the list after seeing model answers.

---

## Metrics (paired)

Record for each arm on the **same** sample_ids:

- Accuracy (micro %); status completeness  
- Fix / Harm / Net vs Control (only when labels exist)  
- Mean Qwen frames (`qwen_returned_frames_v2`); Qwen calls  
- DeepSeek/Qwen tokens & estimated CNY **if** meter available (else UNKNOWN)  
- Per-`task_type` accuracy table  

Primary endpoint: **micro Accuracy Treatment − Control** on the frozen primary set.  
Secondary: frames delta; per-type breakdown (exploratory).

---

## Scoring / GT

Official Test GT is undisclosed in-tree. Options:

1. **Offline:** researcher-supplied labels JSONL (`sample_id`, `answer` ∈ A–F) used **only** in `score.py`.  
2. **Online:** submit predictions to MLVU evaluation service when available — still keep items answer-free locally.

If neither is available after inference, store predictions but mark Accuracy as **unscored**.

---

## Execution template (do not run until approved)

```bash
# Control
python run_batch.py --config <frozen_config> \
  --candidate evolution/run-seed42/versions/initial_harness \
  --items research_audit/mlvu_test_prep/mlvu_test_mc_<split>_items.jsonl \
  --output-dir outputs/mlvu_e0cd_initial_<split> \
  --allow-provider-calls

# Treatment
python run_batch.py --config <frozen_config> \
  --candidate evolution/run-seed42/versions/H_S1 \
  --items research_audit/mlvu_test_prep/mlvu_test_mc_<split>_items.jsonl \
  --output-dir outputs/mlvu_e0cd_hs1_<split> \
  --allow-provider-calls

# Score only with separate labels
python score.py --items ... --predictions .../results.json --labels <labels.jsonl> --output ...
```

Outputs stay under ignored `outputs/` (not pushed).

---

## Stop rules

1. Videos incomplete / checksum fail → no launch.  
2. Smoke engineering error rate >20% → stop.  
3. Cost/frame stop rules in `12_mlvu_cost_estimate.md`.  
4. Any harness edit after seeing MLVU scores → invalidate study.

---

## What success would mean / not mean

| Means | Does not mean |
|---|---|
| Local `H_S1` transfers (or fails to) on MLVU-Test MC under frozen models | Evolver is generally capable |
| Gate accept on LVBench predicted cross-dataset gain | Diagnosis/Modification modules are correct |
| | Same-distribution unseen LVBench video generalization |
