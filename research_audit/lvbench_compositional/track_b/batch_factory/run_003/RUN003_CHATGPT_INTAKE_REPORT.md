# run_003 — ChatGPT still-frame intake (2026-10-31)

Parent HEAD: `226456af6c3e5bb89095044b4287c27a5ddf1a05`  
Factory: `0.2.2` / extractor `batch_factory_v2_2_chatgpt_intake_2026-10-31`  
Invariants: `UNASSIGNED` · no auto-`SUPPORTED` · sealed untouched · `ok_for_expensive_rsi=false`  
Track A: **frozen** (choice 0.833 / exec 0.333 / gold-feed 0) — not modified.

## Why run_003 started

Gates met for a **bounded intake run** (not a yield-chasing replay of run_002):

1. New registered DEV_CONSTRUCTION videos: `Mcggugol2ts`, `xi6r3hZe5Tg` (+ existing `JPPMz8fEml0` unused-region stills).
2. Real semantic observations with distinct provenance: 12× `CHATGPT_FRAME_OBSERVATION` (GitHub-committed, directly inspected stills).
3. Validated schema/path/sha/dedup intake → Event Graph → Relation → QA Draft → Auto Screen.

This is **not** continuous-video discovery and **not** formal benchmark yield.

## Intake validation

| check | result |
|-------|--------|
| raw events | 12 |
| accepted | **12** |
| rejected | 0 |
| provenance | all `CHATGPT_FRAME_OBSERVATION` |
| evidence paths + sha256 vs manifest | OK |
| duplicate event / frame ids | 0 |
| claimed motion / cross-shot identity | none (correctly false) |

Artifact: `chatgpt_ingest_report.json`.

## Pipeline yield (honest)

| metric | value | note |
|--------|------:|------|
| videos | 3 | allowlist-only; ChatGPT-intake-only (no coarse/curated mix) |
| still-frame events | **12** | `is_continuous_video_event=false` |
| continuous video events | **0** | strict separation |
| relations | **10** | 9× `still_ordered_setting_contrast` + 1× `still_commerce_price_display_pair` |
| QA drafts | 10 | all `development_control` |
| distinct question texts | **2** | not 10 unique stems |
| distinct program structures | **2** | |
| independent evidence families | 10 | fact-id families; ≠ novel composition |
| independently answer verified | **0** | |
| formal_blind_ready | **0** | |
| auto grades | 10× `SHORTCUT_CONTROL` | |
| novel directed composition (certified) | **0** | still ordered contrast ≠ unseen composition |
| true composition-dependence (A/B necessity verified) | **0** | same ChatGPT pass cannot be independent blind |

### New DEV focus

| video | still events | relations | mechanisms |
|-------|-------------:|----------:|------------|
| Mcggugol2ts | 4 | 4 | 3 ordered-still + 1 commerce/price-display pair |
| xi6r3hZe5Tg | 4 | 3 | 3 ordered-still only |
| JPPMz8fEml0 | 4 | 3 | 3 ordered-still (existing DEV unused region) |

The commerce/price-display pair on `Mcggugol2ts` is a **bounded domain hypothesis** (two price-bearing commercial stills), still `SHORTCUT_CONTROL` / purchase&currency unverified — **not** claimed as novel composition skill.

## What failed / blocked for formal progress

1. **No continuous motion auditor** → cross-shot identity, action trajectories, causality remain PENDING.
2. **Still pairs are development controls**, not Unseen directed composition structures.
3. **Independent A/B blind** blocked: ChatGPT authored the events; cannot also adjudicate derived QA.
4. **No local VLM** → no `AUTOMATIC_SEMANTIC_MODEL_OBSERVATION`.
5. Scene-contrast all-pairs template **intentionally disabled** for still intake (consecutive-only) to avoid run_002-style churn.

## Cost

- Decode/extract wall: ~0 (intake-only; frames already on GitHub).
- No paid VLM/API.
- ChatGPT still inspection cost: external (prior commits); not re-instrumented here.
- Cursor factory wall time: see `pipeline_metrics.json` `elapsed_s`.

## Track A

Unchanged negative baseline; no selector/RSI work.

## Next actionable steps

1. Independent human (non-ChatGPT) A-only/B-only on a tiny still-pair subset **or** continuous-clip review for one Mcggugol commerce hypothesis.
2. Do not inflate run_003 still contrasts into Seen/Unseen partition.
3. Further DEV registration OK; new semantics still need either continuous review or a second independent annotator.
