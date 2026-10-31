# RUN001 Audit Response + RUN002 Report (Batch Factory V2)

Date: 2026-10-31  
Baseline audited SHA: `22214a1` · Handoff: `CHATGPT_AUDIT_22214A1_BATCH_FACTORY_V2_HANDOFF_2026-10-30.md`  
Constraints: **UNASSIGNED** · no auto-**SUPPORTED** · sealed untouched · `ok_for_expensive_rsi=false`

## RUN001 (preserved baseline — no silent rewrite)

Accepted ChatGPT verdict: E2E software/I/O proof **yes**; autonomous semantic production **not yet**.

| Claim to avoid | Actual |
|----------------|--------|
| 8/8 semantic interpretation | 8/8 media+coarse I/O; **13 curated** semantic fixtures; **0** new semantic on 3 unlabeled seeds |
| AUTO_HIGH=0.8 quality | Rule heuristic score only |
| Blind packets | Leaked A/B facts, grades, proxies — **do not send to user** |

Per-item decisions remain in `CHATGPT_RUN001_AUDIT.jsonl`.

## V2 hardening delivered (Lane 1)

- Tiered provenance + metrics split curated vs new
- Multi-layer dedup (normalized Q+A, overlapping windows)
- Fact-binding gate (0005 Ndure≠USA Gay quarantined)
- Grades renamed `HEURISTIC_*_NOT_VIDEO_TESTED`; `evidence_tested=false`, `masked_qa_executed=false`
- True B_ONLY / A_ONLY packets (integrity tests pass); answers in `blind_keys/`
- Resume reloads **events + evidence**

Tests: `tools/lvbench_comp/test_batch_factory_v2.py` (6/6 OK)

## RUN002 real yield (Lane 2)

CLI:

```bash
python -m tools.lvbench_comp.batch_factory run \
  --output research_audit/lvbench_compositional/track_b/batch_factory/run_002
```

| Metric | Value |
|--------|-------|
| Videos processed | 8/8 |
| Coarse frames | 88 |
| Curated semantic fixtures | **13** (not novelty) |
| **New** frame semantic observations | **9** (3 videos × 3; `CURSOR_FRAME_VISUAL_OBSERVATION`) |
| Paid / local VLM model events | **0** |
| Relations | 17 |
| QA drafts / distinct Q / independent families | 17 / 16 / **9** |
| New relation families (from new obs) | **3** |
| Quarantine binding errors | 1 |
| Dup rate | 0.471 |
| Human reviewable (true-blind) | **8** (`PENDING_HUMAN`) |
| New-candidate yield / video | **0.375** |
| cost_per_new_candidate_s | ~1.7 (decode/extract wall) |

Unit of novelty = **distinct video-grounded answerable families newly produced** = **3** from previously unlabeled seeds (S8vPx / iA / hRO cross-scene contrasts). Curated TT/football/athletics retained as calibration/controls, not counted as new discovery.

### Blockers / honest gaps

1. **No automatic video semantic model** under budget (`model_inferred_events=0`). New events come from **agent still inspection** of seed frames, not continuous video/audio understanding.
2. Motion-blur / identity links across cuts remain `unresolved_flags`; answers stay `ANSWER_PENDING`.
3. Cross-scene QAs are attribute contrasts, **not** verified causal narratives.
4. Full motion/audio still requires local MP4 for human reviewers (`media_access_state` = still paths on GitHub).

Recovery path: ChatGPT can batch-review `run_002` contact/seed frames and register `CHATGPT_FRAME_OBSERVATION` upgrades; optional affordable local VLM later — **without** inventing new method branding or expensive RSI.

## Artifacts

- `track_b/batch_factory/run_002/` (metrics, graphs, drafts, true-blind packets)
- `track_b/batch_factory/run_001/` (historical baseline unchanged)
- `track_a/TRACK_A_EXECUTION_SCORING_INTEGRITY.md`
