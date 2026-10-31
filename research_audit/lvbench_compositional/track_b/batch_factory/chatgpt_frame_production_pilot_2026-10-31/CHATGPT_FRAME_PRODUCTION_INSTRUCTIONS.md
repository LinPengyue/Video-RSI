# ChatGPT Frame Production Pilot — instructions

Batch: `chatgpt_frame_production_pilot_2026-10-31`

## Cursor already did
- Extracted timestamped stills with `video_id`, `time_s`, `evidence_path`, `sha256`.
- Registered new DEV_CONSTRUCTION IDs listed in `batch_manifest.json` → `meta.new_dev_registered`.
- **Coarse sample frames are not semantic discoveries.**

## ChatGPT must do
1. Open each frame under `frames/<video_id>/`.
2. Propose **visible** semantic events only; mark inferences explicitly.
3. Append one JSON object per event to `events_CHATGPT_FRAME_OBSERVATION.jsonl` with fields:
   `event_id, video_id, time_span, actor, action_or_state, object, evidence_paths, observed_vs_inferred, uncertainty, provenance=CHATGPT_FRAME_OBSERVATION`.
4. For motion continuity / cross-shot identity / causality that stills cannot support: leave `PENDING` / high uncertainty — do not invent.
5. **Do not** treat this same ChatGPT pass as independent A-only/B-only blind adjudication for any QA built from these events.

## Status
`PENDING_CHATGPT_FRAME_PRODUCTION` until ChatGPT commits real events to GitHub.
