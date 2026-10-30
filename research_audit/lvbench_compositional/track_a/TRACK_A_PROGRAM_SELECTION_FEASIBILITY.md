# TRACK A — Question-conditioned program selection feasibility

Date: 2026-10-30  
Responds to: `CHATGPT_AUDIT_68E3160_AND_DUAL_TRACK_HANDOFF_2026-10-30.md`  
`ok_for_expensive_rsi=false` · label: **`question_conditioned_program_selection_prototype`**

## Frozen binding negative control (do not tune)
Matched-budget TECE ≈ static strong policy (acc 0.500) remains frozen:
- `matched_budget_parity.json`, `bind_failure_taxonomy.json`, `TRACK_A_BIND_FAILURE_TAXONOMY_AND_PARITY.md`
- Status: **`FROZEN_NEGATIVE_CONTROL_DO_NOT_TUNE`**

No further threshold sweeping on the four-task suite.

## Distinct executable DAGs
| schema_id | graph_hash | Role |
|---|---|---|
| `forward_person_action` | `eebe6b9bf1b690a3` | (i) A→bind→B |
| `reverse_event_to_prior_action` | `0586bcbfab3f704b` | (ii) B→bind→A prior |
| `compare_two_state_transitions` | `3b7b93286889d065` | (iii) order two state changes — **held out of train** |
| `missing_evidence_abstain` | `2755edda56579c3c` | (iv) abstain — **held out of train** |

Structural leave-out OK (no shared graph hashes). Gold schema never passed into `select_program()`.

## Matched ablation (8 seeds) — `program_selection_feasibility.json`

| Arm | Choice acc | Held-out graph acc | Seen graph acc | Oracle leak |
|---|---:|---:|---:|---:|
| fixed_forward | 0.167 | 0.000 | 0.500 | 0 |
| random | 0.208 | 0.219 | 0.188 | 0 |
| vanilla_heuristic | 0.167 | 0.000 | 0.500 | 0 |
| selector | **0.833** | **1.000** | 0.500 | 0 |
| evolver_weights | 0.750 | 0.875 | 0.500 | 0 |
| oracle_program_upper | 1.000 | 1.000 | 1.000 | 1.000 |

### Failures / honesty
- **Evolver does not beat fixed selector** on this toy cue set (0.750 < 0.833). Weight search ≠ harness DAG discovery → **not RSI**.
- Selector fails when forward questions contain “later” (confused with reverse), e.g. `test_5_forward_` → predicted reverse. Feature leakage from English wording, not compositional understanding.
- Held-out compare/abstain succeed mainly via keyword cues (`compare`/`missing`) — useful feasibility, **not** video transfer claim.

## Code / tests
- `tools/lvbench_comp/typed_evidence_contract/program_selection.py`
- `tools/lvbench_comp/test_program_selection.py`

## Boundary
Prototype only. No expensive RSI. Next real step would need observation-conditioned selection without lexical gold shortcuts and execution fidelity on held-out graphs — still synthetic before any video claim.
