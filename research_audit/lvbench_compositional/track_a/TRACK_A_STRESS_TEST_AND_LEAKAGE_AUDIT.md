# TRACK A — Stress test, structural leave-out, and leakage audit

Date: 2026-10-29  
Responds to: `CHATGPT_NEXT_ROUND_RESEARCH_AUDIT_2026-10-29.md`  
Prior synthetic 1.00/1.00 claim: **withdrawn as compositional generalization evidence**.

## 1. What was wrong in `77d524c`

| Issue | Finding |
|---|---|
| A1 Signature ≠ structure | Seen/Unseen labels differed (`describe_attribute/location/action`) but all used `property_name=action` and the same `_world_pair()` DAG + ambiguous `"speaker"` recovery. Measured alias-recovery transfer, not structural composition transfer. |
| A2 Necessity | `STRONG_COMPOSITION` could fire with dual citations even when B-only might suffice; `supports_answer` was an oracle-ish node flag. |
| A3 Oracle privilege | Agent read `SimulatedWorld` entity_ids / fact values directly; recovery rebound via oracle `fact.entity_id`. |
| A4 Unfair baselines | Vanilla mutated budget only; TECE mutated recovery; single seed; hardcoded `run_task` ignored `op_order_template`; Unseen n=1. |

## 2. Fixes implemented

Code:

- `program_schema.py` — executable op DAGs + `graph_hash()`; leave-out by hash.
- `evolution_loop.py` — train/dev/test; select on **dev**; evaluate **test once**; matched `SHARED_MUTATION_POOL`; `op_order_template` honored; arms: fixed, fixed_rebind, random, vanilla, tece, tece_minus_*.
- `evidence_graph.py` — separate `evidence_path_valid` / `composition_necessary_hint`; single-entity B → `PATH_VALID_NECESSITY_UNPROVEN` (not strong necessity).
- `necessity.py` — masked A-only / B-only / A+B for `composition_necessary`.
- `noisy_obs.py` — observation projection + scenario families; leak log when recovery uses oracle ids.

Artifacts:

- `split_witness.json`
- `tece_matched_ablation_structural.json`
- `tece_multiseed_stress.json` (20 seeds)

## 3. Split witness (structural)

`leave_out_ok: true`, intersecting hashes: **[]**

| Split | Schema IDs | Graph hashes (abbrev) |
|---|---|---|
| Train/Dev | `forward_person_action`, `forward_person_location` | `eebe…`, `2c46…` |
| Test (held-out) | `reverse_event_to_prior_action`, `av_reid_then_query` | `948f…`, `0586…` |

Never relabel an unchanged graph as Unseen.

## 4. Matched-budget single-seed (seed=11)

Semantic accuracy on structural **test** (not comparable to prior 1.00/1.00 label-split):

| Arm | Dev | Test semantic | Strict composition | Necessity | Oracle-leak |
|---|---:|---:|---:|---:|---:|
| Fixed (no recovery) | 0.50 | 0.33 | 0.00 | 0.00 | 0.00 |
| Fixed rebind (non-evolving) | 1.00 | **1.00** | 0.00 | 0.00 | **0.67** |
| Random (matched mutations) | 1.00 | 1.00 | 0.00 | 0.67 | 0.67 |
| Vanilla (matched mutations) | 1.00 | 1.00 | 0.00 | 0.67 | 0.67 |
| TECE | 1.00 | 1.00 | 0.00 | 0.67 | 0.00 |
| TECE − recovery | 0.50 | 0.33 | 0.00 | 0.00 | 0.00 |
| TECE − graph / − verify | 1.00 | 1.00 | 0.00 | 0.67 | 0.00 |

**Negative scientific result:** under matched mutation access, Random/Vanilla/Fixed-rebind erase any TECE-only advantage on semantic transfer. Strict composition necessity remains **0** — dual-path credit ≠ necessity.

## 5. Multi-seed stress (n=20, base_seed=100)

Means on structural test:

| Arm | Test semantic mean | Strict mean | Necessity mean | Oracle-leak mean |
|---|---:|---:|---:|---:|
| Fixed | 0.333 | 0.000 | 0.000 | 0.000 |
| Fixed rebind | **1.000** | 0.000 | 0.000 | **0.667** |
| Random | 1.000 | 0.000 | 0.267 | 0.667 |
| Vanilla | 1.000 | 0.000 | 0.267 | 0.667 |
| TECE | 0.967 | 0.000 | 0.200 | 0.467 |
| TECE − recovery | 0.333 | 0.000 | 0.000 | 0.000 |

CIs and per-seed rows: `tece_multiseed_stress.json`. Failure cases logged: **316** (sample in JSON).

## 6. Failure modes (representative)

1. **Oracle bind via recovery** — locate→`fact.entity_id` rebound without successful resolve; fixed_rebind/random leak ≈0.67.
2. **Necessity fails** — A-only or B-only still answers under masked eval, or evidence path lacks multi-entity B disambiguation → `composition_necessary=false` even when semantic correct.
3. **Noisy lookalike / misleading caption** — reverse+noise family confuses bind; semantic drops for TECE on some seeds (mean 0.967 < fixed_rebind 1.0).
4. **AV schema** — without true audio perception channel, “AV” remains a program-schema label over simulated facts; not perceptual AV fusion.
5. **Strict composition rate = 0** across arms — strongest honesty check: no arm earns necessity-validated composition success on this suite.

## 7. What may still evolve

Current search primarily evolves **recovery / budget / op_order parameters**. Program schemas define structure; genomes can reorder ops via `op_order_template`. This is **not** yet proof of open-ended harness program discovery on video.

## 8. Stop conditions (unchanged)

- `ok_for_expensive_rsi=false`
- No expensive RSI
- Do not optimize the synthetic suite to force a TECE win
- Real claims require human-verified multi-video dual-interval tickets + frozen tools

## Status

**Prior 1.00/1.00 synthetic transfer claim invalidated for compositional structure. Fair controls + necessity/leak audits are now the reported result.**
