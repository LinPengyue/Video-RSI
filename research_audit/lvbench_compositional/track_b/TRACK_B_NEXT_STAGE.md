# TRACK B — Next Stage (full long-video compositional benchmark)

Date: 2026-10-29  
Exploratory CG-NEW-001…005 are **not** the full Track B goal.

## 1. This round deliverables

| Artifact | Path |
|---|---|
| Canonical ChatGPT QA (authority) | `../chatgpt_video_driven_qa/canonical_qa_proposals.jsonl` |
| Calibrated registry | `../chatgpt_video_driven_qa/cg_new_registry_canonical.jsonl` |
| Fallback snapshot (85138431) | `../chatgpt_video_driven_qa/fallback_snapshot_85138431.jsonl` |
| Mapping regression | `../chatgpt_video_driven_qa/MAPPING_REGRESSION.json` + unit test |
| Evidence index | `CG_NEW_EVIDENCE_INDEX.jsonl` |
| Second-round necessity scaffold | `cg_new_second_round_status.jsonl` + `NECESSITY_REVIEW_PREP.md` |
| Adjacent observation candidates | `adjacent_new_fact_candidates.jsonl` |
| Local media (gitignored) | `local_media/cg_new_round/` + `lvbench_cg_new_evidence_round.zip` (~34.6 MB) |

Mapping (must not regress):

| CG-NEW | seed | theme |
|---|---|---|
| 001 | TB-003 | animation role ↔ instruments |
| 002 | TB-007 | reverse temporal person track |
| 003 | TB-006 | AV animal link |
| 004 | TB-005 | lobster process (control) |
| 005 | TB-004 | sailor safety prep |

All remain `PROPOSED_*` / `UNASSIGNED`. No auto-`SUPPORTED`.

## 2. Method rule (hard)

Primary construction path:

`real video events → combinable facts → required ops → ChatGPT original QA → independent video review`

Banned as **main** generator: `Official QA1 + QA2 → rename → New QA`.

## 3. Second-round necessity (prep only)

For each CG-NEW, reviewers must separately judge:

1. **Video fact valid** (clip shows claimed event)
2. **Composition structure valid** (A alone / B alone insufficient; A+B needed; subject-swap changes answer)
3. **Strict unseen eval value** (novel signature vs contaminated / control)

Do **not** inherit single-clip conclusions from prior TB-001…007 human notes onto revised wording.

## 4. New-fact windows for ChatGPT (unverified)

Adjacent clips indexed with `verified_as_new_fact=false`. Cursor did **not** invent event labels. Priority observation classes:

- multi-role different actions
- cross-time identity match
- same-object state change
- reverse temporal link
- audio–visual complementary evidence
- condition → later outcome

See `adjacent_new_fact_candidates.jsonl`.

## 5. Full benchmark expansion (maintain in parallel)

Composition / signature coverage still thin. Next stage plan:

1. **Ops & signatures** — catalog primitives and legal composition signatures; mark covered vs missing (reverse temporal, AV bind, state-change, condition→result still under-covered for *strict unseen*).
2. **Video-type distribution** — target ≥20 videos across animation / drama / vlog / doc / sports; current CG-NEW uses contaminated public videos (TJR / Cm73 / LLS / evYm / vaL) → **cannot** be blind sealed final test.
3. **Annotation cost** — ~15–25 human min per dual-interval candidate; prefer 80–120 FACT_VERIFIED facts before large QA minting.
4. **Seen / Unseen leave-out** — signature leave-out + video leave-out; videos used in public ChatGPT/Cursor discussion excluded from sealed final.
5. **Independent video split** — train/dev construction videos ≠ sealed test videos.
6. **Sealed-test freeze conditions** — dual independent reviews; frozen media hashes; no method-side answer access; no post-hoc Unseen tuning.

Detail sketch remains in `BENCHMARK_EXPANSION_PLAN.md`.

## 6. Ask for ChatGPT next

1. Independent necessity judgments on CG-NEW-001…005 using evidence index + packs.
2. Optional new-fact designs from adjacent windows only after watching.
3. Additional **original** QA on **non-contaminated** videos for sealed-pool construction.
4. Do not batch-generate name-swap QA.

## Status

**Track B: canonical five imported; evidence indexed; necessity scaffold ready; full-benchmark plan active. No formal freeze.**
