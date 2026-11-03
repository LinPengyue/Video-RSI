# Seen Pilot run_002 — Scientific Adjudication & Engineering Repair

**Branch:** `research/lvbench-comp-p7-hil-pilot`  
（说明：任务文中 `video-grounded-evidence` 分支不含 run_002/`fa98aae` 工件；本轮继续 p7-hil-pilot。）  
**Baseline:** `fa98aae25f7a5c73259e4dd33c4cb70a46cd0592`

## Headline

**2 USER_APPROVED compositional candidates (SP201/SP202); 1 CONDITIONAL pending engineering (SP205); 1 REJECTED (SP204); 2 DEFER relocalization (SP203/DN201); 0 formal Seen; 0 formal Gold; 0 train exposure; Track A RSI remains gated.**

## Final status table

| Pack | user_decision | Notes |
|------|---------------|-------|
| SP201 | `USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH` v0.2 | Winner(B)→bind→emotion(A); precision limit on shuttle detail |
| SP202 | `USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH` v0.3 | First-server(A)→bind→match-result(B); **same video + shared B with SP201** |
| SP203 | `DEFER_NEEDS_EVIDENCE_RELOCALIZATION` | Orange coughing person not in A; no CoachOf; search packs ready |
| SP204 | `USER_REJECTED_AS_COMPOSITIONAL_CANDIDATE` | `RELATION_UNVERIFIED + COMPOSITION_NECESSITY_NOT_ESTABLISHED` |
| SP205 | `CONDITIONAL_USER_APPROVAL_PENDING_ENGINEERING_ACCEPTANCE` | A restored; **not promoted** — model-access gap |
| DN201 | `DEFER_TARGET_EVENT_RELOCALIZATION` | B lacks exit/upstairs; not certified B-only negative |

## SP205 media repair

| | Before | After |
|--|--------|-------|
| Coverage | 03:22–05:22 (`202–322`) truncated | **03:22–06:10 (`202–370`)** full |
| File | `A_wgBlACG927Y_202_322.mp4` | `A_wgBlACG927Y_202_370.mp4` |
| SHA256 | see `engineering_checks/SP205_A_media_repair.json` | same file |

### HUMAN vs MODEL evidence

- **HUMAN_REVIEWED:** board / disembark / 06:10–13:58 no-other-transport check / subway  
- **MODEL_ACCESSIBLE (clip-only):** restored A + B only  
- **BLOCKER:** `MODEL_ACCESSIBLE_TEMPORAL_GAP_06:10-13:58`  

→ Conditional promotion **not** satisfied; SP205 **not** upgraded to approved compositional candidate.

## SP203 / DN201 relocalization

| Pack | Search ranges | Engineering finding | Human entry |
|------|---------------|---------------------|-------------|
| SP203 | 57:20–57:50, 57:40–58:20, 58:05–58:40 | Match-play stills; orange cougher **not** found | `relocalization/SP203/*.mp4` |
| DN201 | 06:10–07:40, 07:40–09:10, 09:10–11:03 | Mostly onboard HSR; exit/upstairs **not** found | `relocalization/DN201/*.mp4` |

No auto-approval.

## Gates

All remain false: formal Seen/Unseen/Gold, train_exposed, pool freeze, expensive Track A RSI.  
run_001 untouched. Track A readiness document **not** auto-changed.

## Workbench

http://127.0.0.1:8770/ → **Seen Pilot run_002** (loads updated CATALOG clips for SP205).
