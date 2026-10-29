# CVPR2027 — ChatGPT audit of 66b01db and next parallel A/B handoff
Date: 2026-10-30
Audited Cursor commit: `66b01dbe19645cd81fcff56cb0e36c6eba17d351`
Canonical research branch: `research/lvbench-comp-video-grounded-evidence`

## Verified inputs and limitations
- Read `track_a/TRACK_A_CROSS_SCENE_BINDING_AUDIT.md`, `observations_v2.py`, `binding_executor.py`, `binding_loop.py`, `test_cross_scene_binding.py`, and `track_b/T1yh_GOAL_WINDOW_EXTRACTION.jsonl`.
- Actually visually inspected GitHub dense JPEGs: `T1yhBv1ytzw/{scoreboard_29_to_43_every15s,liv_candidate_dense,bha_candidate_dense}.jpg`, `VTCDQYYKA9o/vtcd_0230_0330.jpg`, `Z86xysw5Ncc/z86_0205_0410.jpg`, `CG-NEW-001/hug_dense_0515_0535_contact.jpg`, `CG-NEW-002/table_push_hunt_0419_0841_contact.jpg`.
- Did **not** watch gitignored full MP4 files, hear the newly extracted CG-NEW-003 WAV, or independently execute the code tests. New visual conclusions below are **CONTACT_SHEET_VISUAL_AUDIT**, not `VIDEO_FACT_VERIFIED`.
- ChatGPT's new structured design/observation file: `track_b/CHATGPT_VIDEO_DRIVEN_DESIGN_2026-10-30.jsonl` (6 rows, 2 alternate football hypotheses over the SAME events, plus visual notes). Do not inflate dataset count by counting alternative wordings as independent facts.

## Track A — critical remaining oracle-information leakage despite scene-local IDs
### A0. Reported result / correct interpretation
Cursor reports on 15 seed trials: Fixed-rebind 0.500, TECE 0.267, Random and Vanilla 0.333, Fixed 0.000; 4 fixed synthetic test tasks (two dual_necessary and two B-only shortcut); 'bridge_ok=1.0'. That last column is produced by `assert_no_oracle_bridge(bundle)` and only checks **A/B ID-set intersection is empty**, NOT whether any inferred A↔B correspondence is correct. Rename to `local_ids_disjoint`, and report separate `pair_accuracy`, `top1/topk_pair_recall`, `pair_score_calibration`, and target-query accuracy. This 15-seed run primarily changes mutation/search RNG over a small fixed synthetic task set; it is not 15 independent unseen compositions.

### A1. Soft score uses GOLD identity labels — direct leakage
`observations_v2.py:135–158`:
```python
gold_matches = [(a_map[oid], b_map[oid]) for oid in oracle.entities]
correct = (a_tid, b_tid) in gold_matches ...
score = 0.2 * overlap + (0.5 if correct else 0.0) * (0.4 + 0.3 * rng.random())
```
The **agent-visible link score is explicitly boosted when a pair is the oracle-correct pair**. This violates the claim that the cross-scene match exists only in the scorer. It remains oracle-information leakage even though the actual `a_*` and `b_*` track strings differ. The comment 'Score from cue overlap only' contradicts the code.

Required: compute link hypotheses solely from observable synthetic detector features/cue similarity, noisy appearance, and reproducible random distractors. It is fine for the *generative world* to create appearance cues correlated by identity; it is **not** fine to use gold `correct` as an extra term in the agent-visible match score. Test: hold observed features fixed and **permute gold matching/scorer labels**; agent-visible hypotheses/scores and predictions must be bitwise invariant.

### A2. Surface names also encode the same oracle identity suffix
`observations_v2.py:100–108` creates `person_in_A_{oid[-1]}` and `person_in_B_{oid[-1]}`, e.g. `A_x` and `B_x`; these are independently scene-local *names* but the shared suffix is a direct naming correspondence. Replace with independent random local label vocabularies with no shared oracle-derived suffix, and ensure agent predictions are invariant under independent A/B local-ID renaming. Remove any substring/name equality signal across scenes unless deliberately generated as an actual public visual cue.

### A3. Evolution remains a narrow policy tuner
`binding_executor.CrossSceneBindingExecutor.run_pipeline()` uses the same **resolve-A → bind → query-B → verify** sequence in `program_selection` and `evolver_policy`. These names do not by themselves mean that a program is selected from question evidence; current mechanism appears to evolve recovery/threshold, not genuinely discover diverse execution programs or reverse/AV DAGs. Keep `oracle_program_upper` separate; implement a small program-selection task set in which different task semantics actually require different executable DAGs, or explicitly label results `binding_policy_evolution_only`.

### A4. New rigorous local tests (cheap)
1. Score-label permutation invariance with observations frozen; no gold-conditioned match score.
2. Independent scene name/ID permutation invariance.
3. Adversarial lookalikes and low-quality cues with top1/topk entity pairing accuracy measured separately.
4. B-only shortcut and both-sources-necessary controls with scorer-independent masking.
5. Different held-out task **graphs and scenario instances**, not just changing answer strings under one forward action schema.
6. Equal information, initial harness, search and call budget; preserve negative results.

Deliver `track_a/TRACK_A_GOLD_SCORE_LEAKAGE_FIX.md`, `track_a/scene_local_binding_fair_ablation.json`, tests. Keep `ok_for_expensive_rsi=false` and no real-video generalization claim. Do not force a TECE advantage.

## Track B — dense-sheet visual findings and original QA design

### B1. Football T1yhBv1ytzw: strongest grounded state trajectory yet
My independent visual reading of the three GitHub dense JPEGs supports:
- File ~29:45 board shows BRI 0–0 LIV.
- File ~30:10–30:30 red players celebrating; `ELLIOTT 19` jersey is visible; **this by itself does not prove Elliott scored**. Replays/attacking sequence are shown ~30:32–31:12.
- File ~31:30 board BRI 0–1 LIV.
- File ~38:40 board BRI 0–1 LIV.
- File ~38:50–39:10 crowded box / set-piece-like attacking play, followed by Brighton shirts celebrating and replay sequences through ~40:12. **Set-piece/corner is a candidate, not confirmed via continuous video**.
- File ~39:40 board BRI 1–1 LIV; file ~42:15 still 1–1.

This establishes order of **score changes** from board overlays with much greater confidence than earlier 2 frames; it does **not** yet establish both scorers, assist sequence, final touch, or exact kick type. Distinguish **file time** vs **broadcast clock** and **live play** vs **replay**; a replay of one goal is not a new independent event.

A fresh assistant-designed question idea is in `track_b/CHATGPT_VIDEO_DRIVEN_DESIGN_2026-10-30.jsonl`:
- **CG-SPORT-DESIGN-001**: compare two score-changing attack sequences, identify which begins with set-piece conditions and order by score changes. Current gold is `null`, `HYPOTHESIS_NOT_SUPPORTED`.
- **CG-SPORT-DESIGN-002**: alternative wording over same events, NOT a second independent item.
Both may still be only conjunctive two-QA comparisons; reject if the actual video fails the pairwise/masking/contrastive necessity checks. **Do not invent striker names, goal technique or final-shot specifics.**

### B2. Table tennis VTCDQYYKA9o
Dense 02:30–03:30 contact sheet now visibly suggests one short-haired athlete initially in a **red outer jacket** and later in **blue/yellow playing shirt**, after removing/holding the red jacket ~02:50–03:00. A different black-purple kit wearer also appears from ~03:10. This supports **appearance-change + reidentification hypothesis** more than the former assumption that all bent-over figures were separate players. Need continuous clip, actual competition context and score; don't assert formal identity or rally outcome yet.

### B3. Athletics Z86xysw5Ncc
Dense 02:05–04:10 sheet shows introductions with on-screen names/countries including `Jaysuma Saidy Ndure (NOR)`, `Gay (USA)`, and `Thompson (TRI)`, followed by starting stances and sprint footage. Do not infer final placements from these panels. Potential future test: name/heat lane grounding → cross-angle tracking → outcome, but require race-finish video.

### B4. Existing CG-NEW
- CG-NEW-001 hug dense: 05:21–05:29 shows interactions among king, queen, short-haired purple-clothed child and pink-clothed child. Exact 'who embraces whom' should be **continuous-video adjudicated**; do not conflate adults/hugs.
- CG-NEW-002 04:19–08:41 10s sampled sheet shows confrontation but does **not** provide clear contiguous evidence of table-push and standup; need targeted motion / tighter 1–2fps short windows rather than huge sparse grid.
- CG-NEW-003 new WAV stays gitignored/local. **AUDIO_NOT_AUDITED** until independently listened to, and stick/wood action still requires continuous video.

### B5. Next Cursor actions, bounded
**P0:** two soccer goal windows with **timed key actions and kick origin**, live-vs-replay marker, score-boards anchors and two distinct A/B visual causal witnesses; visual/auditory evidence with precise timestamps. Run independent blind A-only/B-only/A+B on the *exact new question text*. Preserve the assistant-authored question and UNKNOWN gold until verification; final question can be rewritten after actual observed acts.
**P1:** table tennis 02:40–03:10 continuous garment removal and separate athlete appearance; follow-up rally scoreboard if available.
**P1:** athletics starting labels → lane map → finish (or clearly report unavailable).
**P1:** CG-NEW-001 exact embrace clip and CG-NEW-002 action seconds; reduce repetitive extraction if still absent.
**P1:** CG-NEW-003 audio independent listen (no auto transcription as sole ground truth).
**Parallel full B:** expand DEV_CONSTRUCTION across **new genres and videos**, catalog video-grounded facts/operation signatures, keep untouched sealed pool. Existing five videos are now exposed/development and cannot later be blind final.

Do not make `SUPPORTED` assignments automatically. Preserve `UNASSIGNED` statuses and TB human notes. Track B deliver `track_b/CHATGPT_DENSE_AUDIT_AND_NEW_QA_NEXT.md`, evidence timestamps, small review contact sheets and structured candidate records; do not batch name-swap QA.

## Handoff and stop rules
- A and B run independently in parallel; do not block B waiting for a TECE positive result.
- Research artifacts (MD/JSONL/metadata) via GitHub, large media remain local; private local WAV/MP4 not accessible from GitHub alone.
- No expensive RSI, no H_S1 sealed judge, no secret sealed test feedback.
- A negative or null result is acceptable; reproducible footage/event facts and honest test design are priorities.
- Finish with tests, commit/push and distinct Track A/Track B reports.
