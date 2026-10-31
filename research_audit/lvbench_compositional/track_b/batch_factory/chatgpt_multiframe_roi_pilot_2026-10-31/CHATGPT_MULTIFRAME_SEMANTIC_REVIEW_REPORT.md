# ChatGPT multi-frame ROI semantic production — actual visual review (2026-10-31)

Source Cursor SHA: `8df60217ba1f436fb16435859dd831d613f0ac02`.
ChatGPT event JSONL commit: `b3c666de7bbf7dd1f6bc47f19586b23099029a19`.
Evidence: **64/64 GitHub JPEG still frames directly opened in file-clock order** across four 10-second ROIs, two registered DEV_CONSTRUCTION videos. The local MP4s were NOT accessed or played; thus this is `CHATGPT_MULTIFRAME_OBSERVATION` from ORDERED STILLS, not `CONTINUOUS_VIDEO_VERIFIED`, not an independent blind review. Event paths, timestamps and per-frame SHA256 *references* are derived from matching entries in batch_manifest.json; GitHub JPEG bytes were inspected visually, not independently recomputed into cryptographic hashes here.

## Outputs

`events_CHATGPT_MULTIFRAME_OBSERVATION.jsonl` contains **10 evidence-bounded observation/hypothesis records** (not 10 certified independent action families):
- `STATIC_VISIBLE`: 3
- `ORDERED_MULTIFRAME_SUGGESTS`: 6
- `UNRESOLVED`: 1
- `CONTINUOUS_VIDEO_VERIFIED`: **0**.
All `video_motion_verified=false`, `cross_shot_identity_verified=false`, `formal_supported=false`, `data_partition_status=UNASSIGNED`. Six ordered-multiframe suggestions are inferences from sequential stills; they are not continuous-video-certified actions.

| ROI (source video) | Observed sequence | Strongest allowed result | What cannot be claimed |
|---|---|---|---|
| `Mcgg_ROI_vending_hand_1060_1070` (`Mcggugol2ts`) | 1060: man holds drink at restaurant table; 1061.333: abrupt cut to red illuminated vending machines; 1064–1067: close-up of bottles and prices 100/120, hand extends and points to PICNIC WATER middle-shelf area then withdraws; ~1069: view turns back to street | Distinct static beverage-price display and locally ordered pointing-gesture hypothesis | No button press, vending transaction, purchased product, complete payment, definite speaker/hand identity, or continuous motion certification |
| `Mcgg_ROI_cardshop_approach_2128_2138` (`Mcggugol2ts`) | Broad indoor card displays → close-ups; around 2133.333 a hand points at a purple-toned illustrated card; then hand is absent and camera view turns down the aisle | Camera-near/far change and locally ordered gesture hypothesis | No verified card ID/price, physical touch, acquisition, purchase, or cross-scene transaction |
| `xi6_ROI_aerial_to_speaker_528_538` (`xi6r3hZe5Tg`) | 528 city aerial, 528.667–535.333 rooftop with `PARKROYAL` sign, landscaped terrace and multilane road; 536–538 hard cut to seated suited man beside indoor greenery with changing hand position | Frame-order shot transition plus static architectural scene | No proof the speaker is in pictured property, speaking about it, or causally connected to aerial sequence; no independently audited audio |
| `xi6_ROI_bioprint_deposit_1060_1070` (`xi6r3hZe5Tg`) | 1060–1065.333 nozzle position and purple lattice right-hand outline evolve; 1066–1067.333 edited insert of plated red/brown dish; 1068–1070 another angle of nozzle and purple mesh | **Best actual within-ROI state-change hypothesis**: local lattice line extension under adjacent nozzle; separate visible edit cut | No uninterrupted 10s deposition proof, no precise food/biological material identification, no demonstrated direct production of the plated dish. A later shot cannot be assumed to show an identical spatial point/part of that lattice |

### Science gate

- **One comparatively strong local process hypothesis** (purple lattice). Two gestures and camera movement are weaker; all remain observational (no verified causal relation).
- `n_multiframe_records=10` is a producer-count only, `n_locally_ordered_state_change_hypotheses` not equivalent to true novel composition.
- `n_independently_verified_continuous_actions=0`, `n_independently_answer_verified=0`, `n_two_witness_necessity_verified=0`, `n_certified_novel_directed_composition=0`.
- **No formal QA should be manufactured from the shot cuts or 'pointing = buying' shortcuts.** In particular do not construct an invented cause chain of lattice print → plated food. If a rigorous cross-evidence question cannot be formed, report a zero QA result.
- Same ChatGPT pass authored these annotations, so it cannot be used as a separate independent A-only/B-only blind grader of any resulting QA.

## Cursor next-step intake

1. Validate all 10 event records against `batch_manifest.json`, matching each evidence path to the correct ROI/video/frame ID/time/declared hash; sample multi-frame records contain `evidence_sha256[]` aligned with `evidence_paths[]`, not a single-still `source_frame_sha256`. Add a bounded multi-frame normalizer only if the existing factory doesn't accept it; do not rewrite historical run_003.
2. Do **relation feasibility FIRST**. Identify genuine properties and state-before/after hypotheses (especially printer nozzle/lattice) and prevent a generic 'compare two ordered frames' fallback. Shot/edit cuts, camera viewpoint changes and consumer gestures may be suitable controls, not automatic composed programs.
3. Any putative candidate must have a nontrivial directed combination of meaningful primitives, clearly stated two-witness dependency, negative controls for side-only/metadata shortcuts, and separately certifiable ground truth. This **pilot has not yet independently verified such a candidate**. A locally apparent lattice progression alone is a basic temporal state-change, not yet a held-out multi-step structure.
4. Run `run_004` **only if** a bona fide evidence-grounded, nontrivial directed relation hypothesis passes the development gate; otherwise retain `run_004=NOT_STARTED` and return `BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE` with exact reason. Don't inflate yield. Continuous clip verification, if later performed by a qualified independent observer, must use a separate provenance tier, not backfill the ChatGPT annotation as verified.
5. Write a short feasibility report (per ROI: accepted/rejected/control, one- or two-witness necessity and temporal/evidence risk), preserve prior DEV/Track A/negative baselines, and commit/push. For next sampling, allocate scarce ROI budget to **real action/state transitions**, not site-to-interview cut or camera motion.

Invariants: `UNASSIGNED`, no automatic `SUPPORTED`, sealed untouched, `ok_for_expensive_rsi=false`; Track A frozen 0.833 choice/0.333 exec; no paid VLM, no expensive RSI. These are new production observations, not certified QA or independent blinded test outcomes.
