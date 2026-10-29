# CVPR 2027 | ChatGPT Independent Audit and Next Dual-Track Handoff
Date: 2026-10-29
Audited Cursor commit: `77d524c1661d01a79a51bd96700f1d8baa61057f`
Branch: `research/lvbench-comp-video-grounded-evidence`

## Verified status vs conclusions NOT yet supported
- **Shared**: canonical CG-NEW-001..005 mapping is corrected to TB-003/TB-007/TB-006/TB-005/TB-004; prior fallback kept. All PROPOSED_* and UNASSIGNED.
- **A**: evidence graph, non-identical recovery, genome search/evaluation/selection on synthetic worlds are present in code. Cursor reports 19 passing tests; I inspected the tests and code, **did not independently execute those GitHub-sourced tests**.
- **B**: new media index and second-round review scaffold exist. Adjacent windows are not verified new facts; no new audio/video evidence was independently reviewed in this GitHub audit.
- Never claim 1.00/1.00 synthetic Seen/Unseen as empirical Video Agent RSI compositional generalization; keep `ok_for_expensive_rsi=false`.

## Track A code review — critical scientific validity issues

### A1. Held-out `signature` does not imply held-out execution structure
`evolution_loop.py:build_task_split()` has **3 Seen tasks / 1 Unseen task**. Seen uses `identify_person + describe_attribute` and `identify_person + describe_location`, Unseen uses `identify_person + describe_action`, but **all four request `property_name="action"`** and the same `_world_pair()` structure. The ambiguous Seen and Unseen both use `referring_expression="speaker"`, with the same first-speaker correction. This can measure alias-recovery transfer, not controlled *compositional structure* generalization.

**Required**: encode executable op DAG / role-dependency schema, not merely text labels; ensure truly different operator graphs, directionality, entity cardinality and modalities across train vs target split. Produce `split_witness.json` with distinct executed graph hashes and exhaustive leakage check. Never relabel an unchanged graph to call it Unseen.

### A2. A+B structural witness is not sufficient for actual necessity
`evidence_graph.py:evaluate()` can return `STRONG_COMPOSITION` even when B contains only one answer-bearing entity. `supports_answer` is also a pre-filled truth label on an oracle-like `EvidenceNode`. A provenance graph is a useful intermediate criterion, but does not show that B-only could not answer.

**Required**: keep three separate judgments `evidence_path_valid`, `semantic_answer_correct`, `composition_necessary`. Evaluate A-only/B-only/A+B by independently executing the same question with masked observations; deny `composition_necessary` if either single-window setup suffices. Do not equate two citations with necessity. Create negative controls where the A→B link exists but B-only is enough.

### A3. The synthetic agent has privileged world structure
`run_task()` and executor work over `SimulatedWorld` with oracle `EntityCandidate.entity_id` and `WorldFact.entity_id/property_value`, so this prototype has **not** tested noisy perception, imperfect entity tracking or evidence source trust. Query values also come straight from simulated facts.

**Required**: distinguish oracle facts (evaluation-only) from **noisy observations** (agent input); include misleading captions, missing entities, same-category lookalikes, changing appearance, split audio/visual cues, missing/forged evidence, misleading names and time offsets. Log when recovery infers identity from oracle metadata. Evaluate on separate generated scenario families.

### A4. Baseline/search parity and seed robustness
Current single-seed output (`seed=11`) reports Fixed/Random/Vanilla `0.67/0.00` vs TECE `1.00/1.00`; only 1 Unseen example. Vanilla mutates budget only, while TECE can mutate recovery policy/cues. `op_order_template` is defined in genome but `run_task()` executes a hardcoded op sequence, so this does **not yet test general harness program evolution**.

**Required**:
- Compare same initial harness, evaluator budget, candidate count, generations, mutation access, tool-call budget and held-out selection policy.
- Add controls: non-evolving **fixed rebind** policy, random **with identical mutation space**, vanilla **with identical mutation space/objective** (change only intended TECE mechanism), TECE minus evidence graph, TECE minus recovery, TECE minus verification, static planner.
- Sweep ≥20 random seeds and many independently generated scenarios in several world families; report confidence intervals, per-family failure modes, cost/success Pareto, median and distribution.
- Use train for mutations, independent dev for selecting final genome, and untouched synthetic test evaluated **once**. No adaptive use of final test feedback.
- Make executable operation schedule actually depend on `op_order_template`, or state clearly that current project only evolves recovery *parameters*.

### A5. Stop condition
Do not run expensive RSI until multiple videos/signatures are independently human-verified and declared initial harness is wired to frozen video tools. Do **not** optimize the synthetic suite to produce a predetermined TECE advantage. If fair controls erase the synthetic gap, record the negative result — it is scientifically useful.

## Track B — continue original video-based data study, not another name-swap
New indexed CG-NEW clips are still **local/gitignored**. Github metadata and paths do **not** make the video/audio accessible to ChatGPT. The prior TB evidence package is available, but the new ~34.6MB CG evidence package is not in this chat's mounted files. Do not claim independent review of its audio or adjacent scenes.

**Immediate next step**: create an auditable, small **GitHub-visible review manifest** for each CG-NEW-001..003:
1. Time-ordered *contact sheets* (JPEG/WEBP), observed frame timestamps, media SHA256, source video id, original time range, file visibility.
2. For newly observed action, provide a tentative timestamped observation with `source=CURSOR_UNVERIFIED_DESCRIPTION`, not `VERIFIED_FACT`. ChatGPT will inspect and challenge these using actual imagery and request specific full clips if needed.
3. For CG-NEW-003 provide raw audio link/asset or explicit `AUDIO_NOT_AUDITED`; written onomatopoeia is not independent audio verification.
4. Do not commit bulk original videos or copyrighted MP4 to the repository simply to enable review. Small attributed contact sheets may be reviewed under project policy; keep most video media gitignored.
5. Maintain blinded necessity reviews for changed **final question wordings**; A-only/B-only/A+B must target the exact same question.

**Expand B in parallel**: sample independent videos not involved in current public method discussion; event discovery with actual film evidence, cross-video diversity, reserved hidden unseen signatures. The five exploratory CG samples are not the full benchmark and are not sealed test.

## Next Cursor deliverables, independent and budget-limited
**A**: `track_a/TRACK_A_STRESS_TEST_AND_LEAKAGE_AUDIT.md` + code/tests, realistic synthetic scenario families, true program-signature leave-out, matched-budget baselines, per-seed results. Continue no expensive RSI.

**B**: `track_b/CHATGPT_REVIEW_ASSET_MANIFEST.jsonl` + small inspectable contact sheets for CG-NEW-001..003 (if repository policy permits), original clip hashes, and accurate observed-time annotations; `TRACK_B_DISCOVERY_PROGRESS.md` on expanded video/event coverage, no invented facts.

**Shared**: do not alter canonical five proposals silently; preserve review provenance; no `SUPPORTED` or sealed-test assignment; commit/push and report SHA.

## Research interpretation
An emergent improvement that generalizes to a *different executed operator/dependency graph* is a stronger scientific result than new answer words under the same graph. Evidence provenance, compositional necessity and true unseen structural generalization are distinct criteria; evaluate each separately.
