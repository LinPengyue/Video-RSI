# CVPR2027 — Independent audit of 35ebad3 and next dual-Track execution
Date: 2026-10-30
Audited commit: `35ebad3f51a5278738cea99dc1f8edccd0eb2074`
Branch: `research/lvbench-comp-video-grounded-evidence`

## Sources and method
Directly inspected GitHub code `observations_v2.py`, `binding_loop.py`, reports `TRACK_A_GOLD_SCORE_LEAKAGE_FIX.md` and `CHATGPT_DENSE_AUDIT_AND_NEW_QA_NEXT.md`, `T1yh_DESIGN001_NECESSITY_CHECK.jsonl`, plus seven newly tracked JPEG contact sheets:
- `T1yhBv1ytzw/{liv_live_pre_2950_3014,liv_replay_mark_3030_3119,bha_live_3845_3919,bha_replay_mark_3910_4014}.jpg`
- `VTCDQYYKA9o/garment_0240_0320_1fps.jpg`
- `Z86xysw5Ncc/finish_probe_0405_0600.jpg`
- `CG-NEW-002/precise_0419_0505_1fps.jpg`
(all under `track_b/chatgpt_review_assets/`).
Did not play local video/audio, and did not independently execute repository tests. Video action/voice labels still require continuous media verification.

## A. Track A scientific verdict
User/Cursor-reported 15-seed synthetic arm metrics: fixed-rebind test accuracy 0.500; TECE 0.000; link ranking top-1 0.875; actual TECE `pair_correct_at_bind=0`; gold permutation and local-ID renaming invariance tests 10/10 reported. Code inspection supports removal of explicit `gold_matches`-conditioned score terms. Negative result retained. This work is correctly labeled `binding_policy_evolution_only`, not an RSI compositional generalization method result.

### A1. Statistical/evaluation scope
`binding_loop.build_binding_split()` still contains **4 fixed synthetic test tasks** (2 dual, 2 B-only) and 15 seeds perturb the mutation process, not 15 independent unseen tasks. Consequently top-1 0.875 should not be treated as a general reidentification result. Need varied world families, permutations, genuinely novel executable operator graphs, and per-task confidence intervals before any broader claim.

### A2. Budget/initialization confound
In `binding_loop.evolve_binding()`: fixed-rebind starts with `recovery_strategy=rebind_from_a`, `bind_score_threshold=.25`, `search_budget=6`; TECE/Vanilla/Random start with `none`, threshold .45, budget 4. Thus the 'fair' ablation is a **useful strong-policy stress test**, but it is not an exactly **matched-initialization/tool-budget** comparison. Separate two comparisons:
- strong non-evolving fixed-rebind baseline (legit as best-practice reference),
- genuinely matched baseline runs (same initial genome, mutation opportunities, budget, candidate evaluations and dev/test procedure).
Do not weaken fixed-rebind to make TECE appear stronger.

### A3. High Top-1 but 0 successful TECE binding
Separate two failure axes: **hypothesis ranking** (`pair_accuracy_top1`) vs **program execution/acceptance** (`pair_correct_at_bind`). Instrument representative full traces: which A referent was resolved; selected B candidate score; threshold/recovery rejection; tool-call budget; wrong program/question interpretation; answer support. This would diagnose whether 'Evolver failure' is selection, recovery, or binding—more actionable than more seeds on the same four tasks.

### A4. Honest method-science boundary
`program_selection` and `evolver_policy` currently execute the same A-bind→B-query sequence; the evolved element is recovery/threshold policy. No autonomous discovery of reverse/AV DAG. Freeze the current synthetic suite as a negative controls package. Do NOT optimize TECE against those very four held-out examples. In a separate new suite test independently generated multi-entity, role-reversal, missing evidence, audio/visual cue and uncertainty cases; keep true held-out graphs; prefer causal tests to high scores.
Keep `ok_for_expensive_rsi=false`.

**A deliverable:** `track_a/TRACK_A_BIND_FAILURE_TAXONOMY_AND_PARITY.md` with 1–2 reproducible traces per failure type, matched-budget versus strong-policy controls, independent scenario seeds, and ablation of threshold/budget/recovery. Negative results accepted. In parallel start a *design note*, not a new branded method: what agent-adaptive operation sequencing (not mere threshold tuning) could transfer to unseen video compositions? No expensive experiments.

## B. Actual video-grounded new facts / limitations
### B1. Football T1yh — two live attacks and replays
From newly inspected 1fps live/replay sheets:
- LIV live `29:50–30:14`: red-shirt side advances from midfield/wing to the attacking third, then red #19 ELLIOTT appears celebrating by ~30:09–30:14; no proof yet that he took final shot.
- LIV `30:32–31:19` is replay(s) of the SAME goal, with reverse/behind-goal views and a low attacking passage / ball near goal.
- BRI live `38:45–39:19`: players gather in the six-yard/penalty area, play develops near goal ~38:52–39:09, Brighton-shirt celebration ~39:10–39:19.
- BRI `39:39–40:14` replay views show a crowded penalty-area goalmouth sequence.
- Score anchors established earlier: 0–0 → 0–1 LIV → 1–1 BRI.
- Origin of each attacking phase (corner/free-kick vs open play), last touch, scorer, assist **remain unknown from these images**.

**Do not convert the hypothesis into two independent QA** by treating replay as a new goal. Canonical `CG-SPORT-DESIGN-001` remains `HYPOTHESIS_NOT_SUPPORTED`, `UNASSIGNED`, gold=null.

Important scientific caveat: even if both attack types are verified, 'Describe first goal then second goal' might be merely **conjunction of two atomic QA**, not a new relational composition. Proposed *refinement to test* (NOT accepted item):
> `比分先被改写、随后又被扳平的两次进球中，哪一方的进攻首先由定位球发起？该次进球改变的是领先还是扳平状态？`
Gold=null; requires verifying both origins and score-state relation. Run masked A-only/B-only/A+B on EXACT revised wording; if one window provides identity/state and origin, label `SINGLE_WINDOW_SHORTCUT_CONTROL`, not strong composition. Compare both attack mechanisms as a contrastive control only if a legitimate dependency remains.

Cursor should annotate observed ball state at 29:58–30:09 and 38:48–39:10 with frame timestamps, video/radio/audio and first touch source. If images insufficient, request human viewing of `liv_live_attack_2955_3015.mp4` and `bha_live_attack_3848_3915.mp4`. Do not auto-rewrite answer based on scoreboard alone.

### B2. Table tennis VTCD — a newly stronger video fact candidate
The 1fps sheet shows **apparently the same short-haired athlete**:
- around `02:46–02:48` holding/wiping face with a **white towel** while wearing a **red zip-up jacket**;
- around `02:50–02:55` gradually **removing the red outer jacket**, revealing a **blue/yellow playing jersey**;
- around `02:57–03:05` leaning forward in that blue/yellow shirt and holding a towel; another athlete dressed dark/black-purple appears after ~03:06.
The **garment sequence is supported at still-sequence level**, identity continuous enough to motivate video review, but specific repeated movement timing and sport context require continuous clip.

**New video-first QA prototype (weak/short-window control, not formal unseen):**
> `较早穿红色外套、用白色毛巾擦脸的那位选手，脱下外套后露出了什么颜色的比赛服？`
Candidate answer: blue/yellow. Weakness: later frames often show red jacket in hand, so B-only may solve; short time interval, not a long-video generalization claim. Store as `DEV_DIAGNOSTIC_WEAK_COMPOSITION` only after continuous video review and explicit shortcut test. **Better Track B expansion**: look for the same athlete in a substantially later rally and a distinguishable result, then create a cross-event referent/role/score link; don't inflate current asset count.

### B3. Athletics Z86 — finish context is now visibly present
The 04:05–06:00 sheet contains the running finish near `04:55–05:05`, later a full **Men's 100m Final** result-board panel near `05:25–05:30`, and close-ups including a red USA uniform near `05:45–05:55`. Previous introduction panels identified NOR Ndure, USA Gay, TRI Thompson.
**New candidate composition mechanism:** introduced athlete (prior identity+country) → lane/race tracking → result-panel placement. Do **not** infer winner/placing/finish time from the small result image or unrelated person closeups. Extract a legible result-board crop and each player's race-lane/finish evidence with original timestamps. Candidate question AFTER verification:
> `在赛前被字幕标记为某国选手的那名运动员，最终在结果榜中排第几？他在赛道中的位置如何对应？`
Exact subject/gold remains undefined. This is more plausible for multi-person matching than current two static stills, but B-only name-list shortcut remains a concern.

### B4. CG-NEW-002
Dense 04:19–05:05 grid shows prolonged gun aim, other figures arriving and standing; **table push not visible**. Do not automatically accept earlier original UID61 claim at the requested exact time. Target 05:05–07:30 motion windows, or put `TABLE_PUSH_UNCONFIRMED` and deprioritize if not located; avoid repeated re-extraction at the same sparse interval. CG-NEW-001 hug exact actor and CG-NEW-003 dog barking remain separate P1 media review tasks.

## C. Next parallel dual-track execution (tight scope)
**Track A**: keep negative benchmark as regression; add diagnostic traces and exact-parity controls, randomized world/graph families, program-selection design note. No paid model.
**Track B**: prioritize (1) football two attack-origin judgments with independent continuous clip and revised question necessity, (2) athletics legible board + introductory runner matching, (3) table-tennis outfit transition plus later match event, (4) CG-NEW media adjudications when available; maintain independent video coverage and untouched sealed pool.
**Shared**: ChatGPT-generated new QA prototypes are `HYPOTHESIS_NOT_SUPPORTED` or weak-controls, not `SUPPORTED`; do not assign any exposed video to final sealed test; preserve canonical CG-NEW and human TB audits. Use GitHub for metadata and small review image; gitignored MP4/WAV must be explicitly provided via approved media path when audio/video semantic decisions are needed.
**End**: run tests, commit/push, two independent A/B reports and precise evidence manifest, no expensive RSI.
