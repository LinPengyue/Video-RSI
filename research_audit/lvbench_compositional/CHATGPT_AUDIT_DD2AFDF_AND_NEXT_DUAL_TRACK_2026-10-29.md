# CVPR2027 — ChatGPT audit of dd2afdf and next dual-track handoff
Date: 2026-10-29
Cursor commit: `dd2afdf858c56df52c2eacc7d4bc9e8607d77d8d`
Repo: `LinPengyue/Video-RSI`, branch `research/lvbench-comp-video-grounded-evidence`

## Evidence actually inspected
- `track_a/TRACK_A_ORACLE_FREE_CAUSAL_AUDIT.md`
- `tools/lvbench_comp/typed_evidence_contract/{oracle_free_loop.py,observations.py,oracle_free_executor.py,necessity.py}` by GitHub connector.
- `track_b/{construction_video_pool.jsonl,construction_observation_seeds.jsonl,SEALED_POOL_SPLIT_POLICY.json,PRIORITY_VIDEO_VERIFICATION.md}`.
- **All 10 GitHub JPEGs** under `track_b/construction_discovery_assets/` directly fetched and inspected visually (5 videos × 2 frames).
- This audit did NOT replay local MP4/audio, independently run the repository test suite, or verify whole-video event timing.

## A. Research conclusion from 20 seed run
Reported oracle-free test semantic mean: Fixed=0.667, Fixed-rebind=1.000, Random=0.333, Vanilla=0.333, TECE=0.300. All strict composition=0. Reported oracle-id leak=0, declared/compiled schema fidelity=1.0. **Negative result accepted.** Do not claim TECE improved across unseen composition, and do not tune a toy experiment to force an advantage.

### A1. Hidden ground-truth cross-time bridge remains
In `observations.py:project_oracle_free`, `oracle_to_track[oid]=tid` is formed once, and **the exact same `track_id`** is assigned to every ObsFact in A and B for an oracle entity. This exposes the correct cross-scene identity correspondence to the agent despite removing the literal `entity_x` key. Thus, `oracle_leak_rate=0` verifies absence of the *literal oracle entity_id*, not absence of privileged **identity-link information**. `observed_value=f.property_value` also provides error-free ground-truth readout in the main suite.

**Required fix**: separately generate *A-local* and *B-local* ephemeral detection/track IDs, with distinct local IDs after camera cuts, appearance changes, and elapsed time. The correct cross-window match must exist **only in scorer oracle**, not prewired into observations. Provide noisy image/feature/attribute cues and distractors, on which a true binding operation must infer possible matches and uncertainty; randomize IDs, appearance and candidate ordering. Add adversarial tests showing binding is impossible from local IDs alone.

### A2. Necessity still partly measures reference metadata
`mask_observations()` removes facts but retains `ObservationBundle.entities` with global `surface_forms` derived from the original oracle entity descriptors; thus B-only may still access the A-specific name/role as globally visible metadata, despite no Fact A. Do NOT restore biased name stripping; instead model scene-local observations consistently and define a *neutral base context* identical across A-only/B-only/A+B, containing only independently available information. Test both (i) truly necessary two-source tasks, and (ii) B-only shortcut tasks. Do not use answer text in detection features.

### A3. Structural fidelity is not autonomous harness program discovery
`OFTask.force_schema_program=True` for tasks and `compile_program()` uses task schema, ensuring fidelity, but also forces the task-specific **answer/program structure** into the agent. A method that receives target reverse/AV operation DAGs precompiled at evaluation cannot claim to have *discovered* that program from Seen experience. Distinguish (i) **oracle task program execution** (diagnostic upper-bound), (ii) **program selection** from question+observations, and (iii) **Evolver-discovered transferable execution policy**. The held-out program schema is allowed to exist in the test generator/scorer, not supplied as an oracle plan to the tested agent for a genuine transfer claim.

### A4. Twenty seeds are not many independent test tasks
`build_of_split()` contains three held-out task definitions and a handful of fixed oracle families; changing evolution RNG seeds gives variance in search, not statistical coverage of unseen compositions. Increase independent synthetic scenarios, entities, distractors, temporal and modality noise; randomized train/dev/test examples and disjoint families. Report per-task generalization and paired effect vs oracle-free static-rebind, not just 20-seed CIs.

### Track A next deliverables (small, finite scope)
1. `observations_v2.py` scene-local track IDs and uncertain cross-scene match evidence; tests forbidding direct oracle-bridge.
2. Clean three-way mask controls using truly source-local entity lists and identical public context; construct ≥2 tasks **known by generation** to require both sources and ≥2 B-only shortcut controls, confirm predicted necessity distinguishes them.
3. Split **Oracle-Program upper bound** from program-selection baseline and evolver policy; no forced test schema in agent path for transfer experiment.
4. Cheap, oracle-free matched-budget ablation and failure trace. If all arms poor or TECE worse, log it. No expensive RSI; `ok_for_expensive_rsi=false`.
5. Output `track_a/TRACK_A_CROSS_SCENE_BINDING_AUDIT.md`. Keep Track A active but do not invent a new branded method while evidence inadequate.

## B. Five newly inspected construction videos — direct visual observations only

**These are NOT verified multi-frame action facts and NOT formal QA.** Register in new `track_b/chatgpt_construction_visual_audit.jsonl` with `source=CHATGPT_GITHUB_STILL_IMAGE_AUDIT`, explicit absolute timestamps and GitHub source links.

1. **JPPMz8fEml0**, UID2963 at **01:00.150**: indoor shot of a bearded man gesturing with both hands and a headscarf-wearing woman sitting nearby. At **01:18.150**: wide aerial shot of a dense city. Potential multi-shot narrative relation, but city identity, destination relation and who filmed it are UNKNOWN. Request continuous 00:55–01:25 with audio/subtitles; prioritize only if actual place or causality can be independently established.

2. **QWXlvx1GoTY**, UID2463 at **41:55.150**: bearded male presenter and a Cisco Live slide with questions including upgrading infrastructure and security. At **42:13.150**: close-up smiling presenter. Candidate **slide–speech temporal grounding**: does the spoken response explain one slide question, and what concrete solution follows? Need 41:45–43:15 continuous footage/audio/subtitles plus slide transitions; do not mint an answer from a static deck.

3. **Z86xysw5Ncc**, UID4197 at **02:18.900**: on-screen Norway flag/runner caption `Jaysuma Saidy Ndure`; at UID4199 **03:47.950**: red-uniform athlete bent over, **identity not proven** from frame. Potential multi-competitor race positioning, event-order and athlete re-identification; need 02:05–04:10 scoreboard + running footage and UID event intervals, not name-swap. Do not assert both frames show same athlete.

4. **VTCDQYYKA9o**, UID4083 at **02:42.000**: red-shirt table tennis athlete leaning over behind arena barrier; at **03:00.050**: blue/yellow-shirt player leaning over in a similar bench-side area. These appear to be **different players**, not a single-person state change. Potential competing-roles / game-state transitions if score and subsequent rallies available. Need 02:30–03:30 continuous score, players and next serve/rally. Cannot infer actions besides leaning from stills.

5. **T1yhBv1ytzw**, UID3785 at **29:49.800**: football broadcast scoreboard **BRI 0–0 LIV**, broadcast game clock 29:37; UID3789 at **42:21.150**: broadcast scoreboard **BRI 1–1 LIV**, game clock 42:08, player back `DUNK 5` in foreground. **Most promising new factual relation**: scoreboard changed 0–0→1–1 over an interval; winner/order of goals NOT deducible from only two stills. Construct a **state-transition/causal-chain question hypothesis**, not an answer:
   > `从 0–0 变成 1–1 的过程中，哪一方先取得领先，另一方随后通过哪次进攻扳平？`
   Expected answer: `UNKNOWN_PENDING_GOAL_EVENT_VIDEO_REVIEW`; do NOT guess. Need locate both goal moments, scorer/assist, score overlays, and whether 1–1 sequence is contemporaneous with these timestamps (clip game-clock vs file timestamp). Consider more diagnostic variant: identify two score changes from observed plays, not simply read final scoreboard; if only the final scoreboard is needed, tag as shortcut/control.

### Track B next concrete video-first task
- **P0: Football T1yhBv1ytzw**: extract **goal-event windows and score overlays** (broadcast game time between 29:37 and 42:08; map to video clock), plus a few seconds before/after both goals. Report exact goal order and scorer only after independent review. This is highest-potential new composition **state trajectory + causal event**.
- **P1: VTCDQYYKA9o**: examine whether two different bent-over athletes are preparing for service, between-game break, or recovery; identify preceding/following rally and scoreboard before designing a comparative condition→outcome QA.
- **P1: Z86xysw5Ncc**: inspect contestant identification, early/late camera cuts and actual race result/placing; focus multi-runner disambiguation, no assumed identity.
- **P2: QWXlvx1GoTY**: if audio/subtitles available, do slide→spoken explanation; otherwise deprioritize (text-only shortcut).
- **P2: JPPMz8fEml0**: use wider city/people narrative context only if continuity verified; otherwise deprioritize as ungrounded geography.
- Also finish previously required P0 CG-NEW-001/002/003 continuous video/audio verification when media available, not at cost of indefinitely delaying independent-video discovery.
- For each confirmed new local fact, record `fact_id`, `visual/audio evidence`, `exact original time`, `raw question not yet written`, `multiple plausible operations`, `single-interval shortcut risk`, `human_review_state`.
- Preserve sealed pool **untouched**, all exposed construction videos `DEV_CONSTRUCTION`. These current five cannot enter true blind final.
- Ship contact sheets with multiple time-indexed frames **covering the new causal interval**, not just single UID thumbnails; small JPEG via GitHub, full MP4/audio local with explicit availability. Do not hallucinate unobserved speech, goal events, race placements, outcomes.

### Proposed research-quality criterion for new B questions
A newly designed question qualifies as *composition candidate* only if there is a **minimal witness set of ≥2 actually necessary observed event facts** AND a mechanism not already fully restated in original QA, with A-only/B-only/A+B and counterfactual subject/event controls. Question difficulty or word count is irrelevant. Document unknowns as unknown.

## Shared gate and handoff
- Preserve all canonical CG-NEW mappings and TB human review. All pending; no auto `SUPPORTED`.
- Cursor should first implement A local-ID/no-oracle-bridge tests and B target video extracts **in parallel**, with independent reports. No expensive RSI or method claims.
- Commit/push SHA; give paths for the new image-review manifest and scene-local observation tests.
