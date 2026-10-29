# TRACK B CONSTRUCTION REPORT

Event-first discovery round. No formal QA minting. No auto-SUPPORTED. All `UNASSIGNED`.

## Method change

Previous failure mode: start from person-ID QA → hunt an action (led to uncertain agents / non-novel facts).  
This round: **clear observable event → determine subject → other-interval identity/condition clue → composition candidate**.

## VG-002 / VG-003 rework

| Old | Independent status | New alternative |
|---|---|---|
| VG-002 bell ringing | `UNCERTAIN_AGENT` | **TB-001/TB-002** Mikhail → bar / hotel (`identify_person + query_location`) |
| VG-003 post-net action | `NO_CLEAR_NEW_FACT` | **TB-003** embrace-identified Prince → drum performance (`identify_person + query_action`) |

## Screens

- Priority videos screened: **12** (mixed vlog/doc/drama/animation/food/nature)
- Raw automatic bridges: **33**
- Promising pending review kept: **7** extracted (+1 borderline skipped)
- Signatures probed: `identify_person + query_action`, `identify_person + query_location`, `identify_object + query_action`, `condition_event + later_action`, (`identify_person + query_attribute` borderline)

## Promising pending set

`TB-001` … `TB-007` in `candidates_pending_review.jsonl` — for **next independent review**.

## Failure reasons (distribution)

See `discovery_funnel.csv`: wrong-agent/noise, low composition novelty / official already binds, high shortcut, unclear agent.

## Evidence pack

- Path: `local_media/lvbench_track_b_pending_review.zip`
- Size bytes: 48216454 (48.2 MB)
- Contains only filtered promising clips/sheets/QA/notes (not full videos)

## Cost note

Extraction limited to 7 candidates; avoided packing rejected scan hits.

## Status

**Track B discovery: ADVANCED (pending independent review) / NOT a formal benchmark increment.**
