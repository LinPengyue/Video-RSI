# ChatGPT still-frame semantic-production completion — 2026-10-31

## Source and scope
- Cursor source batch: `fb022c33b5fe3931b5ed3eb48cfcf9a726bca1cb`
- First ChatGPT event commit: `aef575c63a8537f569f3f5d875e893fa775daf1d`
- Input: 12 timestamped GitHub still images from 3 registered nonsealed DEV_CONSTRUCTION videos; every image was directly opened and visually reviewed by ChatGPT.
- Output: `events_CHATGPT_FRAME_OBSERVATION.jsonl` contains **12 independent frame-anchored static scene observations**, 1 for each frame. Their paths, frame IDs, timestamps and source SHA256 strings were cross-checked against `batch_manifest.json`. This is *not* a 12-video-event verified dataset.
- Source videos: `JPPMz8fEml0` (4 previously registered DEV unused-region frames); `Mcggugol2ts` and `xi6r3hZe5Tg` (4 frames each, two newly registered DEV videos).

## Main visible evidence (not inferred trajectories)
- `JPPMz8fEml0`: two men beside street and visible English subtitle; three women outside shopfront; nighttime man in a street; seated cap-wearing man in an indoor room.
- `Mcggugol2ts`: man in illuminated shopping street; close-up of hand at a beverage vending machine with visible price numerals; night city street; illustrated trading-card display.
- `xi6r3hZe5Tg`: aerial view of glass buildings with PARKROYAL sign and greenery; decorated plated food; 2D/3D animated explanatory schematic; two children wearing yellow tops indoors.

## Interpretation and protections
- All outputs use `provenance=CHATGPT_FRAME_OBSERVATION` and `evidence_modality=single_static_frame`. `time_span.start_s=end_s` is an **instantaneous frame observation**, NOT a verified action interval.
- `observed_vs_inferred=observed` applies only to the visible objects, appearance and static setting. The `uncertainty` field explicitly quarantines unresolved geolocation, speaker attribution, precise actions, cross-shot identity, causal links, product or dish identification and animated transitions.
- No identity joining between timestamps is warranted. A long gap between still frames is not evidence of the intervening order of actions. Some observed states may be narration or inserted stills/animation, rather than direct real-world events.
- There has been **NO independent motion/audio/video verification** and no independent A-only/B-only review. This same ChatGPT generation pass cannot serve as an independent reviewer of QA derived from it.
- `n_chatgpt_static_observations=12`, `n_model_inferred_semantic_events=0`, `n_continuous_video_verified=0`, `n_new_relations=0`, `n_independent_answerable_QA=0`, `n_formally_supported=0`. Even distinct static descriptions are not guaranteed to be 12 independent useful compositional event families.
- Historical `run_001`, `run_002`, `run_002_patch_regen` and Track A results unchanged.

## Next Cursor intake
1. Read events JSONL and verify schema, manifest paths/timestamps, one record per actually opened frame, provenance, no duplicate fact/event ID and no semantic content inferences promoted as certainty. If schema rejects point-in-time spans, convert to a documented still-point representation without inventing video duration.
2. Run typed Event Graph → relation hypothesis → QA draft → auto screen only on the **actual 12 still-grounded observations**, while preserving Cursor vs ChatGPT vs VLM provenance. Treat cross-frame identity joins, motion and causality as PENDING until continuous evidence exists. Do not manufacture semantic relations or QA for yield quotas.
3. Count unique canonical mechanisms and structural directed signatures, **not** question answer pairs or scene comparisons alone. Use a bounded, nonsealed DEV-only continuation; no final Seen/Unseen assignment until warranted.
4. If the factory cannot consume the new schema, report exact missing input/normalizer and patch narrowly. Any run_003 should be genuinely re-executed on eligible registered inputs, with reproducible data and costs, not a renamed run_002.
5. Report valid events accepted, rejected/downweighted events, real new relation hypotheses and QA families, independent evidence sufficiency, model/cost limits and next blocker. Maintain `UNASSIGNED`, no auto-`SUPPORTED`, sealed untouched, `ok_for_expensive_rsi=false`.
