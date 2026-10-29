# Seen / Unseen Composition split feasibility

This analysis is structural only. Candidates are not video-certified.

- Complete candidates: 56
- Distinct composition schemas: 10
- Distinct videos: 23

## Schema coverage

- `identify_person + query_attribute`: 14 questions across 7 videos
- `identify_event_result + query_action`: 10 questions across 9 videos
- `identify_person + query_action`: 9 questions across 4 videos
- `identify_person + query_location`: 7 questions across 4 videos
- `identify_event_result + query_cause`: 4 questions across 4 videos
- `identify_object + query_action`: 4 questions across 2 videos
- `identify_person + query_relation`: 4 questions across 3 videos
- `identify_place + query_person`: 2 questions across 1 videos
- `identify_object + query_cause`: 1 questions across 1 videos
- `identify_object + query_holder`: 1 questions across 1 videos

## Primitive reuse

- `identify_event_result` appears in 2 schemas: identify_event_result + query_action, identify_event_result + query_cause
- `identify_object` appears in 3 schemas: identify_object + query_action, identify_object + query_cause, identify_object + query_holder
- `identify_person` appears in 4 schemas: identify_person + query_action, identify_person + query_attribute, identify_person + query_location, identify_person + query_relation
- `identify_place` appears in 1 schemas: identify_place + query_person
- `query_action` appears in 3 schemas: identify_event_result + query_action, identify_object + query_action, identify_person + query_action
- `query_attribute` appears in 1 schemas: identify_person + query_attribute
- `query_cause` appears in 2 schemas: identify_event_result + query_cause, identify_object + query_cause
- `query_holder` appears in 1 schemas: identify_object + query_holder
- `query_location` appears in 1 schemas: identify_person + query_location
- `query_person` appears in 1 schemas: identify_place + query_person
- `query_relation` appears in 1 schemas: identify_person + query_relation

## Unseen-composition candidates

Strongest candidate unseen schema: `identify_event_result + query_action`
- Videos for that schema: 2LH3JCGkEBU, Hf-n1yfd8II, JTa_Ue2MSwc, KLIa2UaE2KE, XNtNNplAwiI, evYm0cELO3I, f8DKD78BrQA, oZEVgDXJwCc, wgBlACG927Y
- Proposed held-out test video: `wgBlACG927Y`
- Test item count under video isolation: 2
- Train item count under video isolation: 54
- Primitives `identify_event_result` / `query_action` present in isolated train: `True` / `True`

## Leak checks

- Shared videos between isolated train/test: False
- Shared (video, uid) pairs: False
- Schemas with >=3 videos: 6

## Verdict

`INSUFFICIENT_COMPOSITION_COVERAGE`

Blocking issues: held-out Unseen cell has only 2 items (need >=5).
Main missing pieces: denser multi-video coverage of the same composition schemas, and Unseen cells large enough that a held-out schema is not just one or two items. Renaming people or swapping videos alone would not create true compositional generalization.
