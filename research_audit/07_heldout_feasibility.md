# 07 — Independent held-out video feasibility

Date: 2026-10-22  
Constraint: metadata and local inventory only; **no video download**.

Safe stats: `research_audit/e0_heldout_stats.safe.json`.

---

## LVBench video inventory

| Set | Independent `video_id` count | Source |
|---|---:|---|
| Official/local meta | **103** | `/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl` (103 unique `key`) |
| Local mp4 files | **103** | `/home/descfly/lpy/dataset/LVBench/videos/*.mp4` |
| Train split (seed 42) | **85** | `data/lvbench-split/train_items.jsonl` |
| Gate split (seed 42) | **18** | `data/lvbench-split/gate_items.jsonl` |
| Train ∩ Gate | **0** | set intersection |
| Train ∪ Gate | **103** | set union |

**VERIFIED:** `train_videos ∪ gate_videos == full LVBench 103 videos`.  
**VERIFIED:** `full − union = ∅` (zero remaining videos).  
**VERIFIED:** Train/Gate are video-disjoint from each other, but together they **exhaust** LVBench.

`sampling_summary.json` records `excluded_video_ids: []`.

Hashes from `reproduction/runtime_manifest.json` split block (for provenance):  
`combined_video_id_set_sha256 = c6d6a58702b183de2ce76963263a1bf2fcef1e78157a572603f9faefa1e50523`.

---

## Is there any unused LVBench video?

**No. VERIFIED.**

Therefore the original E0 plan — score `initial_harness` vs `H_S1` on a **new LVBench video-disjoint** set never used for train/investigation/Gate — **cannot be executed without fabricating non-disjoint “held-out” questions**.

Resampling different questions on Gate or Train videos is **not** video-disjoint held-out. Prior local work already documents this contamination mode:

- `patch_validation/pv0_video_exposure_audit.md`: eligible pool is same-video as train (1032/1032).
- `patch_validation/sr3_overlap_audit.md`: Fresh-20 UID-disjoint still shares videos with train risk screens.

---

## Prior experiment exposure (summary)

| Artifact | Videos relative to split | Implication |
|---|---|---|
| Action-space natural68 | 51 train videos, 0 gate | Uses train failures; not a held-out video pool |
| Editor train (216 Q) | 85 train videos | Investigation/evolution saw these videos |
| Gate (72 Q) | 18 gate videos | Used for **selection** of `H_S1` |
| Patch-validation / multipatch “fresh” pools | Drawn from remaining **questions** on already-seen videos | Same-video exposure |

**VERIFIED:** there is no LVBench video that is simultaneously outside train, outside Gate, and unused by the local seed-42 evolution setup.

**UNKNOWN (not blocking the exhaustion result):** exact video sets of every historical pilot JSON without reading multi‑MB dumps. Exhaustion of the 103-meta universe already falsifies LVBench held-out.

---

## Other VideoQA benchmarks (survey only; no download)

Local `/home/descfly/lpy/dataset` contains **only LVBench** (plus conversion scripts). No local MLVU / Video-MME / EgoSchema / LongVideoBench video trees were found.

Paper README reports those benchmarks as evaluation targets for the released method (`README.md` Results tables). For a future **cross-dataset** eval:

| Benchmark | Role if used | Labeling requirement |
|---|---|---|
| MLVU / Video-MME / LongVideoBench / EgoSchema | Possible **cross-dataset** generalization tests | Must be labeled **cross-dataset**, not “unseen LVBench” |
| New LVBench questions on Gate videos | Same-video / different-question | **Not** independent-video generalization |
| Re-split LVBench ignoring train∪gate | Would reuse selection/train videos | Invalid for the original E0 claim |

Availability of public downloads, licenses, and exact video overlap with LVBench IDs: **UNKNOWN** without fetching external metadata beyond this survey. Do not assume zero overlap across datasets without an ID audit.

---

## Terminology fence

| Term | Allowed meaning here |
|---|---|
| Video-disjoint held-out (LVBench) | Videos ∉ train ∪ gate — **empty set** |
| Same-distribution new questions | New items on already-seen LVBench videos — **contaminated for video-level generalization** |
| Cross-dataset generalization | Different benchmark corpus — **different claim** |

---

## Feasibility verdict

**STOP original E0 (LVBench independent-video test).**  
Do not create a fake held-out by reshuffling questions on the 103 videos.
