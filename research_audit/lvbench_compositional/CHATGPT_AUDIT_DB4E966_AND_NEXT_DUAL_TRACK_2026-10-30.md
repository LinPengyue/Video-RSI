# CVPR 2027 — ChatGPT independent audit of db4e966 + next dual-Track handoff
Date: 2026-10-30
Audited Cursor commit: `db4e9669353c54b88696260a778cc25e7b0f7613`
Companion visual audit: `track_b/CHATGPT_DIRECT_VISUAL_REVIEW_DB4E966_2026-10-30.jsonl` (four records)
Branch: `research/lvbench-comp-video-grounded-evidence`

## Provenance
Directly read `tools/lvbench_comp/typed_evidence_contract/program_selection.py` and `test_program_selection.py`, `track_a/TRACK_A_PROGRAM_SELECTION_FEASIBILITY.md`, `track_b/CANDIDATE_FUNNEL_PARALLEL.jsonl`, and commit diff. Inspected the two GitHub TT adjudication contact sheets and all nine GitHub seed frames for S8vPx-u9p_A, iA_69g87Ilw and hROKtPqktO8 by fetching JPEG bytes and looking at images. Did **not** watch gitignored MP4 or listen to audio. I did **not** independently execute Python repository tests. Contact-sheet observations are static frame-level evidence only.

## Executive conclusions
- **A** has moved beyond threshold-only binding policy to a *distinct program-schema selector prototype*, but its reported 0.833 is **DAG-label selection accuracy only**, NOT execution correctness, program synthesis or Harness RSI. The 1.0 held-out graph score is achieved on fixed keyword-heavy questions with the held-out templates already written into the inference library and selector weights. Evolver weights score 0.750 < default selector 0.833. Keep the frozen binding parity/negative result; no new RSI claim.
- **B** now has a reasonably grounded **TT garment-color reverse-reference candidate**, but independent continuous-video / dual-necessity adjudication still pending. Football stopped, athletics revised, CG-NEW-002 unresolved — scientifically appropriate pruning, not failures to hide. Three new seed videos contribute new genres but only 3 widely separated stills each; no genuine new causal fact or verified QA yet.
- Priority: deliver **one completed video-grounded candidate audit and one executable held-out graph test**, not another broad sampling round or new model branding.

## Track A — exact scientific implementation gap

### A1. Four schema DAGs exist; their actions are not executed in the evaluation
`program_selection.py:build_program_selection_split()` calls `_make_world(...)` but assigns the result to `_` and discards it. `evaluate_selector()` checks only:
```
selected_schema_id == gold_schema_id
```
and `run_program_selection_ablation()` similarly compares predicted schema IDs to `t.gold_schema_id`. No selected program is compiled/executed on masked observation windows, no predicted video/synthetic answer is validated, no binding/necessity trace is evaluated. Thus **'held_out_graph_accuracy=1.0' means 4/4 correct *labels* on two compare and two missing-evidence questions; not unseen-structure execution success**. Distinguish `program_choice_accuracy` from `execution_answer_accuracy`, `dependency_validity`, `causal_necessity`, `abstention_precision/recall`, `tool_cost`. New tests should assert DAG edges are realized and the selected program changes predictions.

### A2. Keyword shortcuts and target templates exposed at inference
The held-out compare/abstain programs are in `DAG_LIBRARY` for inference, with explicit manually designed weights from `has_compare` / `has_missing`. Test questions literally include `compare`, `both`, `missing`, `abstain`. This is a *known-library, zero-example template-classification* diagnostic, **not** autonomous synthesis of a new operator graph. In particular `SCHEMA_COMPARE_TWO_STATES` already existed as an exact target DAG before evaluation; train label split alone does not prove composition OOD.
- **Level 1:** unseen task instances / argument values with a *known DAG library*.
- **Level 2:** unseen DAG usage combinations requiring *composition of known primitives*, without predefining the full target DAG for the tested agent.
- **Level 3:** genuine Evolver-adapted harness policy that acquires reusable execution change from train/dev and transfers to blind new video structures.
Never equate L1 with L2/L3.

### A3. Eight seeds do not imply eight independent test sets
`run_program_selection_ablation()` always calls `build_program_selection_split(seed=42)` and evaluates the **same six handcrafted test questions** across 8 seeds; only evolutionary/random choice varies. Report effective `n_test_questions=6`, `n_held_out_examples=4`, `n_independent_test_worlds=0` for actual execution. No confidence interval over semantic task diversity is supported by 8 search seeds.

### A4. Proposed bounded A implementation
1. Implement `execute_selected_program(schema, observations, question)` for the 4 DAG schemas, with observable-only records and a scorer-only oracle; persist the compiled/executed trace and actual answer, budget and refusal status. Use an actual state-order comparator and missing-evidence detection, not a schema-label scoring shortcut. Inversion controls: reverse question direction with same observations, flip score-transition order, remove A or B evidence, insert distracting entity, and make both sides insufficient.
2. Add **lexical invariance pairs**: same underlying DAG, paraphrases with/without `compare`, `missing`, `later`; different DAGs with identical surface keywords; test semantic correctness AND selected-graph fidelity. No classifier with hardcoded exact target question strings.
3. Build one **new independently generated** task family for execution (not identical six questions); hold out at least one **executed graph** and vary entity count/cue noise/state order.
4. Compare with a *strong, equally informed static program selector* and oracle-program upper bound; match mutation access/calls/candidate budget; allow no-win.
5. If no program-compiler executes a selected DAG, explicitly keep metrics as **selection-only** and stop future performance claims.
6. Freeze the 4-task matched binding regression; `ok_for_expensive_rsi=false`; never consult sealed final.

**Deliver A**: `track_a/TRACK_A_EXECUTED_GRAPH_FEASIBILITY.md`, synthetic per-question trace JSONL, tests, labels vs answer vs necessity columns, failure examples. Avoid naming it RSI if merely selecting templates.

## Track B — direct review and candidate convergence

### B1. QA-TT-REVERSE-001 — strongest imminent candidate (still unverified)
Viewed:
- `track_b/chatgpt_review_assets/VTCDQYYKA9o/tt_qa_adjudication/contact_A.jpg` — at 02:43–03:06 a short-haired athlete in red jacket wipes face with white towel and removes red outer layer to reveal blue-yellow playing shirt;
- `.../contact_B.jpg` — at 04:25–04:35 a blue-yellow-shirt athlete is at the table, with **FAN ZHENDONG / PREVIOUS RESULTS** overlay.
This is a plausible *reverse-time identity-conditioned garment query*. From stills alone cannot certify identical person across both times or truly blind necessity. Preserve original question and candidate answer **red** with `gold_answer=null`, `PROPOSED_REVIEW_REQUIRED`, `UNASSIGNED` until review.

One bounded independent adjudication:
- Reviewer 1 blinded to A: exactly original question + **B-only** `04:25–04:35` clip → free-text answer + confidence + evidence moment; record without revealing A.
- Reviewer 2 for **A-only**, then A+B with independently shuffled presentation or different reviewers, preserving exact question wording and no answer/options leakage.
- Watch original **A 02:43–03:06** and **B 04:25–04:35** continuous clips for same-actor wardrobe/facial continuity.
- Inspect full-video context for other blue/yellow players / earlier red attire in B, and name overlay association to depicted player.
- If A-only can trivially answer due to unique athlete, label `DEVELOPMENT_CONTROL` or rewrite to require disambiguation rather than passing strong. No auto `SUPPORTED`.

### B2. Three seed videos — actual visual observations, not new multi-event answers
See the four `CHATGPT_DIRECT_VISUAL_REVIEW_DB4E966_2026-10-30.jsonl` rows with individual GitHub JPEG paths and caveats.

- `S8vPx-u9p_A`: snowy animation with two winter-dressed characters; separate icy staircase/architecture; very distant water/swirling effect. **P1** because potential visually grounded multi-actor/object transformation, but no demonstrated continuity. Get narrow *continuous* windows near 1st scene and final effect, track a character/object. If no real link in 2 clips, reject this candidate hypothesis and explore other parts of the video.
- `iA_69g87Ilw`: travel/interior vlog with fruit plate, male host talking from chair, nighttime lit pool. **P2**, audio/scene-reference dependent; needs speech or explicit camera transition before claiming related location/time.
- `hROKtPqktO8`: urban street, bare volcanic-looking terrain, outdoors hooded person. **P2**, may be a travel context but neither geographic names nor common identity proven. Don't invent locations/causality.
- **All seed filename `tNNN` values need authoritative unit conversion from extraction manifest**, rather than assuming e.g. t3182 means '31:82'. Cursor must write `source_time_seconds`, `HH:MM:SS`, and verify each against original media.

### B3. Stop accumulating unverified material
- Football strong attack-origin QA remains `HYPOTHESIS_NOT_SUPPORTED`, STOP gate; score overlays preserved as source visual facts.
- Athletics `START LIST — ROUND 1 HEAT 2` is not finish result; do not resurrect a rank QA without actual result.
- CG-NEW-002 table push unresolved; no more sparse hunts without one human continuous adjudication.
- CG-NEW-001 hug and CG-NEW-003 bark still need a *single* targeted watch/listen, not endless frame extraction.
- Future full Benchmark: continue **separate new event discovery** across videos/genres, composition signatures, minimal witness sets, and untouched sealed reservoir; do not consume all time chasing TB/CG false positives.

**Deliver B**: `track_b/TRACK_B_TT_ADJUDICATION_AND_NEW_SEED_PROGRESS.md`, neutral A/B/A+B review outcomes when human reviewers actually watched the clips; follow-up seed window manifest with authoritative timestamps; a few specific **new** observed events rather than many random frames. All statuses unchanged unless reviewer evidence supports a graded next stage; no automatic `SUPPORTED`.

## Shared policy
Keep A/B simultaneous; review files/metadata via GitHub, bulk copyrighted MP4/WAV gitignored; local file pointers in GitHub do NOT grant ChatGPT video/audio access. Avoid overstating provenance. All discussed items `UNASSIGNED`, exposed construction videos never blind final. No expensive RSI/H_S1 sealed validation. Commit/push and report separate A/B outcomes. When uncertain, negative/stop decisions are useful research progress.
