# TRACK B PROGRESS — video-driven evidence round

Baseline: `791d25f9603a6533ef2ce0ee9e275430123ff667`

## Method change

Primary path is **video evidence → fact discovery → mechanism → ChatGPT QA design → independent verification**.  
Official-QA name-swap is no longer the main constructor.

## High-value evidence supplements

| ID | Video | Focus | Extracted |
|---|---|---|---|
| CG-NEW-001 / TB-003 | TJR1oYDDTwg | cast continuity + dual performers | yes |
| CG-NEW-002 / TB-007 | Cm73ma6Ibcs | restaurant second-level + snow identity | yes |
| CG-NEW-003 / TB-006 | LLSJrEgOOtw | audio retained + zoomed dog + later play | yes |
| CG-NEW-004 / TB-004 | vaL_vSdZKZo | reuse prior TB media | pending review |
| CG-NEW-005 / TB-001 | _T2Avd3tFHc | reuse prior TB media | pending review |

## New video facts

Cursor **did not invent** new verified facts. Adjacent windows were extracted as `NEEDS_HUMAN_OR_CHATGPT_FACT_DESIGN` in `adjacent_new_fact_candidates.jsonl`.

## Second-round status

All five remain `PROPOSED` / `COMPOSITION_PENDING` / `UNASSIGNED`. No auto `SUPPORTED`.  
See `cg_new_second_round_status.jsonl`.

## Mechanism coverage

role disambiguation; reverse temporal; audio-visual object link; attribute-role bridge; person→location.

## Still needed from ChatGPT

Labeled new facts (if any) from adjacent clips; refined QA wording if import jsonl differs; necessity judgments A-only/B-only/A+B after watching new packs.

## Evidence pack

`local_media/cg_new_round/` + zip `local_media/lvbench_cg_new_evidence_round.zip` (gitignored).

## Status

**Track B: evidence advanced for 001–003; composition still pending independent review. Not a formal benchmark freeze.**
