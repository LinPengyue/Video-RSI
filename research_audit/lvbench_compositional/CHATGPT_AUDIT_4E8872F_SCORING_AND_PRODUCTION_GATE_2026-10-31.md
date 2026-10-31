# CVPR2027 — Independent review of Cursor `4e8872f` and narrow continuation

Date: 2026-10-31. Cursor commit `4e8872ffeef77204957cd34552dff5b3e5481352`.
Audit basis: GitHub file/commit comparison, V2.1 source, reported tests, `run_002_patch_regen` metrics/QA/packets. **No independent local test rerun and no new continuous-video examination.**

## Status: accept V2.1 bookkeeping and leakage repair; Track A oracle-boundary claim still BLOCKED

1. The change is real, one commit after `f5413c62`; run_002 history remains intact. New cross-scene questions no longer literally expose the two location tokens; new test `test_question_side_semantic_leakage_detects_run002_bug` exists. Metrics separate 13 provisional answers / 0 independently verified answers, 8 packets serialized / 6 tentatively answer-bearing / 0 reviewer assets verified / 0 formal blind ready. `run_003` explicitly NOT STARTED due to no newly registered eligible DEV videos and no semantic extractor; do not fabricate a run.
2. **CRITICAL Track A latent gold-answer feed.** In `tools/lvbench_comp/typed_evidence_contract/program_execution.py:schema_to_program`, the `verify_answer` node still uses `inputs["answer"] = task.answer`. `TypedEvidenceExecutor._verify_answer` in `executor.py` consumes `request.inputs["answer"]` and writes `outputs["answer"] = answer`. Therefore the executor-visible program receives the oracle answer directly, even though `executor_saw_gold_answer=False` and `oracle_world_scraped=False` are emitted as hardcoded booleans. `test_oracle_boundary_no_world_facts_in_scorer` excludes `verify_answer` from its sentinel-gold assertion. Remove gold injection from ALL executable nodes; verification must consume an agent-produced prediction derived from tool-visible observations, while only the scorer compares it against gold. Add sentinel-gold and adversarial tests including VERIFY_ANSWER. Preserve old reported 0.333 result as a historical diagnostic, NOT a leakage-free performance estimate; rerun corrected six-task control and report changes without score chasing. It may remain negative.
3. **Distinct text is overstated by QA+answer key.** In `run_002_patch_regen/qa_drafts.jsonl`, 17 records contain only **8 distinct literal question stems**, and `QA_DRAFT_0009–0017` (all nine cross-scene drafts) share **the same identical question stem**. The 16 reported by prior `n_distinct_questions` arises from `dedup.n_distinct_questions` calling `question_answer_key`, which hashes the concatenated question AND provisional answer. It therefore counts identical questions paired with differing answers as distinct Q. Separate `n_distinct_question_texts` from `n_distinct_question_answer_pairs` from `n_independent_evidence_families` and `n_distinct_program_structures`. A text-only change that cures answer leakage must not be presented as semantic/question diversity.
4. The three retained newly observed families all use `cross_scene_attribute_contrast` and a generic `describe A vs B` stem. These may remain DEV/CONTROL artifacts, but have no established directed novel-composition structure or independently checked two-witness answer necessity. The count `n_answerable_candidate=6` is a heuristic candidate label based on provisional text, not verified answerability.
5. Formal review gate of 0 is appropriate: still-only paths and unverified MP4 do not justify a user blind batch. Existing 8 local media videos, if legally available and unsealed, MAY be batch-explored with bounded ffmpeg clips around selected events to test continuous action/identity or audio without pretending that this is a new video or an automated VLM. Avoid another per-Q endless frame-chasing loop; cap clips/time and preserve stop/uncertainty outcomes. No need to ask the user for ordinary MD/JSON transfers.

## Narrow continuation, not a new method roadmap

P0 Track A (small effort): remove task.answer from executor-visible `verify_answer` inputs, add an actual oracle-leakage negative test and rerun matched static/oracle controls. Do not build a new Evolver or tune selection weights.

P0 Track B (small bookkeeping): fix distinct question stems metric, retain previous metrics for historical provenance, and avoid treating 6 provisional answer-bearing candidates as verified.

Track B majority effort: investigate a **bounded actionable** path to real continuous-media review and new semantic coverage, using only existing DEV_CONSTRUCTION media or newly **authorized** nonsealed videos. If no additional legitimate videos/extractor are available, report this capacity blocker, and provide an explicit resource/access dependency (video eligibility, playable clips, or approved low-cost perception method), not further QA-template patches. Do not repurpose sealed test IDs as DEV or claim new run_003.

No formal user A/B blind review now. Existing exposed videos may be used only for development. Maintain Track B 80% / Track A 20%, `UNASSIGNED`, no auto-`SUPPORTED`, sealed untouched, `ok_for_expensive_rsi=false`; Seen can be multi-step and Unseen means held-out target directed composition structures.

## Decision

**Accepted:** genuine V2.1 leak/metrics/readiness maintenance; honest run_003 blocker and preservation of negative results.

**Not accepted:** absolute `oracle_world_scraped=0` / `executor_saw_gold_answer=false` as sufficient evidence of oracle isolation; current program execution accuracy as method evidence; 16 genuinely different question texts; autonomous unseen-video semantic discovery; verified composition benchmark yield.
