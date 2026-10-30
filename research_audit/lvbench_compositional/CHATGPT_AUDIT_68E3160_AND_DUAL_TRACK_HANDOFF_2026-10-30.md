# CVPR2027 — ChatGPT audit of 68e3160 and next dual-track handoff
Date: 2026-10-30
Cursor commit audited: `68e316032ab97edb63e111c865b6f8d04cd8f302`
Companion ChatGPT source: `track_b/CHATGPT_VIDEO_EVIDENCE_ADJUDICATION_2026-10-30.jsonl`

## What was actually checked
Reviewed Cursor commit, `track_a/TRACK_A_BIND_FAILURE_TAXONOMY_AND_PARITY.md`, `track_a/PROGRAM_SELECTION_DESIGN_NOTE.md`, `track_a/bind_failure_taxonomy.json`, `binding_loop.py`, and original B video-design hypothesis files. Independently **visually inspected** GitHub images:
- `track_b/chatgpt_review_assets/Z86xysw5Ncc/board_stills/t_5_27_crop.jpg`, `t_5_30_crop.jpg`, `t_5_25.jpg`.
- `track_b/chatgpt_review_assets/VTCDQYYKA9o/event_stills/later_t_4_30.jpg`, `later_t_4_50.jpg`, `later_rally_0330_0555.jpg`.
- `track_b/chatgpt_review_assets/T1yhBv1ytzw/{liv_attack_origin_2955_3010,bha_attack_origin_3848_3912}.jpg`.
- `track_b/chatgpt_review_assets/CG-NEW-002/hunt_0505_0730_5s.jpg`.
No actual gitignored MP4/WAV was played, and tests were not independently rerun. All interpretations of motion, speech, goal kick origins remain provisional unless visually unambiguous.

## Scientific readout
**Track A:** Matched initial threshold .25, budget 6: matched_static, matched_tece_evolve and strong_fixed_rebind all score **0.500** on frozen four-task regression. Previously TECE=0 vs fixed=.5 was an **initialization confound** (Top-1 gold scores .345/.389 rejected by initial threshold .45 with no recovery), not evidence TECE search necessarily worse. Independent 24 scenarios show stronger fixed rebind dual_acc=.800 against weak init .000, which supports a useful static rebind primitive, not new structural generalization. The current policy evolves threshold/recovery, not DAG discovery. **No TECE advantage demonstrated**; preserve matched negative result and gate `ok_for_expensive_rsi=false`.

**Track B:** New extraction activity is extensive but still lacks independent continuous-video adjudication for kick type, scorer, early table push, animal barking, etc. Avoid another open-ended round of nearly identical JPEG grids. Make bounded accept / revise / weak-control / reject decisions for each candidate rather than accumulating PENDING forever.

## Important factual corrections from direct review
### Z86xysw5Ncc — the purported result panel is a START LIST
At file 05:25–05:30, overlay explicitly reads **`MEN'S 100M — START LIST - ROUND 1 HEAT 2`**, not finals and not an outcome/result table. Clearly lists (among others) USA **Justin Gatlin**; earlier introduction panels show **Tyson Gay** and **Jaysuma Saidy Ndure**. These frames cannot provide finishing order, medal, or race placement; they may be from distinct heats/intro events. Immediately correct any `result_board` or `finish_rank` claim derived from this overlay in review metadata; retain original frame path/history and correction provenance. Keep the *source filenames* unchanged if renaming would break links; change semantics in annotations.
Possible low-complexity control question: `画面早先介绍的美国运动员，与后来 Round 1 Heat 2 名单里的美国运动员，是同一人吗？分别是谁？` Candidate (not formal): `不是；Tyson Gay vs Justin Gatlin`. Text-overlay + event-boundary contrast only, not high-value strict unseen.

### VTCDQYYKA9o — 'PREVIOUS RESULTS', not current score
At ~04:30 overlay says **`PREVIOUS RESULTS / CHN FAN ZHENDONG`**, listing *prior rounds*. It does NOT convey current match winner or instantaneous score against Ma Long. Around 02:46–03:00 earlier sequence shows red jacket and white towel, then blue/yellow jersey; later ~04:30 player in blue/yellow with Fan Zhendong overlay.
New independently designed candidate in `track_b/CHATGPT_VIDEO_EVIDENCE_ADJUDICATION_2026-10-30.jsonl`:
> `后来画面用“PREVIOUS RESULTS”介绍的那位蓝黄色比赛服运动员，在较早的场边准备阶段先脱下了什么颜色的外套？`
Candidate answer: **red**. This is classic cross-time reidentification/reverse query (not groundbreaking higher-order composition), suitable for blind A-only/B-only/A+B and a development QA if full continuity verifies person identity. Do not use previous-results 4–0/4–1 as current score.

### Football T1yhBv1ytzw — do not manufacture goal-type labels
Current GitHub sheets at 1fps show 0–0→0–1 LIV→1–1 BRI score sequence and attacking passages; both live/replay have been separated. Yet neither clearly establishes the exact starting play classification nor the true final touch/scorer under rigorous review. Existing `CG-SPORT-DESIGN-001-REFINED` stays `HYPOTHESIS_NOT_SUPPORTED`, gold=null. NOTE: B-only seeing pre-equalizer score 0–1 may **already reveal Liverpool scored before Brighton**, creating a partial order shortcut. A multi-clause two-goal description could be mere conjunction, not a novel graph. Do not award strong compositional credit without independent minimal-witness and counterfactual checks.

### CG-NEW-002 — cut losses on table push without proof
The 05:05–07:30 5-second grid shows confrontation, hat-wearing character and closeups, **not an unambiguous table-push**. Original UID 61 is a guide only. One narrowly targeted independent full-motion review may be justified; if absent, revise or retire the claim rather than extract more copies of the same range.

## Track A | next bounded work (about 30% effort)
1. Freeze four-task suite as negative-control regression. Preserve `matched_budget_parity.json` and full failure traces.
2. Implement a **small executable question-conditioned program selector** rather than another threshold sweep. Compare genuinely distinct DAGs: (i) A→bind→B property, (ii) B→bind→A prior event, (iii) compare/order two independent state transitions, (iv) missing-evidence/abstain (audio branch optional only if real audio observations exist). Distinguish `oracle_program_upper` from selected program; withhold target graph from selector training and evolution.
3. For new scenario generator: several independent stories/entities, randomized role surfaces, distractors, noisy cues, both source directions and explicit evidence groups. Do not leak graph template via `task.kind`, synthetic file identifiers, or oracle scene roles.
4. Match initial genome, candidate budget, tool calls, selection dev and frozen test; include fixed planner, static strong policy, random, vanilla, proposed selector/evolver. Report **program choice accuracy** and strict necessity separately; allow no-win. Do not call this RSI if only a supervised selector is fitted and no harness evolution occurs.
5. Deliver `track_a/TRACK_A_PROGRAM_SELECTION_FEASIBILITY.md` + executable tests/trace. No expensive RSI.

## Track B | next bounded work (about 70% effort)
1. **Immediately correct overlay semantics** in local metadata and preserve corrections in separate provenance: athletics `START LIST - ROUND 1 HEAT 2`, TT `PREVIOUS RESULTS`.
2. **Prioritize one fully verifiable new QA** using already visible facts: TT red jacket → blue/yellow jersey → named competitor, with targeted *continuous* 02:43–03:06 and ~04:25–04:35 review; evaluate exact A-only/B-only/A+B and possible role/model shortcuts. Store separately from raw QA versions. If the asset does not prove identity, leave `PROPOSED_REVIEW_REQUIRED`, not `SUPPORTED`.
3. **Football stop gate:** ask one blind human to view `liv_live_attack_2955_3015.mp4` and `bha_live_attack_3848_3915.mp4` (local). Collect timestamped ball actions and uncertainty. If attack origin still cannot be stated confidently, **deprioritize CG-SPORT-DESIGN-001**, keep score-trajectory as proven descriptive fact but do not treat as strong composition.
4. **Athletics stop/revise gate:** the current late board is a start list, not outcome. Search for distinct, legible actual finish/result overlay only if video evidence metadata suggests it exists; otherwise demote to text/event-boundary development control and stop re-extracting the same start-list.
5. CG-NEW-001 exact hug, CG-NEW-003 bark, CG-NEW-002 table push: one targeted **continuous-video** adjudication each if media accessible. Mark `EVIDENCE_UNRESOLVED` / `REJECT_OR_REWRITE` if not, instead of repeating dense sampling. Static JPEGs cannot prove sound or fine motion.
6. **Keep B full-benchmark line active:** event-first discovery on additional diverse construction videos; build minimal witness sets and signature taxonomy; maintain untouched final sealed pool outside public assistant method design. A prompt rewrite with two independent atomic answers is not a new structure.
7. Implement a **formal candidate funnel** with `SOURCE_VISUAL_FACT`, `VIDEO_REVIEWED_FACT`, `COMPOSITION_QA_CANDIDATE`, `STRONG_COMPOSITION_VALIDATED`, `DEVELOPMENT_CONTROL`, `REJECTED_OR_UNRESOLVED`. Keep legal existing statuses (PROPOSED_*, UNASSIGNED, SUPPORTED) untouched; new funnel is a **parallel audit view**, not silent schema changes.

## Explicit bounded deliverables
**A**: realistic new program-selection synthetic task + neutral held-out graph, failure traces, true parity; no performance claim or payment.
**B**: visual overlay correction record, one adjudicated TT QA, football/athletics accept-or-stop decision with evidence, next varied construction-video fact batch. Include direct review media paths/checksums, disclose what was human-watched vs inferred from stills.
**Shared**: Commit/push and report SHA; no automatic `SUPPORTED`; all exposed samples `UNASSIGNED`; no sealed-test access; `ok_for_expensive_rsi=false`. Do not make up a next task when evidence is unavailable.
