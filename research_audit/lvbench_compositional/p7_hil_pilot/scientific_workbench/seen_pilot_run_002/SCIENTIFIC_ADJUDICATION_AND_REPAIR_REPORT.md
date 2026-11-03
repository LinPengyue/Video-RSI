# Seen Pilot run_002 — Scientific Adjudication & Engineering Repair

**Branch:** `research/lvbench-comp-p7-hil-pilot`  
**Baseline (all6 sync):** `9afc5e95156041833421ff3e034d76deb8aac7c3`  
**Handoff:** `scientific_reviews/handoff/run_002_scientific_adjudications_all6_v1.json`  
**Sync script:** `eng/sync_scientific_adjudications_all6_v1.py`  
（Legacy `eng/ingest_scientific_adjudications_v1.py` refuses to overwrite SP205 ≥ v0.5.）

## Headline

**3 USER_APPROVED compositional candidates (SP201 v0.2 / SP202 v0.3 / SP205 v0.5); SP205 `USER_ASSIGNED_UNSEEN` (formal_unseen=false); 1 REJECTED (SP204); 2 DEFER (SP203/DN201); 0 formal Seen/Gold; wgBlACG927Y held out of Seen train; Track A RSI remains gated.**

## Final status table

| Pack | user_decision | split | Notes |
|------|---------------|-------|-------|
| SP201 | `USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH` v0.2 | UNASSIGNED | Winner(B)→bind→emotion(A); not auto-Seen |
| SP202 | `USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH` v0.3 | UNASSIGNED | First-server(A)→bind→match-result(B); **same video + shared B with SP201** |
| SP203 | `DEFER_NEEDS_EVIDENCE_RELOCALIZATION` | UNASSIGNED | Orange coughing person not in A; no CoachOf |
| SP204 | `USER_REJECTED_AS_COMPOSITIONAL_CANDIDATE` | UNASSIGNED | `RELATION_UNVERIFIED + COMPOSITION_NECESSITY_NOT_ESTABLISHED` |
| SP205 | `USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH` **v0.5** | **USER_ASSIGNED_UNSEEN** | `CompareTemporalOrder` (“之后”); v0.4 gap superseded |
| DN201 | `DEFER_TARGET_EVENT_RELOCALIZATION` | UNASSIGNED | Same video as SP205 — forbid Seen-train exposure |

## SP205 v0.5

- Program: `IdentifyFirstTransport(A) → DetectDisembark(A) + TimeAnchor(A); IdentifyTransport(B) + TimeAnchor(B) → CompareTemporalOrder(A,B) → QueryLaterTransport(B)`
- Removed: `TemporalSuccessor` (no requirement to prove no intervening transport)
- A media restored 03:22–06:10 SHA `af84566d…ad68e8c08` retained
- v0.4 conditional record preserved under `scientific_reviews/HISTORY/SP205_v0.4_conditional.json`
- `USER_ASSIGNED_UNSEEN` ≠ formal Unseen freeze (`formal_unseen=false`)

## Remaining evidence issues

1. SP205 `first_transport_scope_provenance` still `PENDING_EXPLICIT_EARLIER_TIMELINE_EVIDENCE_POINTER`
2. SP205 `model_time_order_accessibility` still `PENDING_INPUT_PROTOCOL_CHECK`
3. SP203 / DN201 still DEFER pending human re-review of relocalization packs

## Gates (all false)

`formal_seen_train` · `formal_unseen` · `formal_gold` · `train_exposed` · `seen_pool_frozen` · `approve_expensive_track_a_rsi`

run_001 untouched. Track A readiness **not** auto-changed.

## Workbench

http://127.0.0.1:8770/ → **Seen Pilot run_002**
