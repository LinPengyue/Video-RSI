# CVPR2027 — independent audit of Cursor `68ab45c` / run_002

Date: 2026-10-31
Audited Cursor commit: `68ab45c555ebf69e78d2ff78ef60c131009a365c`
Audit basis: GitHub source code, reported metrics, JSONL artifacts, A-only/B-only/A+B serialized packets, and **nine directly fetched GitHub still images**. No continuous MP4/audio was watched; no local Cursor test environment was run. Independent still observations:
`track_b/batch_factory/CHATGPT_RUN002_FRAME_AUDIT.jsonl`.
This audit is **unblinded**: the reviewer saw A and B imagery and the adjudication answers; it must NOT be counted as independent A-only or B-only evaluation.

## Decision: ACCEPT V2 software/measurement progress; novel compositional benchmark items NOT certified

- Branch SHA and actual `run_002` files confirmed. V2 implements provenance tiers, dedup, binding quarantine, separate blind packet variants, heuristic/not-video-tested labels, and Track A execution traces. Keep the original run_001 intact.
- 8 videos, 88 coarse frames, 13 earlier curated semantic fixtures, and **9 Cursor-authored still observations** (three per previously unlabeled seed) are present. All nine cited original still images were opened independently; static visual content is broadly consistent with recorded scene objects, with specific inference limits in the per-event audit. No automatic VLM semantic extraction: `model_inferred_events=0`.
- `n_new_relation_families=3` counts three **candidate evidence families**, all sharing exactly the same `cross_scene_attribute_contrast` mechanism. It does NOT mean three structurally diverse unseen compositions or three validated answerable Benchmark QA. None was continuous-video verified or independently necessity tested.
- `n_independent_evidence_families=9`, `n_distinct_questions=16`, and `n_answer_known=13` are different quantities. The latter is implemented as nonempty non-UNKNOWN provisional answer, even where `answer_status=ANSWER_PENDING`; not verified gold count.
- Cursor reports Track B tests 6/6 and Track A tests 2/2. Their test implementations were inspected, but these numbers were **not independently rerun** in this review.

## Independent review of nine new observations

| Video | Frame observations | Audit verdict |
|---|---|---|
| `S8vPx-u9p_A` | 848 snowy animated exterior with two people; 2121 crystal-like stairway; 3182 water spray/blur | first two scenes supported as static frames; third spray visible, but high-speed maneuver/actor not established |
| `iA_69g87Ilw` | 361 fruit plate, hand near red grapes; 904 man seated with a rod-like camera stick; 1356 illuminated night pool | static objects supported; touch motion, same person, and infinity-edge geometry not confirmed |
| `hROKtPqktO8` | 503 street number 67 and sidewalk; 1259 dark rocky hills; 1889 beanie/parka in snowy-looking setting | static appearance supported; geology, movement, snowfall dynamics and cross-scene identity remain uncertain |

Do not upgrade these observations to `HUMAN_VIDEO_VERIFIED` or `SUPPORTED`. `CHATGPT_FRAME_OBSERVATION` records a separate still-review provenance only, not a second independent video annotator or blinded QA test.

## P0 findings to patch within existing V2, without redesign

1. **Question-side semantic leakage**. `QA_DRAFT_0009/0012/0015` insert `location` tokens for BOTH sides directly into the question, e.g. `snowy_building_exterior` vs `dark_crystalline_corridor`. A-only/B-only JSON hides opposite media paths and answer metadata, but not the opposite-side scene label already written into the question. Thus packet field integrity passing is not an actual single-side necessity test. Remove answer-bearing A/B attribute names from question text. Add a test that inspects literal question contents and a real independent masked-answer protocol before claiming evidence necessity.
2. **Novel mechanism ≠ basic two-scene contrast**. Three new candidates are scene-description comparisons, a useful DEVELOPMENT/CONTROL starting point but not currently demonstrated novel compositional reasoning. Preserve them without promotion. Explore stronger video-grounded relations only when fresh motion/identity/state evidence supports them; do not hallucinate causal joins or invent a new RSI method.
3. **Review readiness overstated**. 8 packet entries are metadata-isolated, but all 8 have `reviewer_asset_verified=false`; most supplied media are stills, not verified playable clips. Two entries (`0002`, `0003`) have no provisional answer and `0003` requires unaudited audio. At most six entries have provisional answers; none yet has independent A/B necessity assessment. Replace `n_human_reviewable=8` with separate counters: `n_packet_serialized`, `n_asset_verified`, `n_answerable_candidate`, `n_clip_audio_reviewable`, `n_true_blind_evaluated`. No user-facing formal blind batch until actual media and question quality gates pass; continue next batch in parallel.
4. **Metric semantics/cost**. The nine novel semantic events are statically enumerated in `extract_events.py:NEW_FRAME_OBSERVATIONS`; `test_new_observations_without_curated_map` merely tests that hardcoded dictionary, not discovery for an unseen arbitrary video. `n_new_machine_semantic_events=9` conflates Cursor still registrations with automatic semantic inference: use separate agent/manual/model counters and rename accordingly. `cost_per_new_candidate_s≈1.688` measures decoding/extraction time divided by three and omits the cost/time of Cursor visual interpretation and question validation; do not call it end-to-end creation cost. Count known answers by independently confirmed answer status, not non-null provisional text.
5. **Blind test coverage**. Current `test_true_blind_packet` checks forbidden JSON fields only, not semantic leakage through Q text, link target visibility, independent reviewer exposure, actual media accessibility, or A-only/B-only predictions. Add bounded regression coverage; do not claim true causal two-witness necessity based on `RULE_PROXY` alone.

## Track A: improvement accepted; two additional scoring integrity tests needed

Observed code fixes the obvious `pred=None` abstain credit and removes direct compare fallback over `world.facts`; per-op success and traces now exist. Preserve the **0.833 choice vs 0.333 execution** negative result, gold DAG also 0.333, and keep expensive RSI disabled.

However, in `program_execution.py`:
- For selected `SCHEMA_MISSING_ABSTAIN`, `answer_ok` tests explicit abstention without checking `gold == "ABSTAIN"`. A wrong abstention DAG chosen on a non-abstain target could get answer credit when the wrong DAG encounters missing evidence. Require explicit decision, correct target/missing-evidence policy, and matching gold.
- Compare can credit `r.outputs.get("evidence_path_valid")` independently of semantic answer equality, and uses loose string-substring comparisons. Evidence validity is not equivalent to correct answer. Add adversarial wrong-answer/evidence-valid and wrong-schema abstention tests with exact normalized answer comparison.
- The returned `oracle_world_scraped=false` is assigned as a constant, so the zero-rate metric alone is not an instrumented leakage proof. Maintain code-level boundary checks and test denied oracle reads, while keeping tool-visible observations separate from scorer-only gold. A `trace.outputs_keys` list does not by itself expose value-level evidence lineage.

These are bounded integrity fixes, not invitations to tune selector weights or invent Graph Rewrite/RSI machinery.

## Cursor continuation (existing task only)

- Retain `run_001` and `run_002` immutably as historical results, and preserve negative controls.
- Apply the minimal P0 metric, semantic question-blinding, reviewer-asset and Track A scoring/test fixes above; run a **new uniquely named batch** with previously unlabeled DEV_CONSTRUCTION videos, if available, without substituting pre-authored `NEW_FRAME_OBSERVATIONS` for automatic semantic discovery.
- If no authorized semantic extractor exists, report `BLOCKED_NO_SEMANTIC_EXTRACTOR` and maintain candidate discovery through bounded, transparent Cursor/ChatGPT still review. Do not convert `CHATGPT_FRAME_OBSERVATION` into `AUTOMATIC_SEMANTIC_MODEL_OBSERVATION`.
- A-only, B-only, A+B reviewer exposure must remain independent; do not request the user to grade this current packet. User batch review is offered only once distinct, answerable, verified accessible media candidates are ready.
- Keep Track B≈80% / Track A≈20%, `UNASSIGNED`, no automatic `SUPPORTED`, sealed untouched, and `ok_for_expensive_rsi=false`. Seen may contain multi-hop; Unseen reserves full target directed combination structures. No expensive RSI, no new Track A method implementation.

## Claims to carry forward

**Supported now:** end-to-end Batch Factory V2 can ingest videos, reuse seeded still observations, build candidate evidence relations, generate drafts, quarantine a known binding error, serialize metadata-separated reviewer packets, and log minimal execution traces.

**Not supported now:** autonomous video-semantic discovery from a fresh video; validated long-video compositional QA yield; A/B causal necessity; generalization to held-out directed compositions; video agent RSI improvement.

Audit-only notes and nine-image validation are to inform the next Cursor execution, **not** to replace it.
