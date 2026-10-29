# TRACK A PROGRESS — Typed Evidence Contract Evolution

Baseline: `791d25f9603a6533ef2ce0ee9e275430123ff667`  
Expensive RSI: **not run** (`ok_for_expensive_rsi=false` remains).

## Method interface

Generic operations (item-agnostic):

1. `locate_event`
2. `resolve_reference`
3. `track_identity`
4. `query_property`
5. `verify_answer`

Shared I/O carries entity candidates, time spans, evidence refs, binding results, ambiguity flags.

Code: `tools/lvbench_comp/typed_evidence_contract/`.

## Evolver modification space

Allowed: op order/branching, search budget, recovery strategy, dual-evidence verify predicates.  
Forbidden: frozen video-model weight updates, sealed-test answer reads, item-hardcoded pipelines.

## Local simulated tests

See `tece_counterfactual_results.json` and `python3 -m unittest tools.lvbench_comp.test_typed_evidence_contract -v`.

| Check | Result |
|---|---|
| Missing evidence reports gap | True |
| Binding change moves query target | True |
| Single-clip ≠ strong composition | True |
| Failure triggers recovery | True |

## Potential increment vs prior RSI / unproven

**Potential increment:** evolvable evidence contracts + dual-interval verify + recovery, aimed at composition transfer rather than prompt templates.  
**Unproven:** no claim of video composition generalization; only simulated-trace logic.

## Still missing for a real method experiment

- ≥6 video-supported Unseen compositions across ≥3 videos
- Multi-video VALID Seen query_action coverage
- Human-verified dual-interval tickets for TECE grounding
- Declared Initial Harness snapshot wired to real tools (still no H_S1 final judge)
- Fair-budget arm runners (no_harness / fixed planner / vanilla RSI / TECE-RSI)

## Status

**Track A: runnable TECE prototype + unit tests. NOT ready for expensive RSI claims.**
