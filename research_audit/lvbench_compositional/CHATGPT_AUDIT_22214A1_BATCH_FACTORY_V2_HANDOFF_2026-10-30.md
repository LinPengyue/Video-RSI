# CVPR2027 — ChatGPT independent audit of 22214a1 and Track B Batch Factory V2 handoff
Date: 2026-10-30
Cursor SHA: `22214a1d9cee3a6a29475ae8ec394350dbf74da6`.
Companion per-item decisions: `track_b/batch_factory/CHATGPT_RUN001_AUDIT.jsonl` (8 items).
Branch: `research/lvbench-comp-video-grounded-evidence`.

## Executive verdict — throughput prototype YES, automatic semantic production NOT YET

The run_001 flow **actually completed** inventory→coarse image extraction/index→event graph→relation→rule QA→grade→human packet for 8 video files. This is a valuable end-to-end **software architecture / I/O / resume proof**.

It **does not yet establish** autonomous video-semantic discovery or 8 independent valid Benchmark QA:
1. `extract_events.py` predefines a `CURATED` dictionary for the **five previously discussed videos**. All 13 semantic records come from these hand-curated earlier visual-audit facts. 3 newly sampled videos generated only `visual_sample` / `seed_frame_present` placeholders. Do not report "semantic events newly extracted from 8 videos" or "one new QA per processed video": **novel semantic discovery yield in the 3 new seed videos = 0 in this run**. 8/8 means I/O and coarse sampling succeeded, not 8/8 semantic interpretation.
2. `qa_draft.py` uses explicit fixed rule templates keyed by relation types; no semantic QA model newly analyzed the 3 new video contents. This is a baseline rule-drafter, not the targeted **video-driven generative factory**.
3. `QA_DRAFT_0004` and `0005` have exact **same question and answer**; `0006` and `0007` too. Thus 8 drafts ≤6 distinct question texts. The current dedup hash uses exact `fact_ids` and composition signature; it misses overlapping evidence windows, semantic duplicates, and identical question strings. Worse, `0005` links `Z86_E_intro_ndure` (**NOR Ndure**) but asks/answers **USA Gay**—fact-to-question contradiction. This must be flagged as an explicit generation error, not an alternative independent family.
4. Current `auto_screen.py:_proxy_blind_answer` returns **fixed rule guesses by mechanism and provisional answer**, without actually viewing masked A/B video. The `AUTO_HIGH` = 0.8 is a hand-set formula score for known mechanism types, not a calibrated quality estimate; for TT it double counts duplicate questions, and football score-order is a dev control with a known B-only shortcut risk.
5. `B_ONLY_BLIND/packet.json` still carries all `required_windows`, both `facts` objects, **A evidence paths and fact IDs**, `proxy_necessity`, `auto_grade` and `auto_score`; only `visible_windows` changes and the answer is redacted. The file is **NOT blinded**. A-only has symmetrical leakage. In the human markdown the provisional answer is included as a spoiler. **Do not send current packet to user as a blind review.**
6. `pipeline_metrics.json.elapsed_s=0.23s` and the existing-frame cache in `_extract_frame()` likely mean this is primarily replay/cached-I/O. Separate `new_video_decoding_time`, `cached_frame_reuse`, `human_curated_events_loaded`, and `model_inferred_events` to make throughput claims meaningful. The 13 semantic records are imported/curated, so zero semantic inference cost is not zero cost of producing new facts.

These are **important, actionable engineering defects, not reasons to abandon the batch approach**. Preserve run_001 as historical baseline; no silent rewrite. Dedup+blinding are hard gates before human labeling, but should **not block run_002 candidate discovery**.

## Track B v2 — bounded changes in two parallel lanes

### Lane 1: 1-day-equivalent hardening of review / measurement (P0)
Implement before soliciting user time:
- **Tiered provenance**: distinct `CURATED_FROM_PRIOR_HUMAN_OR_CHATGPT_AUDIT`, `AUTOMATIC_COARSE_FRAME`, `AUTOMATIC_SEMANTIC_MODEL_OBSERVATION`, `HUMAN_VIDEO_VERIFIED`. Curated counts can be useful calibration fixtures but **not counted as newly discovered**.
- **Semantic/evidence-family dedup** in multiple layers: normalized question+answer; same video + overlapping time spans; normalized mechanism/program; source event aliases and equivalent attributes. Same video windows and question text must collapse even if `fact_ids` differ. Create tests using 0004/5 and 0006/7. Retain alias provenance and original records.
- **Fact binding validator**: every subject/name/country/color/temporal reference in proposed question and answer must derive from compatible cited event fields; test 0005 NOR Ndure vs "USA Gay" as contradiction and reject/quarantine. If generator cannot derive the content, leave ANSWER_PENDING instead of filling from a fixed template.
- **Calibrated labels, not pseudoproof**: change `AUTO_HIGH` to `HEURISTIC_HIGH_NOT_VIDEO_TESTED` or add `evidence_tested=false`, `masked_qa_executed=false` metrics. No claim A-only/B-only/AB was run from content unless an independent evaluator truly saw those masked observations. Rule flags can prioritize reviewers; never claim 0.8 represents objective correctness probability.
- **True blind packets**: B-only JSON/HTML/MD contain ONLY question + B clip/frame links for that variant + reply/confidence fields. No A paths, A event IDs, A times, provisional answer, gold, grader hints, auto scores, question source hints beyond wording. A-only likewise. A+B adjudication intentionally contains full evidence plus fact verification; label as unblinded. Separate storage/access for blind keys; include tests that serialize packets and search for forbidden A metadata. **A reader who has already seen A+B must not claim independent B-only blindness.**
- Human packets: **reviewable media**, i.e. direct preview or local clickable clip URI in reviewer environment; GitHub image paths alone do not prove continuous motion/audio. Each has `media_access_state` and `reviewer_asset_verified` so missing clips can be skipped quickly. No batch of eight duplicate/unanswerable questions to waste user review.
- Replace report summary with `n_total_coarse_frames`, `n_curated_semantic_events`, `n_new_machine_semantic_events`, `n_new_relation_families`, `n_distinct_questions`, `n_answer_known`, `n_human_reviewable`, `n_video_verified`, and `cost_per_new_candidate`.

### Lane 2: actually new event discovery on DEV videos (P0, majority of B effort)
- Run_002 **MUST** include the 3 previously unlabeled seed videos (`S8vPx-u9p_A`, `iA_69g87Ilw`, `hROKtPqktO8`) plus additional available, unexposed construction videos as bandwidth permits, but do not count recycled CURATED input as novelty.
- Coarse frames are visual assets, **not semantic interpretation**. Use a working, authorized affordable video understanding tool (local VLM where available; existing legal inference connector; or shared GitHub contact-sheet batch that ChatGPT can inspect) to transform prioritized windows into **new video-grounded semantic event observations**. If no semantic model is available under budget constraints, explicitly request ChatGPT to batch-review selected image/clip groups via GitHub and register `CHATGPT_FRAME_OBSERVATION`; do not quietly substitute old hand-curated facts or create bogus new events.
- Prioritize **eventful windows** not random deciles: shot/scene cut, motion/actor/garment/object change, captions/ASR where available, repeated referent. For each proposal save `media_path,time,scene_id,actor_local,verb,object,state_before/after,modality,source_model,uncertainty,matching alternatives`. Human/ChatGPT audit can validate at batch-level; unverified observations allowed as draft candidates.
- Relation discovery must be generalized over schema fields, not explicit hardcoded football/TT/athletics cases or word patterns. Promote typed event operators and relation DAGs as transferable **candidate** join patterns with uncertainty. Do not require every video to yield QA.
- Generation: require **video-specific** question/answer conditioned on fresh event attributes, minimal witness, answer derivation and concrete contrast, not templated generic "are these causally related" without observed relation, not literal internal `presenter_local` in user question. LLM can draft when authorized, otherwise send batched event graph to ChatGPT for original QA authoring. Keep answer unknown if unverified.
- Create **blind review package with only truly distinct, question-answerable items**; select at most one per semantic evidence-family plus some uncertain controls. If fewer than 8 reviewable items exist, deliver honest n and keep production running. **Do not pad to 8 with duplicates or UNKNOWN.**
- Keep a random sample of low/medium quality proposals for auditing false negatives, and hold aside unseen video IDs for final sealed evaluation. Existing exposed videos are DEV_CONSTRUCTION.
- Make run_002 **unit of yield** = distinct, video-grounded, answerable candidate families **newly produced** / time / processed videos, separate from total curated fixtures. Report actual funnel drop-off stage by stage and time cost.

### Concrete acceptance tests
1. `test_duplicate_question`: pairs [0004,0005] and [0006,0007] collapse; at most 6 distinct questions from run_001.
2. `test_event_qa_alignment`: 0005 flagged because source intro NOR Ndure conflicts with stated USA Gay.
3. `test_true_blind_packet`: B-only JSON does NOT have A media path, A event IDs, or full required_windows, nor gold/provisional answer, audit score, proxy necessity.
4. `test_provenance_metrics`: all 13 seeded semantic events labeled imported/curated, 0 new machine semantic discoveries in run_001; 3 new videos only coarse/seed observations.
5. `test_masked_qa_honesty`: no claim of actual video model A/B/AB inference if the grader was only rule proxy.
6. `test_resume`: per-video cache resume reconstructs all evidence, not only events, and counters remain correct.
7. `test_new_video_generalization`: removing the hardcoded CURATED mapping should still permit discovery of at least one *genuine new* semantic event on unseeded video via the chosen perception/batched-ChatGPT path, or the result must explicitly report `BLOCKED_NO_SEMANTIC_EXTRACTOR`; do not hallucinate.

**Track B deliverable**: `track_b/batch_factory/RUN001_AUDIT_AND_RUN002_REPORT.md`, run_002 artifacts and corrected genuinely blind small human-review packet. Do not wait for user answers to continue further construction.

## Track A — execution correctness blocker, not score chase
Confirmed by `program_execution.py`: all arms incl oracle-gold-schema score `execution_answer_accuracy=0.333` on 6 tiny tasks; report `abstention_rate=1.0` across all arms. Inspection shows:
- missing-evidence case credits answer if `pred is None` even without an explicit calibrated abstention decision;
- compare code can inspect `world.facts` directly in fallback instead of only observations/execution outputs, which is a scorer/agent-boundary risk;
- selection weights are tuned on labels, not trace correctness.
Next A effort **small**: fix scoring/trace semantics before method invention. Scorer obtains gold answer; executor sees only observations. `ABSTAIN` credit needs explicit evidence-missing policy, not null output. Compare must execute state ordering from tool-visible records and log provenance; never check oracle world in agent-side fallback. Run negative mask/swap tests and report actual per-operation success, program execution correctness and refusal behavior. Keep strong static selector, fixed binding negative baseline and held-out policy; no expensive RSI.

**Track A deliverable**: `track_a/TRACK_A_EXECUTION_SCORING_INTEGRITY.md`, tests and minimal corrected traces. No claim of improvement or real-video generalization.

## Human participation plan
The user has explicitly volunteered to help. **Do not ask them to review the current run_001 pack** because it leaks A/B and includes duplicates. After hardening, create a small **one-shot batch** (ideally 6–10 distinct reviewable cases) with actual playable media. Let user judge after automated candidate production; reviewer decisions are valuable **calibration signals**, not a gate that blocks next batch.
No automatic SUPPORTED; `UNASSIGNED`; sealed untouched; `ok_for_expensive_rsi=false`.

## Research judgment
The valuable deliverable here is **the first measurable factory skeleton and an unusually clear failure audit**. We need **actual open-video semantic discovery and calibrated automatic triage** before claiming a scalable Benchmark-creation method. A negative result in run_002 is acceptable if reported with a precise blocker and a reproducible recovery path; a high made-up QA count is not.
