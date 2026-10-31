# CVPR2027 — independent audit of Cursor `56d68ae` and continuation gate

Date: 2026-10-31
Cursor SHA: `56d68aeba282dda5b8194751d11406af9ec8f02a`.
Basis: GitHub source code, JSON reports, test source, 4 representative GitHub contact frames. Continuous local MP4s are gitignored; ChatGPT has **not** independently played them, and has not rerun Cursor's reported 16/16 tests.

## Verdict

ACCEPT bounded engineering progression (Track A Gold VERIFY-feed closure; Track B question-text metric correction; four local continuous clips decodable). **DO NOT** claim autonomous video-semantic discovery, genuine new benchmark QA, independent A/B necessity, unseen-composition generalization or formal blind readiness. `run_003` correctly remains NOT_STARTED.

- Matched six-task synthetic suite after fix: selected choice 0.833, execution answer 0.333, oracle-schema choice 1.0 and execution 0.333; exec Gold-feed counters reported 0. `schema_to_program` no longer populates `verify_answer.inputs.answer` with `task.answer`; runtime uses agent prediction from prior query. Sentinel-gold tests now cover VERIFY. Scope of evidence is this synthetic harness, not formal process isolation or real-video generalization. Maintain negative baseline; do not tune or initiate expensive RSI.
- `run_002_patch_regen` recount: 17 drafts, eight literal question stems, 16 distinct Q+A pairs and seven distinct `dependency_program` strings. **Seven strings across the full historic draft set are not seven verified unseen structures.** The 3 new scene-contrast families all use the same structural mechanism, not a new proven directed compositional skill.
- Four ffprobe-playable local DEV clips from two previously exposed videos: `VTCDQYYKA9o` garment 23s and overlay 10s; `T1yhBv1ytzw` scoreboard anchor 25s and development-only goal window 90s. Twelve contact frames; no new semantic events. GitHub stills visually show the red garment and later FAN ZHENDONG overlay and two different football score states, but cross-clip identity, actual sequence, event cause/goal origin and witness necessity remain **unverified** by independent continuous review. FFprobe is access/decode proof only.

## P0 data-partition exposure register discrepancy (new finding)

`research_audit/lvbench_compositional/track_b/SEALED_POOL_SPLIT_POLICY.json` defines `exposed_or_construction` as video IDs disqualified from future sealed blind final use. But its current list omits all **three** DEV_CONSTRUCTION videos already inspected and included in `run_002/video_inventory.jsonl`, the nine-still study and QA drafting:
- `S8vPx-u9p_A`
- `iA_69g87Ilw`
- `hROKtPqktO8`

The file's `sealed_reservoir.current_ids=[]`, so **no actual sealed contamination is established**. This is an avoidable FUTURE contamination hazard, not a reason to reset existing experiments.

**Cursor P0:** reconcile all observed/exposed construction IDs against the sealed-exclusion register and add missing IDs to `exposed_or_construction` (or its canonical registry) without accessing, sampling or editing the sealed reservoir contents, and add a regression test `all_run001_run002_exposed_IDs_subset_of_sealed_exclusion`. Do not conflate exclusion-from-sealed with assignment to Seen/Unseen program structures: keep `UNASSIGNED` for the latter. Preserve existing historical results.

## Immediate next phase: capacity discovery, not another template-fix loop

### Track B 80% — two bounded parallel lanes

1. **Existing DEV continuous-evidence feasibility (small, capped)**: Use the four already confirmed locally available clips to build at most two DEV-only hypothesis records: (a) later FAN ZHENDONG name/overlay → earlier red jacket identity binding; (b) football scoreboard-state ordering as shortcut-sensitive control, **not** attack-origin causal QA. Record A/B clip duration, playable asset check, precise cue/event time, evidence provenance, unresolved identity/motion, model/manual auditor access and explicitly distinguish `UNVERIFIED`, `SUPPORTED_DEV_ONLY` and `SHORTCUT_CONTROL` without auto-SUPPORTED. A/B/A+B necessity is a separate test; clip playability is insufficient. If no authorized continuous observer can actually inspect motion, mark `BLOCKED_NO_CONTINUOUS_SEMANTIC_REVIEWER` and stop the small probe. No user-facing formal blind packet until accessible media and independent test.
2. **Eligible data + perception capacity inventory (majority of B)**: Metadata-only check of available LVBench assets/IDs, known exposure records, local storage and any authorized low-cost inference tools. Determine whether **additional eligible, nonsealed** DEV_CONSTRUCTION videos may be registered under the existing split policy, before inspecting or sampling their video content. No scavenging sealed IDs, no dumping sealed metadata/answers to Evolver. If no authorized additions, report exact dependency `BLOCKED_NO_ELIGIBLE_DEV_VIDEO`. If no approved video semantic extractor, report `BLOCKED_NO_SEMANTIC_EXTRACTOR` with the precise missing capability or permission, not pretend still-registration is autonomous video understanding. Do not start `run_003` without new eligible input and an honest semantics path. Existing exposed DEV may be used for small DEV-only perception feasibility without inventing new-video novelty.

Potential future `run_003` acceptance gate: eligible new video provenance, video-grounded semantic event output (human/Cursor/ChatGPT/VLM provenance distinguished), evidence-linked relation/program, answerability and two-witness shortcut risk, independently audited QA candidates, measured time/cost. A negative or blocked pilot is acceptable. Seen may include multi-step; Unseen reserves whole target directed composition structures; do not partition by only QA labels or video IDs.

### Track A 20% — preserve and freeze

Retain corrected matched six-task suite, static/evolver/random/oracle controls and negative trace. No selector retuning, Gold DAG inflation, new RSI architecture or expensive runs. Only fix a newly demonstrated serious integrity regression. `ok_for_expensive_rsi=false`.

## Recommended next Cursor deliverable

- Exposure registry fix plus invariant test, with sealed reservoir untouched and historical runs unchanged.
- `track_b/batch_factory/DEV_CAPACITY_AND_CONTINUOUS_EVIDENCE_GATE_REPORT.md` (DEV clip bounded evidence, eligibility/capacity checks, precise blockers, source/provenance, no inflated claims).
- Track B metadata-only eligible-data inventory + low-cost inference availability/authorization assessment, without unapproved API charges.
- Track A preserved scores and test results; no artificial improvement target.
- Commit/push only actual work; provide SHA and what concrete issue can be acted on next. If blocked, do not fabricate run_003.

Global invariants: Track B~80%, A~20%, `UNASSIGNED`, no auto-`SUPPORTED`, sealed untouched, `ok_for_expensive_rsi=false`, no expensive RSI, no redesign based on speculative RSI methods.
