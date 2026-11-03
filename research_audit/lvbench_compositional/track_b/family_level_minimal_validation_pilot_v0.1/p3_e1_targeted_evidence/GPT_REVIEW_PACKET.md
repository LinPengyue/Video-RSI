# P3-E1 GPT Scientific Review Packet

Base commit: `7daa51985b9b816e3277d862f745ac10d3349508`
Generated: 2026-11-03T12:51:55+00:00

**Cursor has NOT prefilled GPT observations for the continuous windows.**
All candidate relations remain `*_NOT_CERTIFIED`. Do not treat this packet as SUPPORTED/GOLD.

## 1. Human adjudications (4 ROIs)

### hROKtPqktO8_ROI_500_510 (`500–510`)
- review_status: `OBSERVATION_REQUIRES_MODIFICATION_OR_ADDITION`
- certification_status: `NOT_CERTIFIED`
- Direct visual observations:
  - Street / scenery footage visible.
  - Woman recording a selfie-style video visible.
  - Multiple shot cuts within the window.
- Human interpretations / hypotheses (NOT certified events):
  - [HUMAN_HYPOTHESIS_NOT_CERTIFIED] Woman may be traveling or hiking, filming scenery along the way, then cutting back to selfie to share impressions.
- Candidate relations: _(none accepted)_

### hROKtPqktO8_ROI_1255_1265 (`1255–1265`)
- review_status: `OBSERVATION_REQUIRES_MODIFICATION_OR_ADDITION`
- certification_status: `NOT_CERTIFIED`
- Direct visual observations:
  - Rocky hillside / slope scenery visible.
  - Camera viewpoint and distance change across frames.
  - Woman selfie with mountain landscape in background.
  - On-screen subtitle mentions a steep slope (字幕提及陡坡).
- Human interpretations / hypotheses (NOT certified events):
  - [HUMAN_HYPOTHESIS_NOT_CERTIFIED] Woman may be the camera operator approaching or climbing the slope.
  - [HUMAN_HYPOTHESIS_NOT_CERTIFIED] Woman may already have climbed the slope.
  - [HUMAN_HYPOTHESIS_NOT_CERTIFIED] Selfie background may correspond to the previously shown hillside.
  - [UNAUTHENTICATED_IDENTITY_HYPOTHESIS] Appearance cues (blonde hair, nose piercing, etc.) support possible same-person link with ROI-1; NOT authenticated.
  - [HUMAN_HYPOTHESIS_NOT_CERTIFIED] ROI-1 and ROI-2 may have a cross-event dependency; temporal gap alone (~12 min) is insufficient proof.
- Candidate relations: _(none accepted)_

### iA_69g87Ilw_ROI_358_368 (`358–368`)
- review_status: `ACCEPT_GPT_OBSERVATION`
- certification_status: `NOT_CERTIFIED`
- Direct visual observations:
  - A hand points toward fruit on a fruit platter / bowl.
  - Camera subsequently turns toward sofa, window, and lounge / rest area.
- Human interpretations / hypotheses (NOT certified events):
  - [NEGATIVE_CONSTRAINT] Do not infer fruit was taken, eaten, or moved.
- Candidate relations:
  - `FRUIT_DISPLAY_THEN_LOUNGE_DISPLAY` — `HUMAN_ACCEPTED_CANDIDATE_NOT_CERTIFIED`

### iA_69g87Ilw_ROI_900_910 (`900–910`)
- review_status: `ACCEPT_GPT_OBSERVATION`
- certification_status: `NOT_CERTIFIED`
- Direct visual observations:
  - Man seated in a chair speaks and gestures.
  - Later shot shows a Do Not Disturb door hanger / plaque beside a door.
  - Hanger/plaque pose changes while held in a hand.
- Human interpretations / hypotheses (NOT certified events):
  - [NEGATIVE_CONSTRAINT] Do not infer completed hang / remove / flip of the plaque.
  - [NEGATIVE_CONSTRAINT] Do not certify that the speaker and the hand operating the plaque are the same person.
- Candidate relations:
  - `PERSON_SPEAKING_THEN_DOOR_SIGN_DISPLAY` — `HUMAN_ACCEPTED_CANDIDATE_NOT_CERTIFIED`

## 2. Prior 12-frame evidence (unchanged)

- 48-frame SHA revalidation: **PASS** (48/48)
- Paths: `p3_new_video_discovery/gpt_observations/*_ROI_*.json` → `evidence.frames[]`

## 3. Continuous video / audio index

| context | video | window (s) | proxy duration | audio duration | proxy SHA256 | audio SHA256 | GitHub stills |
|---------|-------|------------|----------------|----------------|--------------|--------------|---------------|
| `ROI1_CONTEXT` | `hROKtPqktO8` | 480.0–530.0 | 50.02s | 50.00s | `eefdf7f44709deac` | `af310742e981783b` | 3 |
| `ROI2_CONTEXT` | `hROKtPqktO8` | 1235.0–1285.0 | 50.02s | 50.00s | `3d157298cacb0e49` | `43236b9143c7aadd` | 3 |
| `ROI3_CONTEXT` | `iA_69g87Ilw` | 350.0–375.0 | 25.02s | 25.00s | `9c3243c14e05e6fe` | `4d15bf403c44094f` | 3 |
| `ROI4_CONTEXT` | `iA_69g87Ilw` | 890.0–920.0 | 30.03s | 30.00s | `a58d068d575d9865` | `8c276ce6510fa255` | 3 |

### Media accessibility

- **Continuous proxy + aligned audio**: local only under `track_b/local_media/p3_e1_targeted_evidence/` (gitignored). GPT GitHub review **cannot** stream these unless the review environment mounts this workspace.
- **Review stills**: committed under `p3_e1_targeted_evidence/review_stills/` for GitHub-visible inspection (stills ≠ continuous certification).

## 4. Hypotheses pending GPT direct observation

1. ROI1↔ROI2: possible same woman (hair/piercing cues); need continuous context, not frame order alone.
2. ROI2: hillside vs selfie background correspondence; climb-in-progress vs already-climbed.
3. ROI3: confirm fruit→lounge display order without inventing take/eat.
4. ROI4: speaking→door-sign display order; plaque pose change without certifying hang/remove/flip or same agent.
5. ~12-minute gap between ROI1 and ROI2 contexts must **not** alone prove cross-event dependency.

## 5. Specific questions for GPT (answer only from accessible evidence)

- For each context: what is directly visible in stills / continuous clip (if available)?
- Which human hypotheses gain support, remain unresolved, or are contradicted?
- Do audio cues (if locally available) add evidence without over-claiming?
- Any candidate directed compositional relation that is nontrivial and two-witness necessary? If none, report zero yield.

## 6. Missing evidence / limits

- No embedded subtitles found; no external VTT/SRT located for these videos.
- ASR not run (no authorized local offline ASR; paid ASR not approved).
- Continuous media not on GitHub; GitHub-only reviewers are limited to stills + prior 12-frame packs.
- Cursor did not prefill continuous-window observations.

## 7. Gates

- run_004 = NOT_STARTED
- ok_for_expensive_rsi = false
- QA drafts = 0
- Seen/Unseen/Hold unchanged
