# TRACK A READINESS

Role: minimal strict compositional generalization benchmark + Video Agent RSI method prep.  
Baseline shared commit: `db62562f03904a79dec8d5988f6ae9250ccd5517`  
This round: **no expensive RSI / no paid API**.

## 1. Verified inventory (summary)

| Class | Count / status |
|---|---|
| Verified composition questions (facts+composition) | **2** (`LVCOMP-V2-002/003`, both `JTa_Ue2MSwc`) |
| Verified composition videos | **1** |
| Action-primitive VALID (train audit) | **1** (`LVCOMP-V2-100`) |
| Independent-review positive control | VG-001 (`VISUALLY_SUPPORTED_BUT_NOT_NOVEL`) |
| Unverified structural Unseen (v3) | 7 new + several seeds |
| Rejected/blocked for Unseen | VG-002 `UNCERTAIN_AGENT`, VG-003 `NO_CLEAR_NEW_FACT` |

**Do not equate correct Fact A/B text with a valid composition question.**

Details: `verified_inventory.csv`.

## 2. Minimal evaluation protocol draft

See `protocol_draft.json`.

- Evolution set contains primitives A and B separately.
- Target signature (`identify_person + query_action` for first study) **strict leave-out**.
- Train/test: no video overlap, no UID overlap.
- Shortcut audit required.
- Development set ≠ sealed final test.
- **Initial Harness only** for new runs; **H_S1 must not** be the strict final judge (prior full LVBench exposure).

## 3. Lightweight experiment framework

- Config skeleton: `configs/dry_run_arms.json`
- Arm matrix: `experiment_matrix.json`
- Config check result: `config_check_result.json` → `ok_for_expensive_rsi=false`

Arms: `no_harness`, `fixed_strong_planner`, `vanilla_rsi`, `new_rsi`; ablations `harness_only`, `harness_plus_evolver` under fair budget.

## 4. Mechanism hypotheses (composition transfer)

1. **H1 transferable entity binder** — reusable referring-expression → entity-trace → later-interval query skill (not a fixed prompt template).
2. **H2 evidence-dependency verifier** — require dual-interval evidence tickets; evolver mutates verification predicates to block single-clip answers.

## 5. Missing samples to start a credible diagnostic run

Minimum gate (draft):

- ≥6 video-supported Unseen composition items
- ≥3 Unseen videos
- ≥4 VALID Seen query_action items across ≥3 videos
- ≥8 Seen identify_person items across ≥4 videos
- Shortcut labels complete; sealed final held out

**Current:** far below gate → **BLOCKED**.

## 6. Estimated cost / blockers

- Cost if unblocked later: small dry diagnostic (tens of items × 4 arms) before any large RSI; still requires human video review hours first.
- Blockers: supported Unseen diversity; Seen-B action alignment; contamination risk if H_S1 reused as judge; Track B sealed tests must not tune A.

## Status

**Track A method prep: READY FOR PLANNING / NOT READY FOR RSI EXECUTION.**
