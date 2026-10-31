# ChatGPT multi-frame ROI semantic production — instructions

Batch: `chatgpt_multiframe_roi_pilot_2026-10-31`

## What Cursor prepared
- Up to 2 ROIs × 2 DEV videos (`Mcggugol2ts`, `xi6r3hZe5Tg`)
- ~10s windows @ ~1.5 fps, ≤16 timestamped frames/ROI with sha256
- Optional local continuous clips exist on Cursor machine but are **not** the GitHub primary evidence

## What ChatGPT must do
1. Open frames under `frames/<video_id>/<roi_id>/` **in time order**.
2. Propose candidate events; each event must set exactly one:
   - `STATIC_VISIBLE`
   - `ORDERED_MULTIFRAME_SUGGESTS`
   - `CONTINUOUS_VIDEO_VERIFIED` (only if you independently had continuous media — **you do not from this GitHub still batch**)
   - `UNRESOLVED`
3. Append JSONL to `events_CHATGPT_MULTIFRAME_OBSERVATION.jsonl` with provenance `CHATGPT_MULTIFRAME_OBSERVATION`.
4. Prefer state changes / conditional dependencies over scene-different-only contrasts.
5. Do **not** auto-certify cross-shot identity, purchase completion, or causality.
6. Same ChatGPT pass must **not** later count as independent A/B blind adjudication.

## Status
`PENDING_CHATGPT_MULTIFRAME_SEMANTIC_REVIEW` until real events are committed.
