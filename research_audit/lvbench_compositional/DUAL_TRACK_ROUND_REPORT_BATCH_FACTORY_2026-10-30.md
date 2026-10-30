# Dual-Track Round Report — Batch Factory Reset (2026-10-30)

Baseline commit: `788c212af5aa9f0cd5a45db4bd690f10f4318ed8`  
Plan: `TRACK_B_BATCH_FACTORY_AND_DUAL_TRACK_RESET_2026-10-30.md`  
Constraints held: **UNASSIGNED** · no auto-**SUPPORTED** · sealed not accessed · `ok_for_expensive_rsi=false`

---

## Track B (primary) — Event→Graph→QA factory run_001

**Runnable CLI**

```bash
python -m tools.lvbench_comp.batch_factory run \
  --manifest research_audit/lvbench_compositional/track_b/construction_video_pool.jsonl \
  --pool DEV_CONSTRUCTION --max-videos 12 \
  --output research_audit/lvbench_compositional/track_b/batch_factory/run_001
```

| Metric | Value |
|--------|-------|
| Videos processed | **8 / 8** (0 MEDIA_UNAVAILABLE, 0 EXTRACTION_FAILED) |
| Events total / semantic | 110 / 13 |
| Cross-event relations | 8 |
| QA drafts (independent families) | 8 (dup rate 0) |
| AUTO_HIGH / MEDIUM / LOW | 3 / 4 / 1 |
| Candidate yield / video | 1.0 independent family |
| Human review packet | **8 items**, `PENDING_HUMAN` |
| formal_supported | false |

**Mechanism coverage (independent):** reverse_name_to_early_garment×2, ordered_state_transitions×1, heat_boundary_name_contrast×2 (text control), same_local_actor_temporal×1, slide_speech_av_grounding×1 (audio pending), cross_shot_narrative×1 (uncertain).

**Artifacts:** `track_b/batch_factory/run_001/` — inventory, event_graphs, relations, qa_drafts, qa_auto_screen, review_queue_priority, human_review_packets/{B_ONLY_BLIND,A_ONLY_BLIND,A_PLUS_B_ADJUDICATION}, `PRODUCTION_AND_QUALITY_REPORT.md`.

**Production rule demonstrated:** uncertain / ANSWER_PENDING / audio-required QAs stay flagged and **do not block** the batch. Formal certification deferred.

**Gaps (honest):** 3 unlabeled pool videos contribute coarse frames only (no curated semantic events yet) → relations concentrate on 5 videos with prior audit seeds. First human packet has 8 items (within 8–12); expand next batch by mining more events on unlabeled videos without waiting for this packet.

---

## Track A (~20%) — Execution over selection

**Deliverable:** `track_a/TRACK_A_EXECUTION_OVER_SELECTION.md` + `execution_over_selection.json`  
**Code:** `tools/lvbench_comp/typed_evidence_contract/program_execution.py`  
**Tests:** `tools/lvbench_comp/test_program_execution.py` (pass)

| Policy | choice_acc | **exec_acc** | both |
|--------|------------|--------------|------|
| strong_static_selector | 0.833 | **0.333** | 0.333 |
| evolver_weights | 0.833 | **0.333** | 0.333 |
| random | 0.333 | 0.333 | 0.167 |
| oracle_gold_dag | 1.000 | **0.333** | 0.333 |

**Finding:** Prior 0.833 / 0.750 figures were **program_choice** (label) accuracy. After compiling selected DAGs into `TypedEvidenceExecutor` traces, **execution_answer_accuracy=0.333** even for gold DAG — selection ≠ execution. Frozen 4-task binding matched parity remains untuned negative control. No expensive RSI.

---

## Next for humans / ChatGPT

1. Blind-review `run_001/human_review_packets/` (8 QAs) in one batch.  
2. Do not promote to SUPPORTED; only funnel toward HUMAN_REVIEWED / CANDIDATE_POOL.  
3. Track B: next factory batch on unlabeled videos + ChatGPT structural redesign of high-value families.  
4. Track A: improve executor grounding for reverse/compare schemas; keep choice vs exec metrics separate.
