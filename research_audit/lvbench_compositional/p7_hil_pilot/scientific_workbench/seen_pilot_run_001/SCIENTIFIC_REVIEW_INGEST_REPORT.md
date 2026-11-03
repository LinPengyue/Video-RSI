# Seen Pilot run_001 — Scientific Review Ingest Report

**Engineering baseline:** `e904adac101be299c21159c8dc949f61baccf205`  
**Input SHA-256:** `7d1e9a00782eb3899f1b1f8a9470b57a8c66322adf2809d716c358ca18b8e722`  
**Raw artifact:** `scientific_reviews/RAW_seen_pilot_run_001_scientific_review.json`

## Headline

**3 USER_APPROVED compositional candidate graphs; 2 NOT APPROVED; 0 formal Seen; 0 formal Gold; 0 train exposure; expensive Track A RSI remains gated.**

## Decisions

| Pack | Decision | Graph / classification | Necessity |
|------|----------|------------------------|-----------|
| SP001 | APPROVED v0.3 | `USER_APPROVED_STRUCTURED_GRAPH` | A+B required (country bind → count stage flags) |
| SP002 | APPROVED v0.2 | `USER_APPROVED_STRUCTURED_GRAPH` | A+B required (A person/time bind + B sister subtitle) |
| SP003 | NOT APPROVED | `USER_VERIFIED_B_ONLY_SHORTCUT` | `FAIL_B_ONLY_SUFFICIENT` |
| SP004 | NOT APPROVED | `A_ONLY_ORDER_SHORTCUT_RISK_WITH_UNRESOLVED_DESCRIPTION_REFERENT` | `NOT_ESTABLISHED` |
| SP005 | APPROVED v0.2 | `USER_APPROVED_STRUCTURED_GRAPH` + correction history | A required for target-country selection |

## Engineering validation (≠ scientific upgrade)

- **Pack/UID/window consistency:** PASS vs `CATALOG.json` / review packs.
- **Protected isolation:** PASS (no Unseen/test/approved-graph video leakage).
- **SP002 A-end Tacara subtitle:** `COVERED_IN_EXISTING_A_CLIP` — stills at relative ~75–75.9s show `TACARA` lower-third inside A clip `[2,78]` (duration ≈76.01s). Evidence under `scientific_reviews/engineering_checks/`. No silent rewrite of human judgment; no auto-reapproval action needed.
- **SP004:** Descriptive-referent uncertainty preserved; not upgraded to proven A-only full-question sufficiency.
- **SP005:** `PREVIOUS_B_ONLY_SHORTCUT_CLASSIFICATION_RETRACTED` retained; `B_ONLY_SHORTCUT_CONFIRMED` forbidden.
- **Idempotent re-ingest:** same source SHA → no duplicate packs; `idempotent_replay=true`.

## Gates (unchanged)

```json
{
  "formal_seen_train": false,
  "formal_unseen": false,
  "formal_gold": false,
  "train_exposed": false,
  "seen_pool_frozen": false,
  "approve_expensive_track_a_rsi": false
}
```

Unseen `approved_graphs_v0.2` / judgment archive / PROGRAM_GRAPH_LIBRARY untouched.

## Remaining risks / next scientific gates

1. Human may still want independent frame-level audits beyond user-reported observations.
2. SP001 flagpole-top spatial relation caveat remains.
3. SP004 descriptive clue in A still unresolved — do not treat as A-only proven.
4. Candidate graph approval ≠ formal Seen pool freeze / train exposure / Gold.
5. Do not interpret 3/5 as population compositional yield.
6. Next science-owned steps only: further review, possible run_002 design, or explicit freeze — **not** started by this ingest.

## Workbench

http://127.0.0.1:8770/ → tab **Seen Pilot run_001** (shows ingested decision badges; formal gates remain false).
