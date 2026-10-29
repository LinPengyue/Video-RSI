# CVPR2027 | ChatGPT audit of 6fe9181, direct image review, and next dual-track actions
Date: 2026-10-29
Reviewed commit: `6fe918161363bbef5d38a09e78fb910703f59826`
Sources: Track A stress report, split witness, `evolution_loop.py`, `necessity.py`, `program_schema.py`, `noisy_obs.py`, Track B review manifest, and six actual JPEG contact sheets fetched from GitHub as base64 and visually inspected. GitHub videos/MP4 and audio were **not** independently watched or heard in this audit.

## 0. Scientific readout
- Historical synthetic 1.00/1.00 result from commit 77d524c is **invalidated as evidence for structural generalization**.
- With currently reported controls, no unique semantic-performance advantage is demonstrated for TECE; fixed-rebind/random/vanilla reach about 1.0 and TECE averages 0.967 across 20 seeds. However all baselines with oracle-ID recovery also need reevaluation before a trustworthy head-to-head.
- Strict compositional success is **0 for all arms**; **this is a failure of the present evaluable task/protocol**, not evidence that all models fundamentally lack compositional ability. Some independent necessity values are nonzero but path-validity combined score remains zero.
- Track B contact sheets enable limited new *visual* judgments, not full audio or video fact verification.
- Keep `ok_for_expensive_rsi=false`, no H_S1 final judge, no sealed test leakage, no automatic `SUPPORTED`.

## Track A | high-priority protocol defects to fix, not synthetic-score chasing

### A1. Declared hash vs *actually executed* trace
`split_witness.json` hashes **declared `ProgramSchema.graph_payload()`**. `_program_for_task()` in `evolution_loop.py` prefers the **genome `op_order_template`**, which may execute almost identical op sequences across forward and held-out reverse/AV tasks. A fixed per-task graph hash is not proof that the runtime actually executes that graph. The AV schema's `locate_event` may use a visual-text cue, not an independently grounded audio operation.

**Next work**: record per-task `declared_schema_hash`, `compiled_program_hash`, `executed_trace_hash`, operation arguments and modality provenance. Show that reverse/AV dependencies are genuinely realized at runtime, not only in metadata. Do not automatically require test *trace* hashes disjoint after execution (successful generalization can reuse primitives); enforce disjoint *intended dependency structures* and verify runtime fidelity to intended graph.

### A2. Neutral A-only/B-only masking
In `necessity.py`, B-only evaluation not only removes A interval facts but also strips referring cues from B facts and mutates world entity surface names / aliases, potentially making B-only artificially harder than it is. A-only also assumes 0..10 early and B-only >=20, which is brittle for reverse-time tasks. This breaks the premise 'same question, only remove one source'.

**Next work**: define per-task explicit evidence groups `A`, `B`, plus global allowed context; independently execute **exact same question** under A-only/B-only/A+B while changing **only exposed observations**. Do not rewrite the question, entity alias lexicon, answer schema or distractor set. Randomize which chronological source carries the referent. Add controls where B-only is sufficient even though A→B link exists, and where both A-only/B-only fail but A+B succeeds. Report causal necessity separately from semantic correctness and evidence-path validity.

### A3. Eliminate oracle-leak *by construction*
`project_observations` deepcopies a `SimulatedWorld`; visible facts still carry `entity_id` that originated in oracle, and `_maybe_recover` can bind to `fact.entity_id` after locating. Leak flagging alone does not remove privileged info. Same `entity_x/entity_y` IDs reused across world families.

**Next work**: create a separate **observation type** without oracle entity IDs, gold fact IDs, gold property values and target answers. Use per-scenario ephemeral detection/track IDs and noisy linking hypotheses. Oracle graph goes only to scorer. Assert agent interface cannot access oracle fields, even via recovery/reflection/cached state. Then rerun the same-budget controls. If TECE advantage remains absent, report that negative result without tuning to win.

### A4. Robust evaluation and true mechanism evolution
- Add static recovery baselines with **oracle-free** observations.
- Separate strong fixed policies from budget-matched evolved ones.
- Increase generated test **scenario diversity** (existing 3 synthetic structural test tasks repeatedly reused across 20 seeds). Test variations across number of entities, direction, modality presence, unseen distractors, absent A, missing B, misleading labels and answer location.
- Avoid claiming audio-visual reasoning until distinct audio observations affect execution.
- Frozen base-model video calls remain blocked; run only cheap synthetic protocol checks.

**Required A output**: `track_a/TRACK_A_ORACLE_FREE_CAUSAL_AUDIT.md`, executable tests, and oracle-free ablation tables. A negative/equal result is acceptable. Do not create a new method label without demonstrating an actual incremental mechanism.

## Track B | direct visual audit of six committed contact sheets

**Source limitation**: These conclusions are from static composite JPEGs; they are stronger than Cursor's unverified descriptions but **not** proof of exact video actions, audio content, or successful blind necessity checks. Keep `source=CHATGPT_VISUAL_CONTACT_SHEET_AUDIT`, no `VIDEO_FACT_VERIFIED` without continuous-video review.

### CG-NEW-001 / TB-003 — role-to-instrument
- **05:15–05:35** sheet: green dragon foreground in royal scene; a short-haired blonde child wearing purple stands close to / touches the king; another blonde girl in pink is present. The 'embraces king' event is plausible but the exact temporal verb sequence is not established by a still composite.
- **20:00–20:20** sheet: blond child in purple visibly behind a drum kit, long-haired blond child in pink plays a purple string instrument; green dragon also appears in some frames of this later window.
- **Assessment**: visual cross-interval role/wardrobe/instrument match is **plausible** and strong for follow-up; precise object identity and causal dependence remain pending. The green dragon's reappearance is a newly noticed **scene-presence observation** that can motivate a multi-actor design, but do not claim the dragon performed music.
- Priority: obtain brief continuous visual evidence around hug and performer entrances; blind A-only/B-only/A+B on exact canonical question.

### CG-NEW-002 / TB-007 — snow-to-restaurant reverse event
- **04:19–04:55** sheet: an armed man points a gun indoors, another person in dark clothing and a broad-brimmed hat appears, and a tabletop/pot is seen. **The actual table-push and stand-up sequence is NOT clearly established by these eight sampled stills.**
- **49:55–50:15** sheet: snow scene with fallen figure, snow/hand contacting face visible in several frames; multiple other characters are present.
- **Assessment**: reverse-time QA remains **PENDING_EARLY_ACTION_TIMECODE**; potential role disambiguation, but cannot certify the early reaction from shown contact sheet. Need precise frames within full original UID 61 interval 04:19–08:41 and a character-identity match across scenes, otherwise initial question is unsupported.

### CG-NEW-003 / TB-006 — dog audio+visual
- **00:20–00:45** sheet: in last 3 of 8 frames a **clearly discernible black/white dog** on hillside by a tree approaches camera; earlier 5 frames show broad autumn landscape. Hence prior claim that early interval is **visually unrecognizable** is no longer correct for the new extended window.
- **02:03–02:45** sheet: two people collecting beech nuts in leaf-litter (one frame has text 'Beech nuts'); black/white dog appears near one collector's feet in late frames.
- **Not yet established** by stills: dog actually plays with wood earlier, dog vocalization, or strictly same individual across clips. Matching broad coat pattern is supportive but not definitive.
- **New observable visual candidate**: 'earlier the black-white dog moves from farther up the slope toward the camera; later a black-white dog is near a person collecting nuts' — only candidate until continuous clip shows movement and identity.
- Do **not** mark AV condition as verified or include dog barking as an answer key until separately listening to audio; `AUDIO_NOT_AUDITED`.

## Track B | construction and sealed final
- The canonical five remain `PROPOSED_*` and `UNASSIGNED`. Do not inherit old TB single-clip answers for revised questions.
- **Immediate step**: integrate these *image-level* audit notes into a separate `contact_sheet_independent_review.jsonl`, with `source=CHATGPT_VISUAL_CONTACT_SHEET_AUDIT`, never overwrite source descriptions.
- For CG-NEW-002 request correct timestamped original interval with the table push, NOT simply more adjacent generic footage.
- For CG-NEW-003, separately verify dog voice on continuous audio and the wood action from video; allow separate visual-only candidate if audio unconfirmed.
- For CG-NEW-001, explore an **additional video-first event hypothesis**: the same green dragon appears in early royal scene and later performance window. Ask what new combination operation this enables only after event/cast continuity check; don't auto-mint a QA.
- In parallel, select ≥5 never-discussed videos for **development of new video-grounded facts** across different genres. New video used for assistant-led design becomes construction/dev data, **not** automatically part of sealed blind final. Keep a separate untouched sealed reservoir managed without exposing its clips/questions/answers to method design.
- Be pragmatic about exchange: text/JSON/JPEG contact sheets via GitHub; full clip/audio with safe agreed media access or user upload as necessary. Don't claim GitHub gitignored local media is accessible to ChatGPT.

**Required B output**: reviewed visual notes JSONL, a prioritized short list of precise video segments/uncertainties, initial observation windows on genuinely new construction videos, a separate sealed-pool split policy; NO automatic `SUPPORTED`.

## Independence and decision gate
A: require clean oracle-free observation interface, neutral masked necessity, runtime fidelity, then compare TECE vs equal-information static baselines. B: require actual video and audio where essential before facts can be graded as verified; use the new imagery to design novel relations, not longer paraphrases.
